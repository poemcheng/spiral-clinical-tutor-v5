"""Build the v5.3.2 local guide without altering the historical guide."""
import json
import shutil
import build_operations_guide as guide

guide.PROJECT=guide.ROOT/'runtime/guide-v5.3.2'
guide.SOURCE=guide.ROOT/'runtime/verification-5.3.2'
guide.SHOTS=[
('skeleton-patient.png','從肌少症動作開始','這一步為什麼做','一般影片也能逐格分析','這次使用肌少症的一般影片，示範如何從每張影像、教案目的與前後動作，形成可供教師回饋的判斷。',8,None),
('five-levels.png','學員｜五級累積教案','每一級都有新內容','1單一職類 → 2跨域 → 3影片 → 4環景 → 5逐格','教材依第一到第五級逐步增加，前級內容持續保留。互動自評與教材等級分開，本例自評第二級，已解鎖第五級教材。',10,None),
('level2-curriculum.png','學員｜持續學習知識','跨域教案也能反思','讀目的、知識、觀察問題，再保存判讀','例如第二級有跨域合作知識與交接判讀。閱讀教案後，保存自己的依據與待確認資訊，教師可在訓練紀錄中查看。',8,None),
('step-index.png','學員｜選擇一般影片','用步驟定位行為','兩部肌少症影片各有13個步驟','選擇一般影片，展開行為步驟索引。兩部肌少症影片各有十三個步驟，從任務、評估、動作示範、回做，一直到交接與教師回饋。',10,None),
('step-purpose.png','學員｜先讀動作目的','坐站要看完整過程','準備 → 前移 → 離椅 → 站直 → 坐回','點選坐站執行段，先讀目的、動作解說與觀察焦點。逐格看準備、軀幹前移、離椅、站直與坐回，不能用單張膝角判定完成品質。',10,None),
('patient-roi-form.png','學員｜指定人物與區間','核對要觀察的人','本例145至167秒，選患者所在範圍','多人同框時，先核對畫面，再選患者所在範圍。本例分析第一百四十五到一百六十七秒；也可選取完整影片，單次最長一千八百秒。',10,None),
('normal-video-frame-analysis.png','學員｜逐張解碼與分析','本例完成528張','24 fps · 一般影片原畫面','完成後，本例共有五百二十八張影格。上一格、下一格與滑桿可逐張查看，骨架顯示模型估計，取消勾選可核對本張原圖。',10,None),
('skeleton-patient.png','學員｜核對動作與意義','骨架與目的分開看','可見關節＋步驟解說＋其他可能解釋','綠線與黃點是可見骨架估計。教案另提供步驟目的與解說；機器產生的可能意圖，仍須核對前後畫面、器材及現場語音。',10,None),
('learner-note-draft.png','學員｜保存自己的判讀','寫下動作依據','保存影格、步驟與觀察給教師','在本格動作與目的判讀，寫下影像依據與不確定性，再按保存給教師。系統保留影格、步驟、來源與模型版本，供後續覆核。',10,None),
('teacher-normal-review.png','教師｜核對原片與骨架','回看前後動作和口令','工作台 → 同筆訓練 → 完整分析','教師從工作台開啟同一筆訓練，查看原始觀察，並開啟完整分析。骨架與原片並排，可逐格核對，也可播放前後動作和現場語音。',10,None),
('teacher-feedback.png','教師｜保存具體建議','指出還需要哪些證據','本例補看離椅、站直、坐回與支撐','教師選擇回饋狀態並保存具體建議。本例要求補上離椅、完全站直及再次接觸座椅的影格，說明支撐情況，並核對原始口令。',10,None),
('learner-feedback.png','學員｜查看回饋再修正','讓判斷持續累積','保留原判讀與教師回饋歷程','學員回到影片學習，在原觀察下查看教師建議，再補充證據與反思。這些是形成性學習紀錄，教學解析草稿仍待職類教師正式核定。',10,None),
]

if __name__=='__main__':
    guide.build()
    for name in ('index.html','SPEC.md'):
        path=guide.PROJECT/name
        path.write_text(path.read_text(encoding='utf-8').replace('v5.3.1','v5.3.2'),encoding='utf-8')
    ledger_path=guide.PROJECT/'capture-ledger.json'
    ledger=json.loads(ledger_path.read_text(encoding='utf-8'))
    for scene in ledger['scenes']:
        scene['contains_private_footage']=True
    ledger_path.write_text(json.dumps(ledger,ensure_ascii=False,indent=2),encoding='utf-8')
    (guide.PROJECT/'STORYLINES.md').write_text('採用：以肌少症坐站動作為例，從逐級教案到逐格判讀、教師核對與學員回看。使用者已要求操作影片，直接完成。\n其他方向：從教師的一則回饋倒推學員證據；以五級教材展開一趟課程地圖。\n',encoding='utf-8')
    with (guide.PROJECT/'SPEC.md').open('a',encoding='utf-8') as f:
        f.write('SCOPE: 一般影片與五級累積教材；12段真實UI擷取，非連續錄影。旁白延續前版教學導覽規格。無配樂，以保留專業教學語句辨識度。不得宣稱兩部影片已全長完成骨架驗證。\n')
    guide.build_export()
    shutil.copyfile(guide.PROJECT/'guide.zh-TW.srt',guide.ROOT/'docs/v5.3/v5.3.2-operation-guide.zh-TW.srt')
