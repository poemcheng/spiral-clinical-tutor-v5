"""把 12 段教學分鏡渲染成可嵌入與下載的 MP4。

Stable Diffusion 圖片存在時優先使用；未安裝 SD 時，以內建醫療情境版型
產生完整字幕影片，確保單一 EXE 在離線環境仍具備影片輸出能力。
"""
from __future__ import annotations

import subprocess
import tempfile
from pathlib import Path
from typing import Any, Dict

from PIL import Image, ImageDraw, ImageFont, ImageOps

from .sd_generator import MEDIA_DIR

WIDTH, HEIGHT = 960, 540


def _font(size: int, bold: bool = False):
    candidates = ([Path("C:/Windows/Fonts/msjhbd.ttc"), Path("C:/Windows/Fonts/NotoSansTC-VF.ttf")]
                  if bold else
                  [Path("C:/Windows/Fonts/msjh.ttc"), Path("C:/Windows/Fonts/NotoSansTC-VF.ttf"),
                   Path("C:/Windows/Fonts/kaiu.ttf")])
    for path in candidates:
        if path.exists():
            try:
                return ImageFont.truetype(str(path), size=size)
            except Exception:
                pass
    return ImageFont.load_default()


def capabilities() -> Dict[str, Any]:
    try:
        import imageio_ffmpeg
        exe = Path(imageio_ffmpeg.get_ffmpeg_exe())
        if not exe.is_file():
            raise FileNotFoundError(str(exe))
        result = subprocess.run([str(exe), "-version"], capture_output=True, text=True,
                                encoding="utf-8", errors="replace", timeout=8,
                                creationflags=(subprocess.CREATE_NO_WINDOW if hasattr(subprocess, "CREATE_NO_WINDOW") else 0))
        first = (result.stdout or result.stderr or "").splitlines()[0]
        return {"ready": result.returncode == 0, "engine": "bundled FFmpeg",
                "version": first, "path": str(exe), "error": "" if result.returncode == 0 else first}
    except Exception as exc:
        return {"ready": False, "engine": "bundled FFmpeg", "version": "",
                "path": "", "error": f"影片引擎不可用：{exc}"}


def _wrap(draw: ImageDraw.ImageDraw, text: str, font, max_width: int) -> list[str]:
    lines: list[str] = []
    for paragraph in str(text or "").splitlines() or [""]:
        current = ""
        for char in paragraph:
            candidate = current + char
            if current and draw.textbbox((0, 0), candidate, font=font)[2] > max_width:
                lines.append(current)
                current = char
            else:
                current = candidate
        if current:
            lines.append(current)
    return lines


def _media_image(url: str) -> Path | None:
    prefix = "/media/"
    if not url or not str(url).startswith(prefix):
        return None
    candidate = (MEDIA_DIR / str(url)[len(prefix):]).resolve()
    try:
        candidate.relative_to(MEDIA_DIR.resolve())
    except ValueError:
        return None
    return candidate if candidate.is_file() else None


def _draw_frame(segment: dict, persona: dict, case: dict, output: Path) -> bool:
    seq = int(segment.get("seq") or 1)
    colors = [(8, 47, 73), (7, 89, 133), (15, 76, 92), (22, 78, 99)]
    bg = Image.new("RGB", (WIDTH, HEIGHT), colors[(seq - 1) % len(colors)])
    draw = ImageDraw.Draw(bg)
    # 輕量漸層，讓無 SD 的離線影片也有完整視覺層次。
    for y in range(HEIGHT):
        alpha = y / HEIGHT
        c = tuple(int(v * (1 - .24 * alpha)) for v in colors[(seq - 1) % len(colors)])
        draw.line((0, y, WIDTH, y), fill=c)

    used_sd = False
    image_path = _media_image(str(segment.get("image") or ""))
    if image_path:
        try:
            picture = Image.open(image_path).convert("RGB")
            picture = ImageOps.fit(picture, (WIDTH, HEIGHT), method=Image.Resampling.LANCZOS)
            bg.paste(picture, (0, 0))
            used_sd = True
        except Exception:
            used_sd = False

    overlay = Image.new("RGBA", (WIDTH, HEIGHT), (0, 0, 0, 0))
    od = ImageDraw.Draw(overlay)
    od.rectangle((0, 0, WIDTH, 82), fill=(5, 18, 33, 205))
    od.rectangle((0, 310, WIDTH, HEIGHT), fill=(5, 18, 33, 218))
    if not used_sd:
        # 內建虛擬病患剪影。
        od.ellipse((66, 118, 226, 278), fill=(244, 199, 161, 255), outline=(255, 255, 255, 170), width=4)
        od.pieslice((48, 99, 244, 287), 190, 350, fill=(71, 85, 105, 255))
        od.ellipse((103, 179, 115, 191), fill=(30, 41, 59, 255))
        od.ellipse((175, 179, 187, 191), fill=(30, 41, 59, 255))
        od.arc((126, 192, 166, 225), 10, 170, fill=(139, 74, 58, 255), width=4)
        od.rounded_rectangle((35, 245, 257, 480), radius=80, fill=(14, 165, 233, 230))
        od.rounded_rectangle((315, 118, 900, 276), radius=18, fill=(255, 255, 255, 225))
    bg = Image.alpha_composite(bg.convert("RGBA"), overlay).convert("RGB")
    draw = ImageDraw.Draw(bg)

    white, pale, gold = (255, 255, 255), (203, 213, 225), (253, 230, 138)
    draw.text((32, 21), f"AI 臨床教學影片  ·  {seq:02d}/12", font=_font(24, True), fill=white)
    draw.text((WIDTH - 250, 26), str(case.get("title") or "臨床情境訓練")[:18], font=_font(17), fill=pale)
    if not used_sd:
        title_x, title_y, title_color = 340, 137, (15, 23, 42)
    else:
        title_x, title_y, title_color = 36, 105, white
    draw.text((title_x, title_y), str(segment.get("title") or "臨床情境"), font=_font(28, True), fill=title_color)
    visual = str(segment.get("visual") or "")
    for i, line in enumerate(_wrap(draw, visual, _font(18), 520 if not used_sd else 850)[:4]):
        draw.text((title_x, title_y + 48 + i * 28), line, font=_font(18), fill=(51, 65, 85) if not used_sd else pale)

    narration = str(segment.get("narration") or "")
    for i, line in enumerate(_wrap(draw, narration, _font(23), WIDTH - 80)[:4]):
        draw.text((40, 335 + i * 34), line, font=_font(23), fill=white)
    patient_line = str(segment.get("patient_line") or "").strip()
    if patient_line:
        line = "病患：『" + patient_line + "』"
        draw.text((40, 484), line[:45], font=_font(19, True), fill=gold)
    draw.text((WIDTH - 246, HEIGHT - 24), f"虛擬病患：{persona.get('name', '病患')}", font=_font(14), fill=pale)
    bg.save(output, "PNG", optimize=True)
    return used_sd


def render(session_id: int, script: dict, persona: dict, case: dict) -> Dict[str, Any]:
    status = capabilities()
    if not status["ready"]:
        return {"ok": False, "error": status["error"]}
    segments = list(script.get("segments") or [])
    if not segments:
        return {"ok": False, "error": "影片腳本沒有可渲染的分鏡。"}
    duration = max(1, int(script.get("seg_seconds") or 8))
    out_dir = MEDIA_DIR / f"session_{session_id}"
    out_dir.mkdir(parents=True, exist_ok=True)
    output = out_dir / "training_video.mp4"
    sd_count = 0
    try:
        import imageio_ffmpeg
        ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
        with tempfile.TemporaryDirectory(prefix=f"clinical_video_{session_id}_") as tmp_name:
            tmp = Path(tmp_name)
            frames: list[Path] = []
            for i, segment in enumerate(segments, start=1):
                frame = tmp / f"frame_{i:02d}.png"
                if _draw_frame(segment, persona, case, frame):
                    sd_count += 1
                frames.append(frame)
            concat = tmp / "frames.txt"
            lines: list[str] = []
            for frame in frames:
                lines.extend([f"file '{frame.as_posix()}'", f"duration {duration}"])
            lines.append(f"file '{frames[-1].as_posix()}'")
            concat.write_text("\n".join(lines), encoding="utf-8")
            command = [ffmpeg, "-y", "-f", "concat", "-safe", "0", "-i", str(concat),
                       "-f", "lavfi", "-i", "anullsrc=channel_layout=stereo:sample_rate=44100",
                       "-vf", "fps=24,format=yuv420p", "-c:v", "libx264", "-preset", "veryfast",
                       "-crf", "24", "-c:a", "aac", "-b:a", "64k", "-shortest",
                       "-t", str(duration * len(frames)), "-movflags", "+faststart", str(output)]
            result = subprocess.run(command, capture_output=True, text=True, encoding="utf-8",
                                    errors="replace", timeout=max(180, len(frames) * 20),
                                    creationflags=(subprocess.CREATE_NO_WINDOW if hasattr(subprocess, "CREATE_NO_WINDOW") else 0))
            if result.returncode != 0 or not output.is_file():
                detail = (result.stderr or result.stdout or "FFmpeg 未輸出檔案")[-1200:]
                return {"ok": False, "error": f"MP4 產生失敗：{detail}"}
        return {"ok": True, "url": f"/media/session_{session_id}/training_video.mp4",
                "bytes": output.stat().st_size, "duration_seconds": duration * len(segments),
                "sd_images_used": sd_count, "has_audio": False}
    except Exception as exc:
        return {"ok": False, "error": f"MP4 產生失敗：{exc}"}
