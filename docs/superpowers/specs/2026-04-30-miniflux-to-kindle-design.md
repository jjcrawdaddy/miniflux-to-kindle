# Miniflux → Kindle EPUB Digest — Design Spec

**Date:** 2026-04-30

## Overview

A self-contained Python service running in Docker that fetches unread entries from one or more Miniflux feeds daily, assembles them into a single EPUB digest (flat TOC, sorted by date), and emails it as an attachment to a Kindle email address via Gmail SMTP. After a successful send, all entries are marked as read in Miniflux.

## Architecture

Single Docker container running a long-running Python process. Scheduling is handled in-process using the `schedule` library. Logs go to stdout for capture by `docker logs`.

### Components

- **`miniflux_client.py`** — Copied directly from `fp-to-instapaper`. Fetches unread entries for a given feed ID. Marks a batch of entry IDs as read in a single `PUT /v1/entries` call.
- **`epub_builder.py`** — Takes a flat list of entry dicts (`title`, `url`, `content`, `published`), sorts by `published` ascending, builds an EPUB 3 file with a flat TOC using `ebooklib`. Returns EPUB as bytes.
- **`email_sender.py`** — Takes EPUB bytes and a filename, sends via Gmail SMTP (TLS) with the EPUB as an attachment to the configured Kindle email address.
- **`sync.py`** — Orchestrates one cycle: fetch unread entries from all configured feeds, merge and sort, build EPUB, send email, mark entries as read.
- **`main.py`** — Entry point. Loads and validates config. Initialises `MinifluxClient` per feed. Runs one sync immediately on startup, then schedules daily at the configured hour.

## Data Flow

One sync cycle:

1. For each feed ID in `MINIFLUX_FEED_IDS`: `GET /v1/feeds/{id}/entries?status=unread&limit=100`
   - On failure: log error, skip that feed, continue with others
2. Merge all collected entries into one flat list; sort by `published` ascending
3. If zero entries: log "No unread entries, skipping digest" and exit cycle cleanly
4. Build EPUB with `epub_builder.py` — filename: `digest-YYYY-MM-DD.epub`
5. Send EPUB via Gmail SMTP to `KINDLE_EMAIL`
   - On failure: log error, do NOT mark entries as read (they will be included in next run)
6. Mark all collected entry IDs as read in Miniflux — one batch `PUT /v1/entries` call for all IDs across all feeds

## Configuration

All configuration via environment variables, loaded from a `.env` file in `~/docker/miniflux-to-kindle/`.

| Variable | Description |
|---|---|
| `MINIFLUX_BASE_URL` | Base URL of the Miniflux instance (e.g. `http://localhost:8080`) |
| `MINIFLUX_API_KEY` | Miniflux API key |
| `MINIFLUX_FEED_IDS` | Comma-separated list of feed IDs to include (e.g. `55,12,7`) |
| `GMAIL_USER` | Gmail address used to send (e.g. `you@gmail.com`) |
| `GMAIL_APP_PASSWORD` | Gmail App Password (not the account password) |
| `KINDLE_EMAIL` | Destination Kindle email address |
| `DIGEST_HOUR` | Hour (0–23) to send the daily digest (default: `6`) |

## Error Handling

- **Missing env vars:** Fail fast at startup listing all missing variables.
- **`MINIFLUX_FEED_IDS` unparseable:** Clean `SystemExit` if the value doesn't parse to at least one integer.
- **`DIGEST_HOUR` out of range:** Clean `SystemExit` if not an integer in 0–23.
- **Per-feed fetch failure:** Log and skip that feed; other feeds proceed normally.
- **EPUB build failure:** Log and abort the cycle; entries are not marked read.
- **Email send failure:** Log and do NOT mark entries as read; they will be retried in the next run.
- **All errors** logged to stdout with enough detail to diagnose.

## Project Structure

```
miniflux-to-kindle/           # repo
├── app/
│   ├── main.py
│   ├── sync.py
│   ├── miniflux_client.py
│   ├── epub_builder.py
│   └── email_sender.py
├── Dockerfile
├── requirements.txt
└── .env.example

~/docker/miniflux-to-kindle/  # compose location
├── docker-compose.yml
└── .env
```

## Dependencies

- `requests` — Miniflux API calls
- `ebooklib` — EPUB 3 assembly with TOC
- `schedule` — in-process daily scheduling

Email delivery uses Python's built-in `smtplib` and `email` modules — no extra library needed.

## Docker

- Base image: `python:3.12-slim`
- `docker-compose.yml` and `.env` live in `~/docker/miniflux-to-kindle/`
- The repo carries `.env.example` only — the real `.env` is never committed
- Container restarts automatically (`restart: unless-stopped`)

## Out of Scope (this iteration)

- Per-feed EPUB sections or grouping
- EPUB styling / custom CSS
- Delivery via anything other than Gmail SMTP
- Multiple recipient addresses
- Retry backoff for email failures
