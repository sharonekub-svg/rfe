"""Send the daily summary email over SMTP."""
from __future__ import annotations

import smtplib
from email.message import EmailMessage

from .config import Settings, settings


def send_email(subject: str, body: str, cfg: Settings | None = None) -> None:
    cfg = cfg or settings
    cfg.require_email()

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = cfg.email_from or cfg.smtp_username
    msg["To"] = cfg.email_to
    msg.set_content(body)

    with smtplib.SMTP(cfg.smtp_host, cfg.smtp_port, timeout=30) as server:
        server.ehlo()
        if cfg.smtp_port in (587, 25):
            server.starttls()
            server.ehlo()
        server.login(cfg.smtp_username, cfg.smtp_password)
        server.send_message(msg)
