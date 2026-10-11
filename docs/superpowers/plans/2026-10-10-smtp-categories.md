# Miniflux → Kindle: SMTP + Categories Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add generic SMTP delivery (STARTTLS/SSL/none, configurable host/port/credentials/from) and Miniflux category support (fetch entries by category, group the EPUB by category with a hierarchical TOC), while keeping the Gmail env vars working as a default.

**Architecture:** No new modules. Extend `config.py`, `email_sender.py`, `miniflux_client.py`, `sync.py`, and `epub_builder.py`. Add a `test` build stage to the Dockerfile for in-container pytest.

---

## File Map

| File | Change |
|---|---|
| `app/config.py` | Add `SmtpConfig`; add `category_ids`; parse/validate SMTP + category env vars |
| `app/email_sender.py` | Parameterize transport (host/port/security/from); optional login |
| `app/miniflux_client.py` | Add `get_category_entries`, `refresh_category` |
| `app/sync.py` | Refresh/fetch feeds + categories; dedupe; pass new args |
| `app/epub_builder.py` | Group by category; section headers; hierarchical TOC |
| `tests/*` | Update/add unit tests for every change |
| `Dockerfile` | Add `test` build stage |
| `.env.example` | Document new vars |
| `README.md` | Document SMTP, categories, and the `test` build stage |
| `docs/superpowers/specs/2026-10-10-smtp-categories-design.md` | Design spec (done) |
| `docs/superpowers/plans/2026-10-10-smtp-categories.md` | This plan |

---

## Task 1: Config — `SmtpConfig` + `category_ids`

**Files:** `app/config.py`, `tests/test_main.py`

- [ ] Add frozen `SmtpConfig` dataclass (`host`, `port`, `user`, `password`, `from_address`, `security`, `timeout=300`).
- [ ] Add `category_ids: tuple[int, ...]` and `smtp: SmtpConfig` to `Config`.
- [ ] Make `MINIFLUX_FEED_IDS` optional; require at least one of feeds/categories.
- [ ] Parse `MINIFLUX_CATEGORY_IDS` with the same int-tuple helper as feeds.
- [ ] Parse `SMTP_*` with Gmail fallbacks (`SMTP_HOST` default `smtp.gmail.com`, `SMTP_PORT` default `587`, `SMTP_USER`←`GMAIL_USER`, `SMTP_PASSWORD`←`GMAIL_APP_PASSWORD`, `SMTP_FROM`←`SMTP_USER`, `SMTP_SECURITY` default `starttls`).
- [ ] Validate port (1–65535) and security ∈ {starttls, ssl, none}; fail fast on invalid.
- [ ] Update `test_main.py`: new env parsing, fallbacks, at-least-one-source rule, invalid port/security.

## Task 2: Generic SMTP sender

**Files:** `app/email_sender.py`, `tests/test_email_sender.py`

- [ ] Change signature to `send_epub(epub_bytes, filename, smtp: SmtpConfig, kindle_email: str)`.
- [ ] Branch on `security`: `ssl`→`smtplib.SMTP_SSL`, `starttls`→`SMTP`+`starttls`, `none`→`SMTP`.
- [ ] Use `smtp.from_address` for From + envelope; skip `login` when user/password empty.
- [ ] Keep retry/backoff (`RETRY_DELAYS`) and no-retry-on-auth-failure; use `smtp.timeout`.
- [ ] Rewrite `test_email_sender.py` for the new signature + security modes.

## Task 3: Miniflux category methods

**Files:** `app/miniflux_client.py`, `tests/test_miniflux_client.py`

- [ ] `get_category_entries(category_id)` → `GET /v1/categories/{id}/entries?status=unread&limit=100`.
- [ ] `refresh_category(category_id)` → `PUT /v1/categories/{id}/refresh`.
- [ ] Add endpoint/param assertions in `test_miniflux_client.py`.

## Task 4: Sync feeds + categories

**Files:** `app/sync.py`, `tests/test_sync.py`

- [ ] `refresh_feeds` also refreshes each `category_id`.
- [ ] `run_sync` fetches from `feed_ids` and `category_ids`; dedupe by entry `id`.
- [ ] Pass `category_ids` and `feed_ids` to `build_epub`; send via `config.smtp`.
- [ ] Update `test_sync.py` accordingly.

## Task 5: EPUB grouping + hierarchical TOC

**Files:** `app/epub_builder.py`, `tests/test_epub_builder.py`

- [ ] Group entries by `entry['feed']['category']` (fallback "Uncategorized").
- [ ] Order categories: `category_ids` order → explicit `feed_ids` categories → remaining alphabetical.
- [ ] Within category: sort by `feed_ids` order then `published_at`.
- [ ] Emit a section-header chapter per category; build `book.toc` as `[(epub.Section, [links...]), ...]`.
- [ ] Update/add grouping + TOC tests.

## Task 6: Docker test stage + docs

**Files:** `Dockerfile`, `README.md`, `.env.example`

- [ ] Add `FROM python:3.13-slim AS test` stage running `pytest tests/ -v`.
- [ ] Update `.env.example` with `SMTP_*` + `MINIFLUX_CATEGORY_IDS`.
- [ ] Update `README.md` (SMTP, categories, and the `test` build stage).

## Verification

```bash
venv/bin/python -m pytest tests/
docker build --target test -t miniflux-to-kindle:test . && docker run --rm miniflux-to-kindle:test
docker compose -f docker-compose.yml.example config
```
