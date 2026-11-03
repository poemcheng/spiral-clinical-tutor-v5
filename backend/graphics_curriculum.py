"""Versioned CATIA teaching-practice domain; no clinical data or student imports."""
import copy
import hashlib
import json

VERSION = 'graphics-1.1.0'
SOURCES = [
    {'id': 'P1', 'title': '電腦圖學合作學習學習單（零件建模任務）',
     'url': 'https://docs.google.com/document/d/1iqBYBTsgZSSIbAQZPOB0C3T-5jzLpSdk/edit',
     'scope': '依任務規劃、設計意圖、互換測試、AI使用與教師回饋架構改編；未公開原始教材。'},
    {'id': 'P2', 'title': '電腦圖學合作學習學習單（組合設計任務）',
     'url': 'https://docs.google.com/document/d/1Se84NFo6tVVyiCt8OqGA9ypPOOmg-rOU/edit',
     'scope': '依組合架構、自由度、干涉與維護性之學習活動改編。'},
    {'id': 'CATIA-PDG', 'title': 'Dassault Systèmes｜CATIA Part Design 2',
     'url': 'https://3dswym.3dexperience.3ds.com/wiki/catia-user-community/catia-part-design-2-pdg_wUklCUysT4GXL-WVU4ZrWQ',
     'scope': '零件設計工作台與特徵建模概念參考。本站尺寸、題目與教學模型為另行設計，非原廠認證試題。'},
    {'id': 'CATIA-ASD', 'title': 'Dassault Systèmes｜CATIA Assembly Design 2',
     'url': 'https://3dswym.3dexperience.3ds.com/wiki/catia-user-community/catia-assembly-design-2-asd_Lx2jW-oPR9qcb3gZNgrKhw',
     'scope': '組合架構、元件與約束概念參考；指令名稱依 CATIA V5 語系及授權可能不同。'},
    {'id': 'CATIA-DRAFT', 'title': 'Dassault Systèmes EDU｜Learn Advance – Drafting',
     'url': 'https://3dswym.3dexperience.3ds.com/post/3dexperience-edu-students/learn-advance-%E2%80%93-drafting_qLRgBmRGR1-79RXAAeiTPg',
     'scope': '投影視圖、剖視圖與尺寸標註之學習方向參考；課堂圖面仍由教師核對。'},
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
    {
        'id': 'part-bracket', 'stage': '零件建模', 'weeks': '1–6',
        'title': 'CATIA 零件建模｜參數化 L 型支架',
        'summary': '從完全約束草圖開始，以 Pad、Hole 與 Mirror 完成有明確尺寸的 L 型支架；用長度變更驗證孔位與立板的設計意圖。',
        'brief': '使用 CATIA V5、mm。全域 X 為底座長度、Y 為深度、Z 向上；原點為底座前邊的長度中點。底座範圍 X=−40～40、Y=0～50、Z=0～8。立板範圍 X=−40～40、Y=42～50、Z=8～48，與底座合成單一實體。底座兩個 Ø8 通孔沿 Z 方向，中心為 (−20,20) 與 (20,20)。立板一個 Ø10 通孔沿 Y 方向，中心 X=0、Z=28。所有孔皆貫穿各自板厚。這是尺寸與特徵練習，未指定製造公差、材料或承載能力。',
        'goals': ['以尺寸與幾何約束完成可判讀的草圖，而非以 Fix 掩蓋未定義關係', '說明 Pad、Hole、Mirror 的用途與特徵依存', '在長度變更後量測孔距、邊距與立板尺寸'],
        'workbenches': ['Sketcher（草圖）', 'Part Design（零件設計）'],
        'prerequisites': ['能開啟與儲存 CATPart，操作旋轉、平移及縮放', '認識 XY／YZ／XZ 基準面與 mm 單位'],
        'parameters': [
            {'name': '底座長 L', 'value': '80 mm；變更版 100 mm', 'reference': '以 YZ 面對稱，X=−L/2～L/2'},
            {'name': '底座深度與厚度', 'value': '50 mm、8 mm', 'reference': 'Y=0～50；Z=0～8'},
            {'name': '立板', 'value': '長 L、厚8、高40 mm', 'reference': 'Y=42～50；Z=8～48；高度從底座頂面算起'},
            {'name': '底座通孔', 'value': '2×Ø8；孔距40 mm', 'reference': '沿 Z；X=±20、Y=20；以 YZ 面鏡射'},
            {'name': '立板通孔', 'value': '1×Ø10', 'reference': '沿 Y；X=0、Z=28；由立板前面 Y=42 貫穿'},
        ],
        'operation_steps': [
            '新建 Bracket.CATPart。在 XY 面畫矩形，定義長80、深50、前邊 Y=0，並使長度關於 YZ 面對稱；檢查草圖剩餘自由度。',
            '以 Pad（凸台）向 +Z 拉伸8，命名 Pad_Base。在 Z=8 頂面畫立板矩形，定義 X=−40～40、Y=42～50，向 +Z Pad 40，命名 Pad_Wall。',
            '在底座頂面以 Hole（孔）建立中心 X=20、Y=20 的 Ø8 貫穿孔；檢查方向朝 −Z，以 Mirror（鏡射）關於 YZ 面建立另一孔。',
            '在立板前面 Y=42 建立中心 X=0、Z=28 的 Ø10 貫穿孔，方向朝 +Y；更新並確認單一連通實體。',
            '保留原版，另存 Bracket_L100.CATPart；將底座與立板的共同長度改為100。可用命名參數／公式，或明確記錄兩項尺寸的同步修改，勿拖曳補正孔位。',
            '更新後量測兩孔中心、孔距與左右端邊距，保存前後截圖與特徵樹；交給同儕重開並檢查。',
        ],
        'deliverables': ['Bracket.CATPart 與 Bracket_L100.CATPart', '草圖約束、特徵樹、底座雙孔與立板孔的截圖', '80→100 mm 前後尺寸量測表，含檔名與更新結果'],
        'acceptance': ['底座與立板尺寸、三個通孔的中心與方向符合題目', '底座草圖無非預期自由度，特徵樹更新無錯誤', 'L=100 時底座與立板均加長，底座孔距仍為40且關於 YZ 面對稱', '同儕能從交付檔重現變更，不只提供外觀截圖'],
        'weekly_plan': [{'weeks': '1–2', 'focus': '座標、讀圖、完全約束草圖與前測'}, {'weeks': '3–4', 'focus': 'Pad／Hole／Mirror，完成原始支架與操作紀錄'}, {'weeks': '5–6', 'focus': 'L=100 變更、同儕重開、遷移作答與反思'}],
        'perturbation': '先預測 L=80→100 mm 時兩個底座孔的中心 X、孔距、左右端邊距與立板長度，再在另存副本中更新；以實際量測值對照預測。',
        'source_ids': ['P1', 'CATIA-PDG'],
        'pre': {'question': '在 Sketcher 畫出長80、深50的矩形，只標註長與深，未連結原點或基準。矩形仍可整體拖動，最適當的處理是？', 'options': ['尺寸已有80與50，不必處理', '補上與原點／基準的定位關係，再檢查剩餘自由度', '離開草圖後把 Pad 厚度加大', '刪除長度尺寸後以滑鼠調整'], 'answer': 1},
        'transfer': {'question': '新零件的總長會變動，但兩孔必須始終相對零件中心對稱且孔距固定50 mm。應優先建立哪種關係？', 'options': ['兩孔都固定距左端20 mm', '以零件中心基準建立對稱關係，並控制兩孔間距50 mm', '只鎖住孔的畫面位置', '每次改總長後手動拖曳兩孔'], 'answer': 1},
        'prompts': {
            '1': [
                {'id': 'bracket_axes', 'prompt': '依本題座標，指出底座草圖應畫在哪個基準面、Pad 應朝哪個方向；說明「總高48」與「立板拉伸40」為何不同。', 'placeholder': '基準面：…；方向：…；兩個高度的起算位置：…'},
                {'id': 'bracket_constraints', 'prompt': '矩形長、深都已標尺寸卻仍能整體移動，表示哪一種關係尚未定義？請寫出一個可加入的定位約束，並說明如何確認。', 'placeholder': '缺少的關係：…；約束：…；確認方法：…'},
            ],
            '2': [
                {'id': 'bracket_feature_plan', 'prompt': '按順序列出本支架的草圖平面、Pad／Hole／Mirror 指令、尺寸與方向，並標出你會保留的共同長度參數。', 'placeholder': '1. 平面／指令／尺寸／方向…；共同參數與依存：…'},
                {'id': 'bracket_hole_reference', 'prompt': '底座第一孔為何以 X=20、Y=20 定位，再關於 YZ 面鏡射？請比較它與「兩孔各自距左端定位」在長度變更時的差別。', 'placeholder': '基準選擇：…；兩種策略比較：…'},
            ],
            '3': [
                {'id': 'bracket_measurements', 'prompt': '完成 L=80 原版後，填入實測底座長／深／厚、立板拉伸高度、兩底座孔中心與孔距、立板孔中心；逐項寫出量測或約束截圖檔名。', 'placeholder': '項目｜題目值｜實測值｜證據檔名；至少包含所有指定尺寸與三孔位置。'},
                {'id': 'bracket_change_prediction', 'prompt': '在尚未修改模型前，預測 L=100 時兩底座孔中心的 X、孔距、左右孔中心到各自最近端面的距離、立板長度。寫出計算或依存理由。', 'placeholder': '預測值：…；計算／依存理由：…；目前尚未執行變更。'},
            ],
            '4': [
                {'id': 'bracket_peer_update', 'prompt': '請同儕只依你的交接說明把 L 改成100，列出實際修改的參數／特徵、更新結果與量測值；個人練習則明確記錄自我重開測試。', 'placeholder': '操作者：…；檔案：…；修改項目：…；預測／實測差異：…'},
                {'id': 'bracket_failure_diagnosis', 'prompt': '若改長後立板仍為80或孔不再對稱，應先檢查哪個草圖或依存？請依自己的模型指出一個具名特徵，寫下修正與重新驗證方式。', 'placeholder': '特徵名稱：…；原因假設：…；修正：…；驗證結果／證據：…'},
            ],
            '5': [
                {'id': 'bracket_transfer_numeric', 'prompt': '新題：一塊板的 X=0～140，兩孔距50且關於板的長度中心對稱。請算出兩孔中心 X；若總長改為160，兩孔中心 X 應是多少？不使用 AI。', 'placeholder': 'L=140 的兩孔 X：…；L=160 的兩孔 X：…；計算：…'},
                {'id': 'bracket_transfer_method', 'prompt': '新題：孔距必須隨總長保持固定比例，而不是固定數值。你會改變哪些參數關係？請提出一次測試值與預期檢查項目，不使用 AI。', 'placeholder': '新依存：…；測試條件：…；預期檢查：…'},
            ],
            '6': [
                {'id': 'bracket_evidence_defense', 'prompt': '選一張約束或特徵樹截圖，說明你從「形狀看起來正確」改為「能證明設計意圖正確」的依據。請引用檔名與實測值。', 'placeholder': '證據：…；原先想法：…；現在的判斷與數值：…'},
                {'id': 'bracket_next_trial', 'prompt': '下一輪若把孔距改為50，你會先檢查哪些邊距與板面限制？分別寫出個人應負責的操作與同儕應覆核的證據。', 'placeholder': '先檢查：…；個人工作：…；同儕覆核：…；未合作請明示。'},
            ],
        },
    },
    {
        'id': 'assembly-slider', 'stage': '組合設計', 'weeks': '7–12',
        'title': 'CATIA 組合設計｜U 型導軌與滑塊',
        'summary': '建立兩種 CATPart 與一份 CATProduct，計算0.2 mm單側間隙，以最小必要約束保留 X 平移，再診斷寬度變更造成的干涉。',
        'brief': '使用同一組合座標，X 沿導軌、Y 橫向、Z 向上，單位 mm。導軌底板 X=0～120、Y=−20～20、Z=0～6；左右壁分別 Y=−20～−12 與12～20，皆 X=0～120、Z=6～22，因此槽內寬24。滑塊原位 X=40～70、Y=−11.8～11.8、Z=6.2～16.2，尺寸30×23.6×10。滑塊與兩側壁各有0.2名義間隙，與底板有0.2名義間隙。導軌固定；以平面定位使滑塊只保留沿 X 平移。此開放槽模型不模擬重力、摩擦、接觸或防脫機構。',
        'goals': ['建立與交付 CATProduct 及所有相依 CATPart', '用數值區分間隙、接觸及干涉，說明約束消除的自由度', '以零件變更和三個位置測試檢查組合'],
        'workbenches': ['Sketcher（草圖）', 'Part Design（零件設計）', 'Assembly Design（組合設計）'],
        'prerequisites': ['完成第一階段，能建立完全約束草圖與 Pad', '認識剛體的三個平移與三個旋轉自由度'],
        'parameters': [
            {'name': '導軌底板', 'value': '120×40×6 mm', 'reference': 'X=0～120、Y=−20～20、Z=0～6'},
            {'name': '側壁', 'value': '長120、厚8、高16 mm，左右各一', 'reference': '由 Z=6 向上至22；槽內側 Y=±12'},
            {'name': '滑塊', 'value': '30×23.6×10 mm', 'reference': '原位 X=40～70、Y=±11.8、底面 Z=6.2'},
            {'name': '名義間隙', 'value': '左右各0.2；底部0.2 mm', 'reference': '尺寸差與組合 Offset，非製造公差或接觸模擬'},
            {'name': '位置測試', 'value': '滑塊左端 X=10、40、80 mm', 'reference': '每一位置均檢查滑塊仍在導軌長度範圍內'},
        ],
        'operation_steps': [
            '建立 Rail.CATPart：XY 面矩形 Pad 6；頂面畫左右壁矩形並 Pad 16，使底板與兩壁合為同一實體。',
            '建立 Slider.CATPart：以自身中心面為橫向對稱基準，畫30×23.6矩形並 Pad 10；保留可選取的底面與中央 XZ 基準面。',
            '建立 SliderAssembly.CATProduct，插入兩零件，對 Rail 使用 Fix（固定）；將滑塊放在題目原位。',
            '以滑塊底面與導軌底板頂面建立0.2 mm Offset（偏移），再以兩者中央 XZ 面建立 Coincidence（重合），選擇方向使滑塊朝上。檢查約束狀態，移除重複約束；勿固定滑塊或加入 X 位置尺寸。',
            '以自由度檢核與受約束操作確認只剩 X 平移；依序把滑塊左端移至 X=10、40、80，更新並量測左右及底部間隙。',
            '另存變更版，把滑塊寬增加2成25.6；先保留導軌槽寬24，記錄干涉。再把槽寬改26、左右壁厚仍8（外寬42），驗證是否恢復每側0.2間隙與預期自由度。',
            '若授權提供 Clash／Clearance，可附分析；否則提交剖視／量測證據並註明檢查方法。以 Save Management 等方式保存全部相依檔，請同儕重開。',
        ],
        'deliverables': ['Rail.CATPart、Slider.CATPart、SliderAssembly.CATProduct；原版與變更版分資料夾保存', '約束樹、剩餘自由度、三個 X 位置的截圖', '24／25.6 與26／25.6兩種配合狀態之尺寸、干涉／間隙比較表'],
        'acceptance': ['原版各零件尺寸與原位座標符合題目，導軌固定而滑塊未被 Fix', '求解檢核僅保留滑塊 X 平移；拖曳畫面只作輔助證據', 'X=10、40、80 三個位置均有量測或剖視紀錄', '辨識加寬後的干涉，修訂槽寬後再驗證0.2 mm單側間隙', 'CATProduct 重開無遺失連結，能找到所有 CATPart'],
        'weekly_plan': [{'weeks': '7–8', 'focus': '建立導軌／滑塊、組合架構與自由度前測'}, {'weeks': '9–10', 'focus': 'Fix／Offset／Coincidence、三位置檢核'}, {'weeks': '11–12', 'focus': '滑塊加寬、干涉診斷、同儕替換與遷移作答'}],
        'perturbation': '滑塊寬23.6→25.6 mm，導軌槽寬先維持24；計算並觀察兩側配合。再將槽內寬改26、壁厚維持8，檢查間隙、自由度及連結是否恢復。',
        'source_ids': ['P2', 'CATIA-PDG', 'CATIA-ASD'],
        'pre': {'question': '一個未受約束的剛體，相對固定組合座標一般有多少個自由度？', 'options': ['只有沿 X、Y、Z 的3個平移', '3個平移與3個旋轉，共6個', '只要能拖動就代表1個', '建立 CATProduct 後自然變成0個'], 'answer': 1},
        'transfer': {'question': '新組合的圓柱轉軸應只保留繞自身軸線旋轉，但加入一項角度約束後完全固定。應優先做什麼？', 'options': ['檢查該角度約束是否消除了原本要保留的旋轉，調整後重新檢核自由度', '把所有元件一起 Fix', '增加更多軸線重合約束', '刪除軸孔幾何直到可以拖動'], 'answer': 0},
        'prompts': {
            '1': [
                {'id': 'slider_clearance', 'prompt': '槽內寬24、滑塊寬23.6且置中。請計算單側間隙；若模型看起來有空隙，還需要什麼數值證據才能確認？', 'placeholder': '計算式與單側值：…；量測方法／方向：…'},
                {'id': 'slider_dof_baseline', 'prompt': '列出未受約束滑塊的六個自由度，並圈定本任務最後應保留哪一個。固定導軌的目的為何？', 'placeholder': '六個自由度：…；應保留：…；固定基準的理由：…'},
            ],
            '2': [
                {'id': 'slider_constraint_plan', 'prompt': '規劃 Fix、底面 Offset 0.2與中央 XZ 面 Coincidence 各選哪些零件／面；逐項說明它們控制的方向，避免加入限制 X 移動的尺寸。', 'placeholder': '約束｜選取面或元件｜控制方向｜預期剩餘運動。'},
                {'id': 'slider_file_plan', 'prompt': '畫出文字版組合樹，列出 CATProduct 與兩個 CATPart 的檔名、資料夾及修改負責人；說明為何只寄 CATProduct 不足。', 'placeholder': '樹／檔名：…；連結保存方式：…；個別責任：…'},
            ],
            '3': [
                {'id': 'slider_position_evidence', 'prompt': '填寫滑塊左端 X=10、40、80三個位置時的左右／底部間隙、更新狀態與證據檔名；說明你如何核對只剩 X 平移。', 'placeholder': 'X位置｜左間隙｜右間隙｜底間隙｜自由度／更新｜證據。'},
                {'id': 'slider_width_prediction', 'prompt': '變更前先算：滑塊寬25.6而槽寬仍24、兩者置中時，每側會有多少間隙或重疊？預測改槽寬26後的結果並說明符號意義。', 'placeholder': '原槽配合計算：…；修訂槽配合計算：…；預測：…'},
            ],
            '4': [
                {'id': 'slider_peer_replace', 'prompt': '由同儕替換加寬滑塊，依序記錄槽寬24與26的實測結果、約束是否失效及修復方式；個人練習請標示自我替換。', 'placeholder': '替換者／檔名：…；兩種槽寬的結果：…；失效約束與修復證據：…'},
                {'id': 'slider_overconstraint', 'prompt': '在副本額外限制滑塊 X 位置或 Fix 滑塊，觀察預期運動如何改變；寫出恢復單一 X 平移的最小修正，引用約束名稱。', 'placeholder': '新增約束：…；剩餘運動：…；移除／修正項：…；驗證：…'},
            ],
            '5': [
                {'id': 'slider_transfer_clearance', 'prompt': '新題：槽內寬32，要求每側名義間隙0.3，置中的滑塊應多寬？若滑塊實際做成32.2，會發生什麼尺寸關係？請獨立計算。', 'placeholder': '要求寬度與計算：…；32.2時的配合與理由：…'},
                {'id': 'slider_transfer_rotation', 'prompt': '新題：轉軸需要保留繞自身軸線旋轉。請說明「保留一個自由度」與本題滑塊保留 X 平移有何不同，並提出能分辨兩者的檢核證據。', 'placeholder': '運動差別：…；應避免鎖住的關係：…；檢核證據：…'},
            ],
            '6': [
                {'id': 'slider_claim_limit', 'prompt': '用本次一張截圖與一個量測值，解釋「約束求解正常」為何不足以證明沒有干涉；再說明本模型不能證明哪些真實機械性能。', 'placeholder': '證據：…；求解與幾何檢查差別：…；未驗證項：…'},
                {'id': 'slider_handoff_revision', 'prompt': '同儕重開組合若出現遺失連結，你會如何檢查路徑與版本？列出下一次交付前的三項具體檢查。', 'placeholder': '檢查／修復方式：…；交付前檢查1…2…3…'},
            ],
        },
    },
    {
        'id': 'project-modular', 'stage': '自選專題', 'weeks': '13–18',
        'title': 'CATIA 整合專題｜雙定位銷檢核治具與工程圖',
        'summary': '以底板、定位銷、試片三種零件組成四元件治具，整合孔距參數、名義間隙、組合交接與 Drafting；延伸自選題須保留同等證據。',
        'brief': '共同必做題為定位展示治具，非施力夾具。單位 mm；X 為孔距方向、Y 為寬度、Z 向上，底板底面中心為原點。Base：X=−60～60、Y=−35～35、Z=0～10，兩個沿 Z 的 Ø6 通孔中心 (−40,0)、(40,0)。Pin：Ø5.8、長30，兩支裝入上述孔，軸線位於 X=±40、Y=0，底端 Z=0、頂端 Z=30。Coupon：長100、寬30、厚10，X=−50～50、Y=−15～15，組合底面 Z=10.2、頂面20.2；兩個 Ø6.2 通孔沿 Z、中心 X=±40、Y=0。孔距 P=80；試片長度規則為 P+20。使用理想同心位置顯示名義間隙，不宣稱真實定位精度、夾持力或可製造性。',
        'goals': ['以同一孔距設計意圖協調不同零件，識別外部連結與版本風險', '區分名義配合尺寸、組合約束與實際定位性能', '建立可閱讀工程圖，完成變更與他人重開驗證'],
        'workbenches': ['Sketcher（草圖）', 'Part Design（零件設計）', 'Assembly Design（組合設計）', 'Drafting（工程製圖）'],
        'prerequisites': ['完成前兩階段，能建立與更新多零件組合', '認識正投影、直徑尺寸、中心線及剖視圖'],
        'parameters': [
            {'name': 'Base 底板', 'value': '120×70×10；2×Ø6 通孔', 'reference': '底面中心原點；孔中心 (±P/2,0)，沿 Z'},
            {'name': 'Pin 定位銷', 'value': 'Ø5.8×30，共2支', 'reference': '軸線 X=±P/2、Y=0；組合底端 Z=0'},
            {'name': 'Coupon 試片', 'value': '100×30×10；2×Ø6.2 通孔', 'reference': '長=P+20；關於 X=0、Y=0 對稱；組合底面 Z=10.2'},
            {'name': '共同孔距 P', 'value': '80 mm；變更版90 mm', 'reference': '底板孔、試片孔及兩銷位置均以±P/2定位'},
            {'name': '名義配合與間隔', 'value': '銷／底板徑向0.1；銷／試片徑向0.2；板間0.2 mm', 'reference': '以直徑差除2與底面高度計算，非公差或定位精度承諾'},
            {'name': '工程圖', 'value': 'A3、mm；可用1:1比例', 'reference': '組合正投影＋等角圖；零件尺寸圖；沿 Y=0 的 XZ 剖面可通過兩銷'},
        ],
        'operation_steps': [
            '建立 Base.CATPart：以 XY 面中心矩形 Pad 10，建立兩個 Ø6 貫穿孔，孔距參數 P=80、中心 Y=0。',
            '建立 Pin.CATPart：圓形草圖 Ø5.8，Pad 30；建立 Coupon.CATPart：中心矩形長 P+20、寬30，Pad 10，兩個 Ø6.2 孔中心 X=±P/2、Y=0。',
            '建立 Fixture.CATProduct，插入 Base、Coupon、Pin.1、Pin.2，固定 Base；按指定座標放置元件。銷軸與底板孔軸同心、銷底端與底板底面齊平；光滑銷繞自身軸線的剩餘旋轉應記錄，不必以重複約束消除。',
            '將 Coupon 定位於孔軸同心、底面距 Base 頂面0.2的名義位置。採最小獨立約束並檢查冗餘；若第二組孔軸約束重複控制方向，改用中心連線的方向基準。最終展示可另存固定狀態，但不能以 Fix 作為配合正確證據。',
            '量測銷／底板與銷／試片的直徑差、徑向間隙及板間間隔；以 Y=0 剖視檢查銷、孔、底板與試片位置。',
            '在 Drafting 建立正投影與等角視圖，另以零件圖或多頁圖標示三種零件的必要尺寸、孔徑、孔距、中心線、單位、比例及件數；保存 CATDrawing 與 PDF。',
            '另存 P90 版本：P由80改90，Coupon長由100改110，兩孔與兩銷改至 X=±45；由同儕依變更單更新、量測並更新工程圖。可用共同參數或逐檔變更表，但必須能核對所有版本。',
            '以 Save Management 等方法整理 CATProduct、三種 CATPart、CATDrawing、PDF與變更單；請同儕在另一資料夾重開並核對連結。完成共同題後才提出經教師確認的自選延伸。',
        ],
        'deliverables': ['Base.CATPart、Pin.CATPart、Coupon.CATPart、Fixture.CATProduct（四個元件）', 'P80 與P90兩版 CATDrawing、PDF與尺寸變更單', '組合樹、孔／銷剖視與名義間隙量測截圖', '交接清單：檔名、版本、相依連結、修改者及同儕重開結果'],
        'acceptance': ['包含三種獨立零件、四個組合元件，尺寸與原位符合共同題', '能解釋兩種徑向間隙、0.2板間間隔及銷剩餘旋轉，不把理想組合當成定位精度證明', 'P90版的Base孔、Coupon孔、兩銷位置與Coupon長度一致更新', '工程圖可核對孔徑、孔距與三種零件尺寸，圖面與3D版本相符', '交付資料夾在另一位置重開無遺失連結，教師能依原始檔覆核'],
        'weekly_plan': [{'weeks': '13–14', 'focus': '共同治具需求、三零件建模與參數依存'}, {'weeks': '15–16', 'focus': '四元件組合、間隙量測與Drafting'}, {'weeks': '17–18', 'focus': 'P90變更、同儕交接、個人答辯及教師覆核'}],
        'perturbation': '共同孔距 P=80→90 mm，Coupon長度維持P+20規則；先預測底板孔、試片孔、兩銷位置與端部邊距，再由同儕更新全部零件與工程圖，檢查是否漏改或版本混用。',
        'source_ids': ['P1', 'P2', 'CATIA-PDG', 'CATIA-ASD', 'CATIA-DRAFT'],
        'pre': {'question': 'Fixture.CATProduct 引用了 Base、Pin 與 Coupon，現在只把 CATProduct 複製到另一資料夾。最需要注意什麼？', 'options': ['CATProduct一定內含所有零件幾何，不需檢查', '須確認所有相依CATPart與連結可被找到，並在交付位置實際重開', '只要PDF看起來正確即可', '把檔名改成final就能確保版本一致'], 'answer': 1},
        'transfer': {'question': '新治具把孔距改為100，但工程圖仍標舊孔距、兩支銷也未移動。最有用的改善是？', 'options': ['只重新輸出目前畫面的截圖', '建立共同參數／逐檔變更表，更新所有關聯零件與工程圖，再量測及重開驗證', '只把CATProduct重新命名', '把所有元件Fix後宣稱變更完成'], 'answer': 1},
        'prompts': {
            '1': [
                {'id': 'fixture_interface_reading', 'prompt': '分別列出 Base、Pin、Coupon 的功能與相互配合的尺寸；指出這個模型為何是定位展示，不能直接聲稱能夾緊工件。', 'placeholder': '零件｜用途｜配合尺寸；沒有驗證的施力／定位項目：…'},
                {'id': 'fixture_gap_baseline', 'prompt': '銷Ø5.8、Base孔Ø6、Coupon孔Ø6.2。請分別計算直徑間隙與徑向間隙，並說明兩個詞不能混用的原因。', 'placeholder': 'Base配合：…；Coupon配合：…；直徑／徑向定義：…'},
            ],
            '2': [
                {'id': 'fixture_parameter_plan', 'prompt': '建立共同孔距 P 的依存清單：哪些零件的孔位、元件位置與試片長度必須隨 P 更新？說明你採共同參數還是逐檔變更表。', 'placeholder': 'P→零件／特徵／公式或修改項；同步與核對方式：…'},
                {'id': 'fixture_drawing_plan', 'prompt': '規劃交付工程圖：選哪些投影／剖視、各標哪些尺寸，才能讓另一位同學不靠猜測重建三種零件？請列出頁面或視圖名稱。', 'placeholder': '頁面／視圖｜需要看見的幾何｜必要尺寸／中心線。'},
            ],
            '3': [
                {'id': 'fixture_fit_evidence', 'prompt': '以原版 P80 填寫Base與Coupon孔中心、銷端點高度、Coupon底面高度及兩種徑向間隙；引用剖視／量測證據，並記錄銷軸向旋轉是否仍存在。', 'placeholder': '幾何／配合項｜實測值｜約束／量測方法｜檔名；剩餘旋轉：…'},
                {'id': 'fixture_revision_prediction', 'prompt': '更新前先預測 P=90 時兩孔／兩銷的 X、Coupon長度與孔中心到試片最近端部的距離。哪些 Base 外形尺寸不需要改？', 'placeholder': '變更項與預測：…；計算：…；維持項與理由：…'},
            ],
            '4': [
                {'id': 'fixture_peer_change_order', 'prompt': '由同儕照變更單建立P90，逐項記錄零件、組合、CATDrawing與PDF的更新結果；若發現一項漏改，寫出發現依據與修正。', 'placeholder': '修改者：…；變更項｜結果｜證據；漏改與修正（若無，說明檢查方法）：…'},
                {'id': 'fixture_handoff_test', 'prompt': '把交付資料複製到另一資料夾，請同儕重新開啟 CATProduct 與 CATDrawing。列出相依檔案是否齊全、版本是否一致，以及你實際採用的保存方式。', 'placeholder': '測試者／位置：…；保存方式：…；連結／版本檢查：…；個人測試請明示。'},
            ],
            '5': [
                {'id': 'fixture_transfer_parameter', 'prompt': '新題：共同孔距改為100，試片仍須保持兩孔中心各距最近端部10且關於原點對稱。請算試片長度及兩孔 X，提出一個能抓到漏改零件的驗證步驟。', 'placeholder': '獨立計算：…；驗證步驟與判斷依據：…'},
                {'id': 'fixture_transfer_gap', 'prompt': '新題：改用Ø7.8銷，希望試片孔每側徑向間隙0.15，試片孔應標多少直徑？若工程圖與3D數值不同，交付前應如何處理？不使用AI。', 'placeholder': '孔徑計算：…；圖模不一致的處理與再次核對：…'},
            ],
            '6': [
                {'id': 'fixture_design_defense', 'prompt': '引用一項零件證據、一項組合證據與一項工程圖證據，說明你如何確認 P90 交付完成；再列出本課未驗證的一項製造或力學條件。', 'placeholder': '零件／組合／圖面檔名及數值：…；未驗證條件：…'},
                {'id': 'fixture_extension_proposal', 'prompt': '以共同治具為基礎提出一個自選延伸，例如第三定位點或可換試片。明確列新需求、需修改的CATPart／約束／工程圖及一項可量測驗收條件，交由教師確認。', 'placeholder': '新需求：…；修改清單：…；驗收值／方法：…；個人與同儕分工：…'},
            ],
        },
    },
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
    data = {k: copy.deepcopy(v) for k, v in task.items() if k not in ('pre', 'transfer', 'prompts')}
    if 'prompts' in task:
        data['question_count'] = sum(len(questions) for questions in task['prompts'].values())
    return data


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
