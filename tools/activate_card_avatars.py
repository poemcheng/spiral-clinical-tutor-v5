"""Validate reviewed candidate assets, back up current models, then activate atomically."""
import argparse,datetime,hashlib,json,os,shutil,struct
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]

def activate(source,check_only=False):
    catalog_path=ROOT/'data/characters/catalog.json'
    catalog=json.loads(catalog_path.read_text(encoding='utf-8'));validated=[]
    for actor in catalog['actors']:
        path=source/(actor['id']+'.glb');record=json.loads(path.with_suffix('.json').read_text(encoding='utf-8'));blob=path.read_bytes()
        if hashlib.sha256(blob).hexdigest()!=record['sha256']:raise ValueError('Model checksum mismatch: '+actor['id'])
        if record['face_fitting']['source_card_sha256']!=actor['card_sha256']:raise ValueError('Reference card mismatch: '+actor['id'])
        gltf=json.loads(blob[20:20+struct.unpack_from('<I',blob,12)[0]])
        names={m['name'] for m in gltf['meshes']}
        if not {'Card hairstyle closed 3D volume','Reference fitted rounded rear hair'}<=names:raise ValueError('Missing fitted scalp geometry: '+actor['id'])
        if len(gltf['skins'][0]['joints'])<100:raise ValueError('Missing human skeleton: '+actor['id'])
        validated.append((actor,path,record))
    if check_only:return {'validated':len(validated),'activated':False}
    backup=ROOT/'runtime/avatar-activation-backups'/datetime.datetime.now().strftime('%Y%m%d-%H%M%S-%f');backup.mkdir(parents=True)
    shutil.copy2(catalog_path,backup/'catalog.json')
    staged=[]
    for actor,path,record in validated:
        destination=ROOT/'data/characters'/actor['realistic_model_file']
        for src,dst in [(path,destination),(path.with_suffix('.json'),destination.with_suffix('.json'))]:
            if dst.exists():shutil.copy2(dst,backup/dst.name)
            pending=dst.with_name(dst.name+'.pending');shutil.copy2(src,pending);staged.append((pending,dst))
        actor['realistic_model_sha256']=record['sha256'];actor['face_fitting']=record['face_fitting']
    for pending,destination in staged:os.replace(pending,destination)
    pending=catalog_path.with_suffix('.json.pending');pending.write_text(json.dumps(catalog,ensure_ascii=False,indent=2),encoding='utf-8');os.replace(pending,catalog_path)
    return {'validated':len(validated),'activated':True,'backup':str(backup)}

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--from-dir',type=Path,default=ROOT/'runtime/card-avatar-candidate');parser.add_argument('--check-only',action='store_true');args=parser.parse_args()
    print(json.dumps(activate(args.from_dir.resolve(),args.check_only),ensure_ascii=True))
