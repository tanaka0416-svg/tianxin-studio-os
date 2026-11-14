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

async function readTaskList(signal?: AbortSignal): Promise<Task[]> {
  const response = await fetch(API_URL, signal ? { signal } : undefined);
  if (!response.ok) throw new Error("Task list unavailable");
  return (await response.json()) as Task[];
}

export default function App() {
  const [tasks, setTasks] = useState<Task[]>([]);
  const [draft, setDraft] = useState<TaskDraft>(emptyDraft);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState("");
  const [outcomeUnknown, setOutcomeUnknown] = useState(false);
  const [expandedDescriptions, setExpandedDescriptions] = useState<Set<string>>(
    () => new Set(),
  );
  const savingRef = useRef(false);

  useEffect(() => {
    const controller = new AbortController();
    readTaskList(controller.signal)
      .then((loadedTasks) =>
        setTasks((current) => {
          const loadedIds = new Set(loadedTasks.map((task) => task.id));
          return [...loadedTasks, ...current.filter((task) => !loadedIds.has(task.id))];
        }),
      )
      .catch(() => {
        if (!controller.signal.aborted) setError("無法載入任務清單，請稍後再試。");
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false);
      });
    return () => controller.abort();
  }, []);

  function updateDraft<K extends keyof TaskDraft>(key: K, value: TaskDraft[K]) {
    setDraft((current) => ({ ...current, [key]: value }));
  }

  async function refreshTasks() {
    setRefreshing(true);
    try {
      const refreshedTasks = await readTaskList();
      setTasks(refreshedTasks);
      setError("");
      setOutcomeUnknown(false);
    } catch {
      setError("無法重新載入任務清單，請稍後再試。");
    } finally {
      setRefreshing(false);
    }
  }

  async function createTask(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (savingRef.current) return;

    const submittedTitle = draft.title.trim();
    if (!submittedTitle) return;

    savingRef.current = true;
    setSaving(true);
    setError("");
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

      const createdTask = (await response.json()) as Task;
      setDraft(emptyDraft());
      setTasks((current) => [...current.filter((task) => task.id !== createdTask.id), createdTask]);
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
            <span className="task-count" aria-live="polite">{tasks.length} 項任務</span>
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
              {outcomeUnknown && (
                <button type="button" onClick={refreshTasks} disabled={refreshing}>
                  {refreshing ? "載入中…" : "重新載入任務清單"}
                </button>
              )}
            </div>
          )}

          <section className="task-section" id="tasks" aria-labelledby="list-title">
            <div className="section-heading">
              <div>
                <h2 id="list-title">所有任務</h2>
                <p>依建立時間排列 · 更新時間以台北時區顯示</p>
              </div>
              <span className="task-count-inline">{tasks.length} 項</span>
            </div>
            {loading ? (
              <p className="empty-state">正在載入任務…</p>
            ) : tasks.length === 0 ? (
              <p className="empty-state">目前沒有任務，從上方新增第一項工作。</p>
            ) : (
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
            )}
          </section>
          <footer className="footer-note">本機單一使用者模式 · 時間顯示為台北時間</footer>
        </section>
      </div>
    </main>
  );
}
