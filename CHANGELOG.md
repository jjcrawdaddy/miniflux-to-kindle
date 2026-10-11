# Changelog

## 2026-10-11 — Generic SMTP, categories, and previous-day digest

### Added
- Generic SMTP delivery (STARTTLS/SSL/none, host/port/credentials/from,
  attachment MIME fallback list for relays that reject `application/epub+zip`).
- Category support: fetch by category, refresh categories, dedupe feed↔category
  overlap, EPUB grouped into category sections with a hierarchical TOC.
- `SMTP_*` and `MINIFLUX_CATEGORY_IDS` config (`GMAIL_*` kept as fallbacks).
- `TIMEZONE`-aware, DST-safe scheduling and digest date.
- healthchecks.io monitoring (`/start`, success, `/fail`) + Docker `HEALTHCHECK`.
- Docker `test` stage for in-container pytest; container hardening.

### Changed
- Digest now includes only the previous calendar day's articles
  (server-side `published_after`/`published_before`).
- EPUB filename now includes category slugs (`miniflux-<categories>-YYYY-MM-DD.epub`).

### Fixed
- WebP/BMP images (unsupported on Kindle) are always converted to JPEG, and
  dropped if conversion fails.

### Notes / gotchas
- `MARK_AS_READ=false` leaves everything unread, so the backlog grows unbounded
  (a single category reached ~12k unread). Flip to `true` when done testing.
- With the previous-day window, entries from a failed send are not retried the
  next run (they fall outside the window). In-cycle retries (1 min, 5 min) still apply.
- One feed entry's `content` isn't HTML; it renders empty (harmless warning).
