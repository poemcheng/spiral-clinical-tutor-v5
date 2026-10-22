"""Portable configuration for reused v3 content and AI adapters; no dependency on v3."""
import os
from pathlib import Path
from ..config import ROOT, RUNTIME

APP_VERSION = '4.0.0'
IS_FROZEN = False
RUNTIME_ROOT = RUNTIME
BUNDLE_ROOT = ROOT
BUNDLED_DATA_DIR = ROOT / 'data'
DATA_DIR = RUNTIME
LESSON_CASES_DIR = ROOT / 'data/lesson_cases'
SELF_ASSESSMENTS_DIR = ROOT / 'data/self_assessments'
OVERLAYS_DIR = ROOT / 'data/overlays'
VIDEO_LESSONS_DIR = ROOT / 'data/video_lessons'
VIDEO_LIBRARY_DIR = Path(os.getenv('VIDEO_LIBRARY_DIR', str(ROOT.parent / 'AI醫學教案/AI醫學教案')))
FRONTEND_DIR = ROOT / 'frontend'
DB_PATH = RUNTIME / 'clinical_tutor.sqlite3'
OLLAMA_BASE_URL = os.getenv('OLLAMA_URL', 'http://127.0.0.1:11434').rstrip('/')
OLLAMA_MODEL = os.getenv('OLLAMA_MODEL', 'gemma4:12b')
OLLAMA_CHAT_TOKENS = 260
OLLAMA_KEEP_ALIVE = '10m'
OLLAMA_TIMEOUT = int(os.getenv('OLLAMA_TIMEOUT', '120'))
SD_WEBUI_URL = os.getenv('SD_WEBUI_URL', 'http://127.0.0.1:7860')
SD_WEBUI_DIR = os.getenv('SD_WEBUI_DIR', '')
SD_AUTO_START = False
SD_START_TIMEOUT = 120
HOST = '127.0.0.1'
PORT = 8700
AUTO_OPEN_BROWSER = False
TEACHER_ACCESS_CODE = ''
