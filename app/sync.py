import logging
from datetime import date

from epub_builder import build_epub
from email_sender import send_epub
from miniflux_client import MinifluxClient

logger = logging.getLogger(__name__)


def refresh_feeds(clients: list[MinifluxClient]) -> None:
    for client in clients:
        try:
            client.refresh_feed()
        except Exception as exc:
            logger.error("Failed to refresh feed: %s", exc)
    logger.info("Refreshed %d feeds", len(clients))


def run_sync(
    clients: list[MinifluxClient],
    gmail_user: str,
    gmail_app_password: str,
    kindle_email: str,
) -> None:
    all_entries = []

    for client in clients:
        try:
            entries = client.get_unread_entries()
            all_entries.extend(entries)
        except Exception as exc:
            logger.error("Failed to fetch feed: %s", exc)

    if not all_entries:
        logger.info("No unread entries, skipping digest")
        return

    logger.info("Fetched %d entries across %d feeds", len(all_entries), len(clients))

    digest_date = date.today().isoformat()
    filename = f'digest-{digest_date}.epub'

    try:
        feed_ids = [c._feed_id for c in clients]
        # Miniflux may rewrite image URLs to its own media proxy, which can live
        # at a private address — exempt it from the public-URL check
        allowed_hosts = {c.hostname for c in clients}
        epub_bytes = build_epub(
            all_entries, digest_date, feed_ids=feed_ids, allowed_hosts=allowed_hosts
        )
    except Exception as exc:
        logger.error("EPUB build failed: %s", exc)
        return

    size_mb = len(epub_bytes) / 1024 / 1024
    logger.info("EPUB size: %.1f MB", size_mb)

    try:
        send_epub(epub_bytes, filename, gmail_user, gmail_app_password, kindle_email)
        logger.info("Sent digest: %s", filename)
    except Exception as exc:
        logger.error("Email send failed, entries not marked read: %s", exc)
        return

    all_ids = [e['id'] for e in all_entries]
    try:
        # All clients share the same API key, so any client can mark entries from any feed
        clients[0].mark_entries_read(all_ids)
        logger.info("Marked %d entries as read", len(all_ids))
    except Exception as exc:
        logger.error("Failed to mark entries as read: %s", exc)
