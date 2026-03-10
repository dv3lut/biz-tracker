"""SMTP email delivery."""
from __future__ import annotations

import logging
import smtplib
from email.message import EmailMessage
from typing import Iterable, Sequence

from app.config import EmailSettings, get_settings

_LOGGER = logging.getLogger(__name__)


class EmailService:
    """Send email alerts if SMTP is configured."""

    def __init__(self) -> None:
        self._settings: EmailSettings | None = None

    @property
    def settings(self) -> EmailSettings:
        if self._settings is None:
            try:
                self._settings = get_settings().email
            except Exception as exc:  # pragma: no cover - defensive fallback
                _LOGGER.debug("Falling back to disabled email settings: %s", exc)
                self._settings = EmailSettings()
        return self._settings

    @property
    def provider(self) -> str:
        return self.settings.provider

    def is_enabled(self) -> bool:
        return bool(self.settings.enabled)

    def is_configured(self) -> bool:
        settings = self.settings
        return bool(
            settings.enabled
            and settings.smtp_host
            and settings.from_address
        )

    def send(
        self,
        subject: str,
        body: str,
        recipients: Iterable[str],
        *,
        html_body: str | None = None,
        reply_to: str | None = None,
        attachments: Sequence[tuple[str, bytes, str]] | None = None,
    ) -> None:
        settings = self.settings
        recipient_list = [addr for addr in recipients if addr]
        if not settings.enabled:
            _LOGGER.info("Email service disabled; skipping send (subject=%r)", subject)
            return
        if not settings.smtp_host or not settings.from_address:
            _LOGGER.warning(
                "Email service misconfigured; host or from address missing (subject=%r)",
                subject,
            )
            return
        if not recipient_list:
            _LOGGER.info("No recipients supplied; nothing to send (subject=%r)", subject)
            return

        _LOGGER.info(
            "Sending email via %s to %s (subject=%r)",
            settings.provider,
            recipient_list,
            subject,
        )
        timeout_seconds = getattr(settings, "smtp_timeout_seconds", 10)
        try:
            server_context = smtplib.SMTP(
                settings.smtp_host,
                settings.smtp_port,
                timeout=timeout_seconds,
            )
        except TypeError:
            server_context = smtplib.SMTP(
                settings.smtp_host,
                settings.smtp_port,
            )
        with server_context as server:
            if settings.use_tls:
                server.starttls()
            if settings.smtp_username and settings.smtp_password:
                server.login(settings.smtp_username, settings.smtp_password)
            message = EmailMessage()
            message["Subject"] = subject
            message["From"] = settings.from_address
            message["To"] = ", ".join(recipient_list)
            if reply_to:
                message["Reply-To"] = reply_to
            message.set_content(body)
            if html_body:
                message.add_alternative(html_body, subtype="html")

            for filename, content, mime_type in attachments or []:
                maintype, _sep, subtype = (mime_type or "application/octet-stream").partition("/")
                message.add_attachment(content, maintype=maintype, subtype=subtype or "octet-stream", filename=filename)
            server.send_message(message, to_addrs=recipient_list)
            _LOGGER.debug(
                "Email sent via %s to %s (subject=%r)",
                settings.provider,
                recipient_list,
                subject,
            )
