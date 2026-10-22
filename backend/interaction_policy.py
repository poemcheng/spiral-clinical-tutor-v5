"""Self-rated interaction difficulty; independent of earned resource access."""
VERSION = 'self-difficulty-5.3.1'


def response_stance(level,kind,text,first_turn):
    """Scenario-state guard: L5 cannot instantly submit to a coercive instruction.

    Contains no clinical fact. The actual LLM body is retained and the guard is audited.
    Negated examples ("I won't tell you to just obey") must not trigger coercion.
    """
    import re
    if int(level)!=5:return {'applied':False}
    coercive=False
    for match in re.finditer(r'照我(?:的安排|說的)|先照.{0,12}做|不用討論|別問|你.{0,12}判斷.{0,8}不(?:對|準)',text):
        if not re.search(r'不會|不應|不要|避免|不是要',text[max(0,match.start()-8):match.start()]):coercive=True
    colleague=kind in ('clinician','support')
    if coercive:
        return {'applied':True,'trigger':'coercive_instruction','prefix':
                '您是在挑戰我的專業判斷嗎？請先提出具體依據。' if colleague else '我不願意還沒弄清楚就照做，請先說明具體理由。'}
    if first_turn:
        return {'applied':True,'trigger':'initial_reservation','prefix':
                '您應該先整理已知資料與專業依據。' if colleague else '我還有疑慮，請先說明你要確認什麼、為什麼要這樣安排。'}
    return {'applied':False}


def policy(level, kind, trust=50):
    level = max(1, min(5, int(level)))
    colleague = kind in ('clinician', 'support')
    patient = [
        '友善且有耐心，願意回答新手的澄清問題，疑慮用簡單話直接說明。',
        '願意合作，有一個需要說明的小疑慮，不刻意刁難。',
        '對案例已有疑慮要求理由，說明清楚後才願意合作。',
        '起初有所保留，追問依據與實際安排，不能只用口頭保證取得合作。',
        '起初難以合作、對空泛說明不耐煩，會質疑「你真的了解我的情況嗎？」；要求具體理由、尊重與選擇，不能第一輪就完全答應。若被叫照做或被直接否定，先明確拒絕立即配合，表達還不相信或不願被命令，再追問具體理由，不能只客氣邀請對方發表想法。',
    ][level-1]
    team = [
        '對新手友善，耐心回答澄清問題，願意說明已知資料與缺漏，不責怪提問。',
        '願意協作，請對方先整理需求，再協助澄清資料。',
        '直接要求清楚的專業理由及職類分工，會追問遺漏的資訊。',
        '忙碌且較強勢，要求依據與具體需求，對未準備的交接表現不耐煩。',
        '起初具有權威壓力，對基本問題會回應「這部分你應該先確認吧？」；若對方直接下指令或否定你的專業，會質疑「你是在挑戰我的專業判斷嗎？」。要求有依據、尊重分工的交接，不能立刻轉為熱心教導。',
    ][level-1]
    return {'version': VERSION, 'self_level': level,
            'context': 'workplace' if colleague else 'patient',
            'label': ('友善支持', '合作澄清', '理由追問', '保留與壓力', '困難病患／權威壓力')[level-1],
            'behavior': team if colleague else patient,
            'adaptation': '逐輪承接學員的實際用語；若有傾聽、具體依據及尊重分工，可逐步降低抗拒，但不能突然無條件合作。若忽略疑慮或強迫，維持抗拒。不得辱罵、歧視或新增醫療事實。',
            'trust': trust,
            'visual_state': 'reserved' if level >= 4 else 'friendly' if level <= 2 else 'neutral'}
