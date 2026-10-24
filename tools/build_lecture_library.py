"""Build public, source-only lecturer videos locally; never reads a learner DB."""
import argparse,hashlib,json,re,shutil,subprocess,sys,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from backend import characters,curriculum,lecture_library,virtual_video
from backend.services import registry

BRIEFS={
 'COURSE-SARC':'一位容易疲勞的長者，對努力後的檢查結果感到挫折。先聽懂疑慮，再核對影像、肌力與生活資料。',
 'COURSE-STROKE':'中風個案接受復健並有吞嚥困難，太太關心何時能在病房進食。先釐清安全條件與團隊分工。',
 'COURSE-DEM':'疑似失智的長者需要女兒協助生活，伴隨進食嗆咳、跌倒與溝通困難。先分開觀察各項問題。',
 'COURSE-ICU':'重症個案因肺炎與呼吸衰竭入住加護病房，並有體重減輕。先整理營養風險與監測資訊。',
 'COURSE-DM':'第一型糖尿病個案喜歡旅行，卻擔心享用美食會影響血糖。先理解焦慮與自我管理需求。',
 'COURSE-ASTHMA':'有氣喘的貨運司機常忘記用藥，也不確定吸入技巧。先觀察操作與生活困難，保留待確認資訊。',
 'COURSE-PREG':'孕婦跌倒後到急診，因擔心胎兒而拒絕膝部影像檢查。先理解擔憂，並依各職類任務核對風險。',
 'COURSE-BEDXR':'孕婦需要床邊胸部影像檢查，她與陪伴者擔心輻射。練習核對必要性、擺位安全與溝通。',
 'COURSE-PEDXR':'嬰兒哭鬧，陪同的阿嬤擔心檢查固定姿勢會造成傷害。先回應情緒，再確認醫囑與安全條件。',
}

def plans():
    result=[]
    for course in curriculum.COURSES.values():
        case=registry.case(course['id'])
        for profession in course['professions']:
            actor=characters.get_actor(lecture_library.recommended(profession))
            task=re.split('[；;。]',case['roles'][profession]['task'])[0].strip()
            sections=[('情境與觀察目標',BRIEFS[case['id']]),
                (lecture_library.LABELS[profession]+'任務導讀','本職類學員將練習'+task+'。請說明判斷依據與資料缺口；實際技能依院內規範與教師指導。'),
                ('交接與練習目的','核對資料缺口與安全風險，再以SBAR說明分工與追蹤。影片是共用教案導讀，當級任務另見教案；能力仍需教師觀察。')]
            result.append({'case':case,'profession':profession,'actor':actor,'sections':sections,
                'lecturer_scope':'本職類講師導讀' if actor['profession']==profession else '跨域案例導讀；本職類技能需由對應專業教師核對'})
        # The support lecturer teaches family/resource communication, not clinical skills.
        result.append({'case':case,'profession':course['professions'][0],'actor':characters.get_actor('he-sw'),'audiences':course['professions'],
            'sections':[('情境與家屬視角',BRIEFS[case['id']]),('支援角色與專業界線','本片是跨專業溝通補充導讀。先了解病人與家屬的疑慮、意願及可用支持；臨床判斷由相應醫事專業負責。'),('交接與練習目的','說清楚誰需要協助、已知資料和待核對事項，再確認接收者與下一步。資源連結需依實際院內流程。')],
            'lecturer_scope':'社工支援導讀：家庭溝通與資源協調，不代替醫事技能教學'})
    return result

def persist(catalog):
    directory=lecture_library.DIRECTORY;directory.mkdir(parents=True,exist_ok=True)
    target=directory/'catalog.json';tmp=directory/'catalog.json.pending'
    tmp.write_text(json.dumps(catalog,ensure_ascii=False,indent=2),encoding='utf-8');tmp.replace(target)

def prepare(plan):
    case,actor=plan['case'],plan['actor'];audiences=plan.get('audiences',[plan['profession']])
    identity=[lecture_library.VERSION,lecture_library.source_fingerprint(case),audiences,actor['id'],actor['realistic_model_sha256'],plan['sections'],plan['lecturer_scope']]
    key=hashlib.sha256(json.dumps(identity,ensure_ascii=False,sort_keys=True).encode()).hexdigest()[:24]
    row={'profession':plan['profession'],'level':1,'payload':{'actors':{'lecturer':actor}}}
    project,manifest=virtual_video.build_project(case,row,0,lecture_sections=plan['sections'])
    # Shared lectures accompany all levels; never label them as a personal Level 1 result.
    p=project/'index.html';text=p.read_text(encoding='utf8').replace(' / Level 1',' / Level 1–5 共用導讀');p.write_text(text,encoding='utf8')
    record={'id':key,'case_id':case['id'],'audiences':audiences,'actor_id':actor['id'],'actor_name':actor['name'],'actor_gender':actor['gender'],
        'actor_model_sha256':actor['realistic_model_sha256'],'title':case['title'],'source_fingerprint':lecture_library.source_fingerprint(case),
        'source_file':case['source_file'],'source_pages':case.get('source_pages',[]),'source_sha256':case.get('source_sha256'),
        'teaching_purpose':'理解情境、辨識本職任務與缺口、練習安全溝通和交接；不代表完成臨床技能。','lecturer_scope':plan['lecturer_scope'],
        'review_status':'來源、角色界線與教學目的已核對；臨床教師正式核定待完成','shared_levels':[1,2,3,4,5],
        'script':plan['sections'],'project_key':manifest['key'],'renderer':virtual_video.RENDERER,'modules':[]}
    for i,s in enumerate(manifest['segments']):
        meta=json.loads((project/f'voice-{i}.wav.voice.json').read_text(encoding='utf8'))
        assert meta['gender']==actor['gender']
    return project,manifest,record

def render(project,manifest,workers):
    output=project/'training_video.mp4'
    if not output.is_file():
        cli=shutil.which('npx.cmd') or shutil.which('npx');environment=__import__('os').environ.copy()
        environment['PATH']=str(next((ROOT/'tools/ffmpeg').glob('*/bin')))+__import__('os').pathsep+environment.get('PATH','')
        with (project/'render.log').open('w',encoding='utf8') as log:
            subprocess.run([cli,'--yes','hyperframes@0.8.185','render','--quality','looks','--fps','24','--workers',str(workers),'--output',str(output)],cwd=project,env=environment,stdout=log,stderr=subprocess.STDOUT,timeout=1200,check=True,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
    return output

def export(plan,project,manifest,record):
    output=project/'training_video.mp4';directory=lecture_library.DIRECTORY/record['id'];directory.mkdir(parents=True,exist_ok=True)
    ff=next((ROOT/'tools/ffmpeg').glob('*/bin/ffmpeg.exe'));probe=ff.with_name('ffprobe.exe')
    for i,s in enumerate(manifest['segments']):
        target=directory/f'module-{i}.mp4'
        if not target.is_file():
            subprocess.run([str(ff),'-hide_banner','-loglevel','error','-y','-ss',str(s['start']),'-i',str(output),'-t',str(s['duration']),'-c:v','libx264','-preset','veryfast','-crf','21','-c:a','aac','-b:a','128k','-movflags','+faststart',str(target)],check=True,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
        media=json.loads(subprocess.check_output([str(probe),'-v','error','-show_streams','-show_format','-of','json',str(target)]))
        assert any(x['codec_type']=='audio' for x in media['streams'])
        record['modules'].append({'module':i,'title':s['title'],'duration':round(float(media['format']['duration']),3),
            'file':target.relative_to(lecture_library.DIRECTORY).as_posix(),'bytes':target.stat().st_size,'sha256':hashlib.file_digest(target.open('rb'),'sha256').hexdigest()})
    (directory/'script.json').write_text(json.dumps({'id':record['id'],'sections':plan['sections'],'source_fingerprint':record['source_fingerprint']},ensure_ascii=False,indent=2),encoding='utf8')
    return record

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--prepare-only',action='store_true');parser.add_argument('--limit',type=int);parser.add_argument('--workers',type=int,default=2);args=parser.parse_args()
    all_plans=plans();catalog=lecture_library.catalog();catalog.update(version=lecture_library.VERSION,expected_profession_tasks=39,expected_support_lectures=9,contains_learner_data=False)
    selected=all_plans[:args.limit] if args.limit else all_plans
    for index,plan in enumerate(selected):
        project,manifest,record=prepare(plan)
        if args.prepare_only:print(json.dumps({'project':str(project),'lecture':record['id'],'case':record['case_id'],'actor':record['actor_id'],'duration':manifest['duration']},ensure_ascii=True),flush=True);continue
        old=next((e for e in catalog['lectures'] if e['id']==record['id']),None)
        if old and all((lecture_library.DIRECTORY/m['file']).is_file() for m in old['modules']):print('cached',index+1,record['case_id'],record['actor_id'],flush=True);continue
        started=time.monotonic();render(project,manifest,args.workers);record=export(plan,project,manifest,record)
        catalog['lectures']=[e for e in catalog['lectures'] if not (e['case_id']==record['case_id'] and e['audiences']==record['audiences'] and e['actor_id']==record['actor_id'])]+[record]
        persist(catalog);print('completed',index+1,'/',len(selected),record['case_id'],record['actor_id'],round(time.monotonic()-started,1),'seconds',flush=True)
    print('Library entries',len(catalog['lectures']),flush=True)

if __name__=='__main__':main()
