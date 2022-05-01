import asyncio
import json
import logging
import os

import aiohttp
import qrcode
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from adapter import cqBot
from database import DataBase as DB
from event import Event


class Bilihttp:
    logger = logging.getLogger('BILI')
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("[%(asctime)s][%(levelname)s]: %(message)s", '%Y-%m-%d %H:%M:%S'))
    logger.addHandler(handler)

    def __init__(self, headers, adapter: cqBot, debug=False):
        self.maxSeqno = 0
        self.maxTs = 0
        self.headers = headers
        self.adapter = adapter if adapter.url else None
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
        
        self.db = DB()

    def __del__(self):
        self.db.close()
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

        events = []
        if js['data']['messages']:
            self.maxSeqno = max(self.maxSeqno, js['data']['messages'][0]['msg_seqno'])
            events = [Event(talker_id, message) for message in js['data']['messages']][::-1]
        return talker_id, events

    def send(self, content):
        if self.adapter:
            asyncio.run_coroutine_threadsafe(self.adapter.send_private_msg(3099665076, content), loop)

    def callback(self, task):
        talker_id, events = task.result()
        for event in events:
            if not self.db.query(seqno=event.msg_seqno):
                print(event)
                if not event.msg_content_type == 5:
                    self.send(event.bl2cq())
                self.db.insert(event.msg_seqno, event.msg_key, talker_id, event.data)
                if event.msg_content_type == 5:
                    msg = self.db.query('MSG', key=event.key)
                    if msg:
                        wdevent = Event(talker_id, msg[0])
                        self.logger.info(f'撤回消息 key={event.key} 内容\n>>>{wdevent}')
                        self.send(f'{event.bl2cq()}:\n{wdevent.bl2cq()}')
                    else:
                        self.logger.error(f'尝试找回撤回消息 key={event.key} 内容失败')
                        self.send(f'{event.bl2cq()}\n尝试找回撤回消息失败')
        self.db.save()

    async def new_sessions(self, begin_ts: int = 0):
        url = f'https://api.vc.bilibili.com/session_svr/v1/session_svr/new_sessions?begin_ts={begin_ts}'
        r = await self.session.get(url)
        js = await r.json()

        tasks = []

        if js['data']['session_list']:
            for session in js['data']['session_list']:
                begin_ts = max(begin_ts, session['session_ts'])
                self.logger.debug(f"获取到对话 {session['talker_id']}: {session['last_msg']['content']}")

                task = asyncio.create_task(self.fetch_session_msgs(session['talker_id']))
                task.add_done_callback(self.callback)
                tasks.append(task)

        if tasks:
            await asyncio.wait(tasks)
        return begin_ts

    async def login(self):
        '通过扫描二维码模拟登录B站并获取cookies'

        # 获取 oauthKey 以生成二维码
        r = await self.session.get('https://passport.bilibili.com/qrcode/getLoginUrl')
        js = (await r.json())['data']

        # 验证时要发送的数据
        check_data = {'oauthKey': js['oauthKey']}

        # 生成图片展示并保存
        qrimg = qrcode.make(js['url'])
        qrimg.show()
        qrimg.save('qrcode.png')

        # 间隔 3 秒轮询扫码状态
        while True:
            self.logger.debug('检测登录状态')
            await asyncio.sleep(3)

            r = await self.session.post('https://passport.bilibili.com/qrcode/getLoginInfo', data=check_data)
            js = await r.json()
            if js['status']:
                self.logger.debug(js)
                await self.session.get(js['data']['url']) # 访问此网站更新cookies
                self.logger.info('登录成功')   

                # 保存cookies到本地文件
                cookies = self.session.cookie_jar.filter_cookies("https://message.bilibili.com")
                cookies = str(cookies).replace('\r\nSet-Cookie: ', ';').replace('Set-Cookie: ', '')
                with open('./config.json', 'w', encoding='utf-8') as fp:
                    config.update({'cookie': cookies})
                    json.dump(config, fp, indent=4, ensure_ascii=False)
                self.logger.debug(cookies)
                break

    async def run(self):
        self.session = aiohttp.ClientSession(headers=self.headers) # 初始化请求会话

        # 配置文件中没有 cookies 通过扫码模拟登录
        if not self.headers['cookie']:
            await self.login()

        # 间隔 3 秒轮询消息列表
        @self.sched.scheduled_job('interval', seconds=3)
        async def qurey():
            self.maxTs = await self.new_sessions(self.maxTs)
            self.logger.debug(f'maxTs = {self.maxTs}')

        self.sched.start()

        # 如果有适配器则连接 go-cqhttp
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

# 读取配置文件
if not os.path.exists('./config.json'):
    with open('./config.json', 'w', encoding='utf-8') as fp:
        fp.write('{}')
with open('./config.json', 'r', encoding='utf-8') as fp:
    config = json.load(fp)
    url = config.get('url') # go-cqhttp 地址
    Headers['cookie'] = config.get('cookie', '') # 账号 cookies

bh = Bilihttp(Headers, adapter=cqBot(url, True), debug=True)

# 获取事件循环并运行爬虫
loop = asyncio.get_event_loop()
loop.run_until_complete(bh.run())
loop.run_forever()
