"""Probe every pre-generated film and create a source-only visual review sheet."""
from pathlib import Path
import concurrent.futures,hashlib,json,subprocess
import numpy as np
from PIL import Image,ImageDraw,ImageFont
ROOT=Path(__file__).resolve().parents[1]
FF=ROOT/'tools/ffmpeg/ffmpeg-9.0.2-essentials_build/bin/ffmpeg.exe';PROBE=FF.with_name('ffprobe.exe')
OUT=ROOT/'runtime/verification-5.6.0';OUT.mkdir(exist_ok=True)
def inspect(item):
    row,module=item;p=ROOT/'data/public_lectures'/module['file']
    d=json.loads(subprocess.check_output([str(PROBE),'-v','error','-show_streams','-show_format','-of','json',str(p)]))
    v=next(s for s in d['streams'] if s['codec_type']=='video');a=next(s for s in d['streams'] if s['codec_type']=='audio')
    assert v['codec_name']=='h264' and v['pix_fmt']=='yuv420p' and a['codec_name']=='aac',p
    assert abs(float(d['format']['duration'])-module['duration'])<.15,p
    pcm=np.frombuffer(subprocess.check_output([str(FF),'-v','error','-i',str(p),'-t','5','-f','f32le','-ar','16000','-ac','1','pipe:1']),dtype='<f4')
    rms=float(np.sqrt(np.mean(pcm**2)));assert rms>.003,p
    frame=None
    if module['module']==0:
        frame=OUT/f"lecture-{row['id']}.jpg"
        subprocess.run([str(FF),'-y','-v','error','-ss','2','-i',str(p),'-frames:v','1','-q:v','3',str(frame)],check=True)
    return {'id':row['id'],'actor':row['actor_id'],'file':module['file'],'duration':float(d['format']['duration']),'audio_rms_first_5s':rms,'video':v['codec_name'],'audio':a['codec_name'],'frame':str(frame) if frame else None,'sha256':hashlib.sha256(p.read_bytes()).hexdigest()}
def main():
    rows=json.loads((ROOT/'data/public_lectures/catalog.json').read_text(encoding='utf8'))['lectures']
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:results=list(pool.map(inspect,[(r,m) for r in rows for m in r['modules']]))
    frames=[r for r in results if r['frame']];sheet=Image.new('RGB',(1920,((len(frames)+3)//4)*300),'#173e4d');draw=ImageDraw.Draw(sheet);font=ImageFont.truetype('C:/Windows/Fonts/msjh.ttc',16)
    for i,r in enumerate(frames):
        sheet.paste(Image.open(r['frame']).resize((480,270)),(i%4*480,i//4*300));draw.text((i%4*480+6,i//4*300+274),r['actor']+' '+r['id'][:8],font=font,fill='white')
    sheet.save(OUT/'lecture-library-contact-sheet.jpg',quality=94)
    (OUT/'lecture-media-check.json').write_text(json.dumps({'passed':True,'films':len(results),'masters':len(frames),'results':results},ensure_ascii=False,indent=2),encoding='utf8')
    print(json.dumps({'passed':True,'films':len(results),'masters':len(frames),'minimum_rms':min(r['audio_rms_first_5s'] for r in results)}))
if __name__=='__main__':main()
