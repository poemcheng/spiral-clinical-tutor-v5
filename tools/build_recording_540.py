"""Private v5.4.0 recording, assembled from actual CUA screenshots and app audio.

No generated product screens. Editing removes waits outside the continuous voice
take; longer reading holds are disclosed. Never publish footage or this runtime.
"""
from pathlib import Path
from collections import OrderedDict
import datetime, hashlib, json, shutil, subprocess, sys, wave
import numpy as np
from PIL import Image, ImageDraw, ImageFont

ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from backend.virtual_video import speech
from tools.build_full_recording import stamp
WORK=ROOT/'runtime/recording-v5.4.0';DEST=ROOT/'docs/v5.4'
RUNTIME=ROOT/'runtime/verification-5.3.2/isolated-runtime'
FF=ROOT/'tools/ffmpeg/ffmpeg-9.0.2-essentials_build/bin/ffmpeg.exe'
NAME='v5.4.0-full-workflow-local'
ORDER=['01','02','03','04','05','06','07','08','09','10','11','11c','12','13','14','15','16','17','18','19','20','21','22','23','24',
       '25','26','27','32',*[f'37{x}' for x in 'abcdef'],*[f'33{x}' for x in 'abcdef'],*[f'34{x}' for x in 'abcdef'],
       *[f'35{x}' for x in 'abcdef'],*[f'36{x}' for x in 'abcde'],'38','28','29a','29b','29','30','31',
       *map(str,range(41,54))]
TEXT={
 '01':'這是第五點四版完整操作實錄。使用示範帳號與示範作答，等待已剪短，部分畫面延長供閱讀。',
 '02':'選擇自己的職種及肌少症情境。每個職種分開保存自評、教案及訓練紀錄。',
 '03':'自評量尺與客觀前測分開呈現。這些練習題並非已確認的正式公開考題或院方核定考核。',
 '04':'本輪以營養師示範高難度互動，完成自評與前測。示範分數不代表真實臨床能力。',
 '05':'自評分流控制互動難度，累積學習控制教材解鎖；正式能力核定由教師另行評量。',
 '06':'閱讀案例、互動壓力與職類任務，再選擇教案。本例第五級需要面對職場質疑並協商分工。',
 '07':'教材從第一級到第五級逐步增加，前級內容持續保留。',
 '08':'第一級建立本職類的資料判讀；寫下依據與缺少資訊，保存學習紀錄。',
 '09':'第二級學習跨域資訊接點，區分影像、功能與營養評估的分工。',
 '10':'第三級以一般影片觀察真實的動作、言語與執行順序。',
 '11':'第四級加入環景場域任務，辨認成員位置、視角與交接方向。',
 '11c':'四部環景影片可切換播放並環顧場域。環景畫面不會改寫本輪病歷。',
 '12':'一般肌少症影片也能分析。先展開十三段行為步驟，定位要觀察的動作。',
 '13':'坐站準備與連續坐站分開解說，先確認動作目的、觀察焦點與判讀限制。',
 '14':'指定病人所在範圍與一百四十五到一百五十一秒。按開始後，每張影格都會解碼與分析。',
 '15':'本段完成一百八十張影格，八十七格偵測到人體。沒有可靠骨架的影格也保留原圖。',
 '16':'用骨架與關節點查看可見動作。軌跡編號不代表真實身分；投影角度不等同臨床量測。',
 '17':'按下一格，再取消骨架勾選，可核對同一張原圖。',
 '18':'機器觀測、可能意圖與教案步驟目的分開閱讀，還要核對前後動作與口令。',
 '19':'學員寫出動作、可能目的及判讀限制，保存影格、步驟與觀察給教師。',
 '20':'完成教材觀察與反思，進入角色會談。',
 '21':'營養師與虛擬物理治療師面對面互動。人物使用立體人體與骨架，可轉動視角。',
 '22':'學員先說明已知營養資料與缺口，詢問功能評估需要的資訊。',
 '24':'第二輪承接對方的回覆，說明缺少實測數據，協商營養與功能評估的分工。',
 '25':'第一次按我要對話溝通後，可自動送出並接續收音。這次以測試音源驗證，不使用實體麥克風。',
 '27':'兩輪錄音、辨識、實際模型回覆與語音播放均通過，並驗證回覆後自動接續收音。',
 '32':'以下依序展示放射、物理治療、醫師與護理情境；五個職種分別示範第一到第五級難度。',
 '37a':'放射師示範自評第二級。題本起測級別、互動分流與教材解鎖是不同資訊。',
 '37b':'放射師的對話對象是物理治療師，任務是檢查資料與功能評估的協作。',
 '37c':'交接影像數值，同時指出前次報告與儀器條件還需要核對。',
 '37e':'學員承接儀器一致性的問題，明確保留資料缺口並約定補齊。',
 '33a':'物理治療師示範第一級，互動採友善支持，讓新手練習傾聽與說明。',
 '33b':'物理治療師與教案病患互動，先理解需求，再確認下一步。',
 '33c':'學員先肯定病人的努力，詢問對檢查及身體變化的疑慮。',
 '33e':'第二輪回應挫折，說明會核對資料與評估流程，再確認病人的意願。',
 '34a':'醫師示範自評第三級，先閱讀任務與教案，再進入會談。',
 '34b':'醫師與虛擬病患討論目前已知資訊、不確定性與可接受的下一步。',
 '34c':'學員先詢問病人想釐清的問題，而不是直接給出結論。',
 '34e':'第二輪說明為何需要核對檢查條件及肌力資料，再確認是否回答到疑問。',
 '35a':'護理師示範第四級，同一教案包含病患與物理治療師兩種對象。',
 '35b':'護理師先向病患說明照護與檢查流程，回應疑慮並確認理解。',
 '35c':'學員介紹自己的角色，讓病人提出對過程的擔心。',
 '35e':'第二輪請病人用自己的話回述，確認真正想解決的疑問。',
 '36a':'切換到本輪另一位對話對象，與物理治療師討論照護追蹤。',
 '36b':'護理師交接病人疑慮、資料缺口與活動協助需求。',
 '36d':'第二輪釐清功能評估、照護紀錄與回覆病人的責任。',
 '38':'按取消語音會談可停止收音及角色播放，再返回學習流程。',
 '28':'完成四項關鍵決策，逐項查看即時回饋與安全重點。',
 '29a':'情境操作保存為獨立證據，本例先確認身分。',
 '29b':'從側面檢視立體人體，再回到正面；角色不是場景內的平面螢幕。',
 '29':'以狀況、背景、評估與協助需求整理跨專業交接。',
 '30':'完成即時測驗，系統保存本輪作答與解析。',
 '31':'成果頁將客觀練習分、自評及教師核定分開呈現。對話與交接仍需教師覆核。',
 '41':'教師使用自己的帳號登入，從教學工作台開啟同一筆訓練。',
 '42':'查看原始對話、關鍵決策、交接及情境會談的進展。',
 '43':'再查看學員的各級學習紀錄與保存的逐格觀察。',
 '44':'開啟完整覆核頁，並排檢視骨架與原始影片，定位同一張影格。',
 '45':'逐格切換原圖，並播放前後影片核對連續動作與現場口令。此段另加操作解說。',
 '46':'教師指出已做對的判讀，並具體要求補看前後畫面、手位、腳位與起始點。',
 '47':'保存逐格回饋後，學員原始觀察保留，教師建議另外列入歷程。',
 '48':'教師另填整體回饋及補作要求。本次為操作示範，不授予真實臨床資格。',
 '49':'保存後可看到教師、時間、分數與完整理由。',
 '50':'學員按重新整理教師回饋，即可看到最新整體評語與補作建議。',
 '51':'在原始影格觀察下方，也能查看教師逐格建議，依要求補充證據。',
 '52':'學習歷程分別保存五個職種的訓練。本例營養師完成六階段，其餘四職種示範兩輪情境會談。',
 '53':'回看成果與教師建議，再安排下一輪練習。完整對話、影格與回饋可追溯至本輪訓練。',
}
ACTUAL={'23':14,'37d':34,'37f':36,'33d':18,'33f':20,'34d':22,'34f':24,'35d':26,'35f':28,'36c':30,'36e':32}

def decode(path):
    return np.frombuffer(subprocess.check_output([str(FF),'-v','error','-i',str(path),'-f','f32le','-ar','48000','-ac','1','pipe:1']),dtype='<f4').copy()

def build():
    DEST.mkdir(exist_ok=True);(WORK/'narration').mkdir(exist_ok=True);(WORK/'fonts').mkdir(exist_ok=True)
    shutil.copyfile('C:/Windows/Fonts/msjh.ttc',WORK/'fonts/guide.ttc')
    groups=OrderedDict()
    for line in (WORK/'frames.jsonl').read_text(encoding='utf8').splitlines():
        f=json.loads(line);groups.setdefault(f['chapter'].split(' ',1)[0],[]).append(f)
    voice=json.loads((WORK/'voice-report.json').read_text(encoding='utf8'));assert voice['passed']
    messages={r['id']:r for r in json.loads((WORK/'dialogue-audio.json').read_text(encoding='utf8'))}
    font=ImageFont.truetype('C:/Windows/Fonts/msjh.ttc',25)
    concat=['ffconcat version 1.0'];ass=[];srt=[];meta=[';FFMETADATA1'];ledger=[];pcm=[];current=0
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
        # Keep the useful, explicitly checked end view for these retakes.
        if key in {'16','50','51'}:data=data[-1:]
        intervals=[max(.08,min(1.2,b['seconds']-a['seconds'])) for a,b in zip(data,data[1:])]
        tail=.35;placements=[];subcaptions=[]
        if key=='26':
            start_time=datetime.datetime.fromisoformat(voice['startedAt'].replace('Z','+00:00')).timestamp()
            # Preserve wall-clock timing in this unaccelerated voice take.
            intervals=[max(.04,b['seconds']-a['seconds']) for a,b in zip(data,data[1:])]
            origin=data[0]['seconds'];base=sum(intervals)+tail
            duration=max(base,voice['events'][-1]['ms']/1000+start_time-origin+.4)
            diag=RUNTIME/'voice-diagnostics'
            for event in voice['events']:
                offset=start_time-origin+event['ms']/1000
                if event['kind'] in {'listening','resumed'}:
                    turn=event['turn'];sound=diag/f'input-{turn}.wav';placements.append((offset+.2,decode(sound)))
                    subcaptions.append((offset+.2,offset+.2+voice['rounds'][turn-1]['inputSeconds'],'測試學員音源：'+voice['rounds'][turn-1]['expected']))
                if event['kind']=='playback-started':
                    turn=event['turn'];sound=next(diag.glob(f"*-13-{voice['testId']}-{turn}.wav"));placements.append((offset,decode(sound)))
                    subcaptions.append((offset,offset+voice['rounds'][turn-1]['outputSeconds'],'角色實際合成回覆：'+voice['rounds'][turn-1]['reply']['text']))
            text='兩輪自動語音實測：測試音源 → 辨識 → AI → 男聲回覆 → 自動接續收音。'
        else:
            if key in ACTUAL:
                message=messages[ACTUAL[key]];sound=Path(message['audio']);text='角色實際合成回覆：'+message['content']
            else:
                text=TEXT[key];sound=WORK/'narration'/f'{key}.wav';speech(text,sound,'female')
            samples=decode(sound);placements=[(.15,samples)];base=sum(intervals)+tail;duration=max(base,len(samples)/48000+.65)
        # Rounded scene boundaries are exactly reproducible at 30 fps.
        duration=np.ceil(duration*30)/30;audio=np.zeros(round(duration*48000),dtype=np.float32)
        for offset,samples in placements:
            a=max(0,round(offset*48000));n=min(len(samples),len(audio)-a);audio[a:a+n]+=samples[:n]
        pcm.append(audio)
        durations=[*intervals,tail+duration-base]
        for f,d in zip(data,durations):concat.extend([f"file 'frames/{f['file']}'",f'duration {d:.6f}'])
        local=0;frame_map=[]
        for f,d in zip(data,durations):frame_map.append({'file':f['file'],'offset':round(local,6),'duration':round(d,6)});local+=d
        start=current;end=start+duration
        if subcaptions:
            for a,b,txt in subcaptions:caption(start+a,min(end,start+b),txt)
        else:caption(start,end,text)
        ass.append(f'Dialogue: 0,{stamp(start,True)},{stamp(end,True)},Header,,0,0,0,,v5.4.0 完整操作實錄  ·  {i+1:02}/{len(ORDER):02}  {title}')
        meta.extend(['[CHAPTER]','TIMEBASE=1/1000',f'START={round(start*1000)}',f'END={round(end*1000)}','title='+title])
        middle=data[len(data)//2]['file'];ledger.append({'key':key,'title':title,'start':round(start,6),'duration':round(duration,6),'capture_seconds_edited':round(base,6),'reading_hold':round(duration-base,6),'frames':frame_map,'caption':text,'audio_source':'actual app synthesized reply' if key in ACTUAL else 'actual continuous diagnostic audio' if key=='26' else 'added narration','middle_frame':middle,'middle_frame_sha256':hashlib.sha256((WORK/'frames'/middle).read_bytes()).hexdigest()})
        sheet.paste(Image.open(WORK/'frames'/middle).resize((450,253)),(i%4*450,i//4*280));draw.text((i%4*450+5,i//4*280+254),key+' '+title[:25],font=small,fill='white')
        current=end
    concat.append(f"file 'frames/{groups[ORDER[-1]][-1]['file']}'")
    (WORK/'capture.ffconcat').write_text('\n'.join(concat)+'\n',encoding='utf8')
    combined=np.concatenate(pcm);assert np.isfinite(combined).all() and np.max(np.abs(combined))<1
    with wave.open(str(WORK/'narration.wav'),'wb') as out:
        out.setnchannels(1);out.setsampwidth(2);out.setframerate(48000);out.writeframes((combined*32767).astype('<i2').tobytes())
    original=(ROOT/'tools/build_full_recording.py').read_text(encoding='utf8');styles=original.split("    header='''",1)[1].split("'''",1)[0].replace('Caption,Microsoft JhengHei,28','Caption,Microsoft JhengHei,25')
    ass.append(f'Dialogue: 1,0:00:00.00,{stamp(current,True)},Notice,,0,0,0,,示範帳號・操作剪輯與閱讀停格・語音測試非實體麥克風')
    (WORK/'full-flow.ass').write_text(styles+'\n'.join(ass)+'\n',encoding='utf-8-sig')
    (WORK/'chapters.ffmetadata').write_text('\n'.join(meta)+'\n',encoding='utf8');(DEST/(NAME+'.zh-TW.srt')).write_text('\n'.join(srt),encoding='utf8')
    sheet.save(WORK/'selected-captures-review.jpg',quality=92)
    manifest={'version':'5.4.0','format':'edited actual CUA browser captures with added narration, reading holds and actual app synthesized dialogue audio','continuous_unedited':False,'continuous_voice_take_wallclock_preserved':True,'private_local_only':True,'physical_microphone_tested':False,'synthetic_accounts':True,'duration':round(current,6),'scenes':ledger}
    (WORK/'edit-ledger.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf8')
    print(json.dumps({'duration':current,'chapters':len(ledger),'peak':float(np.max(np.abs(combined)))}),flush=True)

def render():
    manifest=json.loads((WORK/'edit-ledger.json').read_text(encoding='utf8'))
    command=[str(FF),'-y','-v','warning','-f','concat','-safe','0','-i','capture.ffconcat','-i','narration.wav','-i','chapters.ffmetadata',
      '-map','0:v:0','-map','1:a:0','-map_metadata','2','-map_chapters','2','-vf','scale=1640:924:flags=lanczos,pad=1920:1080:140:70:color=0xf1f5f7,fps=30,ass=full-flow.ass:fontsdir=fonts',
      '-c:v','libx264','-preset','veryfast','-crf','18','-threads','4','-r','30','-pix_fmt','yuv420p','-c:a','aac','-b:a','160k','-ar','48000','-t',str(manifest['duration']),'-movflags','+faststart',str(DEST/(NAME+'.mp4'))]
    with (WORK/'encode.log').open('w',encoding='utf8') as log:subprocess.run(command,cwd=WORK,stdout=log,stderr=log,check=True)

if __name__=='__main__':
    if '--render-only' not in sys.argv:build()
    if '--prepare-only' not in sys.argv:render()
