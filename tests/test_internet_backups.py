import contextlib,json,sqlite3,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from cryptography.fernet import Fernet,InvalidToken
from fastapi.testclient import TestClient
from tools.encrypted_learning_backup import create_snapshot,verify_snapshot,restore_snapshot
from tools.internet_service import private_visibility_check
from backend import internet_access,server
import test_workflow as workflow

class BackupTests(unittest.TestCase):
    def test_encrypted_roundtrip_preserves_records_and_excludes_recovery_and_push_keys(self):
        from backend.store import Store
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);runtime=root/'runtime';runtime.mkdir();db=Store(runtime/'clinical_tutor.sqlite3')
            uid=db.create_user('synthetic','123456','student','Synthetic learner')
            with db.tx() as c:
                c.execute('INSERT INTO logins(token_hash,user_id,expires) VALUES (?,?,?)',('synthetic-token-hash',uid,9999999999))
                db.event(c,uid,None,'observation',{'note':'synthetic confidential observation'})
                c.execute('INSERT INTO teacher_lessons VALUES (?,?,?,?,?,?)',('TEST',uid,1,'draft','{"title":"Synthetic lesson"}',1))
            private=runtime/'secrets';private.mkdir();(private/'smtp.key').write_bytes(Fernet.generate_key());(private/'github-private-backup').write_text('NEVER UPLOAD SSH PRIVATE KEY')
            db.conn.close()
            folder=root/'snapshot';meta=create_snapshot(runtime,folder,'test')
            self.assertTrue(meta['verified']);self.assertTrue(all(p.suffix=='.enc' for p in folder.iterdir()))
            self.assertFalse(any(b'confidential' in p.read_bytes() or b'NEVER UPLOAD' in p.read_bytes() for p in folder.iterdir()))
            target=root/'restored';restore_snapshot(folder,private/'backup-recovery.key',target)
            self.assertFalse((target/'runtime/secrets/backup-recovery.key').exists());self.assertFalse((target/'runtime/secrets/github-private-backup').exists())
            with contextlib.closing(sqlite3.connect(target/'runtime/clinical_tutor.sqlite3')) as restored:
                self.assertEqual(restored.execute('SELECT count(*) FROM events').fetchone()[0],1)
                self.assertEqual(restored.execute('SELECT count(*) FROM teacher_lessons').fetchone()[0],1)
                self.assertEqual(restored.execute('SELECT expires FROM logins').fetchone()[0],0)
            with self.assertRaises(ValueError):restore_snapshot(folder,private/'backup-recovery.key',target)
            wrong=root/'wrong.key';wrong.write_bytes(Fernet.generate_key())
            with self.assertRaises(InvalidToken):verify_snapshot(folder,wrong)
            part=folder/'part-00000.enc';part.write_bytes(part.read_bytes()+b'corrupt')
            with self.assertRaises(ValueError):verify_snapshot(folder,private/'backup-recovery.key')

    def test_public_or_unverifiable_repository_is_refused_before_learning_upload(self):
        import urllib.error,io
        with patch('urllib.request.urlopen',return_value=io.BytesIO(b'{"private":false}')):
            with self.assertRaises(RuntimeError):private_visibility_check()
        with patch('urllib.request.urlopen',side_effect=urllib.error.HTTPError('url',403,'Forbidden',{},None)):
            with self.assertRaises(RuntimeError):private_visibility_check()
        with patch('urllib.request.urlopen',side_effect=urllib.error.HTTPError('url',404,'Not Found',{},None)):private_visibility_check()

class InternetAccessTests(unittest.TestCase):
    setUp=workflow.WorkflowTests.setUp
    tearDown=workflow.WorkflowTests.tearDown
    def test_deployment_status_and_backup_control_require_administrator(self):
        self.db.create_user('manager','654321','admin');admin=TestClient(server.app)
        self.addCleanup(admin.close);admin.post('/api/auth/login',json={'username':'manager','password':'654321'})
        with patch.object(internet_access,'RUNTIME',Path(self.tmp.name)):
            self.assertEqual(self.alice.get('/api/admin/deployment').status_code,403)
            self.assertEqual(self.prof.post('/api/admin/deployment/backup').status_code,403)
            self.assertEqual(admin.post('/api/admin/deployment/backup').status_code,200)
            self.assertTrue((Path(self.tmp.name)/'backup-request').is_file())
            self.assertEqual(admin.get('/api/admin/deployment').json()['host_must_stay_online'],True)
    def test_internet_and_lan_have_distinct_voice_capabilities(self):
        from starlette.requests import Request
        def request(host):return Request({'type':'http','scheme':'https','server':(host,443),'headers':[(b'host',host.encode())],'path':'/'})
        self.assertTrue(internet_access.external(request('example.trycloudflare.com')))
        self.assertFalse(internet_access.external(request('192.168.68.108')))
        with patch.object(server.llm,'check') as check,patch.object(server.voice_bridge,'ready',return_value=True),patch.object(server.voice_agents,'available',return_value=True):
            check.return_value.to_dict.return_value={'ready':True}
            internet=server.service_status(request('example.trycloudflare.com'),{'role':'student'})
            self.assertFalse(internet['livekit_agent_configured']);self.assertEqual(internet['voice_transport'],'authenticated-http-audio')
            self.assertTrue(server.service_status(request('192.168.68.108'),{'role':'student'})['livekit_agent_configured'])
