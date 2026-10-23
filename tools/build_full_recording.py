"""Assemble real browser captures into a private, narrated operation recording.

UI frames come exclusively from the browser-use capture API. Between-tool idle
time and rejected takes are removed; brief last-frame reading holds may be added.
No browser automation or simulated product UI is used by this assembler.
"""
from pathlib import Path
from collections import OrderedDict
import hashlib,json,shutil,subprocess,wave
import numpy as np
from PIL import Image,ImageDraw,ImageFont
import sys
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from backend.virtual_video import speech
WORK=ROOT/'runtime/recording-v5.3.2'
DEST=ROOT/'docs/v5.3'
FF=ROOT/'tools/ffmpeg/ffmpeg-9.0.2-essentials_build/bin/ffmpeg.exe'

ORDER=[*map(lambda n:f'{n:02}',range(1,29)),*map(lambda n:f'{n:02}',range(31,40)),
       'R01','R02b',*map(lambda n:f'{n:02}',range(54,59)),
       'R03','R04','R05','R06','R07','R08','R09','R10','R10c','R11','R12b','R13','R14']
NARRATION={
 '01':'先以學員帳號登入。示範帳號已開放全部教材。',
 '02':'選擇營養師，再選擇這次要練習的情境。',
 '03':'先查看本職類核心能力自評與客觀前測。',
 '04':'依實際經驗完成自評，再送出客觀前測答案。',
 '05':'自評、客觀分數與累積教材等級分開呈現。',
 '06':'依自評等級進入教案，先讀互動壓力與學習目標。',
 '07':'選定教案後，系統保存本輪內容與來源版本。',
 '08':'教材由第一到第五級累加，前級內容持續保留。',
 '09':'第一級先建立本職類資料判讀與病人溝通知識。',
 '10':'第二級加入跨域分工、資訊接點與團隊交接。',
 '11':'寫下自己的判讀，保存本教案的學習紀錄。',
 '12':'第三級以一般影片對照真實的語言、動作與順序。',
 '13':'第四級加入環景場域的位置、視角與協調任務。',
 '14':'第五級逐張檢視原圖、骨架、目的與替代判斷。',
 '15':'四部環景影片都可從教材選單開啟。',
 '16':'轉動視角並播放影片，觀察不同位置的資訊。',
 '17':'一般影片也可以分析。本例選肌少症影片分析。',
 '18':'展開十三段行為步驟，先定位要觀察的動作。',
 '19':'坐站步驟分開說明目的、觀察重點與常見誤判。',
 '20':'核對患者所在範圍，指定本例的分析時間。',
 '21':'按開始逐格分析，每張影格都會解碼與計算。',
 '22':'本例完成五百二十八張影格，請核對結果與限制。',
 '23':'使用綠線與關節點觀察患者的動作變化。',
 '24':'按下一格，取消骨架勾選，可核對本張原圖。',
 '25':'骨架觀測與教案目的分開閱讀，避免直接猜測意圖。',
 '26':'寫出本格動作、目的、影像依據及仍需確認的資訊。',
 '27':'保存影格、步驟與觀察，交由教師覆核。',
 '28':'完成教材觀察與反思，再進入角色互動。',
 '31':'角色使用立體人體與骨架，可從正面檢視。',
 '32':'轉到側面，確認人物是場景中的立體角色。',
 '33':'以職類角色提出問題。本例是第五級職場互動。',
 '34':'面對專業質疑，整理已知資料與依據，再協商分工。',
 '35':'完成案例界線暖身，未確認資料應標記並核對。',
 '36':'每個關鍵決策都會留下答案與即時回饋。',
 '37':'版本與資訊不足時，先確認依據再作判斷。',
 '38':'營養決策需回到完整資料與個別照護條件。',
 '39':'安全關鍵項目與其他決策分開保存。',
 'R01':'兩輪語音已通過。這是測試音源，不是實體麥克風驗收。',
 '54':'完成對話及決策後，返回目前互動步驟。',
 '55':'用四個欄位整理狀況、背景、評估及具體需求。',
 '56':'提交交接，系統檢核必要對話與決策是否完成。',
 '57':'完成即時測驗，再查看六階段的學習成果。',
 '58':'客觀練習分、原始證據與教師核定分開呈現。',
 'R03':'教師使用自己的帳號登入教學工作台。',
 'R04':'開啟同一筆訓練，查看各級知識判讀與原始觀察。',
 'R05':'教師可並排檢視骨架與原片，逐格定位。',
 'R06':'播放前後動作，核對連續變化及現場口令。',
 'R07':'填寫具體逐格建議，指出還需要哪些證據。',
 'R08':'按保存。新回饋另存歷程，保留學員原始判讀。',
 'R09':'完成訓練後，教師另填整體評語與補強要求。',
 'R10':'按保存正式教師回饋，等待系統完成保存。',
 'R10c':'覆核歷史保留教師、時間、分數與完整理由。',
 'R11':'學員重新整理回饋，即可查看最新評語與補作建議。',
 'R12b':'逐格建議與歷次回饋也保留在原始觀察下方。',
 'R13':'在學習歷程中，可查看自評與每輪訓練紀錄。',
 'R14':'重開成果頁，依教師建議補充證據，再開始下一輪。',
}

def stamp(t,ass=False):
    if ass:
        n=round(t*100);return f'{n//360000:01}:{n//6000%60:02}:{n//100%60:02}.{n%100:02}'
    n=round(t*1000);return f'{n//3600000:02}:{n//60000%60:02}:{n//1000%60:02},{n%1000:03}'

def build():
    frames=[json.loads(line) for line in (WORK/'frames.jsonl').read_text(encoding='utf-8').splitlines()]
    groups=OrderedDict()
    for frame in frames:groups.setdefault(frame['chapter'].split(' ',1)[0],[]).append(frame)
    (WORK/'narration').mkdir(exist_ok=True);(WORK/'fonts').mkdir(exist_ok=True)
    shutil.copyfile('C:/Windows/Fonts/msjh.ttc',WORK/'fonts/guide.ttc')
    voice=json.loads((WORK/'voice-report.json').read_text(encoding='utf-8'))
    assert voice['passed'] and len(voice['rounds'])==2
    font=ImageFont.truetype('C:/Windows/Fonts/msjh.ttc',28)
    concat=['ffconcat version 1.0'];pcm=[];ledger=[];captions=[];ass=[];meta=[';FFMETADATA1'];current=0
    review=Image.new('RGB',(1800,((len(ORDER)+3)//4)*280),'#173e4d');draw=ImageDraw.Draw(review)
    small=ImageFont.truetype('C:/Windows/Fonts/msjh.ttc',15)
    for i,key in enumerate(ORDER):
        data=groups[key];title=data[0]['chapter'].split(' ',1)[1]
        sound=WORK/'narration'/f'{key}.wav'
        if key=='R02b':
            source=list((ROOT/'runtime/verification-5.3.2/isolated-runtime/voice-diagnostics').glob(f"*-2-{voice['testId']}-2.wav"))
            assert len(source)==1;shutil.copyfile(source[0],sound)
            text='男角色實際合成回覆：'+voice['rounds'][1]['reply']['text']
        else:text=NARRATION[key];speech(text,sound,'female')
        raw=subprocess.check_output([str(FF),'-v','error','-i',str(sound),'-f','f32le','-ar','48000','-ac','1','pipe:1'])
        samples=np.frombuffer(raw,dtype='<f4');seconds=len(samples)/48000
        intervals=[max(.04,b['seconds']-a['seconds']) for a,b in zip(data,data[1:])]
        tail=float(np.median(intervals)) if intervals else .25
        base=sum(intervals)+tail;duration=max(base,seconds+.65)
        for item,length in zip(data,[*intervals,tail+duration-base]):
            concat.extend([f"file 'frames/{item['file']}'",f'duration {length:.6f}'])
        start=current;end=start+duration
        audio=np.zeros(round(duration*48000),dtype=np.float32);offset=round(.15*48000)
        audio[offset:offset+len(samples)]=samples;pcm.append(audio)
        lines=['']
        for char in text:
            if font.getlength(lines[-1]+char)>1710:lines.append('')
            lines[-1]+=char
        ass_text=r'\N'.join(lines)
        ass.append(f'Dialogue: 0,{stamp(start,True)},{stamp(end,True)},Caption,,0,0,0,,{ass_text}')
        ass.append(f'Dialogue: 0,{stamp(start,True)},{stamp(end,True)},Header,,0,0,0,,v5.3.2 完整操作實錄  ·  {i+1:02}/{len(ORDER):02}  {title}')
        captions.append(f'{i+1}\n{stamp(start)} --> {stamp(end)}\n{text}\n')
        meta.extend(['[CHAPTER]','TIMEBASE=1/1000',f'START={round(start*1000)}',f'END={round(end*1000)}','title='+title])
        ledger.append({'key':key,'title':title,'start':round(start,3),'duration':round(duration,3),'capture_seconds':round(base,3),'reading_hold':round(duration-base,3),'captured_frames':len(data),'caption':text,'narration_seconds':round(seconds,3),'native_tab':data[0].get('tabId','5'),'first_frame':data[0]['file'],'middle_frame':data[len(data)//2]['file'],'last_frame':data[-1]['file'],'middle_frame_sha256':hashlib.sha256((WORK/'frames'/data[len(data)//2]['file']).read_bytes()).hexdigest()})
        review.paste(Image.open(WORK/'frames'/data[len(data)//2]['file']).resize((450,253)),(i%4*450,i//4*280))
        draw.text((i%4*450+5,i//4*280+254),key+' '+title[:25],font=small,fill='white')
        current=end
    concat.append(f"file 'frames/{groups[ORDER[-1]][-1]['file']}'")
    (WORK/'capture.ffconcat').write_text('\n'.join(concat)+'\n',encoding='utf-8')
    combined=np.concatenate(pcm)
    with wave.open(str(WORK/'narration.wav'),'wb') as out:
        out.setnchannels(1);out.setsampwidth(2);out.setframerate(48000);out.writeframes((np.clip(combined,-1,1)*32767).astype('<i2').tobytes())
    header='''[Script Info]
ScriptType: v4.00+
PlayResX: 1920
PlayResY: 1080
ScaledBorderAndShadow: yes
[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Caption,Microsoft JhengHei,28,&H004D3E17,&H004D3E17,&H00F7F5F1,&H00F7F5F1,0,0,0,0,100,100,0,0,1,0,0,2,100,100,8,1
Style: Header,Microsoft JhengHei,30,&H004D3E17,&H004D3E17,&H00F7F5F1,&H00F7F5F1,1,0,0,0,100,100,0,0,1,0,0,7,100,100,14,1
Style: Notice,Microsoft JhengHei,20,&H0070634D,&H0070634D,&H00F7F5F1,&H00F7F5F1,0,0,0,0,100,100,0,0,1,0,0,9,90,90,20,1
[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
'''
    ass.append(f'Dialogue: 1,{stamp(0,True)},{stamp(current,True)},Notice,,0,0,0,,示範帳號・等待已剪短・僅供授權本機檢視')
    (WORK/'full-flow.ass').write_text(header+'\n'.join(ass)+'\n',encoding='utf-8-sig')
    (WORK/'chapters.ffmetadata').write_text('\n'.join(meta)+'\n',encoding='utf-8')
    (DEST/'v5.3.2-full-workflow.zh-TW.srt').write_text('\n'.join(captions),encoding='utf-8')
    (WORK/'selected-captures-review.jpg').write_bytes(b'')
    review.save(WORK/'selected-captures-review.jpg',quality=92)
    manifest={'version':'5.3.2','format':'edited recording of actual browser UI frames with added narration','continuous_unedited':False,'inter_action_waits_removed':True,'capture_cadence':'approximately 2–4 frames/second; source timestamps retained within takes','output_fps':30,'private_local_only':True,'synthetic_accounts':True,'physical_microphone_tested':False,'duration':round(current,3),'scenes':ledger}
    (WORK/'edit-ledger.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({'duration':round(current,3),'scenes':len(ledger),'frames':sum(x['captured_frames'] for x in ledger),'output':'v5.3.2-full-workflow-local.mp4'}))

def render():
    manifest=json.loads((WORK/'edit-ledger.json').read_text(encoding='utf-8'))
    command=[str(FF),'-y','-v','warning','-f','concat','-safe','0','-i','capture.ffconcat','-i','narration.wav','-i','chapters.ffmetadata',
             '-map','0:v:0','-map','1:a:0','-map_metadata','2','-map_chapters','2','-vf','scale=1640:924:flags=lanczos,pad=1920:1080:140:70:color=0xf1f5f7,ass=full-flow.ass:fontsdir=fonts',
             '-c:v','libx264','-preset','veryfast','-crf','18','-threads','4','-r','30','-pix_fmt','yuv420p','-c:a','aac','-b:a','160k','-ar','48000','-t',str(manifest['duration']),'-movflags','+faststart',str(DEST/'v5.3.2-full-workflow-local.mp4')]
    with (WORK/'encode.log').open('w',encoding='utf-8') as log:subprocess.run(command,cwd=WORK,stdout=log,stderr=log,check=True)

if __name__=='__main__':
    if '--render-only' not in sys.argv:build()
    if '--prepare-only' not in sys.argv:render()
