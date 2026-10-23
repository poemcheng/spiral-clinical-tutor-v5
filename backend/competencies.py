"""Profession-specific learning indicators; locally authored mappings, not validated scales."""
import copy
import secrets
from .legacy.builtin_cases import PROFESSIONS
from . import core_alignment

VERSION = core_alignment.VERSION
HCPC = 'https://www.hcpc-uk.org/standards/standards-of-proficiency/'
SOURCES = {
 'MD': ('CanMEDS Physician Competency Framework 2015', 'https://www.royalcollege.ca/content/dam/document/standards-and-accreditation/canmeds-full-framework-e.pdf', 'Seven roles; 2026 comparison checked separately'),
 'RN': ('AACN Essentials 2026', 'https://www.aacnnursing.org/Portals/0/PDFs/Publications/Essentials-2026.pdf', 'Domains for Nursing; person-centered care, quality and safety, partnerships'),
 'DT': ('ICDA International Competency Standards 2016', 'https://internationaldietetics.org/wp-content/uploads/2023/05/International-Competency-Standards-for-Dietitian-Nutritionists.pdf', 'Sections 1–5; PDF pp.9–21'),
 'PT': ('World Physiotherapy education framework 2021', 'https://world.physio/what-we-do/education/physiotherapist-education-framework', 'Framework: practice competence; implementation guidance'),
 'RT': ('HCPC radiographers 2023', HCPC+'radiographers/', 'Standards 7–8, 12–15; radiographic safety, quality and collaboration'),
 'OT': ('HCPC occupational therapists 2023', HCPC+'occupational-therapists/', 'Standards 7–8, 12–15'),
 'ST': ('HCPC speech and language therapists 2023', HCPC+'speech-and-language-therapists/', 'Standards 7–8, 12–15'),
 'AUD': ('HCPC hearing aid dispensers 2023', HCPC+'hearing-aid-dispensers/', 'Standards 7–8, 12–15; contextual mapping only'),
 'CP': ('HCPC practitioner psychologists 2023', HCPC+'practitioner-psychologists/', 'Standards 7–8, 12–15; clinical psychology'),
 'MLS': ('HCPC biomedical scientists 2023', HCPC+'biomedical-scientists/', 'Standards 8.3, 12.3–12.6, 13–15'),
 'RPH': ('FIP Global Competency Framework v2 2020', 'https://www.fip.org/file/4805', 'Pharmaceutical care; professional and personal competencies'),
 'RSP': ('CoARC entry into respiratory care standards', 'https://coarc.com/accreditation/entry-into-practice-standards/', 'Current version in effect 3/2024; section 4 curriculum (2027 edition not yet effective)'),
}
# Name, observable behavior, compatibility dimension. Counts are local curricular choices.
DEFINITIONS = {
 'MD': [('診斷整合','整合病史、檢查與功能資料並說明不確定性','CJ'),('共同決策','以病人可理解的方式討論選擇','COM'),('跨職類協作','整合會診意見及確認分工','TC'),('照護協調','安排追蹤責任與時間','PC'),('健康倡議','辨識就醫及生活資源障礙','HC'),('實證反思','核對證據版本與個案適用條件','CJ'),('專業倫理','說明職責界線及隱私保護','SAFE')],
 'RN': [('護理觀察','辨識攝食、活動與身體狀況的變化','CJ'),('照護執行','依病人需求安排照護與追蹤','PC'),('衛教確認','以回覆示教確認病人理解','COM'),('病人安全','辨識風險並停止不安全的照護','SAFE'),('團隊交接','以SBAR向物理治療師交接功能及照護問題','TC'),('轉介追蹤','確認跨職類轉介的接收與後續處理','TC'),('家庭支持','評估照顧負荷與可用資源','HC'),('紀錄與倫理','準確記錄並保護病人資訊','SAFE')],
 'DT': [('營養資料收集','確認飲食份量、頻率與資料缺口','CJ'),('營養問題判斷','依案例資料釐清營養問題與限制','PC'),('個別化介入','協商可執行的飲食目標','HC'),('營養監測','設定攝食及營養追蹤方式','PC'),('跨專業營養溝通','向物理治療師交接營養需求並確認理解','TC'),('營養專業安全','核對疾病限制、依據與職責界線','SAFE')],
 'PT': [('功能評估','記錄肌力、移動與生活功能線索','CJ'),('測試品質','依流程執行並說明測量限制','PC'),('運動計畫','依個案狀態設定漸進活動目標','PC'),('活動安全','辨識不適、停止活動並求助','SAFE'),('病人溝通','處理跌倒焦慮並確認理解','COM'),('團隊轉介','向營養及醫護團隊交接功能需求','TC'),('生活參與','把居家條件及病人目標納入追蹤','HC')],
 'RT': [('檢查準備安全','核對身分、檢查需求與移位風險','SAFE'),('影像技術品質','核對擺位、檢查條件與影像品質','PC'),('影像資料限制','辨識報告差異及判讀限制','CJ'),('放射檢查溝通','清楚說明檢查流程並確認理解','COM'),('跨職類影像交接','向物理治療師交接影像品質與功能評估限制','TC')],
 'OT': [('生活職能評估','辨識日常活動限制與環境障礙','CJ'),('職能活動計畫','以生活目標安排活動練習','PC'),('環境與輔具','核對居家調整與輔具需求','HC'),('參與式溝通','與病人協商有意義的活動目標','COM'),('團隊協作','交接生活功能與照顧支持需求','TC'),('職能安全','檢查活動、移位與輔具使用風險','SAFE')],
 'RSP': [('呼吸狀況觀察','辨識呼吸與活動耐受的變化','CJ'),('呼吸照護流程','核對照護任務及追蹤紀錄','PC'),('異常求助','辨識異常並依權責求助','SAFE'),('呼吸照護溝通','說明照護安排並回應喘促焦慮','COM'),('呼吸團隊交接','向醫護與復健團隊交接狀態變化','TC')],
 'RPH': [('用藥整合','核對完整用藥清單及資料缺口','CJ'),('藥事問題評估','辨識需向處方者確認的用藥疑點','PC'),('用藥安全','確認處方及不擅自停改藥的界線','SAFE'),('用藥溝通','確認病人理解用藥說明','COM'),('藥事協作','交接用藥相關照護需求','TC'),('服藥支持','評估作息、負擔及家庭協助','HC')],
 'ST': [('吞嚥評估線索','記錄進食困難與待確認資訊','CJ'),('溝通功能','觀察表達及理解的支持需求','PC'),('支持性溝通','以可近的溝通方式確認理解','COM'),('進食安全','辨識進食異常並依界線求助','SAFE'),('吞嚥團隊交接','向營養及醫護團隊交接限制','TC'),('生活參與目標','納入進食偏好與共餐需求','HC')],
 'AUD': [('聽覺需求辨識','記錄聽覺困難及評估資料缺口','CJ'),('聽覺評估品質','核對評估準備與紀錄','PC'),('溝通可近性','確認病人聽清及理解照護資訊','COM'),('聽覺轉介','向團隊交接溝通調整需求','TC'),('聽覺照護安全','辨識需進一步轉介及知情同意事項','SAFE')],
 'CP': [('心理評估','辨識情緒、行為與待確認資訊','CJ'),('心理支持計畫','與病人討論可執行的支持目標','PC'),('同理溝通','理解焦慮並確認病人感受','COM'),('危機與界線','辨識風險並依專業界線轉介','SAFE'),('心理團隊合作','在同意範圍內交接支持需求','TC'),('社會情境','將生活壓力及支持資源納入評估','HC')],
 'MLS': [('檢體前處理','核對身分、採檢條件及檢體品質','SAFE'),('檢驗品質','確認品質控制及結果可靠性','PC'),('結果限制','辨識干擾及資料解讀限制','CJ'),('異常通報','依流程通報並確認接收','TC'),('檢驗資訊溝通','清楚說明檢驗流程與限制','COM')],
}

def profile(profession):
    from .training_evidence import REFERENCES,NOTE
    title,url,location=SOURCES[profession]
    return {'version':VERSION,'profession':profession,'label':PROFESSIONS[profession]['label'],
      'status':'核心能力名稱及順序依使用者提供《核心能力.docx》；情境行為與題目由平台轉寫，並非正式核定量表，待職類教師審核。',
      'source_file':core_alignment.CATALOG['source_file'],'source_sha256':core_alignment.CATALOG['source_sha256'],
      'epa_note':NOTE,'epa_reference':REFERENCES.get(profession),
      'references':[{'title':'使用者提供《核心能力》職種對照','url':'/api/materials/core-competencies','location':core_alignment.CATALOG['professions'][profession]['source_label']+'欄','support':'核心能力名稱、軸數與順序的直接來源'},
        {'title':title,'url':url,'location':location,'checked_at':'2026-10-22','support':'補充框架參照；不代表附件或本地題目已獲官方核定'}],
      'indicators':core_alignment.indicators(profession)}

def aligned_result(scores,profession):
    return core_alignment.align(scores,profession,profile)

def apply_profile(core, previous=None):
    p=profile(core['profession']);old=copy.deepcopy(core['items'])
    core['reference_self_items']=old
    old_ids={q['item_id'] for q in (previous or {}).get('items',[])}
    items=[]
    for i in p['indicators']:
        variant=secrets.randbelow(2)
        base=f"{VERSION}-{i['id']}-L{core['level']}"
        if f'{base}-{variant}' in old_ids:variant=1-variant
        focus='我能'+i['description'] if variant==0 else '我能說明如何'+i['description']+'，並指出需要協助之處'
        items.append({'item_id':f'{base}-{variant}','indicator_id':i['id'],'dimension':i['dimension'],'level':core['level'],'profession':core['profession'],
          'dimension_name':i['name'],'prompt':f"在{core['topic']} Level {core['level']}的本職類任務中，{focus}。",
          'reference_ids':[i['id']],'authoring_status':p['status']})
    core.update(items=items,competency_profile=p,form_version=VERSION+' / '+core['form_version'],
      form_title=f"{p['label']}・{core['topic']} Level {core['level']}・{len(items)}項核心指標自評",
      source_status=p['status'],source_file='data/職種核心指標＋既有客觀前測',
      score_formula='各職種核心指標自評分數 × 20 後等權平均；共通構面僅供跨版補強比較。')
    return core

def result(snapshot, answers):
    p=snapshot.get('competency_profile')
    if not p:return {}
    by_id={q['indicator_id']:answers[q['item_id']]*20 for q in snapshot['items']}
    rows=[{**i,'score':by_id[i['id']],'feedback':('優先練習：' if by_id[i['id']]<60 else '持續驗證：')+i['description']} for i in p['indicators']]
    return {'competency_profile':p,'competency_scores':by_id,'competency_results':rows,'score_formula':snapshot['score_formula']}
