import logging
from datetime import datetime
from zoneinfo import ZoneInfo

from config import Config
from epub_builder import build_epub
from email_sender import send_epub
from miniflux_client import MinifluxClient

logger = logging.getLogger(__name__)


def refresh_feeds(client: MinifluxClient, feed_ids: list[int]) -> None:
    for feed_id in feed_ids:
        try:
            client.refresh_feed(feed_id)
        except Exception as exc:
            logger.error("Failed to refresh feed %d: %s", feed_id, exc)
    logger.info("Refreshed %d feeds", len(feed_ids))


def run_sync(client: MinifluxClient, config: Config) -> None:
    all_entries = []

    for feed_id in config.feed_ids:
        try:
            all_entries.extend(client.get_unread_entries(feed_id))
        except Exception as exc:
            logger.error("Failed to fetch feed %d: %s", feed_id, exc)

    if not all_entries:
        logger.info("No unread entries, skipping digest")
        return

    logger.info("Fetched %d entries across %d feeds", len(all_entries), len(config.feed_ids))

    digest_date = datetime.now(ZoneInfo(config.timezone)).date().isoformat()
    filename = f'digest-{digest_date}.epub'

    try:
        # Miniflux may rewrite image URLs to its own media proxy, which can live
        # at a private address — exempt it from the public-URL check
        epub_bytes = build_epub(
            all_entries, digest_date, feed_ids=config.feed_ids, allowed_hosts={client.hostname}
        )
    except Exception as exc:
        logger.error("EPUB build failed: %s", exc)
        return

    size_mb = len(epub_bytes) / 1024 / 1024
    logger.info("EPUB size: %.1f MB", size_mb)

    try:
        send_epub(
            epub_bytes, filename,
            config.gmail_user, config.gmail_app_password, config.kindle_email,
        )
        logger.info("Sent digest: %s", filename)
    except Exception as exc:
        logger.error("Email send failed, entries not marked read: %s", exc)
        return

    all_ids = [e['id'] for e in all_entries]
    try:
        client.mark_entries_read(all_ids)
        logger.info("Marked %d entries as read", len(all_ids))
    except Exception as exc:
        logger.error("Failed to mark entries as read: %s", exc)
