"""Five actual curriculum tiers, conventional video and snapshot integrity."""
import copy,json,time
from pathlib import Path
from unittest.mock import patch
import unittest
from backend import server,learning_resources,learning_curriculum,teaching_media,pose_analysis
import test_frame_review as fixtures

class CumulativeLessonTests(unittest.TestCase):
    setUp=fixtures.FrameReviewTests.setUp
    tearDown=fixtures.FrameReviewTests.tearDown
    start=fixtures.FrameReviewTests.start
    setup_note=fixtures.FrameReviewTests.setup_note

    def set_level(self,sid,level):
        with self.db.tx() as c:
            d=json.loads(self.db.one('SELECT data FROM sessions WHERE id=?',(sid,))['data']);d['adaptive_plan']['learning_level']=level;self.db.save(c,sid,d)

    def test_all_five_levels_add_lessons_and_keep_earlier_content(self):
        sid,_=self.setup_note();previous=[]
        for level in range(1,6):
            self.set_level(sid,level)
            r=self.client.get(f'/api/sessions/{sid}/learning').json()['resources'];tiers=r['lesson_levels']
            self.assertEqual([x['level'] for x in tiers],list(range(1,6)))
            lessons=[l for t in tiers for l in t.get('lessons',[])]
            self.assertEqual(len(lessons),level*2)
            self.assertEqual([l['id'] for l in lessons][:len(previous)],previous)
            self.assertTrue(all(l['purpose'] and l['knowledge'] and l['observe'] and l['question'] and l['sources'] for l in lessons))
            self.assertTrue(all('lessons' not in t for t in tiers if not t['unlocked']))
            previous=[l['id'] for l in lessons]
        self.assertEqual(tiers[2]['title'],'一般影片教案')

    def test_learning_reflections_respect_unlock_and_preserve_grades(self):
        sid,_=self.setup_note();self.set_level(sid,2)
        r=self.client.get(f'/api/sessions/{sid}/learning').json()['resources']
        own=r['lesson_levels'][1]['lessons'][0]['id'];url=f'/api/sessions/{sid}/learning-notes'
        body={'lesson_id':own,'reflection':'先確認本職類已知資料，再向接收職類提出具體資訊缺口。'}
        before=json.loads(self.db.one('SELECT data FROM sessions WHERE id=?',(sid,))['data'])
        self.assertEqual(self.faculty.post(url,json=body).status_code,403)
        self.assertEqual(self.client.post(url,json={**body,'lesson_id':own.replace('-L2-','-L5-')}).status_code,403)
        saved=self.client.post(url,json=body);self.assertEqual(saved.status_code,200,saved.text)
        item=saved.json();self.assertEqual(item['lesson_snapshot']['level'],2);self.assertFalse(item['affects_formal_grade'])
        after=json.loads(self.db.one('SELECT data FROM sessions WHERE id=?',(sid,))['data'])
        self.assertEqual({k:v for k,v in after.items() if k!='learning_notes'},before)
        self.assertEqual(self.faculty.get(f'/api/teacher/sessions/{sid}').json()['data']['learning_notes'][0],item)

    def test_conventional_video_unlocked_at_three_and_topic_scoped(self):
        sid,_=self.setup_note();self.set_level(sid,3)
        f=Path(self.tmp.name)/'fixture.mp4';f.write_bytes(b'fixture-video')
        clip={'id':'flat-fixture','file':'fixture.mp4','title':'Plain film','topic':'肌少症','projection':'flat','duration':20,'fps':24,'status':'fixture'}
        with patch.object(learning_resources,'manifest',return_value={'clips':[clip]}),patch.object(teaching_media,'path_for',return_value=f):
            self.assertEqual(self.client.get(f'/api/sessions/{sid}/resources/video/flat-fixture').status_code,200)
            self.assertEqual(len(self.client.get(f'/api/sessions/{sid}/learning').json()['resources']['media']),1)
            self.set_level(sid,2)
            self.assertEqual(self.client.get(f'/api/sessions/{sid}/resources/video/flat-fixture').status_code,403)
            self.assertEqual(self.client.get(f'/api/sessions/{sid}/learning').json()['resources']['media'],[])
            clip['topic']='其他主題'
            self.assertEqual(self.client.get(f'/api/sessions/{sid}/resources/video/flat-fixture').status_code,404)

    def test_video_steps_partition_both_films_without_gaps_or_overlaps(self):
        clips=[c for c in teaching_media.manifest()['clips'] if c['id'] in ('sarc-analysis','course-sarc-video')]
        self.assertEqual(len(clips),2)
        for clip in clips:
            steps=teaching_media.steps_for(clip)
            self.assertEqual(len(steps),13);self.assertEqual(steps[0]['start'],0)
            self.assertAlmostEqual(steps[-1]['end'],clip['duration'],places=4)
            for a,b in zip(steps,steps[1:]):self.assertEqual(a['end'],b['start'])
            for s in steps:
                self.assertEqual(teaching_media.step_at(clip,s['start'])['id'],s['id'])
                self.assertTrue(s['purpose'] and s['explanation'] and s['pitfall'] and s['sources'])
            changed={**clip,'source_sha256':'0'*64}
            self.assertEqual(teaching_media.steps_for(changed),[])
        with self.assertRaises(ValueError):teaching_media.path_for({'storage':'teaching_library','file':'../outside.mp4'})

    def test_plain_video_job_canonicalizes_projection_and_saves_step_evidence(self):
        sid,_=self.setup_note();temp=Path(self.tmp.name);f=temp/'film.mp4';f.write_bytes(b'fixture')
        clip={'id':'plain','title':'Plain','file':'film.mp4','projection':'flat','duration':600,'fps':24,'proxy_sha256':'a'*64}
        step={'id':'sitstand','title':'動作執行','purpose':'觀察坐站轉位'}
        result={'version':pose_analysis.VERSION,'source':{'id':'plain','projection':'flat'},'view':{'yaw':0,'pitch':0,'fov':70,'projection':'flat'},'frames':[{'frame':7200,'seconds':300,'poses':[],'teaching_step_id':'sitstand'}],'frame_count':1,'detection_frames':0,'model':'fixture','model_sha256':'b'*64,'teaching_steps':[step],'limitation':'fixture'}
        def analyze(c,params,directory,on_progress):
            self.assertEqual(c['projection'],'flat');self.assertEqual(params['yaw'],0);self.assertEqual(params['pitch'],0)
            directory.mkdir(parents=True);(directory/'result.json').write_text(json.dumps(result),encoding='utf-8');(directory/'raw-frame-7200.jpg').write_bytes(b'raw');return result
        with patch.object(learning_resources,'manifest',return_value={'clips':[clip]}),patch.object(teaching_media,'path_for',return_value=f),patch.object(pose_analysis,'availability',return_value={'ready':True}),patch.object(pose_analysis,'analyze',side_effect=analyze),patch.object(learning_resources,'RUNTIME',temp):
            bad=self.client.post(f'/api/sessions/{sid}/pose-analysis',json={'clip_id':'plain','start':0,'end':600,'roi':[.8,0,.5,1]})
            self.assertEqual(bad.status_code,400)
            r=self.client.post(f'/api/sessions/{sid}/pose-analysis',json={'clip_id':'plain','start':0,'end':600,'yaw':45,'pitch':20})
            self.assertEqual(r.status_code,200,r.text);job=r.json()['id']
            for _ in range(100):
                status=self.client.get(f'/api/sessions/{sid}/pose-analysis/{job}').json()
                if status['status']!='running':break
                time.sleep(.02)
            self.assertEqual(status['status'],'completed',status)
            n=self.client.post(f'/api/sessions/{sid}/frame-notes',json={'clip_id':'plain','seconds':300,'observation':'核對坐站動作及上肢是否有支撐，不能只從膝角判定。','analysis_id':job,'analysis_frame':7200})
            self.assertEqual(n.status_code,200,n.text);self.assertEqual(n.json()['analysis_snapshot']['teaching_step']['id'],'sitstand')
            self.assertEqual(self.faculty.get(f'/api/sessions/{sid}/pose-analysis/{job}/frames/7200?overlay=false').content,b'raw')
