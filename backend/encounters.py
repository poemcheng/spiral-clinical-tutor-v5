"""Persisted scenario assignments and conversation lifecycle; no new clinical facts."""
import json
import re
import secrets
from . import characters

VERSION = 'encounters-5.4.0'
REPLY_SCHEMA={'type':'object','properties':{
    'text':{'type':'string','minLength':1,'maxLength':150},
    'phase':{'type':'string','enum':['active','closing','closed']},
    'emotion':{'type':'string','enum':['friendly','reserved','concerned','neutral']}},
    'required':['text','phase','emotion'],'additionalProperties':False}
TASKS = {
 'RT': {'PT': [('影像與功能資料交接', '向物理治療師說明本教案影像資料、檢查條件與限制，釐清功能評估還需要什麼資訊。'), ('檢查協作', '與物理治療師確認本教案檢查準備、移位協助及資料缺口，約定誰負責確認。')]},
 'DT': {'PT': [('營養與復健協作', '與物理治療師交接本教案已知營養問題及活動需求，釐清計畫是否可共同執行。'), ('追蹤與分工', '與物理治療師討論本教案營養和活動追蹤，確認資訊缺口、分工及回報方式。')]},
 'PT': {'patient': [('復健說明與疑慮', '以病人能理解的方式說明本教案評估或復健安排，先聽疑慮，再確認理解與意願。'), ('生活目標訪談', '了解本教案病人的生活目標與執行障礙，共同確認下一步；未記載的資料主動標明待確認。')]},
 'MD': {'patient': [('評估與共同決策', '向本教案病人說明已知資料及不確定性，了解期待，討論可接受的照護下一步。'), ('病情說明與追蹤', '回應本教案病人的疑問，確認理解、資料缺口及後續追蹤安排。')]},
 'RN': {'patient': [('檢查與治療過程說明', '向本教案病人說明已記載的檢查、治療或照護流程，回應疑慮並以回述確認理解。'), ('照護與安全衛教', '了解本教案病人的照護困難，說明活動與安全注意事項，確認需要哪些協助。')],
        'PT': [('復健照護協作', '向物理治療師交接本教案護理觀察、活動與安全疑慮，討論如何協助復健及確認分工。'), ('照護追蹤交接', '與物理治療師核對本教案已知功能資料、尚待確認事項及回報責任。')]},
}

def target(actor):
    return 'patient' if actor['kind'] in ('patient', 'caregiver') else actor['profession']

def assign(row, case, chooser=secrets.choice):
    targets=list(characters.PAIRINGS.get(row['profession'], ['patient']))
    # A nursing episode always includes both partners; its starting partner varies.
    if len(targets)>1 and chooser([False,True]):targets.reverse()
    entries=[]
    for key in targets:
        candidates=TASKS.get(row['profession'],{}).get(key,[('案例會談',case.get('variant',{}).get('role_task','釐清本教案疑慮與下一步。'))])
        title,task=chooser(candidates)
        actor_id=characters.default_actor({**row,'payload':{**row.get('payload',{}),'encounter_plan':{},'case_snapshot':case,'interaction_policy':{'targets':[key]}}})
        entries.append({'target':key,'actor_id':actor_id,'title':title,'task':task,'state':'ready','turns':0,
                        'id':secrets.token_hex(8),'version':VERSION})
    return {'version':VERSION,'case_id':case['id'],'case_hash':row.get('payload',{}).get('case_hash'),
            'self_level':row['level'],'entries':entries,'assignment':'一次抽選後固定；重新整理不重抽。情節不新增病歷事實。'}

def current(row, actor=None):
    actor=actor or characters.selected(row)
    entries=row.get('payload',{}).get('encounter_plan',{}).get('entries',[])
    return next((x for x in entries if x['target']==target(actor)),None)

def learner_closes(text):
    if re.search(r'不要結束|不想結束|先不要|還有|再問|繼續',text):return False
    return bool(re.search(r'再見|結束(?:這次|本次|對話|會談)?|先到這[裡里]|今天到這|下次再|沒有其他問題|沒有問題了|可以收尾',text)
                or re.fullmatch(r'(?:好[的啊]?|可以|沒問題|就這樣)[，,、\s]*(?:謝謝(?:您|你)?|辛苦了)?[。！!\s]*',text.strip()))

def decode_reply(value, turn, previous, learner_text):
    """The model can propose closure; only the learner can accept it or stop."""
    body=value.strip();phase='active';emotion='neutral'
    if body.startswith('```'):body=re.sub(r'^```(?:json)?\s*|\s*```$','',body)
    if body.startswith('{'):
        obj=json.loads(body)
        body=obj.get('text','')
        if not isinstance(body,str) or not body.strip():raise ValueError('角色回覆缺少口語內容。')
        phase=obj.get('phase','active');emotion=obj.get('emotion','neutral')
    if phase not in ('active','closing','closed'):phase='active'
    if emotion not in ('friendly','reserved','concerned','neutral'):emotion='neutral'
    # No hard maximum: complex conversations may continue for any number of turns.
    if phase in ('closing','closed') and turn<3:phase='active'
    if phase=='closed' and not (previous=='closing' and learner_closes(learner_text)):phase='closing' if turn>=3 else 'active'
    if previous=='closing' and learner_closes(learner_text):phase='closed'
    return body.strip(),{'phase':phase,'emotion':emotion,'turns':turn,'version':VERSION}

def save_reply(payload, actor, conversation):
    plan=payload.get('encounter_plan',{})
    for entry in plan.get('entries',[]):
        if entry['target']==target(actor):
            entry.update(state=conversation['phase'],turns=conversation['turns'],emotion=conversation.get('emotion','neutral'))
    return plan

def suppress_repeated_missing_question(body,messages):
    """Keep complete model statements, removing requests for already missing values.

    This is dialogue memory, not a clinical assertion that a measurement is absent.
    A learner's reported gap remains unverified and visible in the transcript.
    """
    topics={'握力':('握力',),'坐站':('坐站',),'前次報告':('前次','前一次','上次報告')}
    missing=set()
    for message in messages:
        if message['role']!='user':continue
        for clause in re.split(r'[。！？!?；;，,]',message['content']):
            if re.search(r'尚未|還沒|沒有|未取得|待確認|未確認',clause):
                missing.update(key for key,words in topics.items() if any(w in clause for w in words))
    kept=[];removed=[]
    for sentence in re.findall(r'[^。！？!?]+[。！？!?]?',body):
        asks=bool(re.search(r'[？?]',sentence))
        repeat=any(any(w in sentence for w in topics[key]) for key in missing)
        repeat=repeat or bool(missing and re.search(r'這部分.{0,8}(?:資料|數據|數值)',sentence))
        requests_value=bool(re.search(r'數值|多少|是否|已經|已確認|確認過|核實',sentence))
        asks_plan=bool(re.search(r'何時|什麼時候|哪位|誰負責|如何(?:交接|回報)',sentence))
        if asks and repeat and requests_value and not asks_plan:removed.append(sentence)
        else:kept.append(sentence)
    return ''.join(kept).strip(),{'version':VERSION,'missing_topics_reported_by_learner':sorted(missing),
        'removed_repeated_questions':len(removed),'added_clinical_facts':False,
        **({'original_model_reply':body} if removed else {})}
