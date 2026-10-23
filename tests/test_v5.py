"""V5 user stories: actual pairings, earned media access and append-only observations."""
import json
import unittest
from fastapi.testclient import TestClient
from backend import server,characters
from backend.competencies import profile
import test_uploaded_workflow as fixtures

class V5Tests(unittest.TestCase):
    setUp=fixtures.UploadedWorkflowTests.setUp
    tearDown=fixtures.UploadedWorkflowTests.tearDown
    start=fixtures.UploadedWorkflowTests.start
    interaction=fixtures.UploadedWorkflowTests.interaction

    def test_five_demo_pairings_and_server_rejects_wrong_roles(self):
        for prof,actor,targets in [('RT','wang-pt',['PT']),('DT','wang-pt',['PT']),('PT','auntie-lin',['patient']),('MD','auntie-lin',['patient']),('RN','auntie-lin',['patient','PT'])]:
            sid,_=self.interaction(prof)
            info=self.client.get(f'/api/sessions/{sid}/actors').json()
            self.assertIn(info['interaction']['id'],['auntie-lin','wang-pt'] if prof=='RN' else [actor])
            self.assertEqual(info['pairing']['targets'],targets)
            wrong='li-rph'
            self.assertEqual(self.client.post(f'/api/sessions/{sid}/actors',json={'purpose':'interaction','actor_id':wrong}).status_code,400)
            if prof=='RN':self.assertEqual(self.client.post(f'/api/sessions/{sid}/actors',json={'purpose':'interaction','actor_id':'wang-pt'}).status_code,200)
        self.assertEqual(characters.default_actor({'profession':'RT'},'lecturer'),'zhou-rt')

    def test_nursing_requires_both_patient_and_physiotherapist_conversations(self):
        sid,_=self.interaction('RN');raw=json.loads(self.db.one('SELECT data FROM sessions WHERE id=?',(sid,))['data'])
        for q in raw['case_snapshot']['kdp']:
            best=max(range(len(q['options'])),key=lambda i:q['options'][i]['score'])
            self.assertEqual(self.client.post(f'/api/sessions/{sid}/decision',json={'item_id':q['id'],'option_id':f'o{best}'}).status_code,200)
        handoff={k:'已核對案例，請協助確認功能需求並安排追蹤。' for k in 'SBAR'}
        for actor in ['auntie-lin','wang-pt']:
            self.client.post(f'/api/sessions/{sid}/actors',json={'purpose':'interaction','actor_id':actor})
            for n in range(2):
                r=self.client.post(f'/api/sessions/{sid}/chat',json={'text':'請說明目前疑慮與需要進一步確認的資訊。','mode':'scripted','request_id':f'{actor}-{n}'})
                self.assertTrue(r.json()['ok'])
            if actor=='auntie-lin':self.assertEqual(self.client.post(f'/api/sessions/{sid}/handoff',json=handoff).status_code,409)
        self.assertEqual(self.client.post(f'/api/sessions/{sid}/handoff',json=handoff).status_code,200)

    def test_profession_results_are_distinct_and_have_reference_mapping(self):
        expected={'RT':5,'DT':6,'PT':6,'MD':6,'RN':6}
        for prof,count in expected.items():
            sid,e=self.start(prof)
            self.assertEqual(len(e['snapshot']['items']),count)
            self.assertEqual(e['snapshot']['competency_profile']['source_file'],'核心能力.docx')
            self.assertEqual(e['snapshot']['competency_profile']['references'][0]['url'],'/api/materials/core-competencies')
            r=self.client.get(f"/api/assessments/{e['attempt_id']}").json()['scores']
            self.assertEqual(len(r['competency_results']),count)
            self.assertTrue(all(k.startswith(prof+'-') for k in r['competency_scores']))
            self.assertEqual(r['summary']['self_mean'],20)
            self.assertTrue(all('answer' not in q for q in e['snapshot']['objectives']))

    def test_media_level_gates_and_frame_notes_persist_for_teacher(self):
        from unittest.mock import patch
        from backend import teaching_media
        from pathlib import Path
        fixture_root=Path(self.tmp.name);media=fixture_root/'data/video360';media.mkdir(parents=True)
        (media/'fixture.mp4').write_bytes(b'\x00\x00\x00\x18ftypmp42'+b'0'*100)
        (media/'catalog.json').write_text(json.dumps({'clips':[{'id':'team360-1','title':'Synthetic media permission fixture','file':'fixture.mp4','duration':10,'fps':30000/1001,'status':'test'}]}))
        patcher=patch.object(teaching_media,'ROOT',fixture_root);patcher.start();self.addCleanup(patcher.stop)
        sid,_=self.start('MD',level=5)
        self.client.post(f'/api/sessions/{sid}/case',json={'case_id':'COURSE-SARC'})
        # High self-rating still cannot unlock earned Level 4 resources.
        url=f'/api/sessions/{sid}/resources/360/team360-1'
        self.assertEqual(self.client.get(url).status_code,403)
        body={'clip_id':'team360-1','seconds':1.001,'yaw':30,'pitch':10,'observation':'觀察團隊交接時，接收者是否確認資訊。'}
        self.assertEqual(self.client.post(f'/api/sessions/{sid}/frame-notes',json=body).status_code,403)
        for level in [4,5]:
            with self.db.tx() as c:
                row=self.db.one('SELECT data FROM sessions WHERE id=?',(sid,));payload=json.loads(row['data']);payload['adaptive_plan']['learning_level']=level;self.db.save(c,sid,payload)
            video=self.client.get(url,headers={'Range':'bytes=0-31'})
            self.assertEqual(video.status_code,206)
            self.assertEqual(video.content,(media/'fixture.mp4').read_bytes()[:32])
            if level==4:self.assertEqual(self.client.post(f'/api/sessions/{sid}/frame-notes',json=body).status_code,403)
        response=self.client.post(f'/api/sessions/{sid}/frame-notes',json=body)
        self.assertEqual(response.status_code,200,response.text)
        self.assertEqual(response.json()['frame'],30)
        self.assertEqual(self.faculty.get(f'/api/teacher/sessions/{sid}').json()['data']['frame_notes'][0]['observation'],body['observation'])
        self.assertEqual(self.client.post(f'/api/sessions/{sid}/frame-notes',json={**body,'seconds':999999}).status_code,400)
        self.assertEqual(self.faculty.post(f'/api/sessions/{sid}/frame-notes',json=body).status_code,403)
        with TestClient(server.app) as anonymous:self.assertEqual(anonymous.get(url).status_code,401)

    def test_demographic_assets_and_historical_casting(self):
        actors=self.client.get('/api/characters').json()['actors']
        for group in ['高齡','中年']:
            self.assertEqual({a['gender'] for a in actors if a.get('age_group')==group},{'male','female'})
        self.assertEqual({a['gender'] for a in actors if a['kind']=='clinician'},{'male','female'})
        legacy={'profession':'DT','payload':{'actors':{'interaction':characters.get_actor('li-rph')}}}
        self.assertEqual(characters.selected(legacy)['id'],'li-rph')

    def test_public_bootstrap_does_not_create_weak_administrator(self):
        from unittest.mock import patch
        import os
        with patch.dict(os.environ,{'DEPLOYMENT_MODE':'public','BOOTSTRAP_ADMIN_PASSWORD':'1234'}):
            with self.assertRaises(ValueError):self.db.bootstrap_admin()
        self.assertIsNone(self.db.one("SELECT id FROM users WHERE username='user'"))
