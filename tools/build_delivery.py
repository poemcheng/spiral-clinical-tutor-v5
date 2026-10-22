"""Create a portable source delivery without credentials, learner data or local virtualenvs."""
from pathlib import Path
import hashlib
import json
import zipfile

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT.parent/'output'
OUT.mkdir(exist_ok=True)
target=OUT/'迴旋梯智鏈_v5.3.0_會議核對與逐格回饋版_20261022.zip'
folders=['backend','frontend','data','tests','tools','docs','.github']
singles=['README.md','requirements.txt','requirements.lock.txt','package.json','package-lock.json',
         'Dockerfile','compose.yaml','.dockerignore','run.py','manage.py','run_windows.bat','.env.example','.gitignore','操作活動圖.mmd','測試與交付紀錄_20261021.md']
files=[ROOT/name for name in singles]
for folder in folders:
    files.extend(p for p in (ROOT/folder).rglob('*') if p.is_file()
                 and '__pycache__' not in p.parts and 'node_modules' not in p.parts and p.suffix not in ('.pyc','.sqlite3','.db')
                 and not (p.parent.name=='livekit' and p.suffix=='.zip')
                 and ('ffmpeg' not in p.parts or p.name in ('ffmpeg.exe','ffprobe.exe','LICENSE','README.txt','README.md','release.sha256')))
manifest={'app_version':'5.3.0','kind':'clean_source_delivery','contains_learner_data':False,'files':{}}
with zipfile.ZipFile(target,'w',compression=zipfile.ZIP_DEFLATED) as z:
    for p in sorted(set(files)):
        rel=p.relative_to(ROOT).as_posix();raw=p.read_bytes()
        if rel.startswith('runtime/') or rel=='.env':raise RuntimeError('Private file selected')
        manifest['files'][rel]={'sha256':hashlib.sha256(raw).hexdigest(),'bytes':len(raw)}
        z.writestr('clinical_ai_platform_v5/'+rel,raw)
    z.writestr('clinical_ai_platform_v5/delivery-manifest.json',json.dumps(manifest,ensure_ascii=False,indent=2))
with zipfile.ZipFile(target) as z:
    assert z.testzip() is None
    assert not any('/runtime/' in n or '/.venv/' in n or '/node_modules/' in n for n in z.namelist())
print(json.dumps({'path':str(target),'files':len(manifest['files']),'bytes':target.stat().st_size,'private_data_included':False},ensure_ascii=False))
