from datetime import datetime
import logging
import sqlite3

import pytest
from fastapi import HTTPException, Request
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.main import create_app
from app.migrations import upgrade_database
from app.models.task import RedactionEvent, Task
from app.routes.tasks import create_task, list_tasks, update_task_status
from app.schemas.task import TaskCreate, TaskRead, TaskStatusUpdate


def make_app(tmp_path):
    database = tmp_path / "tasks.sqlite3"
    upgrade_database(database)
    return create_app(f"sqlite:///{database}")


def make_request(app):
    return Request({"type": "http", "app": app})


def response_data(task):
    return TaskRead.model_validate(task).model_dump(mode="json")


def test_create_task_starts_todo_and_redacts_before_storage(tmp_path):
    app = make_app(tmp_path)
    task = create_task(
        TaskCreate(title="寄信給 person@example.com"), make_request(app)
    )
    result = response_data(task)

    assert result["title"] == "寄信給 [REDACTED_EMAIL]"
    assert result["status"] == "TODO"
    assert result["created_at"].endswith("Z")

    with app.state.session_factory() as session:
        stored_task = session.get(Task, result["id"])
        event = session.query(RedactionEvent).one()
        assert stored_task.title == result["title"]
        assert event.redaction_type == "EMAIL"
        assert event.original_length == len("person@example.com")
        assert event.start_position == len("寄信給 ")
        assert event.end_position > event.start_position
        assert not hasattr(event, "original_value")
        assert event.created_at.tzinfo is None or event.created_at.utcoffset() is None


def test_rejects_blank_or_missing_title(tmp_path):
    app = make_app(tmp_path)
    with pytest.raises(ValidationError):
        TaskCreate(title="   ")
    with pytest.raises(ValidationError):
        TaskCreate.model_validate({})

    assert list_tasks(make_request(app)) == []


def test_uncertain_sensitive_text_is_not_saved_and_metadata_is_recorded(tmp_path):
    app = make_app(tmp_path)
    with pytest.raises(HTTPException) as error:
        create_task(TaskCreate(title="護照號碼：格式不明"), make_request(app))

    assert error.value.status_code == 422
    assert list_tasks(make_request(app)) == []
    with app.state.session_factory() as session:
        event = session.query(RedactionEvent).one()
        assert event.redaction_type == "UNCERTAIN"
        assert event.original_length == len("格式不明")
        assert not hasattr(event, "original_value")


def test_list_returns_saved_tasks_in_creation_order(tmp_path):
    app = make_app(tmp_path)
    first = create_task(TaskCreate(title="先建立"), make_request(app))
    second = create_task(TaskCreate(title="後建立"), make_request(app))

    result = [response_data(task) for task in list_tasks(make_request(app))]

    assert [task["id"] for task in result] == [first.id, second.id]
    assert [task["status"] for task in result] == ["TODO", "TODO"]


def test_status_change_updates_task_and_timestamp(tmp_path):
    app = make_app(tmp_path)
    task = create_task(TaskCreate(title="狀態測試"), make_request(app))

    updated = update_task_status(
        task.id,
        TaskStatusUpdate(status="IN_PROGRESS"),
        make_request(app),
    )

    result = response_data(updated)
    assert result["status"] == "IN_PROGRESS"
    assert datetime.fromisoformat(result["updated_at"].replace("Z", "+00:00")) >= datetime.fromisoformat(
        response_data(task)["updated_at"].replace("Z", "+00:00")
    )


def test_rejects_unsupported_status_and_returns_404_for_missing_task(tmp_path):
    app = make_app(tmp_path)
    with pytest.raises(ValidationError):
        TaskStatusUpdate(status="ARCHIVED")

    with pytest.raises(HTTPException) as error:
        update_task_status(
            "00000000-0000-0000-0000-000000000000",
            TaskStatusUpdate(status="DONE"),
            make_request(app),
        )

    assert error.value.status_code == 404


@pytest.mark.parametrize(
    "status_value", ["TODO", "IN_PROGRESS", "REVIEW", "BLOCKED", "RETURNED", "DONE"]
)
def test_all_existing_task_statuses_remain_updatable(tmp_path, status_value):
    app = make_app(tmp_path)
    task = create_task(TaskCreate(title="狀態回歸"), make_request(app))

    updated = update_task_status(
        task.id,
        TaskStatusUpdate(status=status_value),
        make_request(app),
    )

    assert updated.status == status_value


def test_upgraded_synthetic_legacy_task_remains_readable_over_api(tmp_path):
    database = tmp_path / "legacy.sqlite3"
    with sqlite3.connect(database) as connection:
        connection.executescript(
            """
            CREATE TABLE tasks (
                id VARCHAR(36) NOT NULL,
                title VARCHAR NOT NULL,
                status VARCHAR(20) NOT NULL,
                created_at DATETIME NOT NULL,
                updated_at DATETIME NOT NULL,
                CONSTRAINT ck_tasks_status CHECK (
                    status IN ('TODO', 'IN_PROGRESS', 'REVIEW', 'BLOCKED', 'RETURNED', 'DONE')
                ),
                PRIMARY KEY (id)
            );
            CREATE TABLE redaction_events (
                id VARCHAR(36) NOT NULL PRIMARY KEY,
                field_name VARCHAR(32) NOT NULL,
                original_length INTEGER NOT NULL,
                redaction_type VARCHAR(32) NOT NULL,
                start_position INTEGER NOT NULL,
                end_position INTEGER NOT NULL,
                created_at DATETIME NOT NULL
            );
            INSERT INTO tasks VALUES (
                'synthetic-legacy-task', '舊版合成任務', 'DONE',
                '2026-11-14T00:00:00+00:00', '2026-11-14T01:00:00+00:00'
            );
            """
        )

    upgrade_database(database)
    app = create_app(f"sqlite:///{database}")
    with TestClient(app) as client:
        response = client.get("/api/tasks")

    assert response.status_code == 200
    assert response.json() == [
        {
            "id": "synthetic-legacy-task",
            "title": "舊版合成任務",
            "status": "DONE",
            "description": None,
            "department": None,
            "assigned_ai": None,
            "priority": "MEDIUM",
            "due_date": None,
            "created_at": "2026-11-14T00:00:00Z",
            "updated_at": "2026-11-14T01:00:00Z",
        }
    ]


def test_http_create_and_list_round_trip_all_phase_two_fields(tmp_path):
    app = make_app(tmp_path)
    with TestClient(app) as client:
        response = client.post(
            "/api/tasks",
            json={
                "title": "整理開發規格",
                "description": "檢查 API 行為",
                "department": "DEVELOPMENT",
                "assigned_ai": "CODEX",
                "priority": "HIGH",
                "due_date": "2026-12-31",
            },
        )

        assert response.status_code == 201
        created = response.json()
        assert created["status"] == "TODO"
        assert created["description"] == "檢查 API 行為"
        assert created["department"] == "DEVELOPMENT"
        assert created["assigned_ai"] == "CODEX"
        assert created["priority"] == "HIGH"
        assert created["due_date"] == "2026-12-31"

        listed = client.get("/api/tasks")
        assert listed.status_code == 200
        assert listed.json() == [created]


def test_title_only_request_remains_compatible_and_uses_phase_two_defaults(tmp_path):
    app = make_app(tmp_path)
    with TestClient(app) as client:
        response = client.post("/api/tasks", json={"title": "第一階段相容"})

    assert response.status_code == 201
    assert response.json()["title"] == "第一階段相容"
    assert response.json()["status"] == "TODO"
    assert response.json()["description"] is None
    assert response.json()["department"] is None
    assert response.json()["assigned_ai"] is None
    assert response.json()["priority"] == "MEDIUM"
    assert response.json()["due_date"] is None


def test_explicit_null_optional_fields_and_blank_description_are_normalized(tmp_path):
    app = make_app(tmp_path)
    with TestClient(app) as client:
        response = client.post(
            "/api/tasks",
            json={
                "title": "空白描述",
                "description": "   \t ",
                "department": None,
                "assigned_ai": None,
                "due_date": None,
            },
        )

    assert response.status_code == 201
    assert response.json()["description"] is None
    assert response.json()["department"] is None
    assert response.json()["assigned_ai"] is None
    assert response.json()["priority"] == "MEDIUM"
    assert response.json()["due_date"] is None


@pytest.mark.parametrize(
    "invalid_field",
    [
        {"priority": None},
        {"department": "UNKNOWN_DEPARTMENT"},
        {"assigned_ai": "UNKNOWN_AI"},
        {"due_date": "2026-02-30"},
        {"due_date": "2026-12-31T00:00:00"},
        {"description": {"text": "person@example.com"}},
        {"description": "person@example.com " + "x" * 5000},
        {"status": "DONE"},
    ],
)
def test_invalid_field_errors_do_not_echo_sensitive_request_values(
    tmp_path, caplog, invalid_field
):
    app = make_app(tmp_path)
    raw_sensitive_value = "person@example.com"
    payload = {
        "title": f"聯絡 {raw_sensitive_value}",
        "description": f"備註 {raw_sensitive_value}",
        **invalid_field,
    }

    with TestClient(app) as client, caplog.at_level(logging.DEBUG):
        response = client.post("/api/tasks", json=payload)

    assert response.status_code == 422
    assert raw_sensitive_value not in response.text
    assert f"聯絡 {raw_sensitive_value}" not in response.text
    assert f"備註 {raw_sensitive_value}" not in response.text
    assert raw_sensitive_value not in caplog.text
    with app.state.session_factory() as session:
        assert session.query(Task).count() == 0


def test_description_is_redacted_and_audited_with_title_before_insert(tmp_path):
    app = make_app(tmp_path)
    with TestClient(app) as client:
        response = client.post(
            "/api/tasks",
            json={
                "title": "寄給 person@example.com",
                "description": "聯絡 0912345678",
            },
        )

    assert response.status_code == 201
    assert response.json()["title"] == "寄給 [REDACTED_EMAIL]"
    assert response.json()["description"] == "聯絡 [REDACTED_PHONE]"
    with app.state.session_factory() as session:
        task = session.get(Task, response.json()["id"])
        events = session.query(RedactionEvent).order_by(RedactionEvent.field_name).all()
        assert task.title == response.json()["title"]
        assert task.description == response.json()["description"]
        assert {event.field_name for event in events} == {"title", "description"}
        assert all(not hasattr(event, "original_value") for event in events)


def test_uncertain_description_rejects_whole_task_without_echoing_source(tmp_path, caplog):
    app = make_app(tmp_path)
    raw_description = "護照號碼：格式不明"
    with TestClient(app) as client, caplog.at_level(logging.DEBUG):
        response = client.post(
            "/api/tasks",
            json={"title": "安全標題", "description": raw_description},
        )

    assert response.status_code == 422
    assert raw_description not in response.text
    assert raw_description not in caplog.text
    with app.state.session_factory() as session:
        assert session.query(Task).count() == 0
        event = session.query(RedactionEvent).one()
        assert event.field_name == "description"
        assert event.redaction_type == "UNCERTAIN"
        assert not hasattr(event, "original_value")


@pytest.mark.parametrize("schema_kind", ["empty", "legacy", "unknown"])
def test_app_startup_safely_refuses_unversioned_or_unknown_schema(tmp_path, schema_kind):
    database = tmp_path / f"{schema_kind}.sqlite3"
    if schema_kind == "empty":
        sqlite3.connect(database).close()
    elif schema_kind == "legacy":
        with sqlite3.connect(database) as connection:
            connection.executescript(
                """
                CREATE TABLE tasks (
                    id VARCHAR(36) NOT NULL,
                    title VARCHAR NOT NULL,
                    status VARCHAR(20) NOT NULL,
                    created_at DATETIME NOT NULL,
                    updated_at DATETIME NOT NULL,
                    CONSTRAINT ck_tasks_status CHECK (
                        status IN ('TODO', 'IN_PROGRESS', 'REVIEW', 'BLOCKED', 'RETURNED', 'DONE')
                    ),
                    PRIMARY KEY (id)
                );
                CREATE TABLE redaction_events (
                    id VARCHAR(36) NOT NULL PRIMARY KEY,
                    field_name VARCHAR(32) NOT NULL,
                    original_length INTEGER NOT NULL,
                    redaction_type VARCHAR(32) NOT NULL,
                    start_position INTEGER NOT NULL,
                    end_position INTEGER NOT NULL,
                    created_at DATETIME NOT NULL
                );
                """
            )
    else:
        with sqlite3.connect(database) as connection:
            connection.execute("CREATE TABLE unrelated (value TEXT NOT NULL)")
            connection.execute("INSERT INTO unrelated VALUES ('synthetic')")
    app = create_app(f"sqlite:///{database}")

    with pytest.raises(RuntimeError, match="schema"):
        with TestClient(app):
            pass

    with sqlite3.connect(database) as connection:
        names = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
            )
        }
    expected_names = {
        "empty": set(),
        "legacy": {"tasks", "redaction_events"},
        "unknown": {"unrelated"},
    }
    assert names == expected_names[schema_kind]
