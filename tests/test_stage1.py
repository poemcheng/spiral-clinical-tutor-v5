from backend.competencies import profile
"""Stage 1 acceptance: account ownership, 12 professions, 5 levels and persistence."""
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest
from fastapi.testclient import TestClient
from backend import server
from backend.assessment import create_snapshot
from backend.stage1_bank import ROLE_TASKS, TRAINING_PROFESSIONS, role_items
from backend import sarcopenia_bank
from backend.store import Store, verify_password


class StageOneTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.original = server.store
        self.db = server.store = Store(Path(self.temp.name)/'stage1.sqlite3')
        self.db.bootstrap_admin()
        self.admin, self.learner, self.teacher = [TestClient(server.app) for _ in range(3)]
        self.assertEqual(self.admin.post('/api/auth/login', json={'username':'user','password':'1234'}).json()['role'], 'admin')
        for username, role, client in [('test-student','student',self.learner),('test-teacher','teacher',self.teacher)]:
            r=self.admin.post('/api/admin/users',json={'username':username,'password':'Stage1-test-2026!', 'role':role,'display_name':username})
            self.assertEqual(r.status_code,201,r.text)
            self.assertEqual(client.post('/api/auth/login',json={'username':username,'password':'Stage1-test-2026!'}).json()['role'],role)

    def tearDown(self):
        for client in (self.admin,self.learner,self.teacher):client.close()
        self.db.conn.close();server.store=self.original;self.temp.cleanup()

    def enter(self, profession):
        r=self.learner.post('/api/entry',json={'profession':profession})
        self.assertEqual(r.status_code,200,r.text)
        return r.json()

    def body(self, snapshot):
        return {'answers':{q['item_id']:5 for q in snapshot['items']},
                'objective_answers':{q['item_id']:q['options'][0] if q['item_type']=='single_choice' else '測試作答：先核對資料，確認個案疑慮與團隊追蹤。' for q in snapshot['objectives']}}

    def test_admin_accounts_roles_duplicate_and_no_password_disclosure(self):
        for client in (self.learner,self.teacher):
            self.assertEqual(client.get('/api/admin/users').status_code,403)
            self.assertEqual(client.post('/api/admin/users',json={'username':'illegal','password':'Stage1-test-2026!','display_name':'非法','role':'teacher'}).status_code,403)
        self.assertEqual(self.admin.post('/api/entry',json={'profession':'DT'}).status_code,403)
        self.assertEqual(self.teacher.post('/api/entry',json={'profession':'DT'}).status_code,403)
        self.assertEqual(self.admin.post('/api/admin/users',json={'username':'test-student','password':'Stage1-test-2026!','display_name':'重複','role':'student'}).status_code,409)
        self.assertEqual(self.admin.post('/api/admin/users',json={'username':'new-admin','password':'Stage1-test-2026!','display_name':'管理員','role':'admin'}).status_code,400)
        self.assertNotIn('password',self.admin.get('/api/admin/users').text)
        self.assertTrue(verify_password('1234',self.db.one("SELECT password_hash FROM users WHERE username='user'")['password_hash']))
        self.db.bootstrap_admin()
        self.assertEqual(self.db.one("SELECT count(*) n FROM users WHERE role='admin'")['n'],1)

    def test_password_reset_disable_enable_preserve_records(self):
        e=self.enter('OT')
        uid=self.db.one("SELECT id FROM users WHERE username='test-student'")['id']
        update={'display_name':'測試學員','role':'student','enabled':True,'password':'New-test-2026!'}
        self.assertEqual(self.admin.patch(f'/api/admin/users/{uid}',json=update).status_code,200)
        self.assertEqual(self.learner.get('/api/me').status_code,401)
        self.assertEqual(self.learner.post('/api/auth/login',json={'username':'test-student','password':'Stage1-test-2026!'}).status_code,401)
        self.assertEqual(self.learner.post('/api/auth/login',json={'username':'test-student','password':'New-test-2026!'}).status_code,200)
        update.pop('password');update['enabled']=False
        self.admin.patch(f'/api/admin/users/{uid}',json=update)
        self.assertEqual(self.learner.get('/api/me').status_code,401)
        self.assertEqual(self.learner.post('/api/auth/login',json={'username':'test-student','password':'New-test-2026!'}).status_code,401)
        update['enabled']=True;self.admin.patch(f'/api/admin/users/{uid}',json=update)
        self.assertEqual(self.learner.post('/api/auth/login',json={'username':'test-student','password':'New-test-2026!'}).status_code,200)
        self.assertEqual(self.db.one('SELECT id FROM attempts')['id'],e['attempt_id'])
        events=self.db.all("SELECT data FROM events WHERE kind LIKE 'admin_account_%'")
        self.assertTrue(events)
        self.assertTrue(all('New-test' not in ev['data'] and 'Stage1-test' not in ev['data'] for ev in events))

    def test_all_twelve_professions_level_one_and_only_five_have_lessons(self):
        combos=self.learner.get('/api/catalog').json()['combinations']
        self.assertEqual(len(combos),12)
        self.assertEqual({c['profession'] for c in combos if c['training_available']},TRAINING_PROFESSIONS)
        for c in combos:
            e=self.enter(c['profession']);self.assertEqual(e['approved_level'],1)
            self.assertEqual(e['snapshot']['profession'],c['profession'])
            expected=len(profile(c['profession'])['indicators'])
            self.assertEqual(len(e['snapshot']['items']),expected)
            self.assertTrue(all(q['level']==1 and q['profession']==c['profession'] for q in e['snapshot']['items']))
            r=self.learner.post(f"/api/assessments/{e['attempt_id']}/submit",json=self.body(e['snapshot']))
            self.assertEqual(r.status_code,200,r.text)
            sid=r.json()['session_id']
            if c['training_available']:
                self.assertIsNotNone(sid)
                session=self.learner.get(f'/api/sessions/{sid}').json()
                self.assertEqual(session['level'],5)
                self.assertEqual(r.json()['scores']['level_result']['self_score'],100)
                self.assertTrue(self.learner.get(f'/api/sessions/{sid}/cases').json())
            else:
                self.assertIsNone(sid)
                self.assertEqual(e['snapshot']['objectives'],[])
                self.assertEqual(self.db.one('SELECT count(*) n FROM sessions WHERE profession=?',(c['profession'],))['n'],0)
        self.assertEqual(self.db.one('SELECT count(*) n FROM attempts WHERE completed IS NOT NULL')['n'],12)
        self.assertEqual(self.db.one('SELECT count(*) n FROM sessions')['n'],5)

    def test_sixty_strata_real_tasks_six_dimensions_and_rotation(self):
        ids=set();texts=set()
        before=self.db.one('SELECT count(*) n FROM attempts')['n']
        for profession in ROLE_TASKS:
            for level in range(1,6):
                all_items=role_items(profession,level)
                self.assertEqual(len(all_items),12)
                for q in all_items:
                    self.assertNotIn(q['item_id'],ids);ids.add(q['item_id'])
                    self.assertNotIn(q['prompt'],texts);texts.add(q['prompt'])
                first=create_snapshot(server.registry,profession,'肌少症',level)
                second=create_snapshot(server.registry,profession,'肌少症',level,first)
                self.assertEqual({q['dimension'] for q in first['items']},{i['dimension'] for i in profile(profession)['indicators']})
                overlap={q['item_id'] for q in first['items']} & {q['item_id'] for q in second['items']}
                if sarcopenia_bank.has_bank(profession):
                    n=sarcopenia_bank.draw_counts(profession)['self']
                    # 30 題自評抽 n 題：連續兩次登入的重複降到題庫容量允許的最低值。
                    self.assertFalse(overlap)
                    self.assertLessEqual(len({q['item_id'] for q in first['objectives']} & {q['item_id'] for q in second['objectives']}),1)
                else:
                    self.assertFalse(overlap)
                preview=self.admin.get(f'/api/admin/question-preview?profession={profession}&level={level}')
                self.assertEqual(preview.status_code,200,preview.text)
                self.assertTrue(all('answer' not in q for q in preview.json()['objectives']))
        self.assertEqual(len(ids),720)
        self.assertEqual(self.db.one('SELECT count(*) n FROM attempts')['n'],before)
        self.assertEqual(self.admin.get('/api/admin/question-preview?profession=OT&level=6').status_code,400)
        self.assertEqual(self.learner.get('/api/admin/question-preview?profession=OT&level=1').status_code,403)

    def test_assessment_only_refresh_idempotence_and_teacher_view(self):
        e=self.enter('MLS');first=e['snapshot']['items'][0]['item_id']
        draft={'answers':{first:4},'objective_answers':{}}
        self.assertEqual(self.learner.put(f"/api/assessments/{e['attempt_id']}/draft",json=draft).status_code,200)
        refresh=self.enter('MLS');self.assertEqual(refresh['draft'],draft)
        self.assertEqual(refresh['snapshot']['content_hash'],e['snapshot']['content_hash'])
        body=self.body(e['snapshot'])
        for _ in range(2):
            response=self.learner.post(f"/api/assessments/{e['attempt_id']}/submit",json=body)
            self.assertEqual(response.status_code,200,response.text);self.assertIsNone(response.json()['session_id'])
        completed=self.enter('MLS');self.assertFalse(completed['assessment_required']);self.assertIsNone(completed['resume_session_id'])
        teacher=self.teacher.get(f"/api/teacher/assessments/{e['attempt_id']}").json()
        self.assertTrue(teacher['completed']);self.assertEqual(teacher['answers'],body)
        self.assertEqual(len(self.teacher.get('/api/teacher/overview').json()['assessments']),1)
        self.assertEqual(len(self.learner.get('/api/history').json()['assessments']),1)
        self.learner.post('/api/auth/logout');self.learner.post('/api/auth/login',json={'username':'test-student','password':'Stage1-test-2026!'})
        next_entry=self.enter('MLS')
        self.assertTrue(next_entry['assessment_required'])
        self.assertFalse({q['item_id'] for q in e['snapshot']['items']} & {q['item_id'] for q in next_entry['snapshot']['items']})
        other=TestClient(server.app)
        try:
            self.admin.post('/api/admin/users',json={'username':'other','password':'Stage1-test-2026!','display_name':'他人','role':'student'})
            other.post('/api/auth/login',json={'username':'other','password':'Stage1-test-2026!'})
            self.assertEqual(other.get(f"/api/assessments/{e['attempt_id']}").status_code,404)
        finally:other.close()

    def test_sarcopenia_bank_cells_draws_and_calibration(self):
        from backend.assessment import score_snapshot
        bank=sarcopenia_bank.load_bank()
        self.assertEqual(set(bank['professions']),{'DT','PT','RT','MD','RN'})
        ids=set()
        for prof,data in bank['professions'].items():
            for level in range(1,6):
                cell=data['levels'][str(level)]
                self.assertEqual((len(cell['self']),len(cell['objective'])),(30,20))
                for q in cell['self']+cell['objective']:
                    self.assertNotIn(q['item_id'],ids);ids.add(q['item_id'])
                    self.assertEqual((q['profession'],q['level']),(prof,level))
                for q in cell['objective']:
                    if q['item_type']=='single_choice':
                        self.assertEqual(len(set(q['options'])),4);self.assertIn(q['answer'],q['options'])
                    else:
                        self.assertEqual(set(q['rubric']),{'0','1','2'})
                snap=create_snapshot(server.registry,prof,'肌少症',level)
                counts=sarcopenia_bank.draw_counts(prof)
                self.assertEqual((len(snap['items']),len(snap['objectives'])),(len(profile(prof)['indicators']),counts['objective']))
                self.assertEqual({q['dimension'] for q in snap['reference_self_items']},{'CJ','PC','COM','TC','SAFE','HC'})
                self.assertEqual({q['dimension'] for q in snap['objectives']},{'CJ','PC','COM','TC','SAFE','HC'})
                self.assertLessEqual(sum(q['item_type']=='short_answer' for q in snap['objectives']),1)
                public=server.public_snapshot(snap)
                self.assertTrue(all('answer' not in q and 'explanation' not in q for q in public['objectives']))
                # 全選 5 分但客觀題全錯：應標示自評高估
                wrong={q['item_id']:(next(o for o in q['options'] if o!=q['answer']) if q['item_type']=='single_choice' else '待評') for q in snap['objectives']}
                scores=score_snapshot(snap,{q['item_id']:5 for q in snap['items']},wrong)
                self.assertTrue(scores['summary']['overconfident_dimensions'])
                self.assertEqual(scores['summary']['objective_auto_percent'],0.0)
        self.assertEqual(len(ids),1250)


class MigrationTests(unittest.TestCase):
    def test_existing_users_and_foreign_keys_survive_admin_migration(self):
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp)/'old.sqlite3'
            c=sqlite3.connect(path)
            c.executescript('''CREATE TABLE users(id INTEGER PRIMARY KEY,username TEXT NOT NULL UNIQUE,
                password_hash TEXT NOT NULL,display_name TEXT NOT NULL,
                role TEXT NOT NULL CHECK(role IN ('student','teacher')),enabled INTEGER NOT NULL DEFAULT 1);
                INSERT INTO users VALUES (42,'existing','preserved-hash','既有學員','student',1);
                CREATE TABLE logins(id INTEGER PRIMARY KEY,token_hash TEXT UNIQUE NOT NULL,
                  user_id INTEGER NOT NULL REFERENCES users(id),expires REAL NOT NULL);
                INSERT INTO logins VALUES(3,'preserved-token',42,0);''')
            c.commit();c.close()
            db=Store(path)
            try:
                db.bootstrap_admin()
                self.assertEqual(db.one("SELECT id,password_hash FROM users WHERE username='existing'"),{'id':42,'password_hash':'preserved-hash'})
                self.assertEqual(db.one('SELECT user_id FROM logins')['user_id'],42)
                self.assertEqual(db.all('PRAGMA foreign_key_check'),[])
                self.assertEqual(db.one('PRAGMA foreign_keys')['foreign_keys'],1)
            finally:db.conn.close()


if __name__=='__main__':unittest.main(verbosity=2)
