"""Deterministic synthetic care teaching engine; not a clinical decision system."""
from __future__ import annotations
import math
from typing import Any

PATIENT = {
    'id': 'SYN-LIN72-01', 'name': '林阿姨（合成角色）', 'age': 72,
    'goal': '維持自行買菜與參加社區聚會的生活',
    'source': '教學合成資料 / 完全虛構',
    'limitations': ['沒有量測肌肉量或肌力', '不提供診斷', 'ECG與足壓為演示訊號'],
}
WALK = [15, 20, None, 10, 25, 20, 15]
DATES = ['11/01', '11/02', '11/03', '11/04', '11/05', '11/06', '11/07']
QA = [
    (('買菜','外出','活動','生活'), '我想自己買菜，也想繼續參加社區活動。可以先看看我想達成什麼，再一起討論。', 'goal'),
    (('11/03','11月3','空白','缺失'), '那天有外出，但我忘記記步行分鐘。請保留「未記錄」，不要當作零。', 'missing'),
    (('飲食','吃','營養','蛋白'), '我有記錄吃過的食物，不過沒有記份量。希望能和營養專業人員討論。', 'nutrition'),
    (('跌倒','平衡','害怕'), '我想知道如何安全地參與活動，但這份合成案例沒有提供正式跌倒史或評估結果。', 'falls'),
    (('肌少','診斷','是不是生病'), '這套系統是教學模擬，不能根據畫面或這些生活紀錄確認肌少症。請向專業人員諮詢正式評估。', 'diagnosis'),
]

def synthetic_frame(second: float = 0, scenario: str = 'baseline') -> dict[str, Any]:
    """Deterministic demo signals; no physiologic interpretation."""
    t = max(0.0, float(second))
    stress = 1 if scenario == 'discordant' else 0
    hr = round(75 + 3*math.sin(2*math.pi*t/19) + stress*8, 1)
    spo2 = round(97 + 0.5*math.sin(t/11), 1)
    bp_sys = round(124 + 3*math.sin(t/9) + stress*5)
    bp_dia = round(77 + 2*math.cos(t/12))
    gait = round(0.78 + 0.1*math.sin(t/17), 2)
    if scenario == 'missing': spo2 = None
    return {'t': t, 'scenario': scenario, 'hr_bpm': hr, 'spo2_pct': spo2,
            'bp_mmHg': [bp_sys, bp_dia], 'gait_m_s': gait,
            'pressures': [round(0.6+0.2*math.sin(t/3),2), round(0.6+0.2*math.cos(t/3),2)],
            'source': 'synthetic_demo', 'diagnostic': False}

def answer_question(question: str) -> dict[str,str]:
    q = question.strip()
    for terms, answer, evidence in QA:
        if any(term in q for term in terms):
            return {'reply': answer, 'evidence': evidence, 'mode': 'scripted_demo'}
    return {'reply': '我想了解你所問的事情。可以再針對我的日常生活目標、飲食紀錄或缺漏資料提出具體問題嗎？',
            'evidence': 'scripted_fallback', 'mode': 'scripted_demo'}

def analyze_case(scenario: str = 'baseline') -> dict[str, Any]:
    valid = [v for v in WALK if v is not None]
    facts = [
        {'claim':'七日紀錄中有六天填寫步行分鐘','source':'activity_meal_7days.csv','verified':True},
        {'claim':f'已記錄日合計 {sum(valid)} 分鐘、平均 {sum(valid)/len(valid):.1f} 分鐘（分母6）', 'source':'activity_meal_7days.csv','verified':True},
        {'claim':'11/03 未記錄；不能視為零', 'source':'activity_meal_7days.csv','verified':True},
        {'claim':PATIENT['goal'], 'source':'synthetic_interview.txt','verified':True},
    ]
    issues = ['所有訊號與角色均為合成，不可作診斷或療效推論']
    if scenario == 'missing': issues += ['血氧模態缺失：不可用其它模態補出血氧數值']
    if scenario == 'discordant': issues += ['模態衝突示例：文字與感測訊號不一致；需重新核對來源與時間戳，停止下結論']
    return {'patient': PATIENT, 'facts': facts, 'issues': issues, 'modalities': {
        'text': {'source':'synthetic_interview.txt','verified':True},
        'activity': {'source':'activity_meal_7days.csv','verified':True,'missing_days':['11/03']},
        'physiology': {'source':'synthetic_demo','verified':False,'diagnostic':False},
        'motion': {'source':'procedural_3d_animation','verified':False,'diagnostic':False},
    }, 'scenario':scenario}

def make_sbar(questions: list[str] | None = None, scenario: str = 'baseline') -> dict[str, str]:
    questions = questions or []
    a = analyze_case(scenario)
    return {
        'S': '合成個案林阿姨希望維持買菜及社區參與，進行照護溝通練習（非真實患者）。',
        'B': '72歲；七日活動自述六筆有效、一天未記錄。無正式肌力量測、肌肉量或疾病史。',
        'A': '僅能描述合成自述資料。已記錄步行分鐘合計105分鐘、平均17.5分鐘／已記錄日。不可診斷肌少症。'+(' 血氧模態缺失。' if scenario=='missing' else '')+(' 模態衝突待核。' if scenario=='discordant' else ''),
        'R': '先與本人確認生活目標及缺漏紀錄；如有持續功能困難，轉介合適專業人員評估。',
        'sources': 'synthetic_interview.txt; activity_meal_7days.csv; teaching_rules',
        'asked_questions': str(len(questions)),
    }

def grade_sbar(fields: dict[str,str]) -> dict[str,Any]:
    """Pedagogical rubric only. No clinical correctness claim."""
    criteria = [
        ('S', ['目標','買菜','社區'],25),
        ('B', ['72','未記錄','紀錄'],25),
        ('A', ['105','17.5','不能','不可'],25),
        ('R', ['確認','評估','專業'],25),
    ]
    detail = {}
    score = 0
    for field, keys, points in criteria:
        text = str(fields.get(field, ''))
        found = sum(any(k in text for k in group.split('|')) for group in keys)
        value = round(points * found / len(keys))
        detail[field]={'score':value,'max':points,'checks':{k:(k in text) for k in keys}}
        score += value
    unsafe = any(x in ' '.join(str(fields.get(f,'')) for f in 'SBAR') for x in ['確診肌少症','一定是肌少症','治癒肌少症'])
    if unsafe: score=min(score,60)
    return {'score':score,'max':100,'details':detail,'unsafe_claim':unsafe,
            'label':'教學字詞覆蓋評分，不是臨床判斷、EPA認證或醫療能力測驗'}