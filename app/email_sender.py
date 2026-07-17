import logging
import os
import smtplib
import ssl
import time
from email import encoders
from email.mime.base import MIMEBase
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

logger = logging.getLogger(__name__)

# Gmail can take minutes to accept a large attachment (upload + virus scan
# before the final 250), so the timeout must be generous
SMTP_TIMEOUT = 300
RETRY_DELAYS = (60, 300)


def _send(msg_string: str, gmail_user: str, gmail_app_password: str, kindle_email: str) -> None:
    with smtplib.SMTP('smtp.gmail.com', 587, timeout=SMTP_TIMEOUT) as smtp:
        smtp.ehlo()
        smtp.starttls(context=ssl.create_default_context())
        smtp.login(gmail_user, gmail_app_password)
        smtp.sendmail(gmail_user, kindle_email, msg_string)


def send_epub(
    epub_bytes: bytes,
    filename: str,
    gmail_user: str,
    gmail_app_password: str,
    kindle_email: str,
) -> None:
    msg = MIMEMultipart()
    msg['From'] = gmail_user
    msg['To'] = kindle_email
    msg['Subject'] = os.path.splitext(filename)[0]

    msg.attach(MIMEText('Daily digest attached.', 'plain'))

    attachment = MIMEBase('application', 'epub+zip')
    attachment.set_payload(epub_bytes)
    encoders.encode_base64(attachment)
    attachment.add_header('Content-Disposition', 'attachment', filename=filename)
    msg.attach(attachment)

    msg_string = msg.as_string()
    for attempt, delay in enumerate((*RETRY_DELAYS, None), start=1):
        try:
            _send(msg_string, gmail_user, gmail_app_password, kindle_email)
            return
        except smtplib.SMTPAuthenticationError:
            raise
        except (smtplib.SMTPException, OSError) as exc:
            if delay is None:
                raise
            logger.warning(
                "Send attempt %d failed (%s), retrying in %ds", attempt, exc, delay
            )
            time.sleep(delay)
