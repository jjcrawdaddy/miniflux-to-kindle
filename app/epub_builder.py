import hashlib
import html
import io
import ipaddress
import os
import socket
import tempfile
from datetime import datetime
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup
from ebooklib import epub
from PIL import Image

MAX_IMAGE_BYTES = 5 * 1024 * 1024
MAX_REDIRECTS = 3
MAX_IMAGE_DIMENSION = 1200
JPEG_QUALITY = 75

_MEDIA_TYPE_TO_EXT = {
    'image/jpeg': 'jpg',
    'image/jpg': 'jpg',
    'image/png': 'png',
    'image/gif': 'gif',
    'image/webp': 'webp',
    'image/bmp': 'bmp',
}

_SAFE_LINK_SCHEMES = ('', 'http', 'https', 'mailto')

# Image formats the Kindle renderer can display. Anything else (WebP, BMP,
# AVIF, ...) is converted to JPEG, or dropped if that conversion fails.
_KINDLE_SAFE_IMAGE_TYPES = frozenset({'image/jpeg', 'image/jpg', 'image/png', 'image/gif'})


def _is_public_url(url: str, allowed_hosts: frozenset = frozenset()) -> bool:
    hostname = urlparse(url).hostname
    if not hostname:
        return False
    if hostname in allowed_hosts:
        return True
    try:
        for info in socket.getaddrinfo(hostname, None):
            addr = ipaddress.ip_address(info[4][0])
            # is_global reports True for multicast, so check it separately
            if addr.is_multicast or not addr.is_global:
                return False
    except (socket.gaierror, ValueError):
        return False
    return True


def _fetch_image(src: str, allowed_hosts: frozenset) -> requests.Response | None:
    # Follow redirects manually so every hop gets the public-URL check,
    # otherwise a public image URL could redirect to an internal address
    url = src
    for _ in range(MAX_REDIRECTS + 1):
        if not _is_public_url(url, allowed_hosts):
            return None
        resp = requests.get(url, timeout=10, stream=True, allow_redirects=False)
        if resp.is_redirect or resp.is_permanent_redirect:
            location = resp.headers.get('Location')
            if not location:
                return None
            url = urljoin(url, location)
            continue
        resp.raise_for_status()
        return resp
    return None


def _recompress_image(image_data: bytes, media_type: str) -> tuple[bytes, str]:
    # E-reader screens don't need multi-megabyte photos: downscale and
    # re-encode as JPEG, but only keep the result if it's actually smaller
    try:
        img = Image.open(io.BytesIO(image_data))
        img.thumbnail((MAX_IMAGE_DIMENSION, MAX_IMAGE_DIMENSION))
        if img.mode in ('RGBA', 'LA', 'PA') or (img.mode == 'P' and 'transparency' in img.info):
            rgba = img.convert('RGBA')
            flat = Image.new('RGB', rgba.size, 'white')
            flat.paste(rgba, mask=rgba.getchannel('A'))
            img = flat
        elif img.mode != 'RGB':
            img = img.convert('RGB')
        buf = io.BytesIO()
        img.save(buf, format='JPEG', quality=JPEG_QUALITY, optimize=True)
        recompressed = buf.getvalue()
    except Exception:
        return image_data, media_type
    # Kindle can't render WebP/BMP/etc., so always convert those to JPEG. For
    # formats it understands, only switch to JPEG when recompression saves space.
    if media_type not in _KINDLE_SAFE_IMAGE_TYPES or len(recompressed) < len(image_data):
        return recompressed, 'image/jpeg'
    return image_data, media_type


def _replace_incompatible_media(soup: BeautifulSoup, article_url: str = '') -> None:
    labels = {
        'audio': 'Audio', 'video': 'Video', 'iframe': 'Embedded content',
        'object': 'Embedded content', 'embed': 'Embedded content', 'svg': 'SVG image',
    }
    for tag in list(soup.find_all(list(labels))):
        # A parent replacement already removes any nested media or fallback.
        if tag.parent is None:
            continue
        label = labels[tag.name]
        candidates = [tag.get('src'), tag.get('data')]
        candidates.extend(source.get('src') for source in tag.find_all('source'))
        media_url = None
        for candidate in candidates:
            if not isinstance(candidate, str) or not candidate.strip():
                continue
            resolved = urljoin(article_url, candidate.strip())
            parsed = urlparse(resolved)
            if parsed.scheme in ('http', 'https') and parsed.hostname:
                media_url = resolved
                break
        placeholder = soup.new_tag('span')
        placeholder.string = f'[{label} omitted for Kindle compatibility.'
        link_url = media_url or article_url
        parsed = urlparse(link_url)
        if parsed.scheme in ('http', 'https') and parsed.hostname:
            placeholder.append(' ')
            link = soup.new_tag('a', href=link_url)
            link.string = 'Open original media' if media_url else 'View original article'
            placeholder.append(link)
            placeholder.append('.')
        placeholder.append(']')
        tag.replace_with(placeholder)
        tag.decompose()


def _embed_images(book: epub.EpubBook, content: str, seen: dict, allowed_hosts: frozenset = frozenset(), article_url: str = '') -> str:
    soup = BeautifulSoup(content, 'html.parser')
    for tag in soup(['script', 'style']):
        tag.decompose()
    for tag in soup.find_all(True):
        for attr in list(tag.attrs):
            if attr.lower().startswith('on'):
                del tag.attrs[attr]
    _replace_incompatible_media(soup, article_url)
    for source in soup.find_all('source'):
        source.decompose()
    for a in soup.find_all('a', href=True):
        href = a['href']
        if urlparse(href).scheme not in _SAFE_LINK_SCHEMES:
            a.unwrap()
        elif href.startswith('#') and not soup.find(id=href[1:]):
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
            resp = _fetch_image(src, allowed_hosts)
            if resp is None:
                img.decompose()
                continue
            media_type = resp.headers.get('Content-Type', '').split(';')[0].strip()
            # SVG can carry scripts and external references — reject it
            if not media_type.startswith('image/') or media_type == 'image/svg+xml':
                if media_type == 'image/svg+xml':
                    placeholder = soup.new_tag('span')
                    placeholder.string = '[SVG image omitted for Kindle compatibility. '
                    link = soup.new_tag('a', href=src)
                    link.string = 'Open original image'
                    placeholder.append(link)
                    placeholder.append('.]')
                    img.replace_with(placeholder)
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
            image_data, media_type = _recompress_image(b''.join(chunks), media_type)
            if media_type not in _KINDLE_SAFE_IMAGE_TYPES:
                # Decoding/transcoding failed and the original format isn't
                # something the Kindle can display — drop it rather than embed
                # an image that may crash the reader.
                img.decompose()
                continue
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


def _category_of(entry: dict) -> tuple[object, str]:
    feed = entry.get('feed') or {}
    category = feed.get('category') or {}
    cat_id = category.get('id')
    cat_title = category.get('title')
    if not cat_title:
        cat_title = 'Uncategorized'
    return cat_id, cat_title


def _group_by_category(
    entries: list[dict],
    feed_ids: list[int] | None,
    category_ids: list[int] | None,
) -> list[tuple[str, list[dict]]]:
    category_order = {cid: i for i, cid in enumerate(category_ids or ())}
    feed_order = {fid: i for i, fid in enumerate(feed_ids or ())}

    groups: dict[tuple[object, str], list[dict]] = {}
    for entry in entries:
        groups.setdefault(_category_of(entry), []).append(entry)

    def group_sort_key(item):
        (cat_id, cat_title), group_entries = item
        cat_rank = category_order.get(cat_id, len(category_order))
        min_feed_rank = min(
            (feed_order.get(e.get('feed_id'), len(feed_order)) for e in group_entries),
            default=len(feed_order),
        )
        return (cat_rank, min_feed_rank, cat_title.lower())

    result = []
    for (cat_id, cat_title), group_entries in sorted(groups.items(), key=group_sort_key):
        ordered = sorted(
            group_entries,
            key=lambda e: (
                feed_order.get(e.get('feed_id'), len(feed_order)),
                datetime.fromisoformat(e['published_at']),
            ),
        )
        result.append((cat_title, ordered))
    return result


def build_epub(
    entries: list[dict],
    digest_date: str,
    feed_ids: list[int] | None = None,
    category_ids: list[int] | None = None,
    allowed_hosts: frozenset = frozenset(),
) -> bytes:
    grouped = _group_by_category(entries, feed_ids, category_ids)

    book = epub.EpubBook()
    book.set_title(f'Daily Digest — {digest_date}')
    book.set_language('en')

    chapters = []
    toc = []
    seen_images: dict = {}
    article_i = 0
    section_i = 0

    for cat_title, cat_entries in grouped:
        header_file = f'section_{section_i:04d}.xhtml'
        section_i += 1
        header = epub.EpubHtml(title=cat_title, file_name=header_file, lang='en')
        header.content = f'<h1>{html.escape(cat_title)}</h1>'
        book.add_item(header)
        chapters.append(header)

        section_links = []
        for entry in cat_entries:
            file_name = f'article_{article_i:04d}.xhtml'
            article_i += 1
            chapter = epub.EpubHtml(title=entry['title'], file_name=file_name, lang='en')
            embedded_content = _embed_images(book, entry['content'], seen_images, allowed_hosts, entry['url'])
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
            section_links.append(epub.Link(file_name, entry['title'], f'article_{article_i - 1:04d}'))

        toc.append((epub.Section(cat_title), section_links))

    book.toc = toc
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
