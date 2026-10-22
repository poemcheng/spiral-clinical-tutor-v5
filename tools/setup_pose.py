"""Install only Google's public model. No video or learner data leaves this computer."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import urllib.request
from backend.pose_analysis import MODEL,MODEL_URL,MODEL_SHA256,digest

if __name__=='__main__':
    MODEL.parent.mkdir(parents=True,exist_ok=True)
    if not MODEL.is_file():
        tmp=MODEL.with_suffix('.download')
        try:
            urllib.request.urlretrieve(MODEL_URL,tmp)
            # The task is a ZIP model bundle; reject HTML/error downloads.
            import zipfile
            with zipfile.ZipFile(tmp) as z:
                if not {'pose_detector.tflite','pose_landmarks_detector.tflite'}.issubset(z.namelist()):raise RuntimeError('非預期模型內容')
            if digest(tmp)!=MODEL_SHA256:raise RuntimeError('模型雜湊不符')
            tmp.replace(MODEL)
        finally:tmp.unlink(missing_ok=True)
    if digest(MODEL)!=MODEL_SHA256:raise RuntimeError('既有模型雜湊不符，請移開後重新下載。')
    print('POSE_MODEL_READY',MODEL,digest(MODEL))
