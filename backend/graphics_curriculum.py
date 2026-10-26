"""Versioned CATIA teaching-practice domain; no clinical data or student imports."""
import copy
import hashlib
import json

VERSION = 'graphics-1.0.0'
SOURCES = [
    {'id': 'P1', 'title': '電腦圖學合作學習學習單（零件建模任務）',
     'url': 'https://docs.google.com/document/d/1iqBYBTsgZSSIbAQZPOB0C3T-5jzLpSdk/edit',
     'scope': '依任務規劃、設計意圖、互換測試、AI使用與教師回饋架構改編；未公開原始教材。'},
    {'id': 'P2', 'title': '電腦圖學合作學習學習單（組合設計任務）',
     'url': 'https://docs.google.com/document/d/1Se84NFo6tVVyiCt8OqGA9ypPOOmg-rOU/edit',
     'scope': '依組合架構、自由度、干涉與維護性之學習活動改編。'},
]
ROLES = ['組長／協調者', '建模策略長／組合架構規劃者', '設計意圖／配合面稽核', '紀錄與反思整理者', 'AI 數位鷹架操作員']
DIMENSIONS = [
    {'id': 'procedure', 'label': '操作與建模技能', 'anchors': ['尚無可判讀證據', '需逐步協助完成', '能獨立完成並記錄', '能穩健修改並說明策略']},
    {'id': 'concept', 'label': '概念與設計意圖', 'anchors': ['尚無可判讀證據', '能描述現象', '能用幾何與約束解釋', '能預測變更並提出驗證']},
    {'id': 'collaboration', 'label': '合作與個別責任', 'anchors': ['尚無可判讀證據', '完成角色工作', '有策略對照及同儕檢核', '能以證據協商並整合策略']},
    {'id': 'reflection', 'label': '反思與 AI 驗證', 'anchors': ['尚無可判讀證據', '記錄問題或AI建議', '檢核建議並解釋採納理由', '能辨識限制並遷移驗證方法']},
]
STEPS = ['自評與個人前測', '理解任務與規劃', '個人建模與證據', '合作互換與 AI 檢核', '無 AI 概念遷移', '反思與教師回饋']
FIELDS = {
    1: [('baseline_reason', '目前最需要協助的概念或操作', 'textarea')],
    2: [('function', '零件／組合的功能與使用情境', 'textarea'),
        ('geometry', '幾何特徵、基準與約束關係', 'textarea'),
        ('plan', '事前步驟：基準 → 指令 → 特徵 → 關鍵尺寸', 'textarea')],
    3: [('actual_steps', '實際操作步驟與原規劃的差異', 'textarea'),
        ('problems', '問題、嘗試解法與結果（至少一個具體例子）', 'textarea'),
        ('design_intent', '關鍵尺寸／約束與設計意圖', 'textarea'),
        ('prediction', '改變一個條件前，先預測哪些特徵會改變', 'textarea')],
    4: [('peer_strategy', '同儕策略差異；個人練習請明示尚未同儕檢核', 'textarea'),
        ('swap_change', '互換／自我擾動測試：原值、改值與預期結果', 'textarea'),
        ('swap_result', '實際結果、失敗原因與證據檔名', 'textarea'),
        ('team_decision', '共同版本的決策與理由；個人練習請標示', 'textarea'),
        ('ai_use', 'AI 使用情形', 'ai'),
        ('ai_prompt', '代表性提問；未使用可填「未使用」', 'textarea'),
        ('ai_adopted', '採納的建議、理由與驗證；無則說明', 'textarea'),
        ('ai_rejected', '未採納的建議與理由；無則說明', 'textarea')],
    5: [('transfer_reason', '用自己的話解釋答案，提出新情境的驗證方式', 'textarea')],
    6: [('skill_reflection', '操作上最大的收穫與仍需補強處', 'textarea'),
        ('concept_reflection', '哪個原理的理解改變？引用本次證據', 'textarea'),
        ('cooperation_reflection', '角色貢獻與合作反思；未合作請明示', 'textarea'),
        ('next_action', '下一輪要刻意改變的策略與檢驗方式', 'textarea')],
}

TASKS = [
    {'id': 'part-bracket', 'stage': '零件建模', 'weeks': '1–6', 'title': '參數化支架：改尺寸，設計意圖仍成立',
     'summary': '以 CATIA 建立自編教學支架，記錄草圖基準、特徵順序及尺寸依存；先預測，再做尺寸擾動與模型互換。',
     'brief': '自編示例：底座80×50×8 mm、立板高40 mm／厚8 mm、兩孔直徑8 mm。孔中心相對中心線對稱，孔距40 mm。請自行明確定義孔所在平面、距邊及接合方式；這是教學草案，不是可直接製造的完整工程圖。',
     'goals': ['區分幾何外觀與設計意圖', '解釋草圖約束及參考幾何', '以尺寸變更驗證特徵穩健性'],
     'perturbation': '把底座長度80改為100 mm；先預測對稱孔、邊距與立板位置是否改變，再記錄更新結果。',
     'source_ids': ['P1'],
     'pre': {'question': '參數模型外觀正確，是否就代表設計意圖正確？', 'options': ['是，外觀正確即可', '否，還需檢查依存、約束及變更結果'], 'answer': 1},
     'transfer': {'question': '另一零件要保持孔相對中心線對稱，修改總長後孔偏移。最適當的下一步？',
                  'options': ['直接拖曳孔直到看起來置中', '檢查孔與基準的依存、約束並做變更測試', '刪除所有尺寸'], 'answer': 1}},
    {'id': 'assembly-slider', 'stage': '組合設計', 'weeks': '7–12', 'title': '滑塊組合：自由度、間隙與可維護性',
     'summary': '在固定座、導軌與滑塊的組合中，說明每項約束消除的運動，並以零件替換測試維護性。',
     'brief': '自編示例：固定導軌沿X軸，滑塊只保留沿X軸平移。自行定義導軌、滑塊幾何及合理間隙；課堂模型不等於已驗證的公差與製造規格。',
     'goals': ['區分約束不足與過度約束', '說明自由度與功能的關係', '以干涉／替換測試檢核組合'],
     'perturbation': '更換同功能、寬度增加2 mm的滑塊，記錄配合、間隙與自由度是否仍符合任務。',
     'source_ids': ['P2'],
     'pre': {'question': '組合可以拖動，是否足以證明自由度符合功能？', 'options': ['是', '否，需核對預期運動與剩餘自由度'], 'answer': 1},
     'transfer': {'question': '新組合的轉軸應僅保留軸向旋轉，卻完全卡死。應先做什麼？',
                  'options': ['檢查是否有約束消除了所需旋轉', '隨機刪除零件', '增加更多固定約束'], 'answer': 0}},
    {'id': 'project-modular', 'stage': '自選專題', 'weeks': '13–18', 'title': '可交接的模組化設計專題',
     'summary': '自選與課程相符的產品，整合零件、組合與設計論證；同儕依文件修改模型並回報結果。',
     'brief': '先由教師確認專題範圍。至少包含兩種零件、一個有功能意義的組合關係、設計變更測試與個人答辯。沒有教師核定即顯示待審，不將平台練習當正式成績。',
     'goals': ['整合程序與概念知識', '以證據辯護設計決策', '在新需求中驗證可維護性'],
     'perturbation': '由同儕提出一項新需求；原作者先預測，再由另一人依文件修改並記錄成功或失敗。',
     'source_ids': ['P1', 'P2'],
     'pre': {'question': '共同作品能代表每位組員都理解設計嗎？', 'options': ['能', '不能，還需個人證據與說明'], 'answer': 1},
     'transfer': {'question': '接手者無法在新需求下更新模型，哪項最能支持改善？',
                  'options': ['只補更多外觀截圖', '補基準依存、關鍵參數、變更測試及失敗說明', '把尺寸全部固定'], 'answer': 1}},
]


def snapshot(task_id):
    task = next((t for t in TASKS if t['id'] == task_id), None)
    if not task:
        raise ValueError('未知教學任務')
    return make_snapshot(task, VERSION, '平台改編教學草案，待授課教師核定')


def make_snapshot(task, version, status):
    data = {'version': version, 'task': copy.deepcopy(task), 'rubric': copy.deepcopy(DIMENSIONS),
            'sources': copy.deepcopy(SOURCES), 'status': status}
    data['hash'] = hashlib.sha256(json.dumps(data, ensure_ascii=False, sort_keys=True).encode()).hexdigest()
    return data


def public_task(task):
    # Questions and keys appear only at their assessment stage, never in catalog.
    return {k: copy.deepcopy(v) for k, v in task.items() if k not in ('pre', 'transfer')}


def catalog():
    return {'version': VERSION, 'title': '知其然・知其所以然', 'subtitle': '電腦圖學合作學習與設計意圖訓練平台',
            'tasks': [public_task(t) for t in TASKS], 'roles': ROLES, 'dimensions': DIMENSIONS, 'steps': STEPS,
            'sources': SOURCES, 'notice': '個人證據、合作成果、自評與教師核定分開保存。未解析 CATIA 原生特徵樹，不宣稱自動驗證幾何或正式能力。'}


def scaffold(task, level, question):
    leads = {1: '先指出目前停在哪個步驟，寫出已知尺寸、基準與畫面訊息。',
             2: '把問題拆為基準、特徵、約束三部分；選一項假設做最小變更。',
             3: '先預測變更結果，再記錄實測；比較預測與結果，解釋差異。',
             4: '提出兩種策略，對照可維護性、自由度與依存風險，找反例驗證。',
             5: '請用證據答辯：你的解釋何時失效？同儕如何重現？新需求下會如何修正？'}
    return f"{leads[level]}\n本任務檢核：{task['perturbation']}\n請附具體操作證據；提示不代表模型已通過檢查。"
