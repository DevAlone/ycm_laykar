import asyncio
import aiohttp
import json
import traceback
import random
import sys


def log(*args, **kwargs):
    print(*args, **kwargs)
    sys.stdout.flush()


ITEMS_PER_CYCLE = 50
class ItemDeletedException(BaseException):
    pass


def get_session_key():
    with open('.secret_session') as file:
        return file.read().strip()


def get_cookies():
    return {
        'PHPSESSID_production-main': get_session_key(),
    }


async def like_item(item_id, session, recursion_limiter=10):
    if recursion_limiter <= 0:
        raise Exception('recursion depth exceded')
    
    base_url = 'http://youcomedy.me/items/{}/like'
    headers = {
        'X-Requested-With': 'XMLHttpRequest'
    }
    
    async with session.get(base_url.format(item_id), headers=headers) as resp:
        json_result = json.loads(await resp.text())
        if 'error_text' in json_result and json_result['error_text'] == 'Шутка удалена':
            raise ItemDeletedException()
            
        # log(json_result)
        if json_result['userVote'] <= 0:
            await like_item(item_id, session, recursion_limiter - 1)


async def main():
    while True:
        try:
            cookies = get_cookies()
            async with aiohttp.ClientSession(cookies=cookies) as session:
                async with session.get('http://youcomedy.me/user/newlaikar/liked/list?page=1') as resp:
                    json_result = json.loads(await resp.text())
                    
                    maximum_id = max(json_result['items'], key=lambda x: x['id'])['id']
                
                for i in range(maximum_id, maximum_id + ITEMS_PER_CYCLE):
                    try:
                        await like_item(i, session)
                        log('item {} liked'.format(i))
                    except ItemDeletedException:
                        log('item {} deleted'.format(i))
                
        except BaseException as ex:
            log(type(ex))
            log(ex)
            traceback.print_exc()
            await asyncio.sleep(30)
        finally:
            await asyncio.sleep(random.randint(1, 3))


if __name__ == '__main__':
    asyncio.get_event_loop().run_until_complete(main())
