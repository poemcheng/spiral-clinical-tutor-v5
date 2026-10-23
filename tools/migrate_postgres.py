"""Copy a consistent SQLite snapshot to an EMPTY PostgreSQL database.

Explicit operator action only. Existing PostgreSQL learner data aborts the copy;
the source SQLite file is opened read-only and remains unchanged.
"""
import argparse,hashlib,json,os,sqlite3,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from backend.postgres_store import PostgresStore,ID_TABLES

def migrate(source,url):
    origin=sqlite3.connect(Path(source).resolve().as_uri()+'?mode=ro',uri=True);memory=sqlite3.connect(':memory:');origin.backup(memory);origin.close();memory.row_factory=sqlite3.Row
    target=PostgresStore(url)
    tables=['users','logins','progress','learning_progress','learning_access','attempts','sessions','messages','reviews','events']
    counts={}
    with target.tx() as connection:
        for table in tables:
            if target.one(f'SELECT COUNT(*) count FROM {table}')['count']:raise RuntimeError('目的資料庫非空白，停止移轉：'+table)
        for table in tables:
            rows=[dict(r) for r in memory.execute(f'SELECT * FROM {table}')]
            for row in rows:
                columns=list(row);connection.execute(f"INSERT INTO {table}({','.join(columns)}) VALUES ({','.join('?' for _ in columns)})",tuple(row.values()))
            actual=target.all(f'SELECT * FROM {table}')
            canonical=lambda values:sorted(json.dumps(x,sort_keys=True,ensure_ascii=False) for x in values)
            if canonical(actual)!=canonical(rows):raise RuntimeError('資料核對失敗，回復目的資料庫交易：'+table)
            counts[table]=len(rows)
            if table in ID_TABLES:
                connection.execute(f"SELECT setval(pg_get_serial_sequence('{table}','id'),COALESCE((SELECT MAX(id) FROM {table}),1),(SELECT COUNT(*)>0 FROM {table}))")
    memory.close();target.conn.close();return counts

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--source',type=Path,required=True);a=p.parse_args()
    if not os.getenv('DATABASE_URL'):raise SystemExit('請在環境變數設定目的 PostgreSQL DATABASE_URL；不要把密碼貼到命令列。')
    print(json.dumps({'verified_rows':migrate(a.source,os.environ['DATABASE_URL']),'source_unchanged':True}))
