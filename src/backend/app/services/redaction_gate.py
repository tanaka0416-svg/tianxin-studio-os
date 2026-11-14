"""Local fail-closed text redaction for task fields; never stores source values."""

from dataclasses import dataclass
from datetime import datetime, timezone
import re


@dataclass(frozen=True)
class RedactionRecord:
    field_name: str
    original_length: int
    redaction_type: str
    start_position: int
    end_position: int
    created_at: datetime


@dataclass(frozen=True)
class RedactionResult:
    text: str
    records: tuple[RedactionRecord, ...]


class UncertainSensitiveData(Exception):
    def __init__(self, records: tuple[RedactionRecord, ...]):
        super().__init__("文字包含無法安全分類的敏感資料候選值。")
        self.records = records


@dataclass(frozen=True)
class _Match:
    start: int
    end: int
    redaction_type: str
    placeholder: str


_EMAIL = re.compile(r"(?<![\w.+-])[A-Z0-9.!#$%&'*+/=?^_`{|}~-]+@[A-Z0-9-]+(?:\.[A-Z0-9-]+)+", re.I)
_PHONE = re.compile(r"(?<!\d)(?:\+?886[- ]?9\d{2}[- ]?\d{3}[- ]?\d{3}|09\d{2}[- ]?\d{3}[- ]?\d{3})(?!\d)")
_NATIONAL_ID = re.compile(r"(?<![A-Z0-9])[A-Z][12]\d{8}(?!\d)", re.I)
_PASSPORT = re.compile(r"(?:護照(?:號碼|號)?|passport(?:\s*(?:no\.?|number))?)\s*[:：#]?\s*([A-Z0-9]{6,12})", re.I)
_BANK_ACCOUNT = re.compile(r"(?:銀行帳號|金融帳號|bank\s+account(?:\s+number)?)\s*[:：#]?\s*(\d(?:[ -]?\d){5,31})", re.I)
_CARD = re.compile(r"(?<!\d)(?:\d[ -]?){12,18}\d(?!\d)")
_TAX_ID = re.compile(r"(?:統一編號|統編|tax\s+id)\s*[:：#]?\s*(\d{8})(?!\d)", re.I)
_UNCERTAIN_CUES = (
    (re.compile(r"(?:身分證(?:字號)?|身份證(?:字號)?)", re.I), {"ID"}),
    (re.compile(r"(?:護照(?:號碼|號)?|passport(?:\s*(?:no\.?|number))?)", re.I), {"PASSPORT"}),
    (re.compile(r"(?:銀行帳號|金融帳號|bank\s+account(?:\s+number)?)", re.I), {"BANK_ACCOUNT"}),
    (re.compile(r"(?:信用卡(?:號碼)?|credit\s+card(?:\s+number)?)", re.I), {"CREDIT_CARD"}),
    (re.compile(r"(?:統一編號|統編|tax\s+id)", re.I), {"TAX_ID"}),
    (re.compile(r"(?:email|電子郵件)", re.I), {"EMAIL"}),
    (re.compile(r"(?:手機(?:號碼)?|行動電話)", re.I), {"PHONE"}),
)
_PII_SHAPES = (
    re.compile(r"(?<!\s)[A-Z0-9._%+-]{1,64}@[A-Z0-9.-]{0,253}", re.I),
    re.compile(r"(?<!\d)(?:\d[ -]?){7,18}\d(?!\d)"),
    re.compile(r"(?<![A-Z0-9])[A-Z]\d{8,10}(?!\d)", re.I),
    re.compile(r"(?<![A-Z0-9])[A-Z]{1,2}\d{6,9}(?!\d)", re.I),
    re.compile(r"(?<!\d)(?:\+?886|09)[\d -]{5,}"),
)


def _luhn_valid(value: str) -> bool:
    digits = [int(char) for char in value if char.isdigit()]
    if not 13 <= len(digits) <= 19:
        return False
    total = 0
    parity = len(digits) % 2
    for index, digit in enumerate(digits):
        if index % 2 == parity:
            digit *= 2
            if digit > 9:
                digit -= 9
        total += digit
    return total % 10 == 0


def _collect_matches(text: str) -> list[_Match]:
    candidates: list[_Match] = []
    for pattern, kind, placeholder, group in (
        (_EMAIL, "EMAIL", "[REDACTED_EMAIL]", 0),
        (_PHONE, "PHONE", "[REDACTED_PHONE]", 0),
        (_NATIONAL_ID, "ID", "[REDACTED_ID]", 0),
        (_PASSPORT, "PASSPORT", "[REDACTED_PASSPORT]", 1),
        (_BANK_ACCOUNT, "BANK_ACCOUNT", "[REDACTED_BANK_ACCOUNT]", 1),
        (_CARD, "CREDIT_CARD", "[REDACTED_CREDIT_CARD]", 0),
        (_TAX_ID, "TAX_ID", "[REDACTED_TAX_ID]", 1),
    ):
        for match in pattern.finditer(text):
            start, end = match.span(group)
            value = text[start:end]
            if kind == "CREDIT_CARD" and not _luhn_valid(value):
                continue
            candidates.append(_Match(start, end, kind, placeholder))

    selected: list[_Match] = []
    for candidate in sorted(candidates, key=lambda item: (item.start, -(item.end - item.start))):
        if selected and candidate.start < selected[-1].end:
            continue
        selected.append(candidate)
    return selected


def _uncertain_record(text: str, field_name: str, cue: re.Match[str]) -> RedactionRecord:
    start = cue.end()
    while start < len(text) and text[start] in " :：#-\t":
        start += 1
    end = start
    while end < len(text) and not text[end].isspace() and text[end] not in ",，;；。":
        end += 1
    if end == start:
        start = cue.start()
        end = cue.end()
    return RedactionRecord(
        field_name=field_name,
        original_length=max(1, end - start),
        redaction_type="UNCERTAIN",
        start_position=start,
        end_position=end,
        created_at=datetime.now(timezone.utc),
    )


def _shape_record(text: str, field_name: str, start: int, end: int) -> RedactionRecord:
    return RedactionRecord(
        field_name=field_name,
        original_length=end - start,
        redaction_type="UNCERTAIN",
        start_position=start,
        end_position=end,
        created_at=datetime.now(timezone.utc),
    )


def redact_text(text: str, field_name: str) -> RedactionResult:
    if not isinstance(text, str):
        raise UncertainSensitiveData(())

    matches = _collect_matches(text)
    uncertain: list[RedactionRecord] = []
    for pattern, expected_types in _UNCERTAIN_CUES:
        for cue in pattern.finditer(text):
            cue_end = cue.end()
            has_value = any(
                item.redaction_type in expected_types
                and item.start >= cue_end
                and item.start - cue_end <= 32
                for item in matches
            )
            if not has_value:
                uncertain.append(_uncertain_record(text, field_name, cue))

    for pattern in _PII_SHAPES:
        for candidate in pattern.finditer(text):
            start, end = candidate.span()
            if not any(item.start < end and item.end > start for item in matches):
                uncertain.append(_shape_record(text, field_name, start, end))

    uncertain.sort(key=lambda item: (item.start_position, item.end_position))
    deduplicated: list[RedactionRecord] = []
    for record in uncertain:
        if deduplicated and record.start_position < deduplicated[-1].end_position:
            continue
        deduplicated.append(record)
    if deduplicated:
        raise UncertainSensitiveData(tuple(deduplicated))

    records = tuple(
        RedactionRecord(
            field_name=field_name,
            original_length=match.end - match.start,
            redaction_type=match.redaction_type,
            start_position=match.start,
            end_position=match.end,
            created_at=datetime.now(timezone.utc),
        )
        for match in matches
    )
    sanitized = text
    for match in reversed(matches):
        sanitized = sanitized[: match.start] + match.placeholder + sanitized[match.end :]
    return RedactionResult(text=sanitized, records=records)
