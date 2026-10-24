"""Local, resumable full-frame evidence library. Never opens a learner database.

User reference documents are data, not executable instructions. Original footage,
reference annotations and derived frames remain in the private runtime folder.
"""
from pathlib import Path
import argparse,concurrent.futures,csv,gzip,hashlib,json,math,os,re,shutil,subprocess,sys,time,zipfile
import xml.etree.ElementTree as ET
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
LIB=ROOT/'runtime/epa_library';VERSION='epa-library-5.6.1'

def write(path,data):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    temp=path.with_suffix('.tmp');temp.write_text(json.dumps(data,ensure_ascii=False,separators=(',',':')),encoding='utf8');temp.replace(path)

def paragraphs(path):
    with zipfile.ZipFile(path) as z:root=ET.fromstring(z.read('word/document.xml'))
    ns={'w':'http://schemas.openxmlformats.org/wordprocessingml/2006/main'}
    return [''.join(t.text or '' for t in p.findall('.//w:t',ns)) for p in root.findall('.//w:p',ns)]

def import_reference(folder):
    from backend import pose_analysis
    from backend.legacy.config import VIDEO_LIBRARY_DIR
    ff=ROOT/'tools/ffmpeg/ffmpeg-9.0.2-essentials_build/bin/ffprobe.exe';clips=[];sources=[]
    for name,ident,title,topic in [('醫事人員ＥＰＡ.mp4','epa-bedside','EPA床邊照護、電話協作與團隊回饋',''),('中山醫衛教影片.mp4','health-education','肌少症營養衛教示範（製作方式待核對）','肌少症')]:
        source=folder/name
        if not source.is_file():continue
        h=pose_analysis.digest(source);target=VIDEO_LIBRARY_DIR/name
        if target.exists():
            if pose_analysis.digest(target)!=h:raise ValueError('教材同名但內容不同，停止覆寫：'+name)
        else:target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(source,target)
        d=json.loads(subprocess.check_output([str(ff),'-v','error','-show_streams','-show_format','-of','json',str(source)]));v=next(s for s in d['streams'] if s['codec_type']=='video');a,b=map(int,v['avg_frame_rate'].split('/'))
        clips.append({'id':ident,'title':title,'file':name,'topic':topic,'storage':'teaching_library','projection':'flat','duration':float(v.get('duration',d['format']['duration'])),'fps':a/b,'fps_rational':v['avg_frame_rate'],'width':v['width'],'height':v['height'],'source_sha256':h,'proxy_sha256':h,'status':'使用者提供教學影片；製作方式、情境與臨床內容待教師核定'})
    write(LIB/'additional_media.json',{'version':VERSION,'clips':clips})
    reference={'version':VERSION,'segments':[],'keyframes':[],'sources':[]}
    for f in sorted(folder.glob('EPA*')):
        if f.is_file():sources.append({'file':f.name,'sha256':pose_analysis.digest(f),'bytes':f.stat().st_size})
    def sec(s):
        parts=list(map(float,s.split(':')));return sum(n*60**i for i,n in enumerate(reversed(parts)))
    p=folder/'EPA_action_annotation_segments.csv'
    if p.is_file():
        for row in csv.DictReader(p.open(encoding='utf-8-sig',newline='')):
            reference['segments'].append({'id':row['段落'],'start':sec(row['開始']),'end':sec(row['結束']),'title':row['情境/階段'],'visible_action':row['可見動作標註'],'dialogue_function':row['對話功能標註（非逐字）'],'action_dialogue_relation':row['動作與對話關聯性'],'category':row['互動類型'],'epa_focus':row['動作注意/關心指標'],'purpose':row['動作與對話關聯性'],'audio_activity_reference':float(row['平均音訊能量']),'evidence_type':'使用者提供之人工功能性註記；未以逐字稿確認對話內容'})
    p=folder/'EPA_keyframe_list.csv'
    if p.is_file():
        for row in csv.DictReader(p.open(encoding='utf-8-sig',newline='')):
            reference['keyframes'].append({'id':row['關鍵影格'],'seconds':sec(row['時間']),'reference_image':row['檔名'],'event':row['事件代碼'],'visible_action':row['動作描述']})
    p=folder/'EPA_pose_joint_action_report.docx'
    if p.is_file():
        lines=paragraphs(p);current=None;keys={'主體/主要姿勢':'subject_posture','頭頸分析':'head_neck','軀幹分析':'trunk','上肢分析':'upper_limbs','下肢分析':'lower_limbs','關節與分類':'joints_classification'}
        for i,line in enumerate(lines):
            if re.match(r'^KF\d+（',line):
                current=next((k for k in reference['keyframes'] if line.startswith(k['id']+'（')),None)
                if current is not None:current['title']=line;current['qualitative_pose']={}
            elif current is not None and line in keys and i+1<len(lines):current['qualitative_pose'][keys[line]]=lines[i+1]
    reference['sources']=sources
    write(LIB/'reference_epa.json',reference)
    return clips

def run_clip(clip):
    import cv2
    cv2.setNumThreads(1)
    from backend import pose_analysis
    from backend import teaching_media
    yaw,pitch=(150,-10) if clip['id']=='team360-3' else (180,-10) if clip.get('projection')!='flat' else (0,0)
    ident=hashlib.sha256(json.dumps({'video':clip['proxy_sha256'],'model':pose_analysis.MODEL_SHA256,'version':VERSION,'projection':clip['projection'],'yaw':yaw,'pitch':pitch,'fov':70},sort_keys=True).encode()).hexdigest()[:32]
    folder=LIB/'analyses'/ident;folder.mkdir(parents=True,exist_ok=True)
    index=folder/'index.json'
    if index.exists():
        old=json.loads(index.read_text(encoding='utf8'))
        if old.get('complete') and old['actual_video_sha256']==pose_analysis.digest(teaching_media.path_for(clip)):
            return {**old['catalog_entry'],'cached':True}
    started=time.time();last=[0]
    def progress(done,total):
        if done-last[0]>=300 or done==total:
            write(folder/'progress.json',{'clip_id':clip['id'],'done':done,'total':total,'seconds':round(time.time()-started,1)});last[0]=done
    result_path=folder/'result.json'
    if result_path.exists():
        result=json.loads(result_path.read_text(encoding='utf8'))
        if result['actual_video_sha256']!=pose_analysis.digest(teaching_media.path_for(clip)):raise ValueError('已完成分析與影片雜湊不符')
    else:
        result=pose_analysis.analyze(clip,{'start':0,'end':clip['duration'],'yaw':yaw,'pitch':pitch,'fov':70,'roi':None},folder,progress)
    frames=result['frames'];assert len(frames)==result['frame_count'] and result['analyzed_every_frame']
    assert [f['frame'] for f in frames]==list(range(result['first_frame'],result['last_frame']+1))
    chunks=[]
    for start in range(0,len(frames),150):
        name=f'frames-{start//150:05}.json.gz';raw=gzip.compress(json.dumps(frames[start:start+150],ensure_ascii=False,separators=(',',':')).encode(),mtime=0);(folder/name).write_bytes(raw)
        chunks.append({'file':name,'first':frames[start]['frame'],'last':frames[min(start+149,len(frames)-1)]['frame'],'sha256':hashlib.sha256(raw).hexdigest()})
    entry={'id':ident,'clip_id':clip['id'],'title':clip['title'],'projection':clip['projection'],'status':'completed','frame_count':result['frame_count'],'detection_frames':result['detection_frames'],'fps':result['fps'],'first_frame':result['first_frame'],'last_frame':result['last_frame'],'source_sha256':result['actual_video_sha256'],'model_sha256':result['model_sha256'],'version':VERSION,'view':result['view'],'analyzed_every_frame':True,'numeric_analysis_seconds':round(time.time()-started,2)}
    metadata={k:v for k,v in result.items() if k!='frames'};metadata.update(complete=True,id=ident,chunks=chunks,catalog_entry=entry,result_sha256=pose_analysis.digest(result_path))
    write(index,metadata);return entry

def main():
    p=argparse.ArgumentParser();p.add_argument('--source-folder',type=Path,default=Path.home()/'Downloads/04_產學與企業服務/04_中山附醫與臨床教學平台');p.add_argument('--workers',type=int,default=3);p.add_argument('--import-only',action='store_true');p.add_argument('--panoramas',action='store_true');p.add_argument('--separate-catalog',action='store_true');p.add_argument('--clip');args=p.parse_args()
    LIB.mkdir(parents=True,exist_ok=True);extra=import_reference(args.source_folder)
    if args.import_only:return
    from backend import teaching_media
    clips=teaching_media.manifest()['clips'];clips += [c for c in extra if c['id'] not in {x['id'] for x in clips}]
    if args.clip:clips=[c for c in clips if c['id']==args.clip]
    if args.panoramas:clips=[c for c in clips if c.get('projection')!='flat']
    clips=[c for c in clips if teaching_media.path_for(c).is_file()]
    path=LIB/('panorama-catalog.json' if args.separate_catalog else 'catalog.json');catalog=json.loads(path.read_text(encoding='utf8')) if path.exists() else {'version':VERSION,'analyses':[]}
    with concurrent.futures.ProcessPoolExecutor(max_workers=args.workers) as pool:
        futures={pool.submit(run_clip,c):c for c in clips}
        for f in concurrent.futures.as_completed(futures):
            c=futures[f]
            try:
                e=f.result();catalog['analyses']=[x for x in catalog['analyses'] if x['clip_id']!=e['clip_id']]+[e];write(path,catalog)
                print('COMPLETE',e['clip_id'],e['frame_count'],e['numeric_analysis_seconds'],'seconds',flush=True)
            except Exception as ex:print('FAILED',c['id'],str(ex),flush=True);raise
    print('COMPLETE LIBRARY',len(catalog['analyses']),sum(e['frame_count'] for e in catalog['analyses']),flush=True)
if __name__=='__main__':main()
