"""影片自動生成（v3）。

兩層輸出，皆使用「病患生成 skill」產出的同一位病人（人物連續性）：
1. 站內自動播放腳本（12 段 × 8 秒 = 96 秒）：LLM 生成逐段 JSON
   （場景、旁白、病患情緒），前端以虛擬人動畫＋字幕＋瀏覽器語音合成直接播放，
   無需外部工具。AI 不可用時由教案分鏡自動展開為 12 段模板。
2. 外部影片生成 Prompt（Google Flow / Veo）：逐段 Prompt ＋ 人物連續性設定表
   （臉型、髮型、服裝、診間、光線、鏡頭、每段開始/結尾姿勢），
   對應 reference 報告要求的 12×8 秒與角色一致性規範。
"""
from __future__ import annotations

import json
from typing import Any, Dict, List

from .llm import OllamaService

SEGMENTS = 12
SEG_SECONDS = 8

VALID_FACES = {"happy", "receptive", "neutral", "wary", "upset"}

SYSTEM = (
    "你是醫療教學影片編劇。輸出的旁白要能唸出來（口語、每段 8 秒內唸完，約 25-35 字）。"
    "只輸出 JSON，不要輸出任何其他文字。"
)


def build_script_prompt(case: Dict[str, Any], persona: Dict[str, Any], profession_label: str) -> str:
    scenes = "\n".join(f"- {s['scene']}：{s['visual']}｜提示：{s['cue']}"
                       for s in case.get("storyboard", [])[:6]) or "（無分鏡素材）"
    sheet = persona.get("video_character_sheet") or {}
    sheet_txt = json.dumps(sheet, ensure_ascii=False) if sheet else "（未定義，請自行設定並保持一致）"
    return f"""請為以下教學情境寫 12 段、每段 8 秒（共 96 秒）的情境影片腳本。

【教案】{case['title']}
【病人】{persona.get('name','病人')}：{persona.get('identity') or case.get('patient','')}
【病人目前情緒】{persona.get('emotion','')}（信任 {persona.get('trust',50)}/100）
【觀看對象】{profession_label} 學員（影片是互動前的情境導入，讓學員理解病人處境與挑戰）
【分鏡素材】
{scenes}
【人物連續性設定】{sheet_txt}

結構要求：第 1-2 段病人背景與就醫原因；第 3-6 段揭露臨床線索與病人的疑慮；
第 7-10 段呈現病人與{profession_label}互動時的挑戰（不給標準答案）；
第 11-12 段收在「學員接下來要面對的任務」。

emotion 只能是：happy / receptive / neutral / wary / upset。

只輸出以下 JSON：
{{"segments": [{{"seq": 1, "title": "段落標題(8字內)", "visual": "畫面描述(30字內)",
  "narration": "旁白(25-35字，口語可唸)", "patient_line": "病患台詞(可空字串)",
  "emotion": "neutral"}}]}}"""


def _fallback_segments(case: Dict[str, Any], persona: Dict[str, Any]) -> List[Dict[str, Any]]:
    board = case.get("storyboard") or [{"scene": "情境導入", "visual": case.get("summary", ""), "voice": "", "cue": ""}]
    segments = []
    for n in range(1, SEGMENTS + 1):
        s = board[(n - 1) * len(board) // SEGMENTS]
        segments.append({
            "seq": n,
            "title": s["scene"][:12],
            "visual": s["visual"][:60],
            "narration": (s.get("voice") or s.get("cue") or s["visual"])[:48],
            "patient_line": persona.get("opening", "") if n == 3 else "",
            "emotion": "wary" if n >= 7 else "neutral",
        })
    return segments


def _validate_segments(raw: Any) -> List[Dict[str, Any]] | None:
    if not isinstance(raw, dict):
        return None
    segs = raw.get("segments")
    if not isinstance(segs, list) or len(segs) < 6:
        return None
    out = []
    for i, s in enumerate(segs[:SEGMENTS], 1):
        if not isinstance(s, dict):
            return None
        emo = str(s.get("emotion", "neutral"))
        out.append({
            "seq": i,
            "title": str(s.get("title", f"第 {i} 段"))[:16],
            "visual": str(s.get("visual", ""))[:80],
            "narration": str(s.get("narration", ""))[:80],
            "patient_line": str(s.get("patient_line", ""))[:80],
            "emotion": emo if emo in VALID_FACES else "neutral",
        })
    while len(out) < SEGMENTS:  # 不足 12 段時複製收尾段
        last = dict(out[-1]); last["seq"] = len(out) + 1
        out.append(last)
    return out


def external_prompt(case: Dict[str, Any], persona: Dict[str, Any],
                    segments: List[Dict[str, Any]]) -> str:
    """Google Flow / Veo 逐段 Prompt ＋ 人物連續性設定表。"""
    sheet = persona.get("video_character_sheet") or {}
    L = ["【人物連續性設定表（每段生成都必須完全一致）】",
         f"- 病人：{persona.get('name','病人')}，{persona.get('age','')}歲；{persona.get('identity','')}",
         f"- 臉型五官：{sheet.get('face','固定不變')}",
         f"- 髮型：{sheet.get('hair','固定不變')}",
         f"- 服裝：{sheet.get('clothing','固定不變')}",
         f"- 體型：{sheet.get('body','固定不變')}",
         f"- 場景：{sheet.get('setting','同一診間，擺設固定')}",
         f"- 光線色調：{sheet.get('lighting','自然柔光，色調一致')}",
         f"- 鏡頭：{sheet.get('camera','固定方向，中景為主')}",
         "- 每段開始姿勢＝上一段結尾姿勢；禁止改變髮型、服裝、場景與角色外貌。",
         "", f"【逐段 Prompt｜共 {SEGMENTS} 段 × {SEG_SECONDS} 秒 = {SEGMENTS*SEG_SECONDS} 秒】"]
    for s in segments:
        L.append(f"\n第 {s['seq']} 段（{SEG_SECONDS} 秒）｜{s['title']}")
        L.append(f"畫面：{s['visual']}")
        if s.get("patient_line"):
            L.append(f"病患台詞：「{s['patient_line']}」")
        L.append(f"旁白：{s['narration']}")
        L.append(f"病患情緒：{s['emotion']}；延續上一段結尾姿勢開場。")
    return "\n".join(L)


def generate_video_script(llm: OllamaService, case: Dict[str, Any],
                          persona: Dict[str, Any], profession_label: str) -> Dict[str, Any]:
    status = llm.check()
    segments = None
    source = "fallback_storyboard"
    note = ""
    if status.ready:
        result = llm.generate_json(build_script_prompt(case, persona, profession_label),
                                   system=SYSTEM, max_tokens=2200,
                                   operation="編寫情境影片腳本")
        if result.ok:
            try:
                segments = _validate_segments(json.loads(result.text))
                if segments:
                    source = "ai_generated"
                    note = f"由 {result.model} 依教案與本輪病患設定自動編寫"
                else:
                    note = "AI 腳本格式不符，改用教案分鏡模板"
            except json.JSONDecodeError:
                note = "AI 腳本 JSON 解析失敗，改用教案分鏡模板"
        else:
            note = result.error
    else:
        note = status.error
    if segments is None:
        segments = _fallback_segments(case, persona)
    return {
        "segments": segments,
        "seg_seconds": SEG_SECONDS,
        "total_seconds": SEG_SECONDS * len(segments),
        "source": source,
        "source_note": note,
        "character_sheet": persona.get("video_character_sheet") or {},
        "external_prompt": external_prompt(case, persona, segments),
    }
