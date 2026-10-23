"""xAPI 1.0.3 export of saved learning events; stable IDs support LRS deduplication."""
import datetime,hashlib,json,uuid

BASE='https://clinical-tutor.example/xapi/'
def activity_base():
    import os
    from .config import RUNTIME
    override=os.getenv('XAPI_ACTIVITY_BASE')
    if override:return override.rstrip('/')+'/'
    path=RUNTIME/'xapi-installation-id.txt'
    if not path.exists():
        try:
            with path.open('x',encoding='utf-8') as f:f.write(str(uuid.uuid4()))
        except FileExistsError:pass
    return 'https://clinical-tutor.local/'+path.read_text(encoding='utf-8').strip()+'/xapi/'
VERBS={'assessment_completed':'completed','session_completed':'completed','teacher_review':'scored','lesson_saved':'experienced','learning_note_saved':'experienced','speech_transcribed':'interacted','voice_published':'interacted'}
def statement(event,user,session,site=BASE):
    data=json.loads(event['data']) if isinstance(event['data'],str) else event['data']
    verb=VERBS.get(event['kind'],'experienced')
    actor_hash=hashlib.sha256(('clinical-tutor:'+str(user['id'])).encode()).hexdigest()
    result={}
    if isinstance(data.get('score'),(int,float)):result['score']={'raw':data['score'],'min':0,'max':100}
    if 'completed' in event['kind']:result['completion']=True
    return {'id':str(uuid.uuid5(uuid.NAMESPACE_URL,f"{site}events/{event['id']}")),
        'actor':{'objectType':'Agent','account':{'homePage':site.rstrip('/'),'name':actor_hash}},
        'verb':{'id':'http://adlnet.gov/expapi/verbs/'+verb,'display':{'en-US':verb}},
        'object':{'objectType':'Activity','id':site+f"sessions/{session['id']}",'definition':{'name':{'zh-TW':session['profession']+' 臨床教學練習'},'type':'http://adlnet.gov/expapi/activities/lesson'}},
        'timestamp':datetime.datetime.fromtimestamp(event['created'],datetime.timezone.utc).isoformat(),
        'context':{'registration':str(uuid.uuid5(uuid.NAMESPACE_URL,f"{site}sessions/{session['id']}")),'extensions':{site+'event-kind':event['kind'],site+'profession':session['profession'],site+'level':session['level']}},
        **({'result':result} if result else {})}
