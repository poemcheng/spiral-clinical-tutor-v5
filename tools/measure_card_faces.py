"""Measure fictional card drawings locally to drive 3D face proportions.

No embeddings/identity matching, no uploads, no assertion of biometric accuracy.
"""
import json,math
from pathlib import Path
import numpy as np
from PIL import Image
import mediapipe as mp
ROOT=Path(__file__).resolve().parents[1]
def run():
    options=mp.tasks.vision.FaceLandmarkerOptions(base_options=mp.tasks.BaseOptions(model_asset_path=str(ROOT/'runtime/models/face_landmarker.task')),num_faces=1)
    out={}
    with mp.tasks.vision.FaceLandmarker.create_from_options(options) as model:
        for a in json.loads((ROOT/'data/characters/catalog.json').read_text(encoding='utf-8'))['actors']:
            image=Image.open(ROOT/'data/characters'/a['card_file']).convert('RGB');w,h=image.size
            image=image.crop((0,0,int(w*.6),int(h*.48))) if a['id'] not in ('middle-man','middle-woman','zhou-rt') else image.crop((0,0,w//2,h//2))
            pixels=np.array(image);r=model.detect(mp.Image(image_format=mp.ImageFormat.SRGB,data=pixels))
            if not r.face_landmarks:raise RuntimeError('Cannot measure card face: '+a['id'])
            lm=r.face_landmarks[0];iw,ih=image.size
            def distance(x,y):return math.hypot((lm[x].x-lm[y].x)*iw,(lm[x].y-lm[y].y)*ih)
            width=distance(234,454)
            out[a['id']]={'head_aspect':round(distance(10,152)/width,4),'eye_spacing':round(distance(33,263)/width,4),'nose_width':round(distance(98,327)/width,4),'mouth_width':round(distance(61,291)/width,4),'source_card_sha256':a['card_sha256'],'method':'local MediaPipe fictional drawing proportions; artistic fitting controls'}
    p=ROOT/'data/characters/card-face-proportions.json';p.write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding='utf-8');print('Measured',len(out),'fictional reference faces')
if __name__=='__main__':run()
