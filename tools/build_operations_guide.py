"""Build the local, private-footage operation tutorial from genuine UI captures.

This deliberately creates a narrated screenshot walkthrough, not a screen recording.
Never put its captures or output in the public asset pack.
"""
from pathlib import Path
import hashlib
import html
import json
import re
import shutil
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from backend.virtual_video import speech

ROOT=Path(__file__).resolve().parents[1]
PROJECT=ROOT/'runtime/guide-v5.3.1'
SOURCE=ROOT/'runtime/verification-5.3.1/guide'


def build_export():
    """Expand scene templates for CLI 0.8.185's standalone render path.

    Keep index.html and its editable scenes as the authoring source. The CLI's
    export loader currently drops styles/scripts inside these templates even
    though Studio loads them. A deterministic standalone document avoids that
    discrepancy, without changing screenshots, timing, narration or geometry.
    """
    root=(PROJECT/'index.html').read_text(encoding='utf-8')
    ledger=json.loads((PROJECT/'capture-ledger.json').read_text(encoding='utf-8'))
    animations=[]
    for scene in ledger['scenes']:
        ident=scene['scene']
        source=(PROJECT/'compositions'/f'{ident}.html').read_text(encoding='utf-8')
        css=re.search(r'<style>(.*?)</style>',source,re.S).group(1)
        markup=re.search(r'</style>(.*?)<script>',source,re.S).group(1)
        markup=re.sub(r' data-composition-id="[^"]+"','',markup)
        # The outer host owns timing; scene-root durations would otherwise be
        # interpreted on the flattened global clock and hide later scenes.
        markup=re.sub(r' data-(?:duration|width|height)="[^"]+"','',markup,count=3)
        markup=markup.replace(f'id="{ident}"',f'id="{ident}-content"',1)
        css=css.replace(f'#{ident}',f'#{ident}-content')
        pattern=rf'<div id="{ident}" class="clip"[^>]*></div>'
        host=re.search(pattern,root).group(0)
        host=re.sub(r' data-composition-(?:id|src)="[^"]+"','',host)
        root=re.sub(pattern,lambda _: '<style>'+css+'</style>'+host[:-6]+markup+'</div>',root)
        animations.append(f"tl.fromTo('#{ident}-content .guide-aside',{{x:18,opacity:.6}},{{x:0,opacity:1,duration:.35,ease:'power3.out'}},{scene['start']+.08:.3f});")
    source=(PROJECT/'compositions/captions.html').read_text(encoding='utf-8')
    css=re.search(r'<style>(.*?)</style>',source,re.S).group(1)
    markup=re.search(r'</style>(.*?)<script>',source,re.S).group(1)
    markup=re.sub(r' data-composition-id="[^"]+"','',markup)
    markup=markup.replace('id="captions"','id="captions-content"',1)
    pattern=r'<div id="captions" class="clip"[^>]*></div>'
    host=re.search(pattern,root).group(0)
    host=re.sub(r' data-composition-(?:id|src)="[^"]+"','',host)
    root=re.sub(pattern,lambda _:'<style>'+css.replace('#captions','#captions-content')+'</style>'+host[:-6]+markup+'</div>',root)
    root=root.replace("window.__timelines['main']=tl;",''.join(animations)+"window.__timelines['main']=tl;")
    root=root.replace('<script src="assets/gsap.min.js"></script>','')
    root=root.replace('<meta charset="utf-8">','<meta charset="utf-8"><script src="assets/gsap.min.js"></script>')
    (PROJECT/'render.html').write_text(root,encoding='utf-8')
    export=PROJECT/'export'
    export.mkdir(exist_ok=True)
    (export/'index.html').write_text(root,encoding='utf-8')
    shutil.copytree(PROJECT/'assets',export/'assets',dirs_exist_ok=True)
    # A short first-scene export makes layout parity review inexpensive.
    smoke=re.sub(r'(data-composition-id="main"[^>]*data-duration=")[^"]+',r'\g<1>2',root,count=1)
    (PROJECT/'export-smoke.html').write_text(smoke,encoding='utf-8')
SHOTS=[
('01-login.png','登入與角色分工','使用學員帳號開始','學員分析 → 教師回饋 → 學員查看','這份操作導覽使用五點三點一修正版的實際畫面，示範學員逐格分析、教師回饋，以及學員查看回饋的完整流程。',8,None),
('02-professions.png','學員｜選擇專業','選擇職種與情境','本例使用營養師與肌少症教材','學員登入後，選擇營養師及肌少症情境，完成本次登入的自評，再接續原來的訓練。',7,None),
('04-levels.png','學員｜核對兩個Level','難度與教材分開','範例：自評2 · 教材5','本例學員自評為第二級，教材已解鎖第五級。自評決定互動難度；教材等級決定可以閱讀和分析的內容，兩者獨立。',10,None),
('05-360-view.png','學員｜選擇影片視角','先看見分析對象','選擇第二部360影片，向左調整視角','在情境學習頁選擇上傳的第二部三百六十度影片。拖曳或按方向按鈕，把人物轉到清楚可見的位置。',9,None),
('06-range.png','學員｜指定分析區間','固定視角再分析','本例選擇5至7秒','填寫開始與結束秒數，再按開始逐格骨架分析。本例分析第五秒到第七秒；也可以選取完整影片，單次最長三百秒。',10,None),
('07-analysis-running.png','學員｜實際骨架計算','等待本機分析完成','每一影格都會解碼與計算','分析會把球面影片的選定視角轉成平面，再逐格計算骨架。進度列顯示已處理影格，未偵測到人體時會明示。',8,None),
('09-actions-meaning.png','學員｜檢視骨架','逐格核對可見關節','綠線與黃點是模型估計','分析完成後，使用上一格、下一格或進度滑桿檢視骨架。本例有六十格，其中部分影格因遮擋沒有可靠骨架。',10,None),
('10-motion-evidence.png','學員｜判讀動作意義','觀測與意圖要分開','投影角度 · 動作片段 · 替代解釋','先看可見的關節角度與動作片段，再檢視可能意圖、替代解釋及待核對資訊。模型不能只憑抬手就判定求助。',10,'focus'),
('11-learner-note.png','學員｜保存判讀','寫出依據與不確定性','本例：持板可能在示意拍攝開始','在本格觀察寫下自己的判斷與影像依據，並保留其他解釋。本例將持板動作視為可能在示意拍攝，仍須核對現場語音。',10,'focus'),
('12-note-saved.png','學員｜確認送出','保存給教師覆核','影格、視角、模型與來源版本一起保存','按保存時間、視角與觀察。已選取的骨架、動作特徵與意圖假設，會連同學員原始判讀保存，供教師覆核。',9,'focus'),
('13-teacher-dashboard.png','教師｜開啟訓練紀錄','找到同一筆學員訓練','教師工作台 → 監看／覆核','教師以自己的帳號登入工作台，找到學員的同一筆訓練，按監看與覆核，查看學員原始觀察及分析證據。',9,None),
('17-teacher-context-review.png','教師｜核對前後脈絡','不能只看單一影格','逐格骨架＋原始360畫面與現場語音','教師可以開啟完整分析，逐格對照骨架，再播放原始影片的前後畫面與現場語音。超出分析區間時，系統不會推算未分析的骨架。',11,None),
('14-teacher-feedback-draft.png','教師｜提供具體回饋','指出還缺哪些證據','選擇已檢視或建議補充，填寫理由','回到訓練紀錄，選擇回饋狀態並填寫具體建議。本例要求補上前後持板動作與現場口語，說明判斷依據。',9,None),
('15-teacher-feedback-saved.png','教師｜保存回饋','回饋另存，保留原作','形成性回饋不改寫正式分數','按保存逐格觀察回饋。教師意見會另行留下歷程，學員原始觀察不會被覆寫，這項回饋也不會自動改變正式分數。',10,'focus'),
('16-student-reads-feedback.png','學員｜查看教師意見','回到教材檢視回饋','看到教師姓名、時間與具體建議','學員重新開啟影片與情境學習，就能在原觀察下查看教師姓名、回饋時間與具體建議。學員無法編輯教師回饋。',10,'focus'),
('18-3d-interaction.png','3D角色｜互動難度','自評Level改變互動壓力','Level 1友善支持；Level 5追問依據與權威衝突','虛擬人使用真正立體骨架，支援環繞、嘴形及小幅手勢。自評第一級提供友善支持，第五級則面對較難合作的病患，或要求專業依據的強勢同事。',13,None),
('19-voice-male-passed.png','聲音配對｜男角色','男角色使用中文男聲','Microsoft Zhiwei · 以下播放男聲樣本','您好，請先說明您已確認的資料，以及需要我協助的部分。',8,'male'),
('20-voice-female-passed.png','聲音配對｜女角色','女角色使用中文女聲','Microsoft Yating · 以下播放女聲樣本','您好，請先說明您已確認的資料，以及需要我協助的部分。',7,'female'),
('19-voice-male-passed.png','語音驗證｜完整回路','男女角色皆完成兩輪','錄音 → 辨識 → AI → 語音 → 接續收音','男女角色都已完成兩輪自動語音驗證，包含錄音、辨識、實際人工智慧回覆、語音播放與接續收音。這是測試音源驗證，實體麥克風仍待真人驗收。',13,None),
('16-student-reads-feedback.png','完成｜依回饋繼續判讀','讓判斷回到證據','骨架觀測 → 意圖假設 → 教師回饋','完整流程的重點，是把可見動作、意圖假設與教師回饋分開保存，再用前後畫面與語音，持續修正自己的判斷。',10,'focus'),
]


def build():
    assets=PROJECT/'assets';(assets/'fonts').mkdir(parents=True,exist_ok=True)
    comps=PROJECT/'compositions';comps.mkdir(exist_ok=True)
    shutil.copyfile('C:/Windows/Fonts/msjh.ttc',assets/'fonts/guide.ttc')
    shutil.copyfile(ROOT/'frontend/vendor/gsap.min.js',assets/'gsap.min.js')
    hosts=[];audios=[];captions=[];ledger=[];start=0;srt=[]
    for i,(filename,chapter,title,hint,text,minimum,mode) in enumerate(SHOTS):
        src=SOURCE/filename
        if not src.is_file():raise FileNotFoundError(src)
        shutil.copyfile(src,assets/filename)
        audio=assets/f'voice-{i:02}.wav'
        if mode in ('male','female'):
            shutil.copyfile(ROOT/f'runtime/verification-5.3.1/{mode}.wav',audio)
            import wave
            with wave.open(str(audio),'rb') as w:secs=w.getnframes()/w.getframerate()
        else:secs=speech(text,audio,'female')
        duration=round(max(minimum,secs+1),3)
        ident=f'step-{i+1:02}'
        # These are static, declared crops of screenshots, never reconstructed UI.
        focus='focus' if mode=='focus' else ''
        content=f'''<template><style>
        @font-face{{font-family:Guide;src:url('assets/fonts/guide.ttc')}}
        #{ident}{{position:absolute;inset:0;font-family:Guide,sans-serif;color:#173e4d}}.shot-title{{position:absolute;left:96px;top:90px;margin:0;font-size:43px;line-height:1.3}}.screen{{position:absolute;left:96px;top:180px;width:1296px;height:729px;overflow:hidden;background:#fff;border:1px solid #c6d7df;border-radius:12px}}.screen img{{width:100%;height:100%;object-fit:contain}}.screen.focus img{{position:absolute;width:1722px;height:auto;max-width:none;left:-377px;top:-100px}}.guide-aside{{position:absolute;left:1432px;top:188px;width:392px}}.phase{{color:#186f76;font-size:28px;line-height:1.4}}.step-count{{font-size:72px;line-height:1.3;color:#186f76;margin:22px 0 30px}}h3{{font-size:42px;line-height:1.45;margin:0 0 26px}}.hint{{font-size:31px;line-height:1.65;margin:0}}.source{{font-size:28px;line-height:1.7;color:#4d6370;margin-top:46px}}
        </style><div id="{ident}" data-composition-id="{ident}" data-width="1920" data-height="1080" data-duration="{duration}"><h2 class="shot-title">{html.escape(chapter)}</h2><div class="screen {focus}" data-layout-allow-overflow><img src="assets/{filename}" alt="實際操作畫面：{html.escape(chapter)}"></div><aside class="guide-aside"><div class="phase">完整操作流程</div><div class="step-count">{i+1:02} / {len(SHOTS):02}</div><h3>{html.escape(title)}</h3><p class="hint">{html.escape(hint)}</p><p class="source">實際畫面擷取剪輯<br>示範帳號與形成性回饋<br>完整版僅供授權本機檢視</p></aside></div><script>const tl=gsap.timeline({{paused:true}});tl.fromTo('#{ident} .guide-aside',{{x:18,opacity:.6}},{{x:0,opacity:1,duration:.35,ease:'power3.out'}},.08);window.__timelines['{ident}']=tl;</script></template>'''
        (comps/f'{ident}.html').write_text(content,encoding='utf-8')
        hosts.append(f'<div id="{ident}" class="clip" data-composition-id="{ident}" data-composition-src="compositions/{ident}.html" data-start="{start:.3f}" data-duration="{duration}" data-width="1920" data-height="1080" data-track-index="1" data-track-kind="graphics" data-hold="操作步驟與文字閱讀"></div>')
        audios.append(f'<audio id="narration-{i}" class="clip" src="assets/{audio.name}" data-start="{start+.25:.3f}" data-duration="{secs:.3f}" data-track-index="2" data-volume="1"></audio>')
        captions.append(f'<p id="caption-{i}" class="clip caption-layer" data-start="{start+.25:.3f}" data-duration="{duration-.35:.3f}" data-track-index="3" data-track-kind="captions" data-hold="旁白字幕">{html.escape(text)}</p>')
        ledger.append({'scene':ident,'file':filename,'start':start,'duration':duration,'narration_seconds':secs,'text':text,'source_kind':'actual local browser screenshot','screenshot_sha256':hashlib.sha256(src.read_bytes()).hexdigest(),'contains_private_footage':filename in ['05-360-view.png','06-range.png','07-analysis-running.png','08-skeleton-frame.png','09-actions-meaning.png','10-motion-evidence.png','11-learner-note.png','12-note-saved.png','17-teacher-context-review.png']})
        def stamp(t):
            n=round(t*1000);return f'{n//3600000:02}:{n//60000%60:02}:{n//1000%60:02},{n%1000:03}'
        srt.append(f'{i+1}\n{stamp(start+.25)} --> {stamp(start+duration-.1)}\n{text}\n')
        start=round(start+duration,3)
    caption_file='''<template><style>@font-face{font-family:Guide;src:url('assets/fonts/guide.ttc')}#captions{position:absolute;inset:0;font-family:Guide,sans-serif}.caption-layer{position:absolute;inset:0;display:flex;align-items:flex-end;justify-content:center;margin:0;padding:0 96px 40px;font-size:30px;line-height:1.55;text-align:center;color:#193f4e;pointer-events:none}</style><div id="captions" data-composition-id="captions" data-width="1920" data-height="1080">'''+''.join(captions)+'''</div><script>window.__timelines['captions']=gsap.timeline({paused:true});</script></template>'''
    (comps/'captions.html').write_text(caption_file,encoding='utf-8')
    caption_host=f'<div id="captions" class="clip" data-composition-id="captions" data-composition-src="compositions/captions.html" data-start="0" data-duration="{start}" data-width="1920" data-height="1080" data-track-index="3" data-track-kind="captions" style="z-index:5"></div>'
    root=f'''<!doctype html><html lang="zh-Hant"><meta charset="utf-8"><title>v5.3.1學員分析與教師回饋操作指南</title><style>@font-face{{font-family:Guide;src:url('assets/fonts/guide.ttc')}}*{{box-sizing:border-box}}body{{margin:0;background:#f1f5f7}}#root{{position:relative;width:100%;height:100%;overflow:hidden;font-family:Guide,sans-serif}}.paper{{position:absolute;inset:0;background:#f1f5f7}}.edition{{position:absolute;left:96px;top:45px;color:#536c7a;font-size:28px}}.clip{{position:absolute;inset:0}}.caption-layer{{pointer-events:none;z-index:5}}.caption-layer p{{position:absolute;left:96px;right:96px;bottom:40px;margin:0;padding:18px 24px;font-size:30px;line-height:1.55;color:#193f4e;background:#ffffffed;border-radius:10px}}#progress{{position:absolute;left:0;bottom:0;height:8px;width:1920px;background:#166c78;transform-origin:left center;z-index:8}}</style><div id="root" data-composition-id="main" data-width="1920" data-height="1080" data-duration="{start}"><div class="paper"></div><div class="edition">迴旋梯智鏈 · v5.3.1 操作指南 · 2026-10-23</div>{''.join(hosts)}{''.join(audios)}{caption_host}<div id="progress"></div></div><script src="assets/gsap.min.js"></script><script>const tl=gsap.timeline({{paused:true}});tl.fromTo('#progress',{{scaleX:0}},{{scaleX:1,duration:{start},ease:'none'}},0);window.__timelines['main']=tl;</script></html>'''
    (PROJECT/'index.html').write_text(root,encoding='utf-8')
    (PROJECT/'capture-ledger.json').write_text(json.dumps({'private_local_only':True,'format':'narrated screenshot walkthrough, not continuous recording','width':1920,'height':1080,'fps':30,'duration':start,'scenes':ledger},ensure_ascii=False,indent=2),encoding='utf-8')
    (PROJECT/'guide.zh-TW.srt').write_text('\n'.join(srt),encoding='utf-8')
    (PROJECT/'SPEC.md').write_text('GOAL: 學員與教師能依同一段影片完成分析、回饋與查看。\nOUTPUT: HyperFrames 1920x1080 30fps，實際UI畫面擷取剪輯，完整本機版。\nLOOK: #f1f5f7底、#173e4d文字、#186f76操作提示；微軟正黑體42px標題、31px步驟、30px字幕。\nMOTION: 0.35秒右側提示進場，其餘閱讀停留；影片進度線線性推進。\nSOUND: 本機Yating旁白與男女聲樣本；無配樂，避免影響語音辨識與配對示例。\nBANNED: 重新繪製網站、假裝連續錄影、把意圖假設當已確認動機、公開實拍教材或測試資料。\nQA: 各段中點、骨架疊圖、教師保存狀態、學員回饋與男女聲驗證。\n',encoding='utf-8')
    print(json.dumps({'project':str(PROJECT),'duration':start,'scenes':len(SHOTS),'private_local_only':True},ensure_ascii=False))

if __name__=='__main__':
    if '--export-only' not in sys.argv:
        build()
    build_export()
