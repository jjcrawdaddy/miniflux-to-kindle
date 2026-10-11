import logging
import os
import smtplib
import ssl
import time
from email import encoders
from email.mime.base import MIMEBase
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from config import SmtpConfig

logger = logging.getLogger(__name__)

# The greeting + TLS handshake + login should complete quickly; a wrong
# SMTP_SECURITY (e.g. STARTTLS against an implicit-TLS port) blocks here
# waiting for a banner, so keep this short to surface the failure in the logs
# promptly instead of hanging for minutes.
CONNECT_TIMEOUT = 30

# Large attachments can take minutes to upload + scan before the final 250,
# so the data-transfer timeout must be generous (applied after login).
RETRY_DELAYS = (60, 300)


def _connect(smtp: SmtpConfig) -> smtplib.SMTP:
    if smtp.security == 'ssl':
        return smtplib.SMTP_SSL(smtp.host, smtp.port, timeout=CONNECT_TIMEOUT)
    conn = smtplib.SMTP(smtp.host, smtp.port, timeout=CONNECT_TIMEOUT)
    if smtp.security == 'starttls':
        conn.starttls(context=ssl.create_default_context())
    return conn


def _send_once(msg_string: str, smtp: SmtpConfig, kindle_email: str) -> None:
    logger.info("Connecting to SMTP %s:%d (%s)", smtp.host, smtp.port, smtp.security)
    with _connect(smtp) as conn:
        if smtp.user or smtp.password:
            conn.login(smtp.user, smtp.password)
        # Greeting and login are done under the short timeout; the attachment
        # upload itself needs the generous one.
        conn.timeout = smtp.timeout
        conn.sendmail(smtp.from_address, kindle_email, msg_string)


def _build_message(
    epub_bytes: bytes,
    filename: str,
    smtp: SmtpConfig,
    kindle_email: str,
    mime_type: str,
) -> str:
    maintype, subtype = mime_type.split('/', 1)
    msg = MIMEMultipart()
    msg['From'] = smtp.from_address
    msg['To'] = kindle_email
    msg['Subject'] = os.path.splitext(filename)[0]

    msg.attach(MIMEText('Daily digest attached.', 'plain'))

    attachment = MIMEBase(maintype, subtype)
    attachment.set_payload(epub_bytes)
    encoders.encode_base64(attachment)
    attachment.add_header('Content-Disposition', 'attachment', filename=filename)
    msg.attach(attachment)

    return msg.as_string()


def _is_attachment_rejected(exc: Exception) -> bool:
    # Some relays (e.g. Scaleway TEM) reject unknown attachment MIME types with
    # a 501 after DATA. That's a signal to try the next configured type.
    return getattr(exc, 'smtp_code', None) == 501


def _send_with_retries(msg_string: str, smtp: SmtpConfig, kindle_email: str) -> None:
    for attempt, delay in enumerate((*RETRY_DELAYS, None), start=1):
        try:
            _send_once(msg_string, smtp, kindle_email)
            return
        except smtplib.SMTPAuthenticationError:
            raise
        except smtplib.SMTPDataError:
            # Permanent rejection of the message content — retrying the same
            # bytes won't help; let the caller try a different MIME type.
            raise
        except (smtplib.SMTPException, OSError) as exc:
            if delay is None:
                raise
            logger.warning(
                "Send attempt %d failed (%s), retrying in %ds", attempt, exc, delay
            )
            time.sleep(delay)


def send_epub(
    epub_bytes: bytes,
    filename: str,
    smtp: SmtpConfig,
    kindle_email: str,
) -> None:
    last_error = None
    for index, mime_type in enumerate(smtp.attachment_mime):
        msg_string = _build_message(epub_bytes, filename, smtp, kindle_email, mime_type)
        try:
            _send_with_retries(msg_string, smtp, kindle_email)
            return
        except smtplib.SMTPAuthenticationError:
            raise
        except smtplib.SMTPDataError as exc:
            last_error = exc
            if _is_attachment_rejected(exc) and index < len(smtp.attachment_mime) - 1:
                logger.warning(
                    "Attachment MIME type %r rejected (%s), trying next configured type",
                    mime_type, exc,
                )
                continue
            raise
    raise last_error
