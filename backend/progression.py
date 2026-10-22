"""Learning placement/progression is distinct from formal teacher approval."""
import json,time
from .config import ROOT
POLICY=json.loads((ROOT/'data/learning_policy.json').read_text(encoding='utf-8'))
MODEL='independent-levels-v1'

def score_level(score):
    return next(b['level'] for b in reversed(POLICY['level_bands']) if score>=b['min'])

def level_state(store,uid,profession,topic):
    learner=store.one('SELECT * FROM learning_progress WHERE user_id=? AND profession=? AND topic=?',(uid,profession,topic))
    if learner and json.loads(learner['data']).get('progression_model')==MODEL:return learner['level']
    return earned_state(store,uid,profession,topic)['level']

def assessment_level(store,uid,profession,topic):
    previous=store.one('SELECT scores FROM attempts WHERE user_id=? AND profession=? AND topic=? AND completed IS NOT NULL ORDER BY id DESC LIMIT 1',(uid,profession,topic))
    scores=json.loads(previous['scores'] or '{}') if previous else {}
    score=scores.get('summary',{}).get('self_mean')
    return score_level(score) if score is not None else 1

def save_level(c,uid,profession,topic,level,data):
    c.execute('''INSERT INTO learning_progress VALUES (?,?,?,?,?,?) ON CONFLICT(user_id,profession,topic)
      DO UPDATE SET level=excluded.level,data=excluded.data,updated=excluded.updated''',
      (uid,profession,topic,level,json.dumps(data,ensure_ascii=False),time.time()))

def place(store,c,uid,profession,topic,scores):
    score=scores['summary']['self_mean'];recommended=score_level(score)
    existing=store.one('SELECT * FROM learning_progress WHERE user_id=? AND profession=? AND topic=?',(uid,profession,topic))
    data=json.loads(existing['data']) if existing else {}
    level=level_state(store,uid,profession,topic)
    if data.get('progression_model')!=MODEL:data.update(earned_state(store,uid,profession,topic)['data'])
    data.update(latest_self_score=score,latest_self_level=recommended,policy_version=POLICY['version'],progression_model=MODEL)
    save_level(c,uid,profession,topic,level,data)
    result={'self_score':score,'self_level':recommended,'learning_level':level,'policy_version':POLICY['version'],
      'bands':POLICY['level_bands'],'note':'自評分流依本次作答與經驗量尺決定題目及案例難度；累積學習等級只依練習使用與正確性解鎖教材資訊，兩者獨立計算。教師正式核定另行保存。'}
    scores['level_result']=result
    scores['note']='自評分數用於學習分級；客觀前測與教師正式評量另行保存。'
    return result

def practice_records(store,uid,profession,topic):
    rows=store.all("SELECT id,data FROM sessions WHERE user_id=? AND profession=? AND topic=? AND status='completed' ORDER BY id",(uid,profession,topic))
    records=[]
    for row in rows:
        data=json.loads(row['data']);result=data.get('result',{});score=result.get('objective_score')
        if score is None:continue
        review=store.one('SELECT id,score,decision FROM reviews WHERE session_id=? ORDER BY id DESC LIMIT 1',(row['id'],))
        actual=review['score'] if review else score
        critical=[q for q in data.get('case_snapshot',{}).get('kdp',[]) if q.get('critical')]
        safe=not data.get('safety_blocked',False) and not (review and review['decision']=='revise') and all(data.get('decisions',{}).get(q['id'],{}).get('score',0)>0 for q in critical)
        reviewed_safety=store.one("SELECT json_extract(data,'$.safety_pass') passed FROM events WHERE kind='teacher_review' AND json_extract(data,'$.review_id')=? ORDER BY id DESC LIMIT 1",(review['id'],)) if review else None
        if reviewed_safety and not reviewed_safety['passed']:safe=False
        records.append({'session_id':row['id'],'score':actual,'objective_score':score,'safe':safe,'teacher_verified':bool(review and review['decision']=='approve')})
    return records

def earned_state(store,uid,profession,topic):
    """Reconstruct earned progress without importing self ratings or teacher levels."""
    records=practice_records(store,uid,profession,topic);level=1;passed=0;baseline=0
    for index,record in enumerate(records):
        passed+=bool(record['safe'] and record['score']>=POLICY['promotion_score'])
        recent=records[max(0,index+1-POLICY['mastery_window']):index+1]
        mastery=sum(r['score'] for r in recent)/len(recent)
        if level<5 and passed-baseline>=POLICY['promotion_passes'] and mastery>=POLICY['promotion_score'] and all(r['safe'] for r in recent):
            level+=1;baseline=passed
    return {'level':level,'data':{'last_promotion_passes':baseline,'progression_model':MODEL,'policy_version':POLICY['version']}}

def migrate_legacy(store):
    """Repair only derived aggregates; never rewrite attempts, sessions or reviews."""
    with store.tx() as c:
        for row in store.all('SELECT * FROM learning_progress'):
            data=json.loads(row['data'])
            if data.get('progression_model')==MODEL:continue
            earned=earned_state(store,row['user_id'],row['profession'],row['topic'])
            data['level_before_separation']=row['level']
            data.update(earned['data'])
            save_level(c,row['user_id'],row['profession'],row['topic'],earned['level'],data)
            store.event(c,row['user_id'],None,'learning_levels_separated',{'profession':row['profession'],'topic':row['topic'],'previous_coupled_level':row['level'],'earned_level':earned['level'],'policy_version':POLICY['version']})

def evidence(store,uid,profession,topic):
    records=practice_records(store,uid,profession,topic)
    recent=records[-POLICY['mastery_window']:]
    mastery=round(sum(r['score'] for r in recent)/len(recent),1) if recent else None
    passed=sum(r['safe'] and r['score']>=POLICY['promotion_score'] for r in records)
    return {'completed_practices':len(records),'mastery':mastery,'passed_practices':passed,
      'learning_points':sum(round(r['objective_score']) for r in records),'recent_evidence':recent,
      'verified_mastery':round(sum(r['score'] for r in recent)/len(recent),1) if recent and all(r['teacher_verified'] for r in recent) else None}

def plan(store,uid,profession,topic,level):
    result=evidence(store,uid,profession,topic)
    count=result['completed_practices'];mastery=result['mastery']
    safe_recent=all(r['safe'] for r in result['recent_evidence'])
    paths=[{**p,'unlocked':count>=p['practices'] and (p['mastery']==0 or mastery is not None and mastery>=p['mastery'] and safe_recent),
      'requirement':'完成本次自評即可開始' if p['id']=='core' else f"完成 {p['practices']} 輪且近期熟練度達 {p['mastery']} 分，近期安全項目通過且無待補作"} for p in POLICY['paths']]
    tier=sum(p['unlocked'] for p in paths)
    cumulative=level_state(store,uid,profession,topic)
    return {**result,'tier':tier,'video_count':tier,'paths':paths,'level':level,'self_level':level,'learning_level':cumulative,'policy_version':POLICY['version'],
      'information':[{**i,'unlocked':cumulative>=i['level']} for i in POLICY['information']],
      'scene_mode':['guided','exploration','team'][tier-1],'modules':[p['module'] for p in paths if p['unlocked']],
      'reason':f"自評分流 Level {level}；累積學習 Level {cumulative}；完成 {count} 輪；近期熟練度 {mastery if mastery is not None else '待累積'}；學習積分 {result['learning_points']}",
      'mastery_note':'最近3輪客觀表現平均；有教師覆核時採該輪教師分數。安全未通過或需補作時不解鎖進階路徑。重複觀看或登入不增加分數。'}

def advance(store,c,uid,profession,topic):
    old=level_state(store,uid,profession,topic);ev=evidence(store,uid,profession,topic)
    previous=store.one('SELECT data FROM learning_progress WHERE user_id=? AND profession=? AND topic=?',(uid,profession,topic))
    data=json.loads(previous['data']) if previous else {}
    if data.get('progression_model')!=MODEL:data.update(earned_state(store,uid,profession,topic)['data'])
    baseline=data.get('last_promotion_passes',0)
    promoted=ev['passed_practices']-baseline>=POLICY['promotion_passes'] and ev['mastery'] is not None and ev['mastery']>=POLICY['promotion_score'] and all(r['safe'] for r in ev['recent_evidence']) and old<5
    level=old+1 if promoted else old
    if promoted:data['last_promotion_passes']=ev['passed_practices']
    data.update(policy_version=POLICY['version'],progression_model=MODEL,learning_points=ev['learning_points'],mastery=ev['mastery'])
    save_level(c,uid,profession,topic,level,data)
    return {'previous_level':old,'learning_level':level,'promoted':promoted,**ev,'next_plan':plan(store,uid,profession,topic,level),
      'note':'每累積2輪安全達標且熟練度達80分，學習Level升一級，最高Level5；教師正式核定另存。'}

def information_for(case,plan):
    """Extra teaching scaffolds, never additional clinical facts or decision answers."""
    items=plan.get('information',[])
    text={
      'background':[case.get('variant',{}).get('role_task') or '；'.join(case.get('goals',[])[:2]),'對照本職類核心指標閱讀已知資料，並指出資料缺口。'],
      'interview':['辨識各職類負責的評估與交接界線；放射、功能與營養評估不可互換。','以SBAR說明已知事實、限制、協助需求與追蹤，確認接收者。'],
      'handoff':['在上方「案例觀察影片」播放本情境已提供的教材；未提供時顯示缺少影片。','記錄情緒線索、溝通行為與職類任務；影片不會改寫本輪病歷。'],
      'source_limits':['在上方360影片播放器拖曳或使用方向鍵切換視角，辨識成員位置及交接方向。','四支影片的球面投影及格式已核對，情境與職類對應仍待教師核定。'],
      'reflection':['暫停影片後使用上一格／下一格，對照時間、影格與視角記錄觀察。','保存觀察後可由教師在訓練紀錄檢視；學員觀察不是自動臨床判讀。','累積使用代表教材解鎖程度，不代表取得指導資格；教學及正式評量仍由教師核定。']}
    return [{**item,**({'content':text[item['kind']]} if item['unlocked'] else {})} for item in items]
