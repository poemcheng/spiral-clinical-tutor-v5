"""Real API/state checks for formative frame feedback and immutable observations."""
import copy
import json
from pathlib import Path
from unittest.mock import patch
import unittest
from fastapi.testclient import TestClient
from backend import server,learning_resources
from backend.learning_resources import note_fingerprint
import test_uploaded_workflow as fixtures


class FrameReviewTests(unittest.TestCase):
    setUp=fixtures.UploadedWorkflowTests.setUp
    tearDown=fixtures.UploadedWorkflowTests.tearDown
    start=fixtures.UploadedWorkflowTests.start
    interaction=fixtures.UploadedWorkflowTests.interaction

    def setup_note(self):
        sid,_=self.start('RT')
        self.client.post(f'/api/sessions/{sid}/case',json={'case_id':'COURSE-SARC'})
        row=self.db.one('SELECT data FROM sessions WHERE id=?',(sid,));payload=json.loads(row['data'])
        payload['adaptive_plan']['learning_level']=5
        with self.db.tx() as c:self.db.save(c,sid,payload)
        body={'clip_id':'fixture','seconds':1.001,'yaw':20,'pitch':5,'observation':'觀察交接後，接收者是否確認資訊與分工。'}
        clip={'id':'fixture','title':'Synthetic frame fixture','duration':10,'fps':30000/1001,'fps_rational':'30000/1001','projection':'equirectangular','proxy_sha256':'a'*64}
        with patch.object(learning_resources,'manifest',return_value={'clips':[clip]}):
            r=self.client.post(f'/api/sessions/{sid}/frame-notes',json=body)
        self.assertEqual(r.status_code,200,r.text)
        return sid,r.json()

    def body(self,previous=''):
        return {'decision':'needs_revision','feedback':'請指出接收職類的回覆內容，並核對是否形成共同追蹤計畫。','expected_review_id':previous}

    def test_note_freezes_media_identity_and_frame_rate(self):
        sid,note=self.setup_note()
        self.assertEqual(note['frame'],30)
        self.assertEqual(note['media_snapshot']['proxy_sha256'],'a'*64)
        self.assertEqual(note['media_snapshot']['fps_rational'],'30000/1001')
        saved=json.loads(self.db.one('SELECT data FROM sessions WHERE id=?',(sid,))['data'])
        self.assertEqual(saved['frame_notes'],[note])
        self.assertEqual(saved.get('frame_note_reviews',[]),[])

    def test_teacher_history_is_append_only_and_does_not_change_grade_or_levels(self):
        sid,note=self.setup_note();url=f'/api/teacher/sessions/{sid}/frame-notes/0/reviews'
        before=json.loads(self.db.one('SELECT data FROM sessions WHERE id=?',(sid,))['data'])
        first=self.faculty.post(url,json=self.body());self.assertEqual(first.status_code,200,first.text)
        r=first.json();self.assertEqual(r['note_sha256'],note_fingerprint(note));self.assertFalse(r['affects_formal_grade'])
        self.assertEqual(self.faculty.post(url,json=self.body()).status_code,409)
        second=self.faculty.post(url,json={**self.body(r['id']),'decision':'reviewed','feedback':'已核對學員觀察的具體行為，後續仍需實體技能評量。'})
        self.assertEqual(second.status_code,200,second.text)
        after=json.loads(self.db.one('SELECT data FROM sessions WHERE id=?',(sid,))['data'])
        self.assertEqual(after['frame_notes'],[note]);self.assertEqual(len(after['frame_note_reviews']),2)
        self.assertEqual({k:v for k,v in after.items() if k!='frame_note_reviews'},before)
        self.assertEqual(self.db.one('SELECT COUNT(*) n FROM reviews WHERE session_id=?',(sid,))['n'],0)
        exported=self.client.get(f'/api/sessions/{sid}/export')
        self.assertEqual(exported.status_code,200)
        self.assertIn(r['id'],exported.text)
        resources=self.client.get(f'/api/sessions/{sid}/learning').json()['resources']
        self.assertEqual(resources['frame_reviews'],after['frame_note_reviews'])

    def test_only_teachers_can_reply_and_invalid_observations_are_rejected(self):
        sid,_=self.setup_note();base=f'/api/teacher/sessions/{sid}/frame-notes'
        self.assertEqual(self.client.post(base+'/0/reviews',json=self.body()).status_code,403)
        with TestClient(server.app) as anonymous:
            self.assertEqual(anonymous.post(base+'/0/reviews',json=self.body()).status_code,401)
        self.assertEqual(self.faculty.post(base+'/-1/reviews',json=self.body()).status_code,404)
        self.assertEqual(self.faculty.post(base+'/99/reviews',json=self.body()).status_code,404)
        self.assertEqual(self.faculty.post(base+'/0/reviews',json={**self.body(),'decision':'approve_grade'}).status_code,422)
        self.assertEqual(self.faculty.post(base+'/0/reviews',json={**self.body(),'feedback':' '*20}).status_code,400)

    def test_completed_session_allows_feedback_but_keeps_original_evidence(self):
        sid,note=self.setup_note()
        payload=json.loads(self.db.one('SELECT data FROM sessions WHERE id=?',(sid,))['data']);payload['result']={'objective_score':80,'teacher_status':'pending'}
        with self.db.tx() as c:self.db.save(c,sid,payload,status='completed')
        r=self.faculty.post(f'/api/teacher/sessions/{sid}/frame-notes/0/reviews',json=self.body())
        self.assertEqual(r.status_code,200,r.text)
        row=self.db.one('SELECT status,data FROM sessions WHERE id=?',(sid,));data=json.loads(row['data'])
        self.assertEqual(row['status'],'completed');self.assertEqual(data['result'],payload['result']);self.assertEqual(data['frame_notes'],[note])
        self.assertEqual(self.client.post(f'/api/sessions/{sid}/frame-notes',json={k:note[k] for k in ('clip_id','seconds','yaw','pitch','observation')}).status_code,409)

    def test_legacy_notes_remain_readable_and_keep_their_original_hash(self):
        sid,note=self.setup_note();legacy=copy.deepcopy(note);legacy.pop('media_snapshot')
        payload=json.loads(self.db.one('SELECT data FROM sessions WHERE id=?',(sid,))['data']);payload['frame_notes']=[legacy]
        with self.db.tx() as c:self.db.save(c,sid,payload)
        r=self.faculty.post(f'/api/teacher/sessions/{sid}/frame-notes/0/reviews',json=self.body())
        self.assertEqual(r.status_code,200,r.text);self.assertEqual(r.json()['note_sha256'],note_fingerprint(legacy))
        self.assertEqual(self.faculty.get(f'/api/teacher/sessions/{sid}').json()['data']['frame_notes'],[legacy])
