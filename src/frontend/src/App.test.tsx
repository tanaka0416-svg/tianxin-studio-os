import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
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

    await user.type(await screen.findByRole("textbox", { name: "新增任務" }), "規劃產品更新");
    await user.click(screen.getByRole("button", { name: "新增任務" }));

    expect(await screen.findByText("規劃產品更新")).toBeInTheDocument();
    expect(fetchMock).toHaveBeenLastCalledWith(
      "http://127.0.0.1:8000/api/tasks",
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify({ title: "規劃產品更新" }),
      }),
    );
  });

  it("clears an unclassified title after the gateway rejects it", async () => {
    const fetchMock = vi.fn()
      .mockResolvedValueOnce({ ok: true, json: async () => [] })
      .mockResolvedValueOnce({
        ok: false,
        json: async () => ({ detail: "任務標題包含無法安全分類的資料，未建立任務。" }),
      });
    vi.stubGlobal("fetch", fetchMock);
    const user = userEvent.setup();

    render(<App />);
    const input = await screen.findByRole("textbox", { name: "新增任務" });
    await user.type(input, "護照號碼：格式不明");
    await user.click(screen.getByRole("button", { name: "新增任務" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("未建立任務");
    await waitFor(() => expect(input).toHaveValue(""));
    expect(screen.queryByText("護照號碼：格式不明")).not.toBeInTheDocument();
  });
});
