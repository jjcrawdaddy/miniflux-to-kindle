import smtplib
from email import encoders
from email.mime.base import MIMEBase
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText


def send_epub(
    epub_bytes: bytes,
    filename: str,
    gmail_user: str,
    gmail_app_password: str,
    kindle_email: str,
) -> None:
    pass
