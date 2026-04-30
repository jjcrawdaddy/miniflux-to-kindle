import html
import os
import tempfile
from datetime import datetime
from ebooklib import epub


def build_epub(entries: list[dict], digest_date: str) -> bytes:
    entries_sorted = sorted(
        entries,
        key=lambda e: datetime.fromisoformat(e['published_at'])
    )

    book = epub.EpubBook()
    book.set_title(f'Daily Digest — {digest_date}')
    book.set_language('en')

    chapters = []
    toc_links = []

    for i, entry in enumerate(entries_sorted):
        file_name = f'article_{i:04d}.xhtml'
        chapter = epub.EpubHtml(title=entry['title'], file_name=file_name, lang='en')
        safe_title = html.escape(entry['title'])
        safe_url = html.escape(entry['url'], quote=True)
        chapter.content = (
            f'<h1>{safe_title}</h1>'
            f'<p><a href="{safe_url}">{safe_url}</a></p>'
            f'{entry["content"]}'
        )
        book.add_item(chapter)
        chapters.append(chapter)
        toc_links.append(epub.Link(file_name, entry['title'], f'article_{i:04d}'))

    book.toc = toc_links
    book.add_item(epub.EpubNcx())
    book.add_item(epub.EpubNav())
    book.spine = ['nav'] + chapters

    with tempfile.NamedTemporaryFile(suffix='.epub', delete=False) as f:
        tmp_path = f.name
    try:
        epub.write_epub(tmp_path, book)
        with open(tmp_path, 'rb') as f:
            return f.read()
    finally:
        os.unlink(tmp_path)
