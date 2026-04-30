import io
import zipfile

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
