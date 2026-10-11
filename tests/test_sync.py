from datetime import datetime
from unittest.mock import MagicMock, patch
from zoneinfo import ZoneInfo

from config import Config, SmtpConfig
from sync import run_sync, refresh_feeds, digest_filename


def make_entries(id_offset=0):
    return [{
        'id': 1 + id_offset,
        'title': f'Article {1 + id_offset}',
        'url': f'http://ex.com/{1 + id_offset}',
        'content': '<p>Content</p>',
        'published_at': '2026-04-30T08:00:00+00:00',
    }]


def make_config(feed_ids=(55,), category_ids=(), timezone='UTC', mark_as_read=True):
    return Config(
        miniflux_base_url='http://miniflux.lan:8080',
        miniflux_api_key='mk',
        feed_ids=feed_ids,
        category_ids=category_ids,
        smtp=SmtpConfig(
            host='smtp.gmail.com', port=587, user='u@gmail.com',
            password='pass', from_address='u@gmail.com', security='starttls',
        ),
        kindle_email='k@kindle.com',
        digest_hour=6,
        timezone=timezone,
        mark_as_read=mark_as_read,
    )


def make_client(entries_by_feed, entries_by_category=None):
    client = MagicMock()
    client.hostname = 'miniflux.lan'
    client.get_unread_entries.side_effect = lambda fid, *a: entries_by_feed[fid]
    client.get_category_entries.side_effect = lambda cid, *a: (entries_by_category or {}).get(cid, [])
    return client


def test_run_sync_fetches_all_feeds():
    client = make_client({55: make_entries(0), 12: make_entries(10)})

    with patch('sync.build_epub', return_value=b'epub'), patch('sync.send_epub'):
        run_sync(client, make_config(feed_ids=(55, 12)))

    assert [c.args[0] for c in client.get_unread_entries.call_args_list] == [55, 12]


def test_run_sync_filters_to_previous_day():
    client = make_client({55: make_entries()})

    with patch('sync.build_epub', return_value=b'epub'), patch('sync.send_epub'):
        run_sync(client, make_config(timezone='UTC'))

    _, published_after, published_before = client.get_unread_entries.call_args.args
    assert isinstance(published_after, int)
    assert isinstance(published_before, int)
    assert published_before - published_after == 86400


def test_run_sync_passes_previous_day_window_to_categories():
    client = make_client({}, entries_by_category={7: make_entries()})

    with patch('sync.build_epub', return_value=b'epub'), patch('sync.send_epub'):
        run_sync(client, make_config(feed_ids=(), category_ids=(7,), timezone='UTC'))

    _, published_after, published_before = client.get_category_entries.call_args.args
    assert published_before - published_after == 86400


def test_run_sync_fetches_all_categories():
    client = make_client({}, entries_by_category={7: make_entries(0), 8: make_entries(10)})

    with patch('sync.build_epub', return_value=b'epub'), patch('sync.send_epub'):
        run_sync(client, make_config(feed_ids=(), category_ids=(7, 8)))

    assert [c.args[0] for c in client.get_category_entries.call_args_list] == [7, 8]


def test_run_sync_deduplicates_entries_across_sources():
    # Feed 55 and category 7 both contain entry id 1 — it must be sent once
    client = make_client({55: make_entries(0)}, entries_by_category={7: make_entries(0)})

    with patch('sync.build_epub', return_value=b'epub') as mock_epub, patch('sync.send_epub'):
        run_sync(client, make_config(feed_ids=(55,), category_ids=(7,)))

    entries = mock_epub.call_args.args[0]
    assert len(entries) == 1
    client.mark_entries_read.assert_called_once_with([1])


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


def test_run_sync_does_not_mark_read_when_mark_as_read_false():
    client = make_client({55: make_entries(0), 12: make_entries(10)})

    with patch('sync.build_epub', return_value=b'epub'), patch('sync.send_epub'):
        run_sync(client, make_config(feed_ids=(55, 12), mark_as_read=False))

    client.mark_entries_read.assert_not_called()


def test_run_sync_sends_with_configured_smtp():
    client = make_client({55: make_entries()})

    with patch('sync.build_epub', return_value=b'epub'), \
         patch('sync.send_epub') as mock_send:
        run_sync(client, make_config())

    args = mock_send.call_args.args
    assert args[2] is not None
    assert args[2].host == 'smtp.gmail.com'
    assert args[2].user == 'u@gmail.com'
    assert args[3] == 'k@kindle.com'


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
    client.get_category_entries.return_value = []

    def fetch(fid, *a):
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


def test_run_sync_passes_source_ids_to_epub_builder():
    client = make_client({55: make_entries(0), 12: make_entries(10)},
                         entries_by_category={7: make_entries(20)})

    with patch('sync.build_epub', return_value=b'epub') as mock_epub, patch('sync.send_epub'):
        run_sync(client, make_config(feed_ids=(55, 12), category_ids=(7,)))

    assert mock_epub.call_args.kwargs['feed_ids'] == (55, 12)
    assert mock_epub.call_args.kwargs['category_ids'] == (7,)


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
        assert filenames[tz] in (f'miniflux-digest-{before}.epub', f'miniflux-digest-{after}.epub')
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


def test_run_sync_returns_error_when_all_sources_fail():
    # "No entries" because every fetch failed is an outage, not a quiet day
    client = MagicMock()
    client.hostname = 'miniflux.lan'
    client.get_unread_entries.side_effect = Exception('Connection refused')
    client.get_category_entries.side_effect = Exception('Connection refused')

    with patch('sync.build_epub'), patch('sync.send_epub'):
        error = run_sync(client, make_config(feed_ids=(55,), category_ids=(7,)))

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


def test_refresh_feeds_refreshes_all_category_ids():
    client = MagicMock()
    refresh_feeds(client, [55], [7, 8])
    assert [c.args[0] for c in client.refresh_category.call_args_list] == [7, 8]


def test_refresh_feeds_skips_failed_feed():
    client = MagicMock()

    def refresh(fid):
        if fid == 55:
            raise Exception('timeout')

    client.refresh_feed.side_effect = refresh
    refresh_feeds(client, [55, 12])
    assert client.refresh_feed.call_count == 2


def test_refresh_feeds_skips_failed_category():
    client = MagicMock()

    def refresh(cid):
        if cid == 7:
            raise Exception('timeout')

    client.refresh_category.side_effect = refresh
    refresh_feeds(client, [], [7, 8])
    assert client.refresh_category.call_count == 2


def make_entry_with_category(category_title):
    return {
        'id': 1,
        'title': 'Article',
        'url': 'http://ex.com/1',
        'content': '<p>Content</p>',
        'published_at': '2026-04-30T08:00:00+00:00',
        'feed': {'category': {'id': 4, 'title': category_title}},
    }


def test_digest_filename_includes_single_category():
    entries = [make_entry_with_category('News')]
    assert digest_filename('2026-10-10', entries) == 'miniflux-news-2026-10-10.epub'


def test_digest_filename_slugifies_category_title():
    entries = [make_entry_with_category('Engineering Blogs')]
    assert digest_filename('2026-10-10', entries) == 'miniflux-engineering-blogs-2026-10-10.epub'


def test_digest_filename_joins_multiple_categories():
    entries = [
        make_entry_with_category('News'),
        make_entry_with_category('Tech'),
        make_entry_with_category('News'),
    ]
    assert digest_filename('2026-10-10', entries) == 'miniflux-news-tech-2026-10-10.epub'


def test_digest_filename_falls_back_when_no_category():
    entries = [make_entries()[0]]
    assert digest_filename('2026-10-10', entries) == 'miniflux-digest-2026-10-10.epub'


def test_digest_filename_falls_back_for_uncategorized_only():
    entries = [make_entry_with_category('Uncategorized')]
    assert digest_filename('2026-10-10', entries) == 'miniflux-digest-2026-10-10.epub'
