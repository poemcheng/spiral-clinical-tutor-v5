"""Local bootstrap and consistent SQLite backups; normal accounts are managed in the UI."""
import argparse
import getpass
import secrets
from pathlib import Path
from backend.store import Store
from backend.config import RUNTIME

p=argparse.ArgumentParser()
sub=p.add_subparsers(dest='command',required=True)
sub.add_parser('init-demo')
sub.add_parser('init-admin')
u=sub.add_parser('create-user');u.add_argument('username');u.add_argument('--role',choices=['student','teacher'],required=True);u.add_argument('--name',default='')
b=sub.add_parser('backup');b.add_argument('destination')
from backend.postgres_store import open_store
args=p.parse_args();db=open_store()
if args.command=='init-admin':
    db.bootstrap_admin()
    print('管理員已備妥；既有管理員與密碼不變。首次安裝的隨機密碼只保存於 runtime/初始管理員帳號_*.txt。')
elif args.command=='init-demo':
    credentials=[]
    for username,role,name in [('demo','student','Level5全教材Demo學員'),('teacher','teacher','教學管理教師')]:
        if db.one('SELECT id FROM users WHERE username=?',(username,)):
            print(username+' 已存在，不變更密碼。');continue
        password=str(secrets.randbelow(900000)+100000)
        uid=db.create_user(username,password,role,name)
        if role=='student':
            import time
            with db.tx() as c:c.execute('INSERT INTO learning_access VALUES (?,?,?,?,?)',(uid,5,1,'Demo全教材學習授權，非能力核定或預填成績',time.time()))
        credentials.append(f'{name}\n帳號：{username}\n密碼：{password}\n')
    if credentials:
        file=RUNTIME/'初始帳號.txt'
        with file.open('a',encoding='utf-8') as f:f.write('\n'.join(credentials)+'\n登入網址：http://127.0.0.1:8700\n請由管理者妥善保管；勿放入跨院教材包。\n')
        print('初始帳號已建立，密碼僅保存在 '+str(file))
elif args.command=='create-user':
    from backend.workspace_settings import validate_password,password_policy
    policy=password_policy(db)
    password=getpass.getpass(f"密碼（{policy['minimum']}至{policy['maximum']}碼）：")
    validate_password(db,password)
    if password!=getpass.getpass('再次輸入密碼：'):raise SystemExit('密碼不一致。')
    db.create_user(args.username,password,args.role,args.name);print('帳號已建立。')
elif args.command=='backup':
    dest=Path(args.destination)
    if dest.exists():raise SystemExit('目的檔案已存在；請指定新檔名。')
    db.backup(dest);print('一致性資料庫備份完成。另需備份 runtime/media 及 data 內容包。')
