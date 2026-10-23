"""Level 2 team knowledge derived from the supplied sarcopenia care guide."""
from .competencies import profile
from .config import ROOT
VERSION='sarc-team-knowledge-20261023-v1'
ROLES=[
 ('MD','西醫','診斷與整合治療',
  ['理解肌少症與老化、營養不足及活動量下降的關係。','整合肌力、肌量與身體功能評估。','解讀DXA肌肉量資料時註明採用標準與版本，不能只憑單一指標下完整診斷。','評估低體重、跌倒風險及可能次發性原因。','整合物理治療與營養轉介，追蹤照護成效。'],
  '從風險辨識走向整合照護決策。','整合判斷、需補評估與轉介追蹤。','向放射確認影像限制、向物治確認肌力功能、向營養確認攝食問題。'),
 ('RN','護理','早期辨識與生活照護',
  ['辨識疲勞、久站腳痠、拿物無力等需評估的線索。','了解SARC-F等篩檢工具的用途與限制。','評估跌倒、營養不良與日常生活功能風險。','協助居家環境安全、規律活動及照護計畫執行。','以回覆示教確認理解，追蹤體重、飲食與活動情形。'],
  '將風險轉化為日常照護與安全管理。','照護觀察、病人疑慮、活動及飲食執行情形。','向醫師確認整合安排，與物治、營養確認照護協助與回報責任。'),
 ('RT','醫事放射','DXA檢查與肌量分析',
  ['理解DXA測量骨密度、瘦體組織及脂肪的原理。','區分BMD、LMI、ALMI及體脂率的意義。','了解ALMI為四肢瘦體組織量除以身高平方，與其他指標分開解讀。','核對擺位、掃描範圍、分析區域及追蹤檢查一致性。','向團隊說明檢查結果與可能測量差異，保留報告及職責界線。'],
  '提供可靠的身體組成資料，協助團隊理解肌肉量變化。','影像指標、檢查條件、品質及比較限制。','向物治確認功能資訊需求；診斷整合及骨密度判讀由適當醫療人員確認。'),
 ('DT','營養','肌肉合成與個別化飲食',
  ['評估體重過輕與熱量、蛋白質攝取不足風險。','理解蛋白質、足夠熱量與阻力訓練的協作關係。','評估飲食種類、份量、三餐分配與實際進食習慣。','依營養狀況、疾病及腎功能等限制訂定個別化需求。','追蹤體重、攝取量與運動配合情形，將缺少資料列為待核對。'],
  '辨識自認吃得健康但實際攝取可能不足的問題。','攝食資料、營養問題、限制及可執行目標。','向物治確認活動需求與執行情形，向醫療團隊確認疾病及個別限制。'),
 ('PT','物理治療','功能評估與運動處方',
  ['以標準化5次坐站等測試評估功能，核對姿勢、計時及採用標準。','區分散步、伸展與阻力訓練的用途。','示範坐站、抬腿、抬臀及上肢動作，依個案狀況調整。','依能力調整強度、次數及安全措施，辨識需要停止或求助的情況。','以回覆示教確認動作及理解，持續追蹤功能變化。'],
  '協助個案從知道要運動，走向正確且可持續的活動。','標準化功能結果、動作策略、活動安全及協助需求。','向放射確認影像資料，與護理確認安全協助，與營養整合活動及攝食計畫。'),
]

def for_case(case,profession,level,sid):
    unlocked=level>=2
    # The supplied guide describes sarcopenia; do not relabel it for other cases.
    applicable=case.get('symptom')=='肌少症' or case.get('id','').startswith('SARC') or case.get('id')=='COURSE-SARC'
    if not applicable:return None
    base={'version':VERSION,'unlocked':unlocked,'required_level':2,'title':'跨專業肌少症整合照護指南',
        'note':'累積學習Level 2解鎖團隊知識，與自評互動難度分開；學習他職種的資訊接點，不代表取得該職類執業資格。'}
    if not unlocked:return base
    cards=[]
    for code,label,focus,knowledge,task,provide,request in ROLES:
        cards.append({'profession':code,'label':label,'is_own':code==profession,'focus':focus,'knowledge':knowledge,
          'core_task':task,'provide':provide,'request':request,
          'core_competencies':[i['name'] for i in profile(code)['indicators']]})
    return {**base,'roles':cards,'source_file':'跨專業肌少症整合照護指南.png',
        **({'image_url':f'/api/sessions/{sid}/resources/team-guide'} if (ROOT/'data/sources/跨專業肌少症整合照護指南.png').is_file() else {}),
        'version_note':'附件含AWGS 2019教學指標。原圖坐站「超過12秒」應查核為2019共識的≥12秒；2025診斷演算法不同，請依教案版本及教師核定解讀，不能直接當成現行診斷規則。',
        'references':[{'title':'AWGS 2019共識原文摘要','url':'https://pubmed.ncbi.nlm.nih.gov/32033882/'},
                      {'title':'AWGS 2025共識原文摘要','url':'https://pubmed.ncbi.nlm.nih.gov/41188603/'}]}
