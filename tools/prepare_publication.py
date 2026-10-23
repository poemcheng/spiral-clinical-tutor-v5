"""Explicit public allowlist. Local runtime, original documents and real footage never enter it."""
from pathlib import Path
import hashlib,json,zipfile
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'runtime/publication';OUT.mkdir(parents=True,exist_ok=True)
def sha(data):return hashlib.sha256(data).hexdigest()
assets={}
for p in (ROOT/'frontend/vendor').rglob('*'):
    if p.is_file():assets[p.relative_to(ROOT).as_posix()]=p.read_bytes()
for p in (ROOT/'frontend/assets').rglob('*'):
    if p.is_file():assets[p.relative_to(ROOT).as_posix()]=p.read_bytes()
for p in (ROOT/'data').rglob('*'):
    if not p.is_file() or 'sources' in p.parts or p.suffix not in ('.json','.vrm','.png','.glb'):continue
    if p.suffix=='.png' and 'photoreal-v1' not in p.parts:continue
    if 'video360' in p.parts and p.name!='catalog.json':continue
    assets[p.relative_to(ROOT).as_posix()]=p.read_bytes()
catalog=json.loads(assets['data/characters/catalog.json'])
for a in catalog['actors']:
    a['card_file']=a['atlas_file'];a['card_sha256']=a['atlas_sha256'];a['source_file']='Public generated portrait atlas'
    a['usage']='Generated fictional teaching character with CC0 MakeHuman skinned 3D geometry. Original uploaded role cards are excluded.'
assets['data/characters/catalog.json']=json.dumps(catalog,ensure_ascii=False,indent=2).encode()
archive=OUT/'public-assets.zip'
with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED) as z:
    for name,data in sorted(assets.items()):z.writestr(name,data)
manifest={'version':'5.4.0','archive_sha256':sha(archive.read_bytes()),'contains_learner_data':False,'contains_source_documents':False,'contains_real_footage':False,'files':{n:{'sha256':sha(b),'bytes':len(b)} for n,b in assets.items()}}
(OUT/'public-assets-manifest.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
files={}
for folder in ['backend','tests','frontend/src']:
    for p in (ROOT/folder).rglob('*'):
        if p.is_file() and '__pycache__' not in p.parts and p.suffix in ('.py','.js','.mjs'):files[p.relative_to(ROOT).as_posix()]=p.read_text(encoding='utf-8-sig')
for p in (ROOT/'frontend').iterdir():
    if p.is_file() and p.suffix in ('.html','.js','.css'):files[p.relative_to(ROOT).as_posix()]=p.read_text(encoding='utf-8-sig')
for p in (ROOT/'tools').iterdir():
    if not p.is_file() or p.suffix not in ('.py','.mjs','.ps1'):continue
    if p.name not in ('upgrade_v5.py','check_v5_llm.py'):
        files[p.relative_to(ROOT).as_posix()]=p.read_text(encoding='utf-8-sig')
for name in ['README.md','Dockerfile','compose.yaml','.dockerignore','.gitignore','.env.example','requirements.txt','requirements-pose.txt','requirements.lock.txt','package.json','package-lock.json','run.py','run_windows.bat','manage.py','.github/workflows/checks.yml','.github/workflows/publish-assets.yml','data/learning_policy.json']:
    files[name]=(ROOT/name).read_text(encoding='utf-8-sig')
for p in [p for d in (ROOT/'docs').glob('v5*') if d.is_dir() for p in d.iterdir()]:
    if p.is_file() and p.suffix in ('.md','.csv','.json','.txt','.srt') and p.name!='public-assets-manifest.json':files[p.relative_to(ROOT).as_posix()]=p.read_text(encoding='utf-8-sig')
for p in (ROOT/'data/characters/realistic-v1').glob('*.json'):
    files[p.relative_to(ROOT).as_posix()]=p.read_text(encoding='utf-8')
for p in (ROOT/'data/action_lessons').glob('*.json'):
    files[p.relative_to(ROOT).as_posix()]=p.read_text(encoding='utf-8')
files['data/characters/catalog.json']=assets['data/characters/catalog.json'].decode()
files['public-assets-manifest.json']=json.dumps(manifest,indent=2)
entries=[{'path':name,'mode':'100644','type':'blob','content':text} for name,text in sorted(files.items())]
batches=[];batch=[];size=0
for entry in entries:
    length=len(json.dumps(entry,ensure_ascii=False))
    if size+length>80000 and batch:batches.append(batch);batch=[];size=0
    batch.append(entry);size+=length
if batch:batches.append(batch)
for i,batch in enumerate(batches):(OUT/f'source-batch-{i}.json').write_text(json.dumps(batch,ensure_ascii=False),encoding='utf-8')
(OUT/'source-inventory.json').write_text(json.dumps({'files':[e['path'] for e in entries],'batches':len(batches),'asset_files':len(assets),'asset_bytes':archive.stat().st_size,'exclusions':['runtime','databases','credentials','source PDF/Excel','original role cards','real or 360 footage','historical docs and screenshots']},ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({'source_files':len(entries),'batches':len(batches),'public_asset_files':len(assets),'asset_archive_mb':round(archive.stat().st_size/1048576,2),'excluded_private_runtime':True,'excluded_source_documents':True,'excluded_real_footage':True}))
