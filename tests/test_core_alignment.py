import copy,json,unittest
from pathlib import Path
from unittest.mock import patch
from backend import competencies,core_alignment,learning_resources,team_knowledge
import test_cumulative_lessons as fixtures

class CoreAlignmentTests(unittest.TestCase):
    def test_all_twelve_profiles_preserve_supplied_axis_names_and_order(self):
        expected={'MD':6,'RN':6,'DT':6,'PT':6,'RT':5,'RPH':6,'MLS':6,'RSP':7,'AUD':6,'OT':5,'ST':6,'CP':6}
        for profession,count in expected.items():
            p=competencies.profile(profession)
            self.assertEqual(len(p['indicators']),count)
            self.assertEqual([i['name'] for i in p['indicators']],core_alignment.CATALOG['professions'][profession]['axes'])
        self.assertEqual([i['name'] for i in competencies.profile('DT')['indicators']],['營養專業知識','人際關係及溝通技巧','營養照護能力','專業素養','從工作中學習及成長','管理策略與資源運用'])

    def test_legacy_crosswalk_never_invents_missing_scores_or_mutates_original(self):
        original={'competency_profile':{'version':'profession-indicators-20261022-v5'},'competency_scores':{f'DT-{i:02}':i*10 for i in range(1,7)},'summary':{'self_mean':35}}
        before=copy.deepcopy(original);r=competencies.aligned_result(original,'DT')
        self.assertEqual(original,before)
        self.assertEqual(r['summary'],before['summary'])
        self.assertEqual(r['competency_scores']['DT-C03'],25)
        self.assertIsNone(r['competency_scores']['DT-C05'])
        self.assertIsNone(r['competency_scores']['DT-C06'])
        self.assertEqual(r['competency_results'][1]['source_indicators'],['DT-05'])
        self.assertEqual(r['competency_alignment']['kind'],'legacy-crosswalk')
        self.assertEqual(competencies.aligned_result(r,'DT'),r)

    def test_high_self_level_alone_cannot_unlock_team_content(self):
        case={'id':'COURSE-SARC','symptom':'肌少症'}
        locked=team_knowledge.for_case(case,'DT',1,1)
        self.assertFalse(locked['unlocked']);self.assertNotIn('roles',locked);self.assertNotIn('image_url',locked)
        open_=team_knowledge.for_case(case,'DT',2,1)
        self.assertEqual([r['profession'] for r in open_['roles']],['MD','RN','RT','DT','PT'])
        self.assertTrue(all(len(r['knowledge'])==5 and r['core_task'] and r['provide'] and r['request'] for r in open_['roles']))
        self.assertEqual([r['profession'] for r in open_['roles'] if r['is_own']],['DT'])
        self.assertIsNone(team_knowledge.for_case({'id':'COURSE-DM','symptom':'糖尿病'},'DT',5,1))

class TeamResourceTests(unittest.TestCase):
    setUp=fixtures.CumulativeLessonTests.setUp
    tearDown=fixtures.CumulativeLessonTests.tearDown
    start=fixtures.CumulativeLessonTests.start
    setup_note=fixtures.CumulativeLessonTests.setup_note
    set_level=fixtures.CumulativeLessonTests.set_level

    def test_team_image_is_authenticated_and_cumulative_level_gated(self):
        sid,_=self.setup_note();url=f'/api/sessions/{sid}/resources/team-guide'
        root=Path(self.tmp.name);(root/'data/sources').mkdir(parents=True,exist_ok=True)
        (root/'data/sources/跨專業肌少症整合照護指南.png').write_bytes(b'PNG training fixture')
        with patch.object(learning_resources,'ROOT',root):
            self.set_level(sid,1)
            self.assertEqual(self.client.get(url).status_code,403)
            r=self.client.get(f'/api/sessions/{sid}/learning').json()['resources']['team_knowledge']
            self.assertNotIn('roles',r)
            self.set_level(sid,2)
            self.assertEqual(self.client.get(url).status_code,200)
            r=self.client.get(f'/api/sessions/{sid}/learning').json()['resources']['team_knowledge']
            self.assertEqual(len(r['roles']),5)
            self.assertEqual(self.faculty.get(url).status_code,200)

    def test_report_alignment_does_not_rewrite_saved_assessment(self):
        sid,_=self.setup_note();before=self.db.all('SELECT id,scores,snapshot FROM attempts')
        r=self.client.get(f'/api/sessions/{sid}').json()
        self.assertEqual(r['report_competencies']['competency_profile']['version'],core_alignment.VERSION)
        self.assertEqual(self.db.all('SELECT id,scores,snapshot FROM attempts'),before)
