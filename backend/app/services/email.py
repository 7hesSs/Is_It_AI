"""
Minimal email sending via Gmail SMTP - stdlib smtplib, no new dependency.

Reads GMAIL_ADDRESS and GMAIL_APP_PASSWORD from environment variables.
If either is missing, logs the message to the console instead of sending -
keeps the password-reset flow fully testable locally without setting up
real email, and means forgot-password won't hard-crash if you deploy
without configuring this.

GMAIL_APP_PASSWORD must be a Gmail "app password", not your normal Gmail
password:
  Google Account -> Security -> 2-Step Verification (must be enabled first)
  -> App passwords -> generate one for "Mail"
Gmail blocks regular password SMTP login entirely, so this step is required,
not optional.
"""
import os
import smtplib
import logging
from email.mime.text import MIMEText

logger = logging.getLogger("ai_detector")

GMAIL_ADDRESS = os.environ.get("GMAIL_ADDRESS")
GMAIL_APP_PASSWORD = os.environ.get("GMAIL_APP_PASSWORD")


def send_email(to_address: str, subject: str, body: str) -> None:
    if not GMAIL_ADDRESS or not GMAIL_APP_PASSWORD:
        logger.warning(
            "Email not configured (set GMAIL_ADDRESS/GMAIL_APP_PASSWORD env vars). "
            "Would have sent to %s:\nSubject: %s\n%s",
            to_address,
            subject,
            body,
        )
        return

    msg = MIMEText(body)
    msg["Subject"] = subject
    msg["From"] = GMAIL_ADDRESS
    msg["To"] = to_address

    with smtplib.SMTP("smtp.gmail.com", 587) as server:
        server.starttls()
        server.login(GMAIL_ADDRESS, GMAIL_APP_PASSWORD)
        server.sendmail(GMAIL_ADDRESS, [to_address], msg.as_string())
