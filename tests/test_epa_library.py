"""Earned Level 4 access, source binding, pagination integrity and feedback evidence."""
import copy,gzip,hashlib,json
from pathlib import Path
from unittest.mock import patch
import unittest
from fastapi.testclient import TestClient
from backend import server,epa_library,teaching_media,learning_resources
import test_frame_review as fixtures

class EPALibraryTests(unittest.TestCase):
    setUp=fixtures.FrameReviewTests.setUp
    tearDown=fixtures.FrameReviewTests.tearDown
    start=fixtures.FrameReviewTests.start
    setup_note=fixtures.FrameReviewTests.setup_note

    def fixture(self):
        sid,_=self.setup_note();root=Path(self.tmp.name)/'epa';root.mkdir();video=root/'synthetic.mp4';video.write_bytes(b'controlled synthetic video fixture')
        sha=hashlib.sha256(video.read_bytes()).hexdigest();ident='a'*32;folder=root/'analyses'/ident;folder.mkdir(parents=True)
        clip={'id':'epa-fixture','title':'Synthetic EPA fixture','topic':'肌少症','file':'synthetic.mp4','projection':'flat','fps':30,'duration':2,'proxy_sha256':sha,'source_sha256':sha,'status':'synthetic'}
        frames=[{'frame':i,'seconds':i/30,'poses':[],'status':'not detected'} for i in range(2)];raw=gzip.compress(json.dumps(frames).encode());(folder/'frames-00000.json.gz').write_bytes(raw)
        for i in range(2):(folder/f'frame-{i}.jpg').write_bytes(b'controlled jpeg response fixture');(folder/f'raw-frame-{i}.jpg').write_bytes(b'controlled raw response fixture')
        item={'id':ident,'clip_id':clip['id'],'title':clip['title'],'status':'completed','projection':'flat','source_sha256':sha,'model_sha256':'b'*64,'first_frame':0,'last_frame':1,'frame_count':2,'detection_frames':0,'fps':30,'view':{'yaw':0,'pitch':0,'fov':70},'analyzed_every_frame':True,'version':epa_library.VERSION}
        index={'complete':True,'actual_video_sha256':sha,'model_sha256':'b'*64,'model':'synthetic pose','limitation':'not clinical','result_sha256':'c'*64,'chunks':[{'file':'frames-00000.json.gz','first':0,'last':1,'sha256':hashlib.sha256(raw).hexdigest()}]}
        (folder/'index.json').write_text(json.dumps(index));(root/'catalog.json').write_text(json.dumps({'analyses':[item]}));(root/'annotations.json').write_text(json.dumps({'clips':{clip['id']:{'segments':[{'id':'S1','start':0,'end':2,'title':'Synthetic phase','visible_action':'unverified source context'}],'keyframes':[],'sources':[]}}}))
        for patcher in [patch.object(epa_library,'LIB',root),patch.object(teaching_media,'manifest',return_value={'clips':[clip]}),patch.object(teaching_media,'path_for',return_value=video)]:patcher.start();self.addCleanup(patcher.stop)
        return sid,root,clip,item

    def level(self,sid,n):
        with self.db.tx() as c:
            d=json.loads(self.db.one('SELECT data FROM sessions WHERE id=?',(sid,))['data']);d['adaptive_plan']['learning_level']=n;self.db.save(c,sid,d)

    def test_self_rating_does_not_unlock_but_earned_four_opens_frame_and_report(self):
        sid,root,clip,item=self.fixture();url=f'/api/sessions/{sid}/epa-lessons';self.level(sid,3)
        self.assertEqual(self.client.get(url).status_code,403);self.assertEqual(self.client.get(url+'/'+clip['id']+'/report').status_code,403)
        self.assertFalse(self.client.get(f'/api/sessions/{sid}/learning').json()['resources']['epa_library']['unlocked'])
        self.level(sid,4);response=self.client.get(url+'/'+clip['id']+'/report');self.assertEqual(response.status_code,200,response.text);self.assertFalse(response.json()['has_audio_transcript'])
        frame=self.client.get(url+'/'+clip['id']+'/frames/1');self.assertEqual(frame.status_code,200);self.assertEqual(frame.json()['poses'],[]);self.assertEqual(frame.json()['annotation']['id'],'S1')
        self.assertEqual(self.client.get(url+'/'+clip['id']+'/frames/2').status_code,404)
        self.assertEqual(self.client.get(url+'/'+clip['id']+'/frames/1/image').status_code,200)
        with TestClient(server.app) as anonymous:self.assertEqual(anonymous.get(url).status_code,401)

    def test_corrupt_chunk_or_changed_video_is_rejected(self):
        sid,root,clip,item=self.fixture();url=f'/api/sessions/{sid}/epa-lessons/{clip["id"]}'
        part=root/'analyses'/item['id']/'frames-00000.json.gz';part.write_bytes(b'x'*len(part.read_bytes()));self.assertEqual(self.client.get(url+'/frames/1').status_code,409)
        (root/'synthetic.mp4').write_bytes(b'changed video');self.assertEqual(self.client.get(url+'/report').status_code,409)

    def test_topic_bound_access_and_level_four_observation_freeze_source_and_annotation(self):
        sid,root,clip,item=self.fixture();self.level(sid,4)
        body={'clip_id':clip['id'],'seconds':1/30,'yaw':0,'pitch':0,'fov':70,'epa_analysis_id':item['id'],'analysis_frame':1,'observation':'本格無可靠骨架，人工段落功能仍須核對前後原圖與原音。'}
        before=json.loads(self.db.one('SELECT data FROM sessions WHERE id=?',(sid,))['data'])
        self.assertEqual(self.client.post(f'/api/sessions/{sid}/frame-notes',json={**body,'epa_analysis_id':'d'*32}).status_code,400)
        saved=self.client.post(f'/api/sessions/{sid}/frame-notes',json=body);self.assertEqual(saved.status_code,200,saved.text);note=saved.json();self.assertEqual(note['analysis_snapshot']['origin'],'epa_library');self.assertEqual(note['analysis_snapshot']['epa_annotation']['id'],'S1')
        self.assertEqual(self.client.post(f'/api/sessions/{sid}/frame-notes',json={**body,'analysis_id':'a'*32}).status_code,400)
        after=json.loads(self.db.one('SELECT data FROM sessions WHERE id=?',(sid,))['data']);self.assertEqual({k:v for k,v in after.items() if k!='frame_notes'},{k:v for k,v in before.items() if k!='frame_notes'})
        clip['topic']='其他主題';self.assertEqual(self.client.get(f'/api/sessions/{sid}/epa-lessons/{clip["id"]}/report').status_code,404)

    def test_teacher_feedback_retains_the_level_four_learner_observation(self):
        sid,root,clip,item=self.fixture();self.level(sid,4)
        body={'clip_id':clip['id'],'seconds':0,'epa_analysis_id':item['id'],'analysis_frame':0,'observation':'來源教學目的與本格可見證據分開，尚不能確認動作意圖。'}
        saved=self.client.post(f'/api/sessions/{sid}/frame-notes',json=body);self.assertEqual(saved.status_code,200,saved.text)
        note=saved.json();review=self.faculty.post(f'/api/teacher/sessions/{sid}/frame-notes/1/reviews',json={'decision':'needs_revision','feedback':'請核對前後原音與下一張影格，再說明可能動作目的。','expected_review_id':''});self.assertEqual(review.status_code,200,review.text)
        data=self.faculty.get(f'/api/teacher/sessions/{sid}').json()['data'];self.assertEqual(data['frame_notes'][1],note);self.assertEqual(data['frame_note_reviews'][-1]['note_index'],1)
        learner=self.client.get(f'/api/sessions/{sid}/learning').json()['resources'];self.assertEqual(learner['frame_reviews'][-1]['feedback'],review.json()['feedback'])

    def test_report_download_is_earned_level_scoped_and_hash_checked(self):
        sid,root,clip,item=self.fixture();reports=root/'reports';reports.mkdir();p=reports/'epa-fixture.html';p.write_bytes(b'<html>synthetic teaching report</html>')
        manifest={clip['id']:{'file':p.name,'analysis_id':item['id'],'source_sha256':item['source_sha256'],'sha256':hashlib.sha256(p.read_bytes()).hexdigest()}}
        (reports/'manifest.json').write_text(json.dumps(manifest));url=f'/api/sessions/{sid}/epa-lessons/{clip["id"]}/download'
        self.level(sid,3);self.assertEqual(self.client.get(url).status_code,403)
        self.level(sid,4);r=self.client.get(url);self.assertEqual(r.status_code,200);self.assertIn('attachment',r.headers['content-disposition'])
        p.write_bytes(b'x'*p.stat().st_size);self.assertEqual(self.client.get(url).status_code,409)
