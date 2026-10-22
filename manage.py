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
args=p.parse_args();db=Store()
if args.command=='init-admin':
    db.bootstrap_admin()
    print('管理員 user 已備妥。首次安裝密碼依指定為 1234；既有密碼不會被重設。')
elif args.command=='init-demo':
    credentials=[]
    for username,role,name in [('student01','student','試辦學員'),('teacher01','teacher','試辦教師')]:
        if db.one('SELECT id FROM users WHERE username=?',(username,)):
            print(username+' 已存在，不變更密碼。');continue
        password=secrets.token_urlsafe(12)
        db.create_user(username,password,role,name)
        credentials.append(f'{name}\n帳號：{username}\n密碼：{password}\n')
    if credentials:
        file=RUNTIME/'初始帳號.txt'
        with file.open('a',encoding='utf-8') as f:f.write('\n'.join(credentials)+'\n登入網址：http://127.0.0.1:8700\n請由管理者妥善保管；勿放入跨院教材包。\n')
        print('初始帳號已建立，密碼僅保存在 '+str(file))
elif args.command=='create-user':
    password=getpass.getpass('密碼（至少10字元）：')
    if password!=getpass.getpass('再次輸入密碼：'):raise SystemExit('密碼不一致。')
    db.create_user(args.username,password,args.role,args.name);print('帳號已建立。')
elif args.command=='backup':
    dest=Path(args.destination)
    if dest.exists():raise SystemExit('目的檔案已存在；請指定新檔名。')
    db.backup(dest);print('一致性資料庫備份完成。另需備份 runtime/media 及 data 內容包。')
