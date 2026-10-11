# miniflux-to-kindle

Daily RSS digest for your Kindle. Fetches unread entries from selected
[Miniflux](https://miniflux.app) feeds (or whole categories) once a day,
bundles them into a single EPUB (grouped by category, with embedded images and
a table of contents), and emails it to your Kindle address over SMTP (Gmail or
any other provider). Entries are marked as read in Miniflux only after the
email is sent successfully, so nothing is lost if a send fails.

## How it works

A single long-running container:

1. Three minutes before the digest hour, each configured feed is refreshed in
   Miniflux.
2. At the digest hour (in your local timezone, DST-aware), unread entries that
   were published on the previous calendar day (midnight-to-midnight in
   `TIMEZONE`) are fetched from each configured feed and category (up to 100
   per source; anything beyond that rolls over to the next digest). Entries
   that appear in both a feed and a category are deduplicated. Older unread
   entries are intentionally skipped, so the digest never backfills.
3. Entries are assembled into `miniflux-<categories>-YYYY-MM-DD.epub`, grouped by category
   (one section header per category, with a hierarchical table of contents)
   and ordered by your configured source order, then by publish date. Images
   are downloaded (capped at 5 MB each), downscaled to at most 1200 px and
   re-encoded as JPEG when that makes them smaller, then embedded. Formats the
   Kindle can't render (WebP, BMP, …) are always converted to JPEG; HTML is
   sanitized (scripts, event handlers, and unsafe link schemes are stripped).
   Audio, video, embedded players, and SVG images are replaced with visible
   Kindle compatibility notes linking to the original media or article when
   available, so you can see what was omitted.
4. The EPUB is emailed to your Kindle address over SMTP (see Configuration).
5. On success, all included entries are marked read in Miniflux (unless
   `MARK_AS_READ=false`).

## Requirements

- A Miniflux instance and an [API key](https://miniflux.app/docs/api.html#authentication)
- SMTP credentials for the account that sends the digest. For Gmail use an
  [app password](https://support.google.com/accounts/answer/185833) (2FA required);
  any other SMTP provider works via the `SMTP_*` variables.
- Your Kindle's email address, with your sender address added to the
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
| `MINIFLUX_FEED_IDS` | no | — | Comma-separated feed IDs; at least one of this or `MINIFLUX_CATEGORY_IDS` |
| `MINIFLUX_CATEGORY_IDS` | no | — | Comma-separated category IDs; digest is grouped by these categories |
| `SMTP_HOST` | no | `smtp.gmail.com` | SMTP server hostname |
| `SMTP_PORT` | no | `587` | SMTP port |
| `SMTP_USER` | no | `GMAIL_USER` | SMTP login username |
| `SMTP_PASSWORD` | no | `GMAIL_APP_PASSWORD` | SMTP login password |
| `SMTP_FROM` | no | `SMTP_USER` | From/envelope sender address (must be Kindle-approved) |
| `SMTP_SECURITY` | no | `starttls` | `starttls`, `ssl`, or `none` |
| `SMTP_ATTACHMENT_MIME` | no | `application/epub+zip` | Comma-separated MIME types to try for the attachment, in order |
| `GMAIL_USER` | no | — | Legacy; supplies `SMTP_USER` default |
| `GMAIL_APP_PASSWORD` | no | — | Legacy; supplies `SMTP_PASSWORD` default |
| `KINDLE_EMAIL` | yes | — | Your Kindle's email address |
| `DIGEST_HOUR` | no | `6` | Hour of day (0–23) to send the digest, in `TIMEZONE` |
| `TIMEZONE` | no | `UTC` | IANA timezone name, e.g. `America/Chicago` |
| `RUN_ON_STARTUP` | no | `true` | Also send a digest immediately when the container starts |
| `MARK_AS_READ` | no | `true` | Mark included entries as read in Miniflux after a successful send |
| `HEALTHCHECK_URL` | no | — | [healthchecks.io](https://healthchecks.io) ping URL, e.g. `https://hc-ping.com/<uuid>` |

SMTP credentials are required (`SMTP_USER` + `SMTP_PASSWORD`, either directly
or via the `GMAIL_*` fallbacks). `SMTP_SECURITY` selects the connection type:
`starttls` (plaintext then upgrade), `ssl` (implicit TLS, usually port 465), or
`none` (no encryption — only for local relays).

Some SMTP relays restrict attachment MIME types. Scaleway TEM, for example,
rejects `application/epub+zip` with a 501. `SMTP_ATTACHMENT_MIME` lets you list
fallback types (e.g. `application/epub+zip,application/xml`) that are tried in
order when the relay rejects the current type; the `.epub` filename is kept so
the Kindle still identifies the file by extension.

## Monitoring

If `HEALTHCHECK_URL` is set, each digest cycle pings healthchecks.io: `/start`
when the cycle begins, the bare URL on success (a day with no unread entries
counts as success), and `/fail` with the error message in the request body on
failure. Configure the check with a cron schedule matching `DIGEST_HOUR` in
your `TIMEZONE` (e.g. `0 6 * * *`) and a grace period of ~30 minutes. Failed
sends are retried twice (after 1 and 5 minutes) before the cycle is counted
as failed; entries are never marked read unless the email went out.

Feed IDs are visible in the URL when you open a feed in the Miniflux web UI
(`/feed/123/entries`); category IDs appear in `/category/7/entries`.

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

Run the tests locally:

```sh
python3 -m venv venv
venv/bin/pip install -r requirements-dev.txt
venv/bin/python -m pytest tests/
```

Or in a container (the Dockerfile has a `test` build stage):

```sh
docker build --target test -t miniflux-to-kindle:test .
docker run --rm miniflux-to-kindle:test
```

To build the production image:

```sh
docker build -t miniflux-to-kindle .
```

[`deploy.sh`](deploy.sh) is the author's personal deploy helper (syncs the
live compose file into the repo, rebuilds, and restarts); it assumes a
specific directory layout and isn't needed to use the project.
