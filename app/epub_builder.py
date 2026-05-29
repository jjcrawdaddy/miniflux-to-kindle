import hashlib
import html
import ipaddress
import os
import socket
import tempfile
from datetime import datetime
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup
from ebooklib import epub

MAX_IMAGE_BYTES = 5 * 1024 * 1024

_MEDIA_TYPE_TO_EXT = {
    'image/jpeg': 'jpg',
    'image/jpg': 'jpg',
    'image/png': 'png',
    'image/gif': 'gif',
    'image/webp': 'webp',
    'image/svg+xml': 'svg',
    'image/bmp': 'bmp',
}


def _is_public_url(url: str) -> bool:
    hostname = urlparse(url).hostname
    if not hostname:
        return False
    try:
        for info in socket.getaddrinfo(hostname, None):
            addr = ipaddress.ip_address(info[4][0])
            if addr.is_private or addr.is_loopback or addr.is_link_local or addr.is_reserved:
                return False
    except (socket.gaierror, ValueError):
        return False
    return True


def _embed_images(book: epub.EpubBook, content: str, seen: dict) -> str:
    soup = BeautifulSoup(content, 'html.parser')
    for iframe in soup.find_all('iframe'):
        src = iframe.get('src', '')
        iframe.replace_with(f'[Video: {src}]' if src else '[Video]')
    for a in soup.find_all('a', href=True):
        href = a['href']
        if href.startswith('#') and not soup.find(id=href[1:]):
            a.unwrap()
    for img in soup.find_all('img'):
        img.attrs.pop('srcset', None)
        src = img.get('src', '')
        if not src.startswith('http'):
            img.decompose()
            continue
        if src in seen:
            img['src'] = seen[src]
            continue
        try:
            if not _is_public_url(src):
                img.decompose()
                continue
            resp = requests.get(src, timeout=10, stream=True)
            resp.raise_for_status()
            media_type = resp.headers.get('Content-Type', '').split(';')[0].strip()
            if not media_type.startswith('image/'):
                img.decompose()
                continue
            content_length = resp.headers.get('Content-Length')
            if content_length and int(content_length) > MAX_IMAGE_BYTES:
                img.decompose()
                continue
            chunks = []
            size = 0
            for chunk in resp.iter_content(8192):
                size += len(chunk)
                if size > MAX_IMAGE_BYTES:
                    break
                chunks.append(chunk)
            if size > MAX_IMAGE_BYTES:
                img.decompose()
                continue
            image_data = b''.join(chunks)
            ext = _MEDIA_TYPE_TO_EXT.get(media_type) or os.path.splitext(urlparse(src).path)[1].lstrip('.').lower() or 'jpg'
            img_name = f'images/img_{hashlib.md5(src.encode()).hexdigest()[:8]}.{ext}'
            epub_img = epub.EpubImage()
            epub_img.file_name = img_name
            epub_img.media_type = media_type
            epub_img.content = image_data
            book.add_item(epub_img)
            seen[src] = img_name
            img['src'] = img_name
        except Exception:
            img.decompose()
    return str(soup)


def build_epub(entries: list[dict], digest_date: str, feed_ids: list[int] | None = None) -> bytes:
    if feed_ids:
        feed_order = {fid: i for i, fid in enumerate(feed_ids)}
        entries_sorted = sorted(
            entries,
            key=lambda e: (feed_order.get(e.get('feed_id', 0), len(feed_ids)), datetime.fromisoformat(e['published_at']))
        )
    else:
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
        pub_date = datetime.fromisoformat(entry['published_at']).strftime('%B %-d, %Y')
        byline_parts = [pub_date]
        if entry.get('author'):
            byline_parts.insert(0, f'By {html.escape(entry["author"])}')
        chapter.content = (
            f'<h1>{safe_title}</h1>'
            f'<p><em>{" · ".join(byline_parts)}</em></p>'
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
