from datetime import date, datetime, timezone
from enum import Enum
import re
from typing import Literal

from pydantic import (
    AliasChoices,
    BaseModel,
    ConfigDict,
    Field,
    field_serializer,
    field_validator,
    model_validator,
)


class TaskStatus(str, Enum):
    TODO = "TODO"
    IN_PROGRESS = "IN_PROGRESS"
    REVIEW = "REVIEW"
    BLOCKED = "BLOCKED"
    RETURNED = "RETURNED"
    DONE = "DONE"


class Department(str, Enum):
    SECRETARIAT = "SECRETARIAT"
    LEGAL = "LEGAL"
    DEVELOPMENT = "DEVELOPMENT"
    MEDIA = "MEDIA"
    QA = "QA"
    FINANCE = "FINANCE"
    WEB = "WEB"
    DATA_GOVERNANCE = "DATA_GOVERNANCE"


class AssignedAI(str, Enum):
    CLAUDE = "CLAUDE"
    PERPLEXITY = "PERPLEXITY"
    CHATGPT = "CHATGPT"
    CODEX = "CODEX"
    GROK = "GROK"
    LOCAL_AI = "LOCAL_AI"


class TaskPriority(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    URGENT = "URGENT"


class RedactionDecisionInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    field_name: Literal["title", "description"]
    start_position: int = Field(ge=0)
    end_position: int = Field(gt=0)
    action: Literal[
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
    keep_original_confirmed: bool = False

    @model_validator(mode="after")
    def validate_confirmation(self):
        if self.end_position <= self.start_position:
            raise ValueError("脫敏候選位置無效")
        return self


class TaskCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str
    description: str | None = Field(default=None, max_length=5000)
    department: Department | None = None
    assigned_ai: AssignedAI | None = None
    priority: TaskPriority = TaskPriority.MEDIUM
    due_date: date | None = None
    redaction_decisions: list[RedactionDecisionInput] = Field(default_factory=list)

    @field_validator("title")
    @classmethod
    def title_must_not_be_blank(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("任務標題不可空白")
        return normalized

    @field_validator("description", mode="before")
    @classmethod
    def normalize_description(cls, value):
        if value is None:
            return None
        if not isinstance(value, str):
            return value
        normalized = value.strip()
        return normalized or None

    @field_validator("due_date", mode="before")
    @classmethod
    def require_iso_date(cls, value):
        if value is None or isinstance(value, date) and not isinstance(value, datetime):
            return value
        if not isinstance(value, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
            raise ValueError("截止日必須使用 YYYY-MM-DD 格式")
        return date.fromisoformat(value)


class TaskStatusUpdate(BaseModel):
    status: TaskStatus


class TaskUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    title: str | None = None
    description: str | None = Field(default=None, max_length=5000)
    department: Department | None = None
    assigned_ai: AssignedAI | None = Field(
        default=None, validation_alias=AliasChoices("primary_ai", "assigned_ai")
    )
    priority: TaskPriority | None = None
    due_date: date | None = None
    redaction_decisions: list[RedactionDecisionInput] = Field(default_factory=list)

    @field_validator("title")
    @classmethod
    def title_must_not_be_blank_or_null(cls, value: str | None) -> str:
        if value is None:
            raise ValueError("任務標題不可為空")
        normalized = value.strip()
        if not normalized:
            raise ValueError("任務標題不可空白")
        return normalized

    @field_validator("description", mode="before")
    @classmethod
    def normalize_description(cls, value):
        return TaskCreate.normalize_description(value)

    @field_validator("priority")
    @classmethod
    def priority_must_not_be_null(cls, value: TaskPriority | None) -> TaskPriority:
        if value is None:
            raise ValueError("優先級不可為空")
        return value

    @field_validator("due_date", mode="before")
    @classmethod
    def require_iso_date(cls, value):
        return TaskCreate.require_iso_date(value)

    @model_validator(mode="after")
    def require_mutable_field(self):
        mutable_fields = {
            "title",
            "description",
            "department",
            "assigned_ai",
            "priority",
            "due_date",
        }
        if not mutable_fields.intersection(self.model_fields_set):
            raise ValueError("請至少提供一個可更新欄位")
        return self


class TaskRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    title: str
    status: TaskStatus
    description: str | None
    department: Department | None
    assigned_ai: AssignedAI | None
    priority: TaskPriority
    due_date: date | None
    created_at: datetime
    updated_at: datetime

    @field_serializer("created_at", "updated_at")
    def serialize_utc(self, value: datetime) -> str:
        normalized = (
            value.replace(tzinfo=timezone.utc)
            if value.tzinfo is None
            else value.astimezone(timezone.utc)
        )
        return normalized.isoformat().replace("+00:00", "Z")
