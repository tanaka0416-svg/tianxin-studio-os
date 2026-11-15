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
    suspected_type: str | None = None


@dataclass(frozen=True)
class RedactionResult:
    text: str
    records: tuple[RedactionRecord, ...]


@dataclass(frozen=True)
class RedactionDecision:
    field_name: str
    start_position: int
    end_position: int
    action: str
    keep_original_confirmed: bool = False


class InvalidRedactionDecision(Exception):
    """A submitted decision is stale, duplicated, unsupported, or unconfirmed."""

    def __init__(self):
        super().__init__("脫敏處理選擇無效或尚未確認。")


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
_NATIONAL_ID = re.compile(r"(?<![A-Z0-9])[A-Z][12]\d{8}(?![A-Z0-9])", re.I)
_PASSPORT = re.compile(r"(?:護照(?:號碼|號)?|passport(?:\s*(?:no\.?|number))?)\s*[:：#]?\s*([A-Z0-9]{6,12})(?![A-Z0-9])", re.I)
_BANK_ACCOUNT = re.compile(r"(?:銀行帳號|金融帳號|bank\s+account(?:\s+number)?)\s*[:：#]?\s*(\d(?:[ -]?\d){5,31})(?!\d)", re.I)
_CARD = re.compile(r"(?<!\d)(?:\d[ -]?){12,18}\d(?!\d)")
_TAX_ID = re.compile(r"(?:統一編號|統編|tax\s+id)\s*[:：#]?\s*(\d{8})(?![A-Z0-9])", re.I)
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
    re.compile(r"(?<![\w.+-])[A-Z0-9._%+-]{1,64}@[A-Z0-9.-]{0,253}", re.I),
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


def _uncertain_record(
    text: str, field_name: str, cue: re.Match[str], suspected_type: str
) -> RedactionRecord:
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
        suspected_type=suspected_type,
    )


def _shape_record(text: str, field_name: str, start: int, end: int) -> RedactionRecord:
    return RedactionRecord(
        field_name=field_name,
        original_length=end - start,
        redaction_type="UNCERTAIN",
        start_position=start,
        end_position=end,
        created_at=datetime.now(timezone.utc),
        suspected_type="UNCERTAIN",
    )


_APPROVED_ACTIONS = (
    "[REDACTED]",
    "[REDACTED_EMAIL]",
    "[REDACTED_PHONE]",
    "[REDACTED_ID]",
    "[REDACTED_PASSPORT]",
    "[REDACTED_BANK_ACCOUNT]",
    "[REDACTED_TAX_ID]",
    "[REDACTED_CREDIT_CARD]",
    "KEEP_ORIGINAL",
)


def redact_text(
    text: str,
    field_name: str,
    decisions: tuple[RedactionDecision, ...] = (),
) -> RedactionResult:
    if not isinstance(text, str):
        raise UncertainSensitiveData(())

    matches = _collect_matches(text)
    uncertain: list[RedactionRecord] = []
    for pattern, expected_types in _UNCERTAIN_CUES:
        for cue in pattern.finditer(text):
            cue_end = cue.end()
            candidate = _uncertain_record(
                text, field_name, cue, sorted(expected_types)[0]
            )
            has_value = any(
                item.redaction_type in expected_types
                and item.start >= cue_end
                and item.start - cue_end <= 32
                for item in matches
            )
            # A recognized value is already handled by a trusted automatic rule,
            # even when the surrounding label suggests a different category.
            has_value = has_value or any(
                item.start < candidate.end_position
                and item.end > candidate.start_position
                for item in matches
            )
            if not has_value:
                uncertain.append(candidate)

    for pattern in _PII_SHAPES:
        for candidate in pattern.finditer(text):
            start, end = candidate.span()
            if not any(item.start < end and item.end > start for item in matches):
                uncertain.append(_shape_record(text, field_name, start, end))

    uncertain.sort(
        key=lambda item: (item.start_position, -(item.end_position - item.start_position))
    )
    deduplicated: list[RedactionRecord] = []
    for record in uncertain:
        if deduplicated and record.start_position < deduplicated[-1].end_position:
            continue
        deduplicated.append(record)
    decisions = tuple(decisions)
    if any(decision.field_name != field_name for decision in decisions):
        raise InvalidRedactionDecision()
    decision_spans = [(decision.start_position, decision.end_position) for decision in decisions]
    if len(set(decision_spans)) != len(decision_spans):
        raise InvalidRedactionDecision()

    candidate_by_span = {
        (record.start_position, record.end_position): record for record in deduplicated
    }
    if any(span not in candidate_by_span for span in decision_spans):
        raise InvalidRedactionDecision()
    for decision in decisions:
        if decision.action not in _APPROVED_ACTIONS:
            raise InvalidRedactionDecision()
        if decision.action == "KEEP_ORIGINAL":
            if not decision.keep_original_confirmed:
                raise InvalidRedactionDecision()
        elif decision.keep_original_confirmed:
            raise InvalidRedactionDecision()

    decisions_by_span = {
        (decision.start_position, decision.end_position): decision for decision in decisions
    }
    unresolved = tuple(
        record
        for record in deduplicated
        if (record.start_position, record.end_position) not in decisions_by_span
    )
    if unresolved:
        raise UncertainSensitiveData(unresolved)

    replacements: list[tuple[int, int, str]] = []
    records = [
        RedactionRecord(
            field_name=field_name,
            original_length=match.end - match.start,
            redaction_type=match.redaction_type,
            start_position=match.start,
            end_position=match.end,
            created_at=datetime.now(timezone.utc),
        )
        for match in matches
    ]
    for span, decision in decisions_by_span.items():
        candidate = candidate_by_span[span]
        if decision.action == "KEEP_ORIGINAL":
            event_type = "MANUAL_KEEP_CONFIRMED"
        else:
            event_type = (
                "MANUAL_REDACTED"
                if decision.action == "[REDACTED]"
                else f"MANUAL_{decision.action[1:-1]}"
            )
            replacements.append((candidate.start_position, candidate.end_position, decision.action))
        records.append(
            RedactionRecord(
                field_name=field_name,
                original_length=candidate.original_length,
                redaction_type=event_type,
                start_position=candidate.start_position,
                end_position=candidate.end_position,
                created_at=datetime.now(timezone.utc),
                suspected_type=candidate.suspected_type,
            )
        )
    replacements.extend((match.start, match.end, match.placeholder) for match in matches)
    sanitized = text
    for start, end, placeholder in sorted(replacements, reverse=True):
        sanitized = sanitized[:start] + placeholder + sanitized[end:]
    records.sort(key=lambda record: (record.start_position, record.end_position))
    return RedactionResult(text=sanitized, records=tuple(records))
