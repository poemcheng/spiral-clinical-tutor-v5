"""Consistent same-installation backup/restore, with checksums and no unsafe ZIP extraction."""
import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import sqlite3
import sys
import tempfile
import zipfile

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))


def create_backup(destination):
    from backend.store import Store
    from backend.config import RUNTIME, VERSION
    destination=Path(destination).resolve()
    if destination.exists():raise ValueError('目的檔案已存在。')
    with tempfile.TemporaryDirectory() as tmp:
        db=Store();snapshot=Path(tmp)/'clinical_tutor.sqlite3';db.backup(snapshot);db.conn.close()
        files={'runtime/clinical_tutor.sqlite3':snapshot}
        for folder,prefix in [(ROOT/'data','data'),(RUNTIME/'media','runtime/media'),(RUNTIME/'speech','runtime/speech'),(RUNTIME/'virtual_lessons','runtime/virtual_lessons')]:
            if folder.exists():
                for p in folder.rglob('*'):
                    if p.is_file() and '__pycache__' not in p.parts:
                        files[prefix+'/'+p.relative_to(folder).as_posix()]=p
        manifest={'schema_version':1,'app_version':VERSION,'kind':'private_same_institution_backup','files':{}}
        with zipfile.ZipFile(destination,'w',compression=zipfile.ZIP_DEFLATED) as z:
            for name,p in sorted(files.items()):
                raw=p.read_bytes();manifest['files'][name]={'sha256':hashlib.sha256(raw).hexdigest(),'bytes':len(raw)}
                z.writestr(name,raw)
            z.writestr('manifest.json',json.dumps(manifest,ensure_ascii=False,indent=2))
    return manifest


def restore_backup(source,target):
    # Target MUST be a fresh directory. Never overwrite live records or merge users by guessing IDs.
    target=Path(target).resolve()
    if target.exists() and any(target.iterdir()):raise ValueError('還原目的資料夾必須為空白。')
    with zipfile.ZipFile(source) as z:
        if len(z.namelist())!=len(set(z.namelist())):raise ValueError('壓縮包有重複檔名。')
        manifest=json.loads(z.read('manifest.json'))
        if manifest.get('schema_version')!=1 or manifest.get('kind')!='private_same_institution_backup':raise ValueError('不相容的備份版本或模式。')
        files=manifest['files']
        if set(z.namelist()) != set(files)|{'manifest.json'}:raise ValueError('檔案清單與壓縮包不符。')
        for name,meta in files.items():
            rel=PurePosixPath(name)
            if rel.is_absolute() or '..' in rel.parts or '\\' in name or ':' in name:raise ValueError('不安全的檔案路徑。')
            if not (name.startswith('data/') or name.startswith('runtime/')):raise ValueError('備份含非預期路徑。')
            raw=z.read(name)
            if len(raw)!=meta['bytes'] or hashlib.sha256(raw).hexdigest()!=meta['sha256']:raise ValueError('檔案校驗失敗：'+name)
        with tempfile.TemporaryDirectory(dir=target.parent) as tmp:
            staging=Path(tmp)
            for name in files:
                p=staging/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(z.read(name))
            dbpath=staging/'runtime/clinical_tutor.sqlite3'
            if not dbpath.is_file():raise ValueError('缺少資料庫。')
            c=sqlite3.connect(dbpath)
            try:
                if c.execute('PRAGMA integrity_check').fetchone()[0]!='ok' or c.execute('PRAGMA foreign_key_check').fetchall():raise ValueError('資料庫完整性或關聯檢查失敗。')
                c.execute('UPDATE logins SET expires=0');c.commit()
            finally:c.close()
            target.mkdir(exist_ok=True)
            # All validation finished; move only into verified fresh target.
            for child in staging.iterdir():child.rename(target/child.name)
    return manifest


if __name__=='__main__':
    p=argparse.ArgumentParser();sub=p.add_subparsers(dest='action',required=True)
    b=sub.add_parser('backup');b.add_argument('destination')
    r=sub.add_parser('restore');r.add_argument('source');r.add_argument('empty_target')
    a=p.parse_args()
    try:
        m=create_backup(a.destination) if a.action=='backup' else restore_backup(a.source,a.empty_target)
        print(json.dumps({'ok':True,'files':len(m['files']),'kind':m['kind']},ensure_ascii=False))
    except Exception as e:raise SystemExit(str(e))
