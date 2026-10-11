import os
from dataclasses import dataclass
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

REQUIRED_VARS = [
    'MINIFLUX_BASE_URL',
    'MINIFLUX_API_KEY',
    'KINDLE_EMAIL',
]

SMTP_SECURITIES = ('starttls', 'ssl', 'none')


@dataclass(frozen=True)
class SmtpConfig:
    host: str
    port: int
    user: str
    password: str
    from_address: str
    security: str
    timeout: int = 300
    attachment_mime: tuple[str, ...] = ('application/epub+zip',)


@dataclass(frozen=True)
class Config:
    miniflux_base_url: str
    miniflux_api_key: str
    feed_ids: tuple[int, ...]
    category_ids: tuple[int, ...]
    smtp: SmtpConfig
    kindle_email: str
    digest_hour: int
    timezone: str
    run_on_startup: bool = True
    mark_as_read: bool = True
    healthcheck_url: str | None = None


def _parse_bool(name: str, default: str = 'true') -> bool:
    value = os.environ.get(name, default).lower()
    if value in ('true', '1', 'yes'):
        return True
    if value in ('false', '0', 'no'):
        return False
    raise SystemExit(f"{name} must be true or false, got: {value!r}")


def _parse_int_tuple(value: str, name: str) -> tuple[int, ...]:
    value = value.strip()
    if not value:
        return ()
    try:
        ids = tuple(int(x.strip()) for x in value.split(',') if x.strip())
        if not ids:
            raise ValueError('empty')
    except ValueError:
        raise SystemExit(f"{name} must be comma-separated integers, got: {value!r}")
    return ids


def _parse_smtp() -> SmtpConfig:
    host = os.environ.get('SMTP_HOST', 'smtp.gmail.com') or 'smtp.gmail.com'

    port_str = os.environ.get('SMTP_PORT', '587')
    try:
        port = int(port_str)
        if not 1 <= port <= 65535:
            raise ValueError('out of range')
    except ValueError:
        raise SystemExit(f"SMTP_PORT must be an integer 1–65535, got: {port_str!r}")

    user = os.environ.get('SMTP_USER') or os.environ.get('GMAIL_USER', '')
    password = os.environ.get('SMTP_PASSWORD') or os.environ.get('GMAIL_APP_PASSWORD', '')

    from_address = os.environ.get('SMTP_FROM', '') or user

    security = os.environ.get('SMTP_SECURITY', 'starttls').lower()
    if security not in SMTP_SECURITIES:
        raise SystemExit(
            f"SMTP_SECURITY must be one of {', '.join(SMTP_SECURITIES)}, got: {security!r}"
        )

    mime_str = os.environ.get('SMTP_ATTACHMENT_MIME', 'application/epub+zip')
    attachment_mime = tuple(m.strip() for m in mime_str.split(',') if m.strip())
    if not attachment_mime:
        raise SystemExit(f"SMTP_ATTACHMENT_MIME must not be empty, got: {mime_str!r}")
    for mime in attachment_mime:
        if '/' not in mime or not mime.split('/', 1)[1]:
            raise SystemExit(
                f"SMTP_ATTACHMENT_MIME entries must look like 'type/subtype', got: {mime!r}"
            )

    return SmtpConfig(
        host=host,
        port=port,
        user=user,
        password=password,
        from_address=from_address,
        security=security,
        attachment_mime=attachment_mime,
    )


def load_config() -> Config:
    missing = [v for v in REQUIRED_VARS if not os.environ.get(v)]
    if missing:
        raise SystemExit(f"Missing required environment variables: {', '.join(missing)}")

    feed_ids = _parse_int_tuple(
        os.environ.get('MINIFLUX_FEED_IDS', ''), 'MINIFLUX_FEED_IDS'
    )
    category_ids = _parse_int_tuple(
        os.environ.get('MINIFLUX_CATEGORY_IDS', ''), 'MINIFLUX_CATEGORY_IDS'
    )
    if not feed_ids and not category_ids:
        raise SystemExit(
            "At least one of MINIFLUX_FEED_IDS or MINIFLUX_CATEGORY_IDS must be set"
        )

    smtp = _parse_smtp()
    if not smtp.user or not smtp.password:
        raise SystemExit(
            "SMTP credentials are required (set SMTP_USER/SMTP_PASSWORD or "
            "GMAIL_USER/GMAIL_APP_PASSWORD)"
        )

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

    run_on_startup = _parse_bool('RUN_ON_STARTUP')
    mark_as_read = _parse_bool('MARK_AS_READ')

    return Config(
        miniflux_base_url=os.environ['MINIFLUX_BASE_URL'],
        miniflux_api_key=os.environ['MINIFLUX_API_KEY'],
        feed_ids=feed_ids,
        category_ids=category_ids,
        smtp=smtp,
        kindle_email=os.environ['KINDLE_EMAIL'],
        digest_hour=digest_hour,
        timezone=timezone_str,
        run_on_startup=run_on_startup,
        mark_as_read=mark_as_read,
        healthcheck_url=os.environ.get('HEALTHCHECK_URL', '').rstrip('/') or None,
    )
