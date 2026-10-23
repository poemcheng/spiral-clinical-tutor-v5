"""Install the public, checksummed runtime asset pack. Never contains user records."""
from pathlib import Path,PurePosixPath
import argparse,hashlib,json,tempfile,urllib.request,zipfile,shutil
ROOT=Path(__file__).resolve().parents[1]
BASE='https://github.com/poemcheng/spiral-clinical-tutor-v5/releases/download/v5.5.0/'
def main():
    parser=argparse.ArgumentParser();parser.add_argument('--local',type=Path);args=parser.parse_args()
    manifest=json.loads((args.local.parent/'public-assets-manifest.json').read_text()) if args.local else json.load(urllib.request.urlopen(BASE+'public-assets-manifest.json',timeout=60))
    with tempfile.TemporaryDirectory() as tmp:
        archive=Path(tmp)/'assets.zip'
        if args.local:shutil.copyfile(args.local,archive)
        else:urllib.request.urlretrieve(BASE+'public-assets.zip',archive)
        if hashlib.file_digest(archive.open('rb'),'sha256').hexdigest()!=manifest['archive_sha256']:raise SystemExit('Asset archive checksum mismatch')
        with zipfile.ZipFile(archive) as z:
            if set(z.namelist())!=set(manifest['files']):raise SystemExit('Asset list mismatch')
            for name in z.namelist():
                p=PurePosixPath(name)
                if p.is_absolute() or '..' in p.parts or ':' in name or '\\' in name or not name.startswith(('frontend/vendor/','frontend/assets/','data/')) or name.startswith('data/sources/'):
                    raise SystemExit('Unsafe asset path')
                data=z.read(name)
                if hashlib.sha256(data).hexdigest()!=manifest['files'][name]['sha256']:raise SystemExit('File checksum mismatch')
            for name in z.namelist():
                dest=ROOT/name
                # An older bootstrap pack must not replace the current source catalog or compiled code.
                if dest.exists() and (name=='data/learning_policy.json' or name.startswith('data/action_lessons/')):
                    continue
                if args.local and name=='data/characters/catalog.json' and dest.exists():
                    current=json.loads(dest.read_text(encoding='utf-8'))
                    if any(a.get('realistic_model_file') for a in current.get('actors',[])):continue
                if args.local and name.startswith('frontend/vendor/') and dest.exists():continue
                dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes(z.read(name))
    print('Public runtime assets installed. Original teaching documents and 360 footage are supplied separately.')
if __name__=='__main__':main()
