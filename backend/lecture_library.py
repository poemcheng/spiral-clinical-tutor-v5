"""Published, source-versioned lectures. Contains no learner/session data."""
import hashlib,json
from functools import lru_cache
from pathlib import Path
from .config import ROOT
from . import characters

VERSION='published-lectures-5.6.0'
DIRECTORY=ROOT/'data/public_lectures'
LABELS={'DT':'營養師','PT':'物理治療師','RT':'醫事放射師','MD':'醫師','RN':'護理師','ST':'語言治療師','AUD':'聽力師','RPH':'藥師','RSP':'呼吸治療師','OT':'職能治療師','MLS':'醫事檢驗師','CP':'臨床心理師'}

@lru_cache(maxsize=256)
def verify_file(path,size,modified,expected):
    with Path(path).open('rb') as stream:actual=hashlib.file_digest(stream,'sha256').hexdigest()
    if actual!=expected:raise ValueError('影片內容與發行雜湊不符，請重新同步。')

def catalog():
    try:return json.loads((DIRECTORY/'catalog.json').read_text(encoding='utf-8'))
    except FileNotFoundError:return {'version':VERSION,'lectures':[]}

def source_fingerprint(case):
    fields={k:case.get(k) for k in ('id','patient','roles','source_sha256','curriculum_version','clinical_review')}
    return hashlib.sha256(json.dumps(fields,ensure_ascii=False,sort_keys=True).encode()).hexdigest()

def recommended(profession):
    return next((a['id'] for a in characters.ACTORS.values() if a['profession']==profession and a['kind']=='clinician'),'chen-md')

def available(row,case):
    actor=characters.selected(row,'lecturer');fingerprint=source_fingerprint(case)
    entries=[e for e in catalog()['lectures'] if e['actor_id'] in characters.ACTORS and e['case_id']==case['id'] and row['profession'] in e['audiences'] and e['source_fingerprint']==fingerprint and e['actor_model_sha256']==characters.get_actor(e['actor_id']).get('realistic_model_sha256')]
    return {'version':VERSION,'selected_actor':actor['id'],'recommended_actor':recommended(row['profession']),
            'lectures':[public_entry(e,row['id'],row['payload']['adaptive_plan']['video_count']) for e in entries if e['actor_id']==actor['id']],
            'available_actors':list(dict.fromkeys(e['actor_id'] for e in entries)),
            'scope':'共用教案導讀；當級任務與個人補強依本輪教案文字提供。不是個人化生成影片。'}

def public_entry(entry,sid,module_count):
    result={k:entry[k] for k in ('id','case_id','actor_id','actor_name','actor_gender','title','review_status','source_fingerprint','teaching_purpose','lecturer_scope')}
    result['modules']=[{**{k:m[k] for k in ('module','title','duration','sha256')},'transcript':entry['script'][m['module']][1],'url':f"/api/sessions/{sid}/lecture-library/{entry['id']}/{m['module']}"} for m in entry['modules'] if m['module']<module_count]
    result['guideline_note']='肌少症診斷題依 AWGS 2019 歷史教案；AWGS 2025 演算法不同，實務請核對教師核定版本。' if entry['case_id']=='COURSE-SARC' else '本片為來源教案導讀；院內流程與專業操作須核對教師核定版本。'
    return result

def resolve(row,case,lecture_id,module):
    eligible=available(row,case)
    public=next((e for e in eligible['lectures'] if e['id']==lecture_id),None)
    if not public:raise ValueError('此影片不符合本輪教案版本、職種或所選講師。')
    if not any(m['module']==module for m in public['modules']):raise PermissionError('此影片模組尚未解鎖。')
    entry=next(e for e in catalog()['lectures'] if e['id']==lecture_id)
    record=next(m for m in entry['modules'] if m['module']==module)
    path=(DIRECTORY/record['file']).resolve()
    if not path.is_relative_to(DIRECTORY.resolve()) or path.suffix!='.mp4' or not path.is_file():raise FileNotFoundError('主機尚未安裝此公開影片，請由管理者同步影片素材包。')
    if path.stat().st_size!=record['bytes']:raise ValueError('影片大小與發行紀錄不符，請重新同步。')
    verify_file(str(path),path.stat().st_size,path.stat().st_mtime_ns,record['sha256'])
    return path
