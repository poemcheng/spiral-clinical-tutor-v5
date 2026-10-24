"""Author teaching context from supplied EPA references and reviewed video frames.

Annotations describe segment context, never claim framewise intent ground truth.
All output stays in the private EPA runtime library.
"""
from pathlib import Path
import hashlib,json,sys
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from backend import teaching_media
LIB=ROOT/'runtime/epa_library'
COMMON='畫面動作不單獨證明理解、信賴、同理或資訊閉環；須聽前後語音、確認對方回應及教師覆核。'
def segment(ident,start,end,title,action,dialogue,relation,category,focus,purpose,dimensions=(),limitation=COMMON):
    return {'id':ident,'start':start,'end':end,'title':title,'visible_action':action,'dialogue_function':dialogue,'action_dialogue_relation':relation,'category':category,'epa_focus':focus,'purpose':purpose,'dimensions':list(dimensions),'limitation':limitation,'evidence_type':'來源教案與代表畫面抽查之段落教學脈絡；對話功能非逐字稿，邊界為教學定位用近似時間'}
def main():
    reference=json.loads((LIB/'reference_epa.json').read_text(encoding='utf8'));clips={};media={c['id']:c for c in teaching_media.manifest()['clips']}
    sources=reference['sources'];status='已核對來源欄位及代表畫面；教學解析草稿，臨床內容與EPA評量仍待職類教師核定'
    clips['epa-bedside']={'segments':[{**s,'limitation':COMMON+' 原始報告的安撫、信任與閉環描述為待核對的功能性解釋，不是已驗證成效。'} for s in reference['segments']],'keyframes':reference['keyframes'],'sources':sources,'status':status}
    sarc=json.loads((ROOT/'data/action_lessons/sarcopenia_steps.json').read_text(encoding='utf8'))
    categories={'intro':'作業準備','dxa':'跨專業溝通','opening':'臨床評估／衛教互動','prepare':'衛教互動／安全準備','sitstand':'臨床評估／身體動作','explain':'衛教互動','demonstrate':'衛教互動／動作示範','return-demo':'臨床評估／回做','exercise':'衛教互動','nutrition':'臨床評估','referral':'跨專業溝通','closing':'衛教互動／收尾','feedback':'團隊反思'}
    dialogues={'intro':'確認任務與資料（需聽原片核對）','dxa':'檢查資料確認與跨職類詢問','opening':'開場、辨識與需求詢問','prepare':'指令說明、示範與理解確認','sitstand':'執行口令、回應與安全提醒','explain':'結果說明與疑問澄清','demonstrate':'動作與順序說明','return-demo':'回做、即時提示與確認','exercise':'衛教工具說明與動作引導','nutrition':'飲食說法與轉介理由釐清','referral':'轉介、接收與安排確認','closing':'摘要與下一步理解確認','feedback':'行為回饋、反思與改善計畫'}
    for clip_id,steps in sarc['videos'].items():
        segs=[]
        for s in steps:
            dims=['TC'] if s['id'] in ('dxa','referral') else ['TC','SAFE'] if s['id']=='feedback' else ['PC','SAFE'] if s['id'] in ('prepare','sitstand','return-demo') else ['COM','HC']
            segs.append(segment(s['id'],s['start'],s['end'],s['title'],s['explanation'],dialogues[s['id']],s['purpose'],categories[s['id']],'；'.join(s['observe']),s['purpose'],dims,s['pitfall']+' '+COMMON))
        clips[clip_id]={'segments':segs,'keyframes':[{'id':f'KF{i+1:02}','seconds':round((s['start']+s['end'])/2,3),'title':s['title'],'visible_action':s['visible_action']} for i,s in enumerate(segs)],'sources':[{'file':'EPA_擬真教案影片_行為分析資料表.docx','sha256':next(x['sha256'] for x in sources if x['file']=='EPA_擬真教案影片_行為分析資料表.docx')},{'file':'sarcopenia_steps.json','sha256':hashlib.sha256((ROOT/'data/action_lessons/sarcopenia_steps.json').read_bytes()).hexdigest()}],'status':status+'；未直接沿用來源表中與實際版本不符的4分坐站等時間點'}
    rows={
      'course-stroke-video':[
       (0,30,'需求與背景資料','床邊人員面向對方，畫面交替出現背景文字與團隊站位。','家屬需求與背景澄清','先取得需求，再區分口頭說法與既有檢查。','作業準備／臨床評估','確認需求來源及尚缺資料，不從站位推定已完成評估。','理解照護需求與資訊起點',['COM','CJ']),
       (30,120,'吞嚥資訊與跨團隊說明','白袍人員持文件面向團隊，其他人員位於床側與後方。','檢查資訊說明與跨職類提問','持板、指示與面向對方提供說明線索；須聽語音核對檢查內容。','跨專業溝通','區分報告說明與實際做過吞嚥檢查；核對下一步責任。','建立跨團隊共同理解',['TC','CJ']),
       (120,220,'營養狀況與支持討論','團隊維持站姿，前景人員持板或筆示意，其他成員看向發言者。','營養資訊澄清與支持討論','資料板、手勢與輪替發言可支持資訊交換，完整性仍需語音確認。','跨專業溝通／臨床評估','核對資料來源、接收者回述及未回答的問題。','把吞嚥限制與營養資訊連結',['TC','CJ']),
       (220,450,'對家屬的衛教與工具說明','兩位前景人員與家屬面對面，展示紙本或圓盤型工具，家屬有指向與持物回應。','衛教說明、提問與理解確認','共同觀看工具及家屬持物是可見互動，是否理解仍需回述。','衛教互動','不要把點頭、持物當成已理解；區分展示與家屬自行操作。','以具體工具支持家屬參與',['COM','HC']),
       (450,561.127233,'跨專業考官回饋','數位人員坐姿持板，視線與手勢轉向發言者。','行為回饋、反思與後續建議','輪替發言、筆記與指出資料有助反思；是否有共同計畫須聽語音。','團隊反思','記錄具體行為證據、改善方向與下次觀察方式。','將照護互動轉為可執行的學習回饋',['TC','HC'])],
      'course-icu-video':[
       (0,40,'入室與背景核對','人員在門口閱讀資料並入室，之後顯示背景說明文字。','任務與背景確認','先查核資料再進入床邊溝通，畫面不證明資料已核對正確。','作業準備','確認資料版本、身分與評估目的。','建立床邊討論所需背景',['CJ','SAFE']),
       (40,80,'床邊營養資料詢問','白袍學員手持板與筆，與主護站在床旁，後方有人記錄。','詢問、回覆與初步摘要','持板、書寫與面對面輪替支援資訊整理。','臨床評估／跨專業溝通','區分由主護提供的資料、尚缺數據與推估。','蒐集足以討論營養照護的資料',['TC','CJ']),
       (80,160,'營養介入與床邊協作','學員查看或書寫文件，主護以手勢回應，病床位於旁側。','介入方向與照護限制討論','查閱、紀錄及回應要與語音核對，不能由手勢推定處方已執行。','跨專業溝通','核對介入依據、限制、監測指標與回報方式。','將資料轉為可交接的照護討論',['CJ','TC','SAFE']),
       (160,200,'家屬加入討論','家屬角色站於前景側方，學員轉向持板說明，主護同場。','回應家屬疑慮與說明計畫','站位改變對象後需重新確認理解與資訊界線。','衛教互動／情緒支持','先聽疑慮，再核對家屬能理解的說明。','讓家屬參與照護溝通',['COM','HC']),
       (200,260,'醫護與營養交接','新增白袍人員與主護、學員在床側討論，學員持板發言。','摘要、交班與下一步確認','多人發言與文件共享支持交接，但責任閉環需要語音確認。','跨專業溝通','明列負責者、要監測的資訊與何時回報。','練習完整且可追蹤的團隊交接',['TC','SAFE']),
       (260,329.1288,'考官回饋與反思','學員與考官坐姿持板，面對面交談。','回饋、提問與改善確認','持板、聆聽與回應可供比較先前床邊行為。','團隊反思','回饋指向具體行為，避免只給總評。','形成下次練習的具體方向',['TC','HC'])],
      'course-dm-video':[
       (0,18,'片頭與案例標題','標題字卡與素材畫面，尚未顯示完整醫病互動。','情境介紹，非病人對話證據','片頭提供課程背景，不作臨床動作評分。','作業準備','不要把字幕或圖卡當作人物已執行的行為。','辨識本片情境與學習任務',['CJ']),
       (18,75,'病人提出旅遊疑慮','兩人在桌面旁坐姿交談，一方持文件或筆，對方以手勢回應。','疑慮表達與需求澄清','坐姿、手勢與文件可供定位提問，焦慮程度不能只由姿勢判斷。','臨床評估／情緒支持','先確認病人關注點，避免從表情直接下心理結論。','辨識轉介與營養諮詢的原因',['COM','HC']),
       (75,195,'營養門診資料收集','營養師角色與病人坐姿面談，桌上有紙本、筆及圖卡，持續交替查看與手勢說明。','飲食與旅遊資訊詢問、摘要確認','查表、書寫與問答相互配合，資料完整性需語音核對。','臨床評估','缺少份量、時間或情境時明列待查，不從骨架推估攝取量。','建立個別化討論的資訊基礎',['CJ','COM']),
       (195,320,'醫師與藥師電話協調','學員持電話或手機近耳、低頭查看文件，畫面有跨職類通訊提示。','跨職類確認與回報','電話姿勢可見，但電話內容、接收者與安排要以語音及來源確認。','跨專業溝通','不能由電話畫面推定已獲處方授權或用藥調整完成。','連結不同職類的專業責任',['TC','SAFE']),
       (320,485,'旅遊飲食工具與調整討論','桌面圖卡與文件被指示或移動，雙方輪替查看並以手勢回應。','用具體工具說明、練習與理解確認','共同操作圖卡可作學習線索；需看病人是否能獨立回述與應用。','衛教互動','劑量、代換量與用藥安全依個案與教師核定，不由影格產生處方。','將抽象原則轉為可討論的旅遊情境',['CJ','COM','SAFE']),
       (485,555,'跨職類考官回饋','四人圍坐，手持板或文件並輪替發言。','回饋、反思與改進協商','多方視線與資料支援討論，是否形成具體行動需核對原音。','團隊反思','區分肯定、具體行為證據與下一步建議。','整合多職類回饋修正照護溝通',['TC','HC']),
       (555,573.539633,'片尾與製作資訊','結束圖卡與團隊合照，非持續臨床操作。','片尾資訊，非新增會談證據','結束素材不用作病人行為或學員能力推論。','作業結束','不辨識畫面人物真實身分，不將字幕姓名寫入模擬病歷。','辨識影片情境與評量證據的範圍',[])],
    }
    source_file=ROOT/'data/video_lessons/video_lessons.json';source_hash=hashlib.sha256(source_file.read_bytes()).hexdigest()
    for clip_id,values in rows.items():
        segs=[segment(f'S{i+1:02}',*row) for i,row in enumerate(values)]
        clips[clip_id]={'segments':segs,'keyframes':[{'id':f'KF{i+1:02}','seconds':round((s['start']+s['end'])/2,3),'title':s['title'],'visible_action':s['visible_action']} for i,s in enumerate(segs)],'sources':[{'file':'EPA_擬真教案影片_行為分析資料表.docx','sha256':next(x['sha256'] for x in sources if x['file']=='EPA_擬真教案影片_行為分析資料表.docx')},{'file':'video_lessons.json','sha256':source_hash},{'file':media[clip_id]['file'],'sha256':media[clip_id]['source_sha256']}],'status':status+'；未沿用來源表中不符合實際字卡階段的時間範圍'}
    # This supplied short video has illustrated teaching overlays. Production
    # method is not verified, so it is never labelled an actual patient recording.
    health=[('低信賴開場','兩位角色坐姿面談，病人角色抱持檢查單。','先聽疑慮與回應挫折'),('了解生活說法','雙方交替看向對方與桌面資料。','詢問病人的理解與目前做法'),('檢查資料解釋','以檢查單及圖卡共同查看資訊。','分開解釋檢查資訊與尚缺評估'),('份量與頻率澄清','角色展示飲食紀錄板並以手勢指示。','補足飲食份量與頻率'),('熱量與飲食分配','桌面資料支援問答與說明。','將營養原則連到生活情境'),('運動與飲食協調','角色查看衛教圖卡並交替手勢。','核對活動與進食安排'),('蛋白質需求解釋','角色持蛋白質示意板，對方看向資料。','用白話說明，不由圖卡產生個人處方'),('替代選擇','角色共同查看食物與代換資料。','協商可接受的改變'),('回述與確認','角色輪替說話與手勢回應。','用自己的話確認計畫，不由點頭斷定理解'),('共同決策與結尾','角色面對面，資料置於桌上。','確認可執行的下一步與追蹤')]
    duration=media['health-education']['duration'];segs=[]
    for i,(title,action,purpose) in enumerate(health):segs.append(segment(f'S{i+1:02}',i*duration/10,(i+1)*duration/10,title,action,'衛教說明與回應（依畫面教學字幕摘要，非逐字稿）','以文件、手勢及輪替說明支持教學；真實理解與合作不可由單張圖確認。','衛教互動',purpose,purpose,['COM','HC'],'本片製作方式與角色來源待核對，不標為實際病人錄影；分段為十個等長教學導覽區間，需核對字幕切換。'))
    clips['health-education']={'segments':segs,'keyframes':[{'id':f'KF{i+1:02}','seconds':(s['start']+s['end'])/2,'title':s['title'],'visible_action':s['visible_action']} for i,s in enumerate(segs)],'sources':[{'file':media['health-education']['file'],'sha256':media['health-education']['source_sha256']}],'status':status+'；此片不宣稱為真人實拍'}
    vr={1:('人員坐姿面向操作螢幕，手臂靠近桌面；側方可見其他螢幕與器材。','觀察操作場域中的人員位置、資訊來源與可見性。'),2:('坐姿對話者位於窗側，部分影格可見抬手靠近頭側；人物與器材可能在視野邊緣。','核對對話者的回應、場域限制與還需換視角的資訊。'),3:('桌面兩側可見白袍人員與對話者，雙方坐姿面向對方，間有文件或器材。','觀察文件、手勢與輪替發言如何支持說明與確認。'),4:('桌面兩側人員坐姿交談，白袍人員面向對方，旁有電腦螢幕。','比較操作資訊與面對面溝通的注意力分配。')}
    for i,(action,purpose) in vr.items():
        clip_id=f'team360-{i}';c=media[clip_id];duration=c['duration'];segs=[segment('S01',0,min(5,duration),'場域與拍攝準備','開始區間可能出現場記板或人員調整，與後續固定視角分開核對。','錄影準備，不推定臨床對話','場記與入鏡準備不作臨床能力評分。','作業準備','先辨認錄影起點與本視角涵蓋範圍。','建立時空定位',[]),segment('S02',min(5,duration),duration,'固定視角的場域互動觀察',action,'對話功能尚待原音與教師確認；不提供虛構逐字稿',purpose,'場域互動／待核定','不從服裝推定真實職類；視線、器材細節與畫面外行為須換視角確認。',purpose,[],COMMON+' 本片情境與職類配對未核定；固定視角並非全向分析。')]
        clips[clip_id]={'segments':segs,'keyframes':[{'id':f'KF{k+1:02}','seconds':t,'title':'固定分析視角代表格'} for k,t in enumerate([1,duration/3,duration*2/3,duration-2])],'sources':[{'file':c.get('source_file',c['file']),'sha256':c['source_sha256']}],'status':status+'；環景個別情境、職類與互動功能尚未核定'}
    data={'version':'epa-annotations-5.6.1','minimum_learning_level':4,'not_formal_epa_assessment':True,'clips':clips}
    temp=LIB/'annotations.tmp';temp.write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf8');temp.replace(LIB/'annotations.json')
    print(json.dumps({'clips':len(clips),'segments':sum(len(c['segments']) for c in clips.values()),'keyframes':sum(len(c['keyframes']) for c in clips.values())}))
if __name__=='__main__':main()
