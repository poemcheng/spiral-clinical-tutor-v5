"""Teaching annotations from supplied lesson/checklist and reviewed video sections.

These are explicit authored teaching context, never a pose model's intent labels.
Clinical approval remains separate. Original recordings/transcripts stay private.
"""
import hashlib,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
STEPS=[
 ('intro','閱讀任務與情境','辨識本次照護任務及待確認資訊。','先讀題、查看病歷與任務告示，再進入互動。',['分清楚教案背景與實際取得的資料。'],'讀題動作不等於已完成臨床評估。'),
 ('dxa','與放射師確認DXA資訊','向資料提供職類核對報告與限制，避免只憑單一數值下結論。','觀察持電話、查看報告、提問及回述的順序。',['提出比較兩次資料的具體問題。','記錄對方回覆與仍缺少的功能資料。'],'接聽電話的骨架不能證明交接內容完整，須聆聽對話。'),
 ('opening','身分確認、需求與疑慮','建立正確對象與此次共同目標，了解病人的挫折。','觀察面向對方、身分詢問、就診目的與病人回應。',['提問後是否留時間讓對方回答？','是否先聽懂努力未見改善的疑慮？'],'點頭、微笑或視線方向不能單獨證明同理或理解。'),
 ('prepare','坐站測試前的指令與示範','讓受測者了解起止姿勢、動作次數與計時方式，建立可比較的測試條件。','觀察座椅、雙腳、手臂位置與示範說明。',['本片示範雙手交叉胸前；核對是否有上肢支撐或其他改動。','確認是否聽懂口令，再辨識準備與正式計時的差別。'],'本片與原始文字可能有姿勢描述差異；測試規範及必要調整由教師核定。'),
 ('sitstand','連續坐下與站起的執行','用標準化動作過程觀察坐站轉位與下肢功能，並保留動作策略。','逐格看坐姿、軀幹前移、離椅、站直、下降及再次接觸座椅。',['區分每次起立與坐下，觀察有沒有扶手、停頓或協助。','以原始影片時鐘核對口令和完整次數，不用單張圖推算總時間。'],'二維膝角不能當實際關節角度；一次彎膝不代表已完成一次坐站。'),
 ('explain','說明測試結果並回應疑慮','把觀察到的結果轉為病人可理解的資訊，接續釐清運動與生活情境。','觀察說明結果、病人提問、查看衛教單與再次澄清。',['是否把測試結果與完整診斷分開？','病人提出疑問後，說明是否有跟著調整？'],'影片中的時間或說法不是所有族群的診斷標準；採用版本須由教師核定。'),
 ('demonstrate','坐姿下肢動作示範','把口頭衛教轉為可見的動作範例，說清楚起始、維持與結束。','觀察坐姿調整、伸膝抬腿、維持與放下。',['比較示範者與病人看到的角度。','核對口語指令與可見動作是否一致。'],'本片的次數與維持時間是案例示範，不自動成為每位病人的處方。'),
 ('return-demo','病人回做與即時修正','透過病人實際重做確認是否理解，而不是只問「懂了嗎」。','比較示範前後的腿部位置、支撐、維持與治療師提醒。',['病人是否自行做出動作？','治療師回饋後，下一次動作有沒有改變？'],'完成一次動作不等於已會獨立安全執行；不可用痠痛作為效果或安全的唯一依據。'),
 ('exercise','姿勢、上肢及其他動作衛教','將不同動作分開示範，讓病人辨識姿勢、呼吸及動作順序。','逐格看坐姿、手臂抬起與放下；回看衛教單及前後指令。',['分清楚示範、口頭描述與病人回做。','找出哪個細節需要再示範或確認。'],'畫面未呈現的動作不能補成已完成；疼痛或異常不適需停止並由專業人員評估。'),
 ('nutrition','了解飲食說法與轉介理由','辨識本職類評估之外仍需營養專業協助的資訊缺口。','觀察病人描述飲食、治療師追問及說明轉介理由。',['「有吃肉喝奶」是否已交代份量、頻率與其他生活情境？','是否讓病人理解轉介與原來問題的關係？'],'骨架不能辨識攝取量或營養是否足夠，不從表情推測依從性。'),
 ('referral','與營養師確認接續照護','將轉介變成可執行的接續安排，確認接收職類與所需資訊。','觀察電話聯繫、整理資訊、確認安排與回覆病人。',['是否交代需求，而非只問時間地點？','接收者是否回覆，病人是否知道下一步？'],'影片中的門診時間與行政安排僅屬當時案例，不代表現行服務資訊。'),
 ('closing','共同確認後續計畫','在結束前確認回家練習、接續照護與追蹤的理解。','觀察交付資料、說明下一步與病人回應。',['請以回述或實作確認理解。','區分說完計畫與對方確實知道如何執行。'],'影片中的給付次數、期限及門診安排需另查核，不當成最新政策。'),
 ('feedback','教師回饋與學員反思','把實際行為、依據與改進方向連在一起。','對照教師指出的片段，再回看學員原來的行為。',['回饋是否提供具體行為與改進方法？','自己的判讀是否被前後脈絡支持？'],'影片內歷史milestone評語不是目前登入學員的正式分數。'),
]
TIMES={
 'course-sarc-video':[0,35,92,124,150,175,216,234,257,295,337,366,410,495.261438],
 'sarc-analysis':[0,27,90,115,145,167,207,224,243,285,329,357,409,477.791667],
}

def main():
    source=ROOT.parent/'AI醫學教案/AI醫學教案/肌少症運動處方之全人照護.docx'
    doc_hash=hashlib.sha256(source.read_bytes()).hexdigest()
    refs=[{'title':source.name,'sha256':doc_hash,'location':'考生任務、評分項目及場景一至三'},
      {'title':'Five Times Sit to Stand Test / RehabMeasures','url':'https://www.sralab.org/rehabilitation-measures/five-times-sit-stand-test'},
      {'title':'NIDDK Health Tips for Older Adults / exercise safety','url':'https://www.niddk.nih.gov/health-information/weight-management/healthy-eating-physical-activity-for-life/health-tips-older-adults'}]
    videos={}
    for video,times in TIMES.items():
        videos[video]=[{'id':key,'start':times[i],'end':times[i+1],'title':title,'purpose':purpose,'explanation':description,
          'observe':observe,'pitfall':pitfall,'sources':refs,'review_status':'已核對影片段落及來源教案；教學解說草稿，待職類教師正式核定',
          'scope':'此為段落教學目的，不宣稱本段每一張圖皆在執行同一動作；逐格觀測與意圖假設另列。'} for i,(key,title,purpose,description,observe,pitfall) in enumerate(STEPS)]
    p=ROOT/'data/action_lessons/sarcopenia_steps.json'
    catalog=json.loads((ROOT/'data/action_lessons/media_catalog.json').read_text(encoding='utf-8'))['clips']
    hashes={c['id']:c['source_sha256'] for c in catalog if c['id'] in videos}
    p.write_text(json.dumps({'version':'action-teaching-5.3.2','video_sha256':hashes,'videos':videos},ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({'videos':len(videos),'steps_per_video':len(STEPS)}))
if __name__=='__main__':main()
