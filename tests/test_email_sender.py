import smtplib
import ssl
from unittest.mock import MagicMock, patch

import pytest

from email_sender import send_epub


def call_send(epub_bytes=b'epub', filename='digest-2026-04-30.epub',
              gmail_user='u@gmail.com', password='pass', kindle='k@kindle.com'):
    send_epub(epub_bytes, filename, gmail_user, password, kindle)


def mock_smtp():
    m = MagicMock()
    m.__enter__ = MagicMock(return_value=m)
    m.__exit__ = MagicMock(return_value=False)
    return m


def test_send_epub_connects_to_gmail_smtp():
    smtp = mock_smtp()
    with patch('email_sender.smtplib.SMTP', return_value=smtp) as mock_cls:
        call_send()
    mock_cls.assert_called_once_with('smtp.gmail.com', 587, timeout=30)


def test_send_epub_uses_starttls():
    smtp = mock_smtp()
    with patch('email_sender.smtplib.SMTP', return_value=smtp):
        call_send()
    smtp.starttls.assert_called_once()


def test_send_epub_authenticates_with_credentials():
    smtp = mock_smtp()
    with patch('email_sender.smtplib.SMTP', return_value=smtp):
        call_send(gmail_user='user@gmail.com', password='apppass')
    smtp.login.assert_called_once_with('user@gmail.com', 'apppass')


def test_send_epub_sends_to_kindle_address():
    smtp = mock_smtp()
    with patch('email_sender.smtplib.SMTP', return_value=smtp):
        call_send(gmail_user='user@gmail.com', kindle='kindle@kindle.com')
    args = smtp.sendmail.call_args[0]
    assert args[0] == 'user@gmail.com'
    assert args[1] == 'kindle@kindle.com'


def test_send_epub_uses_verified_tls_context():
    smtp = mock_smtp()
    with patch('email_sender.smtplib.SMTP', return_value=smtp):
        call_send()
    ctx = smtp.starttls.call_args.kwargs['context']
    assert isinstance(ctx, ssl.SSLContext)
    assert ctx.verify_mode == ssl.CERT_REQUIRED
    assert ctx.check_hostname is True


def test_send_epub_sets_connection_timeout():
    smtp = mock_smtp()
    with patch('email_sender.smtplib.SMTP', return_value=smtp) as mock_cls:
        call_send()
    assert mock_cls.call_args.kwargs['timeout'] == 30


def test_send_epub_raises_on_auth_failure():
    smtp = mock_smtp()
    smtp.login.side_effect = smtplib.SMTPAuthenticationError(535, b'Bad credentials')
    with patch('email_sender.smtplib.SMTP', return_value=smtp):
        with pytest.raises(smtplib.SMTPAuthenticationError):
            call_send()
