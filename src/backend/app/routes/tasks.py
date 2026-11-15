from typing import Annotated, Literal

from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Query, Request, Response, status
from sqlalchemy import case, select

from app.models.task import RedactionEvent, Task
from app.schemas.task import (
    AssignedAI,
    Department,
    RedactionDecisionInput,
    TaskCreate,
    TaskPriority,
    TaskRead,
    TaskStatus,
    TaskStatusUpdate,
    TaskUpdate,
)
from app.services.redaction_gate import (
    InvalidRedactionDecision,
    RedactionDecision,
    UncertainSensitiveData,
    redact_text,
)


router = APIRouter(prefix="/api/tasks", tags=["tasks"])
REDACTION_ACTIONS = [
    "[REDACTED]",
    "[REDACTED_EMAIL]",
    "[REDACTED_PHONE]",
    "[REDACTED_ID]",
    "[REDACTED_PASSPORT]",
    "[REDACTED_BANK_ACCOUNT]",
    "[REDACTED_TAX_ID]",
    "[REDACTED_CREDIT_CARD]",
    "KEEP_ORIGINAL",
]


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
        uncertain_records = []
        safe_fields = {}
        invalid_decision = False
        decisions_by_field: dict[str, list[RedactionDecisionInput]] = {
            "title": [],
            "description": [],
        }
        for decision in payload.redaction_decisions:
            decisions_by_field[decision.field_name].append(decision)

        for field_name, value in (("title", payload.title), ("description", payload.description)):
            if value is None:
                if decisions_by_field[field_name]:
                    invalid_decision = True
                safe_fields[field_name] = None
                continue
            try:
                result = redact_text(
                    value,
                    field_name=field_name,
                    decisions=tuple(
                        RedactionDecision(
                            field_name=decision.field_name,
                            start_position=decision.start_position,
                            end_position=decision.end_position,
                            action=decision.action,
                            keep_original_confirmed=decision.keep_original_confirmed,
                        )
                        for decision in decisions_by_field[field_name]
                    ),
                )
                safe_fields[field_name] = result.text
                redaction_records.extend(result.records)
            except UncertainSensitiveData as error:
                uncertain_records.extend(error.records)
            except InvalidRedactionDecision:
                invalid_decision = True
                try:
                    redact_text(value, field_name=field_name)
                except UncertainSensitiveData as error:
                    uncertain_records.extend(error.records)

        if uncertain_records:
            _save_records(session, uncertain_records)
            session.commit()
            if invalid_decision:
                raise HTTPException(
                    status_code=422,
                    detail="脫敏處理選擇無效；請重新檢查候選內容。",
                ) from None
            raise HTTPException(
                status_code=422,
                detail={
                    "code": "SENSITIVE_CANDIDATES",
                    "message": "任務文字包含需要人工選擇處理方式的候選內容。",
                    "candidates": [
                        {
                            "field_name": record.field_name,
                            "start_position": record.start_position,
                            "end_position": record.end_position,
                            "suspected_type": record.suspected_type or "UNCERTAIN",
                        }
                        for record in uncertain_records
                    ],
                    "options": REDACTION_ACTIONS,
                },
            ) from None
        if invalid_decision:
            raise HTTPException(
                status_code=422,
                detail="脫敏處理選擇無效；請重新檢查候選內容。",
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
def list_tasks(
    request: Request,
    status_filter: Annotated[TaskStatus | None, Query(alias="status")] = None,
    department: Department | None = None,
    assigned_ai: AssignedAI | None = None,
    priority: TaskPriority | None = None,
    sort_by: Literal["created_at", "updated_at", "due_date", "priority"] = "created_at",
    order: Literal["asc", "desc"] = "asc",
):
    for name in ("status", "department", "assigned_ai", "priority", "sort_by", "order"):
        if len(request.query_params.getlist(name)) > 1:
            raise HTTPException(
                status_code=422,
                detail="查詢參數無效；每個參數只能提供一個值。",
            )

    statement = select(Task).where(Task.archived_at.is_(None))
    if status_filter is not None:
        statement = statement.where(Task.status == status_filter.value)
    if department is not None:
        statement = statement.where(Task.department == department.value)
    if assigned_ai is not None:
        statement = statement.where(Task.assigned_ai == assigned_ai.value)
    if priority is not None:
        statement = statement.where(Task.priority == priority.value)

    priority_rank = case(
        (Task.priority == "LOW", 0),
        (Task.priority == "MEDIUM", 1),
        (Task.priority == "HIGH", 2),
        (Task.priority == "URGENT", 3),
        else_=4,
    )
    sortable_columns = {
        "created_at": Task.created_at,
        "updated_at": Task.updated_at,
        "due_date": Task.due_date,
        "priority": priority_rank,
    }
    sort_column = sortable_columns[sort_by]
    primary_order = sort_column.asc() if order == "asc" else sort_column.desc()
    ordering = []
    if sort_by == "due_date":
        ordering.append(case((Task.due_date.is_(None), 1), else_=0).asc())
    ordering.extend((primary_order, Task.created_at.asc(), Task.id.asc()))

    with request.app.state.session_factory() as session:
        return list(session.scalars(statement.order_by(*ordering)))


@router.patch("/{task_id}", response_model=TaskRead)
def update_task(task_id: str, payload: TaskUpdate, request: Request):
    with request.app.state.session_factory() as session:
        task = session.scalar(
            select(Task).where(Task.id == task_id, Task.archived_at.is_(None))
        )
        if task is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="找不到任務。")

        submitted = payload.model_dump(exclude_unset=True)
        decisions_by_field: dict[str, list[RedactionDecisionInput]] = {
            "title": [],
            "description": [],
        }
        submitted.pop("redaction_decisions", None)
        for decision in payload.redaction_decisions:
            decisions_by_field[decision.field_name].append(decision)

        invalid_decision = any(
            decisions_by_field[field_name] and field_name not in submitted
            for field_name in decisions_by_field
        )
        safe_text_fields = {}
        redaction_records = []
        uncertain_records = []
        for field_name in ("title", "description"):
            if field_name not in submitted:
                continue
            value = submitted[field_name]
            field_decisions = decisions_by_field[field_name]
            if value is None:
                if field_decisions:
                    invalid_decision = True
                safe_text_fields[field_name] = None
                continue
            try:
                result = redact_text(
                    value,
                    field_name=field_name,
                    decisions=tuple(
                        RedactionDecision(
                            field_name=decision.field_name,
                            start_position=decision.start_position,
                            end_position=decision.end_position,
                            action=decision.action,
                            keep_original_confirmed=decision.keep_original_confirmed,
                        )
                        for decision in field_decisions
                    ),
                )
                safe_text_fields[field_name] = result.text
                redaction_records.extend(result.records)
            except UncertainSensitiveData as error:
                uncertain_records.extend(
                    record
                    for record in error.records
                    if not any(
                        known.field_name == field_name
                        and known.start_position == record.start_position
                        and known.end_position == record.end_position
                        for known in uncertain_records
                    )
                )
            except InvalidRedactionDecision:
                invalid_decision = True
                try:
                    redact_text(value, field_name=field_name)
                except UncertainSensitiveData as error:
                    uncertain_records.extend(
                        record
                        for record in error.records
                        if not any(
                            known.field_name == field_name
                            and known.start_position == record.start_position
                            and known.end_position == record.end_position
                            for known in uncertain_records
                        )
                    )

        if uncertain_records:
            _save_records(session, uncertain_records)
            session.commit()
            if invalid_decision:
                raise HTTPException(
                    status_code=422,
                    detail="脫敏處理選擇無效；請重新檢查候選內容。",
                ) from None
            raise HTTPException(
                    status_code=422,
                detail={
                    "code": "SENSITIVE_CANDIDATES",
                    "message": "任務文字包含需要人工選擇處理方式的候選內容。",
                    "candidates": [
                        {
                            "field_name": record.field_name,
                            "start_position": record.start_position,
                            "end_position": record.end_position,
                            "suspected_type": record.suspected_type or "UNCERTAIN",
                        }
                        for record in uncertain_records
                    ],
                    "options": REDACTION_ACTIONS,
                },
            ) from None
        if invalid_decision:
            raise HTTPException(
                status_code=422,
                detail="脫敏處理選擇無效；請重新檢查候選內容。",
            ) from None

        submitted.update(safe_text_fields)
        for field_name in ("department", "assigned_ai", "priority"):
            if field_name in submitted and submitted[field_name] is not None:
                submitted[field_name] = submitted[field_name].value
        for field_name, value in submitted.items():
            setattr(task, field_name, value)
        _save_records(session, redaction_records)
        session.commit()
        session.refresh(task)
        return task


@router.patch("/{task_id}/archive", status_code=status.HTTP_204_NO_CONTENT)
def archive_task(task_id: str, request: Request):
    with request.app.state.session_factory() as session:
        task = session.get(Task, task_id)
        if task is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="找不到任務。")
        if task.archived_at is None:
            task.archived_at = datetime.now(timezone.utc)
            session.commit()
        return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.patch("/{task_id}/status", response_model=TaskRead)
def update_task_status(task_id: str, payload: TaskStatusUpdate, request: Request):
    with request.app.state.session_factory() as session:
        task = session.scalar(
            select(Task).where(Task.id == task_id, Task.archived_at.is_(None))
        )
        if task is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="找不到任務。")
        task.status = payload.status.value
        session.commit()
        session.refresh(task)
        return task
