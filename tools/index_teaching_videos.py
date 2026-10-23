"""Index approved local teaching videos; never copy their pixels into public assets."""
import json,hashlib,subprocess,shutil,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from backend.legacy.config import VIDEO_LIBRARY_DIR

def main():
    probe=shutil.which('ffprobe') or str(ROOT/'tools/ffmpeg/ffmpeg-9.0.2-essentials_build/bin/ffprobe.exe')
    courses=json.loads((ROOT/'data/course_catalog.json').read_text(encoding='utf-8'))['courses']
    inputs=[(c['id'].lower()+'-video',c['video_file'],c['topic'],c['id']) for c in courses if c['video_file']]
    inputs.append(('sarc-analysis','肌少症教案-影片分析.mp4','肌少症','COURSE-SARC'))
    clips=[]
    for ident,name,topic,course in inputs:
        path=(VIDEO_LIBRARY_DIR/name).resolve()
        if not path.is_relative_to(VIDEO_LIBRARY_DIR.resolve()) or not path.is_file():continue
        j=json.loads(subprocess.check_output([probe,'-v','error','-show_format','-show_streams','-of','json',str(path)]))
        s=next(x for x in j['streams'] if x['codec_type']=='video');num,den=map(int,s['r_frame_rate'].split('/'))
        with path.open('rb') as f:digest=hashlib.file_digest(f,'sha256').hexdigest()
        clips.append({'id':ident,'title':path.stem,'file':name,'topic':topic,'course_id':course,'storage':'teaching_library',
          'projection':'flat','duration':float(j['format']['duration']),'fps':num/den,'fps_rational':s['r_frame_rate'],
          'width':s['width'],'height':s['height'],'source_sha256':digest,'proxy_sha256':digest,
          'status':'原始一般影片；動作與臨床解析須分別核對'})
    dest=ROOT/'data/action_lessons';dest.mkdir(exist_ok=True)
    (dest/'media_catalog.json').write_text(json.dumps({'version':'teaching-media-5.3.2','clips':clips},ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({'indexed':len(clips),'private_footage_copied':False}))
if __name__=='__main__':main()
