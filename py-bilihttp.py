import asyncio
from email import header
import json
import logging
import os
import sqlite3
import time

import aiohttp
from apscheduler.schedulers.asyncio import AsyncIOScheduler


class Event:
    known_type = [None, '文字', '图片', 3, 4, '撤回', 6, '分享视频']
    def __init__(self, talker_id, data) -> None:
        if isinstance(data, str):
            data = json.loads(data)
        self.data = data
        self.msg_type = '收到' if talker_id == data.get('sender_uid') else '发送'
        self.msg_content_type = data.get('msg_type')
        self.msg_seqno = data.get('msg_seqno')
        self.msg_key = data.get('msg_key')
    
    def __str__(self):
        self.__content__()
        if self.msg_type == '收到':
            user_id = self.data.get('sender_uid')
        else:
            user_id = self.data.get('receiver_id')
        timestr = time.strftime("[%Y/%m/%d %H:%M:%S]", time.localtime(self.data.get('timestamp')))
        return f'{timestr}{self.msg_type} {user_id} {self.known_type[self.msg_content_type]} 信息: {self.content}'

    def __content__(self):
        cid = self.msg_content_type
        content = json.loads(self.data.get('content'))
        if cid == 1:
            self.content = content.get('content')
        elif cid == 2:
            self.content = '[BL:image,file={url}]'.format_map(content)
        elif cid == 5:
            self.key = content
            self.content = f'[BL:withdraw,key={content}]'
        elif cid == 7:
            self.content = '[BL:video,url={url}]'.format_map(content)



class Bilihttp:
    logger = logging.getLogger('BILI')
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("[%(asctime)s][%(levelname)s]: %(message)s", '%Y-%m-%d %H:%M:%S'))
    logger.addHandler(handler)

    def __init__(self, headers, debug=False):
        self.maxSeqno = 0
        self.headers = headers
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
            events = [Event(talker_id, message) for message in js['data']['messages']][::-1]
            for event in events:
                self.maxSeqno = max(self.maxSeqno, event.msg_seqno)
                print(event)
            return events
        else:
            return []

    async def run(self, uid):
        self.session = aiohttp.ClientSession(headers=self.headers)

        conn = sqlite3.connect(f'./data/sqlite/{uid}.db', check_same_thread=False)
        c = conn.cursor()
        c.execute('CREATE TABLE IF NOT EXISTS DATA(SEQNO INT PRIMARY KEY,MKEY INT,MSG TEXT);')

        uid = int(uid)

        @self.sched.scheduled_job('interval', seconds=3)
        async def qurey():
            self.logger.debug('heartbeat')
            events = await self.fetch_session_msgs(uid, self.maxSeqno)
            for event in events:
                if event.msg_content_type == 5:
                    msg = c.execute(f'SELECT MSG FROM DATA WHERE MKEY = {event.key};').fetchone()[0]
                    print(f'撤回消息 key={event.key} 内容', Event(uid, msg))
                if not c.execute(f'SELECT * FROM DATA WHERE SEQNO = {event.msg_seqno};').fetchone():
                    c.execute('INSERT INTO DATA (SEQNO,MKEY,MSG) VALUES (?,?,?);', (event.msg_seqno, event.msg_key, json.dumps(event.data, indent=4, ensure_ascii=False)))
            conn.commit()

        self.sched.start()

Headers = {
    'Connection': 'keep-alive',
    'Accept-Language': 'zh-CN,zh;q=0.9',
    'Accept-Encoding': 'gzip, deflate',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8',
    'Upgrade-Insecure-Requests': '1',
    'User-Agent': 'Mozilla/5.0 (Windows NT 6.1; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/62.0.3202.62 Safari/537.36',
    'cookie': ''
}


with open('./config.txt', 'r', encoding='utf-8') as f:
    uid, cookies = f.read().split('\n')
    Headers['cookie'] = cookies

bh = Bilihttp(Headers)
loop = asyncio.get_event_loop()
loop.run_until_complete(bh.run(uid))
loop.run_forever()
