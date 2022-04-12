import asyncio
import logging
import os
import json

import aiohttp
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from database import DataBase as DB
from event import Event
from adapter import cqBot


class Bilihttp:
    logger = logging.getLogger('BILI')
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("[%(asctime)s][%(levelname)s]: %(message)s", '%Y-%m-%d %H:%M:%S'))
    logger.addHandler(handler)

    def __init__(self, headers, debug=False):
        self.maxSeqno = 0
        self.headers = headers
        self.adapter = None
        self.sched = AsyncIOScheduler()
        if debug:
            self.logger.setLevel(logging.DEBUG)
        else:
            self.logger.setLevel(logging.INFO)

        if not os.path.exists('./data'):
            os.mkdir('./data')
        if not os.path.exists('./data/images'):
            os.mkdir('./data/images')
        if not os.path.exists('./data/sqlite'):
            os.mkdir('./data/sqlite')


    def __del__(self):
        asyncio.get_event_loop().run_until_complete(self.session.close())

    def setAdapter(self, adapter: cqBot):
        self.adapter = adapter

    async def fetch_session_msgs(self, talker_id: str, begin_seqno: int = 0):
        url = 'https://api.vc.bilibili.com/svr_sync/v1/svr_sync/fetch_session_msgs'
        params = {
            'talker_id': talker_id,
            'session_type': 1,
            'begin_seqno': begin_seqno
        }

        r = await self.session.get(url, params=params)
        js = await r.json()

        if js['data']['messages']:
            self.maxSeqno = max(self.maxSeqno, js['data']['messages'][0]['msg_seqno'])
            events = [Event(talker_id, message) for message in js['data']['messages']][::-1]
            return events
        else:
            return []

    async def run(self, uid):
        self.session = aiohttp.ClientSession(headers=self.headers)

        db = DB(uid)
        uid = int(uid)

        @self.sched.scheduled_job('interval', seconds=3)
        async def qurey():
            self.logger.debug('heartbeat')
            events = await self.fetch_session_msgs(uid, self.maxSeqno)
            for event in events:
                if not db.query(seqno=event.msg_seqno):
                    print(event)
                    if self.adapter:
                        if not event.msg_content_type == 5:
                            await self.adapter.send_private_msg(3099665076, event.bl2cq())
                    db.insert(event.msg_seqno, event.msg_key, event.data)
                    if event.msg_content_type == 5:
                        msg = db.query('MSG', key=event.key)
                        if msg:
                            wdevent = Event(uid, msg[0])
                            self.logger.info(f'撤回消息 key={event.key} 内容\n>>>{wdevent}')
                            await self.adapter.send_private_msg(3099665076, f'{event.bl2cq()}:\n{wdevent.bl2cq()}')
                        else:
                            self.logger.error(f'尝试找回撤回消息 key={event.key} 内容失败')
                            await self.adapter.send_private_msg(3099665076, f'{event.bl2cq()}\n尝试找回撤回消息失败')
            db.save()

        self.sched.start()
        if self.adapter:
            await self.adapter.connect()
            await self.adapter.run()

Headers = {
    'Connection': 'keep-alive',
    'Accept-Language': 'zh-CN,zh;q=0.9',
    'Accept-Encoding': 'gzip, deflate',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8',
    'Upgrade-Insecure-Requests': '1',
    'User-Agent': 'Mozilla/5.0 (Windows NT 6.1; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/62.0.3202.62 Safari/537.36',
    'cookie': ''
}


async def main():
    with open('./config.json', 'r', encoding='utf-8') as fp:
        config = json.load(fp)
        uid = config['uid']
        url = config.get('url')
        Headers['cookie'] = config['cookie']

    bh = Bilihttp(Headers, True)
    if url:
        bh.setAdapter(cqBot(url, True))
    await bh.run(uid)


loop = asyncio.get_event_loop()
loop.run_until_complete(main())
loop.run_forever()
