import pytest

from app.services.redaction_gate import (
    InvalidRedactionDecision,
    RedactionDecision,
    UncertainSensitiveData,
    redact_text,
)


@pytest.mark.parametrize(
    ("text", "kind", "placeholder"),
    [
        ("寄信給 person@example.com", "EMAIL", "[REDACTED_EMAIL]"),
        ("手機 0912345678", "PHONE", "[REDACTED_PHONE]"),
        ("身分證 A123456789", "ID", "[REDACTED_ID]"),
        ("護照號碼：AB1234567", "PASSPORT", "[REDACTED_PASSPORT]"),
        ("銀行帳號：1234567890123", "BANK_ACCOUNT", "[REDACTED_BANK_ACCOUNT]"),
        ("信用卡 4111111111111111", "CREDIT_CARD", "[REDACTED_CREDIT_CARD]"),
        ("統一編號：12345678", "TAX_ID", "[REDACTED_TAX_ID]"),
    ],
)
def test_redact_supported_sensitive_values(text, kind, placeholder):
    result = redact_text(text, field_name="title")

    assert placeholder in result.text
    assert result.records[0].redaction_type == kind
    assert result.records[0].original_length > 0
    assert result.records[0].start_position < result.records[0].end_position
    assert text[result.records[0].start_position : result.records[0].end_position]
    assert "person@example.com" not in result.text
    assert "0912345678" not in result.text


def test_gate_supports_description_field_without_persisting_raw_value():
    result = redact_text("寄給 person@example.com", field_name="description")

    assert result.text == "寄給 [REDACTED_EMAIL]"
    assert result.records[0].field_name == "description"


@pytest.mark.parametrize(
    "text",
    [
        "護照號碼：不確定格式",
        "銀行帳號：格式不明",
        "Email：格式不明",
    ],
)
def test_uncertain_sensitive_candidate_fails_closed(text):
    with pytest.raises(UncertainSensitiveData) as error:
        redact_text(text, field_name="title")

    assert error.value.records
    assert error.value.records[0].redaction_type == "UNCERTAIN"
    assert not hasattr(error.value.records[0], "original_value")


@pytest.mark.parametrize(
    "text",
    [
        "聯絡方式 broken@",
        "票號 1234567890123",
        "文件代碼 AB1234567",
        "護照號碼：格式不明，Email：person@example.com",
    ],
)
def test_unrecognized_pii_shaped_values_fail_closed_even_beside_known_values(text):
    with pytest.raises(UncertainSensitiveData) as error:
        redact_text(text, field_name="title")

    assert error.value.records
    assert all(record.redaction_type == "UNCERTAIN" for record in error.value.records)


@pytest.mark.parametrize("text", ["", "普通工作事項", "提醒我準備會議資料"])
def test_non_sensitive_or_empty_text_is_returned_unchanged(text):
    result = redact_text(text, field_name="title")

    assert result.text == text
    assert result.records == ()


@pytest.mark.parametrize(
    ("action", "expected"),
    [
        ("[REDACTED]", "[REDACTED]"),
        ("[REDACTED_EMAIL]", "[REDACTED_EMAIL]"),
        ("[REDACTED_PHONE]", "[REDACTED_PHONE]"),
        ("[REDACTED_ID]", "[REDACTED_ID]"),
        ("[REDACTED_PASSPORT]", "[REDACTED_PASSPORT]"),
        ("[REDACTED_BANK_ACCOUNT]", "[REDACTED_BANK_ACCOUNT]"),
        ("[REDACTED_TAX_ID]", "[REDACTED_TAX_ID]"),
        ("[REDACTED_CREDIT_CARD]", "[REDACTED_CREDIT_CARD]"),
    ],
)
def test_uncertain_candidate_can_be_replaced_by_each_approved_marker(action, expected):
    text = "聯絡方式 broken@"
    with pytest.raises(UncertainSensitiveData) as error:
        redact_text(text, field_name="title")
    candidate = error.value.records[0]

    result = redact_text(
        text,
        field_name="title",
        decisions=(
            RedactionDecision(
                field_name="title",
                start_position=candidate.start_position,
                end_position=candidate.end_position,
                action=action,
            ),
        ),
    )

    assert result.text == f"聯絡方式 {expected}"
    assert result.records[0].redaction_type.startswith("MANUAL_")
    assert text[candidate.start_position : candidate.end_position] not in result.text


def test_uncertain_candidate_can_be_kept_only_after_explicit_confirmation():
    text = "文件代碼 AB1234567"
    with pytest.raises(UncertainSensitiveData) as error:
        redact_text(text, field_name="title")
    candidate = error.value.records[0]

    with pytest.raises(InvalidRedactionDecision):
        redact_text(
            text,
            field_name="title",
            decisions=(
                RedactionDecision(
                    field_name="title",
                    start_position=candidate.start_position,
                    end_position=candidate.end_position,
                    action="KEEP_ORIGINAL",
                ),
            ),
        )

    result = redact_text(
        text,
        field_name="title",
        decisions=(
            RedactionDecision(
                field_name="title",
                start_position=candidate.start_position,
                end_position=candidate.end_position,
                action="KEEP_ORIGINAL",
                keep_original_confirmed=True,
            ),
        ),
    )

    assert result.text == text
    assert result.records[0].redaction_type == "MANUAL_KEEP_CONFIRMED"


def test_stale_or_duplicate_decisions_are_rejected():
    text = "聯絡方式 broken@"
    with pytest.raises(UncertainSensitiveData) as error:
        redact_text(text, field_name="title")
    candidate = error.value.records[0]

    with pytest.raises(InvalidRedactionDecision):
        redact_text(
            text,
            field_name="title",
            decisions=(
                RedactionDecision(
                    field_name="title",
                    start_position=candidate.start_position + 1,
                    end_position=candidate.end_position,
                    action="[REDACTED]",
                ),
            ),
        )

    with pytest.raises(InvalidRedactionDecision):
        redact_text(
            text,
            field_name="title",
            decisions=(
                RedactionDecision(
                    field_name="title",
                    start_position=candidate.start_position,
                    end_position=candidate.end_position,
                    action="[REDACTED]",
                ),
                RedactionDecision(
                    field_name="title",
                    start_position=candidate.start_position,
                    end_position=candidate.end_position,
                    action="[REDACTED_EMAIL]",
                ),
            ),
        )


@pytest.mark.parametrize(
    ("value", "is_supported"),
    [("A" * 6, True), ("A" * 12, True), ("A" * 5, False), ("A" * 13, False)],
)
def test_passport_rule_respects_length_boundaries(value, is_supported):
    text = f"護照號碼：{value}"

    if is_supported:
        result = redact_text(text, field_name="title")
        assert result.text == "護照號碼：[REDACTED_PASSPORT]"
        assert value not in result.text
    else:
        with pytest.raises(UncertainSensitiveData) as error:
            redact_text(text, field_name="title")
        candidate = error.value.records[0]
        assert text[candidate.start_position : candidate.end_position] == value


@pytest.mark.parametrize(
    ("value", "is_supported"),
    [
        ("123456", True),
        ("12345678901234567890123456789012", True),
        ("12345", False),
        ("123456789012345678901234567890123", False),
    ],
)
def test_bank_account_rule_respects_length_boundaries(value, is_supported):
    text = f"銀行帳號：{value}"

    if is_supported:
        result = redact_text(text, field_name="title")
        assert result.text == "銀行帳號：[REDACTED_BANK_ACCOUNT]"
        assert value not in result.text
    else:
        with pytest.raises(UncertainSensitiveData) as error:
            redact_text(text, field_name="title")
        candidate = error.value.records[0]
        assert text[candidate.start_position : candidate.end_position] == value


@pytest.mark.parametrize(
    ("text", "value"),
    [
        ("身分證字號：A123456789X", "A123456789X"),
        ("統一編號：12345678X", "12345678X"),
    ],
)
def test_identifier_rules_do_not_partially_redact_longer_tokens(text, value):
    with pytest.raises(UncertainSensitiveData) as error:
        redact_text(text, field_name="title")

    candidate = error.value.records[0]
    assert text[candidate.start_position : candidate.end_position] == value


@pytest.mark.parametrize(
    ("text", "candidate_value"),
    [
        ("手機號碼：091234567", "091234567"),
        ("手機號碼：09123456789", "09123456789"),
        ("身分證字號：A12345678", "A12345678"),
        ("身分證字號：A1234567890", "A1234567890"),
        ("統一編號：1234567", "1234567"),
        ("統一編號：123456789", "123456789"),
        ("信用卡號碼：411111111111", "411111111111"),
        ("信用卡號碼：11111111111111111111", "11111111111111111111"),
    ],
)
def test_values_outside_trusted_rule_lengths_are_intercepted_as_whole_candidates(
    text, candidate_value
):
    with pytest.raises(UncertainSensitiveData) as error:
        redact_text(text, field_name="title")

    candidate = error.value.records[0]
    assert text[candidate.start_position : candidate.end_position] == candidate_value
