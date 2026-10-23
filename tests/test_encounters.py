import json
import unittest
from types import SimpleNamespace
from unittest.mock import patch
from backend import server,encounters,characters,training_evidence
import test_uploaded_workflow as fixtures

class EncounterTests(unittest.TestCase):
    setUp=fixtures.UploadedWorkflowTests.setUp
    tearDown=fixtures.UploadedWorkflowTests.tearDown
    start=fixtures.UploadedWorkflowTests.start
    interaction=fixtures.UploadedWorkflowTests.interaction

    def test_assignments_persist_and_roles_match_profession_and_case(self):
        for prof,expected in characters.PAIRINGS.items():
            sid,_=self.interaction(prof)
            before=self.client.get(f'/api/sessions/{sid}/interaction').json()
            after=self.client.get(f'/api/sessions/{sid}/interaction').json()
            plan=before['encounter_plan']
            self.assertEqual(plan,after['encounter_plan'])
            self.assertEqual({x['target'] for x in plan['entries']},set(expected))
            self.assertEqual(plan['case_id'],'COURSE-SARC')
            self.assertEqual(plan['self_level'],1)
            self.assertTrue(all(x['task'] and x['id'] for x in plan['entries']))
        row={'profession':'RN','level':5,'payload':{}}
        case={'id':'synthetic','variant':{'role_task':'test'}}
        a=encounters.assign(row,case,chooser=lambda seq:seq[0])
        b=encounters.assign(row,case,chooser=lambda seq:seq[-1])
        self.assertEqual([x['target'] for x in a['entries']],['patient','PT'])
        self.assertEqual([x['target'] for x in b['entries']],['PT','patient'])
        self.assertNotEqual(a['entries'][0]['title'],b['entries'][-1]['title'])

    def test_model_can_offer_closure_but_not_force_it_and_user_can_continue(self):
        reply=json.dumps({'text':'還有需要確認的嗎？','phase':'closed','emotion':'friendly'})
        self.assertEqual(encounters.decode_reply(reply,1,'active','你好')[1]['phase'],'active')
        self.assertEqual(encounters.decode_reply(reply,4,'active','謝謝說明')[1]['phase'],'closing')
        self.assertEqual(encounters.decode_reply(reply,5,'closing','還有一個問題，不要結束')[1]['phase'],'closing')
        self.assertEqual(encounters.decode_reply(reply,6,'closing','沒有問題了，再見')[1]['phase'],'closed')
        self.assertEqual(encounters.decode_reply(reply,6,'closing','好的，謝謝您')[1]['phase'],'closed')
        with self.assertRaises(ValueError):encounters.decode_reply('{"text":17}',3,'active','測試')

    def test_real_chat_lifecycle_is_saved_reopenable_and_duplicate_safe(self):
        sid,_=self.interaction('PT')
        def answer(case,row,messages,text):
            turn=sum(m['role']=='user' for m in messages)
            state={'phase':'closed' if turn==4 else 'closing' if turn==3 else 'active','turns':turn,'emotion':'friendly','version':encounters.VERSION}
            return SimpleNamespace(ok=True,text='這是合成測試回覆，不是臨床評量。',model='synthetic'),{'conversation_state':state}
        with patch.object(server.llm,'check',return_value=SimpleNamespace(ready=True)),patch.object(server,'patient_reply',side_effect=answer):
            for turn in range(1,5):
                body={'text':'合成對話測試','mode':'ai','request_id':f'controlled-turn-{turn}'}
                r=self.client.post(f'/api/sessions/{sid}/chat',json=body)
                self.assertEqual(r.status_code,200,r.text)
            self.assertEqual(r.json()['conversation']['phase'],'closed')
            repeat=self.client.post(f'/api/sessions/{sid}/chat',json=body)
            self.assertTrue(repeat.json()['duplicate'])
            self.assertEqual(self.db.one('SELECT COUNT(*) n FROM messages WHERE session_id=?',(sid,))['n'],8)
            self.assertEqual(self.client.post(f'/api/sessions/{sid}/chat',json={**body,'request_id':'closed-new-turn'}).status_code,409)
            self.assertEqual(self.client.post(f'/api/sessions/{sid}/conversation/reopen').status_code,200)
            self.assertEqual(self.client.post(f'/api/sessions/{sid}/chat',json={**body,'request_id':'reopened-turn'}).status_code,200)
        self.assertEqual(self.faculty.post(f'/api/sessions/{sid}/conversation/reopen').status_code,403)
        teacher=self.faculty.get(f'/api/teacher/sessions/{sid}').json()
        self.assertTrue(teacher['data']['encounter_plan'])
        self.assertEqual(teacher['data']['case_hash'],teacher['data']['encounter_plan']['case_hash'])

    def test_audit_all_uploaded_items_without_claiming_official_exam(self):
        a=training_evidence.audit()
        self.assertEqual(a['item_count'],1250)
        self.assertEqual(a['review_counts'],{'待審':1250})
        self.assertFalse(a['official_exam_verified'])
        self.assertEqual({r['profession'] for r in a['references']},{'RT','PT','RN','MD','DT'})
        self.assertEqual(self.client.get('/api/training-evidence').json()['item_count'],1250)

    def test_family_role_and_voice_gender_follow_selected_case(self):
        for case_id,title in [('COURSE-STROKE','病患太太'),('COURSE-DEM','病患女兒'),('COURSE-PEDXR','陪同嬰兒的阿嬤')]:
            row={'profession':'MD','payload':{'case_snapshot':{'id':case_id},'interaction_policy':characters.pairing('MD')}}
            a=characters.selected(row)
            self.assertEqual(a['kind'],'caregiver');self.assertEqual(a['gender'],'female');self.assertEqual(a['title'],title)
        self.assertEqual(characters.default_actor({'profession':'MD','payload':{'case_snapshot':{'id':'COURSE-ASTHMA'}}}),'middle-man')

    def test_patient_reply_receives_profession_task_history_and_no_fake_clinical_facts(self):
        from backend.services import patient_reply
        sid,_=self.interaction('RT',level=5)
        raw=self.db.one('SELECT * FROM sessions WHERE id=?',(sid,));row={**raw,'payload':json.loads(raw['data'])}
        case=server.case_for(row)
        messages=[{'role':'user','content':'我是放射師，先前提到兩次報告需要核對。'}]
        with patch('backend.services.llm.chat',return_value=SimpleNamespace(ok=True,text='{"text":"請先說明檢查條件有哪些已確認？","phase":"closed","emotion":"reserved"}',model='synthetic')) as mocked:
            result,facts=patient_reply(case,row,messages,messages[0]['content'])
        prompt=mocked.call_args.args[0]
        self.assertEqual(prompt[-1]['content'],messages[0]['content'])
        self.assertIn(encounters.current(row)['task'],prompt[0]['content']);self.assertIn('dialogue_partner',prompt[0]['content'])
        self.assertEqual(facts['conversation_state']['phase'],'active')
        self.assertNotIn('{',result.text)
        self.assertTrue(mocked.call_args.kwargs['json_mode'])
