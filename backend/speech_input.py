"""Local, short-turn transcription. Recordings are deleted after decoding."""
import io
import os
import threading
from pathlib import Path
from importlib.util import find_spec
from .config import RUNTIME

MODEL_NAME = 'Systran/faster-whisper-base'
MAX_BYTES = 8 * 1024 * 1024
MAX_SECONDS = 60
_model = None
_lock = threading.Lock()

def model_path():
    return Path(os.getenv('WHISPER_MODEL_PATH', str(RUNTIME/'models/faster-whisper-base')))

def status():
    return {'ready':bool(find_spec('faster_whisper') and all((model_path()/f).is_file() for f in ('model.bin','config.json','tokenizer.json','vocabulary.txt'))),
            'model':MODEL_NAME,'local':True,'max_seconds':MAX_SECONDS}

def transcribe(data):
    global _model
    if not status()['ready']:
        raise RuntimeError('本機語音辨識模型尚未安裝，請執行 tools/prepare_voice.py。')
    if not _lock.acquire(blocking=False):
        raise BlockingIOError('另一段語音辨識中，請稍後重試。')
    try:
        from faster_whisper import WhisperModel, decode_audio
        from opencc import OpenCC
        try:
            audio = decode_audio(io.BytesIO(data), sampling_rate=16000)
        except Exception as e:
            raise ValueError('錄音無法解碼，請重新錄製。') from e
        seconds = len(audio)/16000
        if seconds < .25 or seconds > MAX_SECONDS:
            raise ValueError('請錄製 0.25 至 60 秒的語音。')
        if _model is None:
            _model = WhisperModel(str(model_path()), device='cpu', compute_type='int8', cpu_threads=4, local_files_only=True)
        segments, _ = _model.transcribe(audio, language='zh', beam_size=5, vad_filter=True,
            condition_on_previous_text=False, initial_prompt='繁體中文，醫事人員、病患、物理治療師、營養師、交接。')
        text = OpenCC('s2twp').convert(''.join(s.text for s in segments).strip())
        if not text:
            raise ValueError('沒有辨識到清楚語音，請靠近麥克風再試一次。')
        return {'text':text[:2000], 'seconds':round(seconds,2),'model':MODEL_NAME,'local':True}
    finally:
        _lock.release()
