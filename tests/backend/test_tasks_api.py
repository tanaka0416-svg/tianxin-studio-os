from datetime import datetime

import pytest
from fastapi import HTTPException, Request
from pydantic import ValidationError

from app.main import create_app
from app.models.task import Base, RedactionEvent, Task
from app.routes.tasks import create_task, list_tasks, update_task_status
from app.schemas.task import TaskCreate, TaskRead, TaskStatusUpdate


def make_app(tmp_path):
    app = create_app(f"sqlite:///{tmp_path / 'tasks.sqlite3'}")
    Base.metadata.create_all(bind=app.state.session_factory.kw["bind"])
    return app


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
