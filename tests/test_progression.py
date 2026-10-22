"""New placement and unlock policy tested through real API/state transitions."""
import json
import unittest
from backend import progression
import test_workflow


class ProgressionTests(unittest.TestCase):
    setUp=test_workflow.WorkflowTests.setUp
    tearDown=test_workflow.WorkflowTests.tearDown
    enter=test_workflow.WorkflowTests.enter
    submit=test_workflow.WorkflowTests.submit
    complete=test_workflow.WorkflowTests.complete

    def test_all_score_bands_persistence_and_profession_isolation(self):
        for prof,rating in zip(['DT','PT','MD','RN','RT'],range(1,6)):
            e=self.enter(prof=prof);sid,body=self.submit(e,rating=rating)
            first=self.alice.post(f"/api/assessments/{e['attempt_id']}/submit",json=body).json()
            p=first['scores']['level_result']
            self.assertEqual((p['self_score'],p['self_level'],p['learning_level']),(rating*20,rating,1))
            self.assertEqual(self.alice.get(f'/api/sessions/{sid}').json()['level'],rating)
            stored=json.loads(self.db.one('SELECT scores FROM attempts WHERE id=?',(e['attempt_id'],))['scores'])
            self.assertEqual(stored,first['scores'])
            self.assertEqual(self.db.one('SELECT approved_level FROM progress WHERE profession=?',(prof,))['approved_level'],1)
        for score,level in [(0,1),(39.9,1),(40,2),(59.9,2),(60,3),(74.9,3),(75,4),(89.9,4),(90,5),(100,5)]:
            self.assertEqual(progression.score_level(score),level)

    def test_actual_practice_promotes_and_unlocks_without_double_counting(self):
        uid=self.db.one("SELECT id FROM users WHERE username='alice'")['id']
        for number in range(1,5):
            sid,_=self.submit(self.enter(new=number>1))
            plan=self.alice.get(f'/api/sessions/{sid}').json()['data']['adaptive_plan']
            self.assertEqual(plan['video_count'],1 if number==1 else 2 if number<=3 else 3)
            answers=self.complete(sid)
            done=self.alice.get(f'/api/sessions/{sid}').json()['data']['result']['learning_progress']
            self.assertEqual(done['learning_level'],1+number//2)
            self.assertEqual(done['completed_practices'],number)
            self.assertEqual(done['learning_points'],100*number)
            self.assertEqual(done['mastery'],100)
            self.assertEqual(self.alice.post(f'/api/sessions/{sid}/finish',json={'answers':answers}).json()['learning_progress'],done)
            self.assertEqual(progression.evidence(self.db,uid,'DT','肌少症')['completed_practices'],number)
        self.assertEqual(self.db.one('SELECT approved_level FROM progress')['approved_level'],1)
        self.assertEqual(self.enter()['learning_level'],3)

    def test_locked_paths_and_videos_rejected_by_backend(self):
        sid,_=self.submit(self.enter())
        paths=self.alice.get(f'/api/sessions/{sid}/cases').json()[0]['paths']
        self.assertEqual([p['id'] for p in paths if p['unlocked']],['core'])
        self.assertEqual(self.alice.post(f'/api/sessions/{sid}/case',json={'case_id':'COURSE-SARC','path_id':'team'}).status_code,403)
        self.assertEqual(self.alice.post(f'/api/sessions/{sid}/case',json={'case_id':'COURSE-SARC','path_id':'communication'}).status_code,403)
        self.assertEqual(self.alice.post(f'/api/sessions/{sid}/case',json={'case_id':'COURSE-SARC'}).status_code,200)
        self.assertEqual(self.alice.post(f'/api/sessions/{sid}/video',json={'module':2}).status_code,403)

    def test_unlocked_lesson_path_preserves_case_facts(self):
        from backend import server
        sid,_=self.submit(self.enter());self.complete(sid)
        sid2,_=self.submit(self.enter(new=True))
        r=self.alice.post(f'/api/sessions/{sid2}/case',json={'case_id':'COURSE-SARC','path_id':'communication'})
        self.assertEqual(r.status_code,200,r.text)
        case=self.alice.get(f'/api/sessions/{sid2}').json()['data']['case']
        self.assertEqual(case['patient'],server.registry.case('COURSE-SARC')['patient'])
        self.assertEqual(case['lesson_path']['id'],'communication')
        self.assertTrue(any('同理' in g for g in case['goals']))

    def test_high_learning_level_does_not_force_high_formal_teacher_level(self):
        sid,_=self.submit(self.enter(),rating=4);self.complete(sid)
        detail=self.prof.get(f'/api/teacher/sessions/{sid}').json()
        self.assertEqual((detail['level'],detail['approved_level']),(4,1))
        body={'decision':'approve','score':90,'level':5,'safety_pass':True,'note':'測試：依原始證據逐級核定正式等級。','expected_review_id':0}
        self.assertEqual(self.prof.post(f'/api/teacher/sessions/{sid}/review',json=body).status_code,400)
        body['level']=2
        r=self.prof.post(f'/api/teacher/sessions/{sid}/review',json=body)
        self.assertEqual(r.status_code,200)
        body.update(expected_review_id=r.json()['review_id'],safety_pass=False)
        self.assertEqual(self.prof.post(f'/api/teacher/sessions/{sid}/review',json=body).status_code,200)
        uid=self.db.one("SELECT id FROM users WHERE username='alice'")['id']
        self.assertFalse(progression.evidence(self.db,uid,'DT','肌少症')['recent_evidence'][-1]['safe'])
        self.assertEqual(progression.plan(self.db,uid,'DT','肌少症',4)['video_count'],1)

    def test_mastery_and_count_are_both_required_and_safety_blocks_promotion(self):
        sid,_=self.submit(self.enter());self.complete(sid)
        uid=self.db.one("SELECT id FROM users WHERE username='alice'")['id']
        self.assertFalse(progression.plan(self.db,uid,'DT','肌少症',1)['paths'][2]['unlocked'])
        # Below-threshold reviewed performance overrides the automated score.
        with self.db.tx() as c:
            teacher=self.db.one("SELECT id FROM users WHERE username='prof'")['id']
            c.execute('INSERT INTO reviews(session_id,teacher_id,decision,score,level,note,created) VALUES (?,?,?,?,?,?,?)',(sid,teacher,'approve',40,1,'低熟練度測試證據',1))
        self.assertEqual(progression.plan(self.db,uid,'DT','肌少症',1)['video_count'],1)
        sid2,_=self.submit(self.enter(new=True));self.complete(sid2)
        with self.db.tx() as c:
            row=self.db.one('SELECT data FROM sessions WHERE id=?',(sid2,));data=json.loads(row['data']);data['safety_blocked']=True
            self.db.save(c,sid2,data)
            p=progression.advance(self.db,c,uid,'DT','肌少症')
        self.assertFalse(p['promoted'])

    def test_reassessment_does_not_change_active_case_or_erase_learning(self):
        sid,_=self.submit(self.enter(),rating=2)
        self.alice.post(f'/api/sessions/{sid}/case',json={'case_id':'COURSE-SARC'})
        original=self.db.one('SELECT data FROM sessions WHERE id=?',(sid,))['data']
        self.alice.post('/api/auth/logout');self.alice.post('/api/auth/login',json={'username':'alice','password':'Synthetic-test-pass!2026'})
        e=self.enter();_,body=self.submit(e,rating=4)
        result=self.alice.post(f"/api/assessments/{e['attempt_id']}/submit",json=body).json()['scores']['level_result']
        self.assertTrue(result['applies_next_round']);self.assertEqual(result['self_level'],4)
        self.assertEqual(result['learning_level'],1)
        self.assertEqual(self.db.one('SELECT data FROM sessions WHERE id=?',(sid,))['data'],original)
        self.assertEqual(self.alice.get(f'/api/sessions/{sid}').json()['level'],2)

    def test_reviewed_teaching_adapters_and_safe_options(self):
        from backend import server,curriculum
        for course in curriculum.COURSES.values():
            case=server.registry.case(course['id'])
            self.assertTrue(any(q['critical'] for q in case['kdp']))
            for d in case['kdp']:
                self.assertTrue(all(o['text'].strip() for o in d['options']))
                quiz=next(q for q in case['quiz'] if q['id']==d['id']+'-Q')
                self.assertIn(quiz['answer'],quiz['options'])
                self.assertEqual(quiz['answer'],max(d['options'],key=lambda o:o['score'])['text'])
        icu=server.registry.case('COURSE-ICU')
        corrected=next(q for q in icu['kdp'] if '胃殘留' in q['phase'])
        self.assertIn('6小時',corrected['options'][0]['text'])
        self.assertIn('6小時',corrected['hint'])

    def test_self_level_two_and_earned_level_five_are_independent(self):
        for number in range(8):
            sid,_=self.submit(self.enter(new=number>0),rating=2)
            self.complete(sid)
        e=self.enter(new=True)
        self.assertEqual((e['assessment_level'],e['learning_level']),(2,5))
        self.assertTrue(all(q['level']==2 for q in e['snapshot']['items']))
        sid,body=self.submit(e,rating=2)
        p=self.alice.post(f"/api/assessments/{e['attempt_id']}/submit",json=body).json()['scores']['level_result']
        self.assertEqual((p['self_level'],p['learning_level']),(2,5))
        self.assertFalse(p['applies_next_round'])
        self.alice.post(f'/api/sessions/{sid}/case',json={'case_id':'COURSE-SARC'})
        learning=self.alice.get(f'/api/sessions/{sid}/learning').json()
        self.assertEqual(learning['variant']['level'],2)
        self.assertEqual(learning['plan']['learning_level'],5)
        self.assertEqual(learning['plan']['video_count'],3)
        self.assertEqual(len([i for i in learning['information'] if i['unlocked'] and i.get('content')]),5)
        next_user=self.enter(prof='RN')
        self.assertEqual((next_user['assessment_level'],next_user['learning_level']),(1,1))

    def test_high_self_and_teacher_level_do_not_unlock_unearned_information(self):
        from backend import server
        sid,_=self.submit(self.enter(),rating=4)
        self.alice.post(f'/api/sessions/{sid}/case',json={'case_id':'COURSE-SARC'})
        learning=self.alice.get(f'/api/sessions/{sid}/learning').json()
        self.assertEqual(learning['variant']['level'],4)
        self.assertEqual(learning['plan']['learning_level'],1)
        self.assertTrue(all('content' not in i for i in learning['information'] if not i['unlocked']))
        uid=self.db.one("SELECT id FROM users WHERE username='alice'")['id']
        with self.db.tx() as c:c.execute('UPDATE progress SET approved_level=5 WHERE user_id=?',(uid,))
        self.assertEqual(progression.level_state(self.db,uid,'DT','肌少症'),1)
        self.assertEqual(progression.assessment_level(self.db,uid,'DT','肌少症'),4)

    def test_legacy_coupled_aggregate_rebuilt_without_rewriting_evidence(self):
        sid,_=self.submit(self.enter());self.complete(sid)
        original=self.db.one('SELECT data FROM sessions WHERE id=?',(sid,))['data']
        uid=self.db.one("SELECT id FROM users WHERE username='alice'")['id']
        with self.db.tx() as c:
            c.execute('UPDATE learning_progress SET level=5,data=? WHERE user_id=?',(json.dumps({'latest_self_level':5,'policy_version':'learning-level-20261022-1'}),uid))
        progression.migrate_legacy(self.db)
        state=self.db.one('SELECT * FROM learning_progress WHERE user_id=?',(uid,))
        self.assertEqual(state['level'],1)
        self.assertEqual(json.loads(state['data'])['level_before_separation'],5)
        self.assertEqual(self.db.one('SELECT data FROM sessions WHERE id=?',(sid,))['data'],original)
        events=self.db.one("SELECT COUNT(*) n FROM events WHERE kind='learning_levels_separated'")['n']
        progression.migrate_legacy(self.db)
        self.assertEqual(self.db.one("SELECT COUNT(*) n FROM events WHERE kind='learning_levels_separated'")['n'],events)


if __name__=='__main__':unittest.main()
