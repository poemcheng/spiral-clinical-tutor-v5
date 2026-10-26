# 知其然・知其所以然｜電腦圖學合作學習平台

這個改編版本將迴旋梯智鏈的六階段訓練與證據覆核框架，轉為 **CATIA 零件建模、組合設計及自選專題**。依授課教師的合作學習單設計，強調「我如何操作」與「為何如此設計」的雙重證據。原醫事版原始碼與歷史保留，沒有遷移任何臨床紀錄。

> 此版本在 `codex/graphics-teaching-practice` 分支。請先切換至此分支，再安裝／執行；原 `main` 仍為醫事版本。

## Windows 啟動

安裝 Python 3.11 以上，切換至本分支後雙擊 **`run_windows.bat`**（亦可用 `run_graphics_windows.bat`）。第一次建立獨立 `.venv-graphics` 環境，只安裝電腦圖學所需套件，不必下載臨床影音、Whisper或角色模型。

```sh
git clone --branch codex/graphics-teaching-practice https://github.com/poemcheng/spiral-clinical-tutor-v5.git
cd spiral-clinical-tutor-v5
python -m pip install -r requirements-graphics.txt
python -m uvicorn backend.graphics_server:app --host 127.0.0.1 --port 8715
```

開啟 **http://127.0.0.1:8715**。首次管理員帳密保存在本機 `runtime/graphics/initial-admin.txt`，請由管理者保管。密碼隨機產生，不提供公開共用帳密。既有帳號不會因重啟被重設。

Linux/macOS 可執行 `sh run_graphics.sh`。介面使用系統中文字型，不載入第三方CDN；不需 Node 建置即可運行。

## 教學核心

| 原醫事框架 | 電腦圖學用途 |
|---|---|
| 職種與情境 | 零件建模、組合設計、自選專題 |
| 跨專業角色 | 協調、建模策略、設計稽核、紀錄、AI鷹架角色輪替 |
| 病例與關鍵決策 | 功能、基準、特徵、尺寸依存與約束決策 |
| 病患對話與SBAR | 設計意圖說明、策略對照與模型交接 |
| 臨床安全補強 | 尺寸擾動、模型互換、自由度與干涉檢核 |
| 自評／學習／正式核定分開 | 信心自評／支持強度／練習題／教師核定分開 |
| 教師來源覆核 | 對照原始模型、截圖、作答與版本的構面覆核 |

六階段：**自評前測 → 任務規劃 → 個人建模 → 合作互換與AI檢核 → 無AI概念遷移 → 反思與教師回饋**。

詳見 [課程、核心架構與使用說明](docs/graphics/教學框架與操作.md)。

## 已實作

- 學生、教師、管理員登入與角色權限；學生僅能修改自己的進行中作答。
- 三個自編示例任務，對應十八週三階段；不是已核定的工程製造圖或正式考卷。
- 個人規劃、操作問題、尺寸變更預測、同儕策略、共同決策、AI採納／未採納與反思。
- 教師建立2–6人小組，依成員順序與任務階段輪替角色；未分組可個人練習並明示未合作。
- CATPart、CATProduct、STEP、STL、OBJ、圖片、PDF、文字證據上傳／受控下載；每份上限20 MB，保存SHA256。
- 小組分享採明確同意；僅分享第3階段實作及附件，不分享自評、個人反思、教師分數。
- 規則式五層數位鷹架；可選接本機Ollama。個人前測與遷移測驗階段停用平台提示。
- 孔位依存及滑塊自由度的互動概念示意，可保存參數為文字證據；不冒充CAD求解器。
- 教師自編教案、保存草稿、發布修訂；新訓練用新版本，進行中訓練保留原始快照。
- 教師分別核定操作、概念、合作、反思四構面（0–3或未評），追加保存覆核依據與下一輪任務。
- 草稿儲存、舊版本衝突保護、未儲存提示、提交後證據凍結、重新登入查看、JSON歷程匯出。

## 本機 AI（選配）

先自行安裝並確認本機 Ollama 模型可運行，於環境或本機 `.env` 設定：

```dotenv
GRAPHICS_OLLAMA_MODEL=your-installed-model
```

重啟後只呼叫 `http://127.0.0.1:11434/api/chat`，記錄模型名稱與來源；模型未設定或失敗時明示改用規則式提示。預設不呼叫付費雲端服務。模型回覆仍須由使用者驗證；不會讀取CATIA檔案或自動核定正式分數。

## 資料與部署

- 資料：`runtime/graphics/graphics_tutor.sqlite3`，附件：`runtime/graphics/artifacts/`。
- 可用 `GRAPHICS_HOME` 指定獨立資料目錄。不得把此資料目錄加入Git。
- Cookie：`graphics_tutor_session`；不共用原醫事登入。
- 管理員初始帳號：`graphics-admin`。可預先以 `GRAPHICS_ADMIN_PASSWORD` 設定至少12字元密碼。
- Docker：`docker compose -f compose.graphics.yaml up --build`，啟動前設定 `GRAPHICS_ADMIN_PASSWORD`。此設定只綁本機連接埠；對外部署需另設HTTPS，並設定 `COOKIE_SECURE=1`。
- 備份請停止電腦圖學服務後，完整複製 `runtime/graphics/` 至受控且加密的備份位置。原醫事版自動備份工具不會自動涵蓋新資料庫；尚未宣稱本版具自動雲端備份或已完成容器部署驗收。
- 舊醫事版本說明：[README_CLINICAL.md](README_CLINICAL.md)，Windows舊版入口 `run_clinical_windows.bat`。本版沒有更改原臨床資料庫或公開入口。

## 驗證

```sh
python -m pip install -r requirements-graphics.txt
python -m unittest discover -s tests -p test_graphics.py -v
node --check frontend/graphics/app.js
node --test tests/frontend/*.test.mjs
```

詳見 [驗證紀錄與限制](docs/graphics/驗證紀錄.md)。研究同意、正式評分制度與量表效度仍由授課及研究單位確認；本版不宣稱已獲ISO認證。
