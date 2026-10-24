"""Explicit local reset requested by the installation owner; private recoverable backup."""
import argparse,datetime,json,secrets,shutil,sqlite3,sys,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from backend.store import Store
from backend.config import RUNTIME

def reset_installation(runtime):
    runtime=Path(runtime).resolve();runtime.mkdir(exist_ok=True)
    backup=(runtime/'private-account-reset-backups'/datetime.datetime.now().strftime('%Y%m%d-%H%M%S')).resolve()
    assert backup.is_relative_to(runtime)
    backup.mkdir(parents=True,exist_ok=False);db=Store(runtime/'clinical_tutor.sqlite3');db.backup(backup/'clinical_tutor.sqlite3')
    tables={r['name'] for r in db.all("SELECT name FROM sqlite_master WHERE type='table'")}
    with db.tx() as c:
        for table in ['teacher_lesson_revisions','teacher_lessons','reviews','messages','events','legacy_imports','sessions','attempts','progress','learning_progress','learning_access','logins','users']:
            if table in tables:c.execute('DELETE FROM '+table)
        c.execute("DELETE FROM app_settings WHERE key='password_policy'")
    credentials=[]
    for name,role,label in [('demo','student','Level5 全教材Demo學員'),('admin','admin','系統管理員'),('teacher','teacher','教學管理教師')]:
        password=str(secrets.randbelow(900000)+100000);uid=db.create_user(name,password,role,label)
        credentials.append({'username':name,'password':password,'role':role,'display_name':label})
        if role=='student':
            with db.tx() as c:c.execute('INSERT INTO learning_access VALUES (?,?,?,?,?)',(uid,5,1,'Demo全教材授權：Level5學習存取，非能力核定或預填成績',time.time()))
    db.conn.execute('PRAGMA wal_checkpoint(TRUNCATE)');db.conn.execute('VACUUM');db.conn.close()
    # Archive only installation-local learner output and old plaintext credential files.
    paths=[runtime/name for name in ['media','speech','voice-diagnostics','初始帳號.txt','本機管理與Demo帳號_20261024.txt']]
    paths+=list(runtime.glob('初始管理員帳號*.txt'))
    for source in paths:
        source=source.resolve();target=(backup/source.name).resolve()
        if source.exists():
            if not source.is_relative_to(runtime) or not target.is_relative_to(backup):raise ValueError('Archive path outside the authorized runtime')
            shutil.move(str(source),str(target))
    (runtime/'media').mkdir(exist_ok=True);(runtime/'speech').mkdir(exist_ok=True)
    file=runtime/'本機管理與Demo帳號_20261024.txt'
    text='v5.6.1 本機帳號（請勿公開或上傳GitHub）\n登入：https://192.168.68.108:8765/login\n\n'
    for x in credentials:text+=x['display_name']+'\n帳號：'+x['username']+'\n密碼：'+x['password']+'\n\n'
    text+='密碼長度預設4至6碼，可在管理員設定調整。Demo為Level5教材存取，沒有預填訓練成績。\n'
    file.write_text(text,encoding='utf8')
    counts={}
    c=sqlite3.connect(runtime/'clinical_tutor.sqlite3')
    for name in ['users','logins','attempts','sessions','messages','reviews','events','learning_progress','learning_access']:counts[name]=c.execute('SELECT COUNT(*) FROM '+name).fetchone()[0]
    assert counts=={'users':3,'logins':0,'attempts':0,'sessions':0,'messages':0,'reviews':0,'events':0,'learning_progress':0,'learning_access':1},counts
    assert not c.execute('PRAGMA foreign_key_check').fetchall();c.close()
    result={'reset':True,'counts':counts,'credential_file':str(file),'private_backup':str(backup)}
    (backup/'reset-result.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf8');return result

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--execute-authorized-reset',action='store_true');a=p.parse_args()
    if not a.execute_authorized_reset:raise SystemExit('No reset performed. Use --execute-authorized-reset only for an explicitly authorized installation reset.')
    print(json.dumps(reset_installation(RUNTIME),ensure_ascii=False))
