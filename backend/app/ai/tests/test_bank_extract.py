from datetime import UTC, datetime

from app.ai.bank_extract import BankExtract, extract_bank_notification
from app.ai.schemas import AiError
from app.ai.tests.fake_claude import FakeClaude

POSTED = datetime(2026, 11, 18, 5, 1, tzinfo=UTC)
TEXT = "TK xxxx1234 -45,000 VND luc 18-11-2026 12:01:33. ND: com trua"


def _parsed(**kw):
    base = {
        "is_transaction": True,
        "direction": "out",
        "amount_vnd": 45000,
        "account_last4": "1234",
        "txn_type": "purchase",
        "counterparty": None,
        "description": "com trua",
        "occurred_at": None,
        "confidence": 0.95,
    }
    return BankExtract(**{**base, **kw})


def _reply(parsed, **kw):
    return {"content": [{"type": "text", "text": parsed.model_dump_json()}], "parsed_output": parsed, **kw}


def test_extracts_with_haiku_low_effort(make_client):
    fake = FakeClaude([_reply(_parsed())])
    client = make_client(fake)
    out = extract_bank_notification(1, "vcb", "Biến động số dư", TEXT, POSTED, client=client)
    assert out.amount_vnd == 45000 and out.direction == "out" and out.txn_type == "purchase"
    req = fake.requests[0]
    assert req["model"] == "claude-haiku-5-5" and req["output_config"] == {"effort": "low"}
    assert req["output_format"] == "BankExtract"
    assert "xxxx1234" in req["messages"][0]["content"] and "Nguồn: vcb" in req["messages"][0]["content"]
    assert client.recorder.records[0].purpose == "bank_extract"


def test_cleans_out_of_range_values(make_client):
    fake = FakeClaude([_reply(_parsed(amount_vnd=-5, account_last4="12345678", confidence=1.7))])
    out = extract_bank_notification(1, "tcb", "", TEXT, POSTED, client=make_client(fake))
    assert out.amount_vnd is None and out.account_last4 is None and out.confidence == 1.0


def test_refusal_cut_or_error_returns_none(make_client):
    for item in (
        _reply(_parsed(), stop_reason="refusal"),
        _reply(_parsed(), stop_reason="max_tokens"),
        AiError("AI_UNAVAILABLE", "Không gọi được Claude."),
    ):
        assert (
            extract_bank_notification(1, "momo", "", TEXT, POSTED, client=make_client(FakeClaude([item])))
            is None
        )


def test_mask_drops_balance_and_long_account_numbers():
    from app.ai.bank_extract import mask_sensitive

    raw = "So du TK VCB 0011001234567 -45,000 VND luc 18-11-2026 12:01:33. So du 1,234,567 VND. Ref MBVCB.123456"
    out = mask_sensitive(raw)
    assert "0011001234567" not in out and "xxxx4567" in out
    assert "1,234,567" not in out and "[đã bỏ số dư]" in out
    assert "-45,000 VND" in out and "18-11-2026" in out and "MBVCB.123456" in out
    tcb = mask_sensitive("TK 1903xxxx5678 | -45,000 VND | SD: 2,000,000 VND | ND: com trua")
    assert "xxxx5678" in tcb and "2,000,000" not in tcb
    assert mask_sensitive("Thanh toan 1500000 VND tai Highlands") == "Thanh toan 1500000 VND tai Highlands"


def test_otp_never_reaches_claude(make_client):
    fake = FakeClaude([])
    out = extract_bank_notification(
        1, "vcb", "VCB", "Ma OTP cua Quy khach la 123456. Khong chia se ma.", POSTED, client=make_client(fake)
    )
    assert out.is_transaction is False and fake.requests == []


def test_masking_applied_before_sending(make_client):
    fake = FakeClaude([_reply(_parsed())])
    extract_bank_notification(
        1, "vcb", "", "TK 0011001234567 -45,000 VND. SD 9,999,999 VND", POSTED, client=make_client(fake)
    )
    sent = fake.requests[0]["messages"][0]["content"]
    assert "0011001234567" not in sent and "9,999,999" not in sent


def test_classify():
    from app.ai.bank_extract import NOT_TRANSACTION, classify

    assert classify(None) == "ignore"
    assert classify(NOT_TRANSACTION) == "ignore"
    assert classify(_parsed(amount_vnd=None)) == "ignore"
    assert classify(_parsed(confidence=0.5)) == "review"
    assert classify(_parsed()) == "record"


def test_not_transaction_is_normalized(make_client):
    fake = FakeClaude([_reply(_parsed(is_transaction=False, confidence=0.9))])
    out = extract_bank_notification(
        1, "momo", "", "Uu dai 50% cho don dau tien", POSTED, client=make_client(fake)
    )
    assert out.is_transaction is False and out.amount_vnd is None and out.direction is None
