"""Source fidelity, access control and the uploaded Step 1–4 workflow."""
import json
import tempfile
import unittest
from unittest.mock import patch
from types import SimpleNamespace
from pathlib import Path
from fastapi.testclient import TestClient
from backend import server, curriculum, sarcopenia_bank
from backend.assessment import create_snapshot, public_snapshot
from backend.store import Store


class UploadedWorkflowTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.previous=server.store
        server.store=Store(Path(self.tmp.name)/'test.sqlite3');self.db=server.store
        self.db.create_user('source-student','Source-Test-2026!','student','測試學員')
        self.db.create_user('source-teacher','Source-Test-2026!','teacher','測試教師')
        self.client=TestClient(server.app);self.faculty=TestClient(server.app)
        for client,name in [(self.client,'source-student'),(self.faculty,'source-teacher')]:
            self.assertEqual(client.post('/api/auth/login',json={'username':name,'password':'Source-Test-2026!'}).status_code,200)

    def tearDown(self):
        self.client.close();self.faculty.close();self.db.conn.close();server.store=self.previous;self.tmp.cleanup()

    def start(self,profession='DT',topic='肌少症',level=1):
        if level>1:
            with self.db.tx() as c:c.execute('INSERT INTO progress VALUES (?,?,?,?,?)',(self.db.one("SELECT id FROM users WHERE username='source-student'")['id'],profession,topic,level,1))
        entry=self.client.post('/api/entry',json={'profession':profession,'topic':topic}).json()
        self.assertEqual(entry['approved_level'],level)
        body={'answers':{q['item_id']:level for q in entry['snapshot']['items']},'objective_answers':{
            q['item_id']:q['options'][0] if q['item_type']=='single_choice' else '先核對飲食份量、種類與頻率，再設定追蹤目標。' for q in entry['snapshot']['objectives']}}
        response=self.client.post(f"/api/assessments/{entry['attempt_id']}/submit",json=body)
        self.assertEqual(response.status_code,200,response.text)
        return response.json()['session_id'],entry

    def interaction(self,profession='DT',topic='肌少症',level=1,case_id='COURSE-SARC'):
        sid,entry=self.start(profession,topic,level)
        response=self.client.post(f'/api/sessions/{sid}/case',json={'case_id':case_id})
        self.assertEqual(response.status_code,200,response.text)
        self.assertEqual(self.client.post(f'/api/sessions/{sid}/learned',json={'reflection':'測試：先釐清案例疑慮、資料缺口與職類界線。','completed_modules':[0],'observed':True}).status_code,200)
        return sid,entry

    def test_uploaded_bank_source_fidelity_and_no_rubric_leak(self):
        bank=sarcopenia_bank.load_bank();self.assertEqual(bank['attachment_source']['items'],1250)
        self.assertEqual(bank['attachment_source']['review_counts'],{'待審':1250})
        for profession in ['DT','PT','RT','MD','RN']:
            for level in range(1,6):
                snapshot=create_snapshot(server.registry,profession,'肌少症',level)
                self.assertTrue(all(q['attachment_source']['sha256']==bank['attachment_source']['sha256'] for q in snapshot['reference_self_items']+snapshot['objectives']))
                for q in public_snapshot(snapshot)['objectives']:
                    self.assertFalse({'answer','rubric','rubric_source_text','expected_keywords','explanation'}&set(q))
        self.assertEqual(self.client.get('/api/materials/questions').status_code,403)
        from backend.config import ROOT
        expected=200 if (ROOT/'data/sources/肌少症自評題庫_審題表_20261021.xlsx').is_file() else 404
        self.assertEqual(self.faculty.get('/api/materials/questions').status_code,expected)

    def test_nine_courses_thirty_nine_roles_and_five_levels(self):
        self.assertEqual(len(curriculum.COURSES),9)
        self.assertEqual(sum(len(c['professions']) for c in curriculum.COURSES.values()),39)
        for course in curriculum.COURSES.values():
            for profession in course['professions']:
                for level in range(1,6):
                    case=curriculum.adapt_case(server.registry.case(course['id']),profession,level,{'self_dimensions':{'CJ':20,'COM':100,'PC':100,'SAFE':100,'TC':100,'HC':100}})
                    self.assertEqual(case['variant']['level'],level)
                    self.assertEqual(case['variant']['role_task'],course['roles'][profession]['task'])
                    self.assertIn('CJ',case['variant']['weak_dimensions'])
                    self.assertTrue(case['kdp'])
        sid,_=self.start('OT','懷孕婦女外傷')
        self.assertIsInstance(sid,int)
        self.client.post(f'/api/sessions/{sid}/case',json={'case_id':'COURSE-PREG'})
        self.assertIsNone(self.client.get(f'/api/sessions/{sid}/learning').json()['library_video'])
        self.assertEqual(self.client.get(f'/api/sessions/{sid}/library-video').status_code,403)

    def test_hint_permissions_and_safety_remediation_preserves_evidence(self):
        sid,_=self.interaction(level=3)
        questions=self.client.get(f'/api/sessions/{sid}/interaction').json()['questions']
        self.assertTrue(all(q['hint'] is None for q in questions))
        self.assertEqual(self.client.post(f'/api/sessions/{sid}/hint',json={'item_id':questions[0]['id']}).status_code,200)
        self.assertEqual(self.client.post(f'/api/sessions/{sid}/hint',json={'item_id':questions[1]['id']}).status_code,403)
        raw=json.loads(self.db.one('SELECT data FROM sessions WHERE id=?',(sid,))['data'])
        critical=next(q for q in raw['case_snapshot']['kdp'] if q['critical'])
        wrong=next(i for i,o in enumerate(critical['options']) if o['score']==0)
        self.client.post(f'/api/sessions/{sid}/decision',json={'item_id':critical['id'],'option_id':f'o{wrong}'})
        self.assertTrue(self.client.get(f'/api/sessions/{sid}/interaction').json()['safety_blocked'])
        self.assertEqual(self.client.post(f'/api/sessions/{sid}/handoff',json={k:'需要核對資料並向團隊交接安排。' for k in 'SBAR'}).status_code,409)
        self.assertEqual(self.client.post(f'/api/sessions/{sid}/remediate',json={'reflection':'先停止不安全處理，確認風險後請教師協助重新練習。'}).status_code,200)
        after=json.loads(self.db.one('SELECT data FROM sessions WHERE id=?',(sid,))['data'])
        self.assertFalse(after['safety_blocked']);self.assertEqual(after['decisions'],{})
        self.assertEqual(after['remediation_history'][0]['decisions'][critical['id']]['score'],0)

    def test_open_answer_review_is_teacher_only_append_only(self):
        sid,entry=self.start()
        aid=entry['attempt_id'];snap=json.loads(self.db.one('SELECT snapshot FROM attempts WHERE id=?',(aid,))['snapshot'])
        open_item=next((q for q in snap['objectives'] if q['item_type']=='short_answer'),None)
        if open_item is None:
            # Sampling permits zero or one open question; insert a known sampled open item as a controlled fixture.
            open_item=next(q for q in sarcopenia_bank.cell('DT',1)['objective'] if q['item_type']=='short_answer')
            snap['objectives'].append(open_item)
            with self.db.tx() as c:c.execute('UPDATE attempts SET snapshot=? WHERE id=?',(json.dumps(snap),aid))
        body={'item_id':open_item['item_id'],'score':1,'note':'已指出部分詢問重點，仍需確認頻率與總量。','expected_review_id':0}
        self.assertEqual(self.client.post(f'/api/teacher/assessments/{aid}/review',json=body).status_code,403)
        self.assertEqual(self.faculty.post(f'/api/teacher/assessments/{aid}/review',json=body).status_code,200)
        self.assertEqual(self.faculty.post(f'/api/teacher/assessments/{aid}/review',json=body).status_code,409)
        detail=self.client.get(f'/api/assessments/{aid}').json()
        self.assertEqual(detail['item_reviews'][0]['score'],1)
        self.assertEqual(self.client.get(f'/api/sessions/{sid}').json()['level'],1)

    def test_level_five_peer_mode_is_separate_from_patient_dialogue(self):
        sid,_=self.interaction(level=5)
        with patch.object(server.llm,'check',return_value=SimpleNamespace(ready=True)),patch.object(server,'peer_reply',return_value=(SimpleNamespace(ok=True,text='我是Level 2學員，我的開場方式需要您的指導。',model='synthetic-peer'),{})):
            reply=self.client.post(f'/api/sessions/{sid}/chat',json={'text':'請先說明你的開場想法。','mode':'peer','request_id':'level5-peer-test'})
            self.assertEqual(reply.status_code,200,reply.text)
            self.assertEqual(reply.json()['metadata']['mode'],'peer')
        interaction=self.client.get(f'/api/sessions/{sid}/interaction').json()
        self.assertEqual(interaction['hint_budget'],0)
        self.assertEqual(self.client.post(f'/api/sessions/{sid}/hint',json={'item_id':interaction['questions'][0]['id']}).status_code,403)
        sid2,_=self.interaction(profession='PT',level=1)
        self.assertEqual(self.client.post(f'/api/sessions/{sid2}/chat',json={'text':'測試權限','mode':'peer','request_id':'level1-deny-peer'}).status_code,403)

    def test_virtual_video_upgrade_preserves_legacy_media_and_serves_new_file(self):
        sid,_=self.start()
        self.client.post(f'/api/sessions/{sid}/case',json={'case_id':'COURSE-SARC'})
        row=self.db.one('SELECT * FROM sessions WHERE id=?',(sid,));row['payload']=json.loads(row['data'])
        row['payload']['generated_videos']={'0':{'source':'ai_generated','has_audio':False,'url':f'/api/sessions/{sid}/generated-video/0'}}
        with self.db.tx() as c:self.db.save(c,sid,row['payload'])
        runtime=Path(self.tmp.name)/'runtime';legacy=runtime/'media'/f'session_{sid*10}'/'training_video.mp4'
        legacy.parent.mkdir(parents=True);legacy.write_bytes(b'legacy-evidence-must-survive')
        sample=runtime/'synthetic-render.mp4';sample.write_bytes(b'synthetic-render-evidence')
        manifest={'source':'source_bound_virtual_lecturer','duration':45.08,'has_audio':True,'key':'0123456789abcdef0123'}
        with patch.object(server,'RUNTIME',runtime),patch.object(server.virtual_video,'render',return_value=(sample,manifest)):
            server.video_worker(sid,row['payload']['case_snapshot'],row,0)
            data=json.loads(self.db.one('SELECT data FROM sessions WHERE id=?',(sid,))['data'])
            self.assertEqual(data['video_job']['status'],'completed',data['video_job'])
            self.assertEqual(data['generated_videos']['0']['file_name'],'virtual_training_video_0123456789abcdef0123.mp4')
            self.assertEqual(len(data['generated_video_history']),1)
            response=self.client.get(f'/api/sessions/{sid}/generated-video/0')
            self.assertEqual(response.status_code,200);self.assertEqual(response.content,sample.read_bytes())
            second=runtime/'another-render.mp4';second.write_bytes(b'new-version-evidence')
            newer={**manifest,'key':'abcdef0123456789abcd'}
            with patch.object(server.virtual_video,'render',return_value=(second,newer)):
                server.video_worker(sid,row['payload']['case_snapshot'],row,0)
            self.assertEqual(self.client.get(f'/api/sessions/{sid}/generated-video/0').content,b'new-version-evidence')
            self.assertEqual(self.client.get(f'/api/sessions/{sid}/generated-video/0?version=0123456789abcdef0123').content,sample.read_bytes())
        self.assertEqual(legacy.read_bytes(),b'legacy-evidence-must-survive')

