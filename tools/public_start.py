"""Public service startup: bootstrap before accepting requests; one persistent worker."""
import os
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from backend.store import verify_password
from backend.postgres_store import open_store
import uvicorn
db=open_store()
existing=db.one("SELECT password_hash FROM users WHERE username='user'")
if existing and verify_password('1234',existing['password_hash']):
    raise SystemExit('Existing local default password detected. Use a clean deployment volume and BOOTSTRAP_ADMIN_PASSWORD; do not publish a local learner database.')
db.bootstrap_admin();db.conn.close()
uvicorn.run('backend.server:app',host='0.0.0.0',port=int(os.getenv('PORT',os.getenv('PLATFORM_PORT','8705'))),workers=1)
