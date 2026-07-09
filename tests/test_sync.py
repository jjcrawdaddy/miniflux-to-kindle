from unittest.mock import MagicMock, patch

from sync import run_sync, refresh_feeds


def make_entries(id_offset=0):
    return [{
        'id': 1 + id_offset,
        'title': f'Article {1 + id_offset}',
        'url': f'http://ex.com/{1 + id_offset}',
        'content': '<p>Content</p>',
        'published_at': '2026-04-30T08:00:00+00:00',
    }]


def test_run_sync_fetches_all_feeds():
    c1, c2 = MagicMock(), MagicMock()
    c1.get_unread_entries.return_value = make_entries(0)
    c2.get_unread_entries.return_value = make_entries(10)

    with patch('sync.build_epub', return_value=b'epub'), patch('sync.send_epub'):
        run_sync([c1, c2], 'u@gmail.com', 'pass', 'k@kindle.com')

    c1.get_unread_entries.assert_called_once()
    c2.get_unread_entries.assert_called_once()


def test_run_sync_skips_when_no_entries():
    client = MagicMock()
    client.get_unread_entries.return_value = []

    with patch('sync.build_epub') as mock_epub, patch('sync.send_epub') as mock_send:
        run_sync([client], 'u@gmail.com', 'pass', 'k@kindle.com')

    mock_epub.assert_not_called()
    mock_send.assert_not_called()
    client.mark_entries_read.assert_not_called()


def test_run_sync_marks_all_entries_read_after_send():
    c1, c2 = MagicMock(), MagicMock()
    c1.get_unread_entries.return_value = make_entries(0)
    c2.get_unread_entries.return_value = make_entries(10)

    with patch('sync.build_epub', return_value=b'epub'), patch('sync.send_epub'):
        run_sync([c1, c2], 'u@gmail.com', 'pass', 'k@kindle.com')

    c1.mark_entries_read.assert_called_once_with([1, 11])


def test_run_sync_does_not_mark_read_on_email_failure():
    client = MagicMock()
    client.get_unread_entries.return_value = make_entries()

    with patch('sync.build_epub', return_value=b'epub'), \
         patch('sync.send_epub', side_effect=Exception('SMTP error')):
        run_sync([client], 'u@gmail.com', 'pass', 'k@kindle.com')

    client.mark_entries_read.assert_not_called()


def test_run_sync_does_not_mark_read_on_epub_failure():
    client = MagicMock()
    client.get_unread_entries.return_value = make_entries()

    with patch('sync.build_epub', side_effect=Exception('EPUB error')), \
         patch('sync.send_epub') as mock_send:
        run_sync([client], 'u@gmail.com', 'pass', 'k@kindle.com')

    mock_send.assert_not_called()
    client.mark_entries_read.assert_not_called()


def test_run_sync_skips_failed_feed_and_continues():
    c1, c2 = MagicMock(), MagicMock()
    c1.get_unread_entries.side_effect = Exception('Connection refused')
    c2.get_unread_entries.return_value = make_entries(10)

    with patch('sync.build_epub', return_value=b'epub') as mock_epub, \
         patch('sync.send_epub'):
        run_sync([c1, c2], 'u@gmail.com', 'pass', 'k@kindle.com')

    mock_epub.assert_called_once()


def test_run_sync_logs_error_if_mark_read_fails():
    client = MagicMock()
    client.get_unread_entries.return_value = make_entries()
    client.mark_entries_read.side_effect = Exception('Miniflux unavailable')

    with patch('sync.build_epub', return_value=b'epub'), patch('sync.send_epub'):
        run_sync([client], 'u@gmail.com', 'pass', 'k@kindle.com')

    client.mark_entries_read.assert_called_once()


def test_run_sync_allowlists_miniflux_hosts_for_image_fetching():
    client = MagicMock()
    client.hostname = 'miniflux.lan'
    client.get_unread_entries.return_value = make_entries()

    with patch('sync.build_epub', return_value=b'epub') as mock_epub, patch('sync.send_epub'):
        run_sync([client], 'u@gmail.com', 'pass', 'k@kindle.com')

    assert mock_epub.call_args.kwargs['allowed_hosts'] == {'miniflux.lan'}


def test_refresh_feeds_calls_all_clients():
    c1, c2 = MagicMock(), MagicMock()
    refresh_feeds([c1, c2])
    c1.refresh_feed.assert_called_once()
    c2.refresh_feed.assert_called_once()


def test_refresh_feeds_skips_failed_client():
    c1, c2 = MagicMock(), MagicMock()
    c1.refresh_feed.side_effect = Exception('timeout')
    refresh_feeds([c1, c2])
    c2.refresh_feed.assert_called_once()
