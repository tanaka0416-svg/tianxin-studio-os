# TianxinStudio OS

一人公司作業系統：由人類 CEO 決策，AI 分工執行；所有敏感資料上雲前必須通過脫敏閘道。

## 第一階段：任務中心

第一階段提供建立任務、顯示清單、變更狀態與本機文字脫敏。API 僅綁定 `127.0.0.1`，不提供登入、附件或雲端 AI 呼叫。

### 第二階段：任務欄位表單與清單資訊

任務表單可填寫標題、純文字描述、部門、主要負責 AI、優先級與截止日；清單會顯示這些欄位及更新時間。AI 指派只作記錄，不會自動執行。前端尚未加入篩選排序工具列或既有任務欄位編輯。

#### 任務清單 API 篩選與排序

`GET /api/tasks` 支援以下單值查詢參數：

| 參數 | 合法值 |
|---|---|
| `status` | `TODO`、`IN_PROGRESS`、`REVIEW`、`BLOCKED`、`RETURNED`、`DONE` |
| `department` | `SECRETARIAT`、`LEGAL`、`DEVELOPMENT`、`MEDIA`、`QA`、`FINANCE`、`WEB`、`DATA_GOVERNANCE` |
| `assigned_ai` | `CLAUDE`、`PERPLEXITY`、`CHATGPT`、`CODEX`、`GROK`、`LOCAL_AI` |
| `priority` | `LOW`、`MEDIUM`、`HIGH`、`URGENT` |
| `sort_by` | `created_at`、`updated_at`、`due_date`、`priority` |
| `order` | `asc`、`desc` |

省略篩選參數代表不篩選；各篩選維度以 AND 組合，重複參數或非法值回覆 422，不提供未指派專用代碼。預設排序為 `created_at ASC`；時間依資料庫 UTC 值比較，截止日依日曆日期比較且未設定者在兩種方向均置底，優先級依 `LOW < MEDIUM < HIGH < URGENT` 排序。同值結果以 `created_at ASC`、`id ASC` 穩定排列。此 API 不提供搜尋、分頁或自由排序欄位。

範例：`GET /api/tasks?department=DEVELOPMENT&priority=HIGH&sort_by=due_date&order=asc`

### 啟動方式

需要 Python 3.10 以上與 Node.js 20.19 以上。

在第一個 PowerShell 視窗，從專案根目錄執行：

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r src/backend/requirements.txt
python -m uvicorn --app-dir src/backend app.main:app --host 127.0.0.1 --port 8000
```

在第二個 PowerShell 視窗執行：

```powershell
cd src/frontend
npm ci
npm run dev
```

開啟 Vite 顯示的本機網址（預設 `http://127.0.0.1:5173`）。預設 SQLite 路徑為專案根目錄的 `.task-center/tasks.sqlite3`；後端啟動不會建立資料表或自動遷移，資料庫必須先由明確遷移命令升至目前版本。正式工作資料庫遷移另需 CEO 授權。

### 測試

從專案根目錄執行後端測試：

```powershell
python -m pytest
```

執行前端測試與正式建置：

```powershell
cd src/frontend
npm test
npm run build
```

### 第二階段 schema 遷移工具（合成測試路徑範例）

遷移工具不會在應用啟動時執行，且必須明確提供絕對資料庫路徑。以下範例只建立或升級 Windows 暫存目錄中的測試資料庫；正式工作資料庫路徑與備份位置需 CEO 另行授權，本範例不得改指向工作資料庫。

```powershell
cd src/backend
$testDatabase = Join-Path $env:TEMP 'tianxin-phase2-test.sqlite3'
New-Item -ItemType Directory -Force (Split-Path $testDatabase) | Out-Null
python -m app.migrations upgrade --database-path $testDatabase
```

遷移工具只接受符合第一階段 schema 的 SQLite 資料庫或指定的空資料庫；遇到未知 schema 時停止。正式遷移前須停止後端、使用 SQLite Online Backup API 備份並驗證備份，且另行取得 CEO 對正式資料庫操作的授權。

第二階段後端啟動前會以唯讀方式確認資料庫已由明確遷移命令升至目前版本；應用程式啟動不會建立資料表或自動遷移。工作資料庫尚未完成另行授權的正式升級前，不應啟動連向該資料庫的服務。

### 脫敏閘道

任務標題與描述在寫入資料庫前由後端本機檢查。可辨識的 Email、手機、身分證、護照、金融帳號、信用卡及統一編號會以佔位符取代；敏感候選值無法分類時拒絕建立任務，並只記錄長度、類型、位置與時間，不保存原始值。只處理文字。負責 AI 僅為任務指派紀錄，目前未串接自動執行。

## 開發原則

1. 每次只實作一個可驗收的小功能。
2. 先讀 docs/ 與 specs/，再寫程式。
3. 所有功能必須有 acceptance criteria 與測試。
4. 敏感資料不得未脫敏即送往雲端 AI。
5. 每個 PR / 變更都要更新 CHANGELOG.md。
