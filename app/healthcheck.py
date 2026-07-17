import logging

import requests

logger = logging.getLogger(__name__)

PING_TIMEOUT = 10


def ping(url: str | None, endpoint: str = '', message: str = '') -> None:
    """Fire-and-forget ping to a healthchecks.io check; never raises."""
    if not url:
        return
    try:
        requests.post(url + endpoint, data=message, timeout=PING_TIMEOUT)
    except Exception as exc:
        logger.warning("Healthcheck ping%s failed: %s", endpoint, exc)
