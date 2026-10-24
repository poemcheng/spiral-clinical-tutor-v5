"""Validate published lecture coverage, file hashes and locally recorded voice identities."""
import argparse,hashlib,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from backend import characters,curriculum,lecture_library
from backend.services import registry

def verify(strict=False,enrich=False):
    data=lecture_library.catalog();coverage=set();actors=set();files=0
    for entry in data['lectures']:
        source=registry.case(entry['case_id'])
        assert source is not None,('Published teaching case is missing',entry['case_id'])
        case=curriculum.adapt_case(source,entry['audiences'][0],1,{})
        actor=characters.get_actor(entry['actor_id'])
        assert entry['source_fingerprint']==lecture_library.source_fingerprint(case),'Stale teaching source'
        assert entry['actor_model_sha256']==actor['realistic_model_sha256'],'Stale actor appearance'
        assert entry['actor_gender']==actor['gender']
        assert {m['module'] for m in entry['modules']}=={0,1,2}
        assert set(entry['audiences'])<=set(case['professions'])
        if entry['actor_id']!='he-sw':coverage.update((entry['case_id'],p) for p in entry['audiences'])
        actors.add(entry['actor_id'])
        for module in entry['modules']:
            p=(lecture_library.DIRECTORY/module['file']).resolve()
            assert p.is_relative_to(lecture_library.DIRECTORY.resolve()) and p.suffix=='.mp4'
            assert p.stat().st_size==module['bytes']
            assert hashlib.file_digest(p.open('rb'),'sha256').hexdigest()==module['sha256']
            assert module['duration']>1;files+=1
        if enrich:
            voices=[]
            for i in range(3):
                p=ROOT/'runtime/virtual_lessons'/entry['project_key']/f'voice-{i}.wav.voice.json'
                voice=json.loads(p.read_text(encoding='utf8'));assert voice['gender']==actor['gender']
                voices.append({k:voice[k] for k in ('gender','name','engine','locale','fingerprint')})
            entry['voice_identities']=voices
        for voice in entry.get('voice_identities',[]):assert voice['gender']==actor['gender'] and voice['locale'].lower().startswith('zh')
    expected={(c['id'],p) for c in registry.cases if not c.get('teacher_authored') for p in c['professions']}
    if strict:
        assert coverage==expected,('Missing course-profession coverage',sorted(expected-coverage))
        assert len(data['lectures'])>=len(expected) and len(actors)==8
        assert all(len(e.get('voice_identities',[]))==3 for e in data['lectures']),'Local voice identities must be recorded before publication'
    if enrich:(lecture_library.DIRECTORY/'catalog.json').write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf8')
    return {'passed':True,'lectures':len(data['lectures']),'modules':files,'cases':len({c for c,_ in coverage}),'professions':len({p for _,p in coverage}),'course_profession_tasks':len(coverage),'lecturers':len(actors),'missing_tasks':sorted(expected-coverage),'contains_learner_data':False}

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--strict',action='store_true');p.add_argument('--enrich-voices',action='store_true');a=p.parse_args()
    print(json.dumps(verify(a.strict,a.enrich_voices),ensure_ascii=True))
