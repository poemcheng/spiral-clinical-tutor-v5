"""Versioned, stratified Stage 1 forms.

營養師、物理治療師、醫事放射師、醫師、護理師使用肌少症題庫（data/item_banks），
依現行題本題數分層抽題，自評與客觀題分開計分並比對兩者落差；其餘 7 職種沿用
stage1_bank 的職責任務草稿。題庫尚待職類教師審題核定。
"""
import hashlib
import json
import random
import secrets
from .legacy.content import DIMENSION_ORDER, objective_items
from .stage1_bank import BANK_VERSION, TRAINING_PROFESSIONS, role_items
from .legacy.builtin_cases import PROFESSIONS, DIMENSIONS
from . import sarcopenia_bank

LEVEL_CONTEXT = {
    1: '請回想需要教師逐步示範與提示的基礎任務，評估目前的把握程度。',
    2: '請評估在教師即時協助下執行任務的把握程度。',
    3: '請評估自行完成任務，並在必要時主動尋求協助的把握程度。',
    4: '請評估獨立整合個案資料、提出追蹤計畫及跨專業溝通的把握程度。',
    5: '請評估處理複雜情境、說明判斷依據並指導同儕的把握程度。',
}
LEGACY_SCALE = {'1': '非常不足', '2': '不足', '3': '普通', '4': '良好', '5': '非常有把握'}
HIDDEN_OBJECTIVE_FIELDS = {'answer','rubric','rubric_source_text','review_record','expected_keywords','explanation'}
OVERCONFIDENT = (80, 60)   # 自評 ≥ 80 且客觀 < 60：自評可能高估（v1.0 推薦規則）
UNDERCONFIDENT = (60, 80)  # 自評 < 60 且客觀 ≥ 80：信心不足


def _finish(core):
    core['content_hash'] = hashlib.sha256(json.dumps(core, ensure_ascii=False, sort_keys=True).encode()).hexdigest()
    return core


def _bank_snapshot(registry, profession, topic, level, previous, rng):
    bundle = registry.step1_bundle(profession, topic)
    items, objectives = sarcopenia_bank.draw_form(profession, level, previous, rng)
    counts = sarcopenia_bank.draw_counts(profession)
    version = sarcopenia_bank.bank_version()
    meta = sarcopenia_bank.level_meta(level)
    for q in items:
        original = next((d for d in bundle['dimensions'] if d['id'] == q['dimension']), None)
        q.update(adaptation_version=version,
                 reference_prompts=[x['prompt'] for x in original['items']] if original else [],
                 authoring_status='題庫草稿，尚待職類教師審題核定')
    label = PROFESSIONS[profession]['label']
    core = {'items': items, 'objectives': objectives, 'level': level, 'profession': profession, 'topic': topic,
            'form_title': f'{label}肌少症 Level {level} 自評與客觀前測',
            'source_file': '肌少症自評題庫_審題表_20261021.xlsx',
            'reference_source_file': bundle['source_file'],
            'source_status': '題庫依中山附醫教材、肌少症前測自評表 v1.0 與 AWGS 等指引編寫，尚待職類教師審題核定。',
            'objective_status': '客觀題與自評分開計分：單選題自動計分，簡答題待教師評閱；客觀題與自評分開呈現。',
            'form_version': version, 'sampling_version': sarcopenia_bank.SAMPLING_VERSION,
            'draw_basis': {'self': counts['self'], 'objective': counts['objective'],
                           'self_basis': counts['self_basis'], 'objective_basis': counts['objective_basis']},
            'level_name': meta['name'], 'level_supervision': meta['supervision'],
            'level_original': meta.get('dt_original') if profession == 'DT' else None,
            'training_available': profession in TRAINING_PROFESSIONS and bool(registry.cases_for(topic, profession)),
            'context': f"本級支持：{meta['supervision']}。請依最近的實際經驗與行為表現量尺作答。",
            'scale': sarcopenia_bank.self_scale()}
    return _finish(core)


def _create_snapshot(registry, profession, topic, level, previous=None):
    rng = random.Random(secrets.token_hex(16))
    previous = previous or {}
    if topic == '肌少症' and sarcopenia_bank.has_bank(profession):
        return _bank_snapshot(registry, profession, topic, level, previous, rng)
    if topic != '肌少症':
        return _course_snapshot(registry, profession, topic, level, previous, rng)
    bundle = registry.step1_bundle(profession, topic)
    items = []
    previous_ids = {q['item_id'] for q in previous.get('items', [])}
    bank = role_items(profession, level)
    for dim in DIMENSIONS:
        pool = [q for q in bank if q['dimension'] == dim['id']]
        # Avoid the last login's item in each dimension when an alternative exists.
        candidates = [q for q in pool if q['item_id'] not in previous_ids] or pool
        item = rng.choice(candidates)
        original = next((d for d in bundle['dimensions'] if d['id'] == dim['id']), None)
        items.append({**item, 'reference_prompts': [q['prompt'] for q in original['items']] if original else [],
                      'authoring_status': '平台編寫草稿，尚未經院方或職類教師核定'})
    rng.shuffle(items)
    obj_form = registry.objective_form(profession, topic) if profession in TRAINING_PROFESSIONS else None
    objectives = objective_items(obj_form) if obj_form else []
    # Objective tasks are separately versioned and scored; subjective rotation is not an exam.
    prev_obj = {q['item_id'] for q in previous.get('objectives', [])}
    available = [q for q in objectives if q['item_id'] not in prev_obj]
    picked = rng.sample(available if len(available) >= 3 else objectives, min(3, len(objectives)))
    for q in picked:
        # 舊題本以字母記答案（如 "B"），選項為 "B. ……"；改存選項全文才能與作答比對。
        if q['item_type'] == 'single_choice' and q['answer'] not in q['options']:
            q['answer'] = next((o for o in q['options'] if o.split('.')[0].strip() == q['answer']), q['answer'])
        rng.shuffle(q['options'])
    core = {'items': items, 'objectives': picked, 'level': level, 'profession': profession,
            'topic': topic, 'form_title': f'{PROFESSIONS[profession]["label"]}肌少症情境 Level {level} 六構面自評',
            'source_file': 'backend/stage1_bank.py', 'reference_source_file': bundle['source_file'],
            'source_status': '本自評為平台依職責與 Level 編寫之草稿；既有題本僅作參照，非院方核定原題。',
            'objective_status': '既有教材前測，尚未完成 Level 分層審核；另行顯示客觀表現。' if picked else '此職種無已核定的肌少症客觀前測，本次僅收集自評。',
            'form_version': BANK_VERSION, 'sampling_version': 'per-dimension-no-immediate-repeat-2',
            'training_available': profession in TRAINING_PROFESSIONS and bool(registry.cases_for(topic, profession)),
            'context': LEVEL_CONTEXT[level],
            'scale': LEGACY_SCALE}
    return _finish(core)


def create_snapshot(registry, profession, topic, level, previous=None):
    from .competencies import apply_profile
    core = _create_snapshot(registry, profession, topic, level, previous)
    core.pop('content_hash', None)
    return _finish(apply_profile(core, previous))


def public_snapshot(snapshot):
    return {**snapshot, 'objectives': [{k: v for k, v in q.items() if k not in HIDDEN_OBJECTIVE_FIELDS}
                                      for q in snapshot['objectives']]}


def _calibration(self_dims, objective_dims):
    rows = []
    for d, s in self_dims.items():
        o = objective_dims.get(d)
        if o is None:
            continue
        if s >= OVERCONFIDENT[0] and o < OVERCONFIDENT[1]:
            flag, note = 'overconfident', '自評高於客觀表現，建議以可驗證的任務型練習確認'
        elif s < UNDERCONFIDENT[0] and o >= UNDERCONFIDENT[1]:
            flag, note = 'underconfident', '客觀表現高於自陳表現，建議與教師確認經驗、練習機會及回饋需求'
        else:
            flag, note = 'consistent', '自評與客觀表現大致一致'
        rows.append({'dimension': d, 'self': s, 'objective': o, 'flag': flag, 'note': note})
    return rows


def score_snapshot(snapshot, answers, objective_answers):
    expected = {q['item_id'] for q in snapshot['items']}
    if set(answers) != expected or any(type(v) is not int or v < 1 or v > 5 for v in answers.values()):
        raise ValueError('請完成全部自評題，分數須為 1–5 的整數。')
    if set(objective_answers) != {q['item_id'] for q in snapshot['objectives']}:
        raise ValueError('請完成本次全部客觀前測。')
    by_dim = {}
    for q in snapshot['items']:
        by_dim.setdefault(q['dimension'], []).append(answers[q['item_id']] * 20)
    dimensions = {d: round(sum(v) / len(v), 1) for d, v in by_dim.items()}
    records, obj_dim = [], {}
    for q in snapshot['objectives']:
        given = objective_answers[q['item_id']]
        if not isinstance(given, str) or not given.strip() or len(given) > 4000:
            raise ValueError('客觀前測不可空白，答案最多 4000 字。')
        if q['item_type'] == 'single_choice' and given not in q['options']:
            raise ValueError('客觀前測選項不符本次題本。')
        score = (q['max_score'] if given == q['answer'] else 0) if q['item_type'] == 'single_choice' else None
        records.append({'item_id': q['item_id'], 'dimension': q.get('dimension'), 'score': score,
                        'max_score': q['max_score'],
                        'status': 'auto_scored' if score is not None else 'pending_teacher'})
        if score is not None and q.get('dimension'):
            got, total = obj_dim.get(q['dimension'], (0, 0))
            obj_dim[q['dimension']] = (got + score, total + q['max_score'])
    objective_dims = {d: round(g / t * 100, 1) for d, (g, t) in obj_dim.items() if t}
    auto = [r for r in records if r['score'] is not None]
    summary = {
        'self_mean': round(sum(dimensions.values()) / len(dimensions), 1) if dimensions else None,
        'objective_auto_percent': round(sum(r['score'] for r in auto) / sum(r['max_score'] for r in auto) * 100, 1) if auto else None,
        'objective_auto_items': len(auto),
        'pending_teacher_items': len(records) - len(auto),
    }
    from .competencies import result
    profession_result = result(snapshot, answers)
    if profession_result:
        summary['self_mean'] = round(sum(profession_result['competency_scores'].values()) / len(profession_result['competency_scores']), 1)
    calibration = _calibration(dimensions, objective_dims)
    summary['overconfident_dimensions'] = [r['dimension'] for r in calibration if r['flag'] == 'overconfident']
    summary['underconfident_dimensions'] = [r['dimension'] for r in calibration if r['flag'] == 'underconfident']
    return {**profession_result, 'self_dimensions': dimensions, 'objective_records': records, 'objective_dimensions': objective_dims,
            'calibration': calibration, 'summary': summary,
            'note': '自評與前測分開保存，並比對兩者落差；自評結果用於學習分流。開放題待教師評閱。'}


def _course_snapshot(registry, profession, topic, level, previous, rng):
    # These six prompts are explicitly platform-authored, NOT uploaded clinical exam items.
    case=next(c for c in registry.cases_for(topic,profession) if c.get('curriculum_version'))
    task=case['roles'][profession]['task']
    prompts={'CJ':['我能區分本案例已知資料與尚待確認的資訊。','我能用案例資料說明判斷依據，並指出限制。'],
      'PC':['我能依本職類任務安排評估的順序。','我能辨識目前仍需要補做的評估。'],
      'COM':['我能先回應病人或家屬的疑慮，再說明下一步。','我能以回覆示教確認病人或家屬的理解。'],
      'TC':['我能以SBAR向其他職類提出具體協助需求。','我能確認交接對象接收並安排後續追蹤。'],
      'SAFE':['我能遇到不安全的情況先停止並求助。','我能說出本職類處理界線及需要通報的情況。'],
      'HC':['我能把個人偏好與家庭支持納入計畫。','我能與病人或家屬討論可執行的共同目標。']}
    seen={q['item_id'] for q in previous.get('items',[])};items=[]
    for dim in DIMENSIONS:
        d=dim['id'];pool=[{'item_id':f"{case['id']}-{profession}-L{level}-{d}-{i}",'dimension':d,'dimension_name':dim['name'],
          'prompt':f"在{topic} Level {level}任務中，{text}",'authoring_status':'平台依上傳教案編寫，待審'} for i,text in enumerate(prompts[d])]
        items.append(rng.choice([q for q in pool if q['item_id'] not in seen] or pool))
    rng.shuffle(items)
    return _finish({'items':items,'objectives':[],'profession':profession,'topic':topic,'level':level,
      'form_title':f'{PROFESSIONS[profession]["label"]}・{topic} Level {level}任務自評',
      'source_file':case['source_file'],'reference_source_file':case['source_file'],
      'source_status':'平台依上傳教案任務編寫的六構面自評草稿；非肌少症Excel題庫，尚待審核。',
      'objective_status':'本情境尚無經核定的分級客觀前測，不以其他疾病題目替代。',
      'form_version':'course-task-self-20261022-1','sampling_version':'dimension-rotation-1','training_available':True,
      'context':'本職類任務：'+task,'scale':sarcopenia_bank.self_scale()})
