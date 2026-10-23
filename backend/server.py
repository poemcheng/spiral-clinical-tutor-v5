"""Authenticated six-stage clinical education platform v4."""
import hashlib
import json
import mimetypes
import os
import secrets
import sqlite3
import threading
import time
from collections import defaultdict
from pathlib import Path
from typing import Annotated, Any

from fastapi import Cookie, Depends, FastAPI, HTTPException, Request, Response
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, StrictInt
from .config import ROOT, RUNTIME, VERSION
from .store import Store, encode, verify_password, password_hash
from .assessment import create_snapshot, public_snapshot, score_snapshot
from .stage1_bank import BANK_VERSION, profession_catalog
from .services import registry, llm, adaptive_plan, patient_reply, peer_reply, livekit_token
from .legacy.builtin_cases import PROFESSIONS
from .legacy.config import VIDEO_LIBRARY_DIR
from .legacy.content import resolve_persona
from .legacy.video_generator import generate_video_script
from .legacy import video_renderer
from . import curriculum, virtual_video, characters, voice_bridge, h5p_content, progression, speech_input,learning_curriculum
from starlette.concurrency import run_in_threadpool

# Windows registry may classify .js as text/plain, which breaks module scripts with nosniff.
mimetypes.add_type('application/javascript', '.js')
mimetypes.add_type('text/css', '.css')
app = FastAPI(title='醫事人員智慧訓練平台', version=VERSION)
store = Store()
conversation_locks = defaultdict(threading.Lock)
video_locks = defaultdict(threading.Lock)
login_failures = defaultdict(list)
login_lock = threading.Lock()
COOKIE = 'clinical_v5_session'
dummy_password = password_hash(secrets.token_hex(20))


@app.on_event('startup')
def recover_interrupted_jobs():
    progression.migrate_legacy(store)
    with store.tx() as c:
        for row in store.all('SELECT id,data FROM sessions'):
            data = json.loads(row['data'])
            interrupted=False
            for job in data.get('pose_jobs',[]):
                if job['status']=='running':
                    job.update(status='failed',error='伺服器重新啟動，逐格分析中斷；請重新分析。');interrupted=True
            if interrupted:store.save(c,row['id'],data)
            if data.get('video_job', {}).get('status') == 'running':
                data['video_job'] = {'status':'failed','error':'伺服器重新啟動，影片工作已中斷；請重新產生。'}
                store.save(c, row['id'], data)


@app.middleware('http')
async def same_origin(request: Request, call_next):
    origin = request.headers.get('origin')
    if request.method not in ('GET', 'HEAD', 'OPTIONS') and origin:
        from urllib.parse import urlparse
        if urlparse(origin).netloc != request.headers.get('host'):
            from fastapi.responses import JSONResponse
            return JSONResponse({'detail': '拒絕跨來源寫入。'}, status_code=403)
    response = await call_next(request)
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['Referrer-Policy'] = 'same-origin'
    response.headers['X-Frame-Options'] = 'SAMEORIGIN'
    if request.url.path.startswith('/api/') or request.url.path in ('/','/login') or request.url.path in ('/static/index.html','/static/app.js'):
        response.headers['Cache-Control'] = 'no-store'
    return response


def current_user(clinical_v5_session: Annotated[str | None, Cookie()] = None):
    token_hash = hashlib.sha256((clinical_v5_session or '').encode()).hexdigest()
    user = store.one('''SELECT u.id,u.username,u.display_name,u.role,l.id login_id FROM logins l
      JOIN users u ON u.id=l.user_id WHERE l.token_hash=? AND l.expires>? AND u.enabled=1''',
                     (token_hash, time.time()))
    if not user:
        raise HTTPException(401, '請先使用帳號密碼登入。')
    return user


def teacher(user=Depends(current_user)):
    if user['role'] != 'teacher':
        raise HTTPException(403, '此操作僅限教師。')
    return user


def student(user=Depends(current_user)):
    if user['role'] != 'student':
        raise HTTPException(403, '此操作僅限學員。')
    return user


def administrator(user=Depends(current_user)):
    if user['role'] != 'admin':
        raise HTTPException(403, '此操作僅限管理員。')
    return user


def owned_session(sid, user, require_checkin=True):
    row = store.one('SELECT * FROM sessions WHERE id=?', (sid,))
    if not row or (user['role'] != 'teacher' and row['user_id'] != user['id']):
        raise HTTPException(404, '找不到可存取的訓練。')
    if user['role'] == 'student' and require_checkin:
        latest = store.one('''SELECT completed FROM attempts WHERE login_id=? AND profession=? AND topic=?
                              ORDER BY id DESC LIMIT 1''', (user['login_id'], row['profession'], row['topic']))
        if not latest or not latest['completed']:
            raise HTTPException(409, '本次登入請先完成職種自評，再續訓。')
    row['payload'] = json.loads(row['data'])
    return row


def need_step(row, step):
    if row['status'] != 'active' or row['step'] != step:
        raise HTTPException(409, f'請依訓練流程操作；目前為 Step {row["step"]}。')


def case_for(row):
    case = row['payload'].get('case_snapshot')
    if not case:
        raise HTTPException(409, '請先選擇教案。')
    return case


def session_public(row):
    data = dict(row['payload'])
    case = data.pop('case_snapshot', None)
    if case:
        if case['id'].startswith('COURSE-') and case.get('curriculum_version'):data['content_version']=case['curriculum_version']
        data['case'] = {k: case.get(k) for k in ('id', 'title', 'summary', 'patient', 'goals', 'pre_knowledge', 'source_file', 'rubric','source_pages','variant','review_status','clinical_review','lesson_path','clinical_review_version')}
    if row['step'] < 6:
        data.pop('quiz_result', None)
        if 'quiz_snapshot' in data:
            data['quiz_snapshot'] = [{k: v for k, v in q.items() if k not in ('answer', 'explain')}
                                     for q in data['quiz_snapshot']]
    return {'id': row['id'], 'profession': row['profession'], 'topic': row['topic'],
            'level': row['level'], 'step': row['step'], 'status': row['status'],
            'data': data, 'updated': row['updated']}


class LoginBody(BaseModel):
    username: str = Field(min_length=1, max_length=80)
    password: str = Field(min_length=1, max_length=256)


@app.post('/api/auth/login')
def login(body: LoginBody, response: Response, request: Request):
    key = (request.client.host if request.client else '')
    now = time.time()
    with login_lock:
        login_failures[key] = [t for t in login_failures[key] if now-t < 300]
        if len(login_failures[key]) >= 15:
            raise HTTPException(429, '登入嘗試過多，請五分鐘後再試。')
    user = store.one('SELECT * FROM users WHERE username=?', (body.username.strip(),))
    valid = verify_password(body.password, user['password_hash'] if user else dummy_password)
    if not user or not valid or not user['enabled']:
        with login_lock:
            login_failures[key].append(now)
        raise HTTPException(401, '帳號或密碼錯誤。')
    token = secrets.token_urlsafe(40)
    with store.tx() as c:
        old = request.cookies.get(COOKIE)
        if old:
            c.execute('UPDATE logins SET expires=0 WHERE token_hash=? AND user_id=?',
                      (hashlib.sha256(old.encode()).hexdigest(), user['id']))
        c.execute('INSERT INTO logins(token_hash,user_id,expires) VALUES (?,?,?)',
                  (hashlib.sha256(token.encode()).hexdigest(), user['id'], now+12*3600))
        store.event(c, user['id'], None, 'login', {'role': user['role']})
    response.set_cookie(COOKIE, token, httponly=True, samesite='strict',
                        secure=os.getenv('COOKIE_SECURE', '0') == '1')
    return {k: user[k] for k in ('id', 'username', 'display_name', 'role')}


@app.post('/api/auth/logout')
def logout(request: Request, response: Response):
    revoke_browser_login(request)
    response.delete_cookie(COOKIE)
    return {'ok': True}


def revoke_browser_login(request: Request):
    # Keep the attribution row and all learning evidence; expire only this token.
    token=request.cookies.get(COOKIE)
    if token:
        with store.tx() as c:
            c.execute('UPDATE logins SET expires=0 WHERE token_hash=?',
                      (hashlib.sha256(token.encode()).hexdigest(),))


@app.get('/api/me')
def me(user=Depends(current_user)):
    return user


@app.get('/api/catalog')
def catalog(user=Depends(current_user)):
    return {'version': VERSION, 'combinations': profession_catalog(registry), 'courses':curriculum.public_courses(),
            'learning_policy':progression.POLICY,
            'question_status': '12 職種 × 5 Levels 分層自評草稿，待職類教師核定。'}


class AccountBody(BaseModel):
    username: str = Field(min_length=1, max_length=80)
    password: str = Field(min_length=10, max_length=256)
    display_name: str = Field(min_length=1, max_length=80)
    role: str


class AccountUpdateBody(BaseModel):
    display_name: str = Field(min_length=1, max_length=80)
    role: str
    enabled: bool
    password: str | None = Field(default=None, min_length=10, max_length=256)


@app.get('/api/admin/users')
def admin_users(user=Depends(administrator)):
    return store.all('''SELECT id,username,display_name,role,enabled FROM users ORDER BY id''')


@app.post('/api/admin/users', status_code=201)
def admin_create_user(body: AccountBody, user=Depends(administrator)):
    if body.role not in ('student', 'teacher') or not body.username.strip() or not body.display_name.strip():
        raise HTTPException(400, '請設定學員或教師角色，並填寫帳號及姓名。')
    try:
        with store.tx() as c:
            uid = c.execute('INSERT INTO users(username,password_hash,display_name,role) VALUES (?,?,?,?)',
                            (body.username.strip(), password_hash(body.password), body.display_name.strip(), body.role)).lastrowid
            store.event(c, user['id'], None, 'admin_account_created', {'user_id': uid, 'role': body.role})
    except sqlite3.IntegrityError:
        raise HTTPException(409, '此帳號已存在，請改用其他帳號。')
    return {'id': uid, 'username': body.username.strip(), 'role': body.role}


@app.patch('/api/admin/users/{uid}')
def admin_update_user(uid: int, body: AccountUpdateBody, user=Depends(administrator)):
    if body.role not in ('student', 'teacher') or not body.display_name.strip():
        raise HTTPException(400, '請設定學員或教師角色及姓名。')
    with store.tx() as c:
        target = c.execute('SELECT id,role FROM users WHERE id=?', (uid,)).fetchone()
        if not target:
            raise HTTPException(404, '找不到帳號。')
        if target['role'] == 'admin':
            raise HTTPException(400, '管理員帳號不在學員／教師帳號編輯範圍。')
        c.execute('UPDATE users SET display_name=?,role=?,enabled=? WHERE id=?',
                  (body.display_name.strip(), body.role, int(body.enabled), uid))
        if body.password:
            c.execute('UPDATE users SET password_hash=? WHERE id=?', (password_hash(body.password), uid))
        c.execute('UPDATE logins SET expires=0 WHERE user_id=?', (uid,))
        store.event(c, user['id'], None, 'admin_account_updated',
                    {'user_id': uid, 'role': body.role, 'enabled': body.enabled, 'password_reset': bool(body.password)})
    return {'saved': True}


@app.get('/api/admin/question-preview')
def admin_question_preview(profession: str, level: int = 1, user=Depends(administrator)):
    if profession not in PROFESSIONS or not 1 <= level <= 5:
        raise HTTPException(400, '請選擇 12 職種之一及 Level 1–5。')
    # Preview cannot create an attempt, change a student's level or expose objective answers.
    return public_snapshot(create_snapshot(registry, profession, '肌少症', level))


class EntryBody(BaseModel):
    profession: str
    topic: str = '肌少症'
    new_round: bool = False


@app.post('/api/entry')
def entry(body: EntryBody, user=Depends(student)):
    if not any(c['profession'] == body.profession and c['symptom'] == body.topic
               for c in catalog(user)['combinations']) and not curriculum.available(registry,body.profession,body.topic):
        raise HTTPException(400, '此職種與主題尚未開放。')
    with store.tx() as c:
        c.execute('INSERT OR IGNORE INTO progress VALUES (?,?,?,?,?)',
                  (user['id'], body.profession, body.topic, 1, time.time()))
        progress = c.execute('SELECT * FROM progress WHERE user_id=? AND profession=? AND topic=?',
                             (user['id'], body.profession, body.topic)).fetchone()
        learning_level=progression.level_state(store,user['id'],body.profession,body.topic)
        assessment_level=progression.assessment_level(store,user['id'],body.profession,body.topic)
        attempt = c.execute('''SELECT * FROM attempts WHERE login_id=? AND profession=? AND topic=?
            ORDER BY id DESC LIMIT 1''', (user['login_id'], body.profession, body.topic)).fetchone()
        active = c.execute("SELECT * FROM sessions WHERE user_id=? AND profession=? AND topic=? AND status='active'",
                           (user['id'], body.profession, body.topic)).fetchone()
        if body.new_round and active:
            raise HTTPException(409, '尚有未完成訓練，請先續訓。')
        if not attempt or body.new_round:
            previous = c.execute('''SELECT snapshot FROM attempts WHERE user_id=? AND profession=? AND topic=?
                ORDER BY id DESC LIMIT 1''', (user['id'], body.profession, body.topic)).fetchone()
            snapshot = create_snapshot(registry, body.profession, body.topic, assessment_level,
                                       json.loads(previous['snapshot']) if previous else None)
            aid = c.execute('''INSERT INTO attempts(login_id,user_id,profession,topic,level,snapshot,created)
                            VALUES (?,?,?,?,?,?,?)''', (user['login_id'], user['id'], body.profession,
                            body.topic, assessment_level, encode(snapshot), time.time())).lastrowid
            attempt = c.execute('SELECT * FROM attempts WHERE id=?', (aid,)).fetchone()
        sid = active['id'] if active else None
        if attempt['completed'] and not sid:
            last = c.execute('SELECT id FROM sessions WHERE user_id=? AND profession=? AND topic=? ORDER BY id DESC LIMIT 1',
                             (user['id'], body.profession, body.topic)).fetchone()
            sid = last['id'] if last else None
        return {'attempt_id': attempt['id'], 'assessment_required': not bool(attempt['completed']),
                'approved_level': progress['approved_level'], 'resume_session_id': sid,
                'learning_level':learning_level,
                'assessment_level':assessment_level,
                'has_history': bool(sid), 'snapshot': public_snapshot(json.loads(attempt['snapshot'])),
                'draft': json.loads(attempt['answers'] or '{}'),
                'training_available': curriculum.available(registry,body.profession,body.topic),
                'scores': json.loads(attempt['scores'] or '{}'),
                'note': '每次重新登入完成輪替自評後續訓；重新整理保留本次題目及草稿。'}


class AssessmentBody(BaseModel):
    answers: dict[str, StrictInt] = {}
    objective_answers: dict[str, str] = {}


def own_attempt(aid, user):
    row = store.one('SELECT * FROM attempts WHERE id=? AND user_id=? AND login_id=?',
                    (aid, user['id'], user['login_id']))
    if not row:
        raise HTTPException(404, '找不到本次登入的自評。')
    latest = store.one('SELECT MAX(id) id FROM attempts WHERE login_id=? AND profession=? AND topic=?',
                      (user['login_id'], row['profession'], row['topic']))
    if latest['id'] != aid:
        raise HTTPException(409, '此自評已由新一輪題本取代。')
    return row


@app.put('/api/assessments/{aid}/draft')
def draft(aid: int, body: AssessmentBody, user=Depends(student)):
    row = own_attempt(aid, user)
    if row['completed']:
        raise HTTPException(409, '已完成自評不可覆寫。')
    snap = json.loads(row['snapshot'])
    if set(body.answers) - {q['item_id'] for q in snap['items']} or any(v < 1 or v > 5 for v in body.answers.values()):
        raise HTTPException(400, '草稿題目或分數不符。')
    if set(body.objective_answers) - {q['item_id'] for q in snap['objectives']} or any(len(x) > 4000 for x in body.objective_answers.values()):
        raise HTTPException(400, '草稿前測題目或答案不符。')
    with store.tx() as c:
        updated = c.execute('UPDATE attempts SET answers=? WHERE id=? AND completed IS NULL',
                            (encode(body.model_dump()), aid)).rowcount
        if not updated:
            raise HTTPException(409, '已完成自評不可覆寫。')
    return {'saved': True}


@app.post('/api/assessments/{aid}/submit')
def submit_assessment(aid: int, body: AssessmentBody, user=Depends(student)):
    with store.tx() as c:
        row = own_attempt(aid, user)
        if row['completed']:
            if json.loads(row['answers']) != body.model_dump():
                raise HTTPException(409, '已完成自評不可改答。')
            last = c.execute('SELECT id FROM sessions WHERE user_id=? AND profession=? AND topic=? ORDER BY id DESC LIMIT 1',
                            (user['id'], row['profession'], row['topic'])).fetchone()
            return {'session_id': last['id'] if last else None, 'scores': json.loads(row['scores']), 'assessment_complete': True}
        try:
            scores = score_snapshot(json.loads(row['snapshot']), body.answers, body.objective_answers)
        except ValueError as e:
            raise HTTPException(400, str(e))
        placement=progression.place(store,c,user['id'],row['profession'],row['topic'],scores)
        c.execute('UPDATE attempts SET answers=?,scores=?,completed=? WHERE id=?',
                  (encode(body.model_dump()), encode(scores), time.time(), aid))
        available = curriculum.available(registry,row['profession'],row['topic'])
        if not available:
            store.event(c, user['id'], None, 'assessment_completed', {'attempt_id': aid,'placement':placement,'assessment_only': True})
            return {'session_id': None, 'scores': scores, 'assessment_complete': True}
        active = c.execute("SELECT id FROM sessions WHERE user_id=? AND profession=? AND topic=? AND status='active'",
                           (user['id'], row['profession'], row['topic'])).fetchone()
        if active:
            sid = active['id']
            existing = json.loads(c.execute('SELECT data FROM sessions WHERE id=?', (sid,)).fetchone()['data'])
            if not existing.get('assessment_attempt_id'):
                existing['assessment_attempt_id'] = aid
                store.save(c, sid, existing)
        else:
            level = placement['self_level']
            plan = adaptive_plan(store, user['id'], row['profession'], row['topic'], level)
            data = {'assessment_attempt_id': aid, 'adaptive_plan': plan, 'version': VERSION,
                    'interaction_policy':characters.pairing(row['profession']),
                    'level_axis':'self-assessment','self_level':level,'learning_level_snapshot':placement['learning_level'],
                    'content_version': 'v3-import-20261021', 'trust': 50, 'decisions': {}, 'scene_events': []}
            sid = c.execute('''INSERT INTO sessions(user_id,profession,topic,level,data,created,updated)
                     VALUES (?,?,?,?,?,?,?)''', (user['id'], row['profession'], row['topic'], level,
                     encode(data), time.time(), time.time())).lastrowid
        placement['session_level']=store.one('SELECT level FROM sessions WHERE id=?',(sid,))['level']
        placement['applies_next_round']=placement['session_level']!=placement['self_level']
        c.execute('UPDATE attempts SET scores=? WHERE id=?',(encode(scores),aid))
        store.event(c, user['id'], sid, 'assessment_completed', {'attempt_id': aid,'placement':placement})
    return {'session_id': sid, 'scores': scores, 'assessment_complete': True}


def assessment_record(aid, user, faculty=False):
    row = store.one('''SELECT a.*,u.display_name,u.username FROM attempts a
                      JOIN users u ON u.id=a.user_id WHERE a.id=?''', (aid,))
    if not row or (not faculty and row['user_id'] != user['id']):
        raise HTTPException(404, '找不到可存取的自評。')
    for field in ('snapshot', 'answers', 'scores'):
        row[field] = json.loads(row[field] or '{}')
    row['item_reviews']=[{'id':r['id'],'created':r['created'],'teacher':r['teacher'],**json.loads(r['data'])}
        for r in store.all("SELECT e.*,u.display_name teacher FROM events e JOIN users u ON u.id=e.user_id WHERE kind='assessment_item_review' AND json_extract(e.data,'$.attempt_id')=? ORDER BY e.id",(aid,))]
    row['current_learning_level']=progression.level_state(store,row['user_id'],row['profession'],row['topic'])
    if not faculty:
        row['snapshot'] = public_snapshot(row['snapshot'])
    return row


@app.get('/api/assessments/{aid}')
def get_assessment(aid: int, user=Depends(student)):
    return assessment_record(aid, user)


@app.get('/api/teacher/assessments/{aid}')
def teacher_assessment(aid: int, user=Depends(teacher)):
    return assessment_record(aid, user, faculty=True)


class ItemReviewBody(BaseModel):
    item_id:str
    score:StrictInt=Field(ge=0,le=2)
    note:str=Field(min_length=5,max_length=2000)
    expected_review_id:int=0


@app.post('/api/teacher/assessments/{aid}/review')
def review_open_item(aid:int,body:ItemReviewBody,user=Depends(teacher)):
    with store.tx() as c:
        attempt=store.one('SELECT snapshot,completed FROM attempts WHERE id=?',(aid,))
        if not attempt or not attempt['completed']:raise HTTPException(409,'請先完成自評提交。')
        question=next((q for q in json.loads(attempt['snapshot'])['objectives'] if q['item_id']==body.item_id),None)
        if not question or question['item_type']=='single_choice' or body.score>question['max_score']:raise HTTPException(400,'開放題或評分不符。')
        latest=store.one("SELECT id FROM events WHERE kind='assessment_item_review' AND json_extract(data,'$.attempt_id')=? AND json_extract(data,'$.item_id')=? ORDER BY id DESC LIMIT 1",(aid,body.item_id))
        if (latest['id'] if latest else 0)!=body.expected_review_id:raise HTTPException(409,'此題已有較新教師評閱，請重新載入。')
        store.event(c,user['id'],None,'assessment_item_review',{'attempt_id':aid,'item_id':body.item_id,'score':body.score,
            'max_score':question['max_score'],'note':body.note,'status':'teacher_reviewed','rubric':question.get('rubric'),
            'form_hash':json.loads(attempt['snapshot'])['content_hash']})
    return {'saved':True,'level_changed':False}


@app.get('/api/sessions/{sid}')
def get_session(sid: int, user=Depends(current_user)):
    row = owned_session(sid, user)
    result = session_public(row)
    result['messages'] = store.all('SELECT * FROM messages WHERE session_id=? ORDER BY id', (sid,))
    result['reviews'] = store.all('''SELECT r.*,u.display_name teacher FROM reviews r JOIN users u ON u.id=r.teacher_id
                                  WHERE session_id=? ORDER BY r.id''', (sid,))
    result['assessment'] = store.one('SELECT scores FROM attempts WHERE id=?',
                                     (row['payload'].get('assessment_attempt_id', 0),))
    return result


@app.get('/api/sessions/{sid}/cases')
def cases(sid: int, user=Depends(student)):
    row = owned_session(sid, user)
    scores=store.one('SELECT scores FROM attempts WHERE id=?',(row['payload'].get('assessment_attempt_id',0),))
    return [{**{k: adapted.get(k) for k in ('id','title','summary','goals','source_file','source_pages','variant','review_status','clinical_review')},
            'learning_path':[{k:l[k] for k in ('level','title','unlocked','lesson_count')} for l in learning_curriculum.levels(adapted,row['profession'],row['payload']['adaptive_plan'].get('learning_level',1))],
            'paths':row['payload']['adaptive_plan'].get('paths',progression.plan(store,row['user_id'],row['profession'],row['topic'],row['level'])['paths'])}
            for case in registry.cases_for(row['topic'],row['profession'])
            for adapted in [curriculum.adapt_case(case,row['profession'],row['level'],json.loads(scores['scores'] or '{}') if scores else {})]]


class CaseBody(BaseModel):
    case_id: str
    path_id: str = 'core'


@app.post('/api/sessions/{sid}/case')
def select_case(sid: int, body: CaseBody, user=Depends(student)):
    with store.tx() as c:
        row = owned_session(sid, user)
        need_step(row, 2)
        paths=row['payload']['adaptive_plan'].get('paths',progression.plan(store,row['user_id'],row['profession'],row['topic'],row['level'])['paths'])
        path=next((p for p in paths if p['id']==body.path_id),None)
        if not path:raise HTTPException(400,'未知教案路徑。')
        if not path['unlocked']:raise HTTPException(403,'此教案尚未解鎖：'+path['requirement'])
        case = registry.case(body.case_id)
        if not case or case['symptom'] != row['topic'] or row['profession'] not in case['professions']:
            raise HTTPException(400, '教案不適用此職種與主題。')
        assessment=store.one('SELECT scores FROM attempts WHERE id=?',(row['payload'].get('assessment_attempt_id',0),))
        case=curriculum.adapt_case(case,row['profession'],row['level'],json.loads(assessment['scores'] or '{}') if assessment else {})
        case['lesson_path']={k:path[k] for k in ('id','title','requirement')}
        if path['id']!='core' and case.get('variant'):
            task='以同理與回覆示教處理本案例疑慮，練習本職類弱項。' if path['id']=='communication' else '依本職類已知資料整理SBAR，與團隊核對資訊缺口及追蹤。'
            case['variant']['learner_task']=task+case['variant']['learner_task']
            case['goals']=[task,*case['goals']]
        row['payload']['case_snapshot'] = case
        row['payload']['content_version']=case.get('curriculum_version','v3-import-20261021')
        row['payload']['case_hash'] = hashlib.sha256(encode(case).encode()).hexdigest()
        store.save(c, sid, row['payload'], step=3)
        store.event(c, user['id'], sid, 'case_selected', {'case_id': case['id']})
    return {'step': 3}


@app.get('/api/sessions/{sid}/learning')
def learning(sid: int, user=Depends(current_user)):
    row = owned_session(sid, user)
    case = case_for(row)
    vl = original_video(case)
    return {'plan':row['payload']['adaptive_plan'],'information':progression.information_for(case,row['payload']['adaptive_plan']),'knowledge':case['pre_knowledge'],'rubric':case['rubric'],'clinical_review':case.get('clinical_review'),'lesson_path':case.get('lesson_path'),
        'variant':case.get('variant'),'source_pages':case.get('source_pages'),
        'resources':__import__('backend.learning_resources',fromlist=['resources']).resources(row,case),
        'library_video':{'title':vl['title'],'url':f'/api/sessions/{sid}/library-video','available':vl['video_available']} if vl else None,
        'video_job':row['payload'].get('video_job'),'script':row['payload'].get('video_script'),
        'note':'虛擬講師依本輪教案快照合成中文語音與擬真人像表情；教學內容待教師審核。'}


def original_video(case):
    if case.get('video_file'):
        return {'title':case['title'],'video_file':case['video_file'],'video_available':(VIDEO_LIBRARY_DIR/case['video_file']).is_file()}
    vl=registry.video_lesson(case['id'])
    if not vl and case.get('symptom')=='肌少症':vl=registry.video_lesson('SARC-PT-001')
    return vl


@app.get('/api/sessions/{sid}/library-video')
def library_video(sid:int,user=Depends(current_user)):
    row=owned_session(sid,user)
    if row['payload'].get('interaction_policy') and row['payload']['adaptive_plan'].get('learning_level',1)<3:
        raise HTTPException(403,'情境影片需累積學習 Level 3。')
    vl=original_video(case_for(row))
    path=(VIDEO_LIBRARY_DIR/(vl or {}).get('video_file','')).resolve()
    if not path.is_relative_to(VIDEO_LIBRARY_DIR.resolve()) or not path.is_file():raise HTTPException(404,'此教案尚無原始影片。')
    return FileResponse(path,media_type='video/mp4')


@app.get('/api/materials/{kind}')
def source_material(kind:str,user=Depends(current_user)):
    names={'curriculum':'跨職種擬真教案（依自評等級分流）.pdf','questions':'肌少症自評題庫_審題表_20261021.xlsx'}
    if kind not in names:raise HTTPException(404,'找不到來源文件。')
    if kind=='questions' and user['role'] not in ('teacher','admin'):raise HTTPException(403,'完整題庫與答案限教師及管理員。')
    path=ROOT/'data/sources'/names[kind]
    if not path.is_file():raise HTTPException(404,'公開程式碼包未含原始教材，請由教材管理者另行安裝。')
    return FileResponse(path,filename=names[kind])


def video_worker(sid,case,row,module):
    with video_locks[sid]:
        try:
            output,manifest=virtual_video.render(case,row,module)
            destination=RUNTIME/'media'/f'session_{sid*10+module}'/f'virtual_training_video_{manifest["key"]}.mp4'
            destination.parent.mkdir(parents=True,exist_ok=True)
            import shutil
            shutil.copyfile(output,destination)
            with store.tx() as c:
                payload=json.loads(store.one('SELECT data FROM sessions WHERE id=?',(sid,))['data'])
                previous=payload.setdefault('generated_videos',{}).get(str(module))
                if previous:payload.setdefault('generated_video_history',[]).append(previous)
                payload['generated_videos'][str(module)]={**manifest,'module':module,'file_name':destination.name,'url':f'/api/sessions/{sid}/generated-video/{module}?version={manifest["key"]}'}
                payload['generated_videos'][str(module)]['immersive_url']=f'/api/sessions/{sid}/generated-lesson/{module}/immersive.html'
                payload['video_script']=manifest
                payload['video_job']={'status':'completed','module':module,'source':manifest['source'],'has_audio':True,'note':'three.js診間講師影片已完成，並附可環顧的沉浸式教案。'}
                store.save(c,sid,payload)
        except Exception as e:
            with store.tx() as c:
                payload=json.loads(store.one('SELECT data FROM sessions WHERE id=?',(sid,))['data'])
                payload['video_job']={'status':'failed','error':str(e),'module':module}
                store.save(c,sid,payload)


class ModuleBody(BaseModel):
    module: int = Field(default=0, ge=0, le=2)


@app.get('/api/sessions/{sid}/generated-lesson/{module}/{asset}')
def generated_lesson(sid:int,module:int,asset:str,user=Depends(current_user)):
    row=owned_session(sid,user)
    video=row['payload'].get('generated_videos',{}).get(str(module),{})
    key=video.get('key','')
    import re
    allowed={'immersive.html','lecturer.js','actor-model.glb','actor-atlas.png','voice-0.wav','voice-1.wav','voice-2.wav'}
    if asset not in allowed or not re.fullmatch('[0-9a-f]{20}',key):raise HTTPException(404,'尚未生成此沉浸式教案。')
    path=RUNTIME/'virtual_lessons'/key/asset
    if not path.is_file():raise HTTPException(404,'此歷史影片沒有沉浸場景，請重新產生。')
    return FileResponse(path)


@app.post('/api/sessions/{sid}/video')
def create_video(sid: int, body: ModuleBody, user=Depends(student)):
    with store.tx() as c:
        row = owned_session(sid, user)
        if row['step'] < 3:
            raise HTTPException(409, '請先完成前兩階段。')
        case = case_for(row)
        if body.module >= row['payload']['adaptive_plan']['video_count']:
            raise HTTPException(403, '此補強影片尚未解鎖。')
        if row['payload'].get('video_job', {}).get('status') == 'running':
            return row['payload']['video_job']
        existing=row['payload'].get('generated_videos',{}).get(str(body.module),{})
        actor=characters.selected(row,'lecturer')
        if existing.get('source')=='source_bound_virtual_lecturer' and existing.get('actor',{}).get('id')==actor['id'] and existing.get('actor',{}).get('version')==actor['version'] and existing.get('actor',{}).get('realistic_model_sha256')==actor.get('realistic_model_sha256') and existing.get('renderer')==virtual_video.RENDERER:
            return {'status': 'completed', 'cached': True}
        row['payload']['video_job'] = {'status': 'running', 'module': body.module}
        store.save(c, sid, row['payload'])
    threading.Thread(target=video_worker, args=(sid, case, row, body.module), daemon=True).start()
    return {'status': 'running'}


@app.get('/api/sessions/{sid}/generated-video/{module}')
def generated_video(sid: int, module: int, version:str|None=None,user=Depends(current_user)):
    row = owned_session(sid, user)
    if str(module) not in row['payload'].get('generated_videos', {}):
        raise HTTPException(404, '影片尚未完成。')
    record=row['payload']['generated_videos'][str(module)]
    if version and record.get('key')!=version:
        record=next((v for v in row['payload'].get('generated_video_history',[]) if v.get('key')==version and v.get('module')==module),None)
        if not record:raise HTTPException(404,'找不到影片版本。')
    filename=record.get('file_name','training_video.mp4')
    import re
    if filename not in ('training_video.mp4','virtual_training_video.mp4') and not re.fullmatch(r'virtual_training_video_[a-f0-9]{20}\.mp4',filename):raise HTTPException(404,'無效影片路徑。')
    return FileResponse(RUNTIME / 'media' / f'session_{sid*10+module}' / filename, media_type='video/mp4')


class LearnBody(BaseModel):
    reflection: str = Field(min_length=10, max_length=4000)
    completed_modules: list[int]
    observed: bool


@app.post('/api/sessions/{sid}/learned')
def learned(sid: int, body: LearnBody, user=Depends(student)):
    with store.tx() as c:
        row = owned_session(sid, user)
        need_step(row, 3)
        required = set(range(row['payload']['adaptive_plan']['video_count']))
        if set(body.completed_modules) != required or not body.observed:
            raise HTTPException(400, '請完成已解鎖教材模組及觀察反思。')
        row['payload']['learning'] = {**body.model_dump(), 'record_type': 'learner_attested', 'at': time.time()}
        store.save(c, sid, row['payload'], step=4)
        store.event(c, user['id'], sid, 'learning_completed', body.model_dump())
    return {'step': 4}


def decision_questions(row):
    questions = []
    for q in case_for(row)['kdp']:
        options = [{'id': f'o{i}', 'text': o['text']} for i, o in enumerate(q['options'])]
        secrets.SystemRandom().shuffle(options)
        questions.append({'id': q['id'], 'phase': q.get('phase', ''), 'prompt': q['prompt'], 'options': options, 'critical':bool(q.get('critical')), 'hint':q.get('hint') if row['level']<=2 else None})
    return questions


@app.get('/api/sessions/{sid}/interaction')
def interaction(sid: int, user=Depends(current_user)):
    row = owned_session(sid, user)
    if row['step'] < 4:
        raise HTTPException(409, '請先完成情境學習。')
    from .learning_resources import resources
    from .interaction_policy import policy
    difficulty=policy(row['level'],characters.selected(row)['kind'],row['payload']['trust'])
    return {'difficulty':difficulty,'resources':resources(row,case_for(row)),'questions': decision_questions(row), 'decisions': row['payload']['decisions'],
            'trust': row['payload']['trust'], 'scene_mode': row['payload']['adaptive_plan']['scene_mode'],
            'pairing':row['payload'].get('interaction_policy'),'minimum_turns':2,'variant':case_for(row).get('variant'),'safety_blocked':row['payload'].get('safety_blocked',False),
            'hint_budget':curriculum.hint_budget(row['level']),'hints_used':row['payload'].get('hints_used',0),'source': '案例約束標準病患；AI對話與決策分開記錄。'}


class DecisionBody(BaseModel):
    item_id: str
    option_id: str


@app.post('/api/sessions/{sid}/decision')
def decision(sid: int, body: DecisionBody, user=Depends(student)):
    with store.tx() as c:
        row = owned_session(sid, user)
        need_step(row, 4)
        q = next((q for q in case_for(row)['kdp'] if q['id'] == body.item_id), None)
        if not q or body.option_id not in [f'o{i}' for i in range(len(q['options']))]:
            raise HTTPException(400, '無效決策選項。')
        old = row['payload']['decisions'].get(q['id'])
        if old:
            if old['option_id'] != body.option_id:
                raise HTTPException(409, '本輪決策已保存；可在下一輪重新練習。')
            return old
        option = q['options'][int(body.option_id[1:])]
        record = {'option_id': body.option_id, 'score': option['score'], 'max_score': 2,
                  'feedback': option['feedback'], 'dimension': option['dimension'], 'critical':bool(q.get('critical')), 'at': time.time()}
        row['payload']['decisions'][q['id']] = record
        record.update(actor=characters.selected(row),case_hash=row['payload']['case_hash'])
        if q.get('critical') and option['score']==0:row['payload']['safety_blocked']=True
        row['payload']['trust'] = max(0, min(100, row['payload']['trust'] + {0:-10,1:2,2:8}.get(option['score'],0)))
        store.save(c, sid, row['payload'])
        store.event(c, user['id'], sid, 'decision', {'item_id': q['id'], **record})
    return record


class ChatBody(BaseModel):
    text: str = Field(min_length=1, max_length=2000)
    mode: str = 'ai'
    request_id: str = Field(min_length=8, max_length=80)


@app.post('/api/sessions/{sid}/hint')
def interaction_hint(sid:int,body:dict,user=Depends(student)):
    with store.tx() as c:
        row=owned_session(sid,user);need_step(row,4)
        budget=curriculum.hint_budget(row['level']);used=row['payload'].get('hints_used',0)
        if budget is not None and used>=budget:raise HTTPException(403,'本級可用提示次數已用完。')
        question=next((q for q in case_for(row)['kdp'] if q['id']==body.get('item_id')),None)
        if not question:raise HTTPException(400,'未知決策題。')
        row['payload']['hints_used']=used+1;store.save(c,sid,row['payload'])
        store.event(c,user['id'],sid,'hint_requested',{'item_id':question['id'],'level':row['level'],'ordinal':used+1})
        return {'hint':question.get('hint','請先區分已知資訊與需要確認的事項。'),'used':used+1}


class RetryBody(BaseModel):
    reflection:str=Field(min_length=10,max_length=4000)


@app.post('/api/sessions/{sid}/remediate')
def remediate(sid:int,body:RetryBody,user=Depends(student)):
    with conversation_locks[sid],store.tx() as c:
        row=owned_session(sid,user);need_step(row,4)
        if not row['payload'].get('safety_blocked'):raise HTTPException(409,'目前沒有待重作的安全錯誤。')
        payload=row['payload'];payload.setdefault('remediation_history',[]).append({'decisions':payload['decisions'],
            'reflection':body.reflection,'at':time.time(),'episode_start':payload.get('episode_start',0)})
        payload.update(decisions={},safety_blocked=False,episode_start=time.time(),trust=50,hints_used=0)
        store.save(c,sid,payload);store.event(c,user['id'],sid,'safety_remediation',{'reflection':body.reflection})
    return {'saved':True,'note':'原始決策與對話保留，請重新完成決策與至少兩回合互動。'}


@app.get('/api/sessions/{sid}/speech/{mid}')
def message_speech(sid:int,mid:int,user=Depends(current_user)):
    owned_session(sid,user)
    message=store.one("SELECT content,metadata FROM messages WHERE id=? AND session_id=? AND role='assistant'",(mid,sid))
    if not message:raise HTTPException(404,'找不到可朗讀的病患回覆。')
    path=RUNTIME/'speech'/f'{sid}-{mid}.wav'
    try:virtual_video.speech(message['content'],path,json.loads(message['metadata']).get('actor',{}).get('gender','female'))
    except Exception as e:raise HTTPException(503,str(e))
    return FileResponse(path,media_type='audio/wav')


@app.post('/api/sessions/{sid}/transcribe')
async def transcribe_turn(sid:int,request:Request,user=Depends(student)):
    return await decode_voice(sid,request,user)


async def decode_voice(sid,request,user,diagnostic=False):
    row=owned_session(sid,user,require_checkin=not diagnostic)
    if row['step']!=4 or row['status']!='active':raise HTTPException(409,'請在進行中的角色互動錄音。')
    if request.headers.get('content-type','').split(';')[0] not in ('audio/webm','audio/ogg','audio/wav','audio/mp4'):
        raise HTTPException(415,'請使用瀏覽器錄音格式。')
    recording=bytearray()
    async for chunk in request.stream():
        if len(recording)+len(chunk)>speech_input.MAX_BYTES:raise HTTPException(413,'錄音過大，請縮短至60秒。')
        recording.extend(chunk)
    try:result=await run_in_threadpool(speech_input.transcribe,bytes(recording))
    except BlockingIOError as e:raise HTTPException(429,str(e))
    except ValueError as e:raise HTTPException(400,str(e))
    except RuntimeError as e:raise HTTPException(503,str(e))
    with store.tx() as c:store.event(c,user['id'],sid,'diagnostic_speech_transcribed' if diagnostic else 'speech_transcribed',{'seconds':result['seconds'],'model':result['model'],'recording_retained':False,'input_source':'controlled-test-audio' if diagnostic else 'learner-audio'})
    return result


VOICE_TEST_LINES={1:'您好，請說明目前需要一起確認的資料。',2:'謝謝您的說明，還有哪些資訊需要再核對？'}
voice_diagnostics={}
voice_diagnostic_lock=threading.Lock()


@app.get('/api/sessions/{sid}/voice-diagnostic/input/{turn}')
def voice_diagnostic_input(sid:int,turn:int,user=Depends(student)):
    row=owned_session(sid,user,require_checkin=False);need_step(row,4)
    if turn not in VOICE_TEST_LINES:raise HTTPException(404,'未知測試音源。')
    path=RUNTIME/'voice-diagnostics'/f'input-{turn}.wav'
    virtual_video.speech(VOICE_TEST_LINES[turn],path,'female')
    return FileResponse(path,media_type='audio/wav')


@app.post('/api/sessions/{sid}/voice-diagnostic/transcribe')
async def voice_diagnostic_transcribe(sid:int,request:Request,user=Depends(student)):
    return await decode_voice(sid,request,user,diagnostic=True)


class VoiceDiagnosticBody(BaseModel):
    text:str=Field(min_length=1,max_length=2000)
    test_id:str=Field(pattern=r'^[a-f0-9]{32}$')


@app.post('/api/sessions/{sid}/voice-diagnostic/reply')
def voice_diagnostic_reply(sid:int,body:VoiceDiagnosticBody,user=Depends(student)):
    row=owned_session(sid,user,require_checkin=False);need_step(row,4)
    key=(user['id'],sid,body.test_id)
    with voice_diagnostic_lock:
        now=time.time()
        for old in list(voice_diagnostics):
            if now-voice_diagnostics[old]['created']>1800:del voice_diagnostics[old]
        if key not in voice_diagnostics and len(voice_diagnostics)>=32:raise HTTPException(429,'測試服務忙碌，請稍後再試。')
        test=voice_diagnostics.setdefault(key,{'created':now,'messages':[],'turn':0})
        if test.get('busy') or test['turn']>=2:raise HTTPException(409,'測試已完成或正在回覆。')
        test['busy']=True
    try:
        history=[*test['messages'],{'role':'user','content':body.text}]
        result,facts=patient_reply(case_for(row),row,history,body.text)
        if not result.ok:raise HTTPException(503,result.error)
        turn=test['turn']+1
        path=RUNTIME/'voice-diagnostics'/f"{user['id']}-{sid}-{body.test_id}-{turn}.wav"
        virtual_video.speech(result.text,path,characters.selected(row)['gender'])
        test['messages']=[*history,{'role':'assistant','content':result.text}];test['turn']=turn
        return {'text':result.text,'source':'ollama','model':result.model,'turn':turn,'diagnostic':True,'difficulty':facts.get('interaction_difficulty'),
                'audio_url':f'/api/sessions/{sid}/voice-diagnostic/output/{body.test_id}/{turn}'}
    finally:test['busy']=False


@app.get('/api/sessions/{sid}/voice-diagnostic/output/{test_id}/{turn}')
def voice_diagnostic_output(sid:int,test_id:str,turn:int,user=Depends(student)):
    owned_session(sid,user,require_checkin=False)
    test=voice_diagnostics.get((user['id'],sid,test_id))
    if not test or turn not in (1,2) or turn>test['turn']:raise HTTPException(404,'找不到此測試語音。')
    return FileResponse(RUNTIME/'voice-diagnostics'/f"{user['id']}-{sid}-{test_id}-{turn}.wav",media_type='audio/wav')


@app.post('/api/sessions/{sid}/chat')
def chat(sid: int, body: ChatBody, user=Depends(student)):
    if body.mode not in ('ai', 'scripted','peer'):
        raise HTTPException(400, '未知對話模式。')
    with conversation_locks[sid]:
        row = owned_session(sid, user)
        need_step(row, 4)
        if body.mode=='peer' and row['level']!=5:raise HTTPException(403,'虛擬學員指導模式限 Level 5。')
        case = case_for(row)
        actor=characters.selected(row)
        messages = store.all('SELECT * FROM messages WHERE session_id=? ORDER BY id', (sid,))
        duplicate = [m for m in messages if json.loads(m['metadata']).get('request_id') == body.request_id]
        if duplicate:
            return {'messages': duplicate, 'duplicate': True}
        with store.tx() as c:
            c.execute('INSERT INTO messages(session_id,role,content,source,metadata,created) VALUES (?,?,?,?,?,?)',
                      (sid, 'user', body.text.strip(), 'learner', encode({'request_id':body.request_id,'mode':body.mode,'actor':actor}), time.time()))
        messages = store.all('SELECT * FROM messages WHERE session_id=? ORDER BY id', (sid,))
        if body.mode in ('ai','peer'):
            status = llm.check()
            if status.ready:
                if body.mode=='peer':result,facts=peer_reply(case,[m for m in messages if json.loads(m['metadata']).get('mode')=='peer' or json.loads(m['metadata']).get('request_id')==body.request_id])
                else:result, facts = patient_reply(case, row, [m for m in messages if json.loads(m['metadata']).get('mode')!='peer' and json.loads(m['metadata']).get('actor',{}).get('id',characters.default_actor(row))==actor['id']], body.text)
            else:
                result, facts = None, {}
            if not result or not result.ok:
                note = result.error if result else status.error
                with store.tx() as c:
                    store.event(c, user['id'], sid, 'ai_unavailable', {'request_id': body.request_id, 'error': note})
                    c.execute('INSERT INTO messages(session_id,role,content,source,metadata,created) VALUES (?,?,?,?,?,?)',
                              (sid, 'system', 'AI 未完成回覆：'+note, 'error', encode({'request_id':body.request_id}), time.time()))
                return {'ok': False, 'error': note, 'note': '作答已保存，可選擇明示的劇本演練；未產生虛構AI回覆。'}
            text, source, metadata = result.text, 'ollama', {'model': result.model, 'case_hash': row['payload']['case_hash'],
                'prompt_version':'peer-1' if body.mode=='peer' else 'self-difficulty-5.3.1','mode':body.mode,
                'interaction_difficulty':facts.get('interaction_difficulty'),
                'retrieval_version':facts.get('retrieval_version','case-peer-1'),'evidence':facts.get('retrieved_evidence',[])}
        else:
            # Explicit scripted patient exercise, not a false AI fallback.
            lines = [case.get('patient_behavior') or '您可以先說明接下來要問什麼嗎？', '我擔心做不到，能不能先一起討論我的疑慮？', '請再用簡單的話說明下一步。']
            if actor['kind'] in ('clinician','support'):
                lines=[f"我是{actor['name']}。目前只能使用本輪教案已提供的資料，缺漏項目需要進一步核對。",
                       '請說明您已確認的資料、目前疑慮，以及需要本職類協助的部分。',
                       '這部分資料尚未提供，我們先記錄並和負責同仁核對。']
            if row['level']==1:
                lines=['您好，沒關係，我願意一起確認；您想先了解哪一部分？','可以，我們先釐清已知資料與需要協助的地方。','謝謝您先確認，我願意繼續說明。']
            elif row['level']==5:
                lines=(['這部分您應該先確認吧？請先說明依據與具體協助需求。','您是在挑戰我的專業判斷嗎？請先確認彼此的職責與資料依據。','我們先把已確認的資料與仍有疑慮的部分說清楚，再討論下一步。']
                       if actor['kind'] in ('clinician','support') else ['你真的了解我的情況嗎？請先說明為什麼要這樣安排。','不要只叫我照做，我還沒有理解這樣做的理由。','謝謝您願意聽我的顧慮，請先讓我知道有哪些選擇。'])
            turn = sum(m['role'] == 'user' for m in messages)
            text, source, metadata = lines[(turn-1) % len(lines)], 'scripted', {'script_version':'source-patient-2','source_file':case.get('source_file')}
        metadata['request_id'] = body.request_id
        metadata['actor']=actor
        metadata['mode']=body.mode
        metadata['role_kind']='peer' if body.mode=='peer' else actor['kind']
        with store.tx() as c:
            message_id=c.execute('INSERT INTO messages(session_id,role,content,source,metadata,created) VALUES (?,?,?,?,?,?)',
                      (sid, 'assistant', text, source, encode(metadata), time.time())).lastrowid
            store.event(c, user['id'], sid, 'patient_reply', {'source': source, **metadata})
        if sid in voice_bridge.rooms:
            def speak_to_room():
                try:
                    path=RUNTIME/'speech'/f'{sid}-{message_id}.wav'
                    virtual_video.speech(text,path,actor['gender'])
                    future=voice_bridge.publish(sid,path)
                    if future:future.result(timeout=120)
                    with store.tx() as c:store.event(c,user['id'],sid,'voice_published',{'message_id':message_id,'actor_id':actor['id'],'actor_name':actor['name'],'transport':'LiveKit'})
                except Exception as e:
                    with store.tx() as c:store.event(c,user['id'],sid,'voice_error',{'message_id':message_id,'error':str(e)[:300]})
            threading.Thread(target=speak_to_room,daemon=True).start()
        return {'ok': True, 'text':text,'source':source,'metadata':metadata,'audio_url':f'/api/sessions/{sid}/speech/{message_id}'}


class SceneBody(BaseModel):
    action: str


@app.post('/api/sessions/{sid}/scene')
def scene_event(sid: int, body: SceneBody, user=Depends(student)):
    allowed = {'identify', 'report', 'safety', 'handoff'}
    if body.action not in allowed:
        raise HTTPException(400, '未知場景動作。')
    with store.tx() as c:
        row = owned_session(sid, user)
        need_step(row, 4)
        events = row['payload']['scene_events']
        if len(events) >= 200:
            raise HTTPException(400, '本輪場景紀錄已達上限。')
        events.append({'action': body.action, 'at': time.time(), 'evidence_type': 'interface_action_not_skill_certification'})
        store.save(c, sid, row['payload'])
        store.event(c, user['id'], sid, 'scene_action', {'action': body.action})
    return {'saved': True}


class SBARBody(BaseModel):
    S: str = Field(min_length=5, max_length=2000)
    B: str = Field(min_length=5, max_length=2000)
    A: str = Field(min_length=5, max_length=2000)
    R: str = Field(min_length=5, max_length=2000)
    coaching: str = Field(default='',max_length=4000)


@app.post('/api/sessions/{sid}/handoff')
def handoff(sid: int, body: SBARBody, user=Depends(student)):
    with conversation_locks[sid], store.tx() as c:
        row = owned_session(sid, user)
        need_step(row, 4)
        if row['payload'].get('safety_blocked'):raise HTTPException(409,'本輪有安全關鍵錯誤，請先完成補強重作。')
        if body.coaching.strip() and len(body.coaching.strip())<10:raise HTTPException(400,'選填同儕回饋時，請提供至少10字的具體紀錄。')
        if len(row['payload']['decisions']) != len(case_for(row)['kdp']):
            raise HTTPException(409, '請完成全部決策點。')
        evidence = c.execute("SELECT metadata FROM messages WHERE session_id=? AND role='assistant' AND source IN ('ollama','scripted','legacy_v3') AND created>=? AND COALESCE(json_extract(metadata,'$.mode'),'')!='peer'", (sid,row['payload'].get('episode_start',0))).fetchall()
        policy=row['payload'].get('interaction_policy')
        if policy:
            counts={target:0 for target in policy['targets']}
            for message in evidence:
                actor=json.loads(message['metadata']).get('actor',{})
                key='patient' if actor.get('kind') in ('patient','caregiver') else actor.get('profession')
                if key in counts:counts[key]+=1
            if any(n < policy['turns_per_target'] for n in counts.values()):
                raise HTTPException(409,'請完成指定互動對象各至少'+str(policy['turns_per_target'])+'回合：'+policy['label'])
        elif sum(json.loads(m['metadata']).get('actor',{}).get('kind','patient') in ('patient','caregiver') for m in evidence)<2:
            raise HTTPException(409, '請先完成至少兩回合病患對話。')
        plan = row['payload']['adaptive_plan']
        if plan['tier'] >= 2 and not row['payload']['scene_events']:
            raise HTTPException(409, '請完成至少一項情境操作，可使用人物下方的操作按鈕。')
        row['payload']['sbar'] = {'answers': body.model_dump(), 'status': 'pending_teacher', 'rubric': 'SBAR完整性、案例一致性、專業界線及追蹤可行性'}
        pool = list(case_for(row)['quiz'])
        secrets.SystemRandom().shuffle(pool)
        for q in pool:
            secrets.SystemRandom().shuffle(q['options'])
        row['payload']['quiz_snapshot'] = pool
        store.save(c, sid, row['payload'], step=5)
    return {'step': 5}


@app.get('/api/sessions/{sid}/quiz')
def quiz(sid: int, user=Depends(student)):
    row = owned_session(sid, user)
    if row['step'] < 5:
        raise HTTPException(409, '請先完成互動任務與 SBAR。')
    return [{k:v for k,v in q.items() if k not in ('answer', 'explain')} for q in row['payload']['quiz_snapshot']]


class QuizBody(BaseModel):
    answers: dict[str, str]


@app.post('/api/sessions/{sid}/finish')
def finish(sid: int, body: QuizBody, user=Depends(student)):
    with store.tx() as c:
        row = owned_session(sid, user)
        if row['status'] == 'completed':
            if row['payload'].get('quiz_answers') != body.answers:
                raise HTTPException(409, '已完成測驗不可覆寫。')
            return row['payload']['result']
        need_step(row, 5)
        questions = row['payload']['quiz_snapshot']
        if set(body.answers) != {q['id'] for q in questions}:
            raise HTTPException(400, '請完成全部測驗題。')
        records=[]
        for q in questions:
            given=body.answers[q['id']]
            if given not in q['options']:
                raise HTTPException(400, '無效測驗選項。')
            records.append({'id':q['id'],'given':given,'answer':q['answer'],
                            'correct':given==q['answer'],'explain':q.get('explain',''),'dimension':q.get('dimension','')})
        kdp = list(row['payload']['decisions'].values())
        kdp_score = sum(q['score'] for q in kdp)/sum(q['max_score'] for q in kdp)*100
        quiz_score = sum(q['correct'] for q in records)/len(records)*100
        overall = round(kdp_score*.6+quiz_score*.4,1)
        result = {'decision_score':round(kdp_score,1),'quiz_score':round(quiz_score,1),'objective_score':overall,
                  'formula':'決策點 60% + 後測 40%（試辦規則 v1）','teacher_status':'pending',
                  'communication_score':None, 'sbar_score':None,
                  'level_suggestion':min(5,row['level']+1) if overall>=80 else row['level'],
                  'note':'客觀練習分不含自評、未覆核對話及SBAR；達標練習可提升學習Level，正式能力核定由教師另行評量。'}
        row['payload'].update(result=result,quiz_result=records,quiz_answers=body.answers)
        store.save(c,sid,row['payload'],step=6,status='completed')
        result['learning_progress']=progression.advance(store,c,user['id'],row['profession'],row['topic'])
        result['level_suggestion']=row['level']
        store.save(c,sid,row['payload'],step=6,status='completed')
        store.event(c,user['id'],sid,'training_completed',result)
    return result


@app.get('/api/history')
def history(user=Depends(student)):
    rows=store.all('SELECT id,profession,topic,level,step,status,created,updated FROM sessions WHERE user_id=? ORDER BY id DESC',(user['id'],))
    return {'access_grant':progression.access(store,user['id']),'sessions':rows,'progress':store.all('SELECT * FROM progress WHERE user_id=?',(user['id'],)),
            'learning_progress':store.all('SELECT * FROM learning_progress WHERE user_id=?',(user['id'],)),
            'assessments':store.all('SELECT id,profession,topic,level,completed,created FROM attempts WHERE user_id=? ORDER BY id DESC',(user['id'],))}


@app.get('/api/teacher/overview')
def overview(user=Depends(teacher)):
    rows=store.all('''SELECT s.*,u.display_name,u.username FROM sessions s JOIN users u ON u.id=s.user_id
                      ORDER BY s.updated DESC LIMIT 500''')
    for r in rows:
        d=json.loads(r.pop('data'))
        r['result']=d.get('result')
        r['case_title']=(d.get('case_snapshot') or {}).get('title')
        r['turns']=store.one("SELECT COUNT(*) n FROM messages WHERE session_id=? AND role='user'",(r['id'],))['n']
        r['review']=store.one('SELECT * FROM reviews WHERE session_id=? ORDER BY id DESC LIMIT 1',(r['id'],))
    assessments = store.all('''SELECT a.id,a.profession,a.topic,a.level,a.completed,a.created,a.scores,
                     u.username,u.display_name FROM attempts a JOIN users u ON u.id=a.user_id ORDER BY a.id DESC LIMIT 500''')
    for a in assessments:
        a['scores'] = json.loads(a['scores'] or '{}')
    return {'sessions':rows,'assessments':assessments,'students':store.all("SELECT id,username,display_name FROM users WHERE role='student'"),
            'note':'本機試辦教師可監看本系統學員；正式多班級部署需設定教師指派範圍。'}


@app.get('/api/teacher/sessions/{sid}')
def teacher_detail(sid:int,user=Depends(teacher)):
    result=get_session(sid,user)
    row=owned_session(sid,user)
    attempts=store.all('''SELECT * FROM attempts WHERE user_id=? AND profession=? AND topic=? ORDER BY id DESC''',
                        (row['user_id'],row['profession'],row['topic']))
    for a in attempts:
        for k in ['snapshot','answers','scores']: a[k]=json.loads(a[k] or '{}')
    result['assessments']=attempts
    formal=store.one('SELECT approved_level FROM progress WHERE user_id=? AND profession=? AND topic=?',(row['user_id'],row['profession'],row['topic']))
    result['approved_level']=formal['approved_level'] if formal else 1
    result['events']=store.all('SELECT * FROM events WHERE session_id=? ORDER BY id',(sid,))
    return result


class ReviewBody(BaseModel):
    decision: str
    score: float = Field(ge=0,le=100)
    level: int = Field(ge=1,le=5)
    safety_pass: bool
    note: str = Field(min_length=10,max_length=4000)
    expected_review_id: int = 0


@app.post('/api/teacher/sessions/{sid}/review')
def review(sid:int,body:ReviewBody,user=Depends(teacher)):
    if body.decision not in ('approve','revise'):
        raise HTTPException(400,'請選擇核定或補作。')
    with store.tx() as c:
        row=owned_session(sid,user)
        if row['status']!='completed': raise HTTPException(409,'訓練完成後才能核定。')
        latest=store.one('SELECT id FROM reviews WHERE session_id=? ORDER BY id DESC LIMIT 1',(sid,))
        if (latest['id'] if latest else 0)!=body.expected_review_id:
            raise HTTPException(409,'已有新的教師覆核，請重新載入。')
        formal=store.one('SELECT approved_level FROM progress WHERE user_id=? AND profession=? AND topic=?',(row['user_id'],row['profession'],row['topic']))
        approved=formal['approved_level'] if formal else 1
        if body.level<approved or body.level>min(5,approved+1):
            raise HTTPException(400,'本次可維持原等級或逐級升一級。')
        if body.level>approved and (not body.safety_pass or body.decision!='approve'):
            raise HTTPException(400,'安全未通過或需補作時不可升級。')
        rid=c.execute('INSERT INTO reviews(session_id,teacher_id,decision,score,level,note,created) VALUES (?,?,?,?,?,?,?)',
                      (sid,user['id'],body.decision,body.score,body.level,body.note,time.time())).lastrowid
        if body.decision=='approve':
            c.execute('UPDATE progress SET approved_level=MAX(approved_level,?),updated=? WHERE user_id=? AND profession=? AND topic=?',
                      (body.level,time.time(),row['user_id'],row['profession'],row['topic']))
        store.event(c,user['id'],sid,'teacher_review',{'review_id':rid,**body.model_dump()})
    return {'review_id':rid,'saved':True}


@app.get('/api/sessions/{sid}/export')
def export_session(sid:int,user=Depends(current_user)):
    data=get_session(sid,user)
    row=owned_session(sid,user)
    attempts=store.all('SELECT id,snapshot,answers,scores,created,completed FROM attempts WHERE user_id=? AND profession=? AND topic=? AND completed IS NOT NULL',
                       (row['user_id'],row['profession'],row['topic']))
    for a in attempts:
        for k in ('snapshot','answers','scores'): a[k]=json.loads(a[k] or '{}')
        if row['status']!='completed' and user['role']!='teacher':
            a['snapshot']=public_snapshot(a['snapshot'])
    events=store.all('SELECT * FROM events WHERE session_id=? ORDER BY id',(sid,))
    return Response(encode({'schema_version':1,'app_version':VERSION,'exported_at':time.time(),
                            'record':data,'assessments':attempts,'events':events,
                            'restore_note':'單筆證據匯出；全系統遷移請使用 tools/backup_bundle.py'}),
                    media_type='application/json',headers={'Content-Disposition':f'attachment; filename="training-{sid}.json"'})


from .learning_resources import install_routes
install_routes(app, owned_session, current_user, lambda:store)


@app.get('/api/services')
def service_status(user=Depends(current_user)):
    return {'ollama':llm.check().to_dict(),'vrm_available':all((ROOT/'data/characters'/a['model_file']).is_file() for a in characters.ACTORS.values()),
            'realistic_available':all((ROOT/'data/characters'/a.get('realistic_model_file','missing')).is_file() for a in characters.ACTORS.values()),
            'photoreal_available':all((ROOT/'data/characters'/a.get('atlas_file','missing')).is_file() for a in characters.ACTORS.values()),
            'characters':len(characters.ACTORS),'character_version':characters.VERSION,
            'livekit_configured':voice_bridge.ready(),
            'livekit_agent_configured':False,'livekit_audio_bridge':True,'speech_input':speech_input.status(),'voice_transport':'authenticated-http-audio',
            'h5p_available':(ROOT/'frontend/vendor/h5p/main.bundle.js').is_file(),
            'knowledge_mode':'本地案例快照與來源約束檢索；尚未建置醫療知識圖譜',
            'video_mode':'three.js 診間場景／擬真人像與語音驅動表情；四部VR360教材，待教師審核'}


@app.get('/api/characters')
def character_catalog(user=Depends(current_user)):return characters.catalog()


@app.get('/api/characters/{aid}/{asset}')
def character_asset(aid:str,asset:str,user=Depends(current_user)):
    try:a=characters.get_actor(aid)
    except ValueError as e:raise HTTPException(404,str(e))
    field={'card':'card_file','model':'model_file','atlas':'atlas_file','rigged':'realistic_model_file'}.get(asset)
    if not field or not a.get(field):raise HTTPException(404,'未知角色資源。')
    return FileResponse(ROOT/'data/characters'/a[field],media_type='model/gltf-binary' if asset in ('model','rigged') else 'image/png')


@app.get('/api/sessions/{sid}/actors')
def session_actors(sid:int,user=Depends(current_user)):
    row=owned_session(sid,user);case_for(row)
    return {'lecturer':characters.selected(row,'lecturer'),'interaction':characters.selected(row),'catalog':characters.catalog(),'pairing':row['payload'].get('interaction_policy'),
            'note':'角色卡提供造型與風格；病人姓名、病史與數值以本輪教案為準。團隊角色不計入病患對話最低回合。'}


class ActorBody(BaseModel):
    purpose:str
    actor_id:str


@app.post('/api/sessions/{sid}/actors')
def select_actor(sid:int,body:ActorBody,user=Depends(student)):
    if body.purpose not in ('lecturer','interaction'):raise HTTPException(400,'未知角色用途。')
    try:actor=characters.get_actor(body.actor_id)
    except ValueError as e:raise HTTPException(400,str(e))
    if body.purpose=='lecturer' and actor['kind'] not in ('clinician','support'):raise HTTPException(400,'講師請選擇專業或支援角色。')
    with conversation_locks[sid],store.tx() as c:
        row=owned_session(sid,user);need_step(row,3 if body.purpose=='lecturer' else 4)
        if body.purpose=='interaction' and not characters.allowed(row,actor):raise HTTPException(400,'此角色不符合本職種互動配對。')
        if row['payload'].get('video_job',{}).get('status')=='running':raise HTTPException(409,'影片生成中，請完成後再換角。')
        row['payload'].setdefault('actors',{})[body.purpose]=actor
        store.save(c,sid,row['payload'])
        store.event(c,user['id'],sid,'actor_selected',{'purpose':body.purpose,'actor':actor,'case_hash':row['payload']['case_hash']})
    return {'saved':True,'actor':actor}


@app.get('/api/avatar.vrm')
def avatar(user=Depends(current_user)):
    path=ROOT/'data/avatar.vrm'
    if not path.is_file(): raise HTTPException(404,'尚未安裝具有使用授權的 VRM 模型。')
    return FileResponse(path,media_type='application/octet-stream')


@app.get('/api/sessions/{sid}/h5p/h5p.json')
def h5p_manifest(sid:int,user=Depends(current_user)):
    row=owned_session(sid,user)
    if row['step']<4:raise HTTPException(409,'請先進入互動階段。')
    return h5p_content.manifest()


@app.get('/api/sessions/{sid}/h5p/content/content.json')
def h5p_activity(sid:int,user=Depends(current_user)):
    row=owned_session(sid,user)
    if row['step']<4:raise HTTPException(409,'請先進入互動階段。')
    return h5p_content.content(row)[0]


@app.get('/api/sessions/{sid}/h5p/state')
def h5p_state(sid:int,user=Depends(current_user)):
    row=owned_session(sid,user)
    if row['step']<4:raise HTTPException(409,'請先進入互動階段。')
    _,version=h5p_content.content(row)
    return {'content_version':version,'state':row['payload'].get('h5p_states',{}).get(version,{}),
            'readonly':user['role']!='student' or row['step']!=4 or row['status']!='active'}


class H5PEvidenceBody(BaseModel):
    event_id:str=Field(min_length=8,max_length=80)
    content_version:str=Field(min_length=64,max_length=64)
    verb:str=Field(min_length=1,max_length=40)
    result:dict=Field(default_factory=dict)
    state:dict=Field(default_factory=dict)


@app.post('/api/sessions/{sid}/h5p/evidence')
def h5p_evidence(sid:int,body:H5PEvidenceBody,user=Depends(student)):
    if len(encode(body.model_dump()))>20000:raise HTTPException(413,'H5P事件過大。')
    with store.tx() as c:
        row=owned_session(sid,user);need_step(row,4)
        _,version=h5p_content.content(row)
        if body.content_version!=version:raise HTTPException(409,'角色或教案已更換，請重新載入練習。')
        prior=store.all("SELECT data FROM events WHERE session_id=? AND kind='h5p_practice'",(sid,))
        if any(json.loads(p['data'])['event_id']==body.event_id for p in prior):return {'saved':True,'duplicate':True}
        if len(prior)>=500:raise HTTPException(409,'本輪練習事件已達上限。')
        event={**body.model_dump(),'actor':characters.selected(row),'case_hash':row['payload']['case_hash'],
               'evidence_type':'client_reported_practice_not_formal_score','identity_source':'authenticated_session'}
        store.event(c,user['id'],sid,'h5p_practice',event)
        if isinstance(body.state.get('answers'),list) and all(type(x) is int and 0<=x<=2 for x in body.state['answers']):
            row['payload'].setdefault('h5p_states',{})[version]={'answers':body.state['answers'][:3]}
        store.save(c,sid,row['payload'])
    return {'saved':True,'formal_score_changed':False}


@app.post('/api/sessions/{sid}/livekit')
def connect_livekit(sid:int,user=Depends(current_user)):
    row=owned_session(sid,user)
    if row['step']<4: raise HTTPException(409,'請先進入互動階段。')
    try:
        if not voice_bridge.ready():raise ValueError('LiveKit 未啟動；請執行 tools/start_livekit.py。')
        voice_bridge.connect(sid)
        # The browser submits confirmed text through the authenticated chat API.
        # Only the backend audio bridge may publish audio to this room.
        token=livekit_token(f"{user['role']}-{user['id']}-{secrets.token_hex(3)}",voice_bridge.room_name(sid),True)
    except Exception as e: raise HTTPException(503,str(e))
    with store.tx() as c:store.event(c,user['id'],sid,'voice_join',{'role':user['role'],'room':voice_bridge.room_name(sid)})
    return {'token':token,'url':voice_bridge.settings()['LIVEKIT_URL'],'room':voice_bridge.room_name(sid),
            'observer':user['role']=='teacher','agent_ready':False,'audio_bridge':True,
            'note':'病患已保存回覆透過 LiveKit 播放；語音輸入由瀏覽器辨識，確認文字後送出。教師可唯讀收聽。'}


@app.get('/')
@app.get('/login')
def home(request: Request):
    # Opening/reloading the platform is an explicit fresh sign-in boundary.
    revoke_browser_login(request)
    response=FileResponse(ROOT/'frontend/index.html',headers={'Cache-Control':'no-store'})
    response.delete_cookie(COOKIE)
    return response


@app.get('/health')
def health():return {'status':'ok','product':'clinical-tutor','version':VERSION,'login_entry':'/login'}

app.mount('/static',StaticFiles(directory=ROOT/'frontend'),name='static')
