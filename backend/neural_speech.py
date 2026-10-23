"""Cross-platform Piper adapter. Voice gender must be explicitly configured.

Never substitute the other gender or clone a person from the role-card picture.
"""
import hashlib,json,os,threading,wave
from pathlib import Path

_voices={};_lock=threading.Lock()
def identity(gender):
    if gender not in ('male','female'):raise ValueError('角色語音性別未指定。')
    path=os.getenv('PIPER_'+gender.upper()+'_MODEL','')
    if not path or not Path(path).is_file():raise RuntimeError(f'尚未設定 Piper {gender} 中文模型；請設定 PIPER_{gender.upper()}_MODEL。')
    manifest=Path(path+'.identity.json')
    info=json.loads(manifest.read_text(encoding='utf-8')) if manifest.is_file() else {}
    if info.get('gender')!=gender or not str(info.get('language','')).startswith('zh'):
        raise RuntimeError('Piper 模型缺少相符的中文聲音性別登錄檔。')
    digest=hashlib.sha256(Path(path).read_bytes()).hexdigest()
    if info.get('sha256')!=digest:raise RuntimeError('Piper 模型雜湊與聲音登錄不符。')
    return Path(path),info,digest

def synthesize(text,target,gender):
    from piper.voice import PiperVoice
    path,info,digest=identity(gender)
    with _lock:
        voice=_voices.get(digest)
        if voice is None:voice=PiperVoice.load(str(path));_voices[digest]=voice
        with wave.open(str(target),'wb') as wav:voice.synthesize_wav(text,wav)
    return {'engine':'Piper','gender':gender,'name':info.get('name',path.stem),'language':info['language'],'model_sha256':digest}
