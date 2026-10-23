"""Actor appearance/style are separate from immutable clinical case facts."""
import hashlib
import json
from .config import ROOT

CATALOG=json.loads((ROOT/'data/characters/catalog.json').read_text(encoding='utf-8'))
ACTORS={a['id']:a for a in CATALOG['actors']}
VERSION=CATALOG['version']

PAIRINGS={'RT':['PT'],'DT':['PT'],'PT':['patient'],'MD':['patient'],'RN':['patient','PT']}
TARGET_NAMES={'patient':'病患／家屬','PT':'物理治療師','DT':'營養師','MD':'醫師','RN':'護理師'}
CASE_CAST={
 'COURSE-SARC':('auntie-lin','patient','教案病患'),
 'COURSE-STROKE':('middle-woman','caregiver','病患太太'),
 'COURSE-DEM':('middle-woman','caregiver','病患女兒'),
 'COURSE-ICU':('mr-wang','caregiver','病患家屬'),
 'COURSE-DM':('middle-woman','patient','教案病患'),
 'COURSE-ASTHMA':('middle-man','patient','教案病患'),
 'COURSE-PREG':('middle-woman','patient','教案孕婦'),
 'COURSE-BEDXR':('middle-woman','patient','教案孕婦'),
 'COURSE-PEDXR':('auntie-lin','caregiver','陪同嬰兒的阿嬤'),
}

def pairing(profession):
    targets=PAIRINGS.get(profession,['patient'])
    return {'version':'clinical-pairing-5.4.0','targets':list(targets),
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
    entries=row.get('payload',{}).get('encounter_plan',{}).get('entries',[])
    if entries:return entries[0]['actor_id']
    policy=row.get('payload',{}).get('interaction_policy')
    if policy and policy['targets'][0]!='patient':
        return next(a['id'] for a in ACTORS.values() if a['profession']==policy['targets'][0])
    case=row.get('payload',{}).get('case_snapshot',{})
    return CASE_CAST.get(case.get('id'),('auntie-lin',))[0]

def case_cast(row,actor,purpose):
    if purpose!='interaction' or actor['kind'] not in ('patient','caregiver'):return actor
    cast=CASE_CAST.get(row.get('payload',{}).get('case_snapshot',{}).get('id'))
    if cast:
        actor={**actor,'kind':cast[1],'title':cast[2],'display_name':cast[2],
               'casting_note':'虛構演員造型；家庭關係與病歷依選定教案。'}
    return actor

def selected(row,purpose='interaction'):
    # An actor is a cast member, never a replacement medical record.
    snapshot=row.get('payload',{}).get('actors',{}).get(purpose)
    if not snapshot:return case_cast(row,get_actor(default_actor(row,purpose)),purpose)
    # Resolve current visual assets without rewriting historical casting/messages.
    a=dict(snapshot);current=get_actor(a['id'])
    for key in ('visual_type','visual_version','atlas_file','atlas_sha256','atlas_url','face','realistic_model_file','realistic_model_sha256','realistic_model_url','appearance','reference_card_sha256','likeness_status'):
        if key in current:a[key]=current[key]
    return case_cast(row,a,purpose)

def catalog():return {'version':VERSION,'actors':[get_actor(aid) for aid in ACTORS]}
