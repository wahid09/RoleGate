import logging
import smtplib
from email.message import EmailMessage

from .config import settings

log = logging.getLogger(__name__)


def send_email(to: str, subject: str, body: str) -> None:
    msg = EmailMessage()
    msg["From"] = settings.SMTP_FROM
    msg["To"] = to
    msg["Subject"] = subject
    msg.set_content(body)
    try:
        with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=10) as smtp:
            if settings.SMTP_USER:
                smtp.starttls()
                smtp.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
            smtp.send_message(msg)
    except Exception:
        log.exception("Failed to send email to %s", to)