# CATIA 免費學習工作室

學生入口：<https://poemcheng.github.io/spiral-clinical-tutor-v5/catia/>

這是可完全由 GitHub Pages 提供的靜態自學網站，含三階段 CATIA V5 教材、操作步驟、概念練習、具體作答題及可下載題本。不需要啟動教師電腦或 Python 服務。

學生進度及文字答案只保存在各自瀏覽器，可匯出 JSON 備份／交給教師，也可匯入繼續學習。關閉網頁後同瀏覽器可續用；清除網站資料或更換電腦前應匯出。本站不集中收取個人作答、檔案或成績。CATIA 原生檔與圖面請依教師指定管道繳交。

題目與解說是公開自學練習，不是保密測驗或自動核定的正式成績。CATIA 須在學生電腦另行安裝並具對應工作台授權。

## 維護

完整教材與產生程式保存在 `codex/graphics-teaching-practice` 分支：

- `backend/graphics_curriculum.py`：三任務尺寸與 36 題開放問答。
- `data/graphics/catia_learning.json`：知識教材、操作實作及練習解說。
- `tools/build_catia_site.py`：產生公開 `learning-data.js` 與題本。

執行 `python tools/build_catia_site.py` 產生資料，以 `--check` 檢查資料是否一致。將此資料夾發布到 `main/web_portal/catia/`，既有 `.github/workflows/pages.yml` 會部署。所有資產採相對路徑，適用 GitHub 專案子路徑。

教材數值為自編教學設計；在 CATIA 建模、求解與工程圖更新結果須由學生實作及教師覆核。原廠參考資料列於各課來源。
