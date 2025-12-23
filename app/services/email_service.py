"""SMTP email delivery."""
from __future__ import annotations

import logging
import smtplib
from email.message import EmailMessage
from typing import Iterable

from app.config import get_settings

_LOGGER = logging.getLogger(__name__)


class EmailService:
    """Send email alerts if SMTP is configured."""

    def __init__(self) -> None:
        self._settings = get_settings().email

    @property
    def provider(self) -> str:
        return self._settings.provider

    def is_enabled(self) -> bool:
        return bool(self._settings.enabled)

    def is_configured(self) -> bool:
        return bool(
            self._settings.enabled
            and self._settings.smtp_host
            and self._settings.from_address
        )

    def send(
        self,
        subject: str,
        body: str,
        recipients: Iterable[str],
        *,
        html_body: str | None = None,
        reply_to: str | None = None,
    ) -> None:
        settings = self._settings
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
        with smtplib.SMTP(settings.smtp_host, settings.smtp_port) as server:
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
            server.send_message(message, to_addrs=recipient_list)
            _LOGGER.debug(
                "Email sent via %s to %s (subject=%r)",
                settings.provider,
                recipient_list,
                subject,
            )
