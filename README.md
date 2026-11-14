# TianxinStudio OS

一人公司作業系統：由人類 CEO 決策，AI 分工執行；所有敏感資料上雲前必須通過脫敏閘道。

## 第一階段：任務中心

第一階段提供建立任務、顯示清單、變更狀態與本機文字脫敏。API 僅綁定 `127.0.0.1`，不提供登入、附件或雲端 AI 呼叫。

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

開啟 Vite 顯示的本機網址（預設 `http://127.0.0.1:5173`）。SQLite 資料庫建立於專案根目錄的 `.task-center/tasks.sqlite3`。

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
python -m app.migrations upgrade --database-path "$env:TEMP\tianxin-phase2-test.sqlite3"
```

遷移工具只接受符合第一階段 schema 的 SQLite 資料庫或指定的空資料庫；遇到未知 schema 時停止。正式遷移前須停止後端、使用 SQLite Online Backup API 備份並驗證備份，且另行取得 CEO 對正式資料庫操作的授權。

### 脫敏閘道

任務標題在寫入資料庫前由後端本機檢查。可辨識的 Email、手機、身分證、護照、金融帳號、信用卡及統一編號會以佔位符取代；敏感候選值無法分類時拒絕建立任務，並只記錄長度、類型、位置與時間，不保存原始值。第一階段只處理文字。

## 開發原則

1. 每次只實作一個可驗收的小功能。
2. 先讀 docs/ 與 specs/，再寫程式。
3. 所有功能必須有 acceptance criteria 與測試。
4. 敏感資料不得未脫敏即送往雲端 AI。
5. 每個 PR / 變更都要更新 CHANGELOG.md。
