"""Earned-level media access with authenticated, fixed-id resources and frame notes."""
import json
import math
import time
from fastapi import Depends, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from .config import ROOT
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
      'review_note':'360影片已核對球面投影與媒體格式；個別情境、職類視角及臨床解析仍待教師核定，不自動當作本輪病歷。'}

class FrameNote(BaseModel):
    clip_id:str
    seconds:float=Field(ge=0)
    yaw:float=Field(default=0,ge=-360,le=360)
    pitch:float=Field(default=0,ge=-85,le=85)
    observation:str=Field(min_length=5,max_length=2000)

def install_routes(app,owned_session,current_user,store_provider):
    def require(row,level):
        if earned(row)<level:raise HTTPException(403,f'本輪教材需累積學習 Level {level}；自評Level不會解鎖此教材。')

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
            data={**body.model_dump(),'frame':round(body.seconds*clip['fps']),'created':time.time(),'kind':'learner_observation','review_status':'學員觀察，待教師覆核'}
            row['payload'].setdefault('frame_notes',[]).append(data)
            store.save(c,sid,row['payload']);store.event(c,user['id'],sid,'frame_analysis',data)
        return data
