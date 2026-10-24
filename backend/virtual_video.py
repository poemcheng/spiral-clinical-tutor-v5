"""Local Chinese TTS + a photographic talking lecturer, encoded with HyperFrames.

Scripts quote a saved source snapshot; no generative clinical facts are inserted.
"""
import hashlib
import html
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import threading
import wave
import array
import math
from .config import ROOT, RUNTIME
from .characters import selected

RENDER_LOCK = threading.Lock()
SPEECH_LOCK = threading.Lock()
VOICE_VERSION = 'gender-strict-5.5.0'
RENDERER = 'Three.js skinned realistic human v2 / HyperFrames 0.8.185'


def audio_envelope(path):
    """50 ms RMS values from the actual narration, not a synthetic mouth clock."""
    with wave.open(str(path),'rb') as wav:
        if wav.getsampwidth()!=2:raise RuntimeError('語音格式須為 16-bit PCM')
        samples=array.array('h',wav.readframes(wav.getnframes()))
        chunk=max(1,int(wav.getframerate()*wav.getnchannels()*.05))
    return [round(min(1,math.sqrt(sum(x*x for x in samples[i:i+chunk])/len(samples[i:i+chunk]))/32768*7),3) for i in range(0,len(samples),chunk)]


def speech(text, target, gender='female'):
    target = Path(target);target.parent.mkdir(parents=True, exist_ok=True)
    if gender not in ('male','female'):raise ValueError('角色語音性別未指定。')
    engine=os.getenv('TTS_ENGINE','windows' if os.name=='nt' else 'piper')
    model_identity=''
    if engine=='piper':
        from .neural_speech import identity
        model_identity=identity(gender)[2]
    fingerprint=hashlib.sha256((VOICE_VERSION+'|'+engine+'|'+model_identity+'|'+gender+'|'+text).encode()).hexdigest()
    metadata=Path(str(target)+'.voice.json')
    with SPEECH_LOCK:
        try:voice=json.loads(metadata.read_text(encoding='utf-8-sig'))
        except (OSError,ValueError):voice={}
        if not target.exists() or voice.get('fingerprint')!=fingerprint or voice.get('gender')!=gender:
            if engine=='piper':
                from .neural_speech import synthesize
                voice=synthesize(text,target,gender)
            elif engine=='windows':
                text_path = target.with_suffix('.txt');text_path.write_text(text, encoding='utf-8')
                # PowerShell 7's System.Speech can enumerate installed OneCore voices (e.g. zh-TW Zhiwei).
                # Legacy Windows PowerShell often exposes only Hanhan Desktop. Never substitute its gender.
                shell=shutil.which('pwsh') or shutil.which('powershell.exe')
                if not shell:raise RuntimeError('未安裝 Windows 本機語音執行環境。')
                result = subprocess.run([shell,'-NoProfile','-ExecutionPolicy','Bypass','-File',str(ROOT/'tools/speak.ps1'),
                    '-TextFile',str(text_path),'-OutputFile',str(target),'-Gender',gender],capture_output=True,timeout=150,
                    creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
                if result.returncode or not target.exists():
                    target.unlink(missing_ok=True)
                    raise RuntimeError('本機中文語音合成失敗：'+result.stderr.decode('utf-8',errors='replace')[-500:])
                voice=json.loads(metadata.read_text(encoding='utf-8-sig'))
                if voice.get('gender')!=gender:raise RuntimeError('合成聲音性別與角色不符。')
            else:raise RuntimeError('未知語音引擎，請使用 windows 或 piper。')
            metadata.write_text(json.dumps({**voice,'fingerprint':fingerprint},ensure_ascii=False,indent=2),encoding='utf-8')
    with wave.open(str(target),'rb') as audio:
        return audio.getnframes()/audio.getframerate()


def concise(value, limit=96):
    value=re.sub(r'\s+','',value or '')
    # End at a source sentence boundary; never invent a replacement clinical claim.
    parts=re.split(r'(?<=[。；;])',value)
    result=''
    for part in parts:
        if result and len(result)+len(part)>limit:break
        result+=part
        if len(result)>=limit:break
    return result or value


def write_immersive_lesson(project,case,actor,segments,duration):
    """Interactive companion uses the same 3D renderer and actual audio envelope."""
    data=json.dumps(segments,ensure_ascii=False).replace('<','\\u003c')
    face=json.dumps(actor.get('face',{}))
    title=html.escape(case['title']);name=html.escape(actor['name'])
    content=f'''<!doctype html><html lang="zh-Hant"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{title} · 3D教案</title>
<style>*{{box-sizing:border-box}}body{{margin:0;background:#0d2531;color:#eef7f6;font:16px/1.6 system-ui,sans-serif}}header{{padding:12px 24px;background:#153746}}h1{{font-size:21px;margin:0}}main{{display:grid;grid-template-columns:minmax(0,1fr) 310px;min-height:calc(100vh - 85px)}}#stage{{position:relative;min-height:440px}}canvas{{display:block;width:100%;height:100%;position:absolute;inset:0;touch-action:none}}aside{{padding:24px;background:#f5f9f7;color:#193c49}}button{{background:#1c7276;color:white;border:0;padding:12px 18px;border-radius:8px;cursor:pointer;margin:4px}}audio{{width:100%;margin:12px 0}}.hint{{font-size:13px;color:#b4d4d9}}#stage:fullscreen{{width:100vw;height:100vh}}@media(max-width:700px){{main{{grid-template-columns:1fr}}#stage{{height:55vh}}}}</style>
<header><h1>{title}</h1><span>{name} · three.js沉浸式教案</span></header><main><div id="stage"><canvas id="scene" aria-label="可拖曳環顧的3D診間"></canvas></div><aside><h2 id="section"></h2><p id="script"></p><button id="prev">上一段</button><button id="next">下一段</button><button id="play">播放講師語音</button><audio id="speech" controls></audio><button id="full">全螢幕診間</button><p id="status" role="status">人物載入中…</p><p>拖曳環顧診間，滾輪調整距離。語音嘴形依實際音訊連動。</p><small>角色具有立體人體網格、蒙皮骨架與表情變形。依本輪教案快照生成，待教師審核。</small></aside></main><script src="lecturer.js"></script><script>
const parts={data},rig=ClinicalLecturer.lecturerScene(document.querySelector('#scene'),{{modelUrl:'actor-model.glb',interactive:true}}),audio=document.querySelector('#speech');let index=0,disposed=false;
function select(i){{audio.pause();index=Math.max(0,Math.min(parts.length-1,i));audio.src='voice-'+index+'.wav';document.querySelector('#section').textContent=parts[index].title;document.querySelector('#script').textContent=parts[index].text;}}select(0);
document.querySelector('#play').onclick=()=>{{if(audio.paused)audio.play().catch(e=>document.querySelector('#status').textContent=e.message);else audio.pause();}};audio.onplay=()=>document.querySelector('#play').textContent='暫停講師語音';audio.onpause=()=>document.querySelector('#play').textContent='播放講師語音';
document.querySelector('#prev').onclick=()=>select(index-1);document.querySelector('#next').onclick=()=>select(index+1);audio.onended=()=>{{if(index<parts.length-1){{select(index+1);audio.play().catch(()=>{{}});}}}};
document.querySelector('#full').onclick=()=>document.querySelector('#stage').requestFullscreen().catch(()=>{{document.querySelector('#status').textContent='此瀏覽器未提供全螢幕。';}});
rig.ready.then(()=>document.querySelector('#status').textContent='3D診間已就緒，按播放聆聽講師。').catch(e=>document.querySelector('#status').textContent=e.message);
function draw(){{if(disposed)return;const t=audio.currentTime||0,a=audio.paused?0:(parts[index].envelope[Math.floor(t/.05)]||0);rig.renderAt(parts[index].start+t,a);requestAnimationFrame(draw);}}draw();window.addEventListener('pagehide',()=>{{disposed=true;audio.pause();rig.dispose();}});
</script></html>'''
    (project/'immersive.html').write_text(content,encoding='utf-8')


def build_project(case, row, module, *, lecture_sections=None):
    actor=selected(row,'lecturer')
    variant=case.get('variant',{})
    sections=[('個案背景',concise(case['patient'])),
        ('本職類任務',concise(variant.get('role_task') or '；'.join(case['goals'][:2]))),
        (f"Level {row['level']} 練習重點",concise(variant.get('learner_task') or case['pre_knowledge'][0]))]
    if module==1:sections[1:]=[('弱項補強',concise('；'.join(variant.get('supplement_tasks') or case['goals'][:2]))),('溝通練習','先確認病人的疑慮，再用回覆示教確認理解，並記錄需要教師協助的資訊。')]
    if module==2:sections[1:]=[('團隊整合',concise(variant.get('role_task') or case['goals'][0])),('交接與追蹤','以SBAR整理目前狀況、背景資料、本職類評估，以及具體協助需求與追蹤計畫。')]
    if lecture_sections is not None:sections=lecture_sections
    key=hashlib.sha256(json.dumps([case,row['profession'],row['level'],module,actor,RENDERER,lecture_sections],ensure_ascii=False,sort_keys=True).encode()).hexdigest()[:20]
    project=RUNTIME/'virtual_lessons'/key;project.mkdir(parents=True,exist_ok=True)
    segments=[];start=0
    for i,(title,text) in enumerate(sections):
        duration=speech(text,project/f'voice-{i}.wav',actor['gender'])+.6
        segments.append({'title':title,'text':text,'start':start,'duration':duration,'envelope':audio_envelope(project/f'voice-{i}.wav')});start+=duration
    shutil.copyfile(ROOT/'frontend/vendor/lecturer.bundle.js',project/'lecturer.js')
    shutil.copyfile(ROOT/'frontend/vendor/gsap.min.js',project/'gsap.min.js')
    shutil.copyfile(ROOT/'data/characters'/actor['realistic_model_file'],project/'actor-model.glb')
    shutil.copyfile(ROOT/'data/characters'/actor['card_file'],project/'role-card.png')
    font=Path('C:/Windows/Fonts/msjh.ttc')
    if font.exists():shutil.copyfile(font,project/'font.ttc')
    audio=''.join(f'<audio id="voice-{i}" class="clip" src="voice-{i}.wav" data-start="{s["start"]:.3f}" data-duration="{s["duration"]-.6:.3f}" data-track-index="2" data-volume="1"></audio>' for i,s in enumerate(segments))
    panels=''.join(f'<section id="panel-{i}" class="panel clip" data-start="{s["start"]:.3f}" data-duration="{s["duration"]:.3f}" data-track-index="1"><div class="number">0{i+1} / 03</div><h2>{html.escape(s["title"])}</h2><p>{html.escape(s["text"])}</p></section>' for i,s in enumerate(segments))
    segment_json=json.dumps(segments,ensure_ascii=False).replace('<','\\u003c')
    content=f'''<!doctype html><html lang="zh-Hant"><head><meta charset="utf-8"><title>虛擬講師｜{html.escape(case['title'])}</title><style>
@font-face{{font-family:Lesson;src:url('font.ttc')}}*{{box-sizing:border-box}}body{{margin:0;background:#f5f8fd;color:#183251;font-family:Lesson,sans-serif}}#main{{width:960px;height:540px;position:relative;overflow:hidden}}header{{position:absolute;top:28px;left:40px;right:40px;border-bottom:3px solid #174e9a;padding-bottom:15px;font-size:22px;font-weight:700}}header span{{float:right;color:#a42d43;font-size:16px}}canvas{{position:absolute;left:0;top:0;width:960px;height:540px}}header{{z-index:2;background:#ffffffed;border-radius:8px;padding:10px 14px;top:14px;left:20px;right:20px;font-size:20px}}footer{{z-index:2;background:#fffffff0;border-radius:6px;padding:8px;font-size:12px}}.panel{{position:absolute;left:650px;top:100px;width:285px;height:350px;background:#fffffff0;padding:20px;border-radius:14px;box-shadow:0 8px 30px #18325120}}.number{{font-size:18px;color:#a42d43;letter-spacing:4px}}h2{{font-size:25px;margin:14px 0 16px}}p{{font-size:19px;line-height:1.65;margin:0}}footer{{position:absolute;bottom:18px;left:40px;right:40px;font-size:14px;color:#526986;border-top:1px solid #bfd0e6;padding-top:12px}}.progress{{position:absolute;bottom:0;left:0;height:5px;background:#b53a51;transform-origin:left;width:960px}}
</style></head><body><main id="main" data-composition-id="main" data-width="960" data-height="540" data-duration="{start:.3f}"><header>{html.escape(case['title'])}<span>虛擬講師 · 教學試辦</span></header><canvas id="lecturer" width="415" height="425"></canvas>{panels}{audio}<footer>來源：上傳教案 · {html.escape(row['profession'])} / Level {row['level']}　｜　合成角色與中文語音，待教師審核</footer><div id="progress" class="progress"></div></main><script src="lecturer.js"></script><script src="gsap.min.js"></script><script>
const rig=ClinicalLecturer.lecturerScene(document.getElementById('lecturer'),{{modelUrl:'actor-model.glb'}});
const segments={segment_json};
const timeline=gsap.timeline({{paused:true}});segments.forEach((s,i)=>{{timeline.from('#panel-'+i+' h2',{{x:24,opacity:0,duration:.45}},s.start+.1);timeline.from('#panel-'+i+' p',{{y:16,opacity:0,duration:.5}},s.start+.25);}});window.__timelines=window.__timelines||{{}};window.__timelines['main']=timeline;
function renderAt(t){{const s=segments.find(s=>t>=s.start&&t<s.start+s.duration-.6);const a=s?(s.envelope[Math.floor((t-s.start)/.05)]||0):0;rig.renderAt(t,a);document.getElementById('progress').style.transform='scaleX('+Math.min(1,t/{start})+')';window.__hfPortraitTime=t;}}
window.addEventListener('hf-seek',event=>renderAt(event.detail.time));window.__hf=window.__hf||{{}};window.__hf.buildReady=rig.ready.then(()=>renderAt(0));
</script></body></html>'''
    content=content.replace('虛擬講師 · 教學試辦',html.escape(actor['name'])+' · 擬真教學試辦')
    (project/'index.html').write_text(content,encoding='utf-8')
    write_immersive_lesson(project,case,actor,segments,start)
    (project/'hyperframes.json').write_text((ROOT/'data/hyperframes.json').read_text(),encoding='utf-8')
    manifest={'source':'source_bound_virtual_lecturer','source_file':case.get('source_file'), 'source_sha256':case.get('source_sha256'),
        'case_hash':row.get('payload',{}).get('case_hash'),'actor':actor,'renderer':RENDERER,'voice':'Windows zh-TW TTS '+actor['gender'],
        'has_audio':True,'duration':round(start,2),'segments':segments,'review_status':'待教師審核','key':key}
    (project/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
    return project,manifest


def render(case,row,module):
    with RENDER_LOCK:
        project,manifest=build_project(case,row,module)
        output=project/'training_video.mp4'
        if not output.exists():
            cli=shutil.which('npx.cmd') or shutil.which('npx')
            if not cli:raise RuntimeError('未安裝 Node.js/npx，無法輸出虛擬人影片。')
            args=[cli,'--yes','hyperframes@0.8.185','render','--quality','looks','--fps','24','--workers','1','--output',str(output)]
            with (project/'render.log').open('w',encoding='utf-8') as log:
                environment=os.environ.copy()
                local_bins=list((ROOT/'tools/ffmpeg').glob('*/bin'))
                if local_bins:environment['PATH']=str(local_bins[0])+os.pathsep+environment.get('PATH','')
                result=subprocess.run(args,cwd=project,env=environment,stdout=log,stderr=subprocess.STDOUT,timeout=1200,
                    creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
            if result.returncode or not output.exists():
                raise RuntimeError('虛擬人影片輸出失敗，請檢查 runtime/virtual_lessons 下的 render.log。')
        return output,manifest
