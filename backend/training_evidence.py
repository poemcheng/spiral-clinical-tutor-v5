"""Provenance audit, not external endorsement or a licensed EPA reproduction."""
from collections import Counter
from .sarcopenia_bank import load_bank

CHECKED='2026-10-23'
REFERENCES={
 'RT': {'title':'醫事放射師全聯會：醫事放射師 EPAs','url':'https://www.cart.org.tw/main/page_view.aspx?chapid=&langid=1&mnuid=5320&modid=796','scope':'臨床實習之任務觀察與回饋；並非本題庫的出處或核定。'},
 'PT': {'title':'臺灣物理治療學會：EPA 描述通例第二版 V.4','url':'https://www.tpta.org.tw/articles.php?type=download','scope':'任務、風險、評估與督導架構；網站明示利用須授權，本平台僅提供連結及自編任務，不重製原表。'},
 'RN': {'title':'台灣護理學會：0–3 個月新進護理師 EPA 指引','url':'https://www.tcnurse.org.tw/filecenter/B/8DE64C784817C4B071/8DE64C784817C4B0712.pdf','scope':'台灣護理學會原指引，由臺中市護理師護士公會公開提供；適用新進護理師，非所有護理職涯或專科護理師通用考卷。'},
 'DT': {'title':'營養師全聯會：2024 第二版 EPAs 與 2026 里程碑公告','url':'https://www.dietitians.org.tw/publicUI/B/B10101.aspx?arg=8DB78940508CD1E001','scope':'新進營養師任務及多元多點評量；自評、知識題、觀察與教師信賴判斷須分別保存。'},
 'MD': {'title':'台灣急診醫學會：2019 EPAs 第一版公告','url':'https://www.sem.org.tw/News/1/Details/457','scope':'急診專科的公開範例；不等同所有醫師通用或肌少症專屬核定量表。'},
}
NOTE='自評 Level 1–5 僅決定模擬會談壓力；正式 EPA 信賴授權須由訓練單位依多次臨床觀察與教師／委員會決定。平台分數及教師教學回饋不自動等同院方 EPA 授權。'

def audit():
    bank=load_bank();items=[]
    for prof in bank['professions'].values():
        for level in prof['levels'].values():
            items.extend(level['self']);items.extend(level['objective'])
    counts=Counter(q.get('review_status','未標示') for q in items)
    return {'checked_at':CHECKED,'version':'provenance-5.4.0','item_count':len(items),'review_counts':dict(counts),
       'attachment':bank.get('attachment_source',{}),
       'status':'未驗證為正式公開考題／院方核定考核；現有 1,250 題為待審題庫。',
       'official_exam_verified':False,'verification_scope':'已逐題檢查現有來源、審核及核定欄位；未取得每題公開原題網址、官方題號與院方核定紀錄，不能宣稱已完成官方原題逐字比對。',
       'required_for_official_use':['逐題公開原題網址、版本、頁碼或題號','重製使用權或授權範圍','職類教師審題與答案依據','院方核定版本、效期與信賴授權規則'],
       'level_note':NOTE,'references':[{**v,'profession':k,'checked_at':CHECKED} for k,v in REFERENCES.items()],
       'training_reference':{'title':'衛福部二年期醫事職類訓練課程指引','url':'https://dep.mohw.gov.tw/DOMA/cp-2713-41722-106.html'}}
