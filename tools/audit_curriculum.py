"""Read-only source/structure audit; clinical publication still requires expert review."""
from pathlib import Path
import hashlib,json,re,unicodedata,sys
from pypdf import PdfReader

ROOT=Path(__file__).resolve().parents[1]
catalog=json.loads((ROOT/'data/course_catalog.json').read_text(encoding='utf-8'))
source=ROOT/'data/sources'/catalog['source']
reader=PdfReader(source)
digest=hashlib.sha256(source.read_bytes()).hexdigest()
results=[]
sys.path.insert(0,str(ROOT))
from backend.curriculum import install
class Registry:
    case_map={}
    cases=[]
registry=Registry();install(registry)
for course in catalog['courses']:
    pages=course['source_pages']
    text='\n'.join(reader.pages[p-1].extract_text() or '' for p in range(pages[0],pages[-1]+1))
    compact=lambda s:''.join(unicodedata.normalize('NFKC',s).split())
    text=re.sub(r'跨職種擬真教案[^\n]*|Page \d+ of 38','',unicodedata.normalize('NFKC',text))
    case=registry.case_map[course['id']]
    checks={
      'source_hash_matches':course['source_sha256']==digest==catalog['sha256'],
      'source_pages_in_range':1<=pages[0]<=pages[-1]<=len(reader.pages),
      'source_text_present':compact(course['source_text']) in compact(text),
      'profession_roles_complete':set(course['professions'])==set(course['roles']) and all(r['task'].strip() for r in course['roles'].values()),
      'five_levels_complete':set(course['levels'])==set('12345') and all(x.get('learner_task') and x.get('support') and x.get('patient_behavior') for x in course['levels'].values()),
      'rubric_present':bool(course['rubric']) and all(r['title'] and r['standard'] for r in course['rubric']),
      'decisions_present':bool(case['kdp']) and all(all(o['text'].strip() for o in d['options']) and len({o['text'] for o in d['options']})==len(d['options']) for d in case['kdp']),
      'safety_criteria_present':any(d['critical'] for d in case['kdp']),
    }
    results.append({'id':course['id'],'title':course['title'],'pages':pages,'roles':len(course['roles']),
      'checks':checks,'original_video_supplied':bool(course['video_file']),
      'original_import_empty_option_ids':[d['id'] for d in course['decisions'] if not d['incorrect']],
      'clinical_status':'來源與結構核對，非專家正式核定'})
out=ROOT/'docs/progression';out.mkdir(exist_ok=True)
report={'source':source.name,'sha256':digest,'pages':len(reader.pages),'courses':len(results),
 'profession_role_combinations':sum(r['roles'] for r in results),'level_task_combinations':sum(r['roles'] for r in results)*5,
 'passed':all(all(r['checks'].values()) for r in results),'results':results,
 'limitations':['程式檢查來源一致性與題目結構，不等於臨床效度驗證。','原PDF、Excel及來源目錄不改寫；指引補充保存在clinical_review.py與新訓練快照。',
 '肌少症採AWGS2019歷史教案，明示2025差異；ICU胃殘留補6小時區間，孕婦外傷補孕週及可存活性條件，兒童放射修正OCR用字。',
 '各職種專家仍需完成審題、處方適用性、評分錨點與正式發布核定。']}
(out/'curriculum-audit.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(report,ensure_ascii=False,indent=2))
