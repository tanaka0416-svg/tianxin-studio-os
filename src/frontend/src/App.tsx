import { FormEvent, useEffect, useState } from "react";

const API_URL = "http://127.0.0.1:8000/api/tasks";

const statuses = [
  { value: "TODO", label: "待處理" },
  { value: "IN_PROGRESS", label: "進行中" },
  { value: "REVIEW", label: "待審核" },
  { value: "BLOCKED", label: "卡住" },
  { value: "RETURNED", label: "已退回" },
  { value: "DONE", label: "已完成" },
] as const;

type TaskStatus = (typeof statuses)[number]["value"];

type Task = {
  id: string;
  title: string;
  status: TaskStatus;
  created_at: string;
  updated_at: string;
};

async function errorMessage(response: Response): Promise<string> {
  try {
    const body = (await response.json()) as { detail?: string };
    return body.detail ?? "目前無法完成操作，請稍後再試。";
  } catch {
    return "目前無法完成操作，請稍後再試。";
  }
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

export default function App() {
  const [tasks, setTasks] = useState<Task[]>([]);
  const [title, setTitle] = useState("");
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    const controller = new AbortController();
    fetch(API_URL, { signal: controller.signal })
      .then(async (response) => {
        if (!response.ok) throw new Error(await errorMessage(response));
        return (await response.json()) as Task[];
      })
      .then(setTasks)
      .catch((reason: unknown) => {
        if (!controller.signal.aborted) {
          setError(reason instanceof Error ? reason.message : "無法載入任務清單。");
        }
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false);
      });
    return () => controller.abort();
  }, []);

  async function createTask(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const submittedTitle = title.trim();
    if (!submittedTitle || saving) return;

    setSaving(true);
    setError("");
    try {
      const response = await fetch(API_URL, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ title: submittedTitle }),
      });
      if (!response.ok) throw new Error(await errorMessage(response));
      const task = (await response.json()) as Task;
      setTasks((current) => [...current, task]);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "無法建立任務。");
    } finally {
      setTitle("");
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
      if (!response.ok) throw new Error(await errorMessage(response));
      const updated = (await response.json()) as Task;
      setTasks((current) => current.map((item) => (item.id === task.id ? updated : item)));
    } catch (reason) {
      setTasks((current) =>
        current.map((item) =>
          item.id === task.id ? { ...item, status: previousStatus } : item,
        ),
      );
      setError(reason instanceof Error ? reason.message : "無法更新任務狀態。");
    }
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
            <label htmlFor="task-title">新增任務</label>
            <div className="create-controls">
              <input
                id="task-title"
                name="title"
                value={title}
                onChange={(event) => setTitle(event.target.value)}
                placeholder="輸入任務標題"
                autoComplete="off"
                required
              />
              <button type="submit" disabled={saving || !title.trim()}>
                {saving ? "儲存中…" : "新增任務"}
              </button>
            </div>
            <p className="privacy-note">送出前會先檢查並遮蔽敏感資料。</p>
          </form>

          {error && <p className="error-message" role="alert">{error}</p>}

          <section className="task-section" id="tasks" aria-labelledby="list-title">
            <div className="section-heading">
              <h2 id="list-title">所有任務</h2>
              <span>依建立時間排列</span>
            </div>
            {loading ? (
              <p className="empty-state">正在載入任務…</p>
            ) : tasks.length === 0 ? (
              <p className="empty-state">目前沒有任務，從上方新增第一項工作。</p>
            ) : (
              <ul className="task-list">
                {tasks.map((task) => (
                  <li className="task-row" key={task.id}>
                    <span className={`status-dot status-${task.status.toLowerCase()}`} aria-hidden="true" />
                    <div className="task-copy">
                      <h3>{task.title}</h3>
                      <p>更新於 {formatTime(task.updated_at)}</p>
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
                ))}
              </ul>
            )}
          </section>
          <footer className="footer-note">本機單一使用者模式 · 時間顯示為台北時間</footer>
        </section>
      </div>
    </main>
  );
}
