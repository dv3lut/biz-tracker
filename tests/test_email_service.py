from __future__ import annotations

from types import SimpleNamespace

from app.services import email_service


def _settings(**overrides):
    defaults = dict(
        enabled=True,
        provider="smtp",
        smtp_host="smtp.test",
        smtp_port=25,
        smtp_username=None,
        smtp_password=None,
        use_tls=False,
        from_address="noreply@example.com",
    )
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


def test_email_service_detects_configuration(monkeypatch):
    monkeypatch.setattr(email_service, "get_settings", lambda: SimpleNamespace(email=_settings(enabled=False)))
    service = email_service.EmailService()
    assert not service.is_enabled()
    assert not service.is_configured()

    monkeypatch.setattr(email_service, "get_settings", lambda: SimpleNamespace(email=_settings()))
    service = email_service.EmailService()
    assert service.is_enabled()
    assert service.is_configured()


def test_email_service_send_skips_when_before_ready(monkeypatch):
    monkeypatch.setattr(email_service, "get_settings", lambda: SimpleNamespace(email=_settings(enabled=False)))
    service = email_service.EmailService()
    service.send("subject", "body", ["ops@example.com"])

    monkeypatch.setattr(email_service, "get_settings", lambda: SimpleNamespace(email=_settings(smtp_host=None)))
    service = email_service.EmailService()
    service.send("subject", "body", ["ops@example.com"])

    monkeypatch.setattr(email_service, "get_settings", lambda: SimpleNamespace(email=_settings()))
    service = email_service.EmailService()
    service.send("subject", "body", [])


def test_email_service_send_uses_smtp(monkeypatch):
    sent_messages: list[tuple[str, list[str]]] = []
    sent_reply_to: list[str | None] = []
    sent_attachments: list[list[tuple[str, str]]] = []

    class DummySMTP:
        def __init__(self, host, port) -> None:
            self.host = host
            self.port = port

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def starttls(self):
            pass

        def login(self, username, password):
            assert username == "user"
            assert password == "pass"

        def send_message(self, message, to_addrs):
            sent_messages.append((message["Subject"], to_addrs))
            sent_reply_to.append(message.get("Reply-To"))
            attachments: list[tuple[str, str]] = []
            for part in message.iter_attachments():
                attachments.append((part.get_filename(), part.get_content_type()))
            sent_attachments.append(attachments)

    monkeypatch.setattr(email_service, "get_settings", lambda: SimpleNamespace(email=_settings(use_tls=True, smtp_username="user", smtp_password="pass")))
    monkeypatch.setattr(email_service.smtplib, "SMTP", DummySMTP)

    service = email_service.EmailService()
    service.send(
        "Hello",
        "Body",
        ["ops@example.com", None],
        html_body="<p>Body</p>",
        reply_to="contact@business-tracker.fr",
        attachments=[("alertes.csv", b"col1;col2\n", "text/csv")],
    )

    assert sent_messages == [("Hello", ["ops@example.com"])]
    assert sent_reply_to == ["contact@business-tracker.fr"]
    assert sent_attachments == [[("alertes.csv", "text/csv")]]
