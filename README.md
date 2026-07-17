# miniflux-to-kindle

Daily RSS digest for your Kindle. Fetches unread entries from selected
[Miniflux](https://miniflux.app) feeds once a day, bundles them into a single
EPUB (with embedded images and a table of contents), and emails it to your
Kindle address via Gmail. Entries are marked as read in Miniflux only after
the email is sent successfully, so nothing is lost if a send fails.

## How it works

A single long-running container:

1. Three minutes before the digest hour, each configured feed is refreshed in
   Miniflux.
2. At the digest hour (in your local timezone, DST-aware), unread entries are
   fetched from each feed (up to 100 per feed per day; anything beyond that
   rolls over to the next digest).
3. Entries are assembled into `digest-YYYY-MM-DD.epub`, ordered by the feed
   order you configured, then by publish date. Images are downloaded (capped
   at 5 MB each), downscaled to at most 1200 px and re-encoded as JPEG when
   that makes them smaller, then embedded; HTML is sanitized (scripts, event
   handlers, unsafe link schemes, and SVG images are stripped).
4. The EPUB is emailed to your Kindle address through Gmail SMTP.
5. On success, all included entries are marked read in Miniflux.

## Requirements

- A Miniflux instance and an [API key](https://miniflux.app/docs/api.html#authentication)
- A Gmail account with an [app password](https://support.google.com/accounts/answer/185833)
  (2FA required)
- Your Kindle's email address, with your Gmail address added to the
  [approved sender list](https://www.amazon.com/hz/mycd/myx#/home/settings/payment)
  ("Manage Your Content and Devices" → Preferences → Personal Document Settings)

## Setup

Create a directory for the deployment with a `docker-compose.yml`:

```yaml
services:
  miniflux-to-kindle:
    build:
      context: /path/to/this/repo
      dockerfile: Dockerfile
    env_file: .env
    restart: unless-stopped
    read_only: true
    tmpfs:
      - /tmp
    security_opt:
      - no-new-privileges:true
    cap_drop:
      - ALL
    mem_limit: 512m
```

Copy [`.env.example`](.env.example) to `.env` next to it, fill in your values,
and restrict it (`chmod 600 .env`), then:

```sh
docker compose up -d --build
```

## Configuration

All configuration is via environment variables.

| Variable | Required | Default | Description |
|---|---|---|---|
| `MINIFLUX_BASE_URL` | yes | — | Base URL of your Miniflux instance |
| `MINIFLUX_API_KEY` | yes | — | Miniflux API key |
| `MINIFLUX_FEED_IDS` | yes | — | Comma-separated feed IDs; digest preserves this order |
| `GMAIL_USER` | yes | — | Gmail address used to send the digest |
| `GMAIL_APP_PASSWORD` | yes | — | Gmail app password |
| `KINDLE_EMAIL` | yes | — | Your Kindle's email address |
| `DIGEST_HOUR` | no | `6` | Hour of day (0–23) to send the digest, in `TIMEZONE` |
| `TIMEZONE` | no | `UTC` | IANA timezone name, e.g. `America/Chicago` |
| `RUN_ON_STARTUP` | no | `true` | Also send a digest immediately when the container starts |
| `HEALTHCHECK_URL` | no | — | [healthchecks.io](https://healthchecks.io) ping URL, e.g. `https://hc-ping.com/<uuid>` |

## Monitoring

If `HEALTHCHECK_URL` is set, each digest cycle pings healthchecks.io: `/start`
when the cycle begins, the bare URL on success (a day with no unread entries
counts as success), and `/fail` with the error message in the request body on
failure. Configure the check with a cron schedule matching `DIGEST_HOUR` in
your `TIMEZONE` (e.g. `0 6 * * *`) and a grace period of ~30 minutes. Failed
sends are retried twice (after 1 and 5 minutes) before the cycle is counted
as failed; entries are never marked read unless the email went out.

Feed IDs are visible in the URL when you open a feed in the Miniflux web UI
(`/feed/123/entries`).

## Security notes

- Image URLs from feed content are only fetched if they resolve to public
  addresses; redirects are validated hop-by-hop (SSRF protection). Your
  Miniflux host is exempted so media-proxy URLs still work on a private
  network.
- Feed HTML is sanitized before embedding: script/style tags, `on*` event
  attributes, unsafe link schemes, and SVG images are removed.
- The container runs as a non-root user; the compose file above additionally
  drops all capabilities and mounts the root filesystem read-only.

## Development

```sh
python3 -m venv venv
venv/bin/pip install -r requirements-dev.txt
venv/bin/python -m pytest tests/
```

[`deploy.sh`](deploy.sh) is the author's personal deploy helper (syncs the
live compose file into the repo, rebuilds, and restarts); it assumes a
specific directory layout and isn't needed to use the project.
