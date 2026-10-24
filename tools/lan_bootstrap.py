"""One LAN port: encrypted traffic goes to TLS; plain HTTP serves setup only.

No plaintext request is forwarded to the authenticated application. The CA
fingerprint must be checked against the trusted GitHub Pages copy on clients.
"""
import asyncio,json,time,html,hashlib
from collections import deque
from pathlib import Path
from urllib.parse import urlsplit

class LanBootstrap:
    def __init__(self,root,addresses,tls_port,public_port=8765):
        self.root=Path(root);self.addresses=list(addresses);self.tls_port=tls_port;self.public_port=public_port
        self.connections=deque(maxlen=80)

    def record(self,writer,protocol,device='unknown'):
        peer=writer.get_extra_info('peername')
        self.connections.append({'at':time.time(),'client_ip':peer[0] if peer else 'unknown','protocol':protocol,'device_hint':device})
        target=self.root/'runtime/lan-tls/bootstrap-status.json'
        target.parent.mkdir(parents=True,exist_ok=True)
        target.write_text(json.dumps({'connections':list(self.connections),'plaintext_setup_only':True},indent=2),encoding='utf-8')

    def setup_page(self):
        address=html.escape(self.addresses[0]);base=f'https://{address}:{self.public_port}'
        certificate=self.root/'runtime/lan-tls/clinical-tutor-ca.cer'
        fingerprint=hashlib.sha256(certificate.read_bytes()).hexdigest() if certificate.exists() else 'unavailable'
        return f'''<!doctype html><html lang="zh-Hant"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>已連到教學主機</title><style>body{{background:#edf5f4;color:#183e49;font:17px/1.8 system-ui;margin:0}}main{{max-width:680px;margin:auto;padding:24px}}section{{background:white;padding:20px;border-radius:16px;margin:20px 0}}a{{color:#106c73}}code{{overflow-wrap:anywhere;font-size:12px}}h1{{font-size:27px}}</style><main><h1>已連到教學主機</h1><p>這支手機已能透過區域網路連到這台電腦。接下來設定 HTTPS 憑證後，即可登入及使用麥克風。</p><section><h2>iPhone 安裝步驟</h2><ol><li>請使用獨立的 Safari。</li><li><a href="/clinical-tutor-iphone.mobileconfig">下載本機 CA 憑證描述檔</a>，到「設定 → 一般 → VPN 與裝置管理」安裝。</li><li>到「一般 → 關於本機 → 憑證信任設定」，啟用 Clinical Tutor Local Network CA。</li><li><a href="{base}/static/connection-check.html">開啟 HTTPS 與麥克風檢查</a>。</li><li><a href="{base}/login">前往 HTTPS 登入</a>。</li></ol></section><section><h2>核對憑證來源</h2><p>請先在 <a href="https://poemcheng.github.io/spiral-clinical-tutor-v5/">GitHub 公開入口</a> 核對這台主機 CA 檔案的 SHA256。只安裝您信任的教學主機憑證；不使用時可移除描述檔。</p><code>{fingerprint}</code><p>本頁只有連線與安裝說明，不接收帳號、密碼或學習資料。</p></section></main></html>'''.encode('utf-8')

    def response(self,method,path):
        if method not in ('GET','HEAD'):
            return 405,'text/plain; charset=utf-8',b'Use HTTPS for all application requests.'
        path=urlsplit(path).path
        if path in ('/','/connect','/setup'):
            return 200,'text/html; charset=utf-8',self.setup_page()
        if path=='/health':
            return 200,'application/json',json.dumps({'status':'ok','mode':'public-setup-only','https_port':self.public_port}).encode()
        files={'/clinical-tutor-iphone.mobileconfig':('web_portal/clinical-tutor-iphone.mobileconfig','application/x-apple-aspen-config'),
               '/clinical-tutor-ca.cer':('runtime/lan-tls/clinical-tutor-ca.cer','application/x-x509-ca-cert')}
        if path in files:
            filename,mime=files[path];target=self.root/filename
            if target.is_file():return 200,mime,target.read_bytes()
        return 426,'text/plain; charset=utf-8',b'Use HTTPS for login and the training application. Open http://HOST:8765/connect for setup.'

    async def handle(self,reader,writer):
        upstream=None;tasks=[]
        try:
            first=await asyncio.wait_for(reader.read(1),timeout=8)
            if not first:return
            if first==b'\x16':
                self.record(writer,'TLS')
                other,upstream=await asyncio.open_connection('127.0.0.1',self.tls_port)
                upstream.write(first);await upstream.drain()
                async def pipe(source,target):
                    while True:
                        data=await asyncio.wait_for(source.read(65536),timeout=300)
                        if not data:return
                        target.write(data);await target.drain()
                tasks=[asyncio.create_task(pipe(reader,upstream)),asyncio.create_task(pipe(other,writer))]
                await asyncio.wait(tasks,return_when=asyncio.FIRST_COMPLETED)
            elif first in b'GHPOST':
                headers=first+await asyncio.wait_for(reader.readuntil(b'\r\n\r\n'),timeout=8)
                if len(headers)>8192:return
                lines=headers.decode('latin1').split('\r\n');parts=lines[0].split()
                if len(parts)!=3:return
                method,path,_=parts
                device='iPhone' if any('iphone' in line.lower() for line in lines if line.lower().startswith('user-agent:')) else 'other'
                self.record(writer,'HTTP setup',device)
                status,mime,body=self.response(method,path)
                reasons={200:'OK',405:'Method Not Allowed',426:'Upgrade Required'}
                response=(f'HTTP/1.1 {status} {reasons[status]}\r\nContent-Type: {mime}\r\nContent-Length: {len(body)}\r\nCache-Control: no-store\r\nX-Content-Type-Options: nosniff\r\nConnection: close\r\n\r\n').encode()
                writer.write(response+(b'' if method=='HEAD' else body));await writer.drain()
        except (asyncio.TimeoutError,asyncio.IncompleteReadError,asyncio.LimitOverrunError,ConnectionError,OSError,ValueError):
            pass
        finally:
            for task in tasks:task.cancel()
            if tasks:await asyncio.gather(*tasks,return_exceptions=True)
            for stream in (upstream,writer):
                if stream:
                    stream.close()
                    try:await stream.wait_closed()
                    except (ConnectionError,OSError):pass

    async def serve(self,host='0.0.0.0'):
        server=await asyncio.start_server(self.handle,host,self.public_port,limit=8192)
        async with server:await server.serve_forever()
