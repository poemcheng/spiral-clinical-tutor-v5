import json
import math
from pathlib import Path
import time
import unittest
from unittest.mock import patch
from backend import learning_resources,pose_analysis,server
from backend.interaction_policy import policy,response_stance
import test_frame_review as fixtures


class PoseMathTests(unittest.TestCase):
    def test_occluded_joints_never_get_angles_or_intent_labels(self):
        p=[{'x':.5,'y':.5,'visibility':.1,'presence':.99} for _ in range(33)]
        values,tags=pose_analysis.metrics(p)
        self.assertTrue(all(v is None for v in values.values()));self.assertEqual(tags,[])
        self.assertIn('無法確認',pose_analysis.meanings(tags)[0]['possible'])

    def test_visible_right_angle_is_projected_not_metric_measurement(self):
        p=[{'x':.5,'y':.5,'visibility':0,'presence':0} for _ in range(33)]
        for i,x,y in [(11,.25,.5),(13,.5,.5),(15,.5,.25)]:p[i]={'x':x,'y':y,'visibility':.9,'presence':.9}
        m,tags=pose_analysis.metrics(p);self.assertEqual(m['left_elbow'],90);self.assertIn('左肘彎曲',tags)
        h=pose_analysis.meanings(tags)[0];self.assertIn('可能',h['possible']);self.assertTrue(h['alternative']);self.assertTrue(h['verify'])

    def test_self_difficulty_depends_on_actor_context_not_earned_access(self):
        self.assertIn('新手友善',policy(1,'clinician')['behavior'])
        self.assertIn('權威',policy(5,'clinician')['behavior'])
        self.assertIn('難以合作',policy(5,'patient')['behavior'])
        self.assertNotIn('教導',policy(5,'patient')['behavior'])
        self.assertEqual(policy(5,'patient')['self_level'],5)

    def test_coercive_dialogue_requires_l5_resistance_but_negated_reflection_does_not(self):
        t='先照我的安排做就好，我覺得你原本的判斷不太對。'
        self.assertFalse(response_stance(1,'patient',t,False)['applied'])
        self.assertIn('不願意',response_stance(5,'patient',t,False)['prefix'])
        self.assertIn('專業判斷',response_stance(5,'clinician',t,False)['prefix'])
        self.assertFalse(response_stance(5,'patient','我不會要求你照我的安排，我想先了解您的顧慮。',False)['applied'])


class PoseApiTests(unittest.TestCase):
    setUp=fixtures.FrameReviewTests.setUp
    tearDown=fixtures.FrameReviewTests.tearDown
    start=fixtures.FrameReviewTests.start
    setup_note=fixtures.FrameReviewTests.setup_note
    def test_pose_snapshot_is_bound_to_immutable_job_frame_source_and_view(self):
        sid,_=self.setup_note();tmp=Path(self.tmp.name)
        frame={'frame':30,'seconds':1.001,'poses':[]}
        result={'version':pose_analysis.VERSION,'model':'test-model','model_sha256':'b'*64,'view':{'yaw':20,'pitch':5},'frames':[frame],'limitation':'fixture'}
        folder=tmp/'pose_analysis'/('c'*32);folder.mkdir(parents=True)
        (folder/'result.json').write_text(json.dumps(result),encoding='utf-8')
        (folder/'frame-30.jpg').write_bytes(b'controlled-fixture')
        job={'id':'c'*32,'clip_id':'fixture','status':'completed','result_sha256':pose_analysis.digest(folder/'result.json')}
        with self.db.tx() as c:
            data=json.loads(self.db.one('SELECT data FROM sessions WHERE id=?',(sid,))['data']);data['pose_jobs']=[job];self.db.save(c,sid,data)
        clip={'id':'fixture','duration':10,'fps':30000/1001,'proxy_sha256':'a'*64}
        body={'clip_id':'fixture','seconds':1.001,'yaw':20,'pitch':5,'observation':'此格未偵測可靠人體，不推斷對方意圖。','analysis_id':'c'*32,'analysis_frame':30}
        with patch.object(learning_resources,'RUNTIME',tmp),patch.object(learning_resources,'manifest',return_value={'clips':[clip]}):
            bad=self.client.post(f'/api/sessions/{sid}/frame-notes',json={**body,'yaw':25});self.assertEqual(bad.status_code,400)
            zoom=self.client.post(f'/api/sessions/{sid}/frame-notes',json={**body,'fov':50});self.assertEqual(zoom.status_code,400)
            adjacent=self.client.post(f'/api/sessions/{sid}/frame-notes',json={**body,'seconds':1.02});self.assertEqual(adjacent.status_code,400)
            good=self.client.post(f'/api/sessions/{sid}/frame-notes',json=body);self.assertEqual(good.status_code,200,good.text)
            self.assertEqual(good.json()['analysis_snapshot']['result_sha256'],job['result_sha256'])
            self.assertEqual(self.faculty.get(f'/api/sessions/{sid}/pose-analysis/{job["id"]}/frames/30').status_code,200)
            self.assertEqual(self.client.get(f'/api/sessions/{sid}/pose-analysis/{"d"*32}/result').status_code,404)
            (folder/'result.json').write_text('{}',encoding='utf-8')
            self.assertEqual(self.client.get(f'/api/sessions/{sid}/pose-analysis/{job["id"]}/result').status_code,409)

    def test_invalid_interval_unknown_clip_and_teacher_cannot_start(self):
        sid,_=self.setup_note();url=f'/api/sessions/{sid}/pose-analysis'
        self.assertEqual(self.faculty.post(url,json={'clip_id':'missing','start':0,'end':2}).status_code,403)
        self.assertEqual(self.client.post(url,json={'clip_id':'missing','start':0,'end':2}).status_code,404)
        self.assertEqual(self.client.post(url,json={'clip_id':'missing','start':-1,'end':2}).status_code,422)
