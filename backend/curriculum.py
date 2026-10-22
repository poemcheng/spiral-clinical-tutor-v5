"""Versioned adapters for the uploaded curriculum. Documents are data, never code."""
import copy
import json
from .clinical_review import REVIEW,apply_corrections
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CATALOG = json.loads((ROOT / 'data/course_catalog.json').read_text(encoding='utf-8'))
COURSES = {c['id']: c for c in CATALOG['courses']}


def install(registry):
    for course in COURSES.values():
        decisions = []
        for d in course['decisions']:
            dimension = 'SAFE' if d['critical'] else 'COM' if any(t in d['title'] for t in ['開場', '溝通', '家屬']) else 'CJ'
            decisions.append({'id': d['id'], 'phase': d['title'], 'prompt': d['title']+'，您會如何處理？',
                'critical': d['critical'], 'hint': d['correct'], 'options': [
                    {'text': d['correct'], 'score': 2, 'dimension': dimension, 'feedback': '符合教案建議：'+d['correct']},
                    {'text': d['incorrect'], 'score': 0, 'dimension': dimension, 'feedback': '需補強：'+d['correct']}]})
        case = {'id': course['id'], 'title': course['title'], 'symptom': course['topic'],
            'professions': course['professions'], 'summary': course['patient'], 'patient': course['patient'],
            'goals': [r['task'] for r in course['roles'].values()],
            'pre_knowledge': [course['goals_text'], '自評分流決定案例難度；累積學習獨立解鎖教材資訊；原教案信賴等級由教師另行核定。'],
            'rubric': [r['title']+'：'+r['standard'] for r in course['rubric']],
            'source_file': course['source_file'], 'source_pages': course['source_pages'],
            'source_sha256': course['source_sha256'], 'curriculum_version': CATALOG['version'],
            'review_status': course['review_status'], 'video_file': course['video_file'],
            'clinical_review':REVIEW if course['id']=='COURSE-SARC' else {'status':'來源、職種類別與分級結構已核對；臨床專家正式核定待完成','general':REVIEW['general']},
            'roles': course['roles'], 'levels': course['levels'], 'patient_script': course['patient_script'],
            'kdp': decisions, 'quiz': [{'id': d['id']+'-Q', 'question': d['title']+'：選擇較適切的處置',
                'options': [d['correct'], d['incorrect']], 'answer': d['correct'], 'explain': d['correct']} for d in course['decisions']]}
        case=apply_corrections(case)
        registry.case_map[case['id']] = case
        registry.cases.insert(0, case)


def public_courses(profession=None):
    return [{k: c[k] for k in ('id', 'topic', 'title', 'professions', 'source_pages', 'review_status', 'original_source_available')}
            | {'has_original_video': bool(c['video_file'])} for c in COURSES.values()
            if not profession or profession in c['professions']]


def available(registry, profession, topic):
    return bool(registry.cases_for(topic, profession))


def adapt_case(case, profession, level, scores):
    case = copy.deepcopy(case)
    if case.get('symptom')=='肌少症':case['clinical_review']=copy.deepcopy(REVIEW)
    if not case.get('levels') or not case.get('roles'):
        return case
    variant = dict(case['levels'][str(level)])
    from .interaction_policy import policy
    from .characters import PAIRINGS
    context='patient' if PAIRINGS.get(profession,['patient'])[0]=='patient' else 'clinician'
    difficulty=policy(level,context)
    variant['patient_behavior']=difficulty['behavior']
    variant['difficulty_version']=difficulty['version']
    if level==5:
        variant['learner_task']='在困難病患或強勢職場互動中，提出專業依據、處理質疑並協商可行方案；同儕指導為額外選修。'
        variant['support']='低提示支持；主動釐清疑慮、專業依據、角色分工與可行選擇。'
    task = case['roles'][profession]['task']
    dims = scores.get('self_dimensions', {})
    # Scores are on a 100-point scale. Differences of one Likert point = 20.
    mean = sum(dims.values())/len(dims) if dims else 0
    weak = sorted([d for d, value in dims.items() if value <= mean-20], key=lambda d: dims[d])[:2]
    supplements = {'CJ': '用現有資料說明判斷依據與資訊缺口。', 'PC': '提出本職類評估步驟；實際技能仍需教師觀察。',
        'COM': '先同理，再以回覆示教確認理解。', 'TC': '用 SBAR 提出具體協助需求並確認接收。',
        'SAFE': '遇到不安全選擇先停止、確認資訊再重作。', 'HC': '納入個人偏好、家庭支持與可行性。'}
    case['variant'] = {**variant, 'level': level, 'role_task': task, 'weak_dimensions': weak,
        'supplement_tasks': [supplements[d] for d in weak], 'policy': '自評分流決定案例難度；累積使用與正確性解鎖教材資訊，兩者獨立；教師正式核定另存。'}
    if case.get('symptom')=='肌少症':
        case['pre_knowledge']=[x.replace('依 AWGS 標準','依 AWGS 2019 教案標準') for x in case['pre_knowledge']]
        for d in case['kdp']:
            if 'ALMI' in d.get('phase','') or '診斷' in d.get('phase',''):
                d['prompt']='【依AWGS 2019教案】'+d['prompt']
        for q in case['quiz']:
            if 'ALMI' in q.get('question','') or '診斷' in q.get('question',''):q['question']='【依AWGS 2019教案】'+q['question']
        case['pre_knowledge']+=['版本核對：AWGS 2025診斷演算法與2019不同。本歷史教案診斷題依2019作答，教師應核定適用版本。']
    case['patient_behavior'] = variant['patient_behavior']
    case['goals'] = [task, variant['learner_task'], *case['variant']['supplement_tasks']]
    case['pre_knowledge'] = [case['goals_text']] if 'goals_text' in case else case['pre_knowledge']
    case['pre_knowledge'] += ['本職類任務：'+task, '本級任務：'+variant['learner_task'], *case['variant']['supplement_tasks']]
    return case


def hint_budget(level):
    return None if level <= 2 else 1 if level == 3 else 0
