import json,uuid,unittest
from fastapi.testclient import TestClient
import test_uploaded_workflow as fixtures
from backend import server,branching,curriculum

class BranchingTests(unittest.TestCase):
    setUp=fixtures.UploadedWorkflowTests.setUp
    tearDown=fixtures.UploadedWorkflowTests.tearDown
    start=fixtures.UploadedWorkflowTests.start
    interaction=fixtures.UploadedWorkflowTests.interaction

    def setup_branch(self):
        sid,_=self.interaction('DT')
        payload=json.loads(self.db.one('SELECT data FROM sessions WHERE id=?',(sid,))['data'])
        row={'id':sid,'profession':'DT','level':1,'payload':payload}
        return sid,row,*branching.content(row)

    def post(self,sid,version,path,run=None,event=None):
        body={'run_id':run or uuid.uuid4().hex,'event_id':event or uuid.uuid4().hex,'content_version':version,'verb':'navigated',
              'state':{'userPath':path,'scoring':{'score':9999},'endScreen':{'endScreenTitle':'forged'}}}
        return self.client.post(f'/api/sessions/{sid}/branching/evidence',json=body),body

    def test_native_manifest_source_graph_and_legal_retry(self):
        sid,row,params,version,mapping=self.setup_branch();nodes=params['branchingScenario']['content']
        self.assertEqual(self.client.get(f'/api/sessions/{sid}/branching/h5p.json').json()['mainLibrary'],'H5P.BranchingScenario')
        self.assertEqual(params['branchingScenario']['scoringOptionGroup']['scoringOption'],'no-score')
        question=nodes[1];alternatives=question['type']['params']['branchingQuestion']['alternatives']
        wrong=next(a['nextContentId'] for a in alternatives if mapping[a['nextContentId']]['retry'])
        correct=next(a['nextContentId'] for a in alternatives if mapping[a['nextContentId']]['meets_rubric'])
        path=[0,1,wrong,1,correct,nodes[correct]['nextContentId']]
        response,body=self.post(sid,version,path);self.assertEqual(response.status_code,200,response.text)
        self.assertFalse(response.json()['formal_score_changed']);self.assertEqual(response.json()['summary']['remediation_count'],1)
        again=self.client.post(f'/api/sessions/{sid}/branching/evidence',json=body);self.assertTrue(again.json()['duplicate'])
        state=self.client.get(f'/api/sessions/{sid}/branching/state').json()
        self.assertEqual(state['state']['userPath'],path);self.assertNotIn('score',state['state']['scoring'])
        payload=json.loads(self.db.one('SELECT data FROM sessions WHERE id=?',(sid,))['data']);self.assertEqual(payload['decisions'],{})
        self.assertEqual(self.post(sid,version,[0],run=body['run_id'])[0].status_code,409)
        decision=self.client.post(f'/api/sessions/{sid}/decision',json={'item_id':mapping[correct]['question_id'],'option_id':f"o{mapping[correct]['option_index']}"}).json()
        self.assertTrue(decision['prior_branching_practice']['feedback_path_reported'])
        self.assertFalse(decision['prior_branching_practice']['independent_first_attempt'])

    def test_illegal_shortcuts_and_stale_actor_are_rejected(self):
        sid,row,params,version,mapping=self.setup_branch()
        self.assertEqual(self.post(sid,version,[0,-1])[0].status_code,400)
        self.assertEqual(self.post(sid,version,[True])[0].status_code,400)
        self.assertEqual(self.post(sid,version,[0,9999])[0].status_code,400)
        self.client.post(f'/api/sessions/{sid}/actors',json={'purpose':'interaction','actor_id':'auntie-lin'})
        # DT must talk to PT; a disallowed casting request cannot alter this graph.
        self.assertEqual(self.post(sid,'f'*64,[0])[0].status_code,409)
        self.assertEqual(self.faculty.post(f'/api/sessions/{sid}/branching/evidence',json={'run_id':uuid.uuid4().hex,'event_id':uuid.uuid4().hex,'content_version':version,'verb':'started','state':{}}).status_code,403)
        with TestClient(server.app) as anonymous:self.assertEqual(anonymous.get(f'/api/sessions/{sid}/branching/state').status_code,401)

    def test_safety_ending_teacher_feedback_and_student_readback_are_ungraded(self):
        sid,row,params,version,mapping=self.setup_branch();nodes=params['branchingScenario']['content'];path=[0];current=0
        while True:
            node=nodes[current];question=node['type']['params'].get('branchingQuestion')
            if question:
                critical=next((a for a in question['alternatives'] if mapping[a['nextContentId']]['critical_error']),None)
                current=(critical or next(a for a in question['alternatives'] if mapping[a['nextContentId']]['meets_rubric']))['nextContentId']
            else:current=node['nextContentId']
            path.append(current)
            if current==-1:break
        response,body=self.post(sid,version,path);self.assertEqual(response.status_code,200,response.text)
        self.assertEqual(response.json()['summary']['outcome'],'safety-remediation')
        feedback={'run_id':body['run_id'],'feedback':'請回到來源證據說明安全風險，下一輪先核對資料與保護措施。'}
        reviewed=self.faculty.post(f'/api/teacher/sessions/{sid}/branching/review',json=feedback)
        self.assertEqual(reviewed.status_code,200,reviewed.text)
        self.assertEqual(self.faculty.post(f'/api/teacher/sessions/{sid}/branching/review',json=feedback).status_code,409)
        state=self.client.get(f'/api/sessions/{sid}/branching/state').json();self.assertEqual(state['reviews'][0]['feedback'],feedback['feedback'])
        self.assertEqual(self.client.post(f'/api/teacher/sessions/{sid}/branching/review',json=feedback).status_code,403)
        payload=json.loads(self.db.one('SELECT data FROM sessions WHERE id=?',(sid,))['data'])
        self.assertFalse(payload.get('safety_blocked',False));self.assertEqual(payload['decisions'],{})
        self.assertEqual(self.db.one('SELECT COUNT(*) n FROM reviews WHERE session_id=?',(sid,))['n'],0)
        # A new run retains the completed safety attempt and its teacher comments.
        self.assertEqual(self.post(sid,version,[0])[0].status_code,200)
        self.assertEqual(len(json.loads(self.db.one('SELECT data FROM sessions WHERE id=?',(sid,))['data'])['branching_runs']),2)

    def test_all_existing_course_role_levels_have_a_reachable_completion(self):
        for course in curriculum.COURSES.values():
            for profession in course['professions']:
                for level in range(1,6):
                    case=curriculum.adapt_case(server.registry.case(course['id']),profession,level,{})
                    row={'profession':profession,'level':level,'payload':{'case_snapshot':case,'case_hash':'a'*64}}
                    params,version,mapping=branching.content(row);nodes=params['branchingScenario']['content'];path=[0];current=0
                    self.assertTrue(all('feedback' in n for n in nodes if n['type']['library'].startswith('H5P.AdvancedText')))
                    for _ in range(50):
                        node=nodes[current];question=node['type']['params'].get('branchingQuestion')
                        current=next(a['nextContentId'] for a in question['alternatives'] if mapping[a['nextContentId']]['meets_rubric']) if question else node['nextContentId']
                        path.append(current)
                        if current==-1:break
                    self.assertEqual(path[-1],-1,(course['id'],profession,level));branching.validate_state(params,{'userPath':path})
