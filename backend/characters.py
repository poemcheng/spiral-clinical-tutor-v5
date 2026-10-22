"""Actor appearance/style are separate from immutable clinical case facts."""
import hashlib
import json
from .config import ROOT

CATALOG=json.loads((ROOT/'data/characters/catalog.json').read_text(encoding='utf-8'))
ACTORS={a['id']:a for a in CATALOG['actors']}
VERSION=CATALOG['version']

PAIRINGS={'RT':['PT'],'DT':['PT'],'PT':['patient'],'MD':['patient'],'RN':['patient','PT']}
TARGET_NAMES={'patient':'病患／家屬','PT':'物理治療師','DT':'營養師','MD':'醫師','RN':'護理師'}

def pairing(profession):
    targets=PAIRINGS.get(profession,['patient'])
    return {'version':'v5-demo-pairing-20261022','targets':list(targets),
            'label':'＋'.join(TARGET_NAMES[x] for x in targets),'turns_per_target':2}

def allowed(row,actor):
    policy=row.get('payload',{}).get('interaction_policy')
    key='patient' if actor['kind'] in ('patient','caregiver') else actor['profession']
    return not policy or key in policy['targets']

def get_actor(aid):
    if aid not in ACTORS:raise ValueError('未知角色。')
    a=dict(ACTORS[aid]);a['version']=VERSION
    a['card_url']=f'/api/characters/{aid}/card'
    a['model_url']=f'/api/characters/{aid}/model'
    p=ROOT/'data/characters'/a['model_file']
    a['model_sha256']=hashlib.sha256(p.read_bytes()).hexdigest() if p.exists() else None
    if a.get('atlas_file'):
        a['atlas_url']=f'/api/characters/{aid}/atlas?v={a["atlas_sha256"][:12]}'
    if a.get('realistic_model_file'):
        a['realistic_model_url']=f'/api/characters/{aid}/rigged?v={a["realistic_model_sha256"][:12]}'
    return a

def default_actor(row, purpose='interaction'):
    if purpose=='lecturer':
        return next((a['id'] for a in ACTORS.values() if a['profession']==row['profession']),'chen-md')
    policy=row.get('payload',{}).get('interaction_policy')
    if policy and policy['targets'][0]!='patient':
        return next(a['id'] for a in ACTORS.values() if a['profession']==policy['targets'][0])
    case=row.get('payload',{}).get('case_snapshot',{})
    return 'mr-wang' if case.get('id') in ('COURSE-ICU','COURSE-STROKE','COURSE-DEM','COURSE-PEDXR') else 'auntie-lin'

def selected(row,purpose='interaction'):
    # An actor is a cast member, never a replacement medical record.
    snapshot=row.get('payload',{}).get('actors',{}).get(purpose)
    if not snapshot:return get_actor(default_actor(row,purpose))
    # Resolve current visual assets without rewriting historical casting/messages.
    a=dict(snapshot);current=get_actor(a['id'])
    for key in ('visual_type','visual_version','atlas_file','atlas_sha256','atlas_url','face','realistic_model_file','realistic_model_sha256','realistic_model_url'):
        if key in current:a[key]=current[key]
    return a

def catalog():return {'version':VERSION,'actors':[get_actor(aid) for aid in ACTORS]}
