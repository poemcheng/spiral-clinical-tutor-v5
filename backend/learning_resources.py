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
from . import pose_analysis,teaching_media,learning_curriculum,epa_library
from .competencies import profile
from . import characters,team_knowledge

def manifest():
    return teaching_media.manifest()

def earned(row):
    return row['payload']['adaptive_plan'].get('learning_level',1)

def resources(row,case):
    level=earned(row);p=profile(row['profession']);policy=row['payload'].get('interaction_policy',characters.pairing(row['profession']))
    clips=[{'id':c['id'],'title':c['title'],'duration':c['duration'],'fps':c['fps'],'status':c['status'],
      'projection':c.get('projection','equirectangular'),'available':teaching_media.path_for(c).is_file(),
      'steps':teaching_media.steps_for(c) if level>=3 else [],
      **({'url':f"/api/sessions/{row['id']}/resources/video/{c['id']}"} if level>=(3 if c.get('projection')=='flat' else 4) else {})} for c in manifest()['clips'] if teaching_media.applies(c,row,case)]
    return {'learning_level':level,'self_level':row['level'],'profession':p,'team_target':policy['label'],
      'team_knowledge':team_knowledge.for_case(case,row['profession'],level,row['id']),
      'clips':[c for c in clips if c['projection']!='flat'] if level>=4 else [],
      'media':[c for c in clips if 'url' in c],
      'lesson_levels':learning_curriculum.levels(case,row['profession'],level,clips),
      'lesson_notes':row['payload'].get('learning_notes',[]),
      'frame_notes':row['payload'].get('frame_notes',[]) if level>=4 else [],
      'frame_reviews':row['payload'].get('frame_note_reviews',[]) if level>=4 else [],
      'pose_service':pose_analysis.availability() if level>=4 else None,
      'pose_jobs':row['payload'].get('pose_jobs',[]) if level>=4 else [],
      'epa_library':epa_library.available(row,case),
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
    epa_analysis_id:str=Field(default='',pattern=r'^(?:[a-f0-9]{32})?$')


class PoseRequest(BaseModel):
    clip_id:str
    start:float=Field(ge=0,allow_inf_nan=False)
    end:float=Field(gt=0,allow_inf_nan=False)
    yaw:float=Field(default=0,ge=-360,le=360,allow_inf_nan=False)
    pitch:float=Field(default=0,ge=-85,le=85,allow_inf_nan=False)
    fov:float=Field(default=70,ge=35,le=95,allow_inf_nan=False)
    roi:list[float]|None=Field(default=None,min_length=4,max_length=4)


class FrameReview(BaseModel):
    decision:Literal['reviewed','needs_revision']
    feedback:str=Field(min_length=10,max_length=2000)
    expected_review_id:str=Field(default='',max_length=32)

class LearningNote(BaseModel):
    lesson_id:str=Field(min_length=1,max_length=100)
    reflection:str=Field(min_length=10,max_length=4000)


def note_fingerprint(note):
    return hashlib.sha256(json.dumps(note,sort_keys=True,ensure_ascii=False,separators=(',',':')).encode()).hexdigest()

def install_routes(app,owned_session,current_user,store_provider):
    epa_library.install_routes(app,owned_session,current_user)
    def require(row,level):
        if earned(row)<level:raise HTTPException(403,f'本輪教材需累積學習 Level {level}；自評Level不會解鎖此教材。')

    @app.get('/api/sessions/{sid}/resources/team-guide')
    def team_guide(sid:int,user=Depends(current_user)):
        row=owned_session(sid,user);require(row,2)
        if not team_knowledge.for_case(row['payload'].get('case_snapshot',{}),row['profession'],earned(row),sid):
            raise HTTPException(404,'本教案未提供肌少症團隊指南。')
        path=ROOT/'data/sources/跨專業肌少症整合照護指南.png'
        if not path.is_file():raise HTTPException(404,'團隊指南原圖尚未安裝，仍可閱讀已解鎖的團隊知識。')
        return FileResponse(path,media_type='image/png')

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
        row=owned_session(sid,user);require(row,4)
        if row['status']!='active' or row['step']<3:raise HTTPException(409,'請在進行中的情境學習或角色互動分析影片。')
        clip=next((x for x in manifest()['clips'] if x['id']==body.clip_id),None)
        if not clip or not teaching_media.applies(clip,row) or not teaching_media.path_for(clip).is_file():raise HTTPException(404,'此情境影片尚未安裝或不適用。')
        if body.end<=body.start or body.end>clip['duration']+.001 or body.end-body.start>1800:raise HTTPException(400,'分析區間需在影片範圍內，單次最長1800秒。')
        if body.roi:
            x,y,w,h=body.roi
            if not all(math.isfinite(v) for v in body.roi) or x<0 or y<0 or w<.05 or h<.05 or x+w>1.00001 or y+h>1.00001:raise HTTPException(400,'人物範圍需在畫面內，寬高至少5%。')
        if not pose_analysis.availability()['ready']:raise HTTPException(503,'骨架模型未就緒；請執行 python tools/setup_pose.py 並安裝 requirements-pose.txt。')
        if not pose_analysis.LOCK.acquire(blocking=False):raise HTTPException(429,'另一段影片分析中，請待完成後再試。')
        store=store_provider();job_id=secrets.token_hex(16);params=body.model_dump(exclude={'clip_id'})
        if clip.get('projection')=='flat':params.update(yaw=0,pitch=0,fov=70)
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
        row=owned_session(sid,user);require(row,4)
        return job_for(row,job_id)

    @app.get('/api/sessions/{sid}/pose-analysis/{job_id}/result')
    def pose_result(sid:int,job_id:str,user=Depends(current_user)):
        row=owned_session(sid,user);require(row,4)
        return result_for(row,job_id)

    @app.get('/api/sessions/{sid}/pose-analysis/{job_id}/frames/{frame}')
    def pose_frame(sid:int,job_id:str,frame:int,overlay:bool=True,user=Depends(current_user)):
        row=owned_session(sid,user);require(row,4);job=job_for(row,job_id)
        if job['status']!='completed' or frame<0:raise HTTPException(404,'此影格尚未完成。')
        path=RUNTIME/'pose_analysis'/job['id']/f"{'' if overlay else 'raw-'}frame-{frame}.jpg"
        if not path.is_file():raise HTTPException(404,'找不到分析影格。')
        return FileResponse(path,media_type='image/jpeg',headers={'Cache-Control':'private, no-store'})

    @app.get('/api/sessions/{sid}/resources/video/{clip_id}')
    @app.get('/api/sessions/{sid}/resources/360/{clip_id}')
    def media(sid:int,clip_id:str,user=Depends(current_user)):
        row=owned_session(sid,user)
        clip=next((c for c in manifest()['clips'] if c['id']==clip_id),None)
        if not clip or not teaching_media.applies(clip,row):raise HTTPException(404,'此情境未提供該影片。')
        require(row,3 if clip.get('projection')=='flat' else 4)
        path=teaching_media.path_for(clip)
        if not path.is_file():raise HTTPException(404,'影片尚未安裝。')
        return FileResponse(path,media_type='video/mp4')

    @app.post('/api/sessions/{sid}/frame-notes')
    def note(sid:int,body:FrameNote,user=Depends(current_user)):
        if user['role']!='student':raise HTTPException(403,'此紀錄由學員建立。')
        store=store_provider()
        with store.tx() as c:
            row=owned_session(sid,user);require(row,4)
            if row['status']!='active':raise HTTPException(409,'已完成的訓練證據不能改寫。')
            clip=next((x for x in manifest()['clips'] if x['id']==body.clip_id),None)
            if not clip or not teaching_media.applies(clip,row) or not math.isfinite(body.seconds) or body.seconds>clip['duration']:raise HTTPException(400,'影格時間、影片或主題不符。')
            if len(body.observation.strip())<5:raise HTTPException(400,'請填寫實際觀察內容。')
            if body.analysis_id and body.epa_analysis_id:raise HTTPException(400,'請選擇一種影格證據來源。')
            data={**body.model_dump(),'frame':round(body.seconds*clip['fps']),'created':time.time(),'kind':'learner_observation','review_status':'學員觀察，待教師覆核',
                  'media_snapshot':{k:clip[k] for k in ('id','title','fps','fps_rational','projection','source_sha256','proxy_sha256') if k in clip}}
            data['teaching_step']=teaching_media.step_at(clip,body.seconds)
            if body.analysis_id:
                job=job_for(row,body.analysis_id);analysis=result_for(row,body.analysis_id)
                frame=next((f for f in analysis['frames'] if f['frame']==body.analysis_frame),None)
                if job['clip_id']!=body.clip_id or not frame or round(body.seconds*clip['fps'])!=frame['frame'] or abs(body.yaw-analysis['view']['yaw'])>.01 or abs(body.pitch-analysis['view']['pitch'])>.01 or abs(body.fov-analysis['view'].get('fov',70))>.01:
                    raise HTTPException(400,'分析影格、視角與觀察時間不符；請重新選取分析結果。')
                data.update(seconds=frame['seconds'],frame=frame['frame'],yaw=analysis['view']['yaw'],pitch=analysis['view']['pitch'],fov=analysis['view'].get('fov',70))
                data['analysis_snapshot']={'id':job['id'],'session_id':sid,'version':analysis['version'],'result_sha256':job['result_sha256'],
                   'model':analysis['model'],'model_sha256':analysis['model_sha256'],'view':analysis['view'],'frame':frame,'limitation':analysis['limitation'],
                   'teaching_step':next((s for s in analysis.get('teaching_steps',[]) if s['id']==frame.get('teaching_step_id')),None)}
                data['kind']='pose_supported_learner_observation'
            if body.epa_analysis_id:
                media,item,index,folder=epa_library.analysis(body.clip_id)
                if body.epa_analysis_id!=item['id'] or body.analysis_frame is None:raise HTTPException(400,'EPA分析版本或影格不符。')
                frame=epa_library.frame(body.clip_id,body.analysis_frame);view=item['view']
                if round(body.seconds*clip['fps'])!=frame['frame'] or abs(body.yaw-view['yaw'])>.01 or abs(body.pitch-view['pitch'])>.01 or abs(body.fov-view.get('fov',70))>.01:raise HTTPException(400,'EPA影格、時間或視角不符；請重新選取。')
                data.update(seconds=frame['seconds'],frame=frame['frame'],yaw=view['yaw'],pitch=view['pitch'],fov=view.get('fov',70))
                data['analysis_snapshot']={'id':item['id'],'session_id':sid,'origin':'epa_library','clip_id':body.clip_id,'version':epa_library.VERSION,'result_sha256':index['result_sha256'],'model':index['model'],'model_sha256':item['model_sha256'],'view':view,'frame':frame,'limitation':index['limitation'],'teaching_step':teaching_media.step_at(clip,frame['seconds']),'epa_annotation':frame.get('annotation'),'epa_reference_keyframe':frame.get('reference_keyframe'),'annotation_sha256':frame['annotation_sha256']}
                data['kind']='epa_annotated_learner_observation'
            row['payload'].setdefault('frame_notes',[]).append(data)
            store.save(c,sid,row['payload']);store.event(c,user['id'],sid,'pose_supported_observation' if body.analysis_id else 'frame_observation',data)
        return data

    @app.post('/api/sessions/{sid}/learning-notes')
    def save_learning_note(sid:int,body:LearningNote,user=Depends(current_user)):
        if user['role']!='student':raise HTTPException(403,'學習紀錄由學員建立。')
        if len(body.reflection.strip())<10:raise HTTPException(400,'請填寫至少10字的學習判讀。')
        from .server import case_for
        store=store_provider()
        with store.tx() as c:
            row=owned_session(sid,user)
            if row['status']!='active' or row['step']<3:raise HTTPException(409,'請在進行中的教材學習階段保存。')
            course=case_for(row)
            lesson=next((lesson for level in learning_curriculum.levels(course,row['profession'],earned(row),manifest()['clips']) if level['unlocked'] for lesson in level.get('lessons',[]) if lesson['id']==body.lesson_id),None)
            if not lesson:raise HTTPException(403,'此教案未解鎖或不屬於本輪。')
            item={'id':secrets.token_hex(16),'lesson_id':body.lesson_id,'reflection':body.reflection.strip(),'created':time.time(),
                  'lesson_snapshot':lesson,'curriculum_version':learning_curriculum.VERSION,'affects_formal_grade':False}
            row['payload'].setdefault('learning_notes',[]).append(item);store.save(c,sid,row['payload'])
            store.event(c,user['id'],sid,'learning_lesson_reflection',item)
        return item

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
