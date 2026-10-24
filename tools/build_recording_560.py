"""Assemble actual CUA captures; public edition masks original clinical footage.

The voice diagnostic retains wall-clock waits and actual input/output audio.
Intro/lecture retakes are explicitly identified, never fabricated UI states.
"""
from pathlib import Path
from collections import OrderedDict
import datetime, hashlib, json, shutil, sqlite3, subprocess, sys, wave
import numpy as np
from PIL import Image, ImageDraw, ImageFont

ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from backend.virtual_video import speech
from tools.build_full_recording import stamp
WORK=ROOT/'runtime/recording-v5.6.0';DEST=ROOT/'docs/v5.6'
RUNTIME=WORK/'isolated-runtime'
FF=ROOT/'tools/ffmpeg/ffmpeg-9.0.2-essentials_build/bin/ffmpeg.exe'
ORDER=[*[f'R{i:02}' for i in range(1,10)],'RR10','R11',*map(str,range(12,25)),'25B',*map(str,range(26,33)),
       '34','35',*map(str,range(36,42)),'43','45',*[f'46{x}' for x in 'abcd'],*map(str,range(47,53)),'T42','T44',*map(str,range(53,67))]
TEXT={
'R01':'第五點六版完整操作實錄。使用獨立示範帳號，入口及講師播放段落另行補錄。等待剪短與閱讀停格，皆有保留剪輯紀錄。',
'R02':'先選擇自己的職種。本平台有十二種職類，各職種的教案、自評和訓練紀錄分開保存。',
'R03':'依職種選擇適用情境，九個來源情境共有三十九組職種任務。',
'R04':'自評使用本職類核心能力與行為量尺。題庫保留來源及待審狀態，不宣稱是正式公開考試。',
'R05':'本例以示範作答說明操作，並非真實臨床能力證據。客觀前測與自評分開計算。',
'R06':'自評決定本輪互動難度；累積學習決定教材解鎖，教師正式核定另外保存。',
'R07':'選定教案後固定內容來源、職類任務與版本。後面的互動及回饋使用已完成的第一輪示範紀錄。',
'R08':'教材依第一級到第五級逐步增加，包含單職類、跨域、影片、環景與逐格解說，前級內容持續保留。',
'R09':'第二級提供團隊分工與資訊接點，先學會區分各職類資料與交接責任。',
'R11':'預先生成影片保留文字稿、教學目的與角色界線。各級個人任務仍以當輪教案為準。',
'12':'一般肌少症影片同樣能逐格分析。指定人物範圍及一百四十五到一百五十一秒，不限三百六十度影片。',
'13':'開始後按原始幀率解碼每張影格，模型分析在本機執行，保留處理進度。',
'14':'此段完成一百八十張影格，其中八十七格偵測到人體。沒有可靠骨架的畫面也保留。',
'15':'以影格滑桿定位動作。沒有可靠人體時，不產生動作結論。',
'16':'這格只看得到部分關節，右肘彎曲不等於完成坐站。投影角度不能當成臨床量測。',
'17':'取消骨架勾選，查看同一張原圖，再對照前後動作。',
'18':'學員寫出可見動作、教案步驟目的、可能意圖與資訊缺口，保留不確定性。',
'19':'保存影格、來源版本及原始觀察，交由教師覆核，機器不代替教師下結論。',
'20':'第二級學習判讀也能單獨保存，練習營養與功能評估的分工及回報方式。',
'21':'四部環景教材可切換場域視角；觀看影片不會把畫面內容自動寫成當輪病歷。',
'22':'確認教材觀察並寫下反思，進入虛擬角色互動。完成確認不代表技能認證。',
'23':'營養師對應虛擬物理治療師。立體人體使用角色卡擬合的臉部、髮型與骨架。',
'24':'開啟原生分支情境，練習不同決策的結果與補強路徑。',
'25B':'依來源教案閱讀情境，選擇如何回應病人的挫折。',
'26':'非關鍵錯誤會提供具體回饋，說明選擇與教學目的的差距。',
'27':'返回同一題重練，原先選擇仍保留在分支歷程中。',
'28':'影像判讀的關鍵選擇，需要核對教案採用的指引版本及尚缺資料。',
'29':'關鍵錯誤進入安全補強路徑，先閱讀理由再決定下一步。',
'30':'安全結尾要求補強，並保留完整路徑，不能以重練抹除初次錯誤。',
'31':'可以重新開始分支練習，前一輪結果仍供教師查看。',
'32':'連續語音只需一次啟動，回覆播放後自動接續收音，也能取消。接下來用受控測試音源驗證。',
'35':'兩輪辨識、實際模型回覆、男聲播放及自動接續收音通過。此測試使用合成輸入，不能代替手機實體麥克風驗收。',
'36':'重新練習時先肯定病人努力，再說明會一起核對資訊。',
'37':'這份歷史教案依二零一九版判讀，畫面提醒與二零二五版算法區分。',
'38':'營養問題先補足飲食資料與限制，再協商可執行的方向。',
'39':'活動與安全的選擇，需依來源教案及個案條件核對。',
'40':'本輪完成四次正確選擇；安全補強的前一輪仍保留。分支練習不直接計入正式能力分數。',
'41':'一般互動承接同一情境。營養師先詢問物理治療師需要一起核對哪些資料。',
'43':'第二輪明列缺少的肌力、坐站及飲食資訊，提出分工與回報方式。',
'45':'可查閱來源教案的檢查紀錄，查閱紀錄與實際完成檢查分開保存。',
'46a':'逐項完成關鍵決策，確認後保留頁面位置與已填內容。',
'46b':'先前已看過分支回饋的題目會標示練習背景，避免當成獨立初次表現。',
'46c':'將來源依據與營養資料缺口分開整理，查看即時回饋。',
'46d':'確認活動與安全重點，再整理交接。',
'47':'情境操作另外保存，例如確認身分；不把點擊按鈕視為臨床能力認證。',
'48':'以狀況、背景、評估及協助需求整理交接，明列誰補哪份資料及如何回報。',
'49':'完成題序重新排列的即時測驗，依指定教案版本作答。',
'50':'成果將客觀練習分、自評及教師核定分開呈現。對話、交接和原始證據仍待教師檢核。',
'51':'教師用自己的示範帳號登入，從工作台找到同一輪訓練。',
'52':'檢視原始對話、關鍵決策、交接及先前分支練習標記，不只看總分。',
'53':'針對安全分支保存具體補強建議，回饋綁定該輪路徑。',
'54':'教師開啟完整逐格覆核頁，比對同一格骨架與原片來源。',
'55':'前後切換影格，確認哪些動作真的可見，哪些仍缺證據。',
'56':'取消骨架查看原圖，避免把模型估計誤認為原始影像。',
'57':'也能播放前後原片核對連續動作及現場語音。本操作片另加解說。',
'58':'教師明確要求補看手部接觸、口令及完整次數，原始學員觀察仍保留。',
'59':'教師另填整體評語與補作要求。本例分數及等級是操作示範，不授予真實資格。',
'60':'保存正式回饋後，教師、時間、分數與完整理由均列入歷程。',
'61':'學員重新登入，再完成本次輪替自評，接著從學習歷程回看已完成訓練。',
'62':'本次自評另存，不覆寫第一輪的原始評量與教師回饋。',
'63':'學習歷程同時列出第二輪進度與已完成的第一輪，選擇第一輪回看。',
'64':'學員可讀到正式教師評語、補作要求及獨立保存的核定結果。',
'65':'同頁查看安全分支專屬回饋，知道哪個選擇需要補強。',
'66':'原始逐格觀察下方顯示教師具體建議，依據同一影格及前後脈絡修正判讀。',
}
ACTUAL={'T42':2,'T44':4}

def decode(path):
    return np.frombuffer(subprocess.check_output([str(FF),'-v','error','-i',str(path),'-f','f32le','-ar','48000','-ac','1','pipe:1']),dtype='<f4').copy()

def build():
    DEST.mkdir(exist_ok=True);(WORK/'narration').mkdir(exist_ok=True);(WORK/'fonts').mkdir(exist_ok=True)
    shutil.copyfile('C:/Windows/Fonts/msjh.ttc',WORK/'fonts/guide.ttc')
    groups=OrderedDict();all_frames=[json.loads(s) for s in (WORK/'frames.jsonl').read_text().splitlines()]
    last_write={f['file']:f for f in all_frames}
    for f in all_frames:
        key=f['chapter'].split(' ',1)[0]
        if key in ORDER or key=='42':
            assert last_write[f['file']] is f, f'Overwritten capture {key}/{f["file"]}'
            groups.setdefault(key,[]).append(f)
    assert set(ORDER)<=set(groups)
    voice=json.loads((WORK/'voice-report.json').read_text());assert voice['passed']
    take=json.loads((WORK/'lecture-retake.json').read_text())
    db=sqlite3.connect(RUNTIME/'clinical_tutor.sqlite3');db.row_factory=sqlite3.Row
    messages={r['id']:dict(r) for r in db.execute('select id,content from messages')};db.close()
    font=ImageFont.truetype('C:/Windows/Fonts/msjh.ttc',25)
    concat={kind:['ffconcat version 1.0'] for kind in ['local','public']}
    (WORK/'public-frames').mkdir(exist_ok=True)
    ass=[];srt=[];meta=[';FFMETADATA1'];ledger=[];pcm=[];current=0
    sheet=Image.new('RGB',(1800,((len(ORDER)+3)//4)*280),'#173e4d');draw=ImageDraw.Draw(sheet);small=ImageFont.truetype('C:/Windows/Fonts/msjh.ttc',15)
    def caption(start,end,text):
        lines=['']
        for char in text:
            if font.getlength(lines[-1]+char)>1700:lines.append('')
            lines[-1]+=char
        ass.append(f'Dialogue: 0,{stamp(start,True)},{stamp(end,True)},Caption,,0,0,0,,'+r'\N'.join(lines))
        srt.append(f'{len(srt)+1}\n{stamp(start)} --> {stamp(end)}\n{text}\n')
    for i,key in enumerate(ORDER):
        data=groups[key];title=data[0]['chapter'].split(' ',1)[1]
        # Prefer the settled native ending over an animation-transition capture.
        if key=='30':data=groups['31']
        if key=='40':data=groups['42']
        intervals=[max(.04,min(1.2,b['seconds']-a['seconds'])) for a,b in zip(data,data[1:])]
        tail=.35;placements=[];subcaptions=[]
        if key=='34':
            origin=data[0]['seconds'];start_time=datetime.datetime.fromisoformat(voice['startedAt'].replace('Z','+00:00')).timestamp()
            intervals=[max(.04,b['seconds']-a['seconds']) for a,b in zip(data,data[1:])]
            base=sum(intervals)+tail;duration=max(base,start_time-origin+voice['events'][-1]['ms']/1000+.4)
            for event in voice['events']:
                offset=start_time-origin+event['ms']/1000
                if event['kind'] in {'listening','resumed'}:
                    turn=event['turn'];placements.append((offset+.2,decode(RUNTIME/'voice-diagnostics'/f'input-{turn}.wav')))
                    subcaptions.append((offset+.2,offset+.2+voice['rounds'][turn-1]['inputSeconds'],'測試學員音源：'+voice['rounds'][turn-1]['expected']))
                if event['kind']=='playback-started':
                    turn=event['turn'];placements.append((offset,decode(next((RUNTIME/'voice-diagnostics').glob(f'*-1-{voice["testId"]}-{turn}.wav')))))
                    subcaptions.append((offset,offset+voice['rounds'][turn-1]['outputSeconds'],'角色實際回覆：'+voice['rounds'][turn-1]['reply']['text']))
            text='連續語音兩輪實測，保留實際等待；受控合成輸入，不是實體麥克風測試。'
        elif key=='RR10':
            intervals=[max(.04,b['seconds']-a['seconds']) for a,b in zip(data,data[1:])]
            base=sum(intervals)+tail;duration=max(base,take['duration']+.4)
            placements=[(0,decode(ROOT/take['source']))];text='已發布講師影片原速播放，聲音取自同一個影片檔。'
        else:
            if key in ACTUAL:
                m=messages[ACTUAL[key]];sound=RUNTIME/'speech'/f'1-{m["id"]}.wav';text='教師逐字紀錄回放同一輪角色回覆：'+m['content']
            else:
                text=TEXT[key];sound=WORK/'narration'/f'{key}.wav';speech(text,sound,'female')
            samples=decode(sound);placements=[(.15,samples)];base=sum(intervals)+tail;duration=max(base,len(samples)/48000+.65)
        duration=np.ceil(duration*30)/30;audio=np.zeros(round(duration*48000),dtype=np.float32)
        for offset,samples in placements:
            start=max(0,round(offset*48000));n=min(len(samples),len(audio)-start)
            if n>0:audio[start:start+n]+=samples[:n]
        pcm.append(audio);durations=[*intervals,tail+duration-base];local=0;frame_map=[]
        for f,d in zip(data,durations):
            path=WORK/'frames'/f['file'];im=Image.open(path).convert('RGB');dr=ImageDraw.Draw(im)
            for m in f.get('masks',[]):
                x0=max(0,int(m['x'])-2);y0=max(0,int(m['y'])-2);x1=min(im.width,int(m['x']+m['width'])+3);y1=min(im.height,int(m['y']+m['height'])+3)
                if x1>x0 and y1>y0:
                    dr.rectangle((x0,y0,x1,y1),fill='#173e4d')
                    if x1-x0>220 and y1-y0>45:dr.text((x0+10,y0+10),'原始教材影像僅於本機版顯示',font=small,fill='white')
            im.save(WORK/'public-frames'/f['file'])
            for kind in concat:
                folder='frames' if kind=='local' else 'public-frames'
                concat[kind].extend([f"file '{folder}/{f['file']}'",f'duration {d:.6f}'])
            frame_map.append({'file':f['file'],'offset':round(local,6),'duration':round(d,6),'masks':f.get('masks',[])});local+=d
        start=current;end=start+duration
        if subcaptions:
            for a,b,txt in subcaptions:caption(start+a,min(end,start+b),txt)
        else:caption(start,end,text)
        ass.append(f'Dialogue: 0,{stamp(start,True)},{stamp(end,True)},Header,,0,0,0,,v5.6.0 完整操作實錄  ·  {i+1:02}/{len(ORDER):02}  {title}')
        if key=='34':ass.append(f'Dialogue: 1,{stamp(start,True)},{stamp(end,True)},Notice,,0,0,0,,原速語音實測 · 實際等待保留 · 男聲對應男性物理治療師')
        meta.extend(['[CHAPTER]','TIMEBASE=1/1000',f'START={round(start*1000)}',f'END={round(end*1000)}','title='+title])
        middle=data[len(data)//2]['file'];ledger.append({'key':key,'title':title,'start':round(start,6),'duration':round(duration,6),'capture_seconds_edited':round(base,6),'reading_hold':round(duration-base,6),'frames':frame_map,'caption':text,'audio_source':'actual app reply' if key in ACTUAL else 'actual continuous diagnostic' if key=='34' else 'same published lecture' if key=='RR10' else 'added narration','middle_frame':middle,'middle_frame_sha256':hashlib.sha256((WORK/'frames'/middle).read_bytes()).hexdigest()})
        sheet.paste(Image.open(WORK/'public-frames'/middle).resize((450,253)),(i%4*450,i//4*280));draw.text((i%4*450+5,i//4*280+254),key+' '+title[:25],font=small,fill='white');current=end
    for kind,lines in concat.items():
        folder='frames' if kind=='local' else 'public-frames';lines.append(f"file '{folder}/{groups[ORDER[-1]][-1]['file']}'")
        (WORK/f'capture-{kind}.ffconcat').write_text('\n'.join(lines)+'\n',encoding='utf8')
    combined=np.concatenate(pcm);assert np.isfinite(combined).all() and np.max(np.abs(combined))<1
    with wave.open(str(WORK/'narration.wav'),'wb') as out:
        out.setnchannels(1);out.setsampwidth(2);out.setframerate(48000);out.writeframes((combined*32767).astype('<i2').tobytes())
    styles=(ROOT/'tools/build_full_recording.py').read_text(encoding='utf8').split("    header='''",1)[1].split("'''",1)[0].replace('Caption,Microsoft JhengHei,28','Caption,Microsoft JhengHei,25')
    for kind in concat:
        notice='公開版 · 原始教材影像遮蔽' if kind=='public' else '本機完整影像版 · 請勿公開原始教材影像'
        extra=f'Dialogue: 1,0:00:00.00,{stamp(current,True)},Notice,,0,0,0,,示範帳號・操作剪輯與閱讀停格・{notice}'
        (WORK/f'full-flow-{kind}.ass').write_text(styles+'\n'.join(ass)+'\n'+extra+'\n',encoding='utf-8-sig')
    (WORK/'chapters.ffmetadata').write_text('\n'.join(meta)+'\n',encoding='utf8')
    (DEST/'v5.6.0-full-workflow.zh-TW.srt').write_text('\n'.join(srt),encoding='utf8')
    (DEST/'v5.6.0-full-workflow.zh-TW.vtt').write_text('WEBVTT\n\n'+'\n'.join(srt).replace(',','.'),encoding='utf8')
    sheet.save(WORK/'selected-captures-review.jpg',quality=92)
    manifest={'version':'5.6.0','format':'edited actual CUA browser captures with disclosed intro retakes, narration and reading holds','continuous_voice_take_wallclock_preserved':True,'physical_microphone_tested':False,'synthetic_accounts':True,'duration':round(current,6),'scenes':ledger}
    (WORK/'edit-ledger.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf8')
    (DEST/'v5.6.0-full-workflow-chapters.json').write_text(json.dumps([{'title':s['title'],'start':s['start'],'duration':s['duration']} for s in ledger],ensure_ascii=False,indent=2),encoding='utf8')
    print(json.dumps({'duration':current,'chapters':len(ledger),'peak':float(np.max(np.abs(combined)))}),flush=True)

def render():
    manifest=json.loads((WORK/'edit-ledger.json').read_text())
    for kind in ['local','public']:
        command=[str(FF),'-y','-v','warning','-f','concat','-safe','0','-i',f'capture-{kind}.ffconcat','-i','narration.wav','-i','chapters.ffmetadata',
          '-map','0:v:0','-map','1:a:0','-map_metadata','2','-map_chapters','2','-vf',f'scale=1640:924:flags=lanczos,pad=1920:1080:140:70:color=0xf1f5f7,fps=30,ass=full-flow-{kind}.ass:fontsdir=fonts',
          '-c:v','libx264','-preset','veryfast','-crf','20','-threads','4','-r','30','-pix_fmt','yuv420p','-c:a','aac','-b:a','160k','-ar','48000','-t',str(manifest['duration']),'-movflags','+faststart',str(DEST/f'v5.6.0-full-workflow-{kind}.mp4')]
        with (WORK/f'encode-{kind}.log').open('w',encoding='utf8') as log:subprocess.run(command,cwd=WORK,stdout=log,stderr=log,check=True)
        print('rendered',kind,flush=True)

if __name__=='__main__':
    if '--render-only' not in sys.argv:build()
    if '--prepare-only' not in sys.argv:render()
