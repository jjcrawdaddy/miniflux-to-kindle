from datetime import datetime
from unittest.mock import MagicMock, patch
from zoneinfo import ZoneInfo

from config import Config
from sync import run_sync, refresh_feeds


def make_entries(id_offset=0):
    return [{
        'id': 1 + id_offset,
        'title': f'Article {1 + id_offset}',
        'url': f'http://ex.com/{1 + id_offset}',
        'content': '<p>Content</p>',
        'published_at': '2026-04-30T08:00:00+00:00',
    }]


def make_config(feed_ids=(55,), timezone='UTC'):
    return Config(
        miniflux_base_url='http://miniflux.lan:8080',
        miniflux_api_key='mk',
        feed_ids=feed_ids,
        gmail_user='u@gmail.com',
        gmail_app_password='pass',
        kindle_email='k@kindle.com',
        digest_hour=6,
        timezone=timezone,
    )


def make_client(entries_by_feed):
    client = MagicMock()
    client.hostname = 'miniflux.lan'
    client.get_unread_entries.side_effect = lambda fid: entries_by_feed[fid]
    return client


def test_run_sync_fetches_all_feeds():
    client = make_client({55: make_entries(0), 12: make_entries(10)})

    with patch('sync.build_epub', return_value=b'epub'), patch('sync.send_epub'):
        run_sync(client, make_config(feed_ids=(55, 12)))

    assert [c.args[0] for c in client.get_unread_entries.call_args_list] == [55, 12]


def test_run_sync_skips_when_no_entries():
    client = make_client({55: []})

    with patch('sync.build_epub') as mock_epub, patch('sync.send_epub') as mock_send:
        run_sync(client, make_config())

    mock_epub.assert_not_called()
    mock_send.assert_not_called()
    client.mark_entries_read.assert_not_called()


def test_run_sync_marks_all_entries_read_after_send():
    client = make_client({55: make_entries(0), 12: make_entries(10)})

    with patch('sync.build_epub', return_value=b'epub'), patch('sync.send_epub'):
        run_sync(client, make_config(feed_ids=(55, 12)))

    client.mark_entries_read.assert_called_once_with([1, 11])


def test_run_sync_sends_with_configured_credentials():
    client = make_client({55: make_entries()})

    with patch('sync.build_epub', return_value=b'epub'), \
         patch('sync.send_epub') as mock_send:
        run_sync(client, make_config())

    args = mock_send.call_args.args
    assert args[2:] == ('u@gmail.com', 'pass', 'k@kindle.com')


def test_run_sync_does_not_mark_read_on_email_failure():
    client = make_client({55: make_entries()})

    with patch('sync.build_epub', return_value=b'epub'), \
         patch('sync.send_epub', side_effect=Exception('SMTP error')):
        run_sync(client, make_config())

    client.mark_entries_read.assert_not_called()


def test_run_sync_does_not_mark_read_on_epub_failure():
    client = make_client({55: make_entries()})

    with patch('sync.build_epub', side_effect=Exception('EPUB error')), \
         patch('sync.send_epub') as mock_send:
        run_sync(client, make_config())

    mock_send.assert_not_called()
    client.mark_entries_read.assert_not_called()


def test_run_sync_skips_failed_feed_and_continues():
    client = MagicMock()
    client.hostname = 'miniflux.lan'

    def fetch(fid):
        if fid == 55:
            raise Exception('Connection refused')
        return make_entries(10)

    client.get_unread_entries.side_effect = fetch

    with patch('sync.build_epub', return_value=b'epub') as mock_epub, \
         patch('sync.send_epub'):
        run_sync(client, make_config(feed_ids=(55, 12)))

    mock_epub.assert_called_once()


def test_run_sync_logs_error_if_mark_read_fails():
    client = make_client({55: make_entries()})
    client.mark_entries_read.side_effect = Exception('Miniflux unavailable')

    with patch('sync.build_epub', return_value=b'epub'), patch('sync.send_epub'):
        run_sync(client, make_config())

    client.mark_entries_read.assert_called_once()


def test_run_sync_passes_feed_order_to_epub_builder():
    client = make_client({55: make_entries(0), 12: make_entries(10)})

    with patch('sync.build_epub', return_value=b'epub') as mock_epub, patch('sync.send_epub'):
        run_sync(client, make_config(feed_ids=(55, 12)))

    assert mock_epub.call_args.kwargs['feed_ids'] == (55, 12)


def test_run_sync_allowlists_miniflux_host_for_image_fetching():
    client = make_client({55: make_entries()})

    with patch('sync.build_epub', return_value=b'epub') as mock_epub, patch('sync.send_epub'):
        run_sync(client, make_config())

    assert mock_epub.call_args.kwargs['allowed_hosts'] == {'miniflux.lan'}


def test_run_sync_uses_configured_timezone_for_digest_date():
    # Etc/GMT-14 (UTC+14) and Etc/GMT+12 (UTC-12) are 26 hours apart, so they
    # are never on the same calendar date — the filenames must differ
    filenames = {}
    for tz in ('Etc/GMT-14', 'Etc/GMT+12'):
        client = make_client({55: make_entries()})
        with patch('sync.build_epub', return_value=b'epub'), \
             patch('sync.send_epub') as mock_send:
            before = datetime.now(ZoneInfo(tz)).date().isoformat()
            run_sync(client, make_config(timezone=tz))
            after = datetime.now(ZoneInfo(tz)).date().isoformat()
        filenames[tz] = mock_send.call_args.args[1]
        assert filenames[tz] in (f'digest-{before}.epub', f'digest-{after}.epub')
    assert filenames['Etc/GMT-14'] != filenames['Etc/GMT+12']


def test_run_sync_returns_none_on_success():
    client = make_client({55: make_entries()})

    with patch('sync.build_epub', return_value=b'epub'), patch('sync.send_epub'):
        assert run_sync(client, make_config()) is None


def test_run_sync_returns_none_when_no_entries():
    # A quiet day is a success — it must not trigger a monitoring alert
    client = make_client({55: []})

    with patch('sync.build_epub'), patch('sync.send_epub'):
        assert run_sync(client, make_config()) is None


def test_run_sync_returns_error_on_send_failure():
    client = make_client({55: make_entries()})

    with patch('sync.build_epub', return_value=b'epub'), \
         patch('sync.send_epub', side_effect=Exception('SMTP timed out')):
        error = run_sync(client, make_config())

    assert error is not None and 'SMTP timed out' in error


def test_run_sync_returns_error_on_epub_failure():
    client = make_client({55: make_entries()})

    with patch('sync.build_epub', side_effect=Exception('bad HTML')), \
         patch('sync.send_epub'):
        error = run_sync(client, make_config())

    assert error is not None and 'bad HTML' in error


def test_run_sync_returns_error_when_all_feeds_fail():
    # "No entries" because every fetch failed is an outage, not a quiet day
    client = MagicMock()
    client.hostname = 'miniflux.lan'
    client.get_unread_entries.side_effect = Exception('Connection refused')

    with patch('sync.build_epub'), patch('sync.send_epub'):
        error = run_sync(client, make_config(feed_ids=(55, 12)))

    assert error is not None and 'Connection refused' in error


def test_run_sync_returns_error_on_mark_read_failure():
    # Digest was sent, but unmarked entries mean duplicates tomorrow — alert
    client = make_client({55: make_entries()})
    client.mark_entries_read.side_effect = Exception('Miniflux unavailable')

    with patch('sync.build_epub', return_value=b'epub'), patch('sync.send_epub'):
        error = run_sync(client, make_config())

    assert error is not None and 'Miniflux unavailable' in error


def test_refresh_feeds_refreshes_all_feed_ids():
    client = MagicMock()
    refresh_feeds(client, [55, 12])
    assert [c.args[0] for c in client.refresh_feed.call_args_list] == [55, 12]


def test_refresh_feeds_skips_failed_feed():
    client = MagicMock()

    def refresh(fid):
        if fid == 55:
            raise Exception('timeout')

    client.refresh_feed.side_effect = refresh
    refresh_feeds(client, [55, 12])
    assert client.refresh_feed.call_count == 2
