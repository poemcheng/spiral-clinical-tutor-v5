"""Render actual CUA UI captures with narration; never synthesize application UI.

The public edition masks original teaching pixels. Voice keeps its actual audio
and wall-clock wait, with sparse capture gaps explicitly reported in the ledger.
"""
from pathlib import Path
from collections import OrderedDict
import hashlib,json,shutil,subprocess,sys,wave
import numpy as np
from PIL import Image,ImageDraw,ImageFont

ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from backend.virtual_video import speech
from tools.build_full_recording import stamp
WORK=ROOT/'runtime/recording-v5.6.1';DEST=ROOT/'docs/v5.6'
RUNTIME=WORK/'isolated-runtime'
FF=ROOT/'tools/ffmpeg/ffmpeg-9.0.2-essentials_build/bin/ffmpeg.exe'

def decode(path):
    return np.frombuffer(subprocess.check_output([str(FF),'-v','error','-i',str(path),'-f','f32le','-ar','48000','-ac','1','pipe:1']),dtype='<f4').copy()

def build():
    DEST.mkdir(exist_ok=True)
    for folder in ('narration','fonts','local-frames','public-frames'):(WORK/folder).mkdir(exist_ok=True)
    shutil.copyfile('C:/Windows/Fonts/msjh.ttc',WORK/'fonts/guide.ttc')
    source=[json.loads(s) for s in (WORK/'frames.jsonl').read_text(encoding='utf8').splitlines()]
    assert len({f['file'] for f in source})==len(source),'Capture filenames must be unique'
    groups=OrderedDict()
    for f in sorted(source,key=lambda f:(int(f['chapter'].split(' ',1)[0]),f['seconds'])):
        groups.setdefault(f['chapter'].split(' ',1)[0],[]).append(f)
    voice=json.loads((WORK/'voice-report.json').read_text(encoding='utf8'));assert voice['passed'] and not voice['physicalMicrophoneTested']
    voice_anchor=json.loads((WORK/'voice-start.json').read_text(encoding='utf8'))['seconds']
    font=ImageFont.truetype('C:/Windows/Fonts/msjh.ttc',26);small=ImageFont.truetype('C:/Windows/Fonts/msjh.ttc',17)
    concat={kind:['ffconcat version 1.0'] for kind in ('local','public')}
    ass=[];srt=[];meta=[';FFMETADATA1'];ledger=[];pcm=[];current=0
    sheet=Image.new('RGB',(1800,((len(groups)+3)//4)*280),'#173e4d');sd=ImageDraw.Draw(sheet)
    def caption(start,end,text):
        lines=['']
        for ch in text:
            if font.getlength(lines[-1]+ch)>1720:lines.append('')
            lines[-1]+=ch
        ass.append(f'Dialogue: 0,{stamp(start,True)},{stamp(end,True)},Caption,,0,0,0,,'+r'\N'.join(lines))
        srt.append(f'{len(srt)+1}\n{stamp(start)} --> {stamp(end)}\n{text}\n')
    for i,(key,data) in enumerate(groups.items()):
        title=data[0]['chapter'].split(' ',1)[1];text=data[-1]['narration']
        intervals=[max(1/30,min(1.2,b['seconds']-a['seconds'])) for a,b in zip(data,data[1:])]
        tail=.4;placements=[];subcaptions=[]
        if key=='29':
            origin=data[0]['seconds'];offset=voice_anchor-origin
            intervals=[max(1/30,b['seconds']-a['seconds']) for a,b in zip(data,data[1:])]
            duration=max(sum(intervals)+tail,offset+voice['events'][-1]['ms']/1000+.6)
            for event in voice['events']:
                at=offset+event['ms']/1000;turn=event.get('turn',1)
                if event['kind'] in ('listening','resumed'):
                    if turn not in (1,2):continue
                    samples=decode(RUNTIME/'voice-diagnostics'/f'input-{turn}.wav');placements.append((at+.2,samples))
                    subcaptions.append((at+.2,at+.2+len(samples)/48000,'測試學員音源：'+voice['rounds'][turn-1]['expected']))
                if event['kind']=='playback-started':
                    samples=decode(next((RUNTIME/'voice-diagnostics').glob(f'*-1-{voice["testId"]}-{turn}.wav')));placements.append((at,samples))
                    subcaptions.append((at,at+len(samples)/48000,'角色實際回覆：'+voice['rounds'][turn-1]['reply']['text']))
            text='原速兩輪實際語音鏈測試；畫面為間隔擷取，保留實際等待。受控合成輸入，不是實體麥克風驗收。'
        else:
            sound=WORK/'narration'/f'{key}.wav';speech(text,sound,'female')
            samples=decode(sound);placements=[(.15,samples)];duration=max(sum(intervals)+tail,len(samples)/48000+.65)
        base=sum(intervals)+tail;duration=np.ceil(duration*30)/30
        audio=np.zeros(round(duration*48000),dtype=np.float32)
        for at,samples in placements:
            clip=max(0,-round(at*48000));start=max(0,round(at*48000));n=min(len(samples)-clip,len(audio)-start)
            if n>0:audio[start:start+n]+=samples[clip:clip+n]
        pcm.append(audio);durations=[*intervals,tail+duration-base];frame_map=[];local=0
        for f,d in zip(data,durations):
            path=WORK/'frames'/f['file'];raw=Image.open(path).convert('RGB')
            masks=list(f.get('masks',[]))
            # Captured DOM rectangles are CSS pixels; screenshots include the
            # browser's 1280→1265 / 390→375 viewport scaling. Native <video>
            # elements with blob URLs also require the adjacent original panel.
            if key in ('10','11','12','15','43','44') and masks:
                first=masks[0];masks.append({**first,'x':first['x']+first['width']+20,'height':max(first['height'],first['width']*.75)})
            if key=='68' and masks:
                first=masks[0];masks.append({**first,'y':first['y']+first['height']+100,'height':first['width']*.75})
            css_scale=raw.width/(390 if raw.width<600 else 1280)
            masks=[{k:v*css_scale for k,v in m.items()} for m in masks]
            for kind in concat:
                im=raw.copy();dr=ImageDraw.Draw(im)
                if kind=='public':
                    for m in masks:
                        box=(max(0,int(m['x'])-10),max(0,int(m['y'])-10),min(im.width,int(m['x']+m['width'])+11),min(im.height,int(m['y']+m['height'])+11))
                        if box[2]>box[0] and box[3]>box[1]:
                            dr.rectangle(box,fill='#173e4d')
                            if box[2]-box[0]>220 and box[3]-box[1]>42:dr.text((box[0]+8,box[1]+10),'原始教材影像僅於本機版顯示',font=small,fill='white')
                canvas=Image.new('RGB',(1920,1080),'#f1f5f7');scale=min(1720/im.width,880/im.height)
                size=(round(im.width*scale),round(im.height*scale));canvas.paste(im.resize(size,Image.Resampling.LANCZOS),((1920-size[0])//2,88))
                canvas.save(WORK/f'{kind}-frames'/f['file'])
                concat[kind].extend([f"file '{kind}-frames/{f['file']}'",f'duration {d:.6f}'])
            frame_map.append({'file':f['file'],'source_seconds':f['seconds'],'offset':round(local,6),'duration':round(d,6),'sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'masks':masks});local+=d
        start=current;end=start+duration
        if subcaptions:
            for a,b,txt in subcaptions:caption(start+max(0,a),min(end,start+b),txt)
        else:caption(start,end,text)
        ass.append(f'Dialogue: 0,{stamp(start,True)},{stamp(end,True)},Header,,0,0,0,,v5.6.1 完整操作實錄  ·  {i+1:02}/{len(groups):02}  {title}')
        if key=='29':ass.append(f'Dialogue: 1,{stamp(start,True)},{stamp(end,True)},Voice,,0,0,0,,原速語音 · 實際等待保留 · 畫面間隔擷取 · 男性角色男聲')
        meta.extend(['[CHAPTER]','TIMEBASE=1/1000',f'START={round(start*1000)}',f'END={round(end*1000)}','title='+title])
        middle=data[len(data)//2]['file'];ledger.append({'key':key,'title':title,'start':round(start,6),'duration':round(duration,6),'reading_hold':round(duration-base,6),'frames':frame_map,'caption':text,'audio_source':'actual continuous diagnostic' if key=='29' else 'added narration','max_capture_gap_seconds':max([b['seconds']-a['seconds'] for a,b in zip(data,data[1:])],default=0),'middle_frame':middle})
        sheet.paste(Image.open(WORK/'public-frames'/middle).resize((450,253)),(i%4*450,i//4*280));sd.text((i%4*450+5,i//4*280+254),key+' '+title[:25],font=small,fill='white');current=end
        print(f'prepared {key} {duration:.1f}s',flush=True)
    for kind,lines in concat.items():
        lines.append(f"file '{kind}-frames/{source[-1]['file']}'");(WORK/f'capture-{kind}.ffconcat').write_text('\n'.join(lines)+'\n',encoding='utf8')
    combined=np.concatenate(pcm);assert np.isfinite(combined).all() and np.max(np.abs(combined))<1
    with wave.open(str(WORK/'narration.wav'),'wb') as out:
        out.setnchannels(1);out.setsampwidth(2);out.setframerate(48000);out.writeframes((combined*32767).astype('<i2').tobytes())
    styles='''[Script Info]
ScriptType: v4.00+
PlayResX: 1920
PlayResY: 1080
WrapStyle: 2
[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Header,Microsoft JhengHei,30,&H004D3E17,&H004D3E17,&H00FFFFFF,&H00FFFFFF,1,0,0,0,100,100,0,0,1,0,0,8,60,60,14,1
Style: Caption,Microsoft JhengHei,26,&H004D3E17,&H004D3E17,&H00F7F5F1,&H00F7F5F1,0,0,0,0,100,100,0,0,1,2,0,2,85,85,16,1
Style: Notice,Microsoft JhengHei,18,&H006E6657,&H006E6657,&H00FFFFFF,&H00FFFFFF,0,0,0,0,100,100,0,0,1,0,0,8,40,40,55,1
Style: Voice,Microsoft JhengHei,18,&H004D3E17,&H004D3E17,&H00FFFFFF,&H00FFFFFF,1,0,0,0,100,100,0,0,1,1,0,9,20,20,78,1
[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
'''
    for kind in concat:
        notice='公開版・原始教材影像遮蔽' if kind=='public' else '本機完整影像版・原始教材請勿公開'
        extra=f'Dialogue: 1,0:00:00.00,{stamp(current,True)},Notice,,0,0,0,,獨立示範資料・實際畫面擷取／剪輯與閱讀停格・{notice}'
        (WORK/f'full-flow-{kind}.ass').write_text(styles+'\n'.join(ass)+'\n'+extra+'\n',encoding='utf-8-sig')
    (WORK/'chapters.ffmetadata').write_text('\n'.join(meta)+'\n',encoding='utf8')
    (DEST/'v5.6.1-full-workflow.zh-TW.srt').write_text('\n'.join(srt),encoding='utf8')
    (DEST/'v5.6.1-full-workflow.zh-TW.vtt').write_text('WEBVTT\n\n'+'\n'.join(srt).replace(',','.'),encoding='utf8')
    sheet.save(WORK/'selected-captures-review.jpg',quality=92)
    manifest={'version':'5.6.1','format':'edited actual CUA browser captures; added narration, reading holds and explicitly disclosed sparse capture in actual voice take','continuous_voice_take_wallclock_preserved':True,'physical_microphone_tested':False,'synthetic_accounts':True,'duration':round(current,6),'source_captures':len(source),'scenes':ledger}
    (WORK/'edit-ledger.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf8')
    (DEST/'v5.6.1-full-workflow-chapters.json').write_text(json.dumps([{'title':s['title'],'start':s['start'],'duration':s['duration']} for s in ledger],ensure_ascii=False,indent=2),encoding='utf8')
    print(json.dumps({'duration':current,'chapters':len(ledger),'peak':float(np.max(np.abs(combined)))}),flush=True)

def render():
    manifest=json.loads((WORK/'edit-ledger.json').read_text(encoding='utf8'))
    for kind in (('public',) if '--public-only' in sys.argv else ('local','public')):
        cmd=[str(FF),'-y','-v','warning','-f','concat','-safe','0','-i',f'capture-{kind}.ffconcat','-i','narration.wav','-i','chapters.ffmetadata','-map','0:v:0','-map','1:a:0','-map_metadata','2','-map_chapters','2','-vf',f'fps=30,ass=full-flow-{kind}.ass:fontsdir=fonts','-c:v','libx264','-preset','veryfast','-crf','20','-threads','4','-r','30','-pix_fmt','yuv420p','-c:a','aac','-b:a','160k','-ar','48000','-t',str(manifest['duration']),'-movflags','+faststart',str(DEST/f'v5.6.1-full-workflow-{kind}.mp4')]
        with (WORK/f'encode-{kind}.log').open('w',encoding='utf8') as log:subprocess.run(cmd,cwd=WORK,stdout=log,stderr=log,check=True)
        print('rendered',kind,flush=True)

if __name__=='__main__':
    if '--render-only' not in sys.argv:build()
    if '--prepare-only' not in sys.argv:render()
