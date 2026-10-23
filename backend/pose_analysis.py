"""Local, frame-by-frame pose evidence. Intent suggestions are hypotheses, never labels."""
import hashlib
import json
import math
from pathlib import Path
import threading
from .config import ROOT, RUNTIME
from . import teaching_media

VERSION = 'pose-evidence-5.3.2'
MODEL = ROOT / 'runtime/models/pose_landmarker_full.task'
MODEL_URL = 'https://storage.googleapis.com/mediapipe-models/pose_landmarker/pose_landmarker_full/float16/1/pose_landmarker_full.task'
MODEL_SHA256 = '5134a3aad27a58b93da0088d431f366da362b44e3ccfbe3462b3827a839011b1'
LOCK = threading.Lock()
EDGES = [(11,12),(11,13),(13,15),(12,14),(14,16),(11,23),(12,24),(23,24),(23,25),(25,27),(24,26),(26,28)]
LIMITATION = '骨架是單鏡頭估計；遮擋、多人重疊與球面接縫會造成誤差。角度為二維投影，不能當作臨床量測。意圖僅列可能解釋，須結合前後畫面、語音及當事人確認。'


def digest(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        for block in iter(lambda:f.read(1024*1024),b''):h.update(block)
    return h.hexdigest()


def availability():
    try:
        import importlib.util
        installed=bool(importlib.util.find_spec('mediapipe') and importlib.util.find_spec('cv2'))
    except (ImportError,ValueError):installed=False
    return {'ready':installed and MODEL.is_file(),'version':VERSION,
            'model_installed':MODEL.is_file(),'dependencies_installed':installed,
            'setup':'python tools/setup_pose.py','limitation':LIMITATION}


def projection_maps(width,height,yaw,pitch,fov=70,out_width=640,out_height=480):
    """Match panorama.js sphere UV and lookAt convention; yaw=0 faces the UV seam."""
    import numpy as np
    # Image y grows down; panorama.js pitch grows upward; camera right is +Z at yaw=0.
    theta=math.radians(yaw);phi=math.radians(pitch)
    forward=np.array([math.cos(phi)*math.cos(theta),math.sin(phi),math.cos(phi)*math.sin(theta)])
    right=np.array([-math.sin(theta),0,math.cos(theta)])
    up=np.cross(right,forward)
    xx=(np.arange(out_width)+.5)/out_width*2-1
    yy=1-(np.arange(out_height)+.5)/out_height*2
    scale=math.tan(math.radians(fov)/2)
    rays=forward+xx[None,:,None]*scale*(out_width/out_height)*right+yy[:,None,None]*scale*up
    rays/=np.linalg.norm(rays,axis=2,keepdims=True)
    # SphereGeometry after scale(-1,1,1): u=atan2(z,x)/(2pi), v=acos(y)/pi.
    mx=(np.arctan2(rays[:,:,2],rays[:,:,0])/(2*math.pi)%1)*width-.5
    my=np.arccos(np.clip(rays[:,:,1],-1,1))/math.pi*height-.5
    return mx.astype('float32'),my.astype('float32')


def visible(p):
    return p['visibility']>=.65 and p['presence']>=.65 and 0<=p['x']<=1 and 0<=p['y']<=1


def metrics(points,width=640,height=480):
    """Only compute measurements supported by visible joints; no hidden-joint hallucination."""
    def angle(a,b,c):
        if not all(visible(points[i]) for i in (a,b,c)):return None
        pa,pb,pc=[(points[i]['x']*width,points[i]['y']*height) for i in (a,b,c)]
        u=(pa[0]-pb[0],pa[1]-pb[1]);v=(pc[0]-pb[0],pc[1]-pb[1])
        d=math.hypot(*u)*math.hypot(*v)
        return round(math.degrees(math.acos(max(-1,min(1,sum(x*y for x,y in zip(u,v))/d)))),1) if d>1e-5 else None
    values={'left_elbow':angle(11,13,15),'right_elbow':angle(12,14,16),
            'left_knee':angle(23,25,27),'right_knee':angle(24,26,28)}
    tags=[]
    for side,shoulder,wrist in [('left',11,15),('right',12,16)]:
        if visible(points[shoulder]) and visible(points[wrist]) and points[wrist]['y']<points[shoulder]['y']-.04:
            tags.append('左手高於肩部' if side=='left' else '右手高於肩部')
    for key,title in [('left_elbow','左肘彎曲'),('right_elbow','右肘彎曲'),('left_knee','左膝彎曲'),('right_knee','右膝彎曲')]:
        if values[key] is not None and values[key]<110:tags.append(title)
    if all(visible(points[i]) for i in (11,12,23,24)):
        dx=((points[11]['x']+points[12]['x'])-(points[23]['x']+points[24]['x']))*width/2
        dy=((points[23]['y']+points[24]['y'])-(points[11]['y']+points[12]['y']))*height/2
        values['torso_tilt']=round(math.degrees(math.atan2(abs(dx),abs(dy))),1)
        if values['torso_tilt']>20:tags.append('軀幹投影偏斜')
    return values,tags


def meanings(tags):
    candidates=[]
    if any('高於肩' in t for t in tags):candidates.append({'possible':'可能在示意、發問或伸手取物','basis':'手腕高於同側肩部','alternative':'也可能為伸展或被他人協助抬手','verify':'回看手中物件、對話與對象，不直接判為求助。'})
    if any('肘彎曲' in t for t in tags):candidates.append({'possible':'可能在近身操作、持物或交談示意','basis':'可見肘部投影角度小於110°','alternative':'也可能只是休息姿勢','verify':'核對手部接觸物與前後動作；骨架不能識別操作品質。'})
    if any('膝彎曲' in t for t in tags):candidates.append({'possible':'可能處於坐姿、下蹲或轉位過程','basis':'可見膝部投影角度小於110°','alternative':'透視或遮擋也可能影響角度','verify':'回看椅子、支撐點、起止姿勢及是否需要協助。'})
    if '軀幹投影偏斜' in tags:candidates.append({'possible':'可能在轉身、側傾或配合操作位置','basis':'肩中點與髖中點的投影連線偏離畫面垂直超過20°','alternative':'攝影機傾斜、透視亦可造成相同外觀','verify':'核對攝影機方向及身體支撐；不能判定失衡或疼痛。'})
    return candidates or [{'possible':'目前無法確認特定動作意圖','basis':'可見骨架未達動作提示條件','alternative':'動作可能發生於畫面外或遭遮擋','verify':'調整視角、檢視前後影格與語音後再判讀。'}]


def assign_tracks(poses,previous,frame,fps,next_id,width=640,height=480):
    """Local track IDs, not identity or profession recognition. Reject ambiguous matches."""
    used=set()
    for pose in poses:
        p=pose['landmarks'];valid=[p[i] for i in (11,12,23,24) if visible(p[i])]
        center=(sum(x['x'] for x in valid)/len(valid),sum(x['y'] for x in valid)/len(valid)) if len(valid)>=2 else None
        candidates=sorted((math.dist(center,old['center']),tid) for tid,old in previous.items() if center and old['center'] and frame-old['frame']<=max(3,fps*.2) and tid not in used)
        match=candidates[0] if candidates and candidates[0][0]<.16 and (len(candidates)<2 or candidates[1][0]-candidates[0][0]>.04) else None
        tid=match[1] if match else next_id
        if not match:next_id+=1
        pose['track_id']=tid;pose['tracking']='局部連續追蹤' if match else '新軌跡／無法可靠接續'
        old=previous.get(tid)
        if old and frame>old['frame'] and visible(p[15]) and visible(old['landmarks'][15]):
            dt=(frame-old['frame'])/fps
            speed=math.hypot((p[15]['x']-old['landmarks'][15]['x'])*width,(p[15]['y']-old['landmarks'][15]['y'])*height)/dt
            pose['metrics']['left_wrist_px_s']=round(speed,1)
        previous[tid]={'center':center,'frame':frame,'landmarks':p};used.add(tid)
    for tid in list(previous):
        if frame-previous[tid]['frame']>fps*.2:del previous[tid]
    return next_id


def analyze(clip,params,directory,on_progress=lambda done,total:None):
    import cv2
    import mediapipe as mp
    from mediapipe.tasks.python import vision
    source=teaching_media.path_for(clip)
    if not source.is_file():raise ValueError('影片尚未安裝。')
    source_hash=digest(source)
    if clip.get('proxy_sha256') and source_hash!=clip['proxy_sha256']:raise ValueError('影片雜湊與目錄不符，請重新匯入核對。')
    if not MODEL.is_file():raise RuntimeError('骨架模型尚未安裝；請執行 python tools/setup_pose.py。')
    if digest(MODEL)!=MODEL_SHA256:raise RuntimeError('骨架模型雜湊與固定版本不符，請重新安裝模型。')
    directory=Path(directory);directory.mkdir(parents=True,exist_ok=True)
    cap=cv2.VideoCapture(str(source))
    try:
        fps=cap.get(cv2.CAP_PROP_FPS);count=int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        if not cap.isOpened() or fps<=0:raise ValueError('無法解碼影片。')
        first=math.ceil(params['start']*fps);end=min(count,math.ceil(params['end']*fps))
        if first>=end:raise ValueError('分析區間沒有影格。')
        cap.set(cv2.CAP_PROP_POS_FRAMES,first)
        maps=None;frames=[];previous={};next_id=1
        flat=clip.get('projection')=='flat';width=640;height=480
        steps=teaching_media.steps_for(clip)
        options=vision.PoseLandmarkerOptions(base_options=mp.tasks.BaseOptions(model_asset_path=str(MODEL)),running_mode=vision.RunningMode.VIDEO,num_poses=4,min_pose_detection_confidence=.5,min_pose_presence_confidence=.5,min_tracking_confidence=.5)
        with vision.PoseLandmarker.create_from_options(options) as detector:
            for i in range(first,end):
                ok,image=cap.read()
                if not ok:raise ValueError(f'第{i}格解碼中斷；未標記為完整分析。')
                if flat:
                    height=round(image.shape[0]*width/image.shape[1]);view=cv2.resize(image,(width,height))
                else:
                    if maps is None:maps=projection_maps(image.shape[1],image.shape[0],params['yaw'],params['pitch'],params.get('fov',70))
                    view=cv2.remap(image,*maps,cv2.INTER_LINEAR,borderMode=cv2.BORDER_WRAP)
                if not cv2.imwrite(str(directory/f'raw-frame-{i}.jpg'),view,[cv2.IMWRITE_JPEG_QUALITY,86]):raise RuntimeError('原始影格輸出失敗。')
                roi=params.get('roi') or [0,0,1,1]
                rx,ry,rw,rh=roi
                # Detect on the chosen person region, then map points back onto
                # the full original frame so comparisons keep the same geometry.
                crop=view[round(ry*height):round((ry+rh)*height),round(rx*width):round((rx+rw)*width)]
                rgb=cv2.cvtColor(crop,cv2.COLOR_BGR2RGB)
                result=detector.detect_for_video(mp.Image(image_format=mp.ImageFormat.SRGB,data=rgb),round(i/fps*1000))
                poses=[]
                for lm in result.pose_landmarks:
                    points=[{k:round(float(getattr(p,k)),4) for k in ('x','y','z','visibility','presence')} for p in lm]
                    for p in points:
                        if not (0<=p['x']<=1 and 0<=p['y']<=1):p['visibility']=0
                        p['x']=round(rx+p['x']*rw,4);p['y']=round(ry+p['y']*rh,4)
                    m,tags=metrics(points,width,height)
                    poses.append({'landmarks':points,'visible_joints':sum(visible(p) for p in points),'metrics':m,'actions':tags,'interpretations':meanings(tags)})
                next_id=assign_tracks(poses,previous,i,fps,next_id,width,height)
                for pose in poses:
                    pts=pose['landmarks']
                    for a,b in EDGES:
                        if visible(pts[a]) and visible(pts[b]):cv2.line(view,(round(pts[a]['x']*width),round(pts[a]['y']*height)),(round(pts[b]['x']*width),round(pts[b]['y']*height)),(50,240,80),2,cv2.LINE_AA)
                    for p in pts:
                        if visible(p):cv2.circle(view,(round(p['x']*width),round(p['y']*height)),3,(30,210,255),-1)
                    if visible(pts[11]):cv2.putText(view,'P'+str(pose['track_id']),(round(pts[11]['x']*width),round(pts[11]['y']*height)-12),cv2.FONT_HERSHEY_SIMPLEX,.6,(0,255,255),2)
                cv2.putText(view,f'Frame {i} | {i/fps:.3f}s | {len(poses)} pose(s)',(12,25),cv2.FONT_HERSHEY_SIMPLEX,.55,(255,255,255),1,cv2.LINE_AA)
                if not cv2.imwrite(str(directory/f'frame-{i}.jpg'),view,[cv2.IMWRITE_JPEG_QUALITY,86]):raise RuntimeError('影格輸出失敗。')
                step=next((s for s in steps if s['start']<=i/fps<s['end']),None)
                frames.append({'frame':i,'seconds':round(i/fps,6),'poses':poses,'teaching_step_id':step['id'] if step else None,'status':'detected' if poses else '未偵測到可靠人體；仍可閱讀教案步驟與核對原圖'})
                if (i-first)%5==0 or i==end-1:on_progress(i-first+1,end-first)
        result={'version':VERSION,'source':{k:clip[k] for k in ('id','title','fps_rational','projection','source_sha256','proxy_sha256') if k in clip},
                'actual_video_sha256':source_hash,'model_sha256':digest(MODEL),'model':'MediaPipe Pose Landmarker Full float16 v1',
                'fps':fps,'first_frame':first,'last_frame':end-1,'frame_count':len(frames),'analyzed_every_frame':True,
                'view':{**params,'width':width,'height':height,'projection':'flat' if flat else 'rectilinear'},'frames':frames,
                'raw_frames_available':True,'teaching_steps':steps,
                'analysis_region':params.get('roi') or [0,0,1,1],
                'detection_frames':sum(bool(f['poses']) for f in frames),'limitation':LIMITATION,
                'interpretation_status':'機器觀測及意圖假設，待學員判讀與教師覆核；未辨識真實身分或職類。'}
        (directory/'result.json').write_text(json.dumps(result,ensure_ascii=False,separators=(',',':')),encoding='utf-8')
        return result
    finally:cap.release()
