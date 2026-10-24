"""Freeze only previously approved public assets plus the licensed report font."""
from pathlib import Path,PurePosixPath
import argparse,hashlib,json,zipfile
ROOT=Path(__file__).resolve().parents[1]
def build(version='5.6.1'):
    base=json.loads((ROOT/'runtime/release-5.6.0/public-assets-manifest.json').read_text(encoding='utf8'))
    names=set(base['files'])|{'data/report-fonts/NotoSansTC-Regular.ttf','data/report-fonts/OFL.txt'}
    dest=ROOT/'runtime'/('release-'+version);dest.mkdir(exist_ok=True);files={}
    with zipfile.ZipFile(dest/'public-assets.zip','w',zipfile.ZIP_DEFLATED,compresslevel=6) as z:
        for name in sorted(names):
            p=PurePosixPath(name)
            if p.is_absolute() or '..' in p.parts or name.startswith('data/sources/') or not name.startswith(('frontend/vendor/','frontend/assets/','data/')):raise ValueError('Non-public asset path: '+name)
            path=ROOT/name;raw=path.read_bytes()
            if name=='data/characters/catalog.json':
                catalog=json.loads(raw)
                for actor in catalog['actors']:
                    actor['source_file']='Fictional teaching character reference card'
                    actor['usage']='Fictional role-card reference and card-matched CC0 MakeHuman skinned geometry. Not a scan of a real patient.'
                raw=json.dumps(catalog,ensure_ascii=False,indent=2).encode('utf8')
            files[name]={'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest()};z.writestr(name,raw)
    archive=dest/'public-assets.zip';digest=hashlib.file_digest(archive.open('rb'),'sha256').hexdigest()
    manifest={**{k:v for k,v in base.items() if k not in ('files','archive_sha256','archive_bytes','version','release')},'version':version,'release':'v'+version,'archive_sha256':digest,'archive_bytes':archive.stat().st_size,'files':files,'contains_learner_data':False,'contains_original_teaching_footage':False,'contains_private_epa_frames':False}
    (dest/'public-assets-manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf8')
    print(json.dumps({'files':len(files),'bytes':archive.stat().st_size,'sha256':digest,'folder':str(dest)}));return manifest
if __name__=='__main__':build()
