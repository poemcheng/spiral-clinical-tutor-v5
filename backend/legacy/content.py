"""內容載入層（v3）：自評表、客觀前測、rubric、教案、personas。

修正 v2 問題：
- 移除編碼損毀殘留（"????" 別名）。
- 教案推薦優先序改為資料驅動（case JSON 的 priority 欄位）。
- 登入頁只顯示「內容已齊備」的職種×症狀組合（自動掃描）。
- 教案支援 overlays（personas、key_information、priority、video_file）。
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import quote

from .config import (LESSON_CASES_DIR, OVERLAYS_DIR, SELF_ASSESSMENTS_DIR,
                     VIDEO_LESSONS_DIR, VIDEO_LIBRARY_DIR)
from .builtin_cases import CASES as BUILTIN_CASES
from .builtin_cases import DIMENSIONS, PROFESSIONS, SYMPTOMS

DIMENSION_ORDER = ["CJ", "PC", "COM", "TC", "SAFE", "HC"]

CANONICAL_DIMENSION_NAMES = {
    "CJ": "臨床判斷能力",
    "PC": "病人評估與照護能力",
    "COM": "醫病溝通與衛教能力",
    "TC": "跨團隊溝通能力",
    "SAFE": "病人安全與倫理意識",
    "HC": "全人照護與介入規劃能力",
}

CANONICAL_DIMENSION_ALIASES = {
    "CJ": "CJ", "PA": "PC", "PC": "PC", "IP": "HC", "CM": "COM", "COM": "COM",
    "TC": "TC", "SE": "SAFE", "SAFE": "SAFE", "HC": "HC",
    "DT_CJ": "CJ", "DT_NA": "PC", "DT_IP": "HC", "DT_CM": "COM",
    "DT_TC": "TC", "DT_SE": "SAFE",
    "EMPATHY": "COM", "EXPLAIN": "COM", "SHARED_PLAN": "HC", "TEACHBACK": "COM",
    "ENERGY": "CJ", "PROTEIN": "PC", "SUBSTITUTE": "COM", "MONITOR": "PC",
    "FEASIBILITY": "HC",
    "S": "TC", "B": "TC", "A": "TC", "R": "TC",
}


def canon_dim(raw: str) -> str:
    return CANONICAL_DIMENSION_ALIASES.get(str(raw), str(raw) if str(raw) in DIMENSION_ORDER else "HC")


# ---------------------------------------------------------------------------
# Markdown assessment forms
# ---------------------------------------------------------------------------

def _read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return path.read_text(encoding="utf-8-sig")


def load_assessment_md(path: Path) -> Optional[Dict[str, Any]]:
    text = _read_text(path)
    match = re.search(r"```json\s+assessment_data\s*\n(.*?)\n```", text, re.S)
    if not match:
        return None
    data = json.loads(match.group(1))
    data["_source_file"] = path.name
    return data


def load_all_forms() -> Tuple[List[Dict[str, Any]], List[str]]:
    forms, errors = [], []
    if not SELF_ASSESSMENTS_DIR.exists():
        return forms, [f"找不到資料夾：{SELF_ASSESSMENTS_DIR}"]
    for path in sorted(SELF_ASSESSMENTS_DIR.glob("*.md")):
        if path.name.startswith("00_") or path.name.upper() == "INDEX.MD":
            continue
        try:
            data = load_assessment_md(path)
            if data:
                forms.append(data)
        except Exception as exc:
            errors.append(f"{path.name}: {exc}")
    return forms, errors


def _matches(form: Dict[str, Any], profession: str, symptom: str) -> bool:
    prof_ok = form.get("profession") in {profession, "ALL", None}
    symp_ok = form.get("symptom") in {symptom, "ALL", None}
    return prof_ok and symp_ok


def _item_types(form: Dict[str, Any]) -> set:
    return {str(i.get("item_type", "likert")).lower() for i in form.get("items", []) if isinstance(i, dict)}


def is_likert_form(form: Dict[str, Any]) -> bool:
    types = _item_types(form)
    return bool(types & {"likert", "self_rating", "rating"})


def is_objective_form(form: Dict[str, Any]) -> bool:
    fid = str(form.get("form_id", "")).upper()
    types = _item_types(form)
    return "OBJ" in fid or bool(types & {"single_choice", "multiple_choice"})


def is_rubric_form(form: Dict[str, Any]) -> bool:
    fid = str(form.get("form_id", "")).upper()
    src = str(form.get("_source_file", "")).upper()
    # "COMM-" 精準匹配溝通 rubric（避免誤判 COMMON_CORE）
    return bool(re.search(r"COMM-|SBAR|RUBRIC", fid + " " + src))


def choose_step1_form(forms: List[Dict[str, Any]], profession: str) -> Optional[Dict[str, Any]]:
    candidates = [f for f in forms if is_likert_form(f) and not is_rubric_form(f) and not is_objective_form(f)]
    if not candidates:
        return None

    def priority(form: Dict[str, Any]) -> tuple:
        src = form.get("_source_file", "")
        fid = str(form.get("form_id", ""))
        if form.get("profession") == profession and "STEP1" in (fid + src).upper():
            return (0, src)
        if form.get("profession") == profession:
            return (1, src)
        if src.startswith("02_"):
            return (2, src)
        return (3, src)

    return sorted(candidates, key=priority)[0]


def choose_objective_form(forms: List[Dict[str, Any]], profession: str) -> Optional[Dict[str, Any]]:
    candidates = [f for f in forms if is_objective_form(f)]
    if not candidates:
        return None
    exact = [f for f in candidates if f.get("profession") == profession]
    return (exact or candidates)[0]


def rubric_forms(forms: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    return [f for f in forms if is_rubric_form(f)]


def dimensions_from_form(form: Dict[str, Any]) -> List[Dict[str, Any]]:
    """轉成 {id, name, desc, items:[{item_id, prompt}]} 結構（保留 item_id）。"""
    dims_meta = {d.get("dimension_id"): d for d in form.get("dimensions", []) if isinstance(d, dict)}
    grouped: Dict[str, Dict[str, Any]] = {}
    for idx, item in enumerate(form.get("items", []) or []):
        if not isinstance(item, dict):
            continue
        if str(item.get("item_type", "likert")).lower() not in {"likert", "self_rating", "rating"}:
            continue
        raw_dim = item.get("dimension_id") or item.get("dimension") or "HC"
        canon = canon_dim(str(raw_dim))
        meta = dims_meta.get(raw_dim, {})
        name = meta.get("name") or CANONICAL_DIMENSION_NAMES.get(canon, str(raw_dim))
        prompt = item.get("prompt") or item.get("question") or item.get("text")
        if not prompt:
            continue
        entry = grouped.setdefault(canon, {
            "id": canon, "name": str(name),
            "desc": str(meta.get("description") or form.get("form_title") or ""),
            "items": [],
        })
        entry["items"].append({
            "item_id": str(item.get("item_id") or f"{canon}-{idx+1}"),
            "prompt": str(prompt),
        })
    return [grouped[k] for k in DIMENSION_ORDER if k in grouped]


# 開放式作答題型：short_answer（簡答）、oral_response（口語回應，平台以文字作答）、
# sbar（SBAR 交接）。修正前只認 short_answer，營養師前測的 oral_response×2、
# sbar×1 被靜默略過，醫病溝通與團隊溝通構面因此完全沒有客觀分數。
OPEN_ITEM_TYPES = {"short_answer", "oral_response", "sbar"}


def form_dimension_weights(form: Dict[str, Any]) -> Optional[Dict[str, float]]:
    """讀取自評表 dimensions[].weight 並換成標準構面代碼（同代碼權重相加）。
    表單 scoring 規格寫明 role_weighted_score = Σ(構面分數 × dimension.weight)，
    修正前平台改用內建職種權重，與表單設計不一致。"""
    weights: Dict[str, float] = {}
    for d in form.get("dimensions", []) or []:
        if not isinstance(d, dict):
            continue
        try:
            w = float(d.get("weight"))
        except (TypeError, ValueError):
            continue
        if w > 0:
            canon = canon_dim(str(d.get("dimension_id", "")))
            weights[canon] = weights.get(canon, 0.0) + w
    return weights or None


def objective_items(form: Dict[str, Any]) -> List[Dict[str, Any]]:
    """客觀前測題目：single_choice 自動計分；開放題由 LLM 依 rubric 給 0–max_score 分。"""
    items = []
    for item in form.get("items", []) or []:
        if not isinstance(item, dict):
            continue
        itype = str(item.get("item_type", "")).lower()
        if itype != "single_choice" and itype not in OPEN_ITEM_TYPES:
            continue
        items.append({
            "item_id": str(item.get("item_id")),
            "item_type": itype,
            "dimension": canon_dim(str(item.get("dimension_id") or "HC")),
            "prompt": str(item.get("prompt", "")),
            "options": [str(o) for o in (item.get("options") or [])],
            "answer": str(item.get("answer", "")),
            # 開放題原始檔多以 rubric／expected_keywords 表示標準，而不是
            # 放在 answer。保留這兩欄，送出後才能顯示真正的評分要點。
            "rubric": item.get("rubric") if isinstance(item.get("rubric"), dict) else {},
            "expected_keywords": [str(x) for x in (item.get("expected_keywords") or [])],
            "max_score": int(item.get("max_score", 1) or 1),
        })
    return items


# ---------------------------------------------------------------------------
# Lesson cases
# ---------------------------------------------------------------------------

REQUIRED_KEYS = {
    "id", "title", "symptom", "category", "difficulty", "professions",
    "summary", "patient", "goals", "pre_knowledge", "storyboard",
    "kdp", "quiz", "rubric", "tags",
}
LIST_KEYS = {"professions", "goals", "pre_knowledge", "storyboard", "kdp", "quiz", "rubric", "tags"}


def normalize_case(data: Dict[str, Any], source_file: str = "") -> Dict[str, Any]:
    if not isinstance(data, dict):
        raise ValueError("lesson case JSON must be an object")
    if "case_id" in data and "id" not in data:
        data["id"] = data["case_id"]
    defaults: Dict[str, Any] = {
        "id": "UNKNOWN", "title": "未命名教案", "symptom": "未分類",
        "category": "未分類", "difficulty": "未設定", "professions": ["DT"],
        "source_file": source_file, "summary": "尚未提供摘要。",
        "patient": "尚未提供病人情境。", "goals": [], "pre_knowledge": [],
        "storyboard": [], "kdp": [], "quiz": [], "rubric": [], "tags": [],
        "priority": 0, "key_information": [], "personas": {}, "video_file": "",
    }
    merged = {**defaults, **data}
    for key in LIST_KEYS:
        if merged.get(key) is None:
            merged[key] = []
        elif not isinstance(merged[key], list):
            merged[key] = [merged[key]]
    fixed_storyboard = []
    for i, item in enumerate(merged["storyboard"], 1):
        if isinstance(item, dict):
            fixed_storyboard.append({
                "scene": str(item.get("scene") or item.get("title") or f"Scene {i}"),
                "visual": str(item.get("visual") or item.get("description") or ""),
                "voice": str(item.get("voice") or item.get("narration") or ""),
                "cue": str(item.get("cue") or item.get("prompt") or ""),
            })
        else:
            fixed_storyboard.append({"scene": f"Scene {i}", "visual": str(item), "voice": "", "cue": ""})
    merged["storyboard"] = fixed_storyboard
    fixed_kdp = []
    for i, item in enumerate(merged["kdp"], 1):
        if not isinstance(item, dict):
            continue
        options = []
        for j, opt in enumerate(item.get("options") or []):
            if isinstance(opt, dict):
                options.append({
                    "label": str(opt.get("label") or chr(65 + j)),
                    "text": str(opt.get("text") or opt.get("content") or ""),
                    "score": int(opt.get("score", 0)),
                    "dimension": canon_dim(str(opt.get("dimension") or "COM")),
                    "feedback": str(opt.get("feedback") or "系統尚未提供回饋。"),
                    "on_wrong_context": str(opt.get("on_wrong_context") or ""),
                })
        if not options:
            continue
        fixed_kdp.append({
            "id": str(item.get("id") or f"{merged['id']}-KDP{i}"),
            "phase": str(item.get("phase") or f"關鍵決策點 {i}"),
            "prompt": str(item.get("prompt") or item.get("question") or ""),
            "options": options,
        })
    merged["kdp"] = fixed_kdp
    fixed_quiz = []
    for i, q in enumerate(merged["quiz"], 1):
        if not isinstance(q, dict):
            continue
        options = q.get("options") or []
        if not isinstance(options, list) or len(options) < 2:
            continue
        fixed_quiz.append({
            "id": str(q.get("id") or f"{merged['id']}-Q{i}"),
            "question": str(q.get("question") or q.get("prompt") or ""),
            "options": [str(x) for x in options],
            "answer": str(q.get("answer") or options[0]),
            "dimension": canon_dim(str(q.get("dimension") or "COM")),
            "explain": str(q.get("explain") or q.get("explanation") or ""),
        })
    merged["quiz"] = fixed_quiz
    missing = REQUIRED_KEYS - set(merged.keys())
    if missing:
        raise ValueError(f"missing keys: {sorted(missing)}")
    return merged


def _extract_case_blocks(text: str) -> List[str]:
    patterns = [
        r"```json\s+lesson_case\s*\n(.*?)\n```",
        r"```lesson_case\s*\n(.*?)\n```",
    ]
    blocks: List[str] = []
    for pat in patterns:
        blocks.extend(re.findall(pat, text, flags=re.S | re.I))
    if blocks:
        return blocks
    for raw in re.findall(r"```json\s*\n(.*?)\n```", text, flags=re.S | re.I):
        if '"id"' in raw and '"title"' in raw and '"symptom"' in raw:
            blocks.append(raw)
    return blocks


def load_cases() -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """內建 → catalog → markdown → overlays，後者覆蓋前者（同 id）。"""
    report = {"errors": [], "builtin": 0, "catalog": 0, "markdown": 0, "overlays": 0}
    by_id: Dict[str, Dict[str, Any]] = {}
    for case in BUILTIN_CASES:
        try:
            c = normalize_case(dict(case), source_file="builtin")
            by_id[c["id"]] = c
            report["builtin"] += 1
        except Exception as exc:
            report["errors"].append(f"builtin {case.get('id')}: {exc}")

    catalog_path = LESSON_CASES_DIR / "case_catalog.json"
    if catalog_path.exists():
        try:
            raw = json.loads(_read_text(catalog_path))
            raw_cases = raw.get("cases", []) if isinstance(raw, dict) else raw
            for idx, item in enumerate(raw_cases, 1):
                try:
                    c = normalize_case(item, source_file="case_catalog.json")
                    # markdown 版本較完整時不要被 catalog 縮減版蓋掉：
                    # catalog 只在尚無同 id 或 KDP 較多時覆蓋。
                    old = by_id.get(c["id"])
                    if not old or len(c["kdp"]) >= len(old["kdp"]):
                        by_id[c["id"]] = c
                    report["catalog"] += 1
                except Exception as exc:
                    report["errors"].append(f"case_catalog item {idx}: {exc}")
        except Exception as exc:
            report["errors"].append(f"case_catalog.json: {exc}")

    # The seven platform-authored lesson seeds must remain available on a clean
    # installation where the original Markdown teaching files are not shipped.
    from .published_case_seeds import CASES as published_seeds
    for item in published_seeds:
        c = normalize_case(dict(item), source_file="published_case_seeds")
        old = by_id.get(c["id"])
        if not old or len(c["kdp"]) >= len(old["kdp"]):
            by_id[c["id"]] = c
        report["published_seeds"] = report.get("published_seeds", 0) + 1

    if LESSON_CASES_DIR.exists():
        for path in sorted(LESSON_CASES_DIR.glob("*.md")):
            if path.name.startswith("00_") or path.name.upper() == "INDEX.MD":
                continue
            try:
                blocks = _extract_case_blocks(_read_text(path))
                if not blocks:
                    continue
                c = normalize_case(json.loads(blocks[0]), source_file=path.name)
                old = by_id.get(c["id"])
                if not old or len(c["kdp"]) >= len(old["kdp"]):
                    by_id[c["id"]] = c
                report["markdown"] += 1
            except Exception as exc:
                report["errors"].append(f"{path.name}: {exc}")

    # 三職種課程教案（DT/RT/PT 核心能力、知識卡、五級任務、職種題庫）
    try:
        from .curriculum import curriculum_cases
        for item in curriculum_cases():
            try:
                c = normalize_case(item, source_file="curriculum")
                c["curriculum"] = item.get("curriculum", {})
                by_id[c["id"]] = c
                report["curriculum"] = report.get("curriculum", 0) + 1
            except Exception as exc:
                report["errors"].append(f"curriculum {item.get('id')}: {exc}")
    except Exception as exc:
        report["errors"].append(f"curriculum module: {exc}")

    if OVERLAYS_DIR.exists():
        for path in sorted(OVERLAYS_DIR.glob("*.json")):
            try:
                overlay = json.loads(_read_text(path))
                cid = overlay.get("id") or overlay.get("case_id")
                if cid and cid in by_id:
                    for key, value in overlay.items():
                        if key in {"id", "case_id"}:
                            continue
                        by_id[cid][key] = value
                    report["overlays"] += 1
                elif cid:
                    report["errors"].append(f"{path.name}: 找不到對應教案 {cid}")
            except Exception as exc:
                report["errors"].append(f"{path.name}: {exc}")

    cases = sorted(by_id.values(), key=lambda c: (-int(c.get("priority", 0) or 0), c.get("symptom", ""), c["id"]))
    return cases, report


# ---------------------------------------------------------------------------
# Level profiles / personas
# ---------------------------------------------------------------------------

LEVEL_PROFILES = {
    1: {"title": "Level 1｜老師導引模式",
        "role": "你同時扮演標準化病人與臨床教師。病人反應溫和，教師提示明確。",
        "behavior": "每回合先用病人語氣回應，再用「老師提示：」給 1 個下一步方向。允許犯錯，主動提供鷹架。",
        "difficulty": "低壓、教學式、提示密集。"},
    2: {"title": "Level 2｜半導引練習模式",
        "role": "你扮演病人/家屬，必要時加入簡短教師追問。",
        "behavior": "提供少量線索與反問；學員偏離時用問題帶回評估、溝通或安全重點。",
        "difficulty": "中低壓，有提示但不直接給答案。"},
    3: {"title": "Level 3｜標準情境演練模式",
        "role": "你主要扮演標準化病人、家屬或團隊成員。",
        "behavior": "依學員表現自然回應；同理且安全時給新線索，忽略重點時追問。",
        "difficulty": "標準臨床互動，提示適中。"},
    4: {"title": "Level 4｜獨立執行挑戰模式",
        "role": "你扮演較真實、較有壓力的病人/家屬/團隊成員。",
        "behavior": "減少提示，要求學員說出具體評估、計畫、追蹤或交班內容。",
        "difficulty": "中高壓，重視獨立臨床推理。"},
    5: {"title": "Level 5｜專業指導互動模式",
        "role": "你扮演資深臨床同儕或高擬真病人，能進行專業級追問。",
        "behavior": "不給教學提示；精準追問證據、優先順序、風險控管與跨團隊整合。",
        "difficulty": "高壓、少提示。"},
}

# 同一肌少症低信賴情境下的五級對照：包含學員回答鷹架與虛擬病患
# 回應示例。這些是結構範本，不是要求背誦的逐字標準答案。
LEVEL_RESPONSE_TEMPLATES = {
    1: {
        "learner_structure": "自我介紹與確認身分 → 同理一句 → 問一個基本評估問題 → 說明下一步。",
        "learner_example": "您好，我是營養師。聽得出來您已經很努力，結果卻變差一定很挫折。我想先了解您昨天三餐吃了什麼、每餐大約多少，再一起找出可以先調整的一件事。",
        "patient_example": "好，我昨天早餐喝牛奶，中午吃便當，晚餐有吃排骨。老師提示：下一步可追問每份食物的實際份量。",
    },
    2: {
        "learner_structure": "同理與肯定 → 追問份量／頻率 → 用白話連結數據 → 提出一個可行選項。",
        "learner_example": "您有注意補充牛奶和肉類，這很重要。為了判斷是否真的足夠，我想確認牛奶幾毫升、肉大約幾個掌心，以及一週各吃幾次；因為體重偏輕時，總熱量不足也會影響肌肉生成。",
        "patient_example": "牛奶大概半杯吧，肉有時只有兩三塊。那是不是我其實吃得沒有想像中多？",
    },
    3: {
        "learner_structure": "完整評估 → 說明臨床判斷 → 與病人共同訂 SMART 目標 → Teach-back。",
        "learner_example": "依您的 BMI、DXA 與飲食回顧，我擔心總熱量與蛋白質都不足。我們先把早餐牛奶增加到一杯，晚餐補一掌心蛋白質，兩週後追蹤體重與攝取量。可以請您用自己的話說說這兩週準備怎麼做嗎？",
        "patient_example": "所以不是只有吃肉就夠，整體吃太少也會影響肌肉。可是我容易飽，怎麼增加才不會太撐？",
    },
    4: {
        "learner_structure": "快速抓優先風險 → 提出含數值的個別化計畫 → 說明監測與安全界線 → 安排跨團隊追蹤。",
        "learner_example": "目前優先處理低 BMI 與持續肌肉流失。我會依體重估算需求、分散到三餐與點心，並和物理治療師協調阻力運動後補充；兩週追蹤體重、實際攝取和功能表現，若持續下降會回報醫師評估其他原因。",
        "patient_example": "不要只叫我多吃。請告訴我每天到底加多少、多久看得到變化；如果體重還是下降，你們下一步要做什麼？",
    },
    5: {
        "learner_structure": "交代證據與不確定性 → 排定處置優先序 → 比較替代方案與風險 → 整合團隊並示範如何指導同儕。",
        "learner_example": "我會先驗證攝取不足是否足以解釋目前變化，同時排除疾病、用藥與功能限制。計畫需呈現估算依據、可行替代方案、停止／升級條件，並以 SBAR 串聯醫師、物理治療師與營養追蹤；帶學員時我會要求每項建議都對應一個可量測指標。",
        "patient_example": "你的判斷依據是什麼？若我做不到原方案，有哪些替代選擇，各自的風險與追蹤指標又是什麼？",
    },
}


def level_number(level_text: str | None) -> int:
    text = level_text or ""
    for n in range(1, 6):
        if f"Level {n}" in text or f"Level{n}" in text:
            return n
    return 3


def resolve_persona(case: Dict[str, Any], profession: str, level: int) -> Dict[str, Any]:
    """優先取 case.personas[profession][L{level}]（含就近 fallback），否則合成。"""
    profile = LEVEL_PROFILES[max(1, min(5, level))]
    personas = case.get("personas") or {}
    prof_personas = personas.get(profession) or {}
    persona = None
    for lv in [level] + [l for l in (3, 2, 4, 1, 5) if l != level]:
        if f"L{lv}" in prof_personas:
            persona = dict(prof_personas[f"L{lv}"])
            persona["_persona_level"] = lv
            break
    if persona is None:
        persona = {
            "trust": "依教案設定",
            "emotion": "依教案設定",
            "opening": f"（{case.get('patient', '')[:60]}）",
            "challenge": "依學員回應自然提出疑問",
            "_persona_level": level,
            "_synthesized": True,
        }
    persona["level_profile"] = profile
    return persona


# ---------------------------------------------------------------------------
# 通用自評表（無專屬 Markdown 表單時的內建 fallback，會明確標示）
# ---------------------------------------------------------------------------

def generic_step1_dimensions() -> List[Dict[str, Any]]:
    dims = []
    for d in DIMENSIONS:
        dims.append({
            "id": d["id"],
            "name": d["name"],
            "desc": d["desc"],
            "items": [{"item_id": f"GEN-{d['id']}-{i+1}", "prompt": p}
                      for i, p in enumerate(d["items"])],
        })
    return dims


# ---------------------------------------------------------------------------
# Availability scan（登入頁只顯示已備內容，並標示完備程度）
# ---------------------------------------------------------------------------

def scan_availability(forms: List[Dict[str, Any]], cases: List[Dict[str, Any]]) -> Dict[str, Any]:
    combos = []
    for symptom in SYMPTOMS:
        symptom_cases = [c for c in cases if c["symptom"] == symptom and c["kdp"] and c["quiz"]]
        if not symptom_cases:
            continue
        profs = set()
        for c in symptom_cases:
            profs.update(c.get("professions", []))
        for prof in sorted(profs):
            matched = [f for f in forms if _matches(f, prof, symptom)]
            step1 = choose_step1_form(matched, prof)
            obj = choose_objective_form(matched, prof)
            combos.append({
                "profession": prof,
                "profession_label": PROFESSIONS.get(prof, {}).get("label", prof),
                "symptom": symptom,
                "cases": len(symptom_cases),
                "has_custom_step1": bool(step1),
                "has_pretest": bool(obj),
                "has_personas": any(prof in (c.get("personas") or {}) for c in symptom_cases),
            })
    # 客製內容完整的組合排前面
    combos.sort(key=lambda c: (-int(c["has_custom_step1"]), -int(c["has_pretest"]),
                               -int(c["has_personas"]), c["symptom"], c["profession"]))
    return {"combos": combos}


# ---------------------------------------------------------------------------
# Content registry（啟動時載入一次）
# ---------------------------------------------------------------------------

def load_video_lessons() -> Dict[str, Dict[str, Any]]:
    """載入影片×教案行為分析資料庫，key=case_id。"""
    path = VIDEO_LESSONS_DIR / "video_lessons.json"
    if not path.exists():
        return {}
    try:
        data = json.loads(_read_text(path))
        result = {}
        for vl in data.get("video_lessons", []):
            cid = vl.get("case_id")
            if not cid:
                continue
            # 影片檔存在性檢查（實拍影片庫）
            vf = vl.get("video_file", "")
            vl["video_available"] = bool(vf) and (VIDEO_LIBRARY_DIR / vf).exists()
            vl["video_url"] = f"/library/{quote(vf)}" if vl["video_available"] else ""
            raw = vl.get("raw_video_file", "")
            vl["raw_video_url"] = (f"/library/{quote(raw)}"
                                   if raw and (VIDEO_LIBRARY_DIR / raw).exists() else "")
            result[cid] = vl
        return result
    except Exception:
        return {}


class ContentRegistry:
    def __init__(self):
        self.forms, form_errors = load_all_forms()
        self.cases, self.case_report = load_cases()
        self.case_report["form_errors"] = form_errors
        self.video_lessons = load_video_lessons()
        for case in self.cases:
            if case["id"] in self.video_lessons:
                case["has_video_lesson"] = True
        self.case_map = {c["id"]: c for c in self.cases}
        self.availability = scan_availability(self.forms, self.cases)

    def video_lesson(self, case_id: str) -> Optional[Dict[str, Any]]:
        return self.video_lessons.get(case_id)

    def forms_for(self, profession: str, symptom: str) -> List[Dict[str, Any]]:
        return [f for f in self.forms if _matches(f, profession, symptom)]

    def step1_form(self, profession: str, symptom: str) -> Optional[Dict[str, Any]]:
        return choose_step1_form(self.forms_for(profession, symptom), profession)

    def step1_bundle(self, profession: str, symptom: str) -> Dict[str, Any]:
        """回傳 Step 1 維度題組；無專屬表單時使用內建通用表並標示。"""
        form = self.step1_form(profession, symptom)
        if form:
            scale = form.get("scale") if isinstance(form.get("scale"), dict) else {}
            return {
                "dimensions": dimensions_from_form(form),
                "form_title": str(form.get("form_title", "")),
                "source_file": str(form.get("_source_file", "")),
                "is_generic": False,
                "weights": form_dimension_weights(form),
                "scale_min": int(scale.get("min", 1) or 1),
                "scale_max": int(scale.get("max", 5) or 5),
            }
        return {
            "dimensions": generic_step1_dimensions(),
            "form_title": "六構面通用核心能力自評（內建）",
            "source_file": "builtin",
            "is_generic": True,
            "weights": None,
            "scale_min": 1,
            "scale_max": 5,
        }

    def objective_form(self, profession: str, symptom: str) -> Optional[Dict[str, Any]]:
        return choose_objective_form(self.forms_for(profession, symptom), profession)

    def rubrics_for(self, profession: str, symptom: str) -> List[Dict[str, Any]]:
        return rubric_forms(self.forms_for(profession, symptom))

    def cases_for(self, symptom: str, profession: str | None = None) -> List[Dict[str, Any]]:
        result = [c for c in self.cases if c["symptom"] == symptom]
        if profession:
            result = [c for c in result if profession in c.get("professions", [])]
        return result

    def case(self, case_id: str) -> Optional[Dict[str, Any]]:
        # 修正 v2：找不到教案時回傳 None，不再靜默 fallback 到 SARC-DT-001
        return self.case_map.get(case_id)
