import io
import socket
import zipfile
from unittest.mock import MagicMock, patch

from epub_builder import build_epub, _fetch_image, _is_public_url

ENTRIES = [
    {
        'id': 1,
        'title': 'Article One',
        'url': 'http://ex.com/1',
        'content': '<p>Content one</p>',
        'published_at': '2026-04-30T09:00:00+00:00',
    },
    {
        'id': 2,
        'title': 'Article Two',
        'url': 'http://ex.com/2',
        'content': '<p>Content two</p>',
        'published_at': '2026-04-30T08:00:00+00:00',
    },
]


def test_build_epub_returns_bytes():
    result = build_epub(ENTRIES, '2026-04-30')
    assert isinstance(result, bytes)
    assert len(result) > 0


def test_build_epub_is_valid_epub_zip():
    result = build_epub(ENTRIES, '2026-04-30')
    with zipfile.ZipFile(io.BytesIO(result)) as zf:
        assert 'mimetype' in zf.namelist()
        assert zf.read('mimetype') == b'application/epub+zip'


def test_build_epub_contains_all_article_titles():
    result = build_epub(ENTRIES, '2026-04-30')
    with zipfile.ZipFile(io.BytesIO(result)) as zf:
        full_text = ' '.join(
            zf.read(name).decode('utf-8', errors='ignore')
            for name in zf.namelist()
        )
    assert 'Article One' in full_text
    assert 'Article Two' in full_text


def test_build_epub_sorts_by_published_at():
    # Article Two has earlier published_at; it should be article_0000
    result = build_epub(ENTRIES, '2026-04-30')
    with zipfile.ZipFile(io.BytesIO(result)) as zf:
        first_files = [n for n in zf.namelist() if n.endswith('article_0000.xhtml')]
        assert first_files, f"article_0000.xhtml not found in {zf.namelist()}"
        first_content = zf.read(first_files[0]).decode('utf-8')
    assert 'Article Two' in first_content


def test_build_epub_handles_empty_entries():
    result = build_epub([], '2026-04-30')
    assert isinstance(result, bytes)
    assert len(result) > 0


def test_build_epub_includes_author_and_date_in_byline():
    entries = [{
        'id': 1,
        'title': 'A',
        'url': 'http://ex.com/1',
        'content': '<p>Content</p>',
        'author': 'Jane Smith',
        'published_at': '2026-04-30T08:00:00+00:00',
    }]
    result = build_epub(entries, '2026-04-30')
    with zipfile.ZipFile(io.BytesIO(result)) as zf:
        full_text = ' '.join(
            zf.read(name).decode('utf-8', errors='ignore')
            for name in zf.namelist()
        )
    assert 'Jane Smith' in full_text
    assert 'April 30, 2026' in full_text


def test_build_epub_shows_date_without_author_when_author_absent():
    entries = [{
        'id': 1,
        'title': 'A',
        'url': 'http://ex.com/1',
        'content': '<p>Content</p>',
        'published_at': '2026-04-30T08:00:00+00:00',
    }]
    result = build_epub(entries, '2026-04-30')
    with zipfile.ZipFile(io.BytesIO(result)) as zf:
        full_text = ' '.join(
            zf.read(name).decode('utf-8', errors='ignore')
            for name in zf.namelist()
        )
    assert 'April 30, 2026' in full_text
    assert 'By' not in full_text


def test_build_epub_sorts_by_feed_id_order_then_date():
    # feed 200 is listed first in feed_ids, so its articles come before feed 100
    entries = [
        {'id': 1, 'feed_id': 100, 'title': 'Feed100 Early', 'url': 'http://ex.com/1',
         'content': '', 'published_at': '2026-04-30T07:00:00+00:00'},
        {'id': 2, 'feed_id': 200, 'title': 'Feed200 Late', 'url': 'http://ex.com/2',
         'content': '', 'published_at': '2026-04-30T09:00:00+00:00'},
        {'id': 3, 'feed_id': 200, 'title': 'Feed200 Early', 'url': 'http://ex.com/3',
         'content': '', 'published_at': '2026-04-30T08:00:00+00:00'},
    ]
    result = build_epub(entries, '2026-04-30', feed_ids=[200, 100])
    with zipfile.ZipFile(io.BytesIO(result)) as zf:
        first = [n for n in zf.namelist() if n.endswith('article_0000.xhtml')]
        second = [n for n in zf.namelist() if n.endswith('article_0001.xhtml')]
        first_text = zf.read(first[0]).decode('utf-8')
        second_text = zf.read(second[0]).decode('utf-8')
    assert 'Feed200 Early' in first_text
    assert 'Feed200 Late' in second_text


def make_img_mock(content_type='image/jpeg', content=b'\xff\xd8\xff'):
    m = MagicMock()
    m.headers = {'Content-Type': content_type, 'Content-Length': str(len(content))}
    m.content = content
    m.iter_content = lambda chunk_size=8192: [content]
    m.is_redirect = False
    m.is_permanent_redirect = False
    return m


def make_redirect_mock(location):
    m = MagicMock()
    m.is_redirect = True
    m.is_permanent_redirect = False
    m.headers = {'Location': location}
    return m


def make_addrinfo(ip):
    return [(socket.AF_INET, socket.SOCK_STREAM, 6, '', (ip, 0))]


def test_build_epub_embeds_image_from_content():
    entries = [{
        'id': 1, 'title': 'A', 'url': 'http://ex.com/1',
        'content': '<p><img src="http://ex.com/img.jpg" /></p>',
        'published_at': '2026-04-30T08:00:00+00:00',
    }]
    with patch('epub_builder._is_public_url', return_value=True), \
         patch('epub_builder.requests.get', return_value=make_img_mock()):
        result = build_epub(entries, '2026-04-30')
    with zipfile.ZipFile(io.BytesIO(result)) as zf:
        image_files = [n for n in zf.namelist() if 'images/' in n]
    assert image_files, f"No image files found in EPUB"


def test_build_epub_removes_image_on_download_failure():
    entries = [{
        'id': 1, 'title': 'A', 'url': 'http://ex.com/1',
        'content': '<p><img src="http://ex.com/img.jpg" /></p>',
        'published_at': '2026-04-30T08:00:00+00:00',
    }]
    with patch('epub_builder.requests.get', side_effect=Exception('Network error')):
        result = build_epub(entries, '2026-04-30')
    with zipfile.ZipFile(io.BytesIO(result)) as zf:
        full_text = ' '.join(
            zf.read(name).decode('utf-8', errors='ignore')
            for name in zf.namelist()
        )
    assert '<img' not in full_text


def test_build_epub_deduplicates_images():
    entries = [
        {'id': 1, 'title': 'A', 'url': 'http://ex.com/1',
         'content': '<img src="http://ex.com/img.jpg" />',
         'published_at': '2026-04-30T08:00:00+00:00'},
        {'id': 2, 'title': 'B', 'url': 'http://ex.com/2',
         'content': '<img src="http://ex.com/img.jpg" />',
         'published_at': '2026-04-30T09:00:00+00:00'},
    ]
    with patch('epub_builder._is_public_url', return_value=True), \
         patch('epub_builder.requests.get', return_value=make_img_mock()) as mock_get:
        build_epub(entries, '2026-04-30')
    assert mock_get.call_count == 1


def test_is_public_url_allows_global_address():
    with patch('epub_builder.socket.getaddrinfo', return_value=make_addrinfo('93.184.216.34')):
        assert _is_public_url('http://example.com/img.jpg') is True


def test_is_public_url_blocks_non_global_addresses():
    # CGNAT, multicast, and unspecified are not private/loopback/link-local/reserved,
    # but must still be blocked
    for ip in ['100.64.1.1', '224.0.0.1', '0.0.0.0', '10.0.0.1', '127.0.0.1']:
        with patch('epub_builder.socket.getaddrinfo', return_value=make_addrinfo(ip)):
            assert _is_public_url('http://example.com/img.jpg') is False, ip


def test_is_public_url_allows_allowlisted_host_without_resolving():
    with patch('epub_builder.socket.getaddrinfo', side_effect=AssertionError('must not resolve')):
        assert _is_public_url(
            'http://miniflux.lan:8080/proxy/abc',
            allowed_hosts=frozenset({'miniflux.lan'}),
        ) is True


def test_fetch_image_blocks_redirect_to_private_address():
    def fake_public(url, allowed_hosts=frozenset()):
        return 'internal' not in url

    with patch('epub_builder._is_public_url', side_effect=fake_public), \
         patch('epub_builder.requests.get',
               return_value=make_redirect_mock('http://internal.lan/secret')) as mock_get:
        result = _fetch_image('http://public.example/img.jpg', frozenset())
    assert result is None
    assert mock_get.call_count == 1


def test_fetch_image_follows_public_redirect_without_auto_redirects():
    final = make_img_mock()
    with patch('epub_builder._is_public_url', return_value=True), \
         patch('epub_builder.requests.get',
               side_effect=[make_redirect_mock('http://cdn.example/img.jpg'), final]) as mock_get:
        result = _fetch_image('http://public.example/img.jpg', frozenset())
    assert result is final
    for call in mock_get.call_args_list:
        assert call.kwargs['allow_redirects'] is False


def test_fetch_image_gives_up_after_redirect_limit():
    with patch('epub_builder._is_public_url', return_value=True), \
         patch('epub_builder.requests.get',
               return_value=make_redirect_mock('http://public.example/loop.jpg')) as mock_get:
        result = _fetch_image('http://public.example/img.jpg', frozenset())
    assert result is None
    assert mock_get.call_count <= 5


def test_build_epub_removes_image_redirecting_to_private_host():
    entries = [{
        'id': 1, 'title': 'A', 'url': 'http://ex.com/1',
        'content': '<p><img src="http://ex.com/img.jpg" /></p>',
        'published_at': '2026-04-30T08:00:00+00:00',
    }]

    def fake_public(url, allowed_hosts=frozenset()):
        return '192.168.' not in url

    with patch('epub_builder._is_public_url', side_effect=fake_public), \
         patch('epub_builder.requests.get',
               return_value=make_redirect_mock('http://192.168.1.1/admin')):
        result = build_epub(entries, '2026-04-30')
    with zipfile.ZipFile(io.BytesIO(result)) as zf:
        full_text = ' '.join(
            zf.read(name).decode('utf-8', errors='ignore')
            for name in zf.namelist()
        )
        image_files = [n for n in zf.namelist() if 'images/' in n]
    assert '<img' not in full_text
    assert not image_files
