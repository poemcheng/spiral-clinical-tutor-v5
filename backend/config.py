import os
from pathlib import Path
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / '.env')
RUNTIME = Path(os.getenv('TUTOR_HOME', str(ROOT / 'runtime'))).resolve()
RUNTIME.mkdir(parents=True, exist_ok=True)
DB_PATH = RUNTIME / 'clinical_tutor.sqlite3'
VERSION = '5.2.0'
