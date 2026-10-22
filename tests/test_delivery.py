import contextlib
import hashlib
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch
import zipfile
from fastapi.testclient import TestClient
from backend import server
from backend.store import Store
from tools.import_v3 import import_v3
from tools.backup_bundle import restore_backup


class DeliveryTests(unittest.TestCase):
    def test_repeated_launcher_opens_distinct_signin_urls_on_running_server(self):
        import run as launcher
        from backend import config
        with tempfile.TemporaryDirectory() as temp,patch.object(config,'RUNTIME',Path(temp)),patch.object(launcher,'probe_server',return_value={'product':'clinical-tutor','version':'4.4.2','login_entry':'/login'}),patch.object(launcher.webbrowser,'open',return_value=True) as opener:
            first=launcher.open_login_when_ready('http://127.0.0.1:8700')
            second=launcher.open_login_when_ready('http://127.0.0.1:8700')
            self.assertNotEqual(first,second)
            self.assertTrue(first.startswith('http://127.0.0.1:8700/login?launch='))
            self.assertEqual(opener.call_count,2)
            for call in opener.call_args_list:self.assertEqual(call.kwargs,{'new':2,'autoraise':True})
            self.assertEqual(len((Path(temp)/'launcher.log').read_text().splitlines()),2)

    def test_launcher_uses_fresh_root_for_older_running_server(self):
        import run as launcher
        self.assertTrue(launcher.login_url('http://127.0.0.1:8700',{'version':'4.4.1'}).startswith('http://127.0.0.1:8700/?launch='))

    def test_windows_javascript_mime(self):
        client=TestClient(server.app)
        self.assertIn('javascript',client.get('/static/app.js').headers['content-type'])
        self.assertIn('javascript',client.get('/static/vendor/avatar.bundle.js').headers['content-type'])
        client.close()

    def test_v3_import_preserves_evidence_and_does_not_adopt_unreviewed_level(self):
        with tempfile.TemporaryDirectory() as temp:
            source=Path(temp)/'v3.sqlite3'
            with contextlib.closing(sqlite3.connect(source)) as c:
                c.executescript('''CREATE TABLE learners(id INTEGER,learner_code TEXT,profession TEXT);
                  CREATE TABLE sessions(id INTEGER,learner_id INTEGER,selected_symptom TEXT,case_id TEXT,
                   baseline_level TEXT,learning_completed INTEGER,kdp_json TEXT,chat_json TEXT,report_text TEXT);
                  INSERT INTO learners VALUES (7,'old-learner','DT');''')
                c.execute('INSERT INTO sessions VALUES (?,?,?,?,?,?,?,?,?)',(11,7,'肌少症','SARC-DT-001','Level 5',1,
                   json.dumps([{'kdp_id':'SARCDT-KDP1','score':2,'feedback':'舊版回饋'}]),
                   json.dumps([{'role':'user','content':'舊版學員對話證據'}]),''));c.commit()
            before=hashlib.sha256(source.read_bytes()).hexdigest()
            with contextlib.closing(Store(Path(temp)/'v4.sqlite3').conn) as conn:
                pass
            target=Store(Path(temp)/'v4.sqlite3');target.create_user('mapped','Synthetic-2026-password','student')
            try:
                self.assertEqual(import_v3(source)['supported_sessions'],1)
                first=import_v3(source,{'7':'mapped'},True,target)
                self.assertEqual(first['imported'],1)
                self.assertEqual(import_v3(source,{'7':'mapped'},True,target)['skipped'],1)
                s=target.one('SELECT * FROM sessions')
                self.assertEqual(s['step'],4);self.assertEqual(s['level'],1)
                self.assertEqual(json.loads(s['data'])['legacy_raw']['baseline_level'],'Level 5')
                self.assertEqual(target.one('SELECT content FROM messages')['content'],'舊版學員對話證據')
                self.assertEqual(target.one('SELECT approved_level FROM progress')['approved_level'],1)
                self.assertEqual(hashlib.sha256(source.read_bytes()).hexdigest(),before)
            finally:target.conn.close()

    def test_restore_checks_integrity_rejects_overwrite_and_corruption(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);db=Store(root/'source.sqlite3')
            db.create_user('backup-student','Synthetic-2026-password','student')
            with db.tx() as c:c.execute('INSERT INTO logins(token_hash,user_id,expires) VALUES (?,?,?)',('test-token-hash',1,9999999999))
            db.conn.close()
            raw=(root/'source.sqlite3').read_bytes()
            manifest={'schema_version':1,'kind':'private_same_institution_backup',
                      'files':{'runtime/clinical_tutor.sqlite3':{'sha256':hashlib.sha256(raw).hexdigest(),'bytes':len(raw)}}}
            archive=root/'backup.zip'
            with zipfile.ZipFile(archive,'w') as z:z.writestr('manifest.json',json.dumps(manifest));z.writestr('runtime/clinical_tutor.sqlite3',raw)
            restore_backup(archive,root/'restored')
            restored=Store(root/'restored/runtime/clinical_tutor.sqlite3')
            try:
                self.assertEqual(restored.one('SELECT username FROM users')['username'],'backup-student')
                self.assertEqual(restored.one('SELECT expires FROM logins')['expires'],0)
            finally:restored.conn.close()
            with self.assertRaises(ValueError):restore_backup(archive,root/'restored')
            with zipfile.ZipFile(root/'bad.zip','w') as z:z.writestr('manifest.json',json.dumps(manifest));z.writestr('runtime/clinical_tutor.sqlite3',b'corrupted')
            with self.assertRaises(ValueError):restore_backup(root/'bad.zip',root/'invalid')


if __name__=='__main__':unittest.main(verbosity=2)
