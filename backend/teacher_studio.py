"""Versioned teacher-authored lessons, local Graphify graph and source retrieval."""
import copy,hashlib,json,re,secrets,time
from pathlib import Path
from fastapi import Depends,HTTPException,Query
from pydantic import BaseModel,Field
from .store import encode
from .legacy.builtin_cases import PROFESSIONS
from . import curriculum

class LessonBody(BaseModel):
    expected_revision:int=Field(default=0,ge=0)
    title:str=Field(min_length=3,max_length=160)
    topic:str=Field(min_length=2,max_length=100)
    professions:list[str]=Field(min_length=1,max_length=12)
    summary:str=Field(min_length=10,max_length=3000)
    patient:str=Field(min_length=10,max_length=6000)
    objectives:str=Field(min_length=5,max_length=3000)
    knowledge:str=Field(min_length=5,max_length=6000)
    role_task:str=Field(min_length=5,max_length=3000)
    decision_prompt:str=Field(min_length=5,max_length=1000)
    correct_option:str=Field(min_length=3,max_length=1000)
    incorrect_option:str=Field(min_length=3,max_length=1000)
    explanation:str=Field(min_length=5,max_length=2000)
    source_title:str=Field(min_length=3,max_length=300)
    status:str='draft'

def case_from_lesson(row):
    d=json.loads(row['data']);ident=row['id'];professions=d['professions']
    return {'id':ident,'title':d['title'],'symptom':d['topic'],'professions':professions,'summary':d['summary'],'patient':d['patient'],'goals':d['objectives'].splitlines(),'pre_knowledge':d['knowledge'].splitlines(),'source_file':d['source_title'],'source_pages':[],'source_sha256':hashlib.sha256(row['data'].encode()).hexdigest(),'curriculum_version':f"teacher-lesson-{ident}-r{row['revision']}",'review_status':'教師已發布的模擬教案；不代表院方臨床核定','clinical_review':{'status':'教師編寫與發布；正式院方核定另行辦理'},'video_file':'','teacher_authored':True,'teacher_owner_id':row['owner_id'],'teacher_revision':row['revision'],'roles':{p:{'task':d['role_task']} for p in professions},'levels':{str(n):{'learner_task':d['role_task'],'support':['逐步引導','可即時求助','必要時確認','低提示整合','困難互動與替代解釋'][n-1],'patient_behavior':'由本輪等級互動規則決定'} for n in range(1,6)},'patient_script':d['patient'],'rubric':['資訊與理解確認：'+d['explanation']],'kdp':[{'id':ident+'-D1','phase':'教案關鍵決策','prompt':d['decision_prompt'],'critical':False,'hint':d['explanation'],'options':[{'text':d['correct_option'],'score':2,'dimension':'COM','feedback':d['explanation']},{'text':d['incorrect_option'],'score':0,'dimension':'COM','feedback':d['explanation']}]}],'quiz':[{'id':ident+'-Q1','question':d['decision_prompt'],'options':[d['correct_option'],d['incorrect_option']],'answer':d['correct_option'],'explain':d['explanation'],'dimension':'COM'}]}

def sync_registry(store,registry):
    rows=store.all("SELECT * FROM teacher_lessons WHERE status='published'")
    registry.cases[:]=[c for c in registry.cases if not c.get('teacher_authored')]
    registry.case_map={k:c for k,c in registry.case_map.items() if not c.get('teacher_authored')}
    for row in rows:
        case=case_from_lesson(row);registry.cases.append(case);registry.case_map[case['id']]=case
    return [{'id':c['id'],'topic':c['symptom'],'title':c['title'],'professions':c['professions'],'source_pages':[],'review_status':c['review_status'],'original_source_available':False,'has_original_video':False,'teacher_authored':True} for c in registry.cases if c.get('teacher_authored')]

TERMS=['肌少症','營養','復健','蛋白質','熱量','坐站','吞嚥','安全','病人','家屬','同理','交接','SBAR','回覆示教','DXA','ALMI','EPA','資訊缺口','權威','溝通','飲食','物理治療','護理','醫師','放射']

def graph_search(store,registry,query,sid=None):
    from graphify import build_from_json
    from importlib.metadata import version
    nodes=[];edges=[];texts={}
    def node(ident,label,kind,text,source):
        nodes.append({'id':ident,'label':label,'type':kind,'source_file':source,'confidence':'EXTRACTED','extraction_method':'source_fields','text':text});texts[ident]=text
    def edge(a,b,relation,source):edges.append({'source':a,'target':b,'relation':relation,'confidence':'EXTRACTED','source_file':source,'evidence':'來源欄位或文字明確包含此詞；不代表因果或臨床正確性'})
    def case_node(case):
        digest=hashlib.sha256(json.dumps(case,ensure_ascii=False,sort_keys=True).encode()).hexdigest()[:12]
        return 'lesson:'+case['id']+':'+digest
    cases=list(registry.cases)
    if sid is not None:
        selected=store.one('SELECT data FROM sessions WHERE id=?',(sid,))
        snapshot=json.loads(selected['data']).get('case_snapshot') if selected else None
        cases=[snapshot] if snapshot else []
    for case in cases:
        cid=case_node(case);source=case.get('source_file',case['id'])+' · '+case.get('curriculum_version','來源版本未標示');text='\n'.join([case['title'],str(case.get('patient','')),*case.get('goals',[]),*case.get('pre_knowledge',[])])
        node(cid,case['title'],'lesson',text,source)
    sql='SELECT s.id,s.data,m.id message_id,m.role,m.content FROM sessions s JOIN messages m ON m.session_id=s.id';args=()
    if sid is not None:sql+=' WHERE s.id=?';args=(sid,)
    sql+=' ORDER BY m.id DESC LIMIT 1200'
    for row in store.all(sql,args):
        d=json.loads(row['data']);case=d.get('case_snapshot',{});cid=case_node(case) if case.get('id') else 'lesson:unknown';mid='message:'+str(row['message_id']);source='training-session:'+str(row['id'])
        if cid not in texts:node(cid,case.get('title','歷史教案快照'),'lesson',json.dumps(case,ensure_ascii=False),source)
        node(mid,f"訓練{row['id']} · {'學員' if row['role']=='user' else '虛擬角色'}對話{row['message_id']}",'message',row['content'],source);edge(mid,cid,'belongs_to_lesson',source)
    for n in list(nodes):
        for term in TERMS:
            if term.lower() in n['text'].lower():
                tid='concept:'+term
                if tid not in texts:node(tid,term,'concept',term,'curated-vocabulary')
                edge(n['id'],tid,'mentions',n['source_file'])
    graph=build_from_json({'nodes':copy.deepcopy(nodes),'edges':copy.deepcopy(edges)},directed=True,dedup=False)
    query=query.strip();tokens=[t for t in TERMS if t.lower() in query.lower()]
    def rank(n):
        text=n['text'].lower();score=(20 if query.lower() in text else 0)+sum(text.count(t.lower()) for t in tokens)
        if not tokens and len(query)>1:score+=sum(text.count(query[i:i+2].lower()) for i in range(len(query)-1))*.1
        return score
    hits=sorted([(rank(n),n) for n in nodes if n['type']!='concept'],key=lambda x:-x[0]);hits=[n for score,n in hits[:12] if score>0]
    chosen={n['id'] for n in hits}
    for edge_ in edges:
        if edge_['source'] in chosen:chosen.add(edge_['target'])
    selected=[n for n in nodes if n['id'] in chosen];links=[x for x in edges if x['source'] in chosen and x['target'] in chosen]
    return {'engine':'Graphify '+version('graphifyy'),'mode':'本機來源欄位抽取與圖譜關聯檢索；未呼叫外部LLM','query':query,'indexed_nodes':graph.number_of_nodes(),'indexed_edges':graph.number_of_edges(),'scope':f'限定訓練{sid}的原始教案快照與最近1200筆對話' if sid else '已發布及既有教案、原訓練教案快照與最近1200筆授權對話','hits':[{'id':n['id'],'title':n['label'],'kind':n['type'],'source':n['source_file'],'excerpt':n['text'][:1800]} for n in hits],'nodes':[{'id':n['id'],'label':n['label'],'kind':n['type']} for n in selected],'edges':links,'answer':'\n\n'.join('['+n['source_file']+'] '+n['text'][:600] for n in hits[:5]) if hits else '未找到可支持的來源，請改用教案中的術語或指定訓練。','notice':'檢索回答摘錄來源，不自動核定臨床結論。文字共現關聯不表示因果；學員陳述可能有誤，必須區分來源角色。'}

def install(app,store,registry,teacher):
    @app.get('/api/teacher/lessons')
    def lessons(user=Depends(teacher)):
        rows=store.all('SELECT * FROM teacher_lessons ORDER BY updated DESC')
        return {'lessons':[{**{k:r[k] for k in ('id','owner_id','revision','status','updated')},**json.loads(r['data']),'editable':r['owner_id']==user['id']} for r in rows],'templates':[{'id':c['id'],'title':c['title']} for c in registry.cases if not c.get('teacher_authored')]}
    @app.get('/api/teacher/lessons/template/{ident}')
    def template(ident:str,user=Depends(teacher)):
        case=registry.case_map.get(ident)
        if not case:raise HTTPException(404,'找不到來源教案。')
        d=case['kdp'][0];opts=d['options'];good=max(opts,key=lambda x:x['score']);bad=min(opts,key=lambda x:x['score'])
        return {'title':case['title']+'（教師延伸）','topic':case['symptom']+'延伸','professions':case['professions'],'summary':case['summary'],'patient':str(case['patient']),'objectives':'\n'.join(case['goals']),'knowledge':'\n'.join(case['pre_knowledge']),'role_task':next(iter(case.get('roles',{}).values()),{}).get('task','依職類完成評估、說明與交接'),'decision_prompt':d['prompt'],'correct_option':good['text'],'incorrect_option':bad['text'],'explanation':good.get('feedback',d.get('hint','依來源教案核對')),'source_title':case.get('source_file','原始教案'),'status':'draft','expected_revision':0}
    def save(ident,body,user):
        if any(p not in PROFESSIONS for p in body.professions) or body.status not in ('draft','published'):raise HTTPException(400,'請設定有效職種與教案狀態。')
        if body.correct_option==body.incorrect_option:raise HTTPException(400,'兩個決策選項不可相同。')
        with store.tx() as c:
            old=store.one('SELECT * FROM teacher_lessons WHERE id=?',(ident,))
            if old and old['owner_id']!=user['id']:raise HTTPException(403,'僅編寫教師可修改此教案。')
            if (old['revision'] if old else 0)!=body.expected_revision:raise HTTPException(409,'教案已有新版本，請重新載入。')
            revision=body.expected_revision+1;data=encode(body.model_dump(exclude={'expected_revision'}));now=time.time()
            c.execute('DELETE FROM teacher_lessons WHERE id=?',(ident,));c.execute('INSERT INTO teacher_lessons VALUES (?,?,?,?,?,?)',(ident,user['id'],revision,body.status,data,now))
            c.execute('INSERT INTO teacher_lesson_revisions VALUES (?,?,?,?,?)',(ident,revision,user['id'],data,now));store.event(c,user['id'],None,'teacher_lesson_saved',{'id':ident,'revision':revision,'status':body.status})
        sync_registry(store,registry);return {'id':ident,'revision':revision,'status':body.status}
    @app.post('/api/teacher/lessons',status_code=201)
    def create(body:LessonBody,user=Depends(teacher)):return save('COURSE-TCH-'+secrets.token_hex(5).upper(),body,user)
    @app.put('/api/teacher/lessons/{ident}')
    def update(ident:str,body:LessonBody,user=Depends(teacher)):
        if not store.one('SELECT id FROM teacher_lessons WHERE id=?',(ident,)):raise HTTPException(404,'找不到教師教案。')
        return save(ident,body,user)
    @app.get('/api/teacher/knowledge/search')
    def search(q:str=Query(min_length=1,max_length=200),session_id:int|None=None,user=Depends(teacher)):
        sync_registry(store,registry)
        if session_id is not None and not store.one('SELECT id FROM sessions WHERE id=?',(session_id,)):raise HTTPException(404,'找不到訓練。')
        return graph_search(store,registry,q,session_id)
