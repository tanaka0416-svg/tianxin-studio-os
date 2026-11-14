import { FormEvent, useEffect, useRef, useState } from "react";

const API_URL = "http://127.0.0.1:8000/api/tasks";

const statuses = [
  { value: "TODO", label: "待處理" },
  { value: "IN_PROGRESS", label: "進行中" },
  { value: "REVIEW", label: "待審核" },
  { value: "BLOCKED", label: "卡住" },
  { value: "RETURNED", label: "已退回" },
  { value: "DONE", label: "已完成" },
] as const;

const departments = [
  { value: "SECRETARIAT", label: "秘書室" },
  { value: "LEGAL", label: "法律合規" },
  { value: "DEVELOPMENT", label: "開發部" },
  { value: "MEDIA", label: "影視部" },
  { value: "QA", label: "品管部" },
  { value: "FINANCE", label: "財務部" },
  { value: "WEB", label: "網頁部" },
  { value: "DATA_GOVERNANCE", label: "資料治理中心" },
] as const;

const assignedAIs = [
  { value: "CLAUDE", label: "Claude" },
  { value: "PERPLEXITY", label: "Perplexity" },
  { value: "CHATGPT", label: "ChatGPT" },
  { value: "CODEX", label: "Codex" },
  { value: "GROK", label: "Grok" },
  { value: "LOCAL_AI", label: "本機 AI" },
] as const;

const priorities = [
  { value: "LOW", label: "低" },
  { value: "MEDIUM", label: "一般" },
  { value: "HIGH", label: "高" },
  { value: "URGENT", label: "緊急" },
] as const;

type TaskStatus = (typeof statuses)[number]["value"];
type DepartmentCode = (typeof departments)[number]["value"];
type AssignedAICode = (typeof assignedAIs)[number]["value"];
type PriorityCode = (typeof priorities)[number]["value"];
type SortBy = "created_at" | "updated_at" | "due_date" | "priority";
type SortOrder = "asc" | "desc";
type TaskQuery = {
  status: TaskStatus | "";
  department: DepartmentCode | "";
  assigned_ai: AssignedAICode | "";
  priority: PriorityCode | "";
  sort_by: SortBy;
  order: SortOrder;
};

const defaultQuery: TaskQuery = {
  status: "",
  department: "",
  assigned_ai: "",
  priority: "",
  sort_by: "created_at",
  order: "asc",
};

type Task = {
  id: string;
  title: string;
  status: TaskStatus;
  description?: string | null;
  department?: DepartmentCode | null;
  assigned_ai?: AssignedAICode | null;
  priority?: PriorityCode | null;
  due_date?: string | null;
  created_at: string;
  updated_at: string;
};

type TaskDraft = {
  title: string;
  description: string;
  department: DepartmentCode | "";
  assignedAI: AssignedAICode | "";
  priority: PriorityCode;
  dueDate: string;
};

function emptyDraft(): TaskDraft {
  return {
    title: "",
    description: "",
    department: "",
    assignedAI: "",
    priority: "MEDIUM",
    dueDate: "",
  };
}

function displayValue<T extends string>(
  options: readonly { value: T; label: string }[],
  value: string | null | undefined,
  fallback: string,
): string {
  return options.find((option) => option.value === value)?.label ?? fallback;
}

function formatTime(value: string): string {
  return new Intl.DateTimeFormat("zh-TW", {
    timeZone: "Asia/Taipei",
    month: "numeric",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  }).format(new Date(value));
}

async function readTaskList(query: TaskQuery, signal?: AbortSignal): Promise<Task[]> {
  const params = new URLSearchParams({ sort_by: query.sort_by, order: query.order });
  if (query.status) params.set("status", query.status);
  if (query.department) params.set("department", query.department);
  if (query.assigned_ai) params.set("assigned_ai", query.assigned_ai);
  if (query.priority) params.set("priority", query.priority);
  const response = await fetch(`${API_URL}?${params.toString()}`, signal ? { signal } : undefined);
  if (!response.ok) throw new Error("Task list unavailable");
  return (await response.json()) as Task[];
}

export default function App() {
  const [tasks, setTasks] = useState<Task[]>([]);
  const [query, setQuery] = useState<TaskQuery>(defaultQuery);
  const [draft, setDraft] = useState<TaskDraft>(emptyDraft);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState("");
  const [listLoadFailed, setListLoadFailed] = useState(false);
  const [successMessage, setSuccessMessage] = useState("");
  const [outcomeUnknown, setOutcomeUnknown] = useState(false);
  const [expandedDescriptions, setExpandedDescriptions] = useState<Set<string>>(
    () => new Set(),
  );
  const savingRef = useRef(false);
  const loadedRef = useRef(false);
  const requestIdRef = useRef(0);
  const listControllerRef = useRef<AbortController | null>(null);
  const queryRef = useRef(query);
  queryRef.current = query;

  const activeFilterCount = [query.status, query.department, query.assigned_ai, query.priority]
    .filter(Boolean).length;

  async function loadTasks(
    nextQuery: TaskQuery,
    failureMessage?: string,
  ): Promise<void> {
    listControllerRef.current?.abort();
    const controller = new AbortController();
    listControllerRef.current = controller;
    const requestId = ++requestIdRef.current;
    setLoading(!loadedRef.current);
    setRefreshing(loadedRef.current);
    setError("");
    setListLoadFailed(false);

    try {
      const loadedTasks = await readTaskList(nextQuery, controller.signal);
      if (controller.signal.aborted || requestId !== requestIdRef.current) return;
      setTasks(loadedTasks);
      loadedRef.current = true;
      setError("");
      setListLoadFailed(false);
    } catch {
      if (controller.signal.aborted || requestId !== requestIdRef.current) return;
      const hasPreviousResults = loadedRef.current;
      setError(failureMessage ?? (hasPreviousResults
        ? "載入失敗，目前顯示先前結果"
        : "載入失敗，目前沒有先前結果可顯示"));
      setListLoadFailed(true);
      setOutcomeUnknown(false);
    } finally {
      if (!controller.signal.aborted && requestId === requestIdRef.current) {
        setLoading(false);
        setRefreshing(false);
      }
    }
  }

  useEffect(() => {
    void loadTasks(defaultQuery);
    return () => listControllerRef.current?.abort();
  }, []);

  function updateQuery<K extends keyof TaskQuery>(key: K, value: TaskQuery[K]) {
    const nextQuery = { ...queryRef.current, [key]: value };
    queryRef.current = nextQuery;
    setQuery(nextQuery);
    void loadTasks(nextQuery);
  }

  function clearFilters() {
    const nextQuery: TaskQuery = {
      ...queryRef.current,
      status: "",
      department: "",
      assigned_ai: "",
      priority: "",
    };
    queryRef.current = nextQuery;
    setQuery(nextQuery);
    void loadTasks(nextQuery);
  }

  function updateDraft<K extends keyof TaskDraft>(key: K, value: TaskDraft[K]) {
    setDraft((current) => ({ ...current, [key]: value }));
  }

  function refreshTasks() {
    setOutcomeUnknown(false);
    void loadTasks(queryRef.current);
  }

  async function createTask(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (savingRef.current) return;

    const submittedTitle = draft.title.trim();
    if (!submittedTitle) return;

    savingRef.current = true;
    setSaving(true);
    setError("");
    setSuccessMessage("");
    setListLoadFailed(false);
    setOutcomeUnknown(false);
    try {
      const response = await fetch(API_URL, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          title: submittedTitle,
          description: draft.description.trim() || null,
          department: draft.department || null,
          assigned_ai: draft.assignedAI || null,
          priority: draft.priority,
          due_date: draft.dueDate || null,
        }),
      });

      if (response.status === 422) {
        setDraft((current) => ({ ...current, title: "", description: "" }));
        setError("內容未通過伺服器檢查，已清除標題與描述，請重新輸入。");
        return;
      }
      if (!response.ok) {
        setError("目前無法建立任務，請稍後再試。");
        return;
      }

      await response.json();
      setDraft(emptyDraft());
      setSuccessMessage("任務已建立。");
      await loadTasks(queryRef.current);
    } catch {
      setError("建立結果尚待確認；請重新載入任務清單確認是否已建立。系統不會自動重送。");
      setOutcomeUnknown(true);
    } finally {
      savingRef.current = false;
      setSaving(false);
    }
  }

  async function changeStatus(task: Task, status: TaskStatus) {
    const previousStatus = task.status;
    setError("");
    setTasks((current) =>
      current.map((item) => (item.id === task.id ? { ...item, status } : item)),
    );
    try {
      const response = await fetch(`${API_URL}/${task.id}/status`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ status }),
      });
      if (!response.ok) throw new Error("Status update rejected");
      const updated = (await response.json()) as Task;
      setTasks((current) => current.map((item) => (item.id === task.id ? updated : item)));
      await loadTasks(queryRef.current, "狀態已更新，但清單重新載入失敗");
    } catch {
      setTasks((current) =>
        current.map((item) =>
          item.id === task.id ? { ...item, status: previousStatus } : item,
        ),
      );
      setError("無法更新任務狀態，請稍後再試。");
    }
  }

  function toggleDescription(taskId: string) {
    setExpandedDescriptions((current) => {
      const next = new Set(current);
      if (next.has(taskId)) next.delete(taskId);
      else next.add(taskId);
      return next;
    });
  }

  return (
    <main className="page-shell">
      <header className="topbar">
        <a className="brand" href="#main" aria-label="TianxinStudio OS 任務中心首頁">
          <span className="brand-mark" aria-hidden="true">天</span>
          <span>TianxinStudio <strong>OS</strong></span>
        </a>
        <span className="local-mode"><span aria-hidden="true" />本機工作區</span>
      </header>

      <div className="workspace" id="main">
        <aside className="rail" aria-label="主要導覽">
          <p className="rail-label">工作區</p>
          <a className="rail-link active" href="#tasks" aria-current="page">
            <span className="rail-icon" aria-hidden="true">☷</span>
            <span>任務中心</span>
          </a>
        </aside>

        <section className="content" aria-labelledby="page-title">
          <div className="page-heading">
            <div>
              <p className="breadcrumb">工作區 <span>/</span> 任務中心</p>
              <h1 id="page-title">任務中心</h1>
              <p className="page-description">建立任務，掌握每一件工作的最新進度。</p>
            </div>
            <span className="task-count" aria-live="polite">
              {loading || refreshing
                ? "正在載入…"
                : listLoadFailed
                  ? "清單載入失敗"
                  : loadedRef.current
                    ? `符合目前條件：${tasks.length} 項`
                    : ""}
            </span>
          </div>

          <form className="create-form" onSubmit={createTask}>
            <div className="form-heading">
              <div>
                <h2>新增任務</h2>
                <p>先描述工作內容，再選擇指派資訊。</p>
              </div>
              <span className="required-note">標示 * 為必填</span>
            </div>

            <div className="task-form-grid">
              <div className="form-field form-field-wide">
                <label htmlFor="task-title">任務標題 <span aria-hidden="true">*</span></label>
                <input
                  id="task-title"
                  name="title"
                  value={draft.title}
                  onChange={(event) => updateDraft("title", event.target.value)}
                  placeholder="輸入清楚易懂的任務名稱"
                  autoComplete="off"
                  required
                />
              </div>

              <div className="form-field form-field-wide">
                <label htmlFor="task-description">任務描述</label>
                <textarea
                  id="task-description"
                  name="description"
                  value={draft.description}
                  onChange={(event) => updateDraft("description", event.target.value)}
                  placeholder="補充背景、交付內容或注意事項（選填）"
                  maxLength={5000}
                  rows={3}
                />
                <span className="field-hint character-count">
                  {draft.description.length.toLocaleString("zh-TW")} / 5,000
                </span>
              </div>

              <div className="form-field">
                <label htmlFor="task-department">部門</label>
                <select
                  id="task-department"
                  value={draft.department}
                  onChange={(event) => updateDraft("department", event.target.value as TaskDraft["department"])}
                >
                  <option value="">未指派</option>
                  {departments.map((item) => (
                    <option key={item.value} value={item.value}>{item.label}</option>
                  ))}
                </select>
              </div>

              <div className="form-field">
                <label htmlFor="task-assigned-ai">主要負責 AI</label>
                <select
                  id="task-assigned-ai"
                  value={draft.assignedAI}
                  onChange={(event) => updateDraft("assignedAI", event.target.value as TaskDraft["assignedAI"])}
                >
                  <option value="">未指派</option>
                  {assignedAIs.map((item) => (
                    <option key={item.value} value={item.value}>{item.label}</option>
                  ))}
                </select>
              </div>

              <div className="form-field">
                <label htmlFor="task-priority">優先級</label>
                <select
                  id="task-priority"
                  value={draft.priority}
                  onChange={(event) => updateDraft("priority", event.target.value as PriorityCode)}
                >
                  {priorities.map((item) => (
                    <option key={item.value} value={item.value}>{item.label}</option>
                  ))}
                </select>
              </div>

              <div className="form-field">
                <label htmlFor="task-due-date">截止日</label>
                <input
                  id="task-due-date"
                  type="date"
                  value={draft.dueDate}
                  onInput={(event) => updateDraft("dueDate", event.currentTarget.value)}
                />
                <span className="field-hint">使用日曆日期，不含時間</span>
              </div>
            </div>

            <div className="form-actions">
              <p className="privacy-note">標題與描述送出前會由本機後端檢查並遮蔽敏感資料。</p>
              <button type="submit" disabled={saving || !draft.title.trim()}>
                {saving ? "儲存中…" : "新增任務"}
              </button>
            </div>
            <p className="ai-assignment-note">
              負責 AI 僅為任務指派紀錄，目前未串接自動執行。
            </p>
          </form>

          {error && (
            <div className="error-message" role="alert">
              <p>{error}</p>
              {(outcomeUnknown || listLoadFailed) && (
                <button type="button" onClick={refreshTasks} disabled={refreshing}>
                  {refreshing ? "載入中…" : outcomeUnknown ? "重新載入任務清單" : "以目前條件重試"}
                </button>
              )}
            </div>
          )}

          {successMessage && <p className="success-message" role="status">{successMessage}</p>}

          <section className="task-toolbar" aria-label="任務篩選與排序">
            <details className="filter-disclosure" open>
              <summary>
                <span>篩選條件</span>
                <span className="active-filter-count">已套用 {activeFilterCount} 項篩選</span>
              </summary>
              <div className="filter-grid">
                <div className="filter-field">
                  <label htmlFor="filter-status">狀態</label>
                  <select id="filter-status" aria-label="狀態篩選" value={query.status} onChange={(event) => updateQuery("status", event.target.value as TaskQuery["status"])}>
                    <option value="">全部</option>
                    {statuses.map((item) => <option key={item.value} value={item.value}>{item.label}</option>)}
                  </select>
                </div>
                <div className="filter-field">
                  <label htmlFor="filter-department">部門</label>
                  <select id="filter-department" aria-label="部門篩選" value={query.department} onChange={(event) => updateQuery("department", event.target.value as TaskQuery["department"])}>
                    <option value="">全部</option>
                    {departments.map((item) => <option key={item.value} value={item.value}>{item.label}</option>)}
                  </select>
                </div>
                <div className="filter-field">
                  <label htmlFor="filter-assigned-ai">主要負責 AI</label>
                  <select id="filter-assigned-ai" aria-label="主要負責 AI 篩選" value={query.assigned_ai} onChange={(event) => updateQuery("assigned_ai", event.target.value as TaskQuery["assigned_ai"])}>
                    <option value="">全部</option>
                    {assignedAIs.map((item) => <option key={item.value} value={item.value}>{item.label}</option>)}
                  </select>
                </div>
                <div className="filter-field">
                  <label htmlFor="filter-priority">優先級</label>
                  <select id="filter-priority" aria-label="優先級篩選" value={query.priority} onChange={(event) => updateQuery("priority", event.target.value as TaskQuery["priority"])}>
                    <option value="">全部</option>
                    {priorities.map((item) => <option key={item.value} value={item.value}>{item.label}</option>)}
                  </select>
                </div>
              </div>
            </details>
            <button className="clear-filters" type="button" onClick={clearFilters} disabled={activeFilterCount === 0}>
              清除篩選
            </button>
            <div className="sort-controls">
              <div className="filter-field">
                <label htmlFor="sort-by">排序欄位</label>
                <select id="sort-by" aria-label="排序欄位" value={query.sort_by} onChange={(event) => updateQuery("sort_by", event.target.value as SortBy)}>
                  <option value="created_at">建立時間</option>
                  <option value="updated_at">更新時間</option>
                  <option value="due_date">截止日</option>
                  <option value="priority">優先級</option>
                </select>
              </div>
              <div className="filter-field">
                <label htmlFor="sort-order">排序方向</label>
                <select id="sort-order" aria-label="排序方向" value={query.order} onChange={(event) => updateQuery("order", event.target.value as SortOrder)}>
                  <option value="asc">{query.sort_by === "due_date" ? "由近到遠" : query.sort_by === "priority" ? "由低到高" : "由舊到新"}</option>
                  <option value="desc">{query.sort_by === "due_date" ? "由遠到近" : query.sort_by === "priority" ? "由高到低" : "由新到舊"}</option>
                </select>
              </div>
            </div>
          </section>

          <section className="task-section" id="tasks" aria-labelledby="list-title">
            <div className="section-heading">
              <div>
                <h2 id="list-title">任務清單</h2>
                <p>依目前條件顯示 · 更新時間以台北時區顯示</p>
              </div>
            </div>
            {loading && !loadedRef.current ? (
              <p className="empty-state">正在載入符合條件的任務…</p>
            ) : !loading && !refreshing && !listLoadFailed && tasks.length === 0 && activeFilterCount > 0 ? (
              <p className="empty-state">沒有符合目前篩選條件的任務。</p>
            ) : !loading && !refreshing && !listLoadFailed && tasks.length === 0 ? (
              <p className="empty-state">目前沒有任務，從上方新增第一項工作。</p>
            ) : tasks.length > 0 ? (
              <>
              {refreshing && <p className="loading-note" role="status">正在載入符合條件的任務…</p>}
              <ul className="task-list">
                {tasks.map((task) => {
                  const isExpanded = expandedDescriptions.has(task.id);
                  const hasLongDescription = Boolean(task.description && task.description.length > 100);
                  return (
                    <li className="task-row" key={task.id}>
                      <span className={`status-dot status-${task.status.toLowerCase()}`} aria-hidden="true" />
                      <div className="task-copy">
                        <h3>{task.title}</h3>
                        {task.description && (
                          <div className="task-description-wrap">
                            <p
                              id={`task-description-${task.id}`}
                              className={isExpanded ? "task-description" : "task-description description-clamped"}
                            >
                              {task.description}
                            </p>
                            {hasLongDescription && (
                              <button
                                type="button"
                                className="description-toggle"
                                aria-expanded={isExpanded}
                                aria-controls={`task-description-${task.id}`}
                                onClick={() => toggleDescription(task.id)}
                              >
                                {isExpanded ? "收合描述" : "展開描述"}：{task.title}
                              </button>
                            )}
                          </div>
                        )}
                        <dl className="task-meta">
                          <div><dt>部門</dt><dd>{displayValue(departments, task.department, "未指派")}</dd></div>
                          <div><dt>主要負責 AI</dt><dd>{displayValue(assignedAIs, task.assigned_ai, "未指派")}</dd></div>
                          <div><dt>優先級</dt><dd>{displayValue(priorities, task.priority, "一般")}</dd></div>
                          <div><dt>截止日</dt><dd>{task.due_date || "未設定"}</dd></div>
                          <div className="updated-at"><dt>更新於</dt><dd>{formatTime(task.updated_at)}</dd></div>
                        </dl>
                      </div>
                      <label className="status-control">
                        <span className="sr-only">狀態：{task.title}</span>
                        <select
                          aria-label={`狀態：${task.title}`}
                          value={task.status}
                          onChange={(event) => changeStatus(task, event.target.value as TaskStatus)}
                        >
                          {statuses.map((item) => (
                            <option key={item.value} value={item.value}>{item.label}</option>
                          ))}
                        </select>
                      </label>
                    </li>
                  );
                })}
              </ul>
              </>
            ) : loading ? (
              <p className="empty-state">正在載入符合條件的任務…</p>
            ) : null}
          </section>
          <footer className="footer-note">本機單一使用者模式 · 時間顯示為台北時間</footer>
        </section>
      </div>
    </main>
  );
}
