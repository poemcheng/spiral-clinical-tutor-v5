"""Read-only v3 import with explicit account mapping; no guessing identities or approved Levels."""
import argparse
import hashlib
import json
from pathlib import Path
import sqlite3
import sys
import time
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from backend.store import Store,encode
from backend.services import registry,adaptive_plan


def read_json(value,default):
    try:return json.loads(value) if value else default
    except (ValueError,TypeError):return default


def import_v3(source,mapping=None,apply=False,target=None):
    source=Path(source).resolve()
    if not source.is_file():raise ValueError('找不到來源資料庫。')
    conn=sqlite3.connect(source.as_uri()+'?mode=ro',uri=True);conn.row_factory=sqlite3.Row
    try:
        conn.execute('BEGIN')
        rows=[dict(r) for r in conn.execute('''SELECT s.*,l.learner_code,l.profession FROM sessions s
                   JOIN learners l ON l.id=s.learner_id ORDER BY s.id''')]
        supported=[r for r in rows if r['profession'] in ('DT','PT','RT') and r['selected_symptom']=='肌少症']
        summary={'source_sessions':len(rows),'supported_sessions':len(supported),'unsupported_preserved_in_v3':len(rows)-len(supported),
                 'learner_ids':sorted({r['learner_id'] for r in supported}),'mode':'apply' if apply else 'dry_run'}
        if not apply:return summary
        mapping=mapping or {};db=target or Store()
        users={}
        for learner in summary['learner_ids']:
            username=mapping.get(str(learner))
            user=db.one("SELECT id FROM users WHERE username=? AND role='student'",(username,)) if username else None
            if not user:raise ValueError(f'舊 learner_id={learner} 缺少有效的 v4 學員帳號對照。匯入前請先建立帳號。')
            users[learner]=user['id']
        # Latest incomplete session per mapped user/profession/topic may be resumed; others are archived.
        latest={}
        for r in supported:
            if not r.get('report_text'):latest[(users[r['learner_id']],r['profession'],r['selected_symptom'])]=r['id']
        source_id=hashlib.sha256(str(source).lower().encode()).hexdigest()
        imported=skipped=0
        with db.tx() as c:
            c.execute('''CREATE TABLE IF NOT EXISTS legacy_imports(source_id TEXT,old_session_id INTEGER,
                         new_session_id INTEGER REFERENCES sessions(id),PRIMARY KEY(source_id,old_session_id))''')
            for r in supported:
                if c.execute('SELECT 1 FROM legacy_imports WHERE source_id=? AND old_session_id=?',(source_id,r['id'])).fetchone():
                    skipped+=1;continue
                uid=users[r['learner_id']];prof=r['profession'];topic=r['selected_symptom'];now=time.time()
                c.execute('INSERT OR IGNORE INTO progress VALUES (?,?,?,?,?)',(uid,prof,topic,1,now))
                case=registry.case(r.get('case_id') or '')
                if case and prof not in case['professions']:case=None
                completed=bool(r.get('report_text'))
                status='completed' if completed else 'active' if latest[(uid,prof,topic)]==r['id'] else 'archived'
                if status=='active' and c.execute("SELECT 1 FROM sessions WHERE user_id=? AND profession=? AND topic=? AND status='active'",(uid,prof,topic)).fetchone():
                    raise ValueError('目的帳號已有未完成訓練。請先完成或另選帳號，避免覆寫現有進度。')
                data={'version':'4.0.0','content_version':'legacy-v3-reconstructed','adaptive_plan':adaptive_plan(db,uid,prof,topic,1),
                      'trust':50,'decisions':{},'scene_events':[],
                      'legacy_import':{'source_session_id':r['id'],'source_learner_id':r['learner_id'],
                        'old_level_unreviewed':r.get('baseline_level'),'note':'舊原始紀錄保留；未核定Level不直接認列。內容以現有教案重建，需教師確認。'},
                      'legacy_raw':r}
                if case:
                    data['case_snapshot']=case;data['case_hash']=hashlib.sha256(encode(case).encode()).hexdigest()
                    for record in read_json(r.get('kdp_json'),[]):
                        q=next((q for q in case['kdp'] if q['id']==record.get('kdp_id')),None)
                        if q:
                            oi=next((i for i,o in enumerate(q['options']) if o['text']==record.get('choice_text')),None)
                            data['decisions'][q['id']]={'option_id':f'o{oi}' if oi is not None else 'legacy',
                                'score':record.get('score',0),'max_score':2,'feedback':record.get('feedback','舊版紀錄'),
                                'dimension':record.get('dimension',''),'source':'legacy_v3'}
                step=6 if completed else 4 if case and r.get('learning_completed') else 3 if case else 2
                if completed:
                    if not case:
                        data['case_snapshot']={'id':r.get('case_id') or 'LEGACY','title':'舊版教案紀錄（缺少相容內容）',
                          'summary':'僅保留歷史紀錄，重新訓練需選擇現行教案。','patient':'','goals':[],
                          'pre_knowledge':[],'rubric':[],'kdp':[],'quiz':[],'source_file':'legacy_v3'}
                    perf=read_json(r.get('performance_scores_json'),{})
                    data['result']={'decision_score':None,'quiz_score':None,'objective_score':perf.get('overall'),
                        'formula':'v3歷史原始分數，未依v4規則重新計分','teacher_status':'pending','level_suggestion':1,
                        'note':'舊版結果僅保留供教師查核；本次未重新認證或自動升等。'}
                    data['quiz_result']=[]
                sid=c.execute('INSERT INTO sessions(user_id,profession,topic,level,step,status,data,created,updated) VALUES (?,?,?,?,?,?,?,?,?)',
                    (uid,prof,topic,1,step,status,encode(data),now,now)).lastrowid
                for m in read_json(r.get('chat_json'),[]):
                    c.execute('INSERT INTO messages(session_id,role,content,source,metadata,created) VALUES (?,?,?,?,?,?)',
                        (sid,m.get('role','system'),m.get('content',''),'legacy_v3',encode({'source_session_id':r['id']}),now))
                c.execute('INSERT INTO legacy_imports VALUES (?,?,?)',(source_id,r['id'],sid))
                db.event(c,uid,sid,'legacy_import',data['legacy_import']);imported+=1
        summary.update(imported=imported,skipped=skipped)
        if target is None:db.conn.close()
        return summary
    finally:conn.close()


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--source',required=True);p.add_argument('--mapping');p.add_argument('--apply',action='store_true')
    args=p.parse_args()
    mapping=json.loads(Path(args.mapping).read_text(encoding='utf-8-sig')) if args.mapping else None
    try:print(json.dumps(import_v3(args.source,mapping,args.apply),ensure_ascii=False,indent=2))
    except Exception as e:raise SystemExit(str(e))
