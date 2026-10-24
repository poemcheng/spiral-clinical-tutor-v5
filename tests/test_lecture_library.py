import hashlib,json,unittest
from pathlib import Path
from unittest.mock import patch
import test_uploaded_workflow as fixtures
from backend import server,lecture_library,characters

class LectureLibraryTests(unittest.TestCase):
    setUp=fixtures.UploadedWorkflowTests.setUp
    tearDown=fixtures.UploadedWorkflowTests.tearDown
    start=fixtures.UploadedWorkflowTests.start

    def prepare(self):
        sid,_=self.start('DT');self.client.post(f'/api/sessions/{sid}/case',json={'case_id':'COURSE-SARC'})
        payload=json.loads(self.db.one('SELECT data FROM sessions WHERE id=?',(sid,))['data'])
        root=Path(self.tmp.name)/'lectures';root.mkdir();(root/'fixture.mp4').write_bytes(b'0123456789abcdef')
        actor=characters.selected({'profession':'DT','payload':payload},'lecturer')
        entry={'id':'a'*24,'case_id':'COURSE-SARC','audiences':['DT'],'actor_id':actor['id'],'actor_name':actor['name'],'actor_gender':actor['gender'],
               'actor_model_sha256':actor['realistic_model_sha256'],'source_fingerprint':lecture_library.source_fingerprint(payload['case_snapshot']),
               'title':'來源導讀','review_status':'待教師核定','teaching_purpose':'核對資料及分工','lecturer_scope':'營養專業導讀','script':[['情境','來源逐字稿']]*3,
               'modules':[{'module':i,'title':'情境','duration':3,'sha256':hashlib.sha256(b'0123456789abcdef').hexdigest(),'bytes':16,'file':'fixture.mp4'} for i in range(3)]}
        (root/'catalog.json').write_text(json.dumps({'lectures':[entry]}),encoding='utf8')
        return sid,root,entry

    def test_remote_playback_has_range_support_and_never_starts_a_renderer(self):
        sid,root,entry=self.prepare()
        with patch.object(lecture_library,'DIRECTORY',root),patch.object(server.threading,'Thread') as thread:
            learning=self.client.get(f'/api/sessions/{sid}/learning').json()
            self.assertFalse(learning['can_generate_video']);self.assertEqual(len(learning['lecture_library']['lectures'][0]['modules']),1)
            self.assertEqual(self.client.post(f'/api/sessions/{sid}/video',json={'module':0}).json()['published'],True);thread.assert_not_called()
            url=learning['lecture_library']['lectures'][0]['modules'][0]['url'];r=self.client.get(url,headers={'Range':'bytes=4-7'})
            self.assertEqual(r.status_code,206,r.text);self.assertEqual(r.content,b'4567');self.assertEqual(r.headers['content-type'],'video/mp4')
            self.assertEqual(self.client.get(url.replace('/0','/1')).status_code,403)

    def test_stale_source_actor_and_corrupt_media_cannot_be_served_as_current(self):
        sid,root,entry=self.prepare();url=f"/api/sessions/{sid}/lecture-library/{entry['id']}/0"
        with patch.object(lecture_library,'DIRECTORY',root):
            (root/'fixture.mp4').write_bytes(b'fedcba9876543210');self.assertEqual(self.client.get(url).status_code,404)
            entry['source_fingerprint']='f'*64;(root/'catalog.json').write_text(json.dumps({'lectures':[entry]}))
            self.assertEqual(self.client.get(f'/api/sessions/{sid}/lecture-library').json()['lectures'],[])
            self.assertEqual(self.client.get(url).status_code,404)

    def test_remote_missing_video_has_actionable_message_and_local_host_can_queue(self):
        sid,root,entry=self.prepare();(root/'catalog.json').write_text('{"lectures":[]}')
        with patch.object(lecture_library,'DIRECTORY',root),patch.object(server.threading,'Thread') as thread:
            response=self.client.post(f'/api/sessions/{sid}/video',json={'module':0})
            self.assertEqual(response.status_code,409);self.assertIn('主機本機',response.json()['detail']);thread.assert_not_called()
            response=self.client.post(f'/api/sessions/{sid}/video',json={'module':0},headers={'Host':'localhost'})
            self.assertEqual(response.status_code,200,response.text);thread.return_value.start.assert_called_once()

    def test_publication_plan_covers_all_39_tasks_and_does_not_require_personal_scores(self):
        from tools.build_lecture_library import plans
        p=plans();actual={(x['case']['id'],x['profession']) for x in p if x['actor']['id']!='he-sw'}
        self.assertEqual(len(actual),39);self.assertEqual(len({x['actor']['id'] for x in p}),8)
        self.assertTrue(all(len(x['sections'])==3 for x in p))
        case=server.registry.case('COURSE-SARC');before=lecture_library.source_fingerprint(case)
        altered={**case,'variant':{'level':5,'weak_dimensions':['COM']},'goals':['personal draft']}
        self.assertEqual(before,lecture_library.source_fingerprint(altered))
