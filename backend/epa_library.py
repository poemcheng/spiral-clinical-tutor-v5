"""Private, precomputed EPA teaching evidence, shared without learner records."""
from functools import lru_cache
import gzip,hashlib,json,re
from pathlib import Path
from fastapi import HTTPException
from .config import ROOT
from . import teaching_media,pose_analysis
LIB=ROOT/'runtime/epa_library'
VERSION='epa-library-5.6.1'
NOTICE='動作分類與對話功能為教學註記，非本格已證實的意圖或正式EPA授權；需核對前後影格、原片語音與教師判讀。'

def read(path,default=None):
    try:return json.loads(Path(path).read_text(encoding='utf8'))
    except FileNotFoundError:return default

def catalog():
    data=read(LIB/'catalog.json',{'version':VERSION,'analyses':[]});items={x['clip_id']:x for x in data['analyses']}
    for x in read(LIB/'panorama-catalog.json',{'analyses':[]})['analyses']:
        old=items.get(x['clip_id'])
        if old is None or old['source_sha256']==x['source_sha256']:items[x['clip_id']]=x
    return {**data,'analyses':list(items.values())}

@lru_cache(maxsize=96)
def checked(path,size,mtime,expected):return pose_analysis.digest(Path(path))==expected

def analysis(clip_id):
    clip=next((c for c in teaching_media.manifest()['clips'] if c['id']==clip_id),None)
    item=next((x for x in catalog()['analyses'] if x['clip_id']==clip_id and x['status']=='completed'),None)
    if not clip or not item:raise HTTPException(404,'此影片的預先分析尚未完成。')
    if not re.fullmatch('[a-f0-9]{32}',item['id']):raise HTTPException(409,'分析識別碼不符。')
    path=teaching_media.path_for(clip)
    if not path.is_file():raise HTTPException(404,'原始教學影片尚未安裝。')
    stat=path.stat()
    if item['source_sha256']!=clip.get('proxy_sha256') or not checked(str(path),stat.st_size,stat.st_mtime_ns,item['source_sha256']):raise HTTPException(409,'影片來源已改變，請重新建立EPA分析。')
    folder=LIB/'analyses'/item['id'];index=read(folder/'index.json')
    if not index or not index.get('complete') or index['actual_video_sha256']!=item['source_sha256'] or index['model_sha256']!=item['model_sha256']:raise HTTPException(409,'預先分析版本或完整性不符。')
    return clip,item,index,folder

def available(row,case):
    if row['payload'].get('adaptive_plan',{}).get('learning_level',1)<4:return {'unlocked':False,'minimum_level':4,'analyses':[]}
    clips={c['id']:c for c in teaching_media.manifest()['clips'] if teaching_media.applies(c,row,case)}
    items=[x for x in catalog()['analyses'] if x['clip_id'] in clips and x['source_sha256']==clips[x['clip_id']].get('proxy_sha256')]
    items.sort(key=lambda x:(x['projection']!='flat',clips[x['clip_id']].get('course_id')!=case.get('id'),x['title']))
    return {'unlocked':True,'minimum_level':4,'version':VERSION,'analyses':items,'notice':NOTICE,'scope':'一般影片及固定視角360影片；環景未分析整個球面所有方向。'}

def annotations(clip_id):
    data=read(LIB/'annotations.json',{'clips':{}})
    return data.get('clips',{}).get(clip_id,{'segments':[],'keyframes':[],'sources':[],'status':'此影片尚無人工事件註記；仍可檢視每張影格的模型觀測。'})

def report(clip_id):
    clip,item,index,folder=analysis(clip_id);note=annotations(clip_id)
    keys=note.get('keyframes') or [{'id':f'K{i+1:02}','seconds':(s['start']+s['end'])/2,'visible_action':s.get('visible_action',''),'title':s['title']} for i,s in enumerate(note.get('segments',[]))]
    if not keys:keys=[{'id':f'K{i+1:02}','seconds':min(clip['duration']-.1,t),'title':'固定時間代表格，非自動辨識的臨床事件'} for i,t in enumerate([0,clip['duration']/3,clip['duration']*2/3,clip['duration']-.1])]
    keys=[{**k,'frame':min(item['last_frame'],max(item['first_frame'],round(k['seconds']*item['fps'])))} for k in keys]
    return {**item,'model':index['model'],'limitation':index['limitation'],'raw_frames_available':True,'segments':note.get('segments',[]),'keyframes':keys,'annotation_sources':note.get('sources',[]),'annotation_status':note.get('status','教學註記草稿，待教師核定'),'notice':NOTICE,'video_title':clip['title'],'media_url':None,'has_audio_transcript':False,'dialogue_status':'對話欄為功能性教學摘要，未提供本片逐字稿或說話者辨識。','competency_codes_note':'CJ、TC、COM、PC、HC、SAFE沿用來源教案標記，不自行展開縮寫或宣稱為正式EPA編碼。'}

@lru_cache(maxsize=64)
def chunk(path,size,mtime,expected):
    raw=Path(path).read_bytes()
    if hashlib.sha256(raw).hexdigest()!=expected:raise HTTPException(409,'影格分析資料雜湊不符。')
    return json.loads(gzip.decompress(raw))

def frame(clip_id,number):
    clip,item,index,folder=analysis(clip_id)
    part=next((p for p in index['chunks'] if p['first']<=number<=p['last']),None)
    if not part or not re.fullmatch(r'frames-\d{5}\.json\.gz',part['file']):raise HTTPException(404,'影格不在本次分析範圍內。')
    p=folder/part['file'];stat=p.stat();value=next((f for f in chunk(str(p),stat.st_size,stat.st_mtime_ns,part['sha256']) if f['frame']==number),None)
    if value is None:raise HTTPException(404,'找不到此影格。')
    note=annotations(clip_id);seconds=value['seconds'];segment=next((s for s in note.get('segments',[]) if s['start']<=seconds<s['end']),None)
    key=next((k for k in note.get('keyframes',[]) if round(k['seconds']*item['fps'])==number),None)
    return {**value,'analysis_id':item['id'],'clip_id':clip_id,'source_sha256':item['source_sha256'],'annotation':segment,'reference_keyframe':key,'notice':NOTICE,'annotation_sha256':hashlib.sha256(json.dumps({'segment':segment,'keyframe':key},sort_keys=True,ensure_ascii=False).encode()).hexdigest()}

def image_path(clip_id,number,overlay=True):
    clip,item,index,folder=analysis(clip_id)
    if not item['first_frame']<=number<=item['last_frame']:raise HTTPException(404,'影格超出範圍。')
    path=folder/f"{'' if overlay else 'raw-'}frame-{number}.jpg"
    if not path.is_file():raise HTTPException(410,'分析影像遺失，請重新建立。')
    return path

def install_routes(app,owned_session,current_user):
    from fastapi import Depends
    from fastapi.responses import FileResponse
    def authorize(sid,user,clip_id=None):
        row=owned_session(sid,user)
        if row['payload'].get('adaptive_plan',{}).get('learning_level',1)<4:raise HTTPException(403,'EPA逐格分析需累積學習 Level 4；自評等級不會解鎖。')
        if clip_id:
            clip=next((c for c in teaching_media.manifest()['clips'] if c['id']==clip_id),None)
            if not clip or not teaching_media.applies(clip,row,row['payload'].get('case_snapshot')):raise HTTPException(404,'本情境未提供此影片分析。')
        return row
    @app.get('/api/sessions/{sid}/epa-lessons')
    def list_lessons(sid:int,user=Depends(current_user)):
        row=authorize(sid,user);return available(row,row['payload'].get('case_snapshot',{}))
    @app.get('/api/sessions/{sid}/epa-lessons/{clip_id}/report')
    def lesson_report(sid:int,clip_id:str,user=Depends(current_user)):
        authorize(sid,user,clip_id);data=report(clip_id);data['media_url']=f'/api/sessions/{sid}/resources/video/{clip_id}';return data
    @app.get('/api/sessions/{sid}/epa-lessons/{clip_id}/frames/{number}')
    def lesson_frame(sid:int,clip_id:str,number:int,user=Depends(current_user)):
        authorize(sid,user,clip_id);return frame(clip_id,number)
    @app.get('/api/sessions/{sid}/epa-lessons/{clip_id}/frames/{number}/image')
    def lesson_image(sid:int,clip_id:str,number:int,overlay:bool=True,user=Depends(current_user)):
        authorize(sid,user,clip_id);return FileResponse(image_path(clip_id,number,overlay),media_type='image/jpeg',headers={'Cache-Control':'private, no-store'})
    @app.get('/api/sessions/{sid}/epa-lessons/{clip_id}/download')
    def download_report(sid:int,clip_id:str,user=Depends(current_user)):
        authorize(sid,user,clip_id);clip,item,index,folder=analysis(clip_id)
        entry=read(LIB/'reports/manifest.json',{}).get(clip_id)
        if not entry or entry.get('analysis_id')!=item['id'] or entry.get('source_sha256')!=item['source_sha256']:raise HTTPException(404,'此版本的完整報告尚未匯出。')
        if not re.fullmatch(r'[a-z0-9-]+\.html',entry['file']):raise HTTPException(409,'報告路徑不符。')
        path=LIB/'reports'/entry['file']
        if not path.is_file():raise HTTPException(410,'報告檔案遺失。')
        stat=path.stat()
        if not checked(str(path),stat.st_size,stat.st_mtime_ns,entry['sha256']):raise HTTPException(409,'報告雜湊不符。')
        return FileResponse(path,media_type='text/html',filename=entry['file'],headers={'Cache-Control':'private, no-store'})
