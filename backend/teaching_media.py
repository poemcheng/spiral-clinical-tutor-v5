"""Fixed identifiers and local roots for conventional and panoramic teaching media."""
import json
from .config import ROOT
from .legacy.config import VIDEO_LIBRARY_DIR

def manifest():
    clips=[]
    for name in ('data/video360/catalog.json','data/action_lessons/media_catalog.json'):
        p=ROOT/name
        if p.is_file():clips.extend(json.loads(p.read_text(encoding='utf-8'))['clips'])
    return {'clips':clips}

def path_for(clip):
    base=VIDEO_LIBRARY_DIR if clip.get('storage')=='teaching_library' else ROOT/'data/video360'
    path=(base/clip['file']).resolve()
    if not path.is_relative_to(base.resolve()):raise ValueError('影片路徑超出教材資料夾。')
    return path

def applies(clip,row,case=None):
    return not clip.get('topic') or clip['topic']==row['topic'] or (case and clip.get('course_id')==case['id'])

def steps_for(clip):
    p=ROOT/'data/action_lessons/sarcopenia_steps.json'
    if not p.is_file():return []
    data=json.loads(p.read_text(encoding='utf-8'))
    expected=data.get('video_sha256',{}).get(clip['id'])
    if expected and expected!=(clip.get('source_sha256') or clip.get('proxy_sha256')):return []
    return data.get('videos',{}).get(clip['id'],[])

def step_at(clip,seconds):
    return next((s for s in steps_for(clip) if s['start']<=seconds<s['end']),None)
