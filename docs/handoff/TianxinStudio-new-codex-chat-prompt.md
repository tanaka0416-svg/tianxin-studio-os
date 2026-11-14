# 新 Codex 對話開場提示詞

專案根目錄：D:\tianxin-studio-os
請先閱讀附件／我指定路徑中的階段交接摘要。若檔案不存在，停下回報，不猜路徑。

本次僅做唯讀接手，不進行下一階段實作。
1. 讀取適用的 AGENTS.md（若存在），以及交接摘要。
2. 讀取 docs/releases/F001-phase02-upgrade-plan.md、docs/acceptance-record.md、CHANGELOG.md 的相關內容。
3. 在專案根目錄核對 git status --short、git log --oneline -3。
4. 如需確認啟動資訊，僅唯讀檢查 package.json 與相關設定，不輸出秘密。

歷史基準為 02866e4；若 HEAD 不同，回報差異，不 reset、不 checkout 舊版。
歷史未追蹤項目為 docs/acceptance-evidence/，保留不動。

禁止：修改檔案、建立或修改 AGENTS.md、讀取正式工作資料庫內容、遷移、啟動服務、安裝套件、執行測試、清理檔案、提交或推送。
不要終止歷史 PID；它們不是當前程序身分。

最後只回報：
- 已讀文件、目前分支與 HEAD。
- 工作目錄狀態與交接快照的差異。
- 已完成及尚未核准範圍的理解。
- 需要 CEO 決策的阻礙（若無就寫無）。
完成後等待我的下一階段指令，不自行開工。
