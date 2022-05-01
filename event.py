import time
import json
import os
import asyncio
import aiohttp


class Event:
    known_type = [None, '文字', '图片', 3, 4, '撤回', 6, '分享视频']
    def __init__(self, talker_id, data):
        '''信息事件类型
        talker_id: 对话者 uid 用于判断接收或是发送消息
        data 接收到的事件详细信息
        '''
        if isinstance(data, str):
            data = json.loads(data)
        self.data = data
        self.msg_type = '收到' if talker_id == data.get('sender_uid') else '发送'
        self.msg_content_type = data.get('msg_type')
        self.msg_seqno = data.get('msg_seqno')
        self.msg_key = data.get('msg_key')
        try:
            self.__content__()
        except Exception as e:
            print(f'[Error][{e}]{data}')
    
    def __str__(self):
        if self.msg_type == '收到':
            user_id = self.data.get('sender_uid')
        else:
            user_id = self.data.get('receiver_id')
        timestr = time.strftime("[%Y-%m-%d %H:%M:%S]", time.localtime(self.data.get('timestamp')))
        return f'{timestr}[MSG]: {self.msg_type} {user_id} {self.known_type[self.msg_content_type]} 信息: {self.content}'

    def __content__(self):
        cid = self.msg_content_type
        content = json.loads(self.data.get('content'))
        if cid == 1:
            self.content = content.get('content')
        elif cid == 2:
            self.url = content['url']
            self.content = '[BL:image,file={url}]'.format_map(content)
            asyncio.run_coroutine_threadsafe(self.download_pic(content['url'], str(self.msg_seqno)+'.png'), asyncio.get_event_loop())
        elif cid == 5:
            self.key = content
            self.content = f'[BL:withdraw,key={content}]'
        elif cid == 7:
            try:
                self.url = content['url']
                self.content = '[BL:video,url={url}]'.format_map(content)
            except Exception:
                self.url = content['title']
                self.content = '[BL:video,title={title}]'.format_map(content)

    def bl2cq(self):
        cid = self.msg_content_type
        if cid == 1:
            return self.content
        elif cid == 2:
            return f'[CQ:image,file={self.url}]'
        elif cid == 5:
            return f'撤回了消息 {self.key}'
        elif cid == 7:
            return f'分享了视频 {self.url}'

    async def download_pic(self, url: str, filename: str):
        async with aiohttp.ClientSession() as session:
            r = await session.get(url)
            with open(os.path.join('./data/images', filename), 'wb') as fp:
                fp.write(await r.read())