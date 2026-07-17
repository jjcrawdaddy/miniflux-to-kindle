import os
from dataclasses import dataclass
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

REQUIRED_VARS = [
    'MINIFLUX_BASE_URL',
    'MINIFLUX_API_KEY',
    'MINIFLUX_FEED_IDS',
    'GMAIL_USER',
    'GMAIL_APP_PASSWORD',
    'KINDLE_EMAIL',
]


@dataclass(frozen=True)
class Config:
    miniflux_base_url: str
    miniflux_api_key: str
    feed_ids: tuple[int, ...]
    gmail_user: str
    gmail_app_password: str
    kindle_email: str
    digest_hour: int
    timezone: str
    run_on_startup: bool = True
    healthcheck_url: str | None = None


def load_config() -> Config:
    missing = [v for v in REQUIRED_VARS if not os.environ.get(v)]
    if missing:
        raise SystemExit(f"Missing required environment variables: {', '.join(missing)}")

    feed_ids_str = os.environ['MINIFLUX_FEED_IDS']
    try:
        feed_ids = tuple(int(x.strip()) for x in feed_ids_str.split(',') if x.strip())
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

    run_on_startup_str = os.environ.get('RUN_ON_STARTUP', 'true').lower()
    if run_on_startup_str in ('true', '1', 'yes'):
        run_on_startup = True
    elif run_on_startup_str in ('false', '0', 'no'):
        run_on_startup = False
    else:
        raise SystemExit(f"RUN_ON_STARTUP must be true or false, got: {run_on_startup_str!r}")

    return Config(
        miniflux_base_url=os.environ['MINIFLUX_BASE_URL'],
        miniflux_api_key=os.environ['MINIFLUX_API_KEY'],
        feed_ids=feed_ids,
        gmail_user=os.environ['GMAIL_USER'],
        gmail_app_password=os.environ['GMAIL_APP_PASSWORD'],
        kindle_email=os.environ['KINDLE_EMAIL'],
        digest_hour=digest_hour,
        timezone=timezone_str,
        run_on_startup=run_on_startup,
        healthcheck_url=os.environ.get('HEALTHCHECK_URL', '').rstrip('/') or None,
    )
