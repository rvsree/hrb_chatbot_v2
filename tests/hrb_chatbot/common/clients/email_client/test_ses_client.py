"""Tests for ses_client.py (Phase 136) - no real AWS call."""

from botocore.exceptions import ClientError

from src.hrb_chatbot.common.clients.email_client import ses_client


class _FakeSesClient:
    def __init__(self, should_fail: bool = False):
        self.should_fail = should_fail
        self.calls: list[dict] = []

    def send_email(self, **kwargs):
        self.calls.append(kwargs)
        if self.should_fail:
            raise ClientError({"Error": {"Code": "MessageRejected", "Message": "Email address not verified"}}, "SendEmail")
        return {"MessageId": "fake-message-id"}


def test_send_email_succeeds_and_calls_ses_with_the_right_shape(monkeypatch):
    fake = _FakeSesClient()
    monkeypatch.setattr(ses_client.boto3, "client", lambda service, region_name=None: fake)
    monkeypatch.setattr(ses_client, "read_setting", lambda value, name, default=None: "sender@example.com" if name == "SES_SENDER_EMAIL" else default)

    result = ses_client.send_email("someone@example.com", "Subject", "Body text")

    assert result == {"sent": True, "message": "Email sent to someone@example.com."}
    assert fake.calls[0]["Source"] == "sender@example.com"
    assert fake.calls[0]["Destination"] == {"ToAddresses": ["someone@example.com"]}
    assert fake.calls[0]["Message"]["Subject"]["Data"] == "Subject"
    assert fake.calls[0]["Message"]["Body"]["Text"]["Data"] == "Body text"


def test_send_email_reports_a_real_ses_failure_as_data_not_an_exception(monkeypatch):
    fake = _FakeSesClient(should_fail=True)
    monkeypatch.setattr(ses_client.boto3, "client", lambda service, region_name=None: fake)
    monkeypatch.setattr(ses_client, "read_setting", lambda value, name, default=None: "sender@example.com" if name == "SES_SENDER_EMAIL" else default)

    result = ses_client.send_email("someone@example.com", "Subject", "Body")

    assert result["sent"] is False
    assert "not verified" in result["message"]


def test_send_email_without_a_configured_sender_fails_gracefully(monkeypatch):
    monkeypatch.setattr(ses_client, "read_setting", lambda value, name, default=None: default)

    result = ses_client.send_email("someone@example.com", "Subject", "Body")

    assert result == {"sent": False, "message": "SES_SENDER_EMAIL is not configured."}
