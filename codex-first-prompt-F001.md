# Codex 第一句指令：F001 任務中心

> 文件狀態：歷史指令，記錄 F001 初始規劃時使用的提示詞，不再直接執行。若要進行後續工作，須依最新決策另行確認範圍；本文建議不構成第二階段核准。

請先依序閱讀以下檔案：

1. D:\tianxin-studio-os\README.md
2. D:\tianxin-studio-os\docs\00-product-brief.md
3. D:\tianxin-studio-os\docs\01-roles-and-permissions.md
4. D:\tianxin-studio-os\docs\02-data-governance.md
5. D:\tianxin-studio-os\docs\03-development-workflow.md
6. D:\tianxin-studio-os\specs\F001-task-center\spec.md
7. D:\tianxin-studio-os\specs\F001-task-center\data-model.md
8. D:\tianxin-studio-os\specs\F001-task-center\acceptance-criteria.md
9. D:\tianxin-studio-os\ai-prompts\secretary.md
10. D:\tianxin-studio-os\ai-prompts\data-governance.md

不要直接開始寫完整系統。

請先產出：

1. 你對本功能的理解
2. 實作計畫
3. 建議技術栈
4. 檔案與資料夾清單
5. 資料庫結構
6. UI 頁面清單
7. API 清單
8. 測試案例
9. 分階段交付順序
10. 你發現規格中缺少或矛盾的地方

等我核准計畫後，才實作第一個最小功能：建立任務、顯示任務清單、變更任務狀態。

限制：

- 不得讀取或上傳 private/、uploads/raw/、exports/ 內容。
- 不得自行擴大功能範圍。
- 每次只交付一個可測試的小功能。
- 所有敏感資料必須先通過脫敏閘道。
- 完成後必須更新 CHANGELOG.md。
