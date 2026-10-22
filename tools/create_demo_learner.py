"""Create an explicitly authorized demo learner without fabricated assessments."""
import argparse,getpass,sys,time
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from backend.store import Store

def create(store,username,password):
    if store.one('SELECT id FROM users WHERE username=?',(username,)):
        raise ValueError('帳號已存在；保留原密碼與紀錄，請使用另一個名稱。')
    uid=store.create_user(username,password,'student','Level 5 全教材體驗學員')
    note='使用者授權之全教材體驗帳號；非實際練習成果或教師能力核定。'
    with store.tx() as c:
        c.execute('INSERT INTO learning_access VALUES (?,?,?,?,?)',(uid,5,1,note,time.time()))
        store.event(c,uid,None,'demo_learning_access_granted',{'level':5,'all_professions':True,'all_topics':True,'all_paths':True,'note':note})
    return uid

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('username');args=parser.parse_args()
    db=Store();uid=create(db,args.username,getpass.getpass('New learner password: '));db.conn.close()
    print(f'Created student #{uid}: {args.username}; all learning resources unlocked. No clinical scores fabricated.')
