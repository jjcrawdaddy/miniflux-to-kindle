import io
import zipfile
from unittest.mock import MagicMock, patch

from epub_builder import build_epub

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


def make_img_mock(content_type='image/jpeg', content=b'\xff\xd8\xff'):
    m = MagicMock()
    m.headers = {'Content-Type': content_type}
    m.content = content
    return m


def test_build_epub_embeds_image_from_content():
    entries = [{
        'id': 1, 'title': 'A', 'url': 'http://ex.com/1',
        'content': '<p><img src="http://ex.com/img.jpg" /></p>',
        'published_at': '2026-04-30T08:00:00+00:00',
    }]
    with patch('epub_builder.requests.get', return_value=make_img_mock()):
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
    with patch('epub_builder.requests.get', return_value=make_img_mock()) as mock_get:
        build_epub(entries, '2026-04-30')
    assert mock_get.call_count == 1
