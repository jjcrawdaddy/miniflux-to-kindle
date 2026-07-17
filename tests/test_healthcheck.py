from unittest.mock import patch

from healthcheck import ping


def test_ping_posts_to_url():
    with patch('healthcheck.requests.post') as mock_post:
        ping('https://hc-ping.com/uuid')
    assert mock_post.call_args.args[0] == 'https://hc-ping.com/uuid'


def test_ping_appends_endpoint():
    with patch('healthcheck.requests.post') as mock_post:
        ping('https://hc-ping.com/uuid', '/start')
    assert mock_post.call_args.args[0] == 'https://hc-ping.com/uuid/start'


def test_ping_sends_message_as_body():
    with patch('healthcheck.requests.post') as mock_post:
        ping('https://hc-ping.com/uuid', '/fail', 'Email send failed: timed out')
    assert mock_post.call_args.kwargs['data'] == 'Email send failed: timed out'


def test_ping_sets_timeout():
    with patch('healthcheck.requests.post') as mock_post:
        ping('https://hc-ping.com/uuid')
    assert mock_post.call_args.kwargs['timeout'] == 10


def test_ping_noop_when_url_unset():
    with patch('healthcheck.requests.post') as mock_post:
        ping(None)
        ping('')
    mock_post.assert_not_called()


def test_ping_swallows_request_errors():
    # Monitoring must never break the job it monitors
    with patch('healthcheck.requests.post', side_effect=Exception('DNS failure')):
        ping('https://hc-ping.com/uuid')
