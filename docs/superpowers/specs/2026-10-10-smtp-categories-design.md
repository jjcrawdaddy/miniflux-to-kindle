# Miniflux → Kindle: Generic SMTP + Categories — Design Spec

**Date:** 2026-10-10

## Overview

Two additions to the existing daily digest service:

1. **Generic SMTP delivery.** Replace the hardcoded Gmail transport with a
   configurable SMTP client supporting STARTTLS, implicit SSL, and plaintext
   relays, while keeping the Gmail env vars as a convenience default.
2. **Category support.** Allow feeds to be selected by Miniflux category in
   addition to (or instead of) explicit feed IDs, and group the resulting EPUB
   digest into category sections with a hierarchical table of contents.

This supersedes the "Out of Scope" items in
`2026-04-30-miniflux-to-kindle-design.md` (non-Gmail delivery and per-feed/
per-category EPUB grouping).

## Architecture

No structural changes to the long-running process model. The existing modules
gain responsibilities:

- **`config.py`** — new `SmtpConfig` dataclass and `category_ids` field; SMTP
  env parsing with Gmail fallbacks.
- **`email_sender.py`** — transport is now parameterized (host/port/security/
  credentials/from-address) instead of hardcoded to `smtp.gmail.com:587`.
- **`miniflux_client.py`** — two new methods for category entries and category
  refresh.
- **`sync.py`** — refreshes and fetches from feeds *and* categories, deduplicating
  entries that appear in both.
- **`epub_builder.py`** — groups entries by category and emits a two-level TOC.

## Data Flow

One sync cycle (changes from the original flow in **bold**):

1. Three minutes before the digest hour, refresh each configured feed
   **and each configured category**.
2. At the digest hour, fetch unread entries from each feed **and each category**
   (up to 100 each). **Entries are deduplicated by `id`** because a feed may be
   listed both directly and via a category.
3. Merge into one list and group by the entry's category (from
   `entry.feed.category`, falling back to "Uncategorized").
4. Build `digest-YYYY-MM-DD.epub`: one section header chapter per category,
   then one chapter per article, ordered by category (config order, then
   alphabetical for the rest) and, within a category, by feed order then
   publish date. TOC is hierarchical: category → articles.
5. Email the EPUB via the configured SMTP server.
6. On success, mark all included entry IDs as read in Miniflux (a single
   `PUT /v1/entries` call works across feeds and categories), unless
   `MARK_AS_READ=false`.

## Configuration

| Variable | Required | Default | Description |
|---|---|---|---|
| `MINIFLUX_BASE_URL` | yes | — | Base URL of the Miniflux instance |
| `MINIFLUX_API_KEY` | yes | — | Miniflux API key |
| `MINIFLUX_FEED_IDS` | no | — | Comma-separated feed IDs (at least one of this or `MINIFLUX_CATEGORY_IDS`) |
| `MINIFLUX_CATEGORY_IDS` | no | — | Comma-separated category IDs |
| `SMTP_HOST` | no | `smtp.gmail.com` | SMTP server hostname |
| `SMTP_PORT` | no | `587` | SMTP port |
| `SMTP_USER` | no | `GMAIL_USER` | SMTP login username |
| `SMTP_PASSWORD` | no | `GMAIL_APP_PASSWORD` | SMTP login password |
| `SMTP_FROM` | no | `SMTP_USER` | From/envelope sender address |
| `SMTP_SECURITY` | no | `starttls` | `starttls`, `ssl`, or `none` |
| `SMTP_ATTACHMENT_MIME` | no | `application/epub+zip` | MIME types to try for the attachment, in order |
| `GMAIL_USER` | no | — | Legacy; supplies `SMTP_USER` default |
| `GMAIL_APP_PASSWORD` | no | — | Legacy; supplies `SMTP_PASSWORD` default |
| `KINDLE_EMAIL` | yes | — | Destination Kindle email address |
| `DIGEST_HOUR` | no | `6` | Hour (0–23) in `TIMEZONE` |
| `TIMEZONE` | no | `UTC` | IANA timezone name |
| `RUN_ON_STARTUP` | no | `true` | Send immediately on startup |
| `MARK_AS_READ` | no | `true` | Mark entries read after a successful send |
| `HEALTHCHECK_URL` | no | — | healthchecks.io ping URL |

SMTP credentials are effectively required: `SMTP_USER` and `SMTP_PASSWORD`
must be set, either directly or via the `GMAIL_*` fallbacks. Login is skipped
only if both are empty (to support open local relays).

## Error Handling

- **No sources configured** (`MINIFLUX_FEED_IDS` and `MINIFLUX_CATEGORY_IDS`
  both empty/unset): fail fast at startup.
- **Invalid SMTP port or security mode:** fail fast at startup.
- **Per-source fetch/refresh failure:** log and skip; other sources proceed.
- **EPUB build / email send failure:** abort cycle without marking read.
- **Duplicate entries across sources:** deduplicated before building.

## Out of Scope

- Per-category EPUB *files* (one file per category); still a single EPUB.
- Custom SMTP auth mechanisms (OAuth, API-key headers).
- Multiple recipient addresses.

## Dependencies

No new dependencies. `smtplib`/`ssl`/`email` (stdlib) cover generic SMTP; the
existing `requests`, `ebooklib`, `schedule`, `pytz`, `beautifulsoup4`, and
`Pillow` stack is unchanged.

## Docker

The Dockerfile gains a `test` build stage so the pytest suite runs inside the
same base image without polluting the production stage.
