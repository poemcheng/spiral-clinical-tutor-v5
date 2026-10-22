# 迴旋梯智鏈 v5.3.1

中山醫學大學附設醫院醫事智慧訓練平台第五版，依2026-10-22需求自4.5.1修訂。

- 本機語音辨識與對話，無須先連LiveKit；three.js診間、四部VR360及可環顧講師教案。
- 12職種獨立核心指標、自評雷達圖、弱項成果及文獻對照。
- Demo配對：放射師／營養師→物理治療師；物理治療師／醫師→病患；護理師→病患＋物理治療師。
- 自評Level決定互動難度；累積學習Level獨立開放單職類知識、團隊知識、情境影片、360視角與逐格分析。
- 13位擬真人物，含醫事人員男女、高齡男女、中年男女及醫事放射師。
- 保留六階段流程、角色權限、來源快照及教師正式覆核；本地Ollama提供案例約束角色對話。

[5.3.1逐格骨架、互動難度與操作影片](docs/v5.3/逐格動作與互動修正版_20261023.md) · [會議需求核對與v5.3更新](docs/v5.3/會議需求核對與持續改善_20261022.md) · [5.2立體角色與自動語音驗證](docs/v5.2/立體角色與語音驗證.md) · [5.1語音與沉浸更新](docs/v5.1/語音與沉浸式更新.md) · [需求與版本差異](docs/v5/第五版差異與需求對照.md) · [部署操作](docs/v5/部署說明.md) · [文獻對照](docs/v5/職種指標文獻對照.csv) · [歷史v5.0導覽（不含新骨架與回饋流程）](https://github.com/poemcheng/spiral-clinical-tutor-v5/releases/download/v5.0.0/v5-operation-guide.mp4)

## 啟動

從GitHub下載或clone後先安裝Python依賴，再取得有SHA256檢查的公開執行素材：

```sh
python -m pip install -r requirements.txt
python tools/fetch_release_assets.py
python tools/prepare_voice.py
python -m pip install -r requirements-pose.txt
python tools/setup_pose.py
npm ci
npm run build
```

Windows雙擊 `run_windows.bat`，本機網址為 **http://127.0.0.1:8705**。首次本機管理員為user／1234，既有帳密不重設；學員及教師由管理員建立。從4.5.1本機升級時原始資料夾保留，移轉前須使用一致性備份。

公開主機使用Docker Compose及獨立強密碼、HTTPS、持久化儲存，詳見[部署說明](docs/v5/部署說明.md)。GitHub Pages不能執行Python後端與Ollama。本儲存庫是可部署程式碼，沒有宣稱此GitHub網址本身已執行完整後端。

## 素材與範圍

公開素材包含人物、前端執行套件及衍生教學資料，不含學員資料、資料庫、密碼、來源PDF／Excel、實拍影片或360代理影片。教材管理者另提供其授權的教材檔案；缺少媒體時介面會明示。四支本機360影片可在選定視角與區間執行逐格骨架分析；關節可見性、二維投影角度、動作片段及意圖候選與替代解釋供學員判讀。情境、職類視角與臨床標準解析仍待教師核定。

指標與題目為平台依職類框架改編的教學草稿，數量與自評切點是本系統課程設計；不宣稱為經驗證量表、臺灣執業標準或院方正式核定成果。自評、客觀練習及教師核定分開保存。

完整操作影片在本機交付的 `docs/v5.3/v5.3.1-operation-guide-local.mp4`，示範學員分析、教師回饋及學員查看；含授權實拍教材畫面，未放入公開素材包。從公開原始碼安裝時，素材下載維持相容的v5.3.0基礎包，再以上述npm指令編譯目前版本。Windows角色語音優先使用PowerShell 7及已安裝的繁體中文男女聲；缺少對應性別會明示錯誤。

## 開發與驗證

```sh
npm ci
npm run build
python -m unittest discover -s tests -v
```

本機Python 71項與前端5項測試通過。新增Level 5教師逐格觀察回饋、不可覆寫的歷史、影片版本快照，以及學員端回饋顯示；不改變正式分數及Level。13位角色使用CC0 MakeHuman立體網格、163骨架與8種表情，不再以平面人像螢幕呈現。瀏覽器已完成兩輪真實MediaRecorder錄音→Whisper辨識→gemma4:12b案例回覆→中文TTS播放→接續收音的自動測試；音源為明示的合成測試語音，未測實體麥克風。實際gemma4:12b已驗證放射師→物理治療師兩輪對話；另以合成學員實際完成8輪訓練後，瀏覽器驗證自評Level2與累積Level5、360視角、逐格定位及紀錄保存。證據在 `docs/v5/`。操作導覽由實際操作截圖組成，非連續錄影。

Docker Compose設定解析通過，但本機Docker Linux引擎未啟動，尚未完成容器建置及雲端推論驗收。Linux目前支援文字互動與既有影片；中文TTS與虛擬講師即時合成仍依賴Windows。

職類框架來源、版本與限制見[文獻核對紀錄](docs/v5/literature-search-log.json)；院徽來源見 `frontend/assets/hospital-logo-source.json`。素材與框架各自保留其權利；公開此程式碼不表示取得對第三方素材的額外授權。
