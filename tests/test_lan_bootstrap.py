import asyncio,json,ssl,tempfile,unittest
from pathlib import Path
from tools.run_lan import certificates
from tools.lan_bootstrap import LanBootstrap
from tools.prepare_iphone_profile import create_profile

class LanBootstrapTests(unittest.IsolatedAsyncioTestCase):
    async def test_same_port_keeps_tls_valid_and_never_forwards_plaintext_login(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);directory=root/'runtime/lan-tls';(root/'web_portal').mkdir()
            cert,key=certificates(['127.0.0.1'],directory)
            create_profile(directory/'clinical-tutor-ca.cer',root/'web_portal/clinical-tutor-iphone.mobileconfig')
            context=ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER);context.load_cert_chain(cert,key)
            backend_requests=[]
            async def backend(reader,writer):
                request=await reader.readuntil(b'\r\n\r\n');backend_requests.append(request)
                body=b'{"status":"encrypted-test"}'
                writer.write(b'HTTP/1.1 200 OK\r\nContent-Length: '+str(len(body)).encode()+b'\r\nConnection: close\r\n\r\n'+body)
                await writer.drain();writer.close();await writer.wait_closed()
            secure=await asyncio.start_server(backend,'127.0.0.1',0,ssl=context)
            router=LanBootstrap(root,['192.168.68.108'],secure.sockets[0].getsockname()[1])
            listener=await asyncio.start_server(router.handle,'127.0.0.1',0,limit=8192);port=listener.sockets[0].getsockname()[1]
            async def request(data,tls=False):
                options={'ssl':ssl.create_default_context(cafile=str(directory/'clinical-tutor-ca.cer')),'server_hostname':'127.0.0.1'} if tls else {}
                reader,writer=await asyncio.open_connection('127.0.0.1',port,**options)
                writer.write(data);await writer.drain();response=await asyncio.wait_for(reader.read(),5);writer.close();await writer.wait_closed();return response
            try:
                setup=await request(b'GET /connect HTTP/1.1\r\nHost: local\r\nUser-Agent: iPhone\r\n\r\n')
                self.assertIn(b'200 OK',setup);self.assertIn('已連到教學主機'.encode(),setup)
                profile=await request(b'GET /clinical-tutor-iphone.mobileconfig HTTP/1.1\r\nHost: local\r\n\r\n')
                self.assertIn(b'application/x-apple-aspen-config',profile)
                blocked=await request(b'POST /api/auth/login HTTP/1.1\r\nHost: local\r\nContent-Length: 4\r\n\r\nnope')
                self.assertIn(b'405',blocked)
                private=await request(b'GET /api/me HTTP/1.1\r\nHost: local\r\n\r\n');self.assertIn(b'426',private)
                self.assertEqual(len(backend_requests),0)
                encrypted=await request(b'GET /health HTTP/1.1\r\nHost: local\r\n\r\n',tls=True)
                self.assertIn(b'encrypted-test',encrypted);self.assertEqual(len(backend_requests),1)
                log=(directory/'bootstrap-status.json').read_text();self.assertNotIn('nope',log)
                self.assertEqual(json.loads(log)['connections'][0]['device_hint'],'iPhone')
            finally:
                listener.close();secure.close();await listener.wait_closed();await secure.wait_closed()
