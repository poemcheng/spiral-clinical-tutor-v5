"""Character casting and client-reported practice cannot change case facts or grades."""
import hashlib
import json
import struct
from unittest.mock import patch
from types import SimpleNamespace
from pathlib import Path
import test_uploaded_workflow as fixtures
from backend import characters,server

class CharacterTests(fixtures.UploadedWorkflowTests):
    # Reuse workflow fixture, not all inherited test executions.
    def test_actor_casting_preserves_medical_snapshot_and_separates_turns(self):
        sid,_=self.interaction('RN');before=self.db.one('SELECT data FROM sessions WHERE id=?',(sid,))
        original=json.loads(before['data'])['case_snapshot']
        self.assertEqual(self.client.post(f'/api/sessions/{sid}/actors',json={'purpose':'interaction','actor_id':'wang-pt'}).status_code,200)
        result=SimpleNamespace(ok=True,text='本案例未提供用藥清單，我們先核對資料。',model='test-fixture')
        with patch.object(server.llm,'check',return_value=SimpleNamespace(ready=True)),patch.object(server.llm,'chat',return_value=result) as llm:
            reply=self.client.post(f'/api/sessions/{sid}/chat',json={'text':'請確認既有資料缺口。','mode':'ai','request_id':'actor-test-request'}).json()
            self.assertEqual(reply['metadata']['actor']['id'],'wang-pt')
            self.assertIn('王物理治療師',llm.call_args.args[0][0]['content'])
        after=json.loads(self.db.one('SELECT data FROM sessions WHERE id=?',(sid,))['data'])
        self.assertEqual(after['case_snapshot'],original)
        self.assertEqual(self.faculty.post(f'/api/sessions/{sid}/actors',json={'purpose':'interaction','actor_id':'auntie-lin'}).status_code,403)
        self.assertEqual(self.client.post(f'/api/sessions/{sid}/actors',json={'purpose':'interaction','actor_id':'../../private'}).status_code,400)
        self.client.post(f'/api/sessions/{sid}/chat',json={'text':'請說明仍須核對的資訊。','mode':'scripted','request_id':'second-team-request'})
        for question in original['kdp']:
            best=max(range(len(question['options'])),key=lambda i:question['options'][i]['score'])
            self.assertEqual(self.client.post(f'/api/sessions/{sid}/decision',json={'item_id':question['id'],'option_id':f'o{best}'}).status_code,200)
        handoff={key:'測試：已核對案例已知資訊並記錄資料缺口。' for key in 'SBAR'}
        self.assertEqual(self.client.post(f'/api/sessions/{sid}/handoff',json=handoff).status_code,409)
        self.client.post(f'/api/sessions/{sid}/actors',json={'purpose':'interaction','actor_id':'auntie-lin'})
        for index in range(2):self.client.post(f'/api/sessions/{sid}/chat',json={'text':'想了解您的生活情境與疑慮。','mode':'scripted','request_id':f'patient-actual-{index}'})
        self.assertEqual(self.client.post(f'/api/sessions/{sid}/handoff',json=handoff).status_code,200)

    def test_h5p_practice_is_scoped_idempotent_and_never_changes_formal_scores(self):
        sid,_=self.interaction('RN');state=self.client.get(f'/api/sessions/{sid}/h5p/state').json()
        evidence={'event_id':'h5p-test-event','content_version':state['content_version'],'verb':'answered','result':{'score':{'raw':999999}},'state':{'answers':[1]}}
        before=json.loads(self.db.one('SELECT data FROM sessions WHERE id=?',(sid,))['data'])
        for _ in range(2):self.assertEqual(self.client.post(f'/api/sessions/{sid}/h5p/evidence',json=evidence).status_code,200)
        after=json.loads(self.db.one('SELECT data FROM sessions WHERE id=?',(sid,))['data'])
        self.assertEqual(before['decisions'],after['decisions']);self.assertNotIn('result',after)
        events=self.db.all("SELECT * FROM events WHERE session_id=? AND kind='h5p_practice'",(sid,));self.assertEqual(len(events),1)
        self.assertEqual(self.client.get(f'/api/sessions/{sid}/h5p/state').json()['state'],{'answers':[1]})
        self.client.post(f'/api/sessions/{sid}/actors',json={'purpose':'interaction','actor_id':'mr-wang'})
        self.assertEqual(self.client.post(f'/api/sessions/{sid}/h5p/evidence',json=evidence).status_code,409)
        self.assertEqual(self.faculty.post(f'/api/sessions/{sid}/h5p/evidence',json=evidence).status_code,403)

    def test_original_cards_and_valid_vrm_humanoid_assets(self):
        actors=self.client.get('/api/characters').json()['actors'];self.assertEqual(len(actors),13)
        for actor in actors:
            card=self.client.get(actor['card_url']);self.assertEqual(hashlib.sha256(card.content).hexdigest(),actor['card_sha256'])
            model=self.client.get(actor['model_url']).content;self.assertEqual(model[:4],b'glTF')
            size=struct.unpack_from('<I',model,12)[0];gltf=json.loads(model[20:20+size]);vrm=gltf['extensions']['VRMC_vrm']
            self.assertIn('hips',vrm['humanoid']['humanBones']);self.assertIn('aa',vrm['expressions']['preset'])
        from fastapi.testclient import TestClient
        with TestClient(server.app) as anonymous:self.assertEqual(anonymous.get(actors[0]['card_url']).status_code,401)

    def test_h5p_vendor_runtime_has_all_declared_assets(self):
        from backend.config import ROOT
        folder=ROOT/'frontend/vendor/h5p-libraries'
        for path in folder.glob('*/library.json'):
            lib=json.loads(path.read_text())
            for asset in lib.get('preloadedJs',[])+lib.get('preloadedCss',[]):
                self.assertTrue((path.parent/asset['path']).is_file(),str(path.parent/asset['path']))

    def test_photoreal_assets_are_authenticated_and_legacy_casts_resolve_current_visual(self):
        actors=self.client.get('/api/characters').json()['actors']
        for actor in actors:
            response=self.client.get(actor['atlas_url'])
            self.assertEqual(response.status_code,200)
            self.assertTrue(response.content.startswith(b'\x89PNG\r\n\x1a\n'))
            self.assertEqual(hashlib.sha256(response.content).hexdigest(),actor['atlas_sha256'])
        legacy={k:v for k,v in actors[0].items() if k not in ('atlas_url','atlas_file','atlas_sha256','face','visual_version','visual_type')}
        legacy['version']='historical-casting-version'
        row={'payload':{'actors':{'interaction':legacy}}}
        resolved=characters.selected(row)
        self.assertEqual(resolved['version'],'historical-casting-version')
        self.assertEqual(resolved['atlas_sha256'],actors[0]['atlas_sha256'])
        self.assertNotIn('atlas_file',row['payload']['actors']['interaction'])
        from fastapi.testclient import TestClient
        with TestClient(server.app) as anonymous:self.assertEqual(anonymous.get(actors[0]['atlas_url']).status_code,401)

    def test_livekit_browser_cannot_publish_and_unrelated_student_cannot_join(self):
        import base64
        sid,_=self.interaction()
        config={'LIVEKIT_URL':'ws://127.0.0.1:7880','LIVEKIT_API_KEY':'synthetic-key','LIVEKIT_API_SECRET':'synthetic-long-secret-for-tests-only'}
        with patch.object(server.voice_bridge,'ready',return_value=True),patch.object(server.voice_bridge,'connect',return_value=True),patch.object(server.voice_bridge,'settings',return_value=config):
            response=self.client.post(f'/api/sessions/{sid}/livekit')
            self.assertEqual(response.status_code,200,response.text)
            payload=response.json()['token'].split('.')[1]
            grants=json.loads(base64.urlsafe_b64decode(payload+'='*(-len(payload)%4)))
            self.assertFalse(grants['video']['canPublish']);self.assertFalse(grants['video']['canPublishData'])
        self.db.create_user('other-student','Source-Test-2026!','student')
        from fastapi.testclient import TestClient
        with TestClient(server.app) as other:
            other.post('/api/auth/login',json={'username':'other-student','password':'Source-Test-2026!'})
            self.assertEqual(other.post(f'/api/sessions/{sid}/livekit').status_code,404)

# Keep only new tests here; shared fixture methods come from UploadedWorkflowTests.
for name in list(dir(fixtures.UploadedWorkflowTests)):
    if name.startswith('test_'):setattr(CharacterTests,name,None)
