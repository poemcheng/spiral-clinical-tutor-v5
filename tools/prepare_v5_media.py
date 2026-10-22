"""Create browser-compatible H.264 spherical proxies; preserve all original files."""
from pathlib import Path
import hashlib,json,subprocess
ROOT=Path(__file__).resolve().parents[1]
BIN=ROOT/'tools/ffmpeg/ffmpeg-9.0.2-essentials_build/bin'
OUT=ROOT/'data/video360';OUT.mkdir(exist_ok=True)
clips=[]
for index,p in enumerate(sorted((ROOT.parent/'AI醫學教案/AI360video').glob('*.mp4')),1):
    data=json.loads(subprocess.check_output([str(BIN/'ffprobe.exe'),'-v','quiet','-show_format','-show_streams','-of','json',str(p)]))
    stream=next(s for s in data['streams'] if s['codec_type']=='video')
    num,den=map(int,stream['r_frame_rate'].split('/'))
    file=f'team360-{index}.mp4';target=OUT/file
    if not target.exists():subprocess.run([str(BIN/'ffmpeg.exe'),'-hide_banner','-loglevel','error','-y','-i',str(p),'-vf','scale=1920:960','-c:v','libx264','-preset','veryfast','-crf','26','-pix_fmt','yuv420p','-threads','2','-c:a','aac','-b:a','96k','-movflags','+faststart',str(target)],check=True)
    clips.append({'id':f'team360-{index}','title':f'跨團隊360觀察教材 {index}','file':file,'duration':float(data['format']['duration']),'fps':num/den,'fps_rational':stream['r_frame_rate'],'status':'情境與職類配對待教師核定','projection':'equirectangular','source_file':p.name,'source_sha256':hashlib.file_digest(p.open('rb'),'sha256').hexdigest(),'proxy_sha256':hashlib.file_digest(target.open('rb'),'sha256').hexdigest(),'original_dimensions':[stream['width'],stream['height']]})
    subprocess.run([str(BIN/'ffmpeg.exe'),'-hide_banner','-loglevel','error','-y','-ss','5','-i',str(target),'-frames:v','1',str(OUT/f'team360-{index}-preview.jpg')],check=True)
    print(f'Prepared {file}',flush=True)
(OUT/'catalog.json').write_text(json.dumps({'version':'v5-360-20261022','clips':clips},ensure_ascii=False,indent=2),encoding='utf-8')
