# 已经绝赞移植到 [bilibili_api/session.py](https://github.com/Nemo2011/bilibili-api/blob/main/bilibili_api/session.py)

**bilihttp** 的 **Python** 实现

需要同目录下 **config.json** 文件存在，若不存在将自动生成

```json
{
    "url": "ws://127.0.0.1:2434",
    "cookie": ""
}
```
其中
```url``` 为待连接 ```go-cqhttp``` 的 ```websocket``` 地址。为空表示不连接 ```go-cqhttp```

```cookie``` 为自己的b站 ```cookie``` 字符，若不存在此项将模拟扫码登录。

会将二维码保存为同级目录下 ```qrcode.png``` 并尝试打开，扫码完成后会自动填写此项。
