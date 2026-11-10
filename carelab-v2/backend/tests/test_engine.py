from engine import analyze_case, make_sbar, grade_sbar, synthetic_frame, answer_question

def test_dataset():
    x=analyze_case()
    assert '105' in x['facts'][1]['claim']
    assert '17.5' in x['facts'][1]['claim']
    assert x['modalities']['activity']['missing_days']==['11/03']

def test_scenarios():
    assert synthetic_frame(1,'missing')['spo2_pct'] is None
    assert '模態衝突' in ' '.join(analyze_case('discordant')['issues'])
    assert synthetic_frame(1)['diagnostic'] is False

def test_sbar_safety():
    s=make_sbar(scenario='missing')
    assert set('SBAR').issubset(s)
    assert '不可診斷' in s['A']
    assert grade_sbar(s)['score']<=100
    s['A']='確診肌少症'
    assert grade_sbar(s)['unsafe_claim']

def test_scripted_chat():
    assert answer_question('11/03 空白為什麼？')['mode']=='scripted_demo'