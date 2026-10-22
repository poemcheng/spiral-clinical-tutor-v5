"""Install generated atlases verbatim, without editing the original role cards."""
from pathlib import Path
import hashlib,json,shutil,sqlite3
ROOT=Path(__file__).resolve().parents[1]
def main(records):
    source=sqlite3.connect(ROOT/'runtime/clinical_tutor.sqlite3')
    destination=sqlite3.connect(ROOT.parent/'output/擬真人物修改前_20261022.sqlite3')
    source.backup(destination);destination.close();source.close()
    folder=ROOT/'data/characters/photoreal-v1';folder.mkdir(exist_ok=True)
    catalog=json.loads((ROOT/'data/characters/catalog.json').read_text(encoding='utf-8'))
    ledger={'version':'photoreal-20261022-1','generator':'built-in imagegen','layout':'2x2: neutral, speech-small, speech-open, blink','note':'Photo portrait animation, not scanned 3D or MuseTalk. Source role cards preserved verbatim.','assets':[]}
    for r in records:
        aid=r['id'];target=folder/(aid+'.png');shutil.copyfile(r['path'],target)
        actor=next(a for a in catalog['actors'] if a['id']==aid)
        my=.55 if aid in ('auntie-lin','mr-chen') else .515
        actor.update(visual_type='photoreal-portrait',visual_version=ledger['version'],atlas_file='photoreal-v1/'+aid+'.png',atlas_sha256=hashlib.sha256(target.read_bytes()).hexdigest(),face={'mouth':[.5,my,.18,.11],'eyes':[.5,.335,.32,.105]})
        ledger['assets'].append({'id':aid,'generated_source':r['path'],'file':actor['atlas_file'],'sha256':actor['atlas_sha256'],'source_card_sha256':actor['card_sha256']})
    (ROOT/'data/characters/catalog.json').write_text(json.dumps(catalog,ensure_ascii=False,indent=2),encoding='utf-8')
    (folder/'provenance.json').write_text(json.dumps(ledger,ensure_ascii=False,indent=2),encoding='utf-8')
if __name__=='__main__':
    import sys
    main(json.loads(Path(sys.argv[1]).read_text(encoding='utf-8')))
