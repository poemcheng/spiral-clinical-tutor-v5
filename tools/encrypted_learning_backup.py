"""Consistent, authenticated, chunked learning-data snapshots. No recovery key upload."""
import contextlib,datetime,hashlib,io,json,os,re,sqlite3,sys,tempfile,uuid,zipfile,zlib
from pathlib import Path,PurePosixPath
from cryptography.fernet import Fernet

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
CHUNK=8*1024*1024

def atomic_json(path,data):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    tmp=path.with_name(path.name+'.tmp');tmp.write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8');tmp.replace(path)

def recovery_cipher(runtime):
    p=Path(runtime)/'secrets/backup-recovery.key';p.parent.mkdir(parents=True,exist_ok=True)
    if not p.exists():
        try:
            with p.open('xb') as f:f.write(Fernet.generate_key())
            os.chmod(p,0o600)
        except FileExistsError:pass
    return Fernet(p.read_bytes())

def create_snapshot(runtime,destination,version):
    runtime=Path(runtime).resolve();destination=Path(destination).resolve()
    if destination.exists():raise ValueError('Snapshot destination already exists')
    cipher=recovery_cipher(runtime)
    with tempfile.TemporaryDirectory() as tmp:
        snapshot=Path(tmp)/'clinical_tutor.sqlite3'
        source=sqlite3.connect((runtime/'clinical_tutor.sqlite3').as_uri()+'?mode=ro',uri=True)
        target=sqlite3.connect(snapshot)
        try:
            source.backup(target)
            if target.execute('PRAGMA integrity_check').fetchone()[0]!='ok' or target.execute('PRAGMA foreign_key_check').fetchall():raise ValueError('Database integrity check failed')
            # Keep attribution rows but make restored browser sessions unusable.
            target.execute('UPDATE logins SET expires=0');target.commit()
        finally:source.close();target.close()
        files={'runtime/clinical_tutor.sqlite3':snapshot}
        for folder in ('pose_analysis','media'):
            for p in (runtime/folder).rglob('*'):
                # Frame JPEGs, render PNGs and generated audio/video are
                # reproducible caches, not learning records. Preserve dense
                # analysis results and authored annotations without uploading
                # tens of thousands of transient rendered frames.
                if p.is_file() and not p.is_symlink() and p.suffix.lower() in ('.json','.txt','.srt','.vtt'):
                    files['runtime/'+p.relative_to(runtime).as_posix()]=p
        for name in ('secrets/smtp.key','xapi-installation-id.txt'):
            p=runtime/name
            if p.is_file():files['runtime/'+name]=p
        destination.mkdir(parents=True);(destination/'objects').mkdir()
        cache=runtime/'encrypted-backup-objects';cache.mkdir(exist_ok=True)
        key_tag=hashlib.sha256((runtime/'secrets/backup-recovery.key').read_bytes()).digest()
        index={'format':'clinical-learning-encrypted-v2','created':datetime.datetime.now(datetime.timezone.utc).isoformat(),'app_version':version,'files':{}}
        new_bytes=0
        try:
            for name,path in sorted(files.items()):
                digest=hashlib.sha256();size=0;parts=[]
                with path.open('rb') as source_file:
                    while raw:=source_file.read(CHUNK):
                        digest.update(raw);size+=len(raw)
                        identity=hashlib.sha256(key_tag+raw).hexdigest();cached=cache/(identity+'.enc')
                        if cached.exists():
                            encrypted=cached.read_bytes()
                            if zlib.decompress(cipher.decrypt(encrypted))!=raw:raise ValueError('Encrypted object cache integrity mismatch')
                        else:
                            encrypted=cipher.encrypt(zlib.compress(raw,6));temporary=cached.with_suffix('.tmp');temporary.write_bytes(encrypted);temporary.replace(cached);new_bytes+=len(encrypted)
                        linked=destination/'objects'/cached.name
                        if not linked.exists():
                            try:os.link(cached,linked)
                            except OSError:
                                import shutil
                                shutil.copyfile(cached,linked)
                        parts.append({'object':identity,'sha256':hashlib.sha256(encrypted).hexdigest(),'raw_sha256':hashlib.sha256(raw).hexdigest()})
                index['files'][name]={'bytes':size,'sha256':digest.hexdigest(),'parts':parts}
            (destination/'index.enc').write_bytes(cipher.encrypt(json.dumps(index).encode()))
            # Read back authenticated bytes before advertising a usable snapshot.
            verify_snapshot(destination,runtime/'secrets/backup-recovery.key')
        except Exception:
            (destination/'INCOMPLETE').touch();raise
    return {'snapshot':destination.name,'created':index['created'],'files':len(files),'encrypted_bytes':sum(p.stat().st_size for p in destination.rglob('*.enc')),'new_encrypted_bytes':new_bytes+(destination/'index.enc').stat().st_size,'verified':True}

def verify_snapshot(source,key,archive_target=None):
    source=Path(source)
    if not (source/'index.enc').is_file() and (source/'current/index.enc').is_file():source=source/'current'
    cipher=Fernet(Path(key).read_bytes());index=json.loads(cipher.decrypt((source/'index.enc').read_bytes()))
    if index.get('format') not in ('clinical-learning-encrypted-v1','clinical-learning-encrypted-v2'):raise ValueError('Unknown encrypted backup')
    with tempfile.TemporaryDirectory() as tmp:
        archive=Path(tmp)/'backup.zip';digest=hashlib.sha256();seen=set()
        if index['format']=='clinical-learning-encrypted-v1':
            with archive.open('wb') as f:
                for i,part in enumerate(index['parts']):
                    if part['file']!=f'part-{i:05d}.enc' or part['file'] in seen:raise ValueError('Invalid part sequence')
                    seen.add(part['file']);encrypted=(source/part['file']).read_bytes()
                    if hashlib.sha256(encrypted).hexdigest()!=part['sha256']:raise ValueError('Encrypted part checksum mismatch')
                    raw=cipher.decrypt(encrypted);digest.update(raw);f.write(raw)
            if digest.hexdigest()!=index['archive_sha256']:raise ValueError('Backup archive checksum mismatch')
        else:
            objects=source/'objects' if (source/'objects').is_dir() else source.parent/'objects'
            manifest={'schema_version':1,'app_version':index['app_version'],'kind':'private_same_institution_backup','files':{}}
            with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED) as z:
                for name,meta in index['files'].items():
                    digest=hashlib.sha256();size=0
                    with z.open(name,'w',force_zip64=True) as output:
                        for part in meta['parts']:
                            if not re.fullmatch('[a-f0-9]{64}',part['object']):raise ValueError('Unsafe object path')
                            encrypted=(objects/(part['object']+'.enc')).read_bytes()
                            if hashlib.sha256(encrypted).hexdigest()!=part['sha256']:raise ValueError('Encrypted object checksum mismatch')
                            decoder=zlib.decompressobj();raw=decoder.decompress(cipher.decrypt(encrypted),CHUNK+1)
                            if len(raw)>CHUNK or not decoder.eof or hashlib.sha256(raw).hexdigest()!=part['raw_sha256']:raise ValueError('Object content integrity mismatch')
                            output.write(raw);digest.update(raw);size+=len(raw)
                    if size!=meta['bytes'] or digest.hexdigest()!=meta['sha256']:raise ValueError('File content integrity mismatch')
                    manifest['files'][name]={'bytes':size,'sha256':digest.hexdigest()}
                z.writestr('manifest.json',json.dumps(manifest))
        with zipfile.ZipFile(archive) as z:
            manifest=json.loads(z.read('manifest.json'));files=manifest['files']
            if len(z.namelist())!=len(set(z.namelist())) or set(z.namelist())!=set(files)|{'manifest.json'}:raise ValueError('Unexpected archive members')
            for name,meta in files.items():
                p=PurePosixPath(name)
                if p.is_absolute() or '..' in p.parts or ':' in name or '\\' in name or not name.startswith('runtime/'):raise ValueError('Unsafe restore path')
                if 'backup-recovery.key' in name or 'github-' in name:raise ValueError('Backup contains excluded key')
                raw=z.read(name)
                if len(raw)!=meta['bytes'] or hashlib.sha256(raw).hexdigest()!=meta['sha256']:raise ValueError('Backup content checksum mismatch')
            db=Path(tmp)/'verify.sqlite3';db.write_bytes(z.read('runtime/clinical_tutor.sqlite3'))
        with contextlib.closing(sqlite3.connect(db)) as c:
            if c.execute('PRAGMA integrity_check').fetchone()[0]!='ok' or c.execute('PRAGMA foreign_key_check').fetchall():raise ValueError('Restored database integrity failed')
        if archive_target:
            import shutil
            shutil.copyfile(archive,archive_target)
    return index

def restore_snapshot(source,key,empty_target):
    from tools.backup_bundle import restore_backup
    with tempfile.TemporaryDirectory() as tmp:
        archive=Path(tmp)/'restore.zip';verify_snapshot(source,key,archive)
        return restore_backup(archive,empty_target)

if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser();sub=p.add_subparsers(dest='action',required=True)
    v=sub.add_parser('verify');v.add_argument('snapshot');v.add_argument('key')
    r=sub.add_parser('restore');r.add_argument('snapshot');r.add_argument('key');r.add_argument('empty_target')
    a=p.parse_args()
    if a.action=='verify':verify_snapshot(a.snapshot,a.key)
    else:restore_snapshot(a.snapshot,a.key,a.empty_target)
    print('Encrypted backup verified; restore never overwrites a live installation.')
