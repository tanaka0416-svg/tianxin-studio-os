import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import App from "./App";

const task = {
  id: "task-1",
  title: "整理本週待辦",
  status: "TODO",
  created_at: "2026-11-14T03:00:00Z",
  updated_at: "2026-11-14T03:00:00Z",
};

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

describe("task center", () => {
  it("shows the approved studio brand names without a logo mark", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: true, json: async () => [] }));
    render(<App />);

    const brand = screen.getByRole("link", {
      name: "田薪個人工作室 TianxinStudio OS 任務中心首頁",
    });
    expect(within(brand).getByText("田薪個人工作室")).toBeInTheDocument();
    expect(within(brand).getByText("TianxinStudio OS")).toBeInTheDocument();
    expect(within(brand).queryByText("天")).not.toBeInTheDocument();
    expect(brand.querySelector(".brand-mark")).toBeNull();
  });

  it("shows the task list and saves a status change", async () => {
    const fetchMock = vi.fn()
      .mockResolvedValueOnce({ ok: true, json: async () => [task] })
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({ ...task, status: "IN_PROGRESS" }),
      })
      .mockResolvedValueOnce({ ok: true, json: async () => [{ ...task, status: "IN_PROGRESS" }] });
    vi.stubGlobal("fetch", fetchMock);
    const user = userEvent.setup();

    render(<App />);

    expect(await screen.findByText("整理本週待辦")).toBeInTheDocument();
    const status = screen.getByRole("combobox", { name: "狀態：整理本週待辦" });
    await user.selectOptions(status, "IN_PROGRESS");

    await waitFor(() => expect(status).toHaveValue("IN_PROGRESS"));
    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(3));
    expect(fetchMock.mock.calls[1]).toEqual([
      "http://127.0.0.1:8000/api/tasks/task-1/status",
      expect.objectContaining({ method: "PATCH" }),
    ]);
  });

  it("rolls status back and shows a safe message when the update fails", async () => {
    const fetchMock = vi.fn()
      .mockResolvedValueOnce({ ok: true, json: async () => [task] })
      .mockResolvedValueOnce({
        ok: false,
        status: 422,
        json: async () => ({ detail: "person@example.com backend error" }),
      });
    vi.stubGlobal("fetch", fetchMock);
    const user = userEvent.setup();
    render(<App />);

    const status = await screen.findByRole("combobox", { name: "狀態：整理本週待辦" });
    await user.selectOptions(status, "IN_PROGRESS");

    expect(await screen.findByRole("alert")).toHaveTextContent("無法更新任務狀態");
    expect(screen.getByRole("alert")).not.toHaveTextContent("person@example.com");
    await waitFor(() => expect(status).toHaveValue("TODO"));
  });

  it("creates a task and adds the returned task to the list", async () => {
    const fetchMock = vi.fn()
      .mockResolvedValueOnce({ ok: true, json: async () => [] })
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({ ...task, title: "規劃產品更新" }),
      })
      .mockResolvedValueOnce({ ok: true, json: async () => [{ ...task, title: "規劃產品更新" }] });
    vi.stubGlobal("fetch", fetchMock);
    const user = userEvent.setup();

    render(<App />);

    await user.type(await screen.findByRole("textbox", { name: "任務標題" }), "規劃產品更新");
    await user.click(screen.getByRole("button", { name: "新增任務" }));

    expect(await screen.findByText("規劃產品更新")).toBeInTheDocument();
    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(3));
    expect(fetchMock.mock.calls[1]).toEqual([
      "http://127.0.0.1:8000/api/tasks",
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify({
          title: "規劃產品更新",
          description: null,
          department: null,
          assigned_ai: null,
          priority: "MEDIUM",
          due_date: null,
        }),
      }),
    ]);
  });

  it("clears an unclassified title after the gateway rejects it", async () => {
    const fetchMock = vi.fn()
      .mockResolvedValueOnce({ ok: true, json: async () => [] })
      .mockResolvedValueOnce({
        ok: false,
        status: 422,
        json: async () => ({ detail: "任務標題包含無法安全分類的資料，未建立任務。" }),
      });
    vi.stubGlobal("fetch", fetchMock);
    const user = userEvent.setup();

    render(<App />);
    const input = await screen.findByRole("textbox", { name: "任務標題" });
    await user.type(input, "護照號碼：格式不明");
    await user.click(screen.getByRole("button", { name: "新增任務" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("已清除標題與描述");
    await waitFor(() => expect(input).toHaveValue(""));
    expect(screen.queryByText("護照號碼：格式不明")).not.toBeInTheDocument();
  });

  it("shows the phase-two form defaults and optional fields", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: true, json: async () => [] }));
    render(<App />);

    await screen.findByText("目前沒有任務，從上方新增第一項工作。");
    expect(screen.getByRole("textbox", { name: "任務標題" })).toHaveValue("");
    expect(screen.getByRole("textbox", { name: "任務描述" })).toHaveValue("");
    expect(screen.getByRole("textbox", { name: "任務描述" })).toHaveAttribute("maxLength", "5000");
    expect(screen.getByRole("combobox", { name: "部門" })).toHaveValue("");
    expect(screen.getByRole("combobox", { name: "主要負責 AI" })).toHaveValue("");
    expect(screen.getByRole("combobox", { name: "優先級" })).toHaveValue("MEDIUM");
    expect(screen.getByLabelText("截止日")).toHaveValue("");
    expect(screen.getByText("負責 AI 僅為任務指派紀錄，目前未串接自動執行。")).toBeInTheDocument();
  });

  it("sends the new task fields and resets the form after success", async () => {
    const created = {
      ...task,
      id: "phase-two-task",
      title: "整理規格",
      description: "檢查 API",
      department: "DEVELOPMENT",
      assigned_ai: "CODEX",
      priority: "HIGH",
      due_date: "2026-12-31",
    };
    const fetchMock = vi.fn()
      .mockResolvedValueOnce({ ok: true, json: async () => [] })
      .mockResolvedValueOnce({ ok: true, json: async () => created })
      .mockResolvedValueOnce({ ok: true, json: async () => [created] });
    vi.stubGlobal("fetch", fetchMock);
    const user = userEvent.setup();
    render(<App />);

    await user.type(await screen.findByRole("textbox", { name: "任務標題" }), "整理規格");
    await user.type(screen.getByRole("textbox", { name: "任務描述" }), "檢查 API");
    await user.selectOptions(screen.getByRole("combobox", { name: "部門" }), "DEVELOPMENT");
    await user.selectOptions(screen.getByRole("combobox", { name: "主要負責 AI" }), "CODEX");
    await user.selectOptions(screen.getByRole("combobox", { name: "優先級" }), "HIGH");
    await user.type(screen.getByLabelText("截止日"), "2026-12-31");
    await user.click(screen.getByRole("button", { name: "新增任務" }));

    expect(await screen.findByText("整理規格")).toBeInTheDocument();
    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(3));
    expect(fetchMock.mock.calls[1]).toEqual([
      "http://127.0.0.1:8000/api/tasks",
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify({
          title: "整理規格",
          description: "檢查 API",
          department: "DEVELOPMENT",
          assigned_ai: "CODEX",
          priority: "HIGH",
          due_date: "2026-12-31",
        }),
      }),
    ]);
    expect(screen.getByRole("textbox", { name: "任務標題" })).toHaveValue("");
    expect(screen.getByRole("textbox", { name: "任務描述" })).toHaveValue("");
    expect(screen.getByRole("combobox", { name: "部門" })).toHaveValue("");
    expect(screen.getByRole("combobox", { name: "主要負責 AI" })).toHaveValue("");
    expect(screen.getByRole("combobox", { name: "優先級" })).toHaveValue("MEDIUM");
    expect(screen.getByLabelText("截止日")).toHaveValue("");
  });

  it("keeps a created task if the initial list request finishes afterward", async () => {
    let resolveInitialList!: (value: { ok: boolean; json: () => Promise<typeof task[]> }) => void;
    const initialList = new Promise<{ ok: boolean; json: () => Promise<typeof task[]> }>((resolve) => {
      resolveInitialList = resolve;
    });
    const created = { ...task, id: "created-during-load", title: "載入期間建立" };
    const fetchMock = vi.fn()
      .mockReturnValueOnce(initialList)
      .mockResolvedValueOnce({ ok: true, json: async () => created })
      .mockResolvedValueOnce({ ok: true, json: async () => [created] });
    vi.stubGlobal("fetch", fetchMock);
    const user = userEvent.setup();
    render(<App />);

    await user.type(screen.getByRole("textbox", { name: "任務標題" }), "載入期間建立");
    await user.click(screen.getByRole("button", { name: "新增任務" }));
    await waitFor(() => expect(screen.getByRole("textbox", { name: "任務標題" })).toHaveValue(""));
    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(3));
    resolveInitialList({ ok: true, json: async () => [] });

    expect(await screen.findByText("載入期間建立")).toBeInTheDocument();
  });

  it("does not overwrite the selected AI when the department changes", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: true, json: async () => [] }));
    const user = userEvent.setup();
    render(<App />);

    const department = await screen.findByRole("combobox", { name: "部門" });
    const assignedAI = screen.getByRole("combobox", { name: "主要負責 AI" });
    await user.selectOptions(assignedAI, "CLAUDE");
    await user.selectOptions(department, "FINANCE");

    expect(assignedAI).toHaveValue("CLAUDE");
  });

  it("shows task metadata and supports keyboard description expansion", async () => {
    const longDescription = "這是一段需要展開的任務描述。".repeat(12);
    const completeTask = {
      ...task,
      description: longDescription,
      department: "DEVELOPMENT",
      assigned_ai: "CODEX",
      priority: "URGENT",
      due_date: "2026-12-31",
    };
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: true, json: async () => [completeTask] }));
    const user = userEvent.setup();
    render(<App />);

    const taskRow = (await screen.findByText("整理本週待辦")).closest("li");
    expect(taskRow).not.toBeNull();
    expect(within(taskRow!).getByText("開發部")).toBeInTheDocument();
    expect(within(taskRow!).getByText("Codex")).toBeInTheDocument();
    expect(within(taskRow!).getByText("緊急")).toBeInTheDocument();
    expect(within(taskRow!).getByText("2026-12-31")).toBeInTheDocument();
    const descriptionToggle = screen.getByRole("button", { name: "展開描述：整理本週待辦" });
    expect(descriptionToggle).toHaveAttribute("aria-expanded", "false");
    descriptionToggle.focus();
    await user.keyboard("{Enter}");
    expect(screen.getByRole("button", { name: "收合描述：整理本週待辦" })).toHaveAttribute(
      "aria-expanded",
      "true",
    );
    await user.keyboard(" ");
    expect(screen.getByRole("button", { name: "展開描述：整理本週待辦" })).toHaveAttribute(
      "aria-expanded",
      "false",
    );
  });

  it("shows unassigned values for a legacy task without phase-two fields", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: true, json: async () => [task] }));
    render(<App />);

    const row = await screen.findByText("整理本週待辦");
    const taskRow = row.closest("li");
    expect(taskRow).toHaveTextContent("未指派");
    expect(taskRow).toHaveTextContent("一般");
    expect(taskRow).toHaveTextContent("未設定");
    expect(taskRow).not.toHaveTextContent("描述");
  });

  it("clears text after a generic 422 without showing the backend body", async () => {
    const fetchMock = vi.fn()
      .mockResolvedValueOnce({ ok: true, json: async () => [] })
      .mockResolvedValueOnce({
        ok: false,
        status: 422,
        json: async () => ({ detail: "person@example.com 原始後端內容" }),
      });
    vi.stubGlobal("fetch", fetchMock);
    const user = userEvent.setup();
    render(<App />);

    const titleInput = await screen.findByRole("textbox", { name: "任務標題" });
    const descriptionInput = screen.getByRole("textbox", { name: "任務描述" });
    await user.type(titleInput, "合成敏感標題");
    await user.type(descriptionInput, "合成敏感描述");
    await user.selectOptions(screen.getByRole("combobox", { name: "主要負責 AI" }), "CODEX");
    await user.click(screen.getByRole("button", { name: "新增任務" }));

    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent("已清除標題與描述");
    expect(alert).not.toHaveTextContent("person@example.com");
    expect(titleInput).toHaveValue("");
    expect(descriptionInput).toHaveValue("");
    expect(screen.getByRole("combobox", { name: "主要負責 AI" })).toHaveValue("CODEX");
    expect(screen.queryByText("合成敏感標題")).not.toBeInTheDocument();
    expect(screen.queryByText("合成敏感描述")).not.toBeInTheDocument();
  });

  it("prevents duplicate submits while a request is pending", async () => {
    let resolveCreate!: (value: { ok: boolean; json: () => Promise<typeof task> }) => void;
    const pendingCreate = new Promise<{ ok: boolean; json: () => Promise<typeof task> }>((resolve) => {
      resolveCreate = resolve;
    });
    const fetchMock = vi.fn()
      .mockResolvedValueOnce({ ok: true, json: async () => [] })
      .mockReturnValueOnce(pendingCreate)
      .mockResolvedValueOnce({ ok: true, json: async () => [{ ...task, title: "單次送出" }] });
    vi.stubGlobal("fetch", fetchMock);
    const user = userEvent.setup();
    render(<App />);

    await user.type(await screen.findByRole("textbox", { name: "任務標題" }), "單次送出");
    const submit = screen.getByRole("button", { name: "新增任務" });
    await user.dblClick(submit);
    await waitFor(() => expect(submit).toBeDisabled());
    expect(fetchMock.mock.calls.filter((call) => call[1]?.method === "POST")).toHaveLength(1);
    resolveCreate({ ok: true, json: async () => ({ ...task, title: "單次送出" }) });
    expect(await screen.findByText("單次送出")).toBeInTheDocument();
  });

  it("does not retry or claim success after a network error and can reload to confirm", async () => {
    const fetchMock = vi.fn()
      .mockResolvedValueOnce({ ok: true, json: async () => [] })
      .mockRejectedValueOnce(new Error("person@example.com network failure"))
      .mockResolvedValueOnce({ ok: true, json: async () => [task] });
    vi.stubGlobal("fetch", fetchMock);
    const user = userEvent.setup();
    render(<App />);

    const titleInput = await screen.findByRole("textbox", { name: "任務標題" });
    await user.type(titleInput, "待確認任務");
    await user.click(screen.getByRole("button", { name: "新增任務" }));

    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent("結果尚待確認");
    expect(alert).not.toHaveTextContent("person@example.com");
    expect(titleInput).toHaveValue("待確認任務");
    expect(screen.queryByText("待確認任務")).not.toBeInTheDocument();
    expect(fetchMock.mock.calls.filter((call) => call[1]?.method === "POST")).toHaveLength(1);

    await user.click(screen.getByRole("button", { name: "重新載入任務清單" }));
    expect(await screen.findByText("整理本週待辦")).toBeInTheDocument();
    expect(fetchMock.mock.calls.filter((call) => call[1]?.method === "POST")).toHaveLength(1);
  });

  it("loads with the default created-time ascending sort and displays the current result count", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: true, json: async () => [task] }));
    render(<App />);

    expect(await screen.findByText("符合目前條件：1 項")).toBeInTheDocument();
    const [url] = vi.mocked(fetch).mock.calls[0];
    expect(String(url)).toContain("sort_by=created_at");
    expect(String(url)).toContain("order=asc");
    expect(new URL(String(url)).searchParams.getAll("sort_by")).toHaveLength(1);
    expect(new URL(String(url)).searchParams.getAll("order")).toHaveLength(1);
  });

  it("sends each selected filter once and combines filter dimensions", async () => {
    const fetchMock = vi.fn().mockResolvedValue({ ok: true, json: async () => [task] });
    vi.stubGlobal("fetch", fetchMock);
    const user = userEvent.setup();
    render(<App />);

    await screen.findByText("符合目前條件：1 項");
    await user.selectOptions(screen.getByRole("combobox", { name: "狀態篩選" }), "TODO");
    await user.selectOptions(screen.getByRole("combobox", { name: "部門篩選" }), "DEVELOPMENT");
    await user.selectOptions(screen.getByRole("combobox", { name: "主要負責 AI 篩選" }), "CODEX");
    await user.selectOptions(screen.getByRole("combobox", { name: "優先級篩選" }), "HIGH");

    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(5));
    const [url] = fetchMock.mock.calls.at(-1)!;
    const params = new URL(String(url)).searchParams;
    for (const [key, value] of Object.entries({
      status: "TODO",
      department: "DEVELOPMENT",
      assigned_ai: "CODEX",
      priority: "HIGH",
    })) {
      expect(params.get(key)).toBe(value);
      expect(params.getAll(key)).toHaveLength(1);
    }
  });

  it.each([
    ["狀態篩選", "status", "DONE"],
    ["部門篩選", "department", "LEGAL"],
    ["主要負責 AI 篩選", "assigned_ai", "CLAUDE"],
    ["優先級篩選", "priority", "URGENT"],
  ])("sends the selected %s value as a single API parameter", async (label, key, value) => {
    const fetchMock = vi.fn().mockResolvedValue({ ok: true, json: async () => [] });
    vi.stubGlobal("fetch", fetchMock);
    const user = userEvent.setup();
    render(<App />);

    await screen.findByText("目前沒有任務，從上方新增第一項工作。");
    await user.selectOptions(screen.getByRole("combobox", { name: label }), value);
    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(2));

    const params = new URL(String(fetchMock.mock.calls.at(-1)![0])).searchParams;
    expect(params.get(key)).toBe(value);
    expect(params.getAll(key)).toHaveLength(1);
  });

  it("changes sort field and direction using the selected field's Traditional Chinese labels", async () => {
    const fetchMock = vi.fn().mockResolvedValue({ ok: true, json: async () => [] });
    vi.stubGlobal("fetch", fetchMock);
    const user = userEvent.setup();
    render(<App />);

    await screen.findByText("目前沒有任務，從上方新增第一項工作。");
    await user.selectOptions(screen.getByRole("combobox", { name: "排序欄位" }), "due_date");
    expect(screen.getByRole("combobox", { name: "排序方向" })).toHaveDisplayValue("由近到遠");
    await user.selectOptions(screen.getByRole("combobox", { name: "排序方向" }), "desc");

    const [url] = fetchMock.mock.calls.at(-1)!;
    const params = new URL(String(url)).searchParams;
    expect(params.get("sort_by")).toBe("due_date");
    expect(params.get("order")).toBe("desc");
    expect(params.getAll("sort_by")).toHaveLength(1);
    expect(params.getAll("order")).toHaveLength(1);
    expect(screen.getByRole("combobox", { name: "排序方向" })).toHaveDisplayValue("由遠到近");
  });

  it.each([
    ["created_at", "asc", "由舊到新"],
    ["created_at", "desc", "由新到舊"],
    ["updated_at", "asc", "由舊到新"],
    ["updated_at", "desc", "由新到舊"],
    ["due_date", "asc", "由近到遠"],
    ["due_date", "desc", "由遠到近"],
    ["priority", "asc", "由低到高"],
    ["priority", "desc", "由高到低"],
  ])("queries %s in %s order with its matching label", async (sortBy, order, label) => {
    const fetchMock = vi.fn().mockResolvedValue({ ok: true, json: async () => [] });
    vi.stubGlobal("fetch", fetchMock);
    const user = userEvent.setup();
    render(<App />);

    await screen.findByText("目前沒有任務，從上方新增第一項工作。");
    await user.selectOptions(screen.getByRole("combobox", { name: "排序欄位" }), sortBy);
    await user.selectOptions(screen.getByRole("combobox", { name: "排序方向" }), order);

    const params = new URL(String(fetchMock.mock.calls.at(-1)![0])).searchParams;
    expect(params.get("sort_by")).toBe(sortBy);
    expect(params.get("order")).toBe(order);
    expect(params.getAll("sort_by")).toHaveLength(1);
    expect(params.getAll("order")).toHaveLength(1);
    expect(screen.getByRole("combobox", { name: "排序方向" })).toHaveDisplayValue(label);
  });

  it("clears only filters while retaining the selected sort", async () => {
    const fetchMock = vi.fn().mockResolvedValue({ ok: true, json: async () => [] });
    vi.stubGlobal("fetch", fetchMock);
    const user = userEvent.setup();
    render(<App />);

    await screen.findByText("目前沒有任務，從上方新增第一項工作。");
    await user.selectOptions(screen.getByRole("combobox", { name: "部門篩選" }), "LEGAL");
    await user.selectOptions(screen.getByRole("combobox", { name: "排序欄位" }), "priority");
    await user.selectOptions(screen.getByRole("combobox", { name: "排序方向" }), "desc");
    await user.click(screen.getByRole("button", { name: "清除篩選" }));

    const [url] = fetchMock.mock.calls.at(-1)!;
    const params = new URL(String(url)).searchParams;
    expect(params.has("status")).toBe(false);
    expect(params.has("department")).toBe(false);
    expect(params.has("assigned_ai")).toBe(false);
    expect(params.has("priority")).toBe(false);
    expect(params.get("sort_by")).toBe("priority");
    expect(params.get("order")).toBe("desc");
    expect(screen.getByRole("combobox", { name: "部門篩選" })).toHaveValue("");
  });

  it("ignores an older filter response after a newer query has completed", async () => {
    let resolveOld!: (value: { ok: boolean; json: () => Promise<typeof task[]> }) => void;
    const oldResponse = new Promise<{ ok: boolean; json: () => Promise<typeof task[]> }>((resolve) => {
      resolveOld = resolve;
    });
    const newerTask = { ...task, id: "newer", title: "新條件結果" };
    const fetchMock = vi.fn()
      .mockResolvedValueOnce({ ok: true, json: async () => [task] })
      .mockReturnValueOnce(oldResponse)
      .mockResolvedValueOnce({ ok: true, json: async () => [newerTask] });
    vi.stubGlobal("fetch", fetchMock);
    const user = userEvent.setup();
    render(<App />);

    await screen.findByText("符合目前條件：1 項");
    const department = screen.getByRole("combobox", { name: "部門篩選" });
    await user.selectOptions(department, "LEGAL");
    await user.selectOptions(department, "DEVELOPMENT");
    expect(await screen.findByText("新條件結果")).toBeInTheDocument();
    resolveOld({ ok: true, json: async () => [task] });

    await waitFor(() => expect(screen.queryByText("整理本週待辦")).not.toBeInTheDocument());
    expect(screen.getByText("符合目前條件：1 項")).toBeInTheDocument();
  });

  it("keeps prior results and offers a retry after a query failure without showing a stale count", async () => {
    const fetchMock = vi.fn()
      .mockResolvedValueOnce({ ok: true, json: async () => [task] })
      .mockRejectedValueOnce(new Error("private backend detail"))
      .mockResolvedValueOnce({ ok: true, json: async () => [task] });
    vi.stubGlobal("fetch", fetchMock);
    const user = userEvent.setup();
    render(<App />);

    await screen.findByText("符合目前條件：1 項");
    await user.selectOptions(screen.getByRole("combobox", { name: "部門篩選" }), "LEGAL");
    expect(await screen.findByRole("alert")).toHaveTextContent("載入失敗，目前顯示先前結果");
    expect(screen.getByText("整理本週待辦")).toBeInTheDocument();
    expect(screen.queryByText("符合目前條件：1 項")).not.toBeInTheDocument();
    expect(screen.getByRole("alert")).not.toHaveTextContent("private backend detail");
    await user.click(screen.getByRole("button", { name: "以目前條件重試" }));
    expect(await screen.findByText("符合目前條件：1 項")).toBeInTheDocument();
    expect(new URL(String(fetchMock.mock.calls.at(-1)![0])).searchParams.get("department")).toBe("LEGAL");
  });

  it("distinguishes no matching tasks from an empty task database", async () => {
    const fetchMock = vi.fn()
      .mockResolvedValueOnce({ ok: true, json: async () => [task] })
      .mockResolvedValueOnce({ ok: true, json: async () => [] });
    vi.stubGlobal("fetch", fetchMock);
    const user = userEvent.setup();
    render(<App />);

    await screen.findByText("符合目前條件：1 項");
    await user.selectOptions(screen.getByRole("combobox", { name: "部門篩選" }), "LEGAL");

    expect(await screen.findByText("沒有符合目前篩選條件的任務。")).toBeInTheDocument();
    expect(screen.queryByText("目前沒有任務，從上方新增第一項工作。")).not.toBeInTheDocument();
    expect(screen.getByText("符合目前條件：0 項")).toBeInTheDocument();
  });

  it("refreshes with current filters after creation without inserting a non-matching task", async () => {
    const created = { ...task, id: "created", title: "新建立任務", department: "LEGAL" };
    const fetchMock = vi.fn()
      .mockResolvedValueOnce({ ok: true, json: async () => [task] })
      .mockResolvedValueOnce({ ok: true, json: async () => [task] })
      .mockResolvedValueOnce({ ok: true, json: async () => created })
      .mockResolvedValueOnce({ ok: true, json: async () => [task] });
    vi.stubGlobal("fetch", fetchMock);
    const user = userEvent.setup();
    render(<App />);

    await screen.findByText("符合目前條件：1 項");
    await user.selectOptions(screen.getByRole("combobox", { name: "部門篩選" }), "DEVELOPMENT");
    await user.type(screen.getByRole("textbox", { name: "任務標題" }), "新建立任務");
    await user.selectOptions(screen.getByRole("combobox", { name: "部門" }), "LEGAL");
    await user.click(screen.getByRole("button", { name: "新增任務" }));

    expect(await screen.findByRole("status")).toHaveTextContent("任務已建立");
    expect(await screen.findByText("整理本週待辦")).toBeInTheDocument();
    expect(screen.queryByText("新建立任務")).not.toBeInTheDocument();
    expect(new URL(String(fetchMock.mock.calls.at(-1)![0])).searchParams.get("department")).toBe("DEVELOPMENT");
  });

  it("removes a task after status update when it no longer matches the status filter", async () => {
    const fetchMock = vi.fn()
      .mockResolvedValueOnce({ ok: true, json: async () => [task] })
      .mockResolvedValueOnce({ ok: true, json: async () => [task] })
      .mockResolvedValueOnce({ ok: true, json: async () => ({ ...task, status: "DONE" }) })
      .mockResolvedValueOnce({ ok: true, json: async () => [] });
    vi.stubGlobal("fetch", fetchMock);
    const user = userEvent.setup();
    render(<App />);

    await screen.findByText("符合目前條件：1 項");
    await user.selectOptions(screen.getByRole("combobox", { name: "狀態篩選" }), "TODO");
    const statusControl = await screen.findByRole("combobox", { name: "狀態：整理本週待辦" });
    await user.selectOptions(statusControl, "DONE");

    expect(await screen.findByText("沒有符合目前篩選條件的任務。")).toBeInTheDocument();
    expect(screen.queryByText("整理本週待辦")).not.toBeInTheDocument();
    expect(screen.getByText("符合目前條件：0 項")).toBeInTheDocument();
  });

  it("reports a successful status update separately when refreshing the list fails", async () => {
    const fetchMock = vi.fn()
      .mockResolvedValueOnce({ ok: true, json: async () => [task] })
      .mockResolvedValueOnce({ ok: true, json: async () => ({ ...task, status: "IN_PROGRESS" }) })
      .mockRejectedValueOnce(new Error("private list error"));
    vi.stubGlobal("fetch", fetchMock);
    const user = userEvent.setup();
    render(<App />);

    await screen.findByText("符合目前條件：1 項");
    const statusControl = screen.getByRole("combobox", { name: "狀態：整理本週待辦" });
    await user.selectOptions(statusControl, "IN_PROGRESS");

    expect(await screen.findByRole("alert")).toHaveTextContent("狀態已更新，但清單重新載入失敗");
    expect(statusControl).toHaveValue("IN_PROGRESS");
    expect(screen.getByText("整理本週待辦")).toBeInTheDocument();
    expect(screen.queryByText("符合目前條件：1 項")).not.toBeInTheDocument();
    expect(screen.getByRole("alert")).not.toHaveTextContent("private list error");
  });

  it("shows loading state without presenting the previous result count", async () => {
    let resolveRefresh!: (value: { ok: boolean; json: () => Promise<typeof task[]> }) => void;
    const pending = new Promise<{ ok: boolean; json: () => Promise<typeof task[]> }>((resolve) => {
      resolveRefresh = resolve;
    });
    const fetchMock = vi.fn()
      .mockResolvedValueOnce({ ok: true, json: async () => [task] })
      .mockReturnValueOnce(pending);
    vi.stubGlobal("fetch", fetchMock);
    const user = userEvent.setup();
    render(<App />);

    await screen.findByText("符合目前條件：1 項");
    await user.selectOptions(screen.getByRole("combobox", { name: "部門篩選" }), "LEGAL");
    expect(screen.getByText("正在載入符合條件的任務…")).toBeInTheDocument();
    expect(screen.queryByText("符合目前條件：1 項")).not.toBeInTheDocument();
    resolveRefresh({ ok: true, json: async () => [] });
    expect(await screen.findByText("符合目前條件：0 項")).toBeInTheDocument();
  });

  it("offers a mobile collapsible filter group and reports active filter count", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: true, json: async () => [] }));
    const user = userEvent.setup();
    render(<App />);

    const summary = await screen.findByText("篩選條件");
    expect(summary.closest("summary")).toBeInTheDocument();
    await user.selectOptions(screen.getByRole("combobox", { name: "部門篩選" }), "LEGAL");
    expect(screen.getByText("已套用 1 項篩選")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "清除篩選" })).toBeInTheDocument();
    expect(screen.getByRole("combobox", { name: "排序方向" })).toBeInTheDocument();
  });
});
