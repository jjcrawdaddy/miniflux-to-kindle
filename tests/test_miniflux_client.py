from unittest.mock import MagicMock

from miniflux_client import MinifluxClient


def make_client():
    return MinifluxClient('http://localhost:8080', 'test-key')


def test_get_unread_entries_returns_entries():
    client = make_client()
    mock_resp = MagicMock()
    mock_resp.json.return_value = {
        'total': 2,
        'entries': [
            {'id': 1, 'title': 'A1', 'url': 'http://ex.com/1', 'content': '<p>One</p>',
             'published_at': '2026-04-30T08:00:00+00:00'},
            {'id': 2, 'title': 'A2', 'url': 'http://ex.com/2', 'content': '<p>Two</p>',
             'published_at': '2026-04-30T09:00:00+00:00'},
        ]
    }
    client.session.get = MagicMock(return_value=mock_resp)

    entries = client.get_unread_entries(55)

    client.session.get.assert_called_once_with(
        'http://localhost:8080/v1/feeds/55/entries',
        params={'status': 'unread', 'limit': 100},
        timeout=30,
    )
    assert len(entries) == 2
    assert entries[0]['id'] == 1
    mock_resp.raise_for_status.assert_called_once()


def test_get_unread_entries_returns_empty_list_when_none():
    client = make_client()
    mock_resp = MagicMock()
    mock_resp.json.return_value = {'total': 0, 'entries': []}
    client.session.get = MagicMock(return_value=mock_resp)

    assert client.get_unread_entries(55) == []


def test_get_unread_entries_strips_trailing_slash():
    client = MinifluxClient('http://localhost:8080/', 'test-key')
    mock_resp = MagicMock()
    mock_resp.json.return_value = {'total': 0, 'entries': []}
    client.session.get = MagicMock(return_value=mock_resp)

    client.get_unread_entries(55)

    args, _ = client.session.get.call_args
    assert args[0] == 'http://localhost:8080/v1/feeds/55/entries'


def test_mark_entries_read_sends_correct_request():
    client = make_client()
    mock_resp = MagicMock()
    client.session.put = MagicMock(return_value=mock_resp)

    client.mark_entries_read([1, 2, 3])

    client.session.put.assert_called_once_with(
        'http://localhost:8080/v1/entries',
        json={'entry_ids': [1, 2, 3], 'status': 'read'},
        timeout=30,
    )
    mock_resp.raise_for_status.assert_called_once()


def test_mark_entries_read_skips_when_empty():
    client = make_client()
    client.session.put = MagicMock()

    client.mark_entries_read([])

    client.session.put.assert_not_called()


def test_refresh_feed_sends_correct_request():
    client = make_client()
    mock_resp = MagicMock()
    client.session.put = MagicMock(return_value=mock_resp)

    client.refresh_feed(55)

    client.session.put.assert_called_once_with(
        'http://localhost:8080/v1/feeds/55/refresh',
        timeout=30,
    )
    mock_resp.raise_for_status.assert_called_once()


def test_all_requests_include_timeout():
    client = make_client()
    mock_resp = MagicMock()
    mock_resp.json.return_value = {'total': 0, 'entries': []}
    client.session.get = MagicMock(return_value=mock_resp)
    client.session.put = MagicMock(return_value=MagicMock())

    client.get_unread_entries(55)
    client.mark_entries_read([1])
    client.refresh_feed(55)

    assert client.session.get.call_args.kwargs['timeout'] == 30
    for call in client.session.put.call_args_list:
        assert call.kwargs['timeout'] == 30


def test_client_exposes_hostname():
    client = MinifluxClient('http://192.168.1.10:8080/', 'key')
    assert client.hostname == '192.168.1.10'
