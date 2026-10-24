"""Freeze only previously approved public assets plus the licensed report font."""
from pathlib import Path,PurePosixPath
import argparse,hashlib,json,zipfile
ROOT=Path(__file__).resolve().parents[1]
def public_bytes(name):
    raw=(ROOT/name).read_bytes()
    if name=='data/characters/catalog.json':
        catalog=json.loads(raw)
        for actor in catalog['actors']:
            actor['source_file']='Fictional teaching character reference card'
            actor['usage']='Fictional role-card reference and card-matched CC0 MakeHuman skinned geometry. Not a scan of a real patient.'
        raw=json.dumps(catalog,ensure_ascii=False,indent=2).encode('utf8')
    return raw

def build(version=None):
    version=version or json.loads((ROOT/'package.json').read_text(encoding='utf8'))['version']
    base=json.loads((ROOT/'runtime/release-5.6.1/public-assets-manifest.json').read_text(encoding='utf8'))
    names=set(base['files'])|{'data/report-fonts/NotoSansTC-Regular.ttf','data/report-fonts/OFL.txt'}
    catalog=json.loads((ROOT/'data/public_lectures/catalog.json').read_text(encoding='utf8'))
    for entry in catalog['lectures']:
        import re
        if not re.fullmatch('[a-f0-9]{24}',entry['id']):raise ValueError('Invalid public lecture id')
        names.add('data/public_lectures/'+entry['id']+'/script.json')
        for module in entry['modules']:names.add('data/public_lectures/'+module['file'])
    dest=ROOT/'runtime'/('release-'+version);dest.mkdir(exist_ok=True);files={}
    if (dest/'public-assets-manifest.json').is_file():
        existing=json.loads((dest/'public-assets-manifest.json').read_text(encoding='utf8'))
        with zipfile.ZipFile(dest/'public-assets.zip') as z:
            if set(z.namelist())!=names:raise ValueError('Frozen release contents changed; use a new release version')
            for name in names:
                if hashlib.sha256(public_bytes(name)).hexdigest()!=existing['files'][name]['sha256']:raise ValueError('Frozen release file changed: '+name)
        print(json.dumps({'reused_frozen_release':version,'files':len(names),'sha256':existing['archive_sha256']}));return existing
    with zipfile.ZipFile(dest/'public-assets.zip','w',zipfile.ZIP_DEFLATED,compresslevel=6) as z:
        for name in sorted(names):
            p=PurePosixPath(name)
            if p.is_absolute() or '..' in p.parts or name.startswith('data/sources/') or not name.startswith(('frontend/vendor/','frontend/assets/','data/')):raise ValueError('Non-public asset path: '+name)
            raw=public_bytes(name)
            files[name]={'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest()};z.writestr(name,raw)
    archive=dest/'public-assets.zip';digest=hashlib.file_digest(archive.open('rb'),'sha256').hexdigest()
    manifest={**{k:v for k,v in base.items() if k not in ('files','archive_sha256','archive_bytes','version','release')},'version':version,'release':'v'+version,'archive_sha256':digest,'archive_bytes':archive.stat().st_size,'files':files,'contains_learner_data':False,'contains_original_teaching_footage':False,'contains_private_epa_frames':False}
    (dest/'public-assets-manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf8')
    print(json.dumps({'files':len(files),'bytes':archive.stat().st_size,'sha256':digest,'folder':str(dest)}));return manifest
if __name__=='__main__':build()
