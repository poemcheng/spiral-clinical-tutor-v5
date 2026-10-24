"""Independent empty demonstration runtime; never seeds the production database."""
import os,sys,json,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
WORK=ROOT/'runtime/recording-v5.6.1';WORK.mkdir(exist_ok=True)
os.environ['TUTOR_HOME']=str(WORK/'isolated-runtime')
for location in [ROOT/'runtime/models/faster-whisper-base',ROOT/'runtime/verification-5.3.2/isolated-runtime/models/faster-whisper-base']:
    if (location/'model.bin').is_file():os.environ['WHISPER_MODEL_PATH']=str(location);break
from backend import server
import uvicorn
credentials=json.loads((WORK/'fixture-credentials.json').read_text(encoding='utf8'))
for name,role,label in [('demo-video','student','操作示範學員（非真實成績）'),('teacher-video','teacher','操作示範教師'),('admin-video','admin','操作示範管理員')]:
    if not server.store.one('SELECT id FROM users WHERE username=?',(name,)):
        uid=server.store.create_user(name,credentials[name],role,label)
        if role=='student':
            with server.store.tx() as c:c.execute('INSERT INTO learning_access VALUES (?,?,?,?,?)',(uid,4,1,'操作示範先授權Level4；非能力核定或真實訓練成績',time.time()))
uvicorn.run(server.app,host='127.0.0.2',port=8714)
