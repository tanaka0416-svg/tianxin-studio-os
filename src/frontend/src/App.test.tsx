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
  it("shows the task list and saves a status change", async () => {
    const fetchMock = vi.fn()
      .mockResolvedValueOnce({ ok: true, json: async () => [task] })
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({ ...task, status: "IN_PROGRESS" }),
      });
    vi.stubGlobal("fetch", fetchMock);
    const user = userEvent.setup();

    render(<App />);

    expect(await screen.findByText("整理本週待辦")).toBeInTheDocument();
    const status = screen.getByRole("combobox", { name: "狀態：整理本週待辦" });
    await user.selectOptions(status, "IN_PROGRESS");

    await waitFor(() => expect(status).toHaveValue("IN_PROGRESS"));
    expect(fetchMock).toHaveBeenLastCalledWith(
      "http://127.0.0.1:8000/api/tasks/task-1/status",
      expect.objectContaining({ method: "PATCH" }),
    );
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
      });
    vi.stubGlobal("fetch", fetchMock);
    const user = userEvent.setup();

    render(<App />);

    await user.type(await screen.findByRole("textbox", { name: "任務標題" }), "規劃產品更新");
    await user.click(screen.getByRole("button", { name: "新增任務" }));

    expect(await screen.findByText("規劃產品更新")).toBeInTheDocument();
    expect(fetchMock).toHaveBeenLastCalledWith(
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
    );
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
      .mockResolvedValueOnce({ ok: true, json: async () => created });
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
    expect(fetchMock).toHaveBeenLastCalledWith(
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
    );
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
      .mockResolvedValueOnce({ ok: true, json: async () => created });
    vi.stubGlobal("fetch", fetchMock);
    const user = userEvent.setup();
    render(<App />);

    await user.type(screen.getByRole("textbox", { name: "任務標題" }), "載入期間建立");
    await user.click(screen.getByRole("button", { name: "新增任務" }));
    await waitFor(() => expect(screen.getByRole("textbox", { name: "任務標題" })).toHaveValue(""));
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
      .mockReturnValueOnce(pendingCreate);
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
});
