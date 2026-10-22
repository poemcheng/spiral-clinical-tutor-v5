"""SQLite persistence. All state transitions run under one transaction and lock."""
import contextlib
import hashlib
import hmac
import json
import secrets
import sqlite3
import threading
import time
import os
from .config import DB_PATH


def encode(value):
    return json.dumps(value, ensure_ascii=False)


def password_hash(password, salt=None):
    salt = salt or secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac('sha256', password.encode(), bytes.fromhex(salt), 310000).hex()
    return f'pbkdf2_sha256$310000${salt}${digest}'


def verify_password(password, stored):
    try:
        return hmac.compare_digest(password_hash(password, stored.split('$')[2]), stored)
    except (ValueError, IndexError):
        return False


class Store:
    def __init__(self, path=DB_PATH):
        self.path = str(path)
        self.lock = threading.RLock()
        self.conn = sqlite3.connect(path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute('PRAGMA foreign_keys=ON')
        self.conn.execute('PRAGMA journal_mode=WAL')
        self.conn.executescript('''
        CREATE TABLE IF NOT EXISTS users (
          id INTEGER PRIMARY KEY, username TEXT NOT NULL UNIQUE, password_hash TEXT NOT NULL,
          display_name TEXT NOT NULL, role TEXT NOT NULL CHECK(role IN ('student','teacher','admin')),
          enabled INTEGER NOT NULL DEFAULT 1);
        CREATE TABLE IF NOT EXISTS logins (
          id INTEGER PRIMARY KEY, token_hash TEXT UNIQUE NOT NULL,
          user_id INTEGER NOT NULL REFERENCES users(id), expires REAL NOT NULL);
        CREATE TABLE IF NOT EXISTS progress (
          user_id INTEGER NOT NULL REFERENCES users(id), profession TEXT NOT NULL, topic TEXT NOT NULL,
          approved_level INTEGER NOT NULL DEFAULT 1, updated REAL NOT NULL,
          PRIMARY KEY(user_id,profession,topic));
        CREATE TABLE IF NOT EXISTS learning_progress (
          user_id INTEGER NOT NULL REFERENCES users(id),profession TEXT NOT NULL,topic TEXT NOT NULL,
          level INTEGER NOT NULL CHECK(level BETWEEN 1 AND 5),data TEXT NOT NULL DEFAULT '{}',updated REAL NOT NULL,
          PRIMARY KEY(user_id,profession,topic));
        CREATE TABLE IF NOT EXISTS learning_access (
          user_id INTEGER PRIMARY KEY REFERENCES users(id), level INTEGER NOT NULL CHECK(level BETWEEN 1 AND 5),
          all_paths INTEGER NOT NULL DEFAULT 0, note TEXT NOT NULL, created REAL NOT NULL);
        CREATE TABLE IF NOT EXISTS attempts (
          id INTEGER PRIMARY KEY, login_id INTEGER NOT NULL REFERENCES logins(id),
          user_id INTEGER NOT NULL REFERENCES users(id), profession TEXT NOT NULL, topic TEXT NOT NULL,
          level INTEGER NOT NULL, snapshot TEXT NOT NULL, answers TEXT, scores TEXT,
          completed REAL, created REAL NOT NULL);
        CREATE TABLE IF NOT EXISTS sessions (
          id INTEGER PRIMARY KEY, user_id INTEGER NOT NULL REFERENCES users(id),
          profession TEXT NOT NULL, topic TEXT NOT NULL, level INTEGER NOT NULL,
          step INTEGER NOT NULL DEFAULT 2, status TEXT NOT NULL DEFAULT 'active',
          data TEXT NOT NULL DEFAULT '{}', created REAL NOT NULL, updated REAL NOT NULL);
        CREATE UNIQUE INDEX IF NOT EXISTS one_active_training
          ON sessions(user_id,profession,topic) WHERE status='active';
        CREATE TABLE IF NOT EXISTS messages (
          id INTEGER PRIMARY KEY, session_id INTEGER NOT NULL REFERENCES sessions(id),
          role TEXT NOT NULL, content TEXT NOT NULL, source TEXT NOT NULL,
          metadata TEXT NOT NULL DEFAULT '{}', created REAL NOT NULL);
        CREATE TABLE IF NOT EXISTS reviews (
          id INTEGER PRIMARY KEY, session_id INTEGER NOT NULL REFERENCES sessions(id),
          teacher_id INTEGER NOT NULL REFERENCES users(id), decision TEXT NOT NULL,
          score REAL NOT NULL, level INTEGER NOT NULL, note TEXT NOT NULL, created REAL NOT NULL);
        CREATE TABLE IF NOT EXISTS events (
          id INTEGER PRIMARY KEY, user_id INTEGER REFERENCES users(id),
          session_id INTEGER REFERENCES sessions(id), kind TEXT NOT NULL, data TEXT NOT NULL, created REAL NOT NULL);
        CREATE TABLE IF NOT EXISTS schema_version (version INTEGER PRIMARY KEY);
        INSERT OR IGNORE INTO schema_version VALUES (1);
        ''')
        self.conn.commit()
        self._migrate_admin_role()

    def _migrate_admin_role(self):
        """Rebuild only users; retain IDs and every referencing learning record."""
        schema = self.conn.execute("SELECT sql FROM sqlite_master WHERE name='users'").fetchone()[0]
        if "'admin'" not in schema:
            self.conn.execute('PRAGMA foreign_keys=OFF')
            try:
                self.conn.execute('BEGIN IMMEDIATE')
                self.conn.execute('''CREATE TABLE users_admin_migration (
                    id INTEGER PRIMARY KEY, username TEXT NOT NULL UNIQUE, password_hash TEXT NOT NULL,
                    display_name TEXT NOT NULL, role TEXT NOT NULL CHECK(role IN ('student','teacher','admin')),
                    enabled INTEGER NOT NULL DEFAULT 1)''')
                self.conn.execute('INSERT INTO users_admin_migration SELECT * FROM users')
                self.conn.execute('DROP TABLE users')
                self.conn.execute('ALTER TABLE users_admin_migration RENAME TO users')
                if self.conn.execute('PRAGMA foreign_key_check').fetchall():
                    raise RuntimeError('帳號結構遷移檢查失敗，已還原。')
                self.conn.commit()
            except Exception:
                self.conn.rollback()
                raise
            finally:
                self.conn.execute('PRAGMA foreign_keys=ON')
        self.conn.execute('INSERT OR IGNORE INTO schema_version VALUES (2)')
        self.conn.commit()

    @contextlib.contextmanager
    def tx(self):
        with self.lock:
            try:
                yield self.conn
                self.conn.commit()
            except Exception:
                self.conn.rollback()
                raise

    def one(self, sql, args=()):
        with self.lock:
            r = self.conn.execute(sql, args).fetchone()
            return dict(r) if r else None

    def all(self, sql, args=()):
        with self.lock:
            return [dict(r) for r in self.conn.execute(sql, args).fetchall()]

    def event(self, c, user_id, sid, kind, data):
        c.execute('INSERT INTO events(user_id,session_id,kind,data,created) VALUES (?,?,?,?,?)',
                  (user_id, sid, kind, encode(data), time.time()))

    def save(self, c, sid, data, **fields):
        permitted = {'step', 'status'}
        assert not set(fields) - permitted
        sets = ['data=?', 'updated=?'] + [f'{k}=?' for k in fields]
        c.execute(f"UPDATE sessions SET {','.join(sets)} WHERE id=?",
                  (encode(data), time.time(), *fields.values(), sid))

    def create_user(self, username, password, role, display_name=''):
        minimum = 4 if role == 'admin' else 10
        if role not in ('student', 'teacher', 'admin') or len(password) < minimum or not username.strip():
            raise ValueError('帳號不可空白；學員及教師密碼至少 10 字元。')
        with self.tx() as c:
            return c.execute('INSERT INTO users(username,password_hash,display_name,role) VALUES (?,?,?,?)',
                             (username.strip(), password_hash(password), display_name or username, role)).lastrowid

    def backup(self, destination):
        with self.lock, contextlib.closing(sqlite3.connect(destination)) as target:
            self.conn.backup(target)

    def bootstrap_admin(self):
        """User-requested first-install administrator. Never reset an existing password."""
        existing = self.one('SELECT id,role FROM users WHERE username=?', ('user',))
        if existing:
            if existing['role'] != 'admin':
                raise ValueError('user 已存在且不是管理員，請先處理帳號衝突。')
            return existing['id']
        password=os.getenv('BOOTSTRAP_ADMIN_PASSWORD','1234')
        if os.getenv('DEPLOYMENT_MODE')=='public' and (len(password)<12 or password=='1234'):
            raise ValueError('公開部署請設定至少12字元的 BOOTSTRAP_ADMIN_PASSWORD。')
        return self.create_user('user', password, 'admin', '系統管理員')
