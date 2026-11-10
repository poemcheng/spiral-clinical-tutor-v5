"""Local teaching server. Only simulated synthetic data by default."""
from __future__ import annotations
import os
from pathlib import Path
from typing import Literal
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from engine import PATIENT, synthetic_frame, answer_question, analyze_case, make_sbar, grade_sbar

BASE=Path(__file__).resolve().parent
app=FastAPI(title='CareLab v2 | Synthetic Multimodal Care', version='2.0.0')
app.mount('/static', StaticFiles(directory=BASE/'static'), name='static')

class ChatInput(BaseModel):
    question: str=Field(min_length=1,max_length=2000)
    provider: Literal['demo','ollama','gemini']='demo'
    model: str | None=None
class Scenario(BaseModel):
    scenario: Literal['baseline','missing','discordant']='baseline'
class GradeInput(BaseModel):
    fields: dict[str,str]
@app.get('/')
def index(): return FileResponse(BASE/'static'/'index.html')
@app.get('/api/health')
def health(): return {'status':'ok','synthetic_only':True,'providers':['demo','ollama' if os.getenv('OLLAMA_URL') else 'demo','gemini' if os.getenv('GEMINI_API_KEY') else 'demo']}
@app.get('/api/patient')
def patient(): return PATIENT
@app.get('/api/frame')
def frame(t:float=0, scenario:Literal['baseline','missing','discordant']='baseline'):
    if not 0<=t<=3600: raise HTTPException(400,'t must be in range')
    return synthetic_frame(t,scenario)
@app.post('/api/analyze')
def analyze(data:Scenario): return analyze_case(data.scenario)
@app.post('/api/sbar')
def sbar(data:Scenario): return make_sbar(scenario=data.scenario)
@app.post('/api/grade')
def grade(data:GradeInput): return grade_sbar(data.fields)
SYSTEM='你是虛構肌少症照護教學個案林阿姨的模擬問答助手。只描述提供的合成案例，不可診斷、治療或推論未量測事實。回答簡短、繁體中文，強調需人工覆核。'
@app.post('/api/chat')
async def chat(data:ChatInput):
    if data.provider=='demo': return answer_question(data.question)
    try:
        import httpx
        if data.provider=='ollama':
            url=os.getenv('OLLAMA_URL')
            if not url: raise HTTPException(503,'請在伺服器環境設定 OLLAMA_URL 才能使用本機模型')
            model=data.model or os.getenv('OLLAMA_MODEL','gemma3:4b')
            async with httpx.AsyncClient(timeout=90) as client:
                r=await client.post(url.rstrip('/')+'/api/chat',json={'model':model,'stream':False,'messages':[{'role':'system','content':SYSTEM},{'role':'user','content':data.question}]})
                r.raise_for_status(); reply=r.json().get('message',{}).get('content','')
            return {'reply':reply,'evidence':'LLM generated — not independently verified','mode':'ollama'}
        key=os.getenv('GEMINI_API_KEY')
        if not key: raise HTTPException(503,'未設定伺服器端 GEMINI_API_KEY')
        model=data.model or os.getenv('GEMINI_MODEL','gemini-2.5-flash')
        if '/' in model or '?' in model: raise HTTPException(400,'invalid model name')
        async with httpx.AsyncClient(timeout=90) as client:
            r=await client.post(f'https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent',headers={'x-goog-api-key':key},json={'systemInstruction':{'parts':[{'text':SYSTEM}]},'contents':[{'parts':[{'text':data.question}]}]})
            r.raise_for_status(); obj=r.json()
        reply=''.join(p.get('text','') for c in obj.get('candidates',[]) for p in c.get('content',{}).get('parts',[]))
        return {'reply':reply or '模型未提供文字回答','evidence':'Gemini generated — not independently verified','mode':'gemini'}
    except HTTPException: raise
    except Exception as e: raise HTTPException(502,'模型連線失敗：'+type(e).__name__)

# Gradio remains optional; the standalone web interface is sufficient for course delivery.
try:
    if os.environ.get('ENABLE_GRADIO')=='1':
        import gradio as gr
        with gr.Blocks(title='CareLab 多模態資料檢核') as demo:
            gr.Markdown('## 合成多模態資料實驗室｜資料與交班核對（非臨床用途）')
            with gr.Row():
                scenario=gr.Dropdown(['baseline','missing','discordant'],value='baseline',label='情境')
                output=gr.JSON(label='來源與缺失檢核')
            btn=gr.Button('分析案例')
            btn.click(analyze_case,inputs=[scenario],outputs=[output])
            gr.Markdown('本頁只展示合成資料；進階 3D 與語音請使用 [主工作台](/)。')
        app=gr.mount_gradio_app(app,demo,path='/gradio')
except ImportError:
    pass