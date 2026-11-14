# 田薪個人工作室｜第一個大階段結案與跨對話交接

- 文件基準日期：2026-11-15（台灣時間）
- 交接基準提交：02866e4 chore: finalize phase-two rollout and studio branding
- 狀態：F001 第二階段正式工作環境升級已驗收、已本機提交、服務已停止。
- 用語區分：「第一個大階段」指截至此份交接的整體建置成果，包含 F001 內部第二階段；不應將它改寫為 F001 phase01。
- 證據範圍：本文件依 CEO 提供的歷程摘要及 Codex 回報整理；產製本文件的助手未直接讀取本機儲存庫、資料庫或截圖。即時狀態須在新工作階段重新核對。

## 1. 工作室目標與治理

- 中文名稱：田薪個人工作室；英文名稱：TianxinStudio；平台名稱：TianxinStudio OS。
- CEO 為唯一人類決策與核准者。AI 協助秘書、研究、開發、影音、品管、財務等工作，不取代 CEO 的核准權。
- 逐步交付可驗收的小功能；不讓 Codex 自行擴大範圍。
- 敏感資料先經本機脫敏；未經核准不傳雲端。
- 曾討論的角色分工：ChatGPT/Codex 協助開發、Claude 協助秘書、Perplexity 協助研究與法規初篩、Grok 交叉檢查、本機 AI 處理敏感內容。這是規劃，不代表已完成整合、安裝或訂閱。

## 2. 專案與技術基準

- 專案：D:\tianxin-studio-os
- 前端：React / TypeScript / Vite。
- 後端：FastAPI / Python。
- 資料庫：SQLite。
- 後端工作目錄：D:\tianxin-studio-os\src\backend
- Python 3.10.6：C:\Users\Cingul Savaran\AppData\Local\Programs\Python\Python310\python.exe
- 正式工作資料庫：D:\tianxin-studio-os\.task-center\tasks.sqlite3
- 已回報資料庫版本：0002_task_metadata（從 legacy 遷移）。

## 3. 已完成範圍與能力界線

已驗收的主要範圍：
- 任務建立、清單與狀態變更。
- 任務描述、部門、主要負責 AI、優先級、截止日等 metadata。
- 篩選與排序。
- 既有文字規則式脫敏及紀錄保留。
- 正式工作資料庫升級與原任務資料保留。
- 品牌呈現：主名稱「田薪個人工作室」、次名稱「TianxinStudio OS」，移除「天」字圖樣與專屬底框，未新增 Logo。

能力界線：
- AI 指派欄位僅為角色紀錄，不代表 AI 會自動執行。
- 文字規則式脫敏不等於完整文件、圖片、聲音或影片脫敏系統，也不保證所有敏感資訊皆可辨識。
- 不宣稱已完成雲端 AI 串接、附件處理、財務、法律追蹤或影視流程。
- 先前助手提到「六種狀態」及「三種尺寸均驗收」；目前交接可見的直接回報未充分列出其依據。狀態列舉應查程式與既有驗收紀錄，不把上述說法當成新增已證實成果。

## 4. 關鍵過程

1. F001 從任務建立、清單、狀態變更的小範圍起步，未把雲端 AI 與附件混入初始範圍。
2. 第二階段加入任務 metadata、篩選與排序，並準備正式資料庫升級。
3. 過程曾發生備份相關匯入失敗；後續確認 Python 後端工作目錄錯誤並修正。完整歷程以升級方案及驗收紀錄為準，不改寫為全程無異常。
4. 正式升級前建立並驗證備份；工作資料庫由 legacy 遷移到 0002_task_metadata。
5. 完整性檢查通過；既有任務欄位及脫敏紀錄保留；舊任務新增 metadata 欄位為 NULL，priority 為 MEDIUM。
6. 正式應用唯讀冒煙：清單、status=TODO 搭配建立時間升冪，以及首頁 GET，均回報 HTTP 200，未寫入測試任務。
7. CEO 確認原任務與狀態、新欄位、篩選排序及無載入／版本錯誤。
8. CEO 指出品牌「天」字不符名稱；Codex 僅修改前端品牌、相關測試與紀錄。
9. CEO 最後確認品牌名稱及排列正常，接受修正。
10. 完成結案文件、本機提交並停止預覽服務；未推送。

## 5. 驗收與測試證據

### CEO 手動確認
- 原有任務與狀態正常。
- 新欄位及篩選排序工具列正常。
- 無載入或版本錯誤。
- 「天」字圖樣及底框已移除。
- 「田薪個人工作室」及「TianxinStudio OS」正確，排列正常。

### Codex 回報的自動驗證
- 品牌測試先 RED：舊輔助名稱不符預期；修改後通過。
- 品牌修正完成時：前端測試 38 passed。
- TypeScript 型別檢查、前端建置、git diff --check 通過。
- 品牌修正未重跑後端測試；未做三種尺寸完整驗收或瀏覽器視覺判定。
- 結案提交時沒有重跑相同測試。
- 不將 CEO 手動確認寫成自動測試，也不將歷史通過寫成新對話已重驗。

## 6. Git 與文件狀態（最後回報快照）

最近三筆提交：
```text
02866e4 chore: finalize phase-two rollout and studio branding
9580fbc test: verify phase-two integration and document upgrade
9fc5c08 feat: add task filtering and sorting interface
```

02866e4 提交檔案：
- docs/releases/F001-phase02-upgrade-plan.md
- docs/acceptance-record.md
- CHANGELOG.md
- src/frontend/src/App.tsx
- src/frontend/src/styles.css
- src/frontend/src/App.test.tsx

最後 git status --short：
```text
?? docs/acceptance-evidence/
```

- 三張驗收截圖仍未追蹤、未提交；不是完全乾淨的工作目錄。
- 已回報未設定遠端、未推送；新工作階段若需要使用遠端，須重新核對並另請 CEO 核准。
- 不自動加入、刪除或清理截圖。

## 7. 正式備份

- 路徑：D:\tianxin-studio-backups\F001-phase02\tasks-pre-phase02-20261115-021808.sqlite3
- 大小：20,480 bytes。
- SHA-256：ffd152326b6b7914555f7c867b78bf42f7c4949c2457ec3690864539b04b75bb
- 此為升級前資料庫的回復基準，不是後續新增任務的最新備份。
- 不覆寫工作資料庫、不擅自還原、不刪除備份。

## 8. 日常啟動與停止（依最後交付命令保留）

以下兩個 PowerShell 視窗分別執行。這是既有交付操作，不代表新對話已再次實測。

### 視窗一：後端
```powershell
Set-Location 'D:\tianxin-studio-os\src\backend'
$env:TASK_CENTER_DATABASE_URL = 'sqlite:///D:/tianxin-studio-os/.task-center/tasks.sqlite3'
& 'C:\Users\Cingul Savaran\AppData\Local\Programs\Python\Python310\python.exe' -m uvicorn --app-dir . app.main:app --host 127.0.0.1 --port 8000
```

### 視窗二：前端
```powershell
Set-Location 'D:\tianxin-studio-os\src\frontend'
npm run dev -- --port 5173 --strictPort
```

- 依最後回報，package.json 的 dev 命令綁定 127.0.0.1；若設定已改變，先核對再執行。
- 正常停止：各自視窗 Ctrl+C。
- 不需要每次安裝套件、建立資料庫或執行遷移。
- 最後回報前端 PID 21484、後端 PID 15676 均已停止，埠無相關監聽；PID 僅為歷史紀錄，絕不可當成未來終止程序的依據。

## 9. 下一階段：尚未核准

- 候選：F002「脫敏閘道」。這只是既有討論中的方向，尚無本輪 CEO 核准的開發規格或實作授權。
- 新對話先核對交接、列出不確定事項，再提一個小範圍供 CEO 決策。
- 不自動把 PDF、OCR、人臉、聲音、雲端串接或完整多代理系統加入同一階段。
- 不因交接文件提到某功能，就視為已授權實作。

## 10. 新工作階段的核對順序

### 規劃／研究助手
1. 閱讀本文件，區分已完成、提案、未驗證與禁止事項。
2. 沒有本機工具證據時，明說依 CEO/Codex 回報，不宣稱已檢查儲存庫。
3. 先提出下一階段最小範圍與驗收方式；等待 CEO 核准。

### Codex
1. 閱讀適用的 AGENTS.md（若存在），再讀本交接與三份既有結案文件。
2. 唯讀核對 git status --short、git log --oneline -3 與必要設定；若 HEAD 已前進，報告差異，不 reset 回舊版。
3. 不讀取工作資料庫內容、不啟動服務、不執行遷移、不寫入任務。
4. 提交接手摘要與差異，等待下一階段指令；不重做已結案驗收。
5. 不自動提交、推送、修改依賴、清除截圖或擴大開發範圍。

## 11. 後續每個大階段的交接慣例（建議，待採用）

- 每階段保留一份具日期與基準提交的結案快照，不覆寫上一份。
- 內容固定含：目標、完成／未完成、驗收證據、決策原因、版本、資料庫／備份、已知限制、下一步與禁止事項。
- 規劃助手與 Codex 共用同一事實摘要，另用角色不同的開場提示詞。
- 若維護 AGENTS.md，僅存放長期規則與交接文件入口，不塞入完整歷史；修改前先讀既有內容並經 CEO 核准。
- 新對話先回報「理解與差異」，不直接開始寫程式。
- 文件不放金鑰、帳密、客戶個資或正式資料庫內容；對外分享前再檢查本機路徑等資訊。
- 文件可以搬移脈絡，但不包含程式、正式資料、備份或未提交截圖本體；跨電腦另需保全這些資產。
