from fastapi import APIRouter, HTTPException, Request, status
from sqlalchemy import select

from app.models.task import RedactionEvent, Task
from app.schemas.task import TaskCreate, TaskRead, TaskStatusUpdate
from app.services.redaction_gate import UncertainSensitiveData, redact_text


router = APIRouter(prefix="/api/tasks", tags=["tasks"])


def _save_records(session, records) -> None:
    for record in records:
        session.add(
            RedactionEvent(
                field_name=record.field_name,
                original_length=record.original_length,
                redaction_type=record.redaction_type,
                start_position=record.start_position,
                end_position=record.end_position,
                created_at=record.created_at,
            )
        )


@router.post("", response_model=TaskRead, status_code=status.HTTP_201_CREATED)
def create_task(payload: TaskCreate, request: Request):
    session_factory = request.app.state.session_factory
    with session_factory() as session:
        redaction_records = []
        safe_fields = {}
        uncertain = False
        for field_name, value in (("title", payload.title), ("description", payload.description)):
            if value is None:
                safe_fields[field_name] = None
                continue
            try:
                result = redact_text(value, field_name=field_name)
                safe_fields[field_name] = result.text
                redaction_records.extend(result.records)
            except UncertainSensitiveData as error:
                uncertain = True
                redaction_records.extend(error.records)

        if uncertain:
            _save_records(session, redaction_records)
            session.commit()
            raise HTTPException(
                status_code=422,
                detail="任務文字包含無法安全分類的資料，未建立任務。",
            ) from None

        task = Task(
            title=safe_fields["title"],
            description=safe_fields["description"],
            department=payload.department.value if payload.department else None,
            assigned_ai=payload.assigned_ai.value if payload.assigned_ai else None,
            priority=payload.priority.value,
            due_date=payload.due_date,
            status="TODO",
        )
        session.add(task)
        _save_records(session, redaction_records)
        session.commit()
        session.refresh(task)
        return task


@router.get("", response_model=list[TaskRead])
def list_tasks(request: Request):
    with request.app.state.session_factory() as session:
        return list(session.scalars(select(Task).order_by(Task.created_at, Task.id)))


@router.patch("/{task_id}/status", response_model=TaskRead)
def update_task_status(task_id: str, payload: TaskStatusUpdate, request: Request):
    with request.app.state.session_factory() as session:
        task = session.get(Task, task_id)
        if task is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="找不到任務。")
        task.status = payload.status.value
        session.commit()
        session.refresh(task)
        return task
