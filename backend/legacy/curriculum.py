from __future__ import annotations

from copy import deepcopy
from typing import Any, Dict, List

SARCOPENIA = "肌少症"


PROFESSION_LABELS = {
    "DT": "營養師",
    "RT": "醫事放射師",
    "PT": "物理治療師",
}


SIX_STEP_ARCHITECTURE = [
    {
        "step": 1,
        "name": "核心能力自評",
        "purpose": "依職種載入不同自評表，評估知識、技能、態度與核心能力，產生 Level 1-5 與弱項構面。",
    },
    {
        "step": 2,
        "name": "多元教案推薦",
        "purpose": "依自評弱項推薦必讀教科書內容、知識卡、情境互動圖與職種專屬教案。",
    },
    {
        "step": 3,
        "name": "分級互動影片",
        "purpose": "依職種與 Level 1-5 產生實際互動影片腳本、觀察任務與錯誤決策後果。",
    },
    {
        "step": 4,
        "name": "Ollama Gemma 虛擬人互動",
        "purpose": "依 Level 調整虛擬人提示密度、壓力與追問深度，記錄聊天與決策歷程。",
    },
    {
        "step": 5,
        "name": "標準測驗",
        "purpose": "根據自評、教案、互動紀錄與聊天內容，提供職種專屬標準測驗題目。",
    },
    {
        "step": 6,
        "name": "整合回饋報告",
        "purpose": "整合自評、學習歷程、互動紀錄、測驗結果，輸出分數、建議、雷達圖與報告。",
    },
]


LEVEL_RULES = {
    1: {
        "name": "Level 1｜老師導引",
        "video_style": "教師示範與逐步旁白，畫面提示明確，讓學員建立基本流程。",
        "virtual_human": "標準化病人反應溫和，回覆後加入老師提示，明確指出下一步。",
        "assessment_focus": "能否完成基本安全流程與核心資料蒐集。",
    },
    2: {
        "name": "Level 2｜半導引練習",
        "video_style": "保留關鍵提示，但要求學員自行說出部分判斷依據。",
        "virtual_human": "病人或團隊成員會反問，必要時提供少量線索。",
        "assessment_focus": "能否在提示下做出合理判斷與溝通。",
    },
    3: {
        "name": "Level 3｜標準情境演練",
        "video_style": "真實門診/檢查/治療情境，提示適中，要求完整流程。",
        "virtual_human": "自然回應，同理與安全時提供新線索，忽略重點時追問。",
        "assessment_focus": "能否獨立完成基本臨床任務。",
    },
    4: {
        "name": "Level 4｜獨立執行挑戰",
        "video_style": "加入時間壓力、病人質疑或團隊交班，提示減少。",
        "virtual_human": "要求具體計畫、追蹤指標與跨團隊分工。",
        "assessment_focus": "能否在壓力下維持安全、同理與專業判斷。",
    },
    5: {
        "name": "Level 5｜專業指導互動",
        "video_style": "高擬真專業情境，學員需示範並能指導他人。",
        "virtual_human": "以資深臨床督導或同儕方式追問證據、優先順序、風險與整合策略。",
        "assessment_focus": "能否示範高品質照護、指導同儕並整合團隊。",
    },
}


CURRICULA: Dict[str, Dict[str, Any]] = {
    "DT": {
        "id": "SARC-DT-CURR-001",
        "title": "營養師肌少症門診營養照護",
        "source_documents": ["營養師-門診病人營養照護_肌少症.pdf"],
        "case_context": "68歲劉小姐，160公分、44.3公斤、BMI約17.3，DXA追蹤後確診肌少症；自認有喝牛奶、吃肉與排骨，仍質疑為何變差。",
        "competencies": {
            "core": [
                "營養專業知識：應用實證臨床營養知識提供建議。",
                "營養照護能力：完成資料收集、營養評估、營養診斷、介入、監測與評值。",
                "人際溝通：以病人為中心進行營養諮詢與衛教。",
                "團隊合作：將營養照護資訊轉化為醫護團隊可理解的訊息。",
                "專業素養：遵循法規與倫理，以病人最佳利益為考量。",
                "工作中學習：持續精進醫療營養與膳食供應管理知識。"
            ],
            "knowledge": [
                "肌少症營養介入需同時評估總熱量、蛋白質品質、維生素D、阻力運動與追蹤。",
                "低BMI可能代表總熱量不足，會限制肌肉生成。",
                "病人說有吃肉不等於攝取足夠，需確認份量、頻率、品質與時間點。"
            ],
            "skills": [
                "核對身份、確認就診需求、收集客觀資訊。",
                "完成飲食與生活型態訪談，判定營養診斷。",
                "共同擬定飲食目標，提供個案飲食計畫、營養諮詢與衛教。",
                "完成營養病歷紀錄並以SBAR與團隊溝通。"
            ],
            "attitudes": [
                "先同理病人努力，再共同檢視資料。",
                "避免責備、羞辱或過度限制飲食。",
                "尊重飲食偏好、家庭支持、經濟可近性與依從性。"
            ],
        },
        "textbook": {
            "title": "必讀：肌少症營養照護流程",
            "sections": [
                "1. 先確認身份與就診需求，再收集身高、體重、BMI、DXA結果、共病與用藥。",
                "2. 飲食訪談需追問一日飲食、蛋白質來源、份量、正餐規律、甜飲與運動後補充。",
                "3. 營養診斷需連結低體重、熱量不足、蛋白質品質與肌肉生成限制。",
                "4. 介入計畫需與病人共同訂定SMART目標，並安排監測體重、攝取量、疲勞與功能表現。",
                "5. 病歷紀錄需包含營養診斷、介入內容、衛教重點、病人回饋與追蹤指標。"
            ],
        },
        "knowledge_cards": [
            {"title": "低BMI不是小事", "body": "BMI約17.3代表體重過輕風險，若總熱量不足，即使有吃蛋白質也可能難以增加肌肉。"},
            {"title": "我有吃肉，需要量化", "body": "追問份量、頻率、種類、烹調方式與運動後補充，才能形成可追蹤的營養診斷。"},
            {"title": "Teach-back", "body": "不要只問『懂了嗎』，要請病人用自己的話說出下週飲食與追蹤做法。"},
        ],
        "interaction_map": [
            "病人質疑檢查與努力無效",
            "營養師同理並追問飲食份量",
            "判斷低體重與熱量/蛋白質不足",
            "與物理治療師整合阻力運動後補充",
            "共同設定SMART目標並Teach-back",
        ],
        "video_level_tasks": {
            1: "教師示範如何從同理開場進入24小時飲食回顧。",
            2: "病人提供模糊飲食描述，學員需在提示下追問份量與頻率。",
            3: "完整門診營養諮詢，學員需完成營養診斷與衛教。",
            4: "病人低信賴且時間有限，學員需快速建立共識與追蹤計畫。",
            5: "學員需向團隊示範營養照護決策，並回應資深同儕追問。"
        },
        "virtual_human": {
            "primary_role": "低信賴門診病人",
            "opening": "我都有喝牛奶、吃肉和排骨，為什麼還肌少症？是不是檢查不準？",
            "level5_challenge": "請說明你如何判斷是總熱量不足、蛋白質不足，還是運動後補充時機不對？你要追蹤哪些指標？"
        },
        "quiz": [
            {
                "id": "DT-STD-Q1",
                "question": "劉小姐BMI約17.3且DXA確診肌少症，營養師最優先的判斷是？",
                "options": ["只需增加蛋白粉", "可能有總熱量不足並影響肌肉生成，需同步評估熱量與蛋白質", "只要多散步", "不需營養介入"],
                "answer": "可能有總熱量不足並影響肌肉生成，需同步評估熱量與蛋白質",
                "dimension": "CJ",
                "explain": "低BMI代表體重過輕風險，肌少症營養照護需同時評估總熱量與蛋白質。"
            },
            {
                "id": "DT-STD-Q2",
                "question": "病人說『我有喝牛奶、吃肉、吃排骨』，下一步最合宜的是？",
                "options": ["直接相信足夠", "追問份量、頻率、種類、正餐規律與運動後補充", "叫她完全不要喝珍奶", "只叫她吃更多"],
                "answer": "追問份量、頻率、種類、正餐規律與運動後補充",
                "dimension": "PC",
                "explain": "營養評估需把描述轉成可計算與可追蹤的資料。"
            },
            {
                "id": "DT-STD-Q3",
                "question": "最符合病人中心營養衛教的是？",
                "options": ["你照做就好", "先肯定努力，再共同檢視可調整處並請病人回述計畫", "直接禁止所有甜飲", "只給衛教單"],
                "answer": "先肯定努力，再共同檢視可調整處並請病人回述計畫",
                "dimension": "COM",
                "explain": "低信賴情境需先建立合作關係並使用Teach-back。"
            },
        ],
    },
    "RT": {
        "id": "SARC-RT-CURR-001",
        "title": "醫事放射師DXA與骨質密度檢查照護",
        "source_documents": ["醫事放射肌無力.docx"],
        "case_context": "68歲劉小姐接受追蹤DXA後確診肌少症，物理治療師詢問5月與8月報告差異、ASMI與肢段肌肉量。",
        "competencies": {
            "core": [
                "醫學影像及放射科學知識：正確調整姿勢、角度與固定，確保影像品質。",
                "醫病關係及團隊溝通：與病人、陪同者及團隊有效溝通。",
                "病人照護：依醫囑安全完成檢查，特殊情境與異常狀況處置得宜。",
                "病人安全與任務交接：落實病人辨識、感染管制、輻射安全與交接。",
                "跨領域團隊合作：將影像檢查資訊銜接至物理治療與營養照護。",
                "專業素養：遵守倫理，以病人最佳利益為優先。"
            ],
            "knowledge": [
                "DXA可提供骨質密度、四肢骨骼肌量與ASMI等團隊照護參考。",
                "放射師可說明檢查資訊與報告項目，但診斷解釋需回到醫師。",
                "右下肢與左側肌肉量差異可支持物理治療師進一步做功能評估。"
            ],
            "skills": [
                "OPA1：醫囑確認、病人辨識、流程說明、感染管制、輻射安全。",
                "OPA2：擺位、參數設定、依醫囑執行、病人安全與異常處理。",
                "OPA3：注意事項、環境清潔、設備維護、影像品管與後處理。",
                "與物理治療師確認病歷號、檢查日期、ASMI變化與骨密度資訊。"
            ],
            "attitudes": [
                "不以『報告就是這樣』中斷團隊溝通。",
                "尊重病人疑慮並守住專業界線。",
                "主動提供有助於全人照護的影像資訊。"
            ],
        },
        "textbook": {
            "title": "必讀：DXA檢查與跨專業溝通流程",
            "sections": [
                "1. 檢查前需確認醫囑、病人身分、檢查流程、感染管制與輻射安全。",
                "2. 檢查中需注意擺位、固定、參數設定與病人安全。",
                "3. 檢查後需完成注意事項、環境清潔、設備維護、影像品管與後處理。",
                "4. 團隊詢問報告差異時，先確認病歷號、日期與問題焦點，再說明可提供的報告資訊。",
                "5. 若涉及診斷或治療判斷，需建議由醫師進一步解釋。"
            ],
        },
        "knowledge_cards": [
            {"title": "先確認再回覆", "body": "團隊成員詢問報告差異時，先確認病人、病歷號、檢查日期與問題項目。"},
            {"title": "ASMI與肢段差異", "body": "ASMI低於建議值或右下肢明顯落差，可提供物理治療師作為功能評估線索。"},
            {"title": "專業界線", "body": "放射師可說明檢查與報告資訊，但診斷與治療解釋需由醫師主責。"},
        ],
        "interaction_map": [
            "物理治療師詢問DXA差異",
            "放射師確認病人與報告",
            "說明ASMI、肢段肌肉量與BMD資訊",
            "提醒骨鬆與團隊照護風險",
            "必要時轉請醫師解釋診斷",
        ],
        "video_level_tasks": {
            1: "教師示範OPA1-OPA3完整流程與安全提醒。",
            2: "學員在提示下回應物理治療師對DXA差異的詢問。",
            3: "完整演練病人檢查與團隊報告溝通。",
            4: "團隊成員帶著質疑詢問報告，學員需有效釐清並守住界線。",
            5: "學員需以專業方式協調放射、復健、營養資訊，並回應資深同儕追問。"
        },
        "virtual_human": {
            "primary_role": "物理治療師同仁",
            "opening": "放射師您好，我想確認劉小姐5月與8月DXA報告，ASMI變化好像很大？",
            "level5_challenge": "請說明你能提供哪些報告資訊，哪些需要醫師解釋？這個結果如何幫助我安排功能評估？"
        },
        "quiz": [
            {
                "id": "RT-STD-Q1",
                "question": "物理治療師詢問DXA報告差異時，放射師最合宜的第一步是？",
                "options": ["直接說報告沒問題", "確認病人、病歷號、檢查日期與詢問項目", "請對方不要問", "直接做診斷"],
                "answer": "確認病人、病歷號、檢查日期與詢問項目",
                "dimension": "TC",
                "explain": "有效團隊溝通需先確認對象與問題焦點。"
            },
            {
                "id": "RT-STD-Q2",
                "question": "DXA檢查前準備不包含下列哪一項？",
                "options": ["確認醫囑與病人辨識", "檢查流程說明", "感染管制與輻射安全", "開立運動處方"],
                "answer": "開立運動處方",
                "dimension": "PC",
                "explain": "運動處方屬物理治療等專業任務，非放射檢查前準備。"
            },
            {
                "id": "RT-STD-Q3",
                "question": "關於專業界線，下列何者最正確？",
                "options": ["放射師可說明檢查資訊，但診斷解釋需由醫師主責", "放射師應直接告訴病人治療方式", "團隊詢問時不可提供任何資訊", "影像品管與病人安全無關"],
                "answer": "放射師可說明檢查資訊，但診斷解釋需由醫師主責",
                "dimension": "SAFE",
                "explain": "專業溝通需提供有用資訊，同時守住診斷與治療界線。"
            },
        ],
    },
    "PT": {
        "id": "SARC-PT-CURR-001",
        "title": "物理治療師肌少症功能評估與運動處方",
        "source_documents": ["物理治療學員—肌少症照護的核心能力.pdf"],
        "case_context": "68歲劉小姐，BMI約17.3，DXA顯示肌少症，主訴已有散步仍覺得無力與功能退化。",
        "competencies": {
            "core": [
                "肌少症臨床評估與診斷支持能力。",
                "運動處方與功能促進能力。",
                "風險管理與安全照護能力。",
                "跨專業合作與照護整合能力。",
                "以病人為中心的溝通與教育能力。"
            ],
            "knowledge": [
                "肌少症定義、原發性/次發性、急性/慢性與老年衰弱概念。",
                "握力、5次坐站、步速、TUG、ADL/IADL與活動耐受度評估。",
                "阻力訓練與功能性訓練為核心，營養與維生素D需同步考量。"
            ],
            "skills": [
                "正確執行並解釋肌力、平衡、步態與功能性測試。",
                "根據評估建立問題列表與治療優先順序。",
                "設計阻力訓練、功能訓練與居家運動，並依疲勞、疼痛、共病調整。",
                "監測頭暈、呼吸困難、跌倒、心血管與骨折風險。"
            ],
            "attitudes": [
                "尊重高齡者生活習慣、文化與目標。",
                "不以年齡作為放棄積極介入的理由。",
                "知道能力界線，適時尋求指導並主動與團隊合作。"
            ],
        },
        "textbook": {
            "title": "必讀：肌少症物理治療評估與運動介入",
            "sections": [
                "1. 肌少症需同時看肌肉量、肌力與身體功能，不只看體重或散步量。",
                "2. 常用評估包含握力、5次坐站、步速、TUG、ADL/IADL與活動耐受度。",
                "3. 介入核心是阻力訓練與功能性訓練，並需與營養補充整合。",
                "4. 運動中需監測疲勞、疼痛、頭暈、呼吸困難與跌倒風險。",
                "5. 治療目標需連結病人的日常生活功能與可持續行為。"
            ],
        },
        "knowledge_cards": [
            {"title": "散步不等於阻力訓練", "body": "散步有助心肺與活動量，但肌少症改善通常需要漸進式阻力訓練。"},
            {"title": "5次坐站", "body": "5 Times Sit-to-Stand 可快速反映下肢肌力與功能風險。"},
            {"title": "運動安全", "body": "疲勞、疼痛、頭暈、呼吸困難、跌倒與骨折風險都需要即時監測。"},
        ],
        "interaction_map": [
            "確認DXA與放射報告資訊",
            "執行握力/5次坐站/步速或TUG",
            "建立問題列表與優先順序",
            "設計阻力與功能訓練",
            "整合營養補充與居家追蹤",
        ],
        "video_level_tasks": {
            1: "教師示範5次坐站與阻力訓練安全教學。",
            2: "學員在提示下選擇評估工具並解釋結果。",
            3: "完整演練功能評估、運動處方與病人衛教。",
            4: "病人疲勞且低信賴，學員需調整處方並維持動機。",
            5: "學員需向團隊示範高風險個案的運動安全決策與跨專業整合。"
        },
        "virtual_human": {
            "primary_role": "低信賴復健病人",
            "opening": "我明明都有散步，也有吃肉，為什麼還是變差？你是不是要叫我做很累的運動？",
            "level5_challenge": "請說明你如何從功能測試決定訓練強度，若我頭暈或膝痛，你會如何調整？"
        },
        "quiz": [
            {
                "id": "PT-STD-Q1",
                "question": "肌少症物理治療評估最不應只依賴哪一項？",
                "options": ["肌力測試", "5次坐站", "病人說有散步", "步速或TUG"],
                "answer": "病人說有散步",
                "dimension": "CJ",
                "explain": "散步描述不足以判斷肌力與功能狀態，需結合客觀功能測試。"
            },
            {
                "id": "PT-STD-Q2",
                "question": "肌少症運動介入的核心通常是？",
                "options": ["只散步", "阻力訓練與功能性訓練", "完全休息", "只做伸展"],
                "answer": "阻力訓練與功能性訓練",
                "dimension": "PC",
                "explain": "阻力訓練與功能性訓練是改善肌力與功能的重要策略。"
            },
            {
                "id": "PT-STD-Q3",
                "question": "運動中出現頭暈、呼吸困難或跌倒風險時，最合宜的是？",
                "options": ["繼續完成原本強度", "即時修正運動並視需要回報或轉介", "請病人忍耐", "只記錄不處理"],
                "answer": "即時修正運動並視需要回報或轉介",
                "dimension": "SAFE",
                "explain": "物理治療師需監測安全風險並即時調整。"
            },
        ],
    },
}


def level_from_text(level_text: str | None) -> int:
    text = level_text or ""
    for level in range(1, 6):
        if f"Level {level}" in text or f"Level{level}" in text:
            return level
    return 3


def get_curriculum(profession: str) -> Dict[str, Any] | None:
    return CURRICULA.get(profession)


def get_curricula() -> Dict[str, Dict[str, Any]]:
    return deepcopy(CURRICULA)


def get_level_rule(level_text_or_number: str | int | None) -> Dict[str, str]:
    if isinstance(level_text_or_number, int):
        level = level_text_or_number
    else:
        level = level_from_text(level_text_or_number)
    return deepcopy(LEVEL_RULES.get(level, LEVEL_RULES[3]))


def get_curriculum_quiz(profession: str, weakest_dimensions: List[str] | None = None) -> List[Dict[str, Any]]:
    curriculum = get_curriculum(profession)
    if not curriculum:
        return []
    quiz = deepcopy(curriculum["quiz"])
    weakest = set(weakest_dimensions or [])
    if weakest:
        quiz.sort(key=lambda q: 0 if q.get("dimension") in weakest else 1)
    return quiz


def curriculum_to_case(profession: str, curriculum: Dict[str, Any]) -> Dict[str, Any]:
    label = PROFESSION_LABELS.get(profession, profession)
    textbook_sections = curriculum["textbook"]["sections"]
    cards = curriculum["knowledge_cards"]
    interaction = curriculum["interaction_map"]
    level_tasks = curriculum["video_level_tasks"]
    virtual_human = curriculum["virtual_human"]

    storyboard = [
        {
            "scene": "必讀教科書導入",
            "visual": f"{label}查看肌少症職種任務與核心能力。",
            "voice": textbook_sections[0],
            "cue": "確認職種任務邊界與安全流程。",
        },
        {
            "scene": "知識卡快問快答",
            "visual": "畫面顯示三張知識卡，學員需說出臨床意義。",
            "voice": "、".join(card["title"] for card in cards),
            "cue": "把知識卡轉成臨床行動。",
        },
        {
            "scene": "情境互動圖",
            "visual": "流程圖顯示： " + " → ".join(interaction),
            "voice": "學員需依序完成關鍵互動節點。",
            "cue": "練習判斷、溝通、團隊整合與安全。",
        },
        {
            "scene": "Level 1-5 實際互動影片",
            "visual": "依學員Level切換提示密度與臨床壓力。",
            "voice": " / ".join(f"L{level}: {task}" for level, task in level_tasks.items()),
            "cue": "Level越高，提示越少、專業追問越深。",
        },
        {
            "scene": "Ollama Gemma 虛擬人",
            "visual": f"虛擬人角色：{virtual_human['primary_role']}。",
            "voice": virtual_human["opening"],
            "cue": "依Level調整病人、家屬或團隊成員的互動方式。",
        },
    ]

    kdp = [
        {
            "id": f"{profession}-CURR-KDP1",
            "phase": "開場與資料釐清",
            "prompt": virtual_human["opening"],
            "options": [
                {"label": "A", "text": "直接否定對方疑問，要求照做。", "score": 0, "dimension": "COM", "feedback": "缺乏同理與資料釐清，容易降低信任。"},
                {"label": "B", "text": "先同理，再確認資料與對方最在意的問題。", "score": 2, "dimension": "COM", "feedback": "能建立合作關係並展開評估。"},
                {"label": "C", "text": "只說等一下再看，先進入自己的流程。", "score": 1, "dimension": "PC", "feedback": "有流程但未回應疑慮，建議補上同理與焦點釐清。"},
            ],
        },
        {
            "id": f"{profession}-CURR-KDP2",
            "phase": "職種核心任務",
            "prompt": f"請依{label}職責完成此情境最重要的下一步。",
            "options": [
                {"label": "A", "text": curriculum["competencies"]["skills"][0], "score": 2, "dimension": "PC", "feedback": "符合職種核心流程。"},
                {"label": "B", "text": "只做一般安慰，不進行職種專業評估。", "score": 0, "dimension": "CJ", "feedback": "情緒支持不足以完成專業任務。"},
                {"label": "C", "text": "跳到其他職種任務，忽略自己的專業邊界。", "score": 1, "dimension": "SAFE", "feedback": "需守住職種界線並啟動團隊合作。"},
            ],
        },
        {
            "id": f"{profession}-CURR-KDP3",
            "phase": "團隊整合與追蹤",
            "prompt": "完成初步處置後，下一步如何與團隊銜接？",
            "options": [
                {"label": "A", "text": "用SBAR或結構化方式交接重點、風險與追蹤指標。", "score": 2, "dimension": "TC", "feedback": "可形成閉環照護。"},
                {"label": "B", "text": "只記在心裡，等別人來問再說。", "score": 0, "dimension": "TC", "feedback": "缺乏主動交接，容易中斷照護。"},
                {"label": "C", "text": "只交代病人自己回家注意。", "score": 1, "dimension": "HC", "feedback": "病人衛教重要，但仍需團隊與追蹤計畫。"},
            ],
        },
    ]

    return {
        "id": curriculum["id"],
        "title": curriculum["title"],
        "symptom": SARCOPENIA,
        "category": f"{label}／肌少症／六步驟整合課程",
        "difficulty": "Level 1–5",
        "professions": [profession],
        "source_file": "、".join(curriculum["source_documents"]),
        "summary": curriculum["case_context"],
        "patient": curriculum["case_context"],
        "goals": (
            curriculum["competencies"]["core"][:2]
            + curriculum["competencies"]["skills"][:2]
            + ["依Level完成虛擬人互動與標準測驗"]
        ),
        "pre_knowledge": curriculum["competencies"]["knowledge"] + textbook_sections[:2],
        "storyboard": storyboard,
        "kdp": kdp,
        "quiz": deepcopy(curriculum["quiz"]),
        "rubric": (
            curriculum["competencies"]["core"]
            + curriculum["competencies"]["skills"]
            + curriculum["competencies"]["attitudes"]
        ),
        "tags": [profession, label, "肌少症", "六步驟", "多元教案"],
        "curriculum_version": "sarcopenia_three_professions_v1",
        "curriculum": deepcopy(curriculum),
    }


def curriculum_cases() -> List[Dict[str, Any]]:
    return [curriculum_to_case(prof, data) for prof, data in CURRICULA.items()]
