"""Behavior tests use a temporary database; never touch the user's training records."""
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from fastapi.testclient import TestClient
from backend import server
from backend.store import Store, verify_password


class WorkflowTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.old = server.store
        server.store = Store(Path(self.tmp.name)/'test.sqlite3')
        self.db = server.store
        for u,r in [('alice','student'),('bob','student'),('prof','teacher')]:
            self.db.create_user(u,'Synthetic-test-pass!2026',r,u)
        self.alice=TestClient(server.app);self.bob=TestClient(server.app);self.prof=TestClient(server.app)
        for client,name in [(self.alice,'alice'),(self.bob,'bob'),(self.prof,'prof')]:
            self.assertEqual(client.post('/api/auth/login',json={'username':name,'password':'Synthetic-test-pass!2026'}).status_code,200)

    def tearDown(self):
        for client in (self.alice,self.bob,self.prof):client.close()
        self.db.conn.close();server.store=self.old;self.tmp.cleanup()

    def enter(self,client=None,prof='DT',new=False):
        response=(client or self.alice).post('/api/entry',json={'profession':prof,'new_round':new})
        self.assertEqual(response.status_code,200,response.text)
        return response.json()

    def submit(self,e,client=None,rating=1):
        body={'answers':{q['item_id']:rating for q in e['snapshot']['items']},
              'objective_answers':{q['item_id']:q['options'][0] if q['item_type']=='single_choice' else '需要確認份量、頻率、生活習慣與追蹤計畫。' for q in e['snapshot']['objectives']}}
        response=(client or self.alice).post(f"/api/assessments/{e['attempt_id']}/submit",json=body)
        self.assertEqual(response.status_code,200,response.text)
        return response.json()['session_id'],body

    def complete(self,sid,client=None):
        client=client or self.alice
        self.assertEqual(client.post(f'/api/sessions/{sid}/case',json={'case_id':'SARC-DT-001'}).status_code,200)
        plan=client.get(f'/api/sessions/{sid}').json()['data']['adaptive_plan']
        self.assertEqual(client.post(f'/api/sessions/{sid}/learned',json={'reflection':'我會先了解病人疑慮，核對資料並共同討論下一步。','completed_modules':list(range(plan['video_count'])),'observed':True}).status_code,200)
        raw=json.loads(self.db.one('SELECT data FROM sessions WHERE id=?',(sid,))['data'])
        for q in raw['case_snapshot']['kdp']:
            index=max(range(len(q['options'])),key=lambda i:q['options'][i]['score'])
            self.assertEqual(client.post(f'/api/sessions/{sid}/decision',json={'item_id':q['id'],'option_id':f'o{index}'}).status_code,200)
        for turn in range(2):
            self.assertEqual(client.post(f'/api/sessions/{sid}/chat',json={'text':'我想了解您的疑慮及實際生活狀況。','mode':'scripted','request_id':f'synthetic-turn-{sid}-{turn}'}).status_code,200)
        if plan['tier']>=2:client.post(f'/api/sessions/{sid}/scene',json={'action':'report'})
        self.assertEqual(client.post(f'/api/sessions/{sid}/handoff',json={k:'病人目前資料需進一步核對與安排追蹤。' for k in 'SBAR'}).status_code,200)
        raw=json.loads(self.db.one('SELECT data FROM sessions WHERE id=?',(sid,))['data'])
        answers={q['id']:q['answer'] for q in raw['quiz_snapshot']}
        public=client.get(f'/api/sessions/{sid}').json()
        self.assertTrue(all('answer' not in q for q in public['data']['quiz_snapshot']))
        self.assertTrue(all('answer' not in q for q in client.get(f'/api/sessions/{sid}/quiz').json()))
        done=client.post(f'/api/sessions/{sid}/finish',json={'answers':answers})
        self.assertEqual(done.status_code,200,done.text)
        return answers

    def test_authentication_role_and_origin(self):
        anonymous=TestClient(server.app)
        self.assertEqual(anonymous.get('/api/catalog').status_code,401)
        self.assertEqual(self.alice.get('/api/teacher/overview').status_code,403)
        self.assertEqual(self.prof.post('/api/entry',json={'profession':'DT'}).status_code,403)
        self.assertEqual(self.alice.post('/api/entry',json={'profession':'DT'},headers={'Origin':'https://evil.example'}).status_code,403)
        self.assertEqual(anonymous.post('/api/auth/login',json={'username':'alice','password':'wrong'}).status_code,401)
        user=self.db.one('SELECT * FROM users WHERE username=?',('alice',))
        self.assertNotIn('Synthetic',user['password_hash'])
        self.assertTrue(verify_password('Synthetic-test-pass!2026',user['password_hash']))
        self.assertIn('HttpOnly',self.alice.post('/api/auth/login',json={'username':'alice','password':'Synthetic-test-pass!2026'}).headers['set-cookie'])

    def test_opening_platform_requires_fresh_login_and_preserves_learning_records(self):
        entry=self.enter();sid,_=self.submit(entry)
        before={table:self.db.all('SELECT * FROM '+table) for table in ('users','attempts','sessions','messages','reviews')}
        token=self.alice.cookies.get(server.COOKIE)
        old_login=self.alice.get('/api/me').json()['login_id']
        response=self.alice.get('/')
        self.assertEqual(response.status_code,200)
        self.assertEqual(response.headers['cache-control'],'no-store')
        self.assertIn('Max-Age=0',response.headers['set-cookie'])
        self.assertEqual(self.alice.get('/api/me').status_code,401)

        # The previous token is revoked server-side as well as removed in this browser.
        with TestClient(server.app) as stale:
            stale.cookies.set(server.COOKIE,token)
            self.assertEqual(stale.get('/api/catalog').status_code,401)
        self.assertEqual(self.db.one('SELECT expires FROM logins WHERE id=?',(old_login,))['expires'],0)
        for table,rows in before.items():self.assertEqual(self.db.all('SELECT * FROM '+table),rows)
        self.assertEqual(self.bob.get('/api/me').status_code,200)
        response=self.alice.post('/api/auth/login',json={'username':'alice','password':'Synthetic-test-pass!2026'})
        self.assertEqual(response.status_code,200)
        self.assertNotIn('Max-Age=',response.headers['set-cookie'])
        resumed=self.enter();self.assertEqual(resumed['resume_session_id'],sid)
        self.assertEqual(self.alice.post('/api/auth/logout').status_code,200)
        self.assertEqual(self.alice.post('/api/auth/logout').status_code,200)
        self.assertEqual(self.alice.get('/api/me').status_code,401)

    def test_launch_login_entry_revokes_existing_browser_token(self):
        token=self.alice.cookies.get(server.COOKIE)
        response=self.alice.get('/login?launch=synthetic-launch-1')
        self.assertEqual(response.status_code,200)
        self.assertEqual(response.headers['cache-control'],'no-store')
        self.assertEqual(self.alice.get('/api/me').status_code,401)
        with TestClient(server.app) as stale:
            stale.cookies.set(server.COOKIE,token)
            self.assertEqual(stale.get('/api/me').status_code,401)
        self.assertEqual(self.bob.get('/api/me').status_code,200)

    def test_high_self_rating_places_level_five_and_resume_preserves_case(self):
        entry=self.enter();sid,body=self.submit(entry,rating=5)
        session=self.alice.get(f'/api/sessions/{sid}').json()
        self.assertEqual(session['level'],5);self.assertEqual(session['step'],2)
        self.assertEqual(self.db.one('SELECT approved_level FROM progress')['approved_level'],1)
        self.assertEqual(self.alice.post(f'/api/assessments/{entry["attempt_id"]}/submit',json=body).json()['session_id'],sid)
        self.alice.post(f'/api/sessions/{sid}/case',json={'case_id':'SARC-DT-001'})
        self.alice.post('/api/auth/logout')
        self.alice.post('/api/auth/login',json={'username':'alice','password':'Synthetic-test-pass!2026'})
        self.assertEqual(self.alice.get(f'/api/sessions/{sid}').status_code,409)
        fresh=self.enter();self.assertTrue(fresh['assessment_required']);self.assertEqual(fresh['resume_session_id'],sid)
        self.assertNotEqual({q['item_id'] for q in entry['snapshot']['items']},{q['item_id'] for q in fresh['snapshot']['items']})
        resumed,_=self.submit(fresh);self.assertEqual(resumed,sid)
        self.assertEqual(self.alice.get(f'/api/sessions/{sid}').json()['step'],3)
        self.assertEqual(self.alice.get(f'/api/sessions/{sid}').json()['data']['case']['id'],'SARC-DT-001')

    def test_draft_survives_refresh_and_invalid_ratings_rejected(self):
        e=self.enter();q=e['snapshot']['items'][0]['item_id']
        draft={'answers':{q:4},'objective_answers':{}}
        self.assertEqual(self.alice.put(f'/api/assessments/{e["attempt_id"]}/draft',json=draft).status_code,200)
        refresh=self.enter();self.assertEqual(refresh['attempt_id'],e['attempt_id']);self.assertEqual(refresh['draft'],draft)
        self.assertEqual(refresh['snapshot']['content_hash'],e['snapshot']['content_hash'])
        self.assertEqual(self.alice.post(f'/api/assessments/{e["attempt_id"]}/submit',json=draft).status_code,400)
        self.assertEqual(self.alice.put(f'/api/assessments/{e["attempt_id"]}/draft',json={'answers':{q:99}}).status_code,400)
        self.assertEqual(self.alice.put(f'/api/assessments/{e["attempt_id"]}/draft',json={'answers':{q:True}}).status_code,422)

    def test_cross_student_access_and_step_gates(self):
        sid,_=self.submit(self.enter());self.submit(self.enter(self.bob),self.bob)
        self.assertEqual(self.bob.get(f'/api/sessions/{sid}').status_code,404)
        self.assertEqual(self.bob.get(f'/api/sessions/{sid}/export').status_code,404)
        self.assertEqual(self.alice.post(f'/api/sessions/{sid}/finish',json={'answers':{}}).status_code,409)
        self.assertEqual(self.alice.get(f'/api/sessions/{sid}/interaction').status_code,409)
        self.assertEqual(self.alice.post(f'/api/sessions/{sid}/scene',json={'action':'report'}).status_code,409)

    def test_full_flow_teacher_review_level_and_adaptation(self):
        sid,_=self.submit(self.enter());answers=self.complete(sid)
        self.assertEqual(self.db.one('SELECT approved_level FROM progress')['approved_level'],1)
        self.assertEqual(self.alice.post(f'/api/sessions/{sid}/finish',json={'answers':answers}).status_code,200)
        review={'decision':'approve','score':92,'level':2,'safety_pass':True,'note':'已查核案例對話及交接證據，可進入下一級任務。','expected_review_id':0}
        self.assertEqual(self.prof.post(f'/api/teacher/sessions/{sid}/review',json=review).status_code,200)
        self.assertEqual(self.prof.post(f'/api/teacher/sessions/{sid}/review',json=review).status_code,409)
        self.assertEqual(self.db.one('SELECT approved_level FROM progress')['approved_level'],2)
        next_entry=self.enter(new=True);self.assertEqual(next_entry['approved_level'],2)
        self.assertTrue(all(q['level']==1 and '-L1-' in q['item_id'] for q in next_entry['snapshot']['items']))
        sid2,_=self.submit(next_entry,rating=2)
        new=self.alice.get(f'/api/sessions/{sid2}').json()
        self.assertEqual(new['level'],2);self.assertEqual(new['data']['adaptive_plan']['video_count'],2)
        self.complete(sid2)
        review['level']=3
        self.assertEqual(self.prof.post(f'/api/teacher/sessions/{sid2}/review',json=review).status_code,200)
        sid3,_=self.submit(self.enter(new=True))
        self.assertEqual(self.alice.get(f'/api/sessions/{sid3}').json()['data']['adaptive_plan']['tier'],2)
        self.complete(sid3)
        sid4,_=self.submit(self.enter(new=True))
        self.assertEqual(self.alice.get(f'/api/sessions/{sid4}').json()['data']['adaptive_plan']['tier'],3)
        # Other professions always have independent progress.
        pt=self.enter(prof='PT');ptid,_=self.submit(pt)
        self.assertEqual(self.alice.get(f'/api/sessions/{ptid}').json()['level'],1)
        self.assertEqual(self.alice.get(f'/api/sessions/{sid}').json()['level'],1)

    def test_teacher_safety_gate_and_monitoring(self):
        sid,_=self.submit(self.enter());self.complete(sid)
        bad={'decision':'approve','score':95,'level':2,'safety_pass':False,'note':'安全項目尚未通過，需要補作與再次評量。'}
        self.assertEqual(self.prof.post(f'/api/teacher/sessions/{sid}/review',json=bad).status_code,400)
        d=self.prof.get(f'/api/teacher/sessions/{sid}').json()
        self.assertEqual(len(d['messages']),4);self.assertTrue(d['assessments'][0]['snapshot']['items'])
        self.assertEqual(self.prof.get('/api/teacher/overview').json()['sessions'][0]['turns'],2)

    def test_ai_failure_is_visible_and_scripted_mode_audited(self):
        from backend.legacy.llm import LLMStatus
        sid,_=self.submit(self.enter());self.alice.post(f'/api/sessions/{sid}/case',json={'case_id':'SARC-DT-001'})
        self.alice.post(f'/api/sessions/{sid}/learned',json={'reflection':'已閱讀案例，接下來需了解實際生活情境。','completed_modules':[0],'observed':True})
        with patch.object(server.llm,'check',return_value=LLMStatus(error='synthetic offline')):
            r=self.alice.post(f'/api/sessions/{sid}/chat',json={'text':'您好，請說明您的疑慮。','mode':'ai','request_id':'offline-unique-1'}).json()
        self.assertFalse(r['ok']);messages=self.alice.get(f'/api/sessions/{sid}').json()['messages']
        self.assertEqual(messages[-1]['source'],'error')
        b={'text':'想再了解您的疑慮。','mode':'scripted','request_id':'scripted-unique-1'}
        self.alice.post(f'/api/sessions/{sid}/chat',json=b)
        self.alice.post(f'/api/sessions/{sid}/chat',json=b)
        messages=self.alice.get(f'/api/sessions/{sid}').json()['messages']
        self.assertEqual(len(messages),4);self.assertEqual(messages[-1]['source'],'scripted')

    def test_livekit_unconfigured_and_backup(self):
        sid,_=self.submit(self.enter())
        with patch.object(server.voice_bridge,'ready',return_value=False):
            self.alice.post(f'/api/sessions/{sid}/case',json={'case_id':'SARC-DT-001'})
            self.alice.post(f'/api/sessions/{sid}/learned',json={'reflection':'已閱讀案例，接下來需了解實際生活情境。','completed_modules':[0],'observed':True})
            self.assertEqual(self.alice.post(f'/api/sessions/{sid}/livekit').status_code,503)
        path=Path(self.tmp.name)/'backup.sqlite3';self.db.backup(path)
        backup=Store(path)
        self.assertEqual(backup.one('SELECT COUNT(*) n FROM sessions')['n'],1)
        self.assertEqual(backup.one('PRAGMA integrity_check')['integrity_check'],'ok')
        backup.conn.close()


if __name__=='__main__':unittest.main(verbosity=2)
