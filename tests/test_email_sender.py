import logging
import smtplib
import ssl
from unittest.mock import MagicMock, patch

import pytest

from config import SmtpConfig
from email_sender import CONNECT_TIMEOUT, send_epub


def make_smtp(host='smtp.gmail.com', port=587, user='u@gmail.com', password='pass',
              from_address=None, security='starttls', timeout=300,
              attachment_mime=('application/epub+zip',)):
    return SmtpConfig(
        host=host, port=port, user=user, password=password,
        from_address=from_address or user, security=security, timeout=timeout,
        attachment_mime=attachment_mime,
    )


def call_send(smtp=None, epub_bytes=b'epub', filename='digest-2026-04-30.epub',
              kindle='k@kindle.com'):
    send_epub(epub_bytes, filename, smtp or make_smtp(), kindle)


def mock_smtp():
    m = MagicMock()
    m.__enter__ = MagicMock(return_value=m)
    m.__exit__ = MagicMock(return_value=False)
    return m


def test_send_epub_connects_to_configured_host():
    smtp = mock_smtp()
    with patch('email_sender.smtplib.SMTP', return_value=smtp) as mock_cls:
        call_send(smtp=make_smtp(host='smtp.fastmail.com', port=2525, timeout=120))
    mock_cls.assert_called_once_with('smtp.fastmail.com', 2525, timeout=CONNECT_TIMEOUT)


def test_send_epub_uses_starttls_by_default():
    smtp = mock_smtp()
    with patch('email_sender.smtplib.SMTP', return_value=smtp):
        call_send()
    smtp.starttls.assert_called_once()


def test_send_epub_authenticates_with_credentials():
    smtp = mock_smtp()
    with patch('email_sender.smtplib.SMTP', return_value=smtp):
        call_send(smtp=make_smtp(user='user@gmail.com', password='apppass'))
    smtp.login.assert_called_once_with('user@gmail.com', 'apppass')


def test_send_epub_sends_to_kindle_address():
    smtp = mock_smtp()
    with patch('email_sender.smtplib.SMTP', return_value=smtp):
        call_send(smtp=make_smtp(user='user@gmail.com'), kindle='kindle@kindle.com')
    args = smtp.sendmail.call_args[0]
    assert args[0] == 'user@gmail.com'
    assert args[1] == 'kindle@kindle.com'


def test_send_epub_uses_from_address_for_envelope_sender():
    smtp = mock_smtp()
    with patch('email_sender.smtplib.SMTP', return_value=smtp):
        call_send(smtp=make_smtp(user='user@gmail.com', from_address='digest@example.com'))
    assert smtp.sendmail.call_args[0][0] == 'digest@example.com'


def test_send_epub_uses_default_epub_mime_type():
    smtp = mock_smtp()
    with patch('email_sender.smtplib.SMTP', return_value=smtp):
        call_send()
    msg_string = smtp.sendmail.call_args[0][2]
    assert 'Content-Type: application/epub+zip' in msg_string


def test_send_epub_falls_back_to_next_mime_type_on_501():
    smtp = mock_smtp()
    smtp.sendmail.side_effect = [
        smtplib.SMTPDataError(501, b"application/epub+zip is not allowed"),
        None,
    ]
    with patch('email_sender.smtplib.SMTP', return_value=smtp), \
         patch('email_sender.time.sleep'):
        call_send(smtp=make_smtp(attachment_mime=('application/epub+zip', 'application/xml')))
    assert smtp.sendmail.call_count == 2
    assert 'Content-Type: application/xml' in smtp.sendmail.call_args_list[1][0][2]


def test_send_epub_does_not_fallback_on_other_data_error():
    smtp = mock_smtp()
    smtp.sendmail.side_effect = smtplib.SMTPDataError(554, b'rejected for another reason')
    with patch('email_sender.smtplib.SMTP', return_value=smtp), \
         patch('email_sender.time.sleep'):
        with pytest.raises(smtplib.SMTPDataError):
            call_send(smtp=make_smtp(attachment_mime=('application/epub+zip', 'application/xml')))
    assert smtp.sendmail.call_count == 1


def test_send_epub_raises_when_all_mime_types_rejected():
    smtp = mock_smtp()
    smtp.sendmail.side_effect = smtplib.SMTPDataError(501, b'not allowed')
    with patch('email_sender.smtplib.SMTP', return_value=smtp), \
         patch('email_sender.time.sleep'):
        with pytest.raises(smtplib.SMTPDataError):
            call_send(smtp=make_smtp(attachment_mime=('application/epub+zip', 'application/xml')))
    assert smtp.sendmail.call_count == 2


def test_send_epub_uses_verified_tls_context():
    smtp = mock_smtp()
    with patch('email_sender.smtplib.SMTP', return_value=smtp):
        call_send()
    ctx = smtp.starttls.call_args.kwargs['context']
    assert isinstance(ctx, ssl.SSLContext)
    assert ctx.verify_mode == ssl.CERT_REQUIRED
    assert ctx.check_hostname is True


def test_send_epub_uses_short_connect_timeout_and_long_send_timeout():
    # A 30s timeout failed on a 9.1 MB digest (2026-07-17), so the attachment
    # upload needs a generous timeout — but the connect/greeting phase must be
    # short so a wrong SMTP_SECURITY surfaces in the logs quickly.
    smtp = mock_smtp()
    with patch('email_sender.smtplib.SMTP', return_value=smtp) as mock_cls:
        call_send(smtp=make_smtp(timeout=300))
    assert mock_cls.call_args.kwargs['timeout'] == CONNECT_TIMEOUT
    assert CONNECT_TIMEOUT < 300
    assert smtp.timeout == 300


def test_send_epub_uses_ssl_for_implicit_tls():
    smtp = mock_smtp()
    with patch('email_sender.smtplib.SMTP_SSL', return_value=smtp) as mock_cls:
        call_send(smtp=make_smtp(port=465, security='ssl'))
    mock_cls.assert_called_once_with('smtp.gmail.com', 465, timeout=CONNECT_TIMEOUT)
    smtp.starttls.assert_not_called()


def test_send_epub_skips_starttls_for_none_security():
    smtp = mock_smtp()
    with patch('email_sender.smtplib.SMTP', return_value=smtp):
        call_send(smtp=make_smtp(security='none'))
    smtp.starttls.assert_not_called()


def test_send_epub_skips_login_when_no_credentials():
    smtp = mock_smtp()
    with patch('email_sender.smtplib.SMTP', return_value=smtp):
        call_send(smtp=make_smtp(user='', password=''))
    smtp.login.assert_not_called()


def test_send_epub_raises_on_auth_failure():
    smtp = mock_smtp()
    smtp.login.side_effect = smtplib.SMTPAuthenticationError(535, b'Bad credentials')
    with patch('email_sender.smtplib.SMTP', return_value=smtp):
        with pytest.raises(smtplib.SMTPAuthenticationError):
            call_send()


def test_send_epub_retries_on_transient_failure():
    smtp = mock_smtp()
    smtp.sendmail.side_effect = [
        smtplib.SMTPServerDisconnected('Connection unexpectedly closed: timed out'),
        None,
    ]
    with patch('email_sender.smtplib.SMTP', return_value=smtp), \
         patch('email_sender.time.sleep'):
        call_send()
    assert smtp.sendmail.call_count == 2


def test_send_epub_logs_connection_attempt_and_failure(caplog):
    # A wrong SMTP_SECURITY (e.g. STARTTLS against an implicit-TLS port) makes
    # the greeting read time out — model that as a TimeoutError from the SMTP
    # constructor and confirm it is logged, not silently swallowed.
    caplog.set_level(logging.INFO, logger='email_sender')
    with patch('email_sender.smtplib.SMTP', side_effect=TimeoutError('timed out')), \
         patch('email_sender.time.sleep'):
        with pytest.raises(TimeoutError):
            call_send()
    messages = [r.getMessage() for r in caplog.records]
    assert any('Connecting to SMTP smtp.gmail.com:587 (starttls)' in m for m in messages)
    assert any('Send attempt' in m for m in messages)


def test_send_epub_gives_up_after_all_attempts():
    smtp = mock_smtp()
    smtp.sendmail.side_effect = smtplib.SMTPServerDisconnected('timed out')
    with patch('email_sender.smtplib.SMTP', return_value=smtp), \
         patch('email_sender.time.sleep'):
        with pytest.raises(smtplib.SMTPServerDisconnected):
            call_send()
    assert smtp.sendmail.call_count == 3


def test_send_epub_waits_between_retries():
    smtp = mock_smtp()
    smtp.sendmail.side_effect = smtplib.SMTPServerDisconnected('timed out')
    with patch('email_sender.smtplib.SMTP', return_value=smtp), \
         patch('email_sender.time.sleep') as mock_sleep:
        with pytest.raises(smtplib.SMTPServerDisconnected):
            call_send()
    assert [c.args[0] for c in mock_sleep.call_args_list] == [60, 300]


def test_send_epub_does_not_retry_auth_failure():
    # Retrying bad credentials only hammers the server and risks a lockout
    smtp = mock_smtp()
    smtp.login.side_effect = smtplib.SMTPAuthenticationError(535, b'Bad credentials')
    with patch('email_sender.smtplib.SMTP', return_value=smtp), \
         patch('email_sender.time.sleep') as mock_sleep:
        with pytest.raises(smtplib.SMTPAuthenticationError):
            call_send()
    assert smtp.login.call_count == 1
    mock_sleep.assert_not_called()
