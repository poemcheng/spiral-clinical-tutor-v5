"""Create isolated synthetic demo data by completing eight full real API workflows."""
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT),str(ROOT/'tests')]
from test_workflow import WorkflowTests
from backend.store import Store
from backend.config import RUNTIME
target=RUNTIME/'acceptance.sqlite3'
if target.exists():raise SystemExit('Acceptance seed exists; preserve it and choose a new TUTOR_HOME.')
test=WorkflowTests();test.setUp()
try:
    for i in range(8):
        sid,_=test.submit(test.enter(new=i>0));test.complete(sid)
    with test.db.tx() as c:c.execute("UPDATE users SET display_name='第五版示範學員（合成資料）' WHERE username='alice'")
    test.db.backup(target)
    print('Seeded eight complete synthetic workflows; earned Level 5; self difficulty remains independent.')
finally:test.tearDown()
