import hashlib
import html
import os
import tempfile
from datetime import datetime
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup
from ebooklib import epub


def _embed_images(book: epub.EpubBook, content: str, seen: dict) -> str:
    soup = BeautifulSoup(content, 'html.parser')
    for img in soup.find_all('img'):
        src = img.get('src', '')
        if not src.startswith('http'):
            img.decompose()
            continue
        if src in seen:
            img['src'] = seen[src]
            continue
        try:
            resp = requests.get(src, timeout=10)
            resp.raise_for_status()
            media_type = resp.headers.get('Content-Type', 'image/jpeg').split(';')[0].strip()
            ext = os.path.splitext(urlparse(src).path)[1].lstrip('.').lower() or 'jpg'
            img_name = f'images/img_{hashlib.md5(src.encode()).hexdigest()[:8]}.{ext}'
            epub_img = epub.EpubImage()
            epub_img.file_name = img_name
            epub_img.media_type = media_type
            epub_img.content = resp.content
            book.add_item(epub_img)
            seen[src] = img_name
            img['src'] = img_name
        except Exception:
            img.decompose()
    return str(soup)


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
    seen_images: dict = {}

    for i, entry in enumerate(entries_sorted):
        file_name = f'article_{i:04d}.xhtml'
        chapter = epub.EpubHtml(title=entry['title'], file_name=file_name, lang='en')
        embedded_content = _embed_images(book, entry['content'], seen_images)
        safe_title = html.escape(entry['title'])
        safe_url = html.escape(entry['url'], quote=True)
        chapter.content = (
            f'<h1>{safe_title}</h1>'
            f'<p><a href="{safe_url}">{safe_url}</a></p>'
            f'{embedded_content}'
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
