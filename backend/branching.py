"""Native H5P Branching Scenario plus server-validated, ungraded practice paths."""
import hashlib,html,json,uuid
from . import characters
from .config import ROOT

VERSION='branching-practice-5.6.0'

def text_node(title,text,next_id,ending=None):
    node={'type':{'library':'H5P.AdvancedText 1.1','params':{'text':text},'metadata':{'title':title}},
          'nextContentId':next_id,'showContentTitle':True,'proceedButtonText':'繼續情境','contentBehaviour':'disabled','feedback':{}}
    if ending:node['feedback']={'title':'先補強安全，再重新練習','subtitle':ending,'endScreenScore':0}
    return node

def content(row):
    case=row['payload']['case_snapshot'];actor=characters.selected(row);questions=case.get('kdp',[])
    nodes=[text_node('本次教案分支練習','<p>'+html.escape(case['title'])+'</p><p>與'+html.escape(actor.get('display_name') or actor['title'])+'練習。選擇不同回應會進入對應回饋或補強結局。</p><p>這是教學練習；回饋提示與正式評量分別保存。</p>',1 if questions else -1)]
    mapping={};question_ids=[]
    for question in questions:
        index=len(nodes);question_ids.append(index);nodes.append({});choices=[]
        for option_index,option in enumerate(question['options']):
            feedback_id=len(nodes);score=option['score'];critical=bool(question.get('critical') and score==0)
            choices.append({'text':html.escape(option['text']),'nextContentId':feedback_id,'feedback':{}})
            feedback=html.escape(option.get('feedback') or '請核對原始教案的理由與資料界線。')
            nodes.append(text_node('安全補強' if critical else '回應後的教學回饋',f'<p>{feedback}</p>',-1 if critical else index))
            mapping[feedback_id]={'question_id':question['id'],'phase':question['phase'],'option_index':option_index,
                'choice':option['text'],'feedback':option.get('feedback',''),'meets_rubric':score==max(o['score'] for o in question['options']),
                'critical_error':critical,'retry':score<max(o['score'] for o in question['options'])}
        nodes[index]={'type':{'library':'H5P.BranchingQuestion 1.0','params':{'branchingQuestion':{'question':'<p>'+html.escape(question['prompt'])+'</p>','alternatives':choices}},'metadata':{'title':question['phase']}},
            'showContentTitle':True,'contentBehaviour':'disabled'}
        for choice in choices:
            detail=mapping[choice['nextContentId']]
            if detail['critical_error']:
                nodes[choice['nextContentId']]['feedback']={'title':'安全關鍵分支：需要補強','subtitle':'請先閱讀本題回饋，再重新練習。這是模擬分支結果，不表示真實病人已發生傷害。','endScreenScore':0}
    for i,question_id in enumerate(question_ids):
        for choice in nodes[question_id]['type']['params']['branchingQuestion']['alternatives']:
            detail=mapping[choice['nextContentId']]
            if detail['meets_rubric']:nodes[choice['nextContentId']]['nextContentId']=question_ids[i+1] if i+1<len(question_ids) else -1
    for index,node in enumerate(nodes):
        node['type']['subContentId']=str(uuid.uuid5(uuid.NAMESPACE_URL,f"{VERSION}:{row['payload']['case_hash']}:{actor['id']}:{index}"))
    params={'branchingScenario':{'title':case['title']+'｜教案分支練習',
        'startScreen':{'startScreenTitle':'教案分支練習','startScreenSubtitle':html.escape(case['title'])+' · 自評難度 Level '+str(row['level'])},
        'endScreens':[{'contentId':-1,'endScreenTitle':'本次分支練習完成','endScreenSubtitle':'請整理選擇的理由，再與虛擬角色討論。分支提示不等於能力認證。','endScreenScore':0}],
        'content':nodes,'scoringOptionGroup':{'scoringOption':'no-score','includeInteractionsScores':False},
        'behaviour':{'enableBackwardsNavigation':False,'forceContentFinished':False,'randomizeBranchingQuestions':False},
        'l10n':{'startScreenButtonText':'開始分支練習','endScreenButtonText':'重新練習（保留本次歷程）','proceedButtonText':'繼續情境','backButtonText':'返回','scoreText':'練習紀錄','fullscreenAria':'全螢幕','replayButtonText':'重播','disableProceedButtonText':'請先完成本段'}}}
    version=hashlib.sha256(json.dumps([VERSION,params,row['payload']['case_hash'],actor['id'],row['level']],sort_keys=True,ensure_ascii=False).encode()).hexdigest()
    return params,version,mapping

def manifest():
    provenance=json.loads((ROOT/'frontend/vendor/h5p-libraries/provenance.json').read_text())
    required=['H5P.BranchingScenario','H5P.BranchingQuestion','H5P.AdvancedText','FontAwesome']
    return {'title':'教案分支練習','language':'zh-tw','mainLibrary':'H5P.BranchingScenario','embedTypes':['iframe'],
        'preloadedDependencies':[{'machineName':name,'majorVersion':provenance[name]['majorVersion'],'minorVersion':provenance[name]['minorVersion']} for name in required]}

def validate_state(params,state):
    path=state.get('userPath',[])
    if not isinstance(path,list) or len(path)>160 or any(type(n) is not int for n in path):raise ValueError('分支路徑格式不正確。')
    nodes=params['branchingScenario']['content']
    if path and path[0]!=0:raise ValueError('分支路徑必須從開始節點進入。')
    for index,node_id in enumerate(path):
        if node_id==-1:
            if index!=len(path)-1 or index==0:raise ValueError('結局後不能繼續跳轉。')
            continue
        if not 0<=node_id<len(nodes):raise ValueError('未知分支節點。')
        if index+1<len(path):
            node=nodes[node_id];q=node['type']['params'].get('branchingQuestion')
            allowed=[a['nextContentId'] for a in q['alternatives']] if q else [node['nextContentId']]
            if path[index+1] not in allowed:raise ValueError('分支路徑包含未允許的跳轉。')
    canonical={'userPath':path[:],'child':{},'scoring':{'scores':[],'visitedIndex':0},'xAPIData':[]}
    if path and path[-1]==-1:
        last=nodes[path[-2]];feedback=last.get('feedback')
        canonical['endScreen']={'endScreenTitle':feedback['title'] if feedback else params['branchingScenario']['endScreens'][0]['endScreenTitle'],
            'endScreenSubtitle':feedback['subtitle'] if feedback else params['branchingScenario']['endScreens'][0]['endScreenSubtitle'],'endScreenScore':0,'showScore':False}
    return canonical

def analyze(params,mapping,path):
    choices=[mapping[n] for n in path if n in mapping]
    complete=bool(path and path[-1]==-1)
    outcome='safety-remediation' if complete and any(x['critical_error'] for x in choices) else 'completed' if complete else 'in-progress'
    return {'outcome':outcome,'choices':choices,'remediation_count':sum(x['retry'] for x in choices),'finished':complete,
            'evidence_type':'client_reported_path_validated_against_source_graph','formal_score_changed':False}

def state_for(row):
    params,version,mapping=content(row)
    run=next((r for r in reversed(row['payload'].get('branching_runs',[])) if r['content_version']==version),None)
    return {'content_version':version,'run_id':run['id'] if run else None,'state':run['state'] if run else {},
        'summary':run.get('summary') if run else None,'reviews':[r for r in row['payload'].get('branching_reviews',[]) if run and r['run_id']==run['id']],
        'version':VERSION}
