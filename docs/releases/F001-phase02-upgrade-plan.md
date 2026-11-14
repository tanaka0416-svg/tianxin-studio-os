# F001 第二階段正式資料庫升級操作方案

> **狀態：F001 第二階段正式工作環境升級完成，驗收通過。** CEO 已於 2026-11-15 手動確認正式資料與功能及品牌區；還原仍未授權。本文件本身不構成其他正式資料庫操作授權。

## 1. 目前版本與適用範圍

- 本方案依目前 Git 基準 `9fc5c08`（第五切片篩選排序 GUI）及目前第二階段後端程式編寫。
- 目標資料庫 revision 為 Alembic `0002_task_metadata`。第一階段未標記 revision 的既有 schema 可由遷移工具驗證後升級；空資料庫也可用明確路徑初始化。
- 工具僅支援 SQLite，且只操作命令列明確指定的絕對路徑。應用程式啟動只做唯讀版本檢查，不會自動遷移或建立資料表。
- 本方案適用於第一階段 SQLite 工作資料庫升至第二階段 schema；不含其他資料庫、應用功能或套件升級。

## 2. 正式路徑（CEO 已確認／指定）

- 正式工作資料庫絕對路徑：`D:\tianxin-studio-os\.task-center\tasks.sqlite3`
- CEO 核准備份目錄：`D:\tianxin-studio-backups\F001-phase02\`
- 本次已建立且驗證的備份：`D:\tianxin-studio-backups\F001-phase02\tasks-pre-phase02-20261115-021808.sqlite3`
- 如需保存遷移失敗後的資料庫副本，其絕對路徑：`<待 CEO 指定：失敗資料庫保留路徑>`

失敗資料庫保留路徑仍待 CEO 指定。後續正式遷移與還原尚未授權。備份目的檔必須是尚不存在的新檔案；其父目錄必須先存在。來源與備份路徑不可相同。

## 3. 停止服務並確認沒有寫入

1. CEO 指定維護時段並確認會使用哪個服務管理器、工作目錄與應用版本。
2. 透過原服務管理器正常停止連到正式資料庫的後端；不要只關閉前端頁面。停止任何其他已知會寫入該 SQLite 檔的本機程序。
3. 由服務管理器確認後端已停止，並確認該服務的程序不再持有資料庫連線。若程序歸屬不明、仍有連線，或無法確認無寫入，停止操作，不終止不明程序。
4. 確認正式資料庫旁沒有仍被使用的 `-wal`／`-shm` sidecar。遷移及還原期間不得有應用程序連線。

## 4. 備份、完整性檢查及驗證

目前沒有獨立備份 CLI。後端提供 `app.migrations.backup_database(source_path, backup_path)`，以 SQLite Online Backup API 建立新備份，並對來源及備份執行 `PRAGMA integrity_check`；若目的檔已存在、路徑不是絕對路徑或檢查未通過，操作會拒絕或失敗。

以下是操作形狀示例，包含待替換佔位符，**不可直接執行**。使用時須填入已核准的來源路徑及新的唯一備份路徑，並使用本節指定的解譯器與工作目錄；正式操作仍須有對應授權：

```powershell
Set-Location 'D:\tianxin-studio-os\src\backend'
& 'C:\Users\Cingul Savaran\AppData\Local\Programs\Python\Python310\python.exe' -c "from app.migrations import backup_database; backup_database(r'<已確認的工作資料庫絕對路徑>', r'<新且唯一的備份檔絕對路徑>')"
```

已驗證的執行環境為 Python `3.10.6`，解譯器 `C:\Users\Cingul Savaran\AppData\Local\Programs\Python\Python310\python.exe`，工作目錄 `D:\tianxin-studio-os\src\backend`。從 repo 根目錄直接匯入會因頂層 `app` 不在該工作目錄的模組搜尋路徑而失敗；不得因此設定全域 `PYTHONPATH`。

備份 helper 成功返回代表 SQLite 完整性檢查通過，不等於已核對業務資料內容。備份完成後，記錄 helper 成功結果、檔案大小及備份路徑（不記錄任務文字）；用唯讀方式確認備份仍可開啟、`PRAGMA integrity_check` 為 `ok`，並確認其 revision/schema 與來源一致。驗證失敗時不得遷移。不得覆寫既有備份。

## 5. 明確路徑遷移命令與預期結果

遷移 CLI 實際命令如下。以下仍含佔位符，**不是可直接執行的命令**；正式遷移目前尚未授權，只有另行核准後才可替換為已確認的絕對路徑並執行：

```powershell
Set-Location 'D:\tianxin-studio-os\src\backend'
& 'C:\Users\Cingul Savaran\AppData\Local\Programs\Python\Python310\python.exe' -m app.migrations upgrade --database-path '<已確認的正式工作資料庫絕對路徑>'
```

成功時 CLI 顯示 `Migration completed for the explicitly specified database.`，資料庫 revision 應為 `0002_task_metadata`。若 schema 不符合已知第一階段結構、revision 未知、完整性檢查失敗或 CLI 回傳非零，立即停止；不得改用 `create_all()`、手動改 schema、重建資料庫或改指其他路徑。

正式遷移前須確認來源是預期的第一階段 schema；若已是 `0002_task_metadata`，不應重複執行本次升級流程。工具對已升級資料庫可安全重跑，但正式操作仍應遵循一次明確維護流程並保留輸出紀錄。

## 6. 遷移後檢查與應用驗證

1. 以唯讀方式確認 revision 是 `0002_task_metadata`，`PRAGMA integrity_check` 為 `ok`，並確認 `tasks` 含 `description`、`department`、`assigned_ai`、`priority`、`due_date` 五欄。
2. 比對遷移前記錄的任務筆數及脫敏事件筆數；確認原有任務 `id`、`title`、`status`、`created_at`、`updated_at` 與脫敏事件均保留。不要輸出或複製任務正文至日誌。
3. 確認舊任務新選填欄位為 `NULL`，`priority` 為 `MEDIUM`。
4. 只在正式升級獲得 CEO 另行核准後，使用明確設定的正式資料庫路徑啟動目前版後端；API 必須只綁定 `127.0.0.1`。啟動時的唯讀版本檢查應接受 `0002_task_metadata`。不得以預設 `.task-center/` 路徑代替已確認路徑。
5. 進行核准範圍內的唯讀清單檢查及必要的合成文字請求驗證。任何輸入均須走現有脫敏閘道；不得使用真實敏感資料作驗證。

## 7. 失敗停止條件與還原

### 停止條件

- 備份未成功或無法再次通過完整性檢查。
- 遷移命令非零退出、revision 非預期、schema／資料比對不符或完整性檢查失敗。
- 新版應用啟動版本檢查失敗、API 無法讀取，或發現非預期資料變化。
- 無法確認服務停止、資料庫沒有寫入者、路徑、備份或程序歸屬。

遇到任一條件，停止服務及後續寫入，保存錯誤訊息（先確認不含輸入資料）、遷移輸出與資料庫檔案；不得自動重試、刪除、覆蓋或清理。記錄失敗原因並交 CEO 決定。

### 還原步驟

1. 先停止新版後端及所有資料庫使用者；確認無連線且沒有活躍的 `-wal`／`-shm` sidecar。若無法確認，停止還原。
2. 還原會以備份內容覆寫目標資料庫。若升級後已有新寫入，先停止並由 CEO 決定如何處置；不要假設可丟棄，也不要直接覆寫。
3. `restore_database(backup_path, database_path)` 要求兩個不同的絕對路徑、已存在的還原目標，並拒絕存在 sidecar 的目標。函式先驗證備份，再以 SQLite Online Backup API 還原並驗證目標完整性；目前沒有獨立還原 CLI。
4. 以下呼叫形狀只供核准後複核，帶有佔位符，**不可直接執行**：

```powershell
python -c "from app.migrations import restore_database; restore_database(r'<待 CEO 指定：已驗證備份絕對路徑>', r'<待 CEO 確認：正式工作資料庫絕對路徑>')"
```

5. 還原第一階段備份會恢復第一階段 schema。新版第二階段應用要求 revision `0002_task_metadata`，因此不可只還原資料庫後繼續啟動新版服務。應部署／啟動與第一階段 schema 相容的應用版本 `5faf666`（第一階段基準提交），再確認其版本及清單讀取行為。若該版本不可用，或版本相容性未經驗證，保持服務停止並等待 CEO 指示；不可對舊 schema 執行新版應用。
6. 還原後逐項核對第一階段 schema、原任務與脫敏事件、`PRAGMA integrity_check`，並確認使用的是相容應用版本。恢復服務前需 CEO 明確批准。

## 8. 後續升級前需 CEO 明確核准

- 工作資料庫路徑及備份目錄已由 CEO 確認；2026-11-15 正式備份已完成並記錄於本方案及驗收紀錄。
- 正式遷移與遷移後驗證已由 CEO 授權並完成；若需再次遷移仍須另行授權。
- 維護時段、停止服務方式、已知資料庫寫入程序及恢復服務負責人。
- 若需還原：還原目標路徑、失敗資料庫保留位置、升級後新寫入處置方式，以及切回 `5faf666` 相容應用的授權。
- 若需重新備份：新備份檔完整絕對路徑及相應操作授權；不得覆寫既有備份。
- 驗收無誤後啟動新版服務的授權。

路徑確認不等於操作授權；每次正式備份、遷移或還原都須有明確授權。本次正式遷移已完成；還原仍未授權。

## 9. 備份、失敗檔與日誌保留

- 備份採新檔名，不覆寫既有備份；正式保留期限與歸檔位置由 CEO 指定。
- 遷移失敗後的資料庫與任何失敗副本先保留，不自行刪除或覆寫；其保存路徑須由 CEO 指定並限制本機存取。
- 操作日誌只記錄時間、命令結果、revision、完整性檢查結果及不含任務正文的錯誤摘要；不得記錄完整請求本文、任務標題／描述或未脫敏值。
- 暫存、失敗與日誌的清理時間及核准方式待 CEO 指定；本方案不自動清理任何資料。

## 10. 本次整合驗收證據與限制

先前整合驗收只在 pytest 暫存目錄使用合成資料庫，當時沒有操作正式工作資料庫。正式備份紀錄如下；其後 CEO 另行核准並完成正式遷移、遷移後驗證及本機唯讀冒煙。還原未執行且未獲授權。

### 2026-11-15 正式備份執行補充

- 首次備份呼叫使用 Python `C:\Users\Cingul Savaran\AppData\Local\Programs\Python\Python310\python.exe`，但工作目錄錯在 repo 根目錄 `D:\tianxin-studio-os`。例外鏈為 `File "<string>", line 1, in <module>` → `ModuleNotFoundError: No module named 'app'`。helper 尚未匯入或呼叫，當次未開啟來源資料庫，未產生備份檔；只建立了核准的備份資料夾。
- 修正後於 `D:\tianxin-studio-os\src\backend` 使用同一 Python 解譯器；`app`、`app.migrations`、`app.migrations.core`、`app.migrations.cli` 均由本專案 `src/backend/app` 載入。已先以合成資料庫驗證相同 helper 呼叫、完整性、schema、所有資料列一致及合成來源位元組未變。
- 正式備份 helper 以 `mode=ro` 開啟來源；備份目的地使用新的唯一檔名。正式來源與備份完整性皆為 `ok`，schema 與所有任務／脫敏資料列一致。
- 備份完成時間：`2026-11-15 02:18:09 +08:00`；大小：`20480` bytes；SHA-256：`ffd152326b6b7914555f7c867b78bf42f7c4949c2457ec3690864539b04b75bb`。
- 截至本備份作業完成時，沒有遷移、還原或啟動應用程式；正式遷移其後依 CEO 另行授權執行，記錄如下。

### 2026-11-15 正式遷移與唯讀冒煙

- 執行前確認基準為 `9580fbc`，來源為已知 `legacy` schema，且來源 schema、`tasks` 與 `redaction_events` 全部資料列與上述已驗證備份相符；備份 SHA-256 再次符合 CEO 指定值。
- 使用已確認 Python 3.10.6 解譯器及 `D:\tianxin-studio-os\src\backend` 工作目錄，遷移前 revision 狀態 `legacy`，明確指定工作資料庫絕對路徑執行既有遷移 CLI；結果 revision 為 `0002_task_metadata`。
- 遷移後 `PRAGMA integrity_check` 為 `ok`；既有任務 `id`、`title`、`status`、`created_at`、`updated_at` 及所有脫敏紀錄均與備份逐筆一致；既有任務新增欄位為 `NULL`、優先級為 `MEDIUM`。
- 唯讀冒煙使用明確 `TASK_CENTER_DATABASE_URL=sqlite:///D:/tianxin-studio-os/.task-center/tasks.sqlite3`。後端 `GET /api/tasks`、`GET /api/tasks?status=TODO&sort_by=created_at&order=asc` 及前端首頁均回覆 HTTP 200；不輸出回應本文，未新增或修改任務。
- 冒煙當時服務仍在執行：後端 PID `15676`，監聽 `127.0.0.1:8000`；前端 PID `21484`，監聽 `127.0.0.1:5173`。CEO 手動驗收後，Codex 重新核對程序路徑、命令列與監聽埠，確認 PID 仍屬本次任務中心服務後停止；兩個 PID 均已退出。
- 執行當時 CEO 最後畫面確認仍待完成；CEO 其後於 2026-11-15 手動確認正式資料與功能及品牌區通過。此補記保留先前執行時的待確認歷程，不把 Codex 冒煙改寫為 CEO 驗收。
