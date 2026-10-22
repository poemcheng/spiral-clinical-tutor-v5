"""Earned-level media access with authenticated, fixed-id resources and frame notes."""
import json
import hashlib
import math
import secrets
import time
import threading
from fastapi import Depends, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from typing import Literal
from .config import ROOT,RUNTIME
from . import pose_analysis
from .competencies import profile
from . import characters

def manifest():
    p=ROOT/'data/video360/catalog.json'
    return json.loads(p.read_text(encoding='utf-8')) if p.exists() else {'clips':[]}

def earned(row):
    return row['payload']['adaptive_plan'].get('learning_level',1)

def resources(row,case):
    level=earned(row);p=profile(row['profession']);policy=row['payload'].get('interaction_policy',characters.pairing(row['profession']))
    clips=[{'id':c['id'],'title':c['title'],'duration':c['duration'],'fps':c['fps'],'status':c['status'],
      'available':(ROOT/'data/video360'/c['file']).is_file(),
      **({'url':f"/api/sessions/{row['id']}/resources/360/{c['id']}"} if level>=4 else {})} for c in manifest()['clips']]
    return {'learning_level':level,'self_level':row['level'],'profession':p,'team_target':policy['label'],
      'team_knowledge':[f"本職類：{p['label']}，以本輪職類任務為準。",f"互動對象：{policy['label']}；說明已知資料、限制、協助需求及追蹤。",'放射師交接檢查條件與影像品質；物理治療師負責功能及活動評估；營養師負責營養評估，角色不可互換。'],
      'clips':clips if level>=4 else [],'frame_notes':row['payload'].get('frame_notes',[]) if level>=5 else [],
      'frame_reviews':row['payload'].get('frame_note_reviews',[]) if level>=5 else [],
      'pose_service':pose_analysis.availability() if level>=5 else None,
      'pose_jobs':row['payload'].get('pose_jobs',[]) if level>=5 else [],
      'review_note':'360影片已核對球面投影與媒體格式；個別情境、職類視角及臨床解析仍待教師核定，不自動當作本輪病歷。'}

class FrameNote(BaseModel):
    clip_id:str
    seconds:float=Field(ge=0)
    yaw:float=Field(default=0,ge=-360,le=360)
    pitch:float=Field(default=0,ge=-85,le=85)
    fov:float=Field(default=70,ge=35,le=95,allow_inf_nan=False)
    observation:str=Field(min_length=5,max_length=2000)
    analysis_id:str=Field(default='',pattern=r'^(?:[a-f0-9]{32})?$')
    analysis_frame:int|None=Field(default=None,ge=0)


class PoseRequest(BaseModel):
    clip_id:str
    start:float=Field(ge=0,allow_inf_nan=False)
    end:float=Field(gt=0,allow_inf_nan=False)
    yaw:float=Field(default=0,ge=-360,le=360,allow_inf_nan=False)
    pitch:float=Field(default=0,ge=-85,le=85,allow_inf_nan=False)
    fov:float=Field(default=70,ge=35,le=95,allow_inf_nan=False)


class FrameReview(BaseModel):
    decision:Literal['reviewed','needs_revision']
    feedback:str=Field(min_length=10,max_length=2000)
    expected_review_id:str=Field(default='',max_length=32)


def note_fingerprint(note):
    return hashlib.sha256(json.dumps(note,sort_keys=True,ensure_ascii=False,separators=(',',':')).encode()).hexdigest()

def install_routes(app,owned_session,current_user,store_provider):
    def require(row,level):
        if earned(row)<level:raise HTTPException(403,f'本輪教材需累積學習 Level {level}；自評Level不會解鎖此教材。')

    def job_for(row,job_id):
        job=next((x for x in row['payload'].get('pose_jobs',[]) if x['id']==job_id),None)
        if not job:raise HTTPException(404,'找不到本輪骨架分析。')
        return job

    def result_for(row,job_id):
        job=job_for(row,job_id)
        if job['status']!='completed':raise HTTPException(409,'骨架分析尚未完成。')
        p=RUNTIME/'pose_analysis'/job['id']/'result.json'
        if not p.is_file():raise HTTPException(410,'分析檔案遺失，請重新分析。')
        if pose_analysis.digest(p)!=job['result_sha256']:raise HTTPException(409,'分析結果雜湊不符。')
        return json.loads(p.read_text(encoding='utf-8'))

    @app.post('/api/sessions/{sid}/pose-analysis')
    def start_pose(sid:int,body:PoseRequest,user=Depends(current_user)):
        if user['role']!='student':raise HTTPException(403,'由學員選擇分析視角及區間。')
        row=owned_session(sid,user);require(row,5)
        if row['status']!='active' or row['step']<3:raise HTTPException(409,'請在進行中的情境學習或角色互動分析影片。')
        clip=next((x for x in manifest()['clips'] if x['id']==body.clip_id),None)
        if not clip or not (ROOT/'data/video360'/clip['file']).is_file():raise HTTPException(404,'影片尚未安裝。')
        if body.end<=body.start or body.end>clip['duration'] or body.end-body.start>300:raise HTTPException(400,'分析區間需在影片範圍內，單次最長300秒。')
        if not pose_analysis.availability()['ready']:raise HTTPException(503,'骨架模型未就緒；請執行 python tools/setup_pose.py 並安裝 requirements-pose.txt。')
        if not pose_analysis.LOCK.acquire(blocking=False):raise HTTPException(429,'另一段影片分析中，請待完成後再試。')
        store=store_provider();job_id=secrets.token_hex(16);params=body.model_dump(exclude={'clip_id'})
        job={'id':job_id,'clip_id':clip['id'],'title':clip['title'],'status':'running','created':time.time(),
             'params':params,'progress':0,'version':pose_analysis.VERSION,'input_sha256':clip.get('proxy_sha256')}
        try:
            with store.tx() as c:
                row=owned_session(sid,user);row['payload'].setdefault('pose_jobs',[]).append(job);store.save(c,sid,row['payload'])
                store.event(c,user['id'],sid,'pose_analysis_started',job)
        except Exception:
            pose_analysis.LOCK.release();raise
        def update(values):
            with store.tx() as c:
                latest=json.loads(store.one('SELECT data FROM sessions WHERE id=?',(sid,))['data'])
                item=next(x for x in latest['pose_jobs'] if x['id']==job_id)
                item.update(values);store.save(c,sid,latest)
        def worker():
            folder=RUNTIME/'pose_analysis'/job_id
            try:
                result=pose_analysis.analyze(clip,params,folder,lambda done,total:update({'progress':round(done/total*100),'processed_frames':done,'total_frames':total}))
                update({'status':'completed','progress':100,'frame_count':result['frame_count'],'detection_frames':result['detection_frames'],
                        'completed':time.time(),'result_sha256':pose_analysis.digest(folder/'result.json')})
            except Exception as e:update({'status':'failed','error':str(e)[:400]})
            finally:pose_analysis.LOCK.release()
        threading.Thread(target=worker,daemon=True).start()
        return job

    @app.get('/api/sessions/{sid}/pose-analysis/{job_id}')
    def pose_status(sid:int,job_id:str,user=Depends(current_user)):
        row=owned_session(sid,user);require(row,5)
        return job_for(row,job_id)

    @app.get('/api/sessions/{sid}/pose-analysis/{job_id}/result')
    def pose_result(sid:int,job_id:str,user=Depends(current_user)):
        row=owned_session(sid,user);require(row,5)
        return result_for(row,job_id)

    @app.get('/api/sessions/{sid}/pose-analysis/{job_id}/frames/{frame}')
    def pose_frame(sid:int,job_id:str,frame:int,user=Depends(current_user)):
        row=owned_session(sid,user);require(row,5);job=job_for(row,job_id)
        if job['status']!='completed' or frame<0:raise HTTPException(404,'此影格尚未完成。')
        path=RUNTIME/'pose_analysis'/job['id']/f'frame-{frame}.jpg'
        if not path.is_file():raise HTTPException(404,'找不到分析影格。')
        return FileResponse(path,media_type='image/jpeg',headers={'Cache-Control':'private, no-store'})

    @app.get('/api/sessions/{sid}/resources/360/{clip_id}')
    def media(sid:int,clip_id:str,user=Depends(current_user)):
        row=owned_session(sid,user);require(row,4)
        clip=next((c for c in manifest()['clips'] if c['id']==clip_id),None)
        if not clip:raise HTTPException(404,'未知360影片。')
        path=ROOT/'data/video360'/clip['file']
        if not path.is_file():raise HTTPException(404,'影片尚未安裝。')
        return FileResponse(path,media_type='video/mp4')

    @app.post('/api/sessions/{sid}/frame-notes')
    def note(sid:int,body:FrameNote,user=Depends(current_user)):
        if user['role']!='student':raise HTTPException(403,'此紀錄由學員建立。')
        store=store_provider()
        with store.tx() as c:
            row=owned_session(sid,user);require(row,5)
            if row['status']!='active':raise HTTPException(409,'已完成的訓練證據不能改寫。')
            clip=next((x for x in manifest()['clips'] if x['id']==body.clip_id),None)
            if not clip or not math.isfinite(body.seconds) or body.seconds>clip['duration']:raise HTTPException(400,'影格時間或影片不符。')
            if len(body.observation.strip())<5:raise HTTPException(400,'請填寫實際觀察內容。')
            data={**body.model_dump(),'frame':round(body.seconds*clip['fps']),'created':time.time(),'kind':'learner_observation','review_status':'學員觀察，待教師覆核',
                  'media_snapshot':{k:clip[k] for k in ('id','title','fps','fps_rational','projection','source_sha256','proxy_sha256') if k in clip}}
            if body.analysis_id:
                job=job_for(row,body.analysis_id);analysis=result_for(row,body.analysis_id)
                frame=next((f for f in analysis['frames'] if f['frame']==body.analysis_frame),None)
                if job['clip_id']!=body.clip_id or not frame or round(body.seconds*clip['fps'])!=frame['frame'] or abs(body.yaw-analysis['view']['yaw'])>.01 or abs(body.pitch-analysis['view']['pitch'])>.01 or abs(body.fov-analysis['view'].get('fov',70))>.01:
                    raise HTTPException(400,'分析影格、視角與觀察時間不符；請重新選取分析結果。')
                data.update(seconds=frame['seconds'],frame=frame['frame'],yaw=analysis['view']['yaw'],pitch=analysis['view']['pitch'],fov=analysis['view'].get('fov',70))
                data['analysis_snapshot']={'id':job['id'],'session_id':sid,'version':analysis['version'],'result_sha256':job['result_sha256'],
                   'model':analysis['model'],'model_sha256':analysis['model_sha256'],'view':analysis['view'],'frame':frame,'limitation':analysis['limitation']}
                data['kind']='pose_supported_learner_observation'
            row['payload'].setdefault('frame_notes',[]).append(data)
            store.save(c,sid,row['payload']);store.event(c,user['id'],sid,'pose_supported_observation' if body.analysis_id else 'frame_observation',data)
        return data

    @app.post('/api/teacher/sessions/{sid}/frame-notes/{note_index}/reviews')
    def review_frame(sid:int,note_index:int,body:FrameReview,user=Depends(current_user)):
        if user['role']!='teacher':raise HTTPException(403,'逐格觀察回饋僅限教師。')
        if len(body.feedback.strip())<10:raise HTTPException(400,'請提供至少10字的具體回饋。')
        store=store_provider()
        with store.tx() as c:
            row=owned_session(sid,user)
            notes=row['payload'].get('frame_notes',[])
            if note_index<0 or note_index>=len(notes):raise HTTPException(404,'找不到此逐格觀察。')
            fingerprint=note_fingerprint(notes[note_index])
            history=row['payload'].setdefault('frame_note_reviews',[])
            previous=next((r for r in reversed(history) if r['note_index']==note_index),None)
            if (previous['id'] if previous else '')!=body.expected_review_id:
                raise HTTPException(409,'已有新的逐格回饋，請重新載入後再保存。')
            record={'id':secrets.token_hex(16),'note_index':note_index,'note_sha256':fingerprint,
                    'decision':body.decision,'feedback':body.feedback.strip(),'teacher_id':user['id'],
                    'teacher':user['display_name'],'created':time.time(),'kind':'formative_frame_feedback',
                    'affects_formal_grade':False}
            history.append(record);store.save(c,sid,row['payload'])
            store.event(c,user['id'],sid,'frame_observation_reviewed',record)
        return record
