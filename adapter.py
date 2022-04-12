import json
import asyncio
import logging

from aiowebsocket.converses import AioWebSocket


class cqBot():
    logger = logging.getLogger('cqBot')
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("[cqBot] [%(asctime)s] [%(levelname)s]: %(message)s", '%Y-%m-%d %H:%M:%S'))
    logger.addHandler(handler)

    def __init__(self, url: str = 'ws://127.0.0.1:2434', debug=False):
        self.url = url
        self.converse = None
        if debug:
            self.logger.setLevel(logging.DEBUG)
        else:
            self.logger.setLevel(logging.INFO)

    async def connect(self):
        while not self.converse:
            try:
                async with AioWebSocket(self.url) as aws:
                    self.converse = aws.manipulator
            except Exception:
                self.logger.debug('重连中...')
                await asyncio.sleep(3)
        await asyncio.sleep(1)

    async def run(self):
        recv = self.converse.receive
        while True:
            mes = await recv()
            self.logger.debug(f'收到信息：{mes.decode("utf-8").strip()}')

    async def send(self, cmd):
        if isinstance(cmd, str):
            await self.converse.send(cmd)
        else:
            try:
                js = json.dumps(cmd, ensure_ascii=False)
                await self.converse.send(js)
            except Exception as e:
                self.logger.error('发送失败 '+str(e))

    async def send_private_msg(self, user_id, text):
        await self.send({
            'action': 'send_private_msg',
            'params': {
                'user_id': int(user_id),
                'message': str(text)
            }
        })

    async def send_group_msg(self, group_id, text):
        await self.send({
            'action': 'send_group_msg',
            'params': {
                'group_id': int(group_id),
                'message': str(text)
            }
        })
