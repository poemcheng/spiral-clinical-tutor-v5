"""AUTOMATIC1111 WebUI API 管理與分鏡圖生成。

除了檢查 API，也會尋找本機安裝目錄，並可在第一次需要時以 ``--api``
自動啟動。所有生成仍由 server.py 的共用模型鎖序列化，避免與 Ollama
同時搶用 GPU。
"""
from __future__ import annotations

import base64
import json
import os
import subprocess
import threading
import time
import urllib.request
from pathlib import Path
from typing import Any, Dict, Optional

from .config import (DATA_DIR, ROOT, SD_AUTO_START, SD_START_TIMEOUT,
                     SD_WEBUI_DIR, SD_WEBUI_URL)

SD_URL = SD_WEBUI_URL
SD_STEPS = int(os.getenv("SD_STEPS") or "22")
SD_SIZE = int(os.getenv("SD_SIZE") or "512")
SD_TIMEOUT = int(os.getenv("SD_TIMEOUT") or "180")
MEDIA_DIR = DATA_DIR / "media"
LOG_DIR = DATA_DIR / "logs"

NEGATIVE = ("lowres, bad anatomy, bad hands, extra fingers, deformed face, "
            "text, watermark, signature, blurry, duplicate person, nsfw")

EMOTION_EN = {
    "happy": "warm smile, relaxed expression",
    "receptive": "gentle attentive expression, slight smile",
    "neutral": "calm neutral expression",
    "wary": "worried skeptical frown, furrowed brows",
    "upset": "frustrated upset expression, frowning",
}

AVATAR_EN = {
    ("male", "elder"): "elderly Taiwanese man in his late 60s",
    ("male", "middle"): "middle-aged Taiwanese man",
    ("male", "young"): "young Taiwanese man",
    ("female", "elder"): "elderly Taiwanese woman in her late 60s",
    ("female", "middle"): "middle-aged Taiwanese woman",
    ("female", "young"): "young Taiwanese woman",
}

HAIR_EN = {"short": "short gray hair", "bun": "gray hair in a bun",
           "bald": "balding with sparse gray hair", "long": "shoulder-length hair"}
COLOR_EN = {"blue": "light blue", "purple": "lavender", "green": "sage green",
            "brown": "beige", "pink": "light pink"}

_process: Optional[subprocess.Popen] = None
_launch_lock = threading.Lock()
_last_launch_error = ""


def _api_models(timeout: int = 4) -> list[str]:
    req = urllib.request.Request(f"{SD_URL}/sdapi/v1/sd-models", method="GET")
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        models = json.loads(resp.read().decode("utf-8", errors="replace"))
    return [str(m.get("model_name", "")) for m in models][:5]


def find_webui_dir() -> Optional[Path]:
    """只掃描明確與常見位置，避免對整顆磁碟做昂貴遞迴搜尋。"""
    home = Path.home()
    candidates = [
        Path(SD_WEBUI_DIR) if SD_WEBUI_DIR else None,
        ROOT.parent / "stable-diffusion-webui",
        ROOT / "stable-diffusion-webui",
        Path("D:/stable-diffusion-webui"), Path("D:/AUTOMATIC1111"),
        Path("C:/stable-diffusion-webui"), Path("C:/AUTOMATIC1111"),
        home / "stable-diffusion-webui",
        home / "Downloads" / "stable-diffusion-webui",
    ]
    for candidate in candidates:
        if not candidate:
            continue
        try:
            path = candidate.expanduser().resolve()
        except Exception:
            continue
        if path.is_dir() and any((path / name).is_file() for name in
                                 ("webui-user.bat", "webui.bat", "webui.sh")):
            return path
    return None


def check() -> Dict[str, Any]:
    webui_dir = find_webui_dir()
    try:
        models = _api_models()
        if not models:
            return {"ready": False, "api_reachable": True, "url": SD_URL,
                    "models": [], "model_count": 0,
                    "error": "Stable Diffusion API 已連線，但尚未安裝 checkpoint 模型。",
                    "detail": "請將 .safetensors 或 .ckpt 放入 models/Stable-diffusion。",
                    "installed": bool(webui_dir),
                    "webui_dir": str(webui_dir) if webui_dir else "",
                    "starting": False, "auto_start": SD_AUTO_START}
        return {"ready": True, "api_reachable": True, "url": SD_URL,
                "models": models, "model_count": len(models), "error": "",
                "installed": bool(webui_dir),
                "webui_dir": str(webui_dir) if webui_dir else "",
                "starting": False, "auto_start": SD_AUTO_START}
    except Exception as exc:
        running = bool(_process and _process.poll() is None)
        if running:
            message = "Stable Diffusion WebUI 正在啟動，模型載入可能需要 1–2 分鐘。"
        elif webui_dir:
            message = "已找到 AUTOMATIC1111，但 API 尚未啟動；可按「啟動 SD WebUI API」。"
        else:
            message = ("未找到 AUTOMATIC1111 安裝目錄。請在 .env 設定 "
                       "SD_WEBUI_DIR，例如 D:\\AI\\stable-diffusion-webui。")
        detail = _last_launch_error or str(exc)
        return {"ready": False, "api_reachable": False, "url": SD_URL,
                "models": [], "model_count": 0, "error": message,
                "detail": detail, "installed": bool(webui_dir),
                "webui_dir": str(webui_dir) if webui_dir else "",
                "starting": running, "auto_start": SD_AUTO_START}


def start() -> Dict[str, Any]:
    """啟動 AUTOMATIC1111。重複呼叫安全，不會再開第二個程序。"""
    global _process, _last_launch_error
    ready = check()
    if ready["ready"]:
        return ready
    webui_dir = find_webui_dir()
    if not webui_dir:
        return ready
    with _launch_lock:
        if _process and _process.poll() is None:
            return check()
        # 優先使用 webui-user.bat，才能沿用該機器已驗證的 Python、Git、Torch/CUDA
        # 設定。若使用者檔尚未包含 --api，才改由 webui.bat 接受環境變數注入。
        user_script = webui_dir / "webui-user.bat"
        base_script = webui_dir / "webui.bat"
        user_has_api = False
        if user_script.is_file():
            try:
                user_has_api = "--api" in user_script.read_text(
                    encoding="utf-8", errors="ignore")
            except Exception:
                pass
        if user_script.is_file() and user_has_api:
            script = user_script
        elif base_script.is_file():
            script = base_script
        else:
            script = next((webui_dir / n for n in ("webui-user.bat", "webui.sh")
                           if (webui_dir / n).is_file()), None)
        if not script:
            _last_launch_error = f"{webui_dir} 缺少 webui-user.bat / webui.bat。"
            return check()
        LOG_DIR.mkdir(parents=True, exist_ok=True)
        log_path = LOG_DIR / "sd_webui.log"
        env = os.environ.copy()
        args = env.get("COMMANDLINE_ARGS", "")
        if "--api" not in args.split():
            env["COMMANDLINE_ARGS"] = (args + " --api").strip()
        try:
            log_handle = log_path.open("a", encoding="utf-8")
            if script.suffix.lower() == ".bat":
                command = [os.environ.get("COMSPEC", "cmd.exe"), "/d", "/c", str(script)]
            else:
                command = ["bash", str(script), "--api"]
            flags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
            _process = subprocess.Popen(command, cwd=str(webui_dir), env=env,
                                        stdout=log_handle, stderr=subprocess.STDOUT,
                                        creationflags=flags)
            _last_launch_error = ""
        except Exception as exc:
            _last_launch_error = f"啟動失敗：{exc}"
    return check()


def ensure_ready(timeout: int = SD_START_TIMEOUT) -> Dict[str, Any]:
    status = check()
    if status["ready"] or not SD_AUTO_START:
        return status
    status = start()
    if not status.get("installed"):
        return status
    deadline = time.monotonic() + max(timeout, 1)
    while time.monotonic() < deadline:
        try:
            models = _api_models(timeout=4)
            if models:
                return {**check(), "ready": True, "api_reachable": True,
                        "models": models, "model_count": len(models), "error": ""}
            status = check()
            status["error"] = "Stable Diffusion API 已啟動，但尚未安裝 checkpoint 模型。"
            return status
        except Exception:
            if _process and _process.poll() is not None:
                break
            time.sleep(2)
    status = check()
    if not status["ready"]:
        status["error"] = (f"AUTOMATIC1111 在 {timeout} 秒內尚未完成啟動；"
                           f"請查看 {LOG_DIR / 'sd_webui.log'}。")
    return status


def unload_checkpoint() -> None:
    """釋放 SD checkpoint 的 VRAM，下一個模型動作才能安全開始。"""
    try:
        req = urllib.request.Request(f"{SD_URL}/sdapi/v1/unload-checkpoint",
                                     data=b"{}", headers={"Content-Type": "application/json"},
                                     method="POST")
        with urllib.request.urlopen(req, timeout=30):
            pass
    except Exception:
        # 舊版 WebUI 可能沒有此端點；生成結果不應因此判定失敗。
        pass


def stop() -> Dict[str, Any]:
    """停止由本平台啟動的 WebUI 程序樹；外部自行啟動的 WebUI 不會被關閉。"""
    global _process
    if not _process or _process.poll() is not None:
        return {"ok": True, "stopped": False, "reason": "not_managed_by_platform"}
    pid = _process.pid
    try:
        if os.name == "nt":
            subprocess.run(["taskkill", "/PID", str(pid), "/T", "/F"],
                           capture_output=True, timeout=20,
                           creationflags=subprocess.CREATE_NO_WINDOW)
        else:  # pragma: no cover
            _process.terminate()
            _process.wait(timeout=20)
        _process = None
        return {"ok": True, "stopped": True, "pid": pid}
    except Exception as exc:
        return {"ok": False, "stopped": False, "pid": pid, "error": str(exc)}


def character_prefix(persona: Dict[str, Any]) -> str:
    avatar = persona.get("avatar") or {}
    sheet = persona.get("video_character_sheet") or {}
    who = AVATAR_EN.get((avatar.get("gender", "female"), avatar.get("age_group", "elder")),
                        "elderly Taiwanese person")
    hair = HAIR_EN.get(avatar.get("hair", "short"), "gray hair")
    glasses = "wearing glasses, " if avatar.get("glasses") else ""
    color = COLOR_EN.get(avatar.get("clothing_color", "blue"), "light blue")
    setting = sheet.get("setting") or "hospital consultation room"
    return (f"photo of {who}, {hair}, {glasses}wearing a {color} cardigan, "
            f"sitting in a {setting}, soft natural lighting, medium shot, "
            f"photorealistic, high quality, consistent character")


def segment_prompt(persona: Dict[str, Any], segment: Dict[str, Any]) -> str:
    emo = EMOTION_EN.get(segment.get("emotion", "neutral"), EMOTION_EN["neutral"])
    return f"{character_prefix(persona)}, {emo}. Scene: {segment.get('visual', '')}"


def generate_segment_image(session_id: int, persona: Dict[str, Any],
                           segment: Dict[str, Any]) -> Dict[str, Any]:
    status = ensure_ready()
    if not status["ready"]:
        return {"ok": False, "error": status["error"]}
    seed = 900000 + session_id
    payload = {
        "prompt": segment_prompt(persona, segment), "negative_prompt": NEGATIVE,
        "steps": SD_STEPS, "width": SD_SIZE, "height": SD_SIZE, "seed": seed,
        "cfg_scale": 7, "sampler_name": "DPM++ 2M",
    }
    try:
        req = urllib.request.Request(
            f"{SD_URL}/sdapi/v1/txt2img",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"}, method="POST")
        with urllib.request.urlopen(req, timeout=SD_TIMEOUT) as resp:
            result = json.loads(resp.read().decode("utf-8", errors="replace"))
        images = result.get("images") or []
        if not images:
            return {"ok": False, "error": "Stable Diffusion 未回傳圖片。"}
        out_dir = MEDIA_DIR / f"session_{session_id}"
        out_dir.mkdir(parents=True, exist_ok=True)
        seq = int(segment.get("seq", 0))
        path = out_dir / f"seg_{seq:02d}.png"
        path.write_bytes(base64.b64decode(images[0].split(",", 1)[-1]))
        return {"ok": True, "url": f"/media/session_{session_id}/seg_{seq:02d}.png"}
    except Exception as exc:
        return {"ok": False, "error": f"Stable Diffusion 生成失敗：{exc}"}
    finally:
        unload_checkpoint()
