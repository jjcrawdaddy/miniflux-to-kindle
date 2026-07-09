import logging
import time
from datetime import datetime, timedelta
from typing import Callable

import schedule

from config import Config, load_config
from miniflux_client import MinifluxClient
from sync import refresh_feeds, run_sync

logger = logging.getLogger(__name__)


def compute_schedule_times(digest_hour: int) -> tuple[str, str]:
    digest = datetime(2000, 1, 1, digest_hour)
    refresh = digest - timedelta(minutes=3)
    return digest.strftime('%H:%M'), refresh.strftime('%H:%M')


def setup_schedule(config: Config, client: MinifluxClient, job: Callable[[], None]) -> None:
    # Scheduling in the configured timezone (not a one-time UTC conversion)
    # keeps the digest at the same local hour across DST transitions
    digest_time, refresh_time = compute_schedule_times(config.digest_hour)
    schedule.every().day.at(refresh_time, config.timezone).do(
        lambda: refresh_feeds(client, config.feed_ids)
    )
    schedule.every().day.at(digest_time, config.timezone).do(job)
    logger.info(
        "Scheduler running — digest at %s %s, refresh at %s %s",
        digest_time, config.timezone, refresh_time, config.timezone
    )


def main() -> None:
    logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
    config = load_config()

    client = MinifluxClient(config.miniflux_base_url, config.miniflux_api_key)

    def job() -> None:
        logger.info("Sync started")
        try:
            run_sync(client, config)
        except Exception as exc:
            logger.error("Sync cycle failed: %s", exc)
        logger.info("Sync finished")

    if config.run_on_startup:
        job()
    setup_schedule(config, client, job)

    while True:
        schedule.run_pending()
        time.sleep(60)


if __name__ == '__main__':
    main()
