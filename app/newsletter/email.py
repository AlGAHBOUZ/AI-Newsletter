import logging
import smtplib
import ssl
from datetime import datetime, timezone
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

logger = logging.getLogger(__name__)

SMTP_HOST = "smtp.gmail.com"
SMTP_PORT = 465  # SSL — more reliable than 587/STARTTLS for App Passwords


class EmailError(Exception):
    """Raised when delivery fails after the SMTP connection is established."""


def _build_plain_text(html: str) -> str:
    """
    Minimal plain-text fallback stripped from the HTML. Not a full HTML→text
    converter — just removes tags and collapses whitespace to produce something
    readable in text-only clients, which is good enough for a fallback.
    """
    import re
    # Keep newlines around block-level elements before stripping tags
    text = re.sub(r"<(h[1-6]|p|li|div|section|br)[^>]*>", "\n", html, flags=re.IGNORECASE)
    text = re.sub(r"<[^>]+>", "", text)          # strip remaining tags
    text = re.sub(r"[ \t]+", " ", text)           # collapse spaces
    text = re.sub(r"\n{3,}", "\n\n", text)        # collapse blank lines
    return text.strip()


def send(
    html: str,
    subject: str,
    from_address: str,
    app_password: str,
    to_address: str,
) -> None:
    """
    Send the newsletter HTML via Gmail SMTP.

    Raises EmailError on delivery failure so the caller can log it without
    crashing the rest of the pipeline (the newsletter.html was already saved
    to disk, so a delivery failure doesn't lose the content).
    """
    if not from_address or not app_password or not to_address:
        raise EmailError(
            "Gmail delivery is not configured. Set GMAIL_ADDRESS, "
            "GMAIL_APP_PASSWORD, and DIGEST_RECIPIENT in your .env file."
        )

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"]    = f"AI Weekly Digest <{from_address}>"
    msg["To"]      = to_address

    # Attach plain-text first, HTML second — email clients prefer the last part
    # they can render, so HTML-capable clients will use the HTML version.
    msg.attach(MIMEText(_build_plain_text(html), "plain", "utf-8"))
    msg.attach(MIMEText(html, "html", "utf-8"))

    context = ssl.create_default_context()
    try:
        with smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT, context=context) as server:
            server.login(from_address, app_password)
            server.sendmail(from_address, to_address, msg.as_string())
    except smtplib.SMTPAuthenticationError:
        raise EmailError(
            "Gmail authentication failed. Make sure GMAIL_APP_PASSWORD is a valid "
            "16-character App Password (not your regular Gmail password). "
            "Generate one at: myaccount.google.com → Security → App passwords"
        )
    except smtplib.SMTPException as exc:
        raise EmailError(f"SMTP error during delivery: {exc}")

    logger.info("Newsletter delivered to %s", to_address)


def build_subject(issue_date: datetime | None = None) -> str:
    if issue_date is None:
        issue_date = datetime.now(tz=timezone.utc)
    date_str = issue_date.strftime("%B %d, %Y").replace(" 0", " ")
    return f"AI Weekly Digest — {date_str}"