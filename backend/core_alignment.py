"""User-supplied core axes and explicit, conservative legacy score crosswalks."""
import copy,json
from .config import ROOT
CATALOG=json.loads((ROOT/'data/core_competencies.json').read_text(encoding='utf-8'))
VERSION=CATALOG['version']
# Observable scenario behaviors authored for the supplied domains, not a validated scale.
BEHAVIORS={
 'MD':[('整合病人需求、症狀、功能與追蹤安排','PC'),('說明肌肉量、肌力及功能資料的意義與限制','CJ'),('依回饋檢討判斷並提出下次改善行為','CJ'),('回應病人疑慮並以白話確認理解','COM'),('保護隱私並說明專業及證據界線','SAFE'),('整合跨職類轉介、資源與追蹤責任','TC')],
 'RN':[('依病人需求安排照護、活動安全與追蹤','PC'),('運用篩檢與照護知識辨識需進一步確認的變化','CJ'),('說明照護流程並以回覆示教確認理解','COM'),('依倫理與安全原則記錄及處理資訊','SAFE'),('整合轉介、分工及照護資源並確認接收','TC'),('依照護結果與教師回饋修正下一輪做法','CJ')],
 'DT':[('解釋營養問題的依據、疾病限制及資料缺口','CJ'),('與病人及團隊協商並確認理解','COM'),('完成飲食資料收集、評估、介入及監測','PC'),('維持營養專業界線與病人資訊保護','SAFE'),('依追蹤與回饋修正營養判斷及溝通','CJ'),('協調照護時間、團隊分工與可用資源','TC')],
 'PT':[('完成標準化功能評估並討論個別化活動目標','PC'),('維持知情同意、活動安全與專業界線','SAFE'),('以可理解的說明回應疑慮並確認理解','COM'),('核對實證並依回饋改進評估與介入','CJ'),('與其他職類確認功能資料、需求及分工','TC'),('安排追蹤資源並為個案生活參與需求發聲','HC')],
 'RT':[('解釋影像指標、檢查條件與結果限制','CJ'),('與病人及跨職類團隊確認影像交接資訊','COM'),('核對身分、移位需求與檢查安全','PC'),('執行及核對擺位、掃描範圍與影像品質','PC'),('保護資訊並遵守放射安全與專業界線','SAFE')],
 'RPH':[('整合用藥及病人照護需求','PC'),('說明用藥相關知識與需查證的限制','CJ'),('依制度協調藥事流程及跨職類轉介','TC'),('向病人及團隊清楚說明並確認理解','COM'),('維持藥事倫理、安全與職責界線','SAFE'),('依實證及回饋持續改善藥事服務','CJ')],
 'MLS':[('解釋檢驗知識、干擾與資料限制','CJ'),('核對檢體處理、品質控制及檢驗流程','PC'),('保護病人資訊並維持專業安全界線','SAFE'),('依品質資料與回饋改進作業','CJ'),('清楚說明檢驗資訊並確認接收','COM'),('依制度完成異常通報及團隊交接','TC')],
 'RSP':[('依體制協調呼吸照護流程與追蹤','TC'),('回應喘促焦慮並確認病人理解','COM'),('解釋呼吸狀態與活動耐受資料的限制','CJ'),('與團隊確認呼吸照護需求及分工','TC'),('辨識病人變化並依需求提供照護','PC'),('辨識風險並維持知情同意與專業界線','SAFE'),('依實證及回饋改善呼吸照護','CJ')],
 'AUD':[('將聽覺專業知識應用於本輪需求','CJ'),('維持知情同意與聽覺照護安全','SAFE'),('將個案偏好及溝通可近性納入照護','HC'),('向病人及團隊說明聽覺知識與限制','COM'),('交接聽覺及溝通調整需求','TC'),('整合轉介與可用照護資源','TC')],
 'OT':[('應用職能治療價值與知能分析日常活動','PC'),('與病人及團隊建立協作關係','COM'),('說明活動選擇的依據與替代解釋','CJ'),('維持知情同意、活動安全及職責界線','SAFE'),('依實證與回饋持續改善職能照護','CJ')],
 'ST':[('整合進食與溝通支持需求','PC'),('說明吞嚥及溝通評估知識與限制','CJ'),('依臨床回饋檢討並改善做法','CJ'),('用可近方式說明並確認理解','COM'),('維持進食安全、知情同意及專業界線','SAFE'),('依制度完成轉介、協作與追蹤','TC')],
 'CP':[('解釋心理評估知識及待確認資訊','CJ'),('依個案需求討論心理支持目標','PC'),('理解感受並確認彼此的溝通意義','COM'),('依同意範圍整合心理照護轉介與資源','TC'),('辨識風險並維持保密與專業界線','SAFE'),('依實證與回饋改善心理照護','CJ')],
}
# Old indicator numbers with reasonably related evidence. Empty lists mean unassessed.
# A crosswalk is a display reference, never a rewrite of the original measurement.
LEGACY={
 'MD':[[1,4],[1],[6],[2],[7],[3,4,5]],
 'RN':[[1,2,7],[1,2],[3],[4,8],[5,6],[]],
 'DT':[[2],[5],[1,2,3,4],[6],[],[]],
 'PT':[[1,2,3],[4],[5],[],[6],[7]],
 'RT':[[3],[4,5],[1],[2],[]],
 'RPH':[[1,2],[2],[5],[4],[3],[]],
 'MLS':[[3],[1,2],[1],[],[5],[4]],
 'RSP':[[2],[4],[1],[5],[2],[3],[]],
 'AUD':[[1,2],[5],[3],[],[4],[]],
 'OT':[[1,2,3],[4],[1],[6],[]],
 'ST':[[1,2,6],[1,2],[],[3],[4],[5]],
 'CP':[[1],[2],[3],[5,6],[4],[]],
}

def indicators(profession):
    axes=CATALOG['professions'][profession]['axes'];behaviors=BEHAVIORS[profession]
    assert len(axes)==len(behaviors)
    return [{'id':f'{profession}-C{i+1:02}','name':name,'description':behavior,'dimension':dimension,'reference_index':0}
            for i,(name,(behavior,dimension)) in enumerate(zip(axes,behaviors))]

def align(scores,profession,profile_factory):
    output=copy.deepcopy(scores);current=profile_factory(profession)
    original=scores.get('competency_profile',{})
    if original.get('version')==VERSION:return output
    available=scores.get('competency_scores',{});rows=[];by_id={}
    for indicator,numbers in zip(current['indicators'],LEGACY[profession]):
        source_ids=[f'{profession}-{n:02}' for n in numbers if isinstance(available.get(f'{profession}-{n:02}'),(int,float))]
        value=round(sum(available[k] for k in source_ids)/len(source_ids),1) if source_ids else None
        by_id[indicator['id']]=value
        rows.append({**indicator,'score':value,'source_indicators':source_ids,
            'feedback':'舊版相關指標對應參考；需以新版自評確認。' if source_ids else '本輪未評估此核心能力，請完成新版自評。'})
    output.update(competency_profile=current,competency_scores=by_id,competency_results=rows,
        score_formula='舊版相關指標等權平均，僅供核心能力對照；不改動原始自評分數、分流或教師核定。',
        competency_alignment={'kind':'legacy-crosswalk','source_version':original.get('version','legacy'),
          'note':'本輪使用舊版指標；下圖依附件核心能力整理相關自評參考值，未評項目不以0分代替。請重新自評取得新版各軸直接評量。'})
    return output
