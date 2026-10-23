"""Cumulative five-level knowledge lessons, independent of dialogue difficulty."""
from . import teaching_media
from .competencies import profile
VERSION='cumulative-lessons-5.3.2'
TITLES=['單一職類教案','跨域合作教案','一般影片教案','環景場域教案','逐格動作分析與解釋教案']

def levels(case,profession,learning_level,clips=()):
    role=case.get('roles',{}).get(profession,{})
    own=role.get('task') or case.get('variant',{}).get('role_task') or '依本職類核心能力完成資料蒐集、判讀與說明。'
    indicators=profile(profession)['indicators']
    source={'title':case.get('source_file') or '平台案例與職類核心指標','location':'來源頁 '+','.join(map(str,case.get('source_pages',[]))),'status':case.get('review_status','教學草稿，待教師核定')}
    normal=[c for c in clips if c.get('projection')=='flat' and (not c.get('topic') or c.get('topic')==case.get('symptom'))]
    team=[f"{r.get('title',code)}：{r['task']}" for code,r in case.get('roles',{}).items() if code!=profession]
    if not team:team=['接收者先確認已知事實、待補資訊、負責者與回覆時間。']
    def lesson(level,key,title,purpose,knowledge,observe,question,**extra):
        return {'id':f"{case['id']}-{profession}-L{level}-{key}",'level':level,'title':title,'purpose':purpose,
          'knowledge':knowledge,'observe':observe,'question':question,'sources':[source],'review_status':'教學解析草稿；臨床正確性與評量標準由教師核定',**extra}
    content={
      1:[lesson(1,'role','本職類任務與資料判讀','先建立單一職類的基本評估順序，再進入跨域合作。',
          [own,*case.get('pre_knowledge',[])[:3]],
          [f"{i['name']}：{i['description']}" for i in indicators[:3]],
          '列出本職類先確認的三項資料，分別說明為何需要，以及目前缺少什麼。'),
         lesson(1,'communication','以病人需求開始說明','將專業任務連到病人的疑慮與理解。',
          ['先確認身分與此次需求，再說明本職類能協助的範圍。','區分病人陳述、客觀資料與尚待驗證的解釋。','使用白話說明後，請對方以自己的話回述下一步。'],
          ['病人的主要疑慮是什麼？','您使用的詞語是否能讓初次接觸此情境者理解？'],
          '寫出一句同理開場與一句確認理解的提問，並解釋兩句話的目的。')],
      2:[lesson(2,'roles','跨職類任務與資訊接點','知道自己的資料如何影響其他職類的判斷。',
          [own,*team,'來源教案的流程、給付與門診安排屬歷史情境；實際運作須核對院內現行版本。'],['哪些資料由自己蒐集？哪些需要向其他職類確認？','不要把影像資料、身體功能與營養資料當成同一項評估。'],
          '選一位合作職類，說明您要交付的資料、要請對方回答的問題及分工。'),
         lesson(2,'handoff','交接、回覆確認與共同計畫','由單向報告進一步形成可追蹤的協作。',
          ['S：目前狀況；B：相關背景；A：本職類評估；R：具體需求與追蹤。','接收者回述關鍵資訊，雙方確認負責者與回覆時間。','將個案偏好納入團隊計畫，未確認的資料明示待查。'],
          ['對方是否知道您要他協助什麼？','回覆是否真的解決原先資訊缺口？'],
          '寫出一段交接及接收者的確認回覆，標出仍未解決的問題。')],
      3:[lesson(3,'video','一般影片：觀察完整照護流程','將書面知識對照影片中的真實言語、動作與順序。',
          ['可播放本主題的一般影片，無須360格式。','先完整觀看，再以步驟索引定位準備、執行、解釋與交接。','鏡頭切換與教材字幕不等於病人動作；需保留上下文。'],
          ['每一步誰在做什麼？','先前的說明是否足以讓病人執行？','示範後是否讓病人實作並確認理解？'],
          '記下兩個影片時間點，描述可見行為，並說明前一步如何支持後一步。',media_ids=[c['id'] for c in normal]),
         lesson(3,'purpose','由影片理解步驟目的','把「看到什麼」連到「為何需要這一步」。',
          ['依影片步驟解說核對行為目的；先說依據，再保留其他解釋。','對照教案目標與職類分工，區分已完成、未顯示與仍需補查。'],
          ['動作之前的指令與之後的回應。','影片示範是否等於已確認病人學會？'],
          '選一個步驟，寫出動作、目的、觀察證據及尚不能下結論的部分。')],
      4:[lesson(4,'space','環景場域：位置、視角與安全資訊','把單一鏡頭的流程擴展成空間中的團隊觀察。',
          ['在360播放器轉向不同位置，辨認人物、器材、出入口與視線遮擋。','不同視角可能看見不同資訊；記下時間與視角供其他人重看。','環景素材尚未核定為本輪同一病人時，不把畫面內容併入本輪病歷。'],
          ['誰能看見目前操作？誰的視線被遮擋？','交接是否到達真正接收者？','有沒有必須換視角才能確認的資訊？'],
          '記錄兩個視角及其資訊差異，說明可能影響哪一項決策。'),
         lesson(4,'coordination','跨域場域的決策與協調','將空間線索連結到人員分工與資訊流。',
          [*team,'對於看不到或聽不清楚的行為，提出要向誰、用何種方式確認。'],
          ['與Level 2書面交接相比，現場增加了哪些限制？','有沒有兩位成員各以為對方會處理的任務？'],
          '提出一個場域資訊缺口、負責確認的人及完成確認後的下一步。')],
      5:[lesson(5,'frames','逐格切割：準備、執行與結束','用每張原圖和骨架觀測核對動作細節。',
          ['一般與360影片皆可選區間，按原始幀率逐張解碼；可以切換原圖與骨架疊圖。','以動作片段與教案步驟定位，不把整段影片只概括成一個動作。','遮擋或無可靠骨架時保留原圖與步驟解說，不補造關節。'],
          ['動作開始前的姿勢、執行中變化與結束時的回應。','哪些是可見關節證據？哪些需要聲音、器材或人員說明？'],
          '選取一個影格保存觀察，說明它位於哪個步驟、動作特徵與判讀限制。',media_ids=[c['id'] for c in normal]),
         lesson(5,'explanation','動作目的、替代判斷與教師解析','為熟練學員增加判斷依據，而非只給骨架數值。',
          ['教案步驟解說提供動作目的、觀察焦點、常見誤判與需核對資訊。','教案目的與機器推測分開：同一抬手、彎膝可有多種用途。','保存影格、影片與模型版本，將自己的判斷交由教師回饋，再回看修正。'],
          ['是否只從一張圖就推斷意圖？','是否用同一段前後影格與聲音確認？','教師建議補充的證據是否已找到？'],
          '比較原判讀與教師回饋，說明您改變判斷的證據，以及仍保留的可能解釋。')]
    }
    return [{'level':n,'title':title,'unlocked':learning_level>=n,'lesson_count':len(content[n]),
             **({'lessons':content[n]} if learning_level>=n else {})} for n,title in enumerate(TITLES,1)]
