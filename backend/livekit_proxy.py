"""Authenticated same-origin signalling proxy; media remains WebRTC/DTLS.

Only /rtc signalling is forwarded to the fixed locally configured LiveKit URL.
"""
import asyncio
from urllib.parse import urlsplit,urlunsplit
from fastapi import HTTPException,WebSocket,WebSocketDisconnect
from fastapi.responses import Response
from .voice_bridge import settings

def target(path,query,websocket=False):
    if path!='rtc' and not path.startswith('rtc/'):raise HTTPException(404,'未知即時語音路徑。')
    p=urlsplit(settings()['LIVEKIT_URL'])
    if p.hostname not in ('127.0.0.1','localhost','::1'):raise HTTPException(503,'同網路代理僅轉送本機 LiveKit。')
    scheme=('wss' if p.scheme=='wss' else 'ws') if websocket else ('https' if p.scheme=='wss' else 'http')
    return urlunsplit((scheme,p.netloc,'/'+path,query,''))

def install(app,current_user,cookie):
    @app.api_route('/livekit/{path:path}',methods=['GET','POST'])
    async def http_proxy(path:str,request:__import__('fastapi').Request):
        import httpx
        current_user(request.cookies.get(cookie))
        url=target(path,request.url.query)
        async with httpx.AsyncClient(timeout=15) as client:
            result=await client.request(request.method,url,content=await request.body(),headers={'content-type':request.headers.get('content-type','application/json')})
        return Response(result.content,status_code=result.status_code,media_type=result.headers.get('content-type'),headers={'Cache-Control':'no-store'})
    @app.websocket('/livekit/{path:path}')
    async def websocket_proxy(socket:WebSocket,path:str):
        import aiohttp
        try:
            current_user(socket.cookies.get(cookie))
            origin=socket.headers.get('origin')
            if origin and urlsplit(origin).netloc!=socket.headers.get('host'):raise HTTPException(403,'跨來源即時語音被拒絕。')
            url=target(path,socket.url.query,True)
        except HTTPException:
            await socket.close(code=1008);return
        async with aiohttp.ClientSession() as client:
            async with client.ws_connect(url) as upstream:
                await socket.accept()
                async def incoming():
                    while True:
                        packet=await socket.receive()
                        if packet['type']=='websocket.disconnect':break
                        if packet.get('bytes') is not None:await upstream.send_bytes(packet['bytes'])
                        elif packet.get('text') is not None:await upstream.send_str(packet['text'])
                async def outgoing():
                    async for packet in upstream:
                        if packet.type==aiohttp.WSMsgType.BINARY:await socket.send_bytes(packet.data)
                        elif packet.type==aiohttp.WSMsgType.TEXT:await socket.send_text(packet.data)
                tasks=[asyncio.create_task(incoming()),asyncio.create_task(outgoing())]
                try:await asyncio.wait(tasks,return_when=asyncio.FIRST_COMPLETED)
                finally:
                    for t in tasks:t.cancel()
                    await asyncio.gather(*tasks,return_exceptions=True)
