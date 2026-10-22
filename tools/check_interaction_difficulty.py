"""Run genuine local-LLM examples for patient/workplace Level 1 and Level 5.

Success means the model answered. Clinical and behavioural acceptance stays human-reviewed.
No learner session, grade or teacher approval is created.
"""
import argparse
import hashlib
import json
from pathlib import Path
import sys
from datetime import datetime,timezone,timedelta
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from backend import services,curriculum,characters


def run():
    rows=[]
    for profession in ('PT','DT'):
        for level in (1,5):
            row={'profession':profession,'level':level,'payload':{'trust':50,'interaction_policy':characters.pairing(profession)}}
            case=curriculum.adapt_case(services.registry.case_map['COURSE-SARC'],profession,level,{})
            history=[];turns=[]
            for text in ('您好，我剛接手這個案，請問可以一起確認資料嗎？','先照我的安排做就好，我覺得你原本的判斷不太對。'):
                history.append({'role':'user','content':text})
                result,facts=services.patient_reply(case,row,history,text)
                turns.append({'input':text,'ok':result.ok,'reply':result.text,'model':result.model,'error':result.error})
                print(profession,level,result.ok,result.text,flush=True)
                if not result.ok:raise RuntimeError(result.error)
                history.append({'role':'assistant','content':result.text})
            rows.append({'profession':profession,'self_level':level,'actor_id':characters.selected(row)['id'],
                         'policy':facts['interaction_difficulty'],'dialogue_partner':facts['dialogue_partner'],
                         'case_sha256':hashlib.sha256(json.dumps(case,sort_keys=True,ensure_ascii=False).encode()).hexdigest(),'turns':turns})
    return {'checked_at':datetime.now(timezone(timedelta(hours=8))).isoformat(),'uses_actual_local_llm':True,
            'creates_learning_evidence':False,'technical_success':True,'clinical_approval':False,'examples':rows}


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,default=Path('runtime/verification-5.3.1/difficulty-final.json'));args=p.parse_args()
    report=run();args.output.parent.mkdir(parents=True,exist_ok=True);args.output.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
