import os
import smtplib
import ssl
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

    with smtplib.SMTP('smtp.gmail.com', 587, timeout=30) as smtp:
        smtp.ehlo()
        smtp.starttls(context=ssl.create_default_context())
        smtp.login(gmail_user, gmail_app_password)
        smtp.sendmail(gmail_user, kindle_email, msg.as_string())
