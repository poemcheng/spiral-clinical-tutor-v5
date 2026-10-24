import json,unittest
from types import SimpleNamespace
from unittest.mock import patch
import test_uploaded_workflow as fixtures
from backend import server,standardized_patient as sp

class StandardizedPatientTests(unittest.TestCase):
    setUp=fixtures.UploadedWorkflowTests.setUp
    tearDown=fixtures.UploadedWorkflowTests.tearDown
    start=fixtures.UploadedWorkflowTests.start
    interaction=fixtures.UploadedWorkflowTests.interaction

    def test_all_authored_hidden_clauses_have_topics_and_speech_transcripts_unlock_them(self):
        for case in server.registry.cases:
            for fact in sp.hidden_facts(case):self.assertTrue(fact['topics'],(case['id'],fact['text']))
        case=server.registry.case('COURSE-PREG')
        _,audit=sp.disclosure_view(case,{},[],'請問今天胎動怎麼樣')
        self.assertEqual(len(audit['eligible_fact_ids']),1)
        view,_=sp.disclosure_view(server.registry.case('COURSE-SARC'),{},[],'您平常做哪些運動')
        self.assertIn('快走',view['patient_script']);self.assertNotIn('珍奶',sp.normalized(view['patient_script']))

    def test_direct_questions_gate_hidden_facts_across_followup_turns(self):
        case=server.registry.case('COURSE-SARC')
        initial,audit=sp.disclosure_view(case,{},[],'您好，您今天想談什麼？')
        serialized=sp.normalized(initial['patient']+initial['patient_script'])
        for fact in ['珍奶','快走','伸展']:self.assertNotIn(fact,serialized)
        diet,audit=sp.disclosure_view(case,{},[],'請問您下午通常喝什麼飲料？')
        self.assertIn('珍奶',sp.normalized(diet['patient_script']));self.assertNotIn('快走',diet['patient_script'])
        followup,_=sp.disclosure_view(case,{},[{'role':'user','content':'您平常做哪些運動？'}],'那還有什麼要補充？')
        self.assertIn('快走',followup['patient_script']);self.assertNotIn('珍奶',sp.normalized(followup['patient_script']))
        self.assertTrue(audit['eligibility_is_not_observed_disclosure'])

    def test_prompt_and_retrieval_do_not_receive_unasked_hidden_information(self):
        sid,_=self.interaction('PT')
        with patch.object(server.llm,'check',return_value=SimpleNamespace(ready=True)),patch.object(server.llm,'chat',return_value=SimpleNamespace(ok=True,text='最近容易累，想了解可以怎麼安排。',model='fixture')) as model:
            response=self.client.post(f'/api/sessions/{sid}/chat',json={'text':'您好，您今天想談什麼？','mode':'ai','request_id':'gated-first-question'})
        self.assertTrue(response.json()['ok'],response.text)
        prompt=model.call_args.args[0][0]['content']
        self.assertNotIn('下午常喝珍奶',sp.normalized(prompt));self.assertNotIn('運動只有快走與伸展',prompt)
        self.assertTrue(response.json()['metadata']['disclosure']['guard_passed'])

    def test_repeated_hidden_leak_is_rejected_instead_of_saved_as_a_patient_fact(self):
        sid,_=self.interaction('PT')
        def leaking(*args,**kwargs):return SimpleNamespace(ok=True,text='我下午常喝珍奶。',model='fixture')
        with patch.object(server.llm,'check',return_value=SimpleNamespace(ready=True)),patch.object(server.llm,'chat',side_effect=leaking):
            response=self.client.post(f'/api/sessions/{sid}/chat',json={'text':'您好，今天想先談什麼？','mode':'ai','request_id':'blocked-disclosure-test'})
        self.assertFalse(response.json()['ok']);self.assertEqual(self.db.one("SELECT COUNT(*) n FROM messages WHERE session_id=? AND role='assistant'",(sid,))['n'],0)

    def test_record_lookup_uses_source_only_and_is_not_an_examination_or_score(self):
        record=sp.lookup({'patient':'個案資料待補。','source_file':'fixture'},'imaging')
        self.assertFalse(record['provided']);self.assertIn('不能視為檢查正常',record['message'])
        sid,_=self.interaction('RT');info=self.client.get(f'/api/sessions/{sid}/patient-records').json()
        body={'section_id':'imaging','event_id':'record-test-event','case_hash':info['case_hash']}
        result=self.client.post(f'/api/sessions/{sid}/patient-records',json=body)
        self.assertEqual(result.status_code,200,result.text);self.assertNotIn('判讀重點',''.join(result.json()['excerpts']))
        self.assertEqual(self.client.post(f'/api/sessions/{sid}/patient-records',json=body).status_code,200)
        self.assertEqual(self.db.one("SELECT COUNT(*) n FROM events WHERE session_id=? AND kind='case_record_viewed'",(sid,))['n'],1)
        payload=json.loads(self.db.one('SELECT data FROM sessions WHERE id=?',(sid,))['data']);self.assertEqual(payload['decisions'],{})
        self.assertEqual(self.faculty.post(f'/api/sessions/{sid}/patient-records',json=body).status_code,403)
