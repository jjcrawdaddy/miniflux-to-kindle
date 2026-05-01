import logging
import os
import time
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import schedule

from miniflux_client import MinifluxClient
from sync import refresh_feeds, run_sync

logger = logging.getLogger(__name__)

REQUIRED_VARS = [
    'MINIFLUX_BASE_URL',
    'MINIFLUX_API_KEY',
    'MINIFLUX_FEED_IDS',
    'GMAIL_USER',
    'GMAIL_APP_PASSWORD',
    'KINDLE_EMAIL',
]


def load_config() -> dict:
    missing = [v for v in REQUIRED_VARS if not os.environ.get(v)]
    if missing:
        raise SystemExit(f"Missing required environment variables: {', '.join(missing)}")

    feed_ids_str = os.environ['MINIFLUX_FEED_IDS']
    try:
        feed_ids = [int(x.strip()) for x in feed_ids_str.split(',') if x.strip()]
        if not feed_ids:
            raise ValueError('empty')
    except ValueError:
        raise SystemExit(f"MINIFLUX_FEED_IDS must be comma-separated integers, got: {feed_ids_str!r}")

    digest_hour_str = os.environ.get('DIGEST_HOUR', '6')
    try:
        digest_hour = int(digest_hour_str)
        if not 0 <= digest_hour <= 23:
            raise ValueError('out of range')
    except ValueError:
        raise SystemExit(f"DIGEST_HOUR must be an integer 0–23, got: {digest_hour_str!r}")

    timezone_str = os.environ.get('TIMEZONE', 'UTC')
    try:
        ZoneInfo(timezone_str)
    except (KeyError, ZoneInfoNotFoundError):
        raise SystemExit(f"TIMEZONE is not a valid IANA timezone: {timezone_str!r}")

    return {
        'miniflux_base_url': os.environ['MINIFLUX_BASE_URL'],
        'miniflux_api_key': os.environ['MINIFLUX_API_KEY'],
        'feed_ids': feed_ids,
        'gmail_user': os.environ['GMAIL_USER'],
        'gmail_app_password': os.environ['GMAIL_APP_PASSWORD'],
        'kindle_email': os.environ['KINDLE_EMAIL'],
        'digest_hour': digest_hour,
        'timezone': timezone_str,
    }


def main() -> None:
    logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
    config = load_config()

    clients = [
        MinifluxClient(config['miniflux_base_url'], config['miniflux_api_key'], fid)
        for fid in config['feed_ids']
    ]

    tz = ZoneInfo(config['timezone'])
    local_digest = datetime.now(tz).replace(
        hour=config['digest_hour'], minute=0, second=0, microsecond=0
    )
    utc_digest = local_digest.astimezone(ZoneInfo('UTC'))
    utc_refresh = utc_digest - timedelta(minutes=3)
    digest_time_str = utc_digest.strftime('%H:%M')
    refresh_time_str = utc_refresh.strftime('%H:%M')

    def job() -> None:
        logger.info("Sync started")
        try:
            run_sync(
                clients,
                config['gmail_user'],
                config['gmail_app_password'],
                config['kindle_email'],
            )
        except Exception as exc:
            logger.error("Sync cycle failed: %s", exc)
        logger.info("Sync finished")

    job()
    schedule.every().day.at(refresh_time_str).do(lambda: refresh_feeds(clients))
    schedule.every().day.at(digest_time_str).do(job)
    logger.info(
        "Scheduler running — digest at %02d:00 %s (%s UTC), refresh at %s UTC",
        config['digest_hour'], config['timezone'], digest_time_str, refresh_time_str
    )

    while True:
        schedule.run_pending()
        time.sleep(60)


if __name__ == '__main__':
    main()
