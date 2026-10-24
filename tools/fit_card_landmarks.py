"""Fit a fictional reference card to the rendered anatomical head, locally."""
import sys,json,math
from pathlib import Path
import numpy as np
from PIL import Image
import mediapipe as mp
import cv2

ROOT=Path(__file__).resolve().parents[1]
OVAL=[10,338,297,332,284,251,389,356,454,323,361,288,397,365,379,378,400,377,152,148,176,149,150,136,172,58,132,93,234,127,162,21,54,103,67,109]
FEATURES=[33,133,159,145,160,144,158,153,263,362,386,374,385,380,387,373,70,63,105,66,107,336,296,334,293,300,1,4,5,6,98,327,168,2,61,291,0,17,37,267,84,314,13,14,172,397]

def fit(actor_id,model):
    directory=ROOT/'runtime/card-face-fit'/actor_id
    actor=next(a for a in json.loads((ROOT/'data/characters/catalog.json').read_text(encoding='utf-8'))['actors'] if a['id']==actor_id)
    original=Image.open(ROOT/'data/characters'/actor['card_file']).convert('RGB');w,h=original.size
    crop=original.crop((0,0,w//2,h//2)) if actor_id in ('middle-man','middle-woman','zhou-rt') else original.crop((0,0,int(w*.6),int(h*.48)))
    def detect(image):
        result=model.detect(mp.Image(image_format=mp.ImageFormat.SRGB,data=np.array(image)))
        if not result.face_landmarks:raise RuntimeError('No facial landmarks: '+actor_id)
        return np.array([[p.x*image.width,p.y*image.height] for p in result.face_landmarks[0]])
    reference=detect(crop);render=detect(Image.open(directory/'neutral-head.png').convert('RGB'))/768
    rc=(reference[33]+reference[263])/2;dc=(render[33]+render[263])/2
    axis=reference[263]-reference[33];angle=math.atan2(axis[1],axis[0]);rotation=np.array([[math.cos(angle),-math.sin(angle)],[math.sin(angle),math.cos(angle)]])
    upright=(reference-rc)@rotation
    scale=np.linalg.norm(render[234]-render[454])/np.linalg.norm(upright[234]-upright[454])
    desired=upright*scale+dc
    face_width=np.linalg.norm(reference[234]-reference[454])
    # Extract the actual hairstyle silhouette rather than reusing one generic cut.
    bottom=reference[152,1]+face_width*(.55 if actor['gender']=='female' and actor_id!='auntie-lin' else -.1)
    hb=(max(0,int(rc[0]-.75*face_width)),max(0,int(reference[10,1]-.6*face_width)),min(w,int(rc[0]+.75*face_width)),min(h,int(bottom)))
    hair_pixels=np.array(original.crop(hb));gray_hair=cv2.cvtColor(hair_pixels,cv2.COLOR_RGB2GRAY)
    threshold=80 if actor_id in ('middle-man','middle-woman','zhou-rt') else 160 if actor_id=='auntie-lin' else 115
    hair_mask=(gray_hair<threshold).astype('uint8')*255
    red,green,blue=[hair_pixels[:,:,i].astype(float) for i in range(3)]
    hair_mask[blue>red*1.03]=0
    skin_edge=(red>green*1.15)&(green>blue*1.1)&(gray_hair>(65 if actor_id=='auntie-lin' else 105))
    hair_mask[skin_edge]=0
    face_poly=np.round(reference[OVAL]-np.array(hb[:2])).astype('int32')
    face_exclusion=np.zeros_like(hair_mask);cv2.fillPoly(face_exclusion,[face_poly],255)
    if actor_id=='auntie-lin':face_exclusion[:max(0,int(rc[1]-hb[1]-.16*face_width)),:]=0
    hair_mask[face_exclusion>0]=0
    hair_mask=cv2.morphologyEx(hair_mask,cv2.MORPH_CLOSE,np.ones((3,3),dtype='uint8'))
    number,labels,stats,centers=cv2.connectedComponentsWithStats(hair_mask)
    candidates=[i for i in range(1,number) if stats[i,cv2.CC_STAT_AREA]>face_width**2*.04 and stats[i,cv2.CC_STAT_TOP]<(rc[1]-hb[1]-.15*face_width)]
    if not candidates:raise RuntimeError('Reference hairstyle segmentation requires review: '+actor_id)
    over_head=[i for i in candidates if stats[i,cv2.CC_STAT_LEFT]<rc[0]-hb[0]<stats[i,cv2.CC_STAT_LEFT]+stats[i,cv2.CC_STAT_WIDTH]]
    selected=max(over_head or candidates,key=lambda i:stats[i,cv2.CC_STAT_AREA])
    hair_mask=(labels==selected).astype('uint8')*255
    hair_mask=cv2.morphologyEx(hair_mask,cv2.MORPH_CLOSE,np.ones((5,5),dtype='uint8'))
    contours,_=cv2.findContours(hair_mask,cv2.RETR_EXTERNAL,cv2.CHAIN_APPROX_SIMPLE)
    cv2.drawContours(hair_mask,[max(contours,key=cv2.contourArea)],-1,255,cv2.FILLED)
    hair_mask[face_exclusion>0]=0
    source_hair_mask=hair_mask.copy()
    source_hair_mask[skin_edge]=0
    crown_mask=source_hair_mask.copy()
    crown_mask[max(0,int(reference[10,1]-hb[1]-.03*face_width)):,:]=0
    if cv2.countNonZero(crown_mask)>30:source_hair_mask=crown_mask
    if actor_id=='auntie-lin':
        # The silver fringe overlaps the reference face-oval estimate. Extend its
        # inner edge to meet the anatomical forehead, without pulling in clothing.
        hair_mask=cv2.dilate(hair_mask,np.ones((5,5),dtype='uint8'))
    # Pad the texture from actual hair pixels so silhouette-edge geometry never
    # carries the card's white background or a fragment of clothing.
    full_hair_mask=np.zeros((h,w),dtype='uint8');full_hair_mask[hb[1]:hb[3],hb[0]:hb[2]]=source_hair_mask
    _,nearest=cv2.distanceTransformWithLabels((full_hair_mask==0).astype('uint8'),cv2.DIST_L2,5,labelType=cv2.DIST_LABEL_PIXEL)
    palette=np.zeros((int(nearest.max())+1,3),dtype='uint8');yy,xx=np.where(full_hair_mask>0)
    palette[nearest[yy,xx]]=np.array(original)[yy,xx]
    padded=palette[nearest]
    Image.fromarray(padded).save(directory/'fitted-hair.png')
    contours,_=cv2.findContours(hair_mask,cv2.RETR_EXTERNAL,cv2.CHAIN_APPROX_SIMPLE)
    outline=cv2.approxPolyDP(max(contours,key=cv2.contourArea),.7,True).reshape(-1,2)
    height,width=hair_mask.shape;subdivision=cv2.Subdiv2D((0,0,width,height));inserted={}
    step=max(2,int(face_width/65))
    samples=list(outline)+[np.array([x,y]) for y in range(1,height-1,step) for x in range(1,width-1,step) if hair_mask[y,x]]
    for p in samples:
        key=tuple(int(v) for v in p)
        if key not in inserted:inserted[key]=len(inserted);subdivision.insert(tuple(float(v) for v in key))
    hair_faces=[]
    for triangle in subdivision.getTriangleList().reshape(-1,3,2):
        keys=[tuple(int(round(v)) for v in p) for p in triangle]
        if not all(key in inserted for key in keys):continue
        center=triangle.mean(axis=0).astype(int)
        if 0<=center[0]<width and 0<=center[1]<height and hair_mask[center[1],center[0]]:hair_faces.append([inserted[key] for key in keys])
    hair_source=np.array(list(inserted))+np.array(hb[:2]);hair_target=((hair_source-rc)@rotation)*scale+dc
    hair={'points':hair_target.tolist(),'source_uv':np.column_stack([hair_source[:,0]/w,1-hair_source[:,1]/h]).tolist(),'faces':hair_faces,'outline':[inserted[tuple(int(v) for v in p)] for p in outline]}
    Image.fromarray(hair_mask).save(directory/'reference-hair-mask.png')
    cheek_pixels=[]
    pixels=np.array(original)
    for index in [205,425,50,280]:
        x,y=reference[index].astype(int);cheek_pixels.extend(pixels[max(0,y-2):y+3,max(0,x-2):x+3].reshape(-1,3))
    glasses=[]
    if actor.get('glasses'):
        box=(int(rc[0]-face_width*.7),int(rc[1]-face_width*.4),int(rc[0]+face_width*.7),int(rc[1]+face_width*.45))
        crop_pixels=np.array(original.crop(box));gray=cv2.cvtColor(crop_pixels,cv2.COLOR_RGB2GRAY)
        partial={}
        for threshold in [145,170,190]:
            mask=cv2.morphologyEx((gray<threshold).astype('uint8')*255,cv2.MORPH_CLOSE,np.ones((2,2),dtype='uint8'))
            contours,_=cv2.findContours(mask,cv2.RETR_TREE,cv2.CHAIN_APPROX_SIMPLE)
            paths=[]
            for side,eye in enumerate([(reference[33]+reference[133])/2,(reference[263]+reference[362])/2]):
                point=tuple(float(v) for v in (eye-np.array(box[:2])))
                candidates=[c for c in contours if .025*face_width**2<cv2.contourArea(c)<.17*face_width**2 and cv2.pointPolygonTest(c,point,False)>=0]
                if candidates:
                    contour=min(candidates,key=cv2.contourArea)
                    xy=cv2.approxPolyDP(contour,.6,True).reshape(-1,2)+np.array(box[:2])
                    path=(((xy-rc)@rotation)*scale+dc).tolist();paths.append(path);partial.setdefault(side,path)
            if len(paths)==2:glasses=paths;break
        if not glasses and partial:
            side=next(iter(partial));path=np.array(partial[side]);eyes=[(desired[33]+desired[133])/2,(desired[263]+desired[362])/2]
            mirror=(path-eyes[side])*np.array([-1,1])+eyes[1-side]
            glasses=[partial[side],mirror.tolist()]
    indices=list(dict.fromkeys(OVAL+FEATURES));source=render[indices];target=desired[indices]
    anchors=np.array([[0,0],[1,0],[0,1],[1,1],[.1,.5],[.9,.5],[.25,.95],[.75,.95]])
    source=np.vstack([source,anchors]);target=np.vstack([target,anchors])
    distance=np.linalg.norm(source[:,None]-source[None,:],axis=2)
    kernel=distance**2*np.log(distance+1e-9);kernel+=np.eye(len(source))*1e-6
    affine=np.column_stack([np.ones(len(source)),source]);system=np.block([[kernel,affine],[affine.T,np.zeros((3,3))]])
    coeff=np.linalg.solve(system,np.vstack([target-source,np.zeros((3,2))]))
    error=np.linalg.norm((kernel@coeff[:len(source)]+affine@coeff[len(source):]+source)-target,axis=1)
    record={'actor_id':actor_id,'source_card':actor['card_file'],'source_card_sha256':actor['card_sha256'],
        'points':source.tolist(),'weights':coeff[:len(source)].tolist(),'affine':coeff[len(source):].tolist(),
        'reference_eye_center_px':rc.tolist(),'render_eye_center':dc.tolist(),'reference_rotation':rotation.tolist(),
        'reference_scale':scale,'reference_size':[w,h],'target_face_oval':desired[OVAL].tolist(),
        'skin_color_srgb':(np.median(cheek_pixels,axis=0)/255).tolist(),'reference_glasses_paths':glasses,
        'reference_hair':hair,
        'landmark_indices':indices,'fit_residual_pixels':float(error[:len(indices)].mean()*768),
        'method':'local reference-to-anatomical-head landmark warp; artistic 3D fitting, not a biometric identity assertion'}
    (directory/'fit.json').write_text(json.dumps(record,indent=2),encoding='utf-8')
    print(actor_id,'fitting landmarks',len(indices),'residual px',round(record['fit_residual_pixels'],3),flush=True)

if __name__=='__main__':
    options=mp.tasks.vision.FaceLandmarkerOptions(base_options=mp.tasks.BaseOptions(model_asset_path=str(ROOT/'runtime/models/face_landmarker.task')),num_faces=1)
    with mp.tasks.vision.FaceLandmarker.create_from_options(options) as model:
        for actor_id in sys.argv[1:]:fit(actor_id,model)
