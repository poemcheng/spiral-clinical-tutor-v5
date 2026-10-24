"""New account policy, lesson publication, graph provenance and report delivery."""
import io,json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from fastapi.testclient import TestClient
from backend import server,workspace_settings,teacher_studio
from backend.store import Store,verify_password
import test_workflow as workflow
from pypdf import PdfReader

class ManagementTests(unittest.TestCase):
    setUp=workflow.WorkflowTests.setUp
    tearDown=workflow.WorkflowTests.tearDown
    enter=workflow.WorkflowTests.enter
    submit=workflow.WorkflowTests.submit
    complete=workflow.WorkflowTests.complete
    def admin(self):
        self.db.create_user('manager','654321','admin','Synthetic admin');c=TestClient(server.app);c.post('/api/auth/login',json={'username':'manager','password':'654321'});self.addCleanup(c.close);return c
    def completed(self):
        sid,_=self.submit(self.enter());self.complete(sid);return sid
    def test_default_six_character_limit_and_admin_change_do_not_rewrite_hashes(self):
        admin=self.admin();self.assertEqual(admin.get('/api/admin/settings').json()['password_policy']['maximum'],6)
        body={'username':'sixchar','password':'482619','display_name':'Synthetic','role':'student'}
        self.assertEqual(admin.post('/api/admin/users',json=body).status_code,201)
        self.assertEqual(admin.post('/api/admin/users',json={**body,'username':'too-long','password':'1234567'}).status_code,400)
        before=self.db.one("SELECT password_hash FROM users WHERE username='sixchar'")
        self.assertEqual(self.prof.patch('/api/admin/settings/password-policy',json={'minimum':4,'maximum':12}).status_code,403)
        self.assertEqual(admin.patch('/api/admin/settings/password-policy',json={'minimum':4,'maximum':12}).status_code,200)
        self.assertEqual(self.db.one("SELECT password_hash FROM users WHERE username='sixchar'"),before)
        self.assertEqual(admin.post('/api/admin/users',json={**body,'username':'long-now','password':'Long-allowed'}).status_code,201)
    def test_own_password_requires_current_and_revokes_old_logins(self):
        self.assertEqual(self.alice.post('/api/auth/password',json={'current_password':'incorrect','new_password':'482619'}).status_code,400)
        r=self.alice.post('/api/auth/password',json={'current_password':'Synthetic-test-pass!2026','new_password':'482619'});self.assertEqual(r.status_code,200,r.text)
        self.assertEqual(self.alice.get('/api/me').status_code,401)
        self.assertEqual(self.alice.post('/api/auth/login',json={'username':'alice','password':'482619'}).status_code,200)
    def test_pdf_is_real_readable_private_and_separates_scores(self):
        sid=self.completed();r=self.alice.get(f'/api/sessions/{sid}/report.pdf');self.assertEqual(r.status_code,200,r.text[:200]);self.assertTrue(r.content.startswith(b'%PDF-'));self.assertIn('inline',r.headers['content-disposition'])
        reader=PdfReader(io.BytesIO(r.content));text='\n'.join(p.extract_text() for p in reader.pages)
        for term in ['訓練前自評','客觀訓練綜合','待評','附錄 A','訓練對話']:self.assertIn(term,text)
        self.assertEqual(self.bob.get(f'/api/sessions/{sid}/report.pdf').status_code,404)
        self.assertEqual(self.prof.get(f'/api/sessions/{sid}/report.pdf').status_code,200)
        summary=self.alice.get(f'/api/sessions/{sid}/report/summary').json();self.assertIsNone(summary['teacher_score']);self.assertTrue(summary['teacher_pending'])
        pages=self.alice.get(f'/api/sessions/{sid}/report/pages');self.assertEqual(pages.status_code,200);self.assertEqual(pages.json()['count'],len(reader.pages))
        image=self.alice.get(f'/api/sessions/{sid}/report/page/1.jpg');self.assertEqual(image.status_code,200);self.assertTrue(image.content.startswith(b'\xff\xd8'))
        self.assertEqual(self.bob.get(f'/api/sessions/{sid}/report/page/1.jpg').status_code,404)
        self.assertEqual(self.alice.get(f'/api/sessions/{sid}/report/page/99999.jpg').status_code,404)
    def test_completed_feedback_is_readable_after_relogin_without_new_assessment(self):
        sid=self.completed();before=len(self.db.all('SELECT id FROM attempts'))
        self.alice.post('/api/auth/logout');self.alice.post('/api/auth/login',json={'username':'alice','password':'Synthetic-test-pass!2026'})
        self.assertEqual(self.alice.get(f'/api/sessions/{sid}').status_code,200);self.assertEqual(self.alice.get(f'/api/sessions/{sid}/actors').status_code,200)
        self.assertEqual(len(self.db.all('SELECT id FROM attempts')),before)
    def test_incomplete_training_cannot_claim_complete_report(self):
        sid,_=self.submit(self.enter());self.assertEqual(self.alice.get(f'/api/sessions/{sid}/report.pdf').status_code,409)
    def test_email_requires_consent_config_and_smtp_acceptance(self):
        sid=self.completed();url=f'/api/sessions/{sid}/report/email'
        self.assertEqual(self.alice.post(url,json={'email':'learner@example.org'}).status_code,400)
        self.assertEqual(self.alice.post(url,json={'email':'bad','consent':True}).status_code,400)
        self.assertEqual(self.alice.post(url,json={'email':'learner@example.org','consent':True}).status_code,503)
        cfg={'host':'smtp.example.org','port':587,'security':'starttls','username':'sender@example.org','sender':'sender@example.org','password':'test-only','ready':True}
        with patch.object(workspace_settings,'smtp_config',return_value=cfg),patch('smtplib.SMTP') as smtp:
            smtp.return_value.send_message.return_value={}
            r=self.alice.post(url,json={'email':'learner@example.org','consent':True});self.assertEqual(r.status_code,200,r.text);self.assertTrue(r.json()['accepted_by_smtp'])
            message=smtp.return_value.send_message.call_args.args[0];self.assertEqual(len(list(message.iter_attachments())),1)
        self.assertEqual(len(self.db.all("SELECT id FROM events WHERE kind='report_email_accepted'")),1)
    def test_teacher_can_publish_versioned_lesson_and_learner_can_start_it(self):
        body=self.prof.get('/api/teacher/lessons/template/COURSE-SARC').json();body.update(title='Synthetic teacher lesson',topic='教師版本測試情境',professions=['DT'],status='draft')
        r=self.prof.post('/api/teacher/lessons',json=body);self.assertEqual(r.status_code,201,r.text);ident=r.json()['id']
        self.assertNotIn(ident,[c['id'] for c in self.alice.get('/api/catalog').json()['courses']])
        body.update(expected_revision=1,status='published');r=self.prof.put('/api/teacher/lessons/'+ident,json=body);self.assertEqual(r.status_code,200,r.text)
        self.assertIn(ident,[c['id'] for c in self.alice.get('/api/catalog').json()['courses']])
        entry=self.alice.post('/api/entry',json={'profession':'DT','topic':body['topic']});self.assertEqual(entry.status_code,200,entry.text);e=entry.json()
        payload={'answers':{q['item_id']:3 for q in e['snapshot']['items']},'objective_answers':{}}
        result=self.alice.post(f"/api/assessments/{e['attempt_id']}/submit",json=payload);self.assertEqual(result.status_code,200,result.text);sid=result.json()['session_id']
        r=self.alice.post(f'/api/sessions/{sid}/case',json={'case_id':ident});self.assertEqual(r.status_code,200,r.text)
        frozen=self.db.one('SELECT data FROM sessions WHERE id=?',(sid,))['data'];body.update(expected_revision=2,patient=body['patient']+'\n新版本資料待核對。');self.prof.put('/api/teacher/lessons/'+ident,json=body)
        self.assertEqual(self.db.one('SELECT data FROM sessions WHERE id=?',(sid,))['data'],frozen)
        self.assertEqual(self.prof.put('/api/teacher/lessons/'+ident,json=body).status_code,409)
    def test_graphify_retrieval_has_sources_and_is_teacher_only(self):
        sid=self.completed();self.assertEqual(self.alice.get('/api/teacher/knowledge/search?q=肌少症').status_code,403)
        r=self.prof.get(f'/api/teacher/knowledge/search?q=疑慮&session_id={sid}');self.assertEqual(r.status_code,200,r.text)
        d=r.json();self.assertTrue(d['engine'].startswith('Graphify'));self.assertTrue(d['hits']);self.assertTrue(any(h['kind']=='message' for h in d['hits']));self.assertTrue(all(e['confidence']=='EXTRACTED' for e in d['edges']))
    def test_inline_materials_enforce_role_and_no_arbitrary_path(self):
        self.assertEqual(self.alice.get('/api/materials/questions/read').status_code,403)
        self.assertEqual(self.alice.get('/api/materials/unknown/read').status_code,404)
        with TestClient(server.app) as c:self.assertEqual(c.get('/api/materials/curriculum/read').status_code,401)
    def test_reset_leaves_only_three_new_accounts_and_no_learning_records(self):
        from tools.reset_demo_installation import reset_installation
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder);db=Store(path/'clinical_tutor.sqlite3');uid=db.create_user('old-user','123456','student')
            with db.tx() as c:
                c.execute('CREATE TABLE legacy_imports (new_session_id INTEGER REFERENCES sessions(id))')
                old_sid=c.execute("INSERT INTO sessions(user_id,profession,topic,level,data,created,updated) VALUES (?,?,?,1,'{}',1,1)",(uid,'DT','舊示範')).lastrowid
                c.execute('INSERT INTO legacy_imports VALUES (?)',(old_sid,))
            db.conn.close()
            result=reset_installation(path);db=Store(path/'clinical_tutor.sqlite3')
            self.assertEqual({r['username'] for r in db.all('SELECT username FROM users')},{'demo','admin','teacher'})
            self.assertEqual(result['counts']['sessions'],0);self.assertEqual(result['counts']['attempts'],0);self.assertEqual(db.one('SELECT level FROM learning_access')['level'],5)
            self.assertTrue(Path(result['credential_file']).is_file());db.conn.close()
    def test_smtp_secret_is_encrypted_and_never_returned_to_admin(self):
        admin=self.admin()
        with tempfile.TemporaryDirectory() as folder,patch.object(workspace_settings,'RUNTIME',Path(folder)):
            secret='SYNTHETIC-SMTP-SECRET'
            r=admin.put('/api/admin/settings/smtp',json={'host':'smtp.example.org','port':587,'security':'starttls','username':'sender@example.org','sender':'sender@example.org','password':secret})
            self.assertEqual(r.status_code,200,r.text);self.assertNotIn(secret,r.text);self.assertTrue(r.json()['password_configured'])
            self.assertNotIn(secret,self.db.one("SELECT value FROM app_settings WHERE key='smtp'")['value'])
            self.assertEqual(workspace_settings.smtp_config(self.db,True)['password'],secret)

if __name__=='__main__':unittest.main()
