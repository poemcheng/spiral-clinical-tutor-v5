"""Independent checks for private full-frame EPA evidence, without learner data."""
from pathlib import Path
import gzip, hashlib, json, math, subprocess, sys, time
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from backend import epa_library as e, pose_analysis as p, teaching_media as media

def verify():
    started=time.time();items=e.catalog()['analyses'];clips={c['id']:c for c in media.manifest()['clips']}
    assert len(items)==11 and {x['clip_id'] for x in items}==set(clips), 'Incomplete video catalog'
    assert p.digest(p.MODEL)==p.MODEL_SHA256
    ff=ROOT/'tools/ffmpeg/ffmpeg-9.0.2-essentials_build/bin/ffprobe.exe'
    output=[]
    for item in items:
        cid=item['clip_id'];clip,item,index,folder=e.analysis(cid)
        probe=json.loads(subprocess.check_output([str(ff),'-v','error','-select_streams','v:0','-show_entries','stream=nb_frames,avg_frame_rate,duration','-of','json',str(media.path_for(clip))]))['streams'][0]
        assert int(probe['nb_frames'])==index['frame_count']==item['frame_count']
        assert index['first_frame']==0 and index['last_frame']==item['frame_count']-1
        assert index['analyzed_every_frame'] and index['complete']
        assert p.digest(folder/'result.json')==index['result_sha256']
        if clip['projection']!='flat':
            assert item['view']['yaw']==(150 if cid=='team360-3' else 180)
            assert item['view']['pitch']==-10
        files={x.name for x in folder.iterdir() if x.suffix=='.jpg'}
        count=0;detections=0;pose_count=0
        for part in index['chunks']:
            raw=(folder/part['file']).read_bytes()
            assert hashlib.sha256(raw).hexdigest()==part['sha256']
            frames=json.loads(gzip.decompress(raw))
            assert frames[0]['frame']==part['first'] and frames[-1]['frame']==part['last']
            for f in frames:
                n=f['frame'];assert n==count
                assert abs(f['seconds']-n/item['fps'])<.00001
                assert f'raw-frame-{n}.jpg' in files and f'frame-{n}.jpg' in files
                detections+=bool(f['poses'])
                for pose in f['poses']:
                    points=pose['landmarks'];assert len(points)==33
                    assert all(math.isfinite(point[k]) for point in points for k in ('x','y','z','presence','visibility'))
                    calculated,tags=p.metrics(points,item['view']['width'],item['view']['height'])
                    assert all(pose['metrics'].get(k)==v for k,v in calculated.items()) and tags==pose['actions'],f'Measurement mismatch {cid}/{n}'
                    pose_count+=1
                count+=1
        assert count==index['frame_count'] and detections==index['detection_frames']
        assert len(files)==2*count
        report=e.report(cid);notes=e.annotations(cid)
        for segment in report['segments']:
            assert 0<=segment['start']<segment['end']<=clip['duration']+.01
            assert all(segment.get(k) for k in ('visible_action','dialogue_function','action_dialogue_relation','category','epa_focus','purpose'))
        for key in report['keyframes']:
            assert 0<=key['frame']<count
            frame=e.frame(cid,key['frame'])
            assert frame['frame']==key['frame'] and frame['source_sha256']==item['source_sha256']
        if cid=='epa-bedside':
            assert len(report['segments'])==14 and len(report['keyframes'])==18
            assert all(key.get('qualitative_pose') for key in report['keyframes'])
        row={'clip':cid,'title':clip['title'],'frames':count,'detection_frames':detections,'candidate_poses':pose_count,'segments':len(report['segments']),'representative_frames':len(report['keyframes']),'source_sha256':item['source_sha256'],'analysis_id':item['id'],'projection':clip['projection'],'view':item['view']}
        output.append(row);print(json.dumps(row,ensure_ascii=False),flush=True)
    totals={'clips':len(output),'frames':sum(x['frames'] for x in output),'segments':sum(x['segments'] for x in output),'representative_frames':sum(x['representative_frames'] for x in output)}
    assert totals=={'clips':11,'frames':104637,'segments':76,'representative_frames':88},totals
    data={'passed':True,'version':'5.6.1','seconds':round(time.time()-started,2),'checks':['source and model SHA256','ffprobe full frame counts','all compressed chunk hashes','consecutive every-frame timestamps','all 209274 raw and overlay JPEG files','all finite 33-landmark candidates','all visibility-gated 2D angles and action prompts recomputed','corrected fixed panoramic view','segment bounds and source EPA qualitative keyframes'],'totals':totals,'videos':output}
    target=ROOT/'runtime/epa-source-review/library-verification.json';target.write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf8')
    print(json.dumps({'passed':True,**totals,'seconds':data['seconds']},ensure_ascii=False))

if __name__=='__main__':verify()
