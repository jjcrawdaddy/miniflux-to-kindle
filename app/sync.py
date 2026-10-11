import logging
import re
from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo

from config import Config
from epub_builder import build_epub
from email_sender import send_epub
from miniflux_client import MinifluxClient

logger = logging.getLogger(__name__)


def _category_titles(entries: list[dict]) -> list[str]:
    titles = []
    seen = set()
    for entry in entries:
        title = ((entry.get('feed') or {}).get('category') or {}).get('title')
        if not title:
            title = 'Uncategorized'
        if title not in seen:
            seen.add(title)
            titles.append(title)
    return titles


def _slugify(text: str) -> str:
    return re.sub(r'[^\w]+', '-', text).strip('-').lower()


def digest_filename(digest_date: str, entries: list[dict]) -> str:
    slugs = [s for s in (_slugify(t) for t in _category_titles(entries)) if s and s != 'uncategorized']
    if not slugs:
        slugs = ['digest']
    return f"miniflux-{'-'.join(slugs)}-{digest_date}.epub"


def previous_day_window(tz_name: str) -> tuple[int, int]:
    """Unix timestamps bounding the previous calendar day in `tz_name`.

    The digest only includes articles published on the day before it runs,
    so a 06:00 digest covers midnight-to-midnight of yesterday (local time).
    """
    tz = ZoneInfo(tz_name)
    now = datetime.now(tz)
    day_start = datetime.combine(now.date(), time.min, tzinfo=tz)
    prev_start = day_start - timedelta(days=1)
    return int(prev_start.timestamp()), int(day_start.timestamp())


def refresh_feeds(
    client: MinifluxClient, feed_ids: list[int], category_ids: list[int] = ()
) -> None:
    for feed_id in feed_ids:
        try:
            client.refresh_feed(feed_id)
        except Exception as exc:
            logger.error("Failed to refresh feed %d: %s", feed_id, exc)
    for category_id in category_ids:
        try:
            client.refresh_category(category_id)
        except Exception as exc:
            logger.error("Failed to refresh category %d: %s", category_id, exc)
    logger.info("Refreshed %d feeds and %d categories", len(feed_ids), len(category_ids))


def run_sync(client: MinifluxClient, config: Config) -> str | None:
    """Run one digest cycle. Returns None on success, an error summary on failure."""
    all_entries = []
    seen_ids = set()
    fetch_errors = []
    published_after, published_before = previous_day_window(config.timezone)

    for feed_id in config.feed_ids:
        try:
            for entry in client.get_unread_entries(feed_id, published_after, published_before):
                if entry['id'] not in seen_ids:
                    seen_ids.add(entry['id'])
                    all_entries.append(entry)
        except Exception as exc:
            logger.error("Failed to fetch feed %d: %s", feed_id, exc)
            fetch_errors.append(f'feed {feed_id}: {exc}')

    for category_id in config.category_ids:
        try:
            for entry in client.get_category_entries(category_id, published_after, published_before):
                if entry['id'] not in seen_ids:
                    seen_ids.add(entry['id'])
                    all_entries.append(entry)
        except Exception as exc:
            logger.error("Failed to fetch category %d: %s", category_id, exc)
            fetch_errors.append(f'category {category_id}: {exc}')

    if not all_entries:
        if fetch_errors:
            return f"No entries and fetches failed — {'; '.join(fetch_errors)}"
        logger.info("No unread entries, skipping digest")
        return None

    logger.info(
        "Fetched %d entries across %d feeds and %d categories",
        len(all_entries), len(config.feed_ids), len(config.category_ids),
    )

    digest_date = datetime.now(ZoneInfo(config.timezone)).date().isoformat()
    filename = digest_filename(digest_date, all_entries)

    try:
        # Miniflux may rewrite image URLs to its own media proxy, which can live
        # at a private address — exempt it from the public-URL check
        epub_bytes = build_epub(
            all_entries,
            digest_date,
            feed_ids=config.feed_ids,
            category_ids=config.category_ids,
            allowed_hosts={client.hostname},
        )
    except Exception as exc:
        logger.error("EPUB build failed: %s", exc)
        return f'EPUB build failed: {exc}'

    size_mb = len(epub_bytes) / 1024 / 1024
    logger.info("EPUB size: %.1f MB", size_mb)

    try:
        send_epub(epub_bytes, filename, config.smtp, config.kindle_email)
        logger.info("Sent digest: %s", filename)
    except Exception as exc:
        logger.error("Email send failed, entries not marked read: %s", exc)
        return f'Email send failed: {exc}'

    all_ids = [e['id'] for e in all_entries]
    if not config.mark_as_read:
        logger.info("MARK_AS_READ is false — leaving %d entries unread", len(all_ids))
        return None
    try:
        client.mark_entries_read(all_ids)
        logger.info("Marked %d entries as read", len(all_ids))
    except Exception as exc:
        logger.error("Failed to mark entries as read: %s", exc)
        return f'Digest sent, but marking entries read failed (expect duplicates): {exc}'
    return None
