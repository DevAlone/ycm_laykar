import asyncio
import aiohttp
import json
import traceback
import random
import sys


def log(*args, **kwargs):
    print(*args, **kwargs)
    sys.stdout.flush()


ITEMS_PER_CYCLE = 32
LIKED_FEED_URL = 'http://youcomedy.me/user/newlaikar/liked/list?page=1'


class ItemDeletedException(BaseException):
    pass


class CommentDeletedException(BaseException):
    pass


def get_session_key():
    with open('.secret_session') as file:
        return file.read().strip()


def get_cookies():
    return {
        'PHPSESSID_production-main': get_session_key(),
    }


async def like(item_id, session, recursion_limiter, is_comment):
    if recursion_limiter <= 0:
        raise Exception('recursion depth exceeded')

    if is_comment:
        base_url = 'http://youcomedy.me/comments/{}/like'
    else:
        base_url = 'http://youcomedy.me/items/{}/like'

    headers = {
        'X-Requested-With': 'XMLHttpRequest'
    }

    async with session.get(base_url.format(item_id), headers=headers) as resp:
        json_result = json.loads(await resp.text())

        if 'error_text' in json_result:
            if is_comment and json_result['error_text'] == 'Нет такого комментария':
                raise CommentDeletedException()
            elif not is_comment and json_result['error_text'] == 'Шутка удалена':
                raise ItemDeletedException()
            else:
                raise Exception('some error: {}'.format(json_result))
        elif 'rating' not in json_result:
            raise Exception(
                "shit happened, "
                "it's most like because of bad authorization: {}".format(
                    json_result
                )
            )

        if json_result['userVote'] <= 0:
            await like(item_id, session, recursion_limiter - 1, is_comment)


async def like_item(item_id, session, recursion_limiter=10):
    await like(item_id, session, recursion_limiter, is_comment=False)


async def like_comment(comment_id, session, recursion_limiter=10):
    await like(comment_id, session, recursion_limiter, is_comment=True)


async def set_last_item_id(item_id):
    with open('.secret_last_item_id', 'w') as f:
        f.write(str(item_id))


async def get_last_item_id(session):
    try:
        with open('.secret_last_item_id') as f:
            return int(f.read().strip())
    except FileNotFoundError:
        async with session.get(LIKED_FEED_URL) as resp:
            json_result = json.loads(await resp.text())
            if not json_result['items']:
                return 1

            maximum_id = max(
                json_result['items'], key=lambda x: x['id']
            )['id']
            await set_last_item_id(maximum_id)

            return maximum_id


async def set_last_comment_id(item_id):
    with open('.secret_last_comment_id', 'w') as f:
        f.write(str(item_id))


async def get_last_comment_id():
    try:
        with open('.secret_last_comment_id') as f:
            return int(f.read().strip())
    except FileNotFoundError:
        set_last_comment_id(1)

        return 1


async def process_item(item_id, session):
    log('start processing item {}'.format(item_id))
    try:
        await like_item(item_id, session)
        log('item {} liked'.format(item_id))
    except ItemDeletedException:
        log('item {} deleted'.format(item_id))
        await asyncio.sleep(60)
        raise
    finally:
        await asyncio.sleep(1)


async def process_comment(comment_id, session):
    log('start processing comment {}'.format(comment_id))
    try:
        await like_comment(comment_id, session)
        log('comment {} liked'.format(comment_id))
    except (CommentDeletedException, ItemDeletedException):
        log('comment {} deleted'.format(comment_id))
        await asyncio.sleep(10)
        raise
    finally:
        await asyncio.sleep(1)


async def moving_forward_items_processor(session):
    while True:
        try:
            maximum_id = await get_last_item_id(session)

            for i in range(maximum_id + 1, maximum_id + 1 + ITEMS_PER_CYCLE):
                await process_item(i, session)
                await set_last_item_id(i)
        except (ItemDeletedException, CommentDeletedException):
            pass
        except:
            traceback.print_exc()
            await asyncio.sleep(60)
        finally:
            await asyncio.sleep(random.randint(5, 60))


async def moving_forward_comments_processor(session):
    while True:
        try:
            maximum_id = await get_last_comment_id()

            for i in range(maximum_id + 1, maximum_id + 1 + ITEMS_PER_CYCLE):
                await process_comment(i, session)
                await set_last_comment_id(i)
        except (ItemDeletedException, CommentDeletedException):
            pass
        except:
            traceback.print_exc()
            await asyncio.sleep(60)
        finally:
            await asyncio.sleep(random.randint(5, 15))


async def recommendations_processor(session):
    while True:
        base_url = 'http://youcomedy.me/recommend/load'\
            '?page=0&rand=0.{}'.format(random.randint(1000000, 9999999))
        try:
            async with session.get(base_url) as resp:
                json_result = json.loads(await resp.text())
                for item in json_result['items']:
                    await process_item(int(item['id']), session)
                else:
                    await asyncio.sleep(120)
        except:
            traceback.print_exc()
            await asyncio.sleep(30)
        finally:
            await asyncio.sleep(random.randint(10, 30))


async def main():
    cookies = get_cookies()
    async with aiohttp.ClientSession(cookies=cookies) as session:
        await asyncio.gather(*[
            moving_forward_items_processor(session),
            recommendations_processor(session),
            moving_forward_comments_processor(session),
        ])


if __name__ == '__main__':
    asyncio.get_event_loop().run_until_complete(main())
