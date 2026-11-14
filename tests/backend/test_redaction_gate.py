import pytest

from app.services.redaction_gate import (
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
