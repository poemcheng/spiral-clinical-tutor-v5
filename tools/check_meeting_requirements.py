"""Read-only evidence checks; technical success never implies clinical acceptance."""
import argparse
import hashlib
import json
from pathlib import Path
import sys
from datetime import datetime,timezone,timedelta

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from backend import characters,competencies


def digest(path):
    with path.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()


def check(require_media=False):
    results=[]
    def add(name,passed,evidence):results.append({'check':name,'passed':bool(passed),'evidence':evidence})
    profiles=[competencies.profile(p) for p in competencies.DEFINITIONS]
    counts={p['profession']:len(p['indicators']) for p in profiles}
    add('profession_specific_indicators',len(profiles)==12 and len(set(counts.values()))>1,counts)
    def valid_reference(p,r):
        if r['url'].startswith('https://'):return True
        return (r['url']=='/api/materials/core-competencies' and p.get('source_file')=='核心能力.docx'
                and p.get('source_sha256')==competencies.core_alignment.CATALOG['source_sha256'])
    add('reference_mapping_and_draft_status',all(p['references'] and all(valid_reference(p,r) for r in p['references']) and any(label in p['status'] for label in ('待職類教師核定','待職類教師審核')) for p in profiles),{'profiles':len(profiles),'clinical_approval':False,'scope':'Checks mappings and labels, not literature validity'})
    expected={'RT':['PT'],'DT':['PT'],'PT':['patient'],'MD':['patient'],'RN':['patient','PT']}
    pairings={p:characters.pairing(p)['targets'] for p in expected}
    add('five_confirmed_demo_pairings',pairings==expected,pairings)
    models=[]
    for actor in characters.ACTORS.values():
        path=ROOT/'data/characters'/actor['realistic_model_file']
        models.append({'actor':actor['id'],'present':path.is_file(),'sha256_matches':path.is_file() and digest(path)==actor['realistic_model_sha256']})
    add('all_13_rigged_model_hashes',len(models)==13 and all(m['sha256_matches'] for m in models),models)
    groups={g:sorted({a['gender'] for a in characters.ACTORS.values() if a.get('age_group')==g}) for g in ('高齡','中年')}
    add('required_age_and_gender_groups',all(v==['female','male'] for v in groups.values()),groups)
    catalog=json.loads((ROOT/'data/video360/catalog.json').read_text(encoding='utf-8'))
    clips=[]
    for c in catalog['clips']:
        path=ROOT/'data/video360'/c['file']
        clips.append({'id':c['id'],'present':path.is_file(),'sha256_matches':digest(path)==c['proxy_sha256'] if path.is_file() else None,'review_status':c['status']})
    add('four_360_clip_versions',len(clips)==4 and all(c['sha256_matches'] is not False and (c['present'] or not require_media) for c in clips),clips)
    source=json.loads((ROOT/'frontend/assets/hospital-logo-source.json').read_text(encoding='utf-8'))
    matches=[p.name for p in (ROOT/'frontend/assets').glob('*.png') if digest(p)==source['sha256']]
    add('hospital_logo_provenance',bool(matches),{'files':matches,'source':source['source']})
    return {'checked_at':datetime.now(timezone(timedelta(hours=8))).isoformat(),'technical_checks_passed':all(r['passed'] for r in results),'all_meeting_requirements_accepted':False,
            'checks':results,'pending_acceptance':['實體麥克風與環境回音','雲端完整後端、HTTPS、持久化與推論驗收','職類指標、題目、權重及切點的教師核定','360情境配對、職類視角及逐格標準解析','跨主機還原演練']}


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--require-local-media',action='store_true');parser.add_argument('--output',type=Path,default=ROOT/'runtime/verification-5.3/requirements-check.json');args=parser.parse_args()
    result=check(args.require_local_media);args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({'technical_checks_passed':result['technical_checks_passed'],'all_meeting_requirements_accepted':False,'checks':len(result['checks']),'report':str(args.output)},ensure_ascii=False))
    return 0 if result['technical_checks_passed'] else 1


if __name__=='__main__':raise SystemExit(main())
