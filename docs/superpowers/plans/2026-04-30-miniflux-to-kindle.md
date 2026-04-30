# Miniflux → Kindle EPUB Digest Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a Python service that fetches unread entries from one or more Miniflux feeds, assembles them into a daily EPUB digest, and emails it to a Kindle address via Gmail SMTP.

**Architecture:** Single long-running Python process using `schedule` for a daily run at a configured hour. Five modules: Miniflux API wrapper (copied from fp-to-instapaper), EPUB builder, email sender, sync orchestrator, entry point. Each entry becomes one chapter in a flat-TOC EPUB sorted by publication date.

**Tech Stack:** Python 3.12, `requests`, `ebooklib` (EPUB 3), `schedule`, `smtplib` (stdlib), pytest, Docker Compose.

---

## File Map

| File | Responsibility |
|---|---|
| `app/miniflux_client.py` | Miniflux API: fetch unread entries per feed, mark entries read |
| `app/epub_builder.py` | Build EPUB 3 from sorted entry list, return bytes |
| `app/email_sender.py` | Send EPUB bytes as attachment via Gmail SMTP |
| `app/sync.py` | Orchestrate one cycle: fetch → build EPUB → send → mark read |
| `app/main.py` | Config validation, client init, scheduler loop |
| `tests/conftest.py` | Add `app/` to sys.path |
| `tests/test_miniflux_client.py` | Unit tests for MinifluxClient |
| `tests/test_epub_builder.py` | Integration tests: build real EPUB, inspect ZIP contents |
| `tests/test_email_sender.py` | Unit tests with mocked smtplib.SMTP |
| `tests/test_sync.py` | Unit tests with mocked components |
| `tests/test_main.py` | Unit tests for load_config |
| `Dockerfile` | python:3.12-slim image |
| `requirements.txt` | Production deps |
| `requirements-dev.txt` | pytest for local dev |
| `.env.example` | Template for all 7 env vars |
| `~/docker/miniflux-to-kindle/docker-compose.yml` | Compose config |

---

## Task 1: Project Scaffold

**Files:**
- Create: `app/miniflux_client.py` (stub)
- Create: `app/epub_builder.py` (stub)
- Create: `app/email_sender.py` (stub)
- Create: `app/sync.py` (stub)
- Create: `app/main.py` (stub)
- Create: `tests/conftest.py`
- Create: `requirements.txt`
- Create: `requirements-dev.txt`
- Create: `.env.example`
- Create: `.gitignore`

- [ ] **Step 1: Create directories**

```bash
mkdir -p app tests
```

- [ ] **Step 2: Create stub files**

`app/miniflux_client.py`:
```python
import requests


class MinifluxClient:
    pass
```

`app/epub_builder.py`:
```python
import io
import os
import tempfile
from datetime import datetime
from ebooklib import epub


def build_epub(entries: list[dict], digest_date: str) -> bytes:
    pass
```

`app/email_sender.py`:
```python
import smtplib
from email import encoders
from email.mime.base import MIMEBase
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText


def send_epub(
    epub_bytes: bytes,
    filename: str,
    gmail_user: str,
    gmail_app_password: str,
    kindle_email: str,
) -> None:
    pass
```

`app/sync.py`:
```python
import logging
from datetime import date

from epub_builder import build_epub
from email_sender import send_epub
from miniflux_client import MinifluxClient

logger = logging.getLogger(__name__)
```

`app/main.py`:
```python
import logging
import os
import time

import schedule

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
logger = logging.getLogger(__name__)
```

- [ ] **Step 3: Create conftest.py**

`tests/conftest.py`:
```python
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'app'))
```

- [ ] **Step 4: Create requirements.txt**

```
requests==2.32.3
ebooklib==0.18
schedule==1.2.2
```

- [ ] **Step 5: Create requirements-dev.txt**

```
-r requirements.txt
pytest==8.3.5
```

- [ ] **Step 6: Create .env.example**

```
MINIFLUX_BASE_URL=http://localhost:8080
MINIFLUX_API_KEY=your-miniflux-api-key
MINIFLUX_FEED_IDS=55,12,7
GMAIL_USER=you@gmail.com
GMAIL_APP_PASSWORD=your-gmail-app-password
KINDLE_EMAIL=you@kindle.com
DIGEST_HOUR=6
```

- [ ] **Step 7: Create .gitignore**

```
__pycache__/
*.pyc
*.pyo
.pytest_cache/
venv/
.env
```

- [ ] **Step 8: Install dev dependencies and verify pytest**

```bash
python3 -m venv venv && source venv/bin/activate && pip install -r requirements-dev.txt
pytest tests/ --collect-only
```

Expected: no errors (no tests yet)

- [ ] **Step 9: Commit**

```bash
git add app/ tests/ requirements.txt requirements-dev.txt .env.example .gitignore
git commit -m "feat: project scaffold with stubs and test infrastructure"
```

---

## Task 2: MinifluxClient

**Files:**
- Modify: `app/miniflux_client.py`
- Create: `tests/test_miniflux_client.py`

Identical implementation to `fp-to-instapaper`. Uses `requests.Session` with `X-Auth-Token` header. Two public methods.

- [ ] **Step 1: Write failing tests**

`tests/test_miniflux_client.py`:
```python
from unittest.mock import MagicMock

from miniflux_client import MinifluxClient


def make_client():
    return MinifluxClient('http://localhost:8080', 'test-key', 55)


def test_get_unread_entries_returns_entries():
    client = make_client()
    mock_resp = MagicMock()
    mock_resp.json.return_value = {
        'total': 2,
        'entries': [
            {'id': 1, 'title': 'A1', 'url': 'http://ex.com/1', 'content': '<p>One</p>',
             'published_at': '2026-04-30T08:00:00+00:00'},
            {'id': 2, 'title': 'A2', 'url': 'http://ex.com/2', 'content': '<p>Two</p>',
             'published_at': '2026-04-30T09:00:00+00:00'},
        ]
    }
    client.session.get = MagicMock(return_value=mock_resp)

    entries = client.get_unread_entries()

    client.session.get.assert_called_once_with(
        'http://localhost:8080/v1/feeds/55/entries',
        params={'status': 'unread', 'limit': 100}
    )
    assert len(entries) == 2
    assert entries[0]['id'] == 1
    mock_resp.raise_for_status.assert_called_once()


def test_get_unread_entries_returns_empty_list_when_none():
    client = make_client()
    mock_resp = MagicMock()
    mock_resp.json.return_value = {'total': 0, 'entries': []}
    client.session.get = MagicMock(return_value=mock_resp)

    assert client.get_unread_entries() == []


def test_get_unread_entries_strips_trailing_slash():
    client = MinifluxClient('http://localhost:8080/', 'test-key', 55)
    mock_resp = MagicMock()
    mock_resp.json.return_value = {'total': 0, 'entries': []}
    client.session.get = MagicMock(return_value=mock_resp)

    client.get_unread_entries()

    args, _ = client.session.get.call_args
    assert args[0] == 'http://localhost:8080/v1/feeds/55/entries'


def test_mark_entries_read_sends_correct_request():
    client = make_client()
    mock_resp = MagicMock()
    client.session.put = MagicMock(return_value=mock_resp)

    client.mark_entries_read([1, 2, 3])

    client.session.put.assert_called_once_with(
        'http://localhost:8080/v1/entries',
        json={'entry_ids': [1, 2, 3], 'status': 'read'}
    )
    mock_resp.raise_for_status.assert_called_once()


def test_mark_entries_read_skips_when_empty():
    client = make_client()
    client.session.put = MagicMock()

    client.mark_entries_read([])

    client.session.put.assert_not_called()
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_miniflux_client.py -v
```

Expected: all FAIL with `TypeError` (class has no methods)

- [ ] **Step 3: Implement MinifluxClient**

`app/miniflux_client.py`:
```python
import requests


class MinifluxClient:
    def __init__(self, base_url: str, api_key: str, feed_id: int):
        self._base_url = base_url.rstrip('/')
        self._feed_id = feed_id
        self.session = requests.Session()
        self.session.headers['X-Auth-Token'] = api_key

    def get_unread_entries(self) -> list[dict]:
        resp = self.session.get(
            f'{self._base_url}/v1/feeds/{self._feed_id}/entries',
            params={'status': 'unread', 'limit': 100}
        )
        resp.raise_for_status()
        return resp.json().get('entries', [])

    def mark_entries_read(self, entry_ids: list[int]) -> None:
        if not entry_ids:
            return
        resp = self.session.put(
            f'{self._base_url}/v1/entries',
            json={'entry_ids': entry_ids, 'status': 'read'}
        )
        resp.raise_for_status()
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_miniflux_client.py -v
```

Expected: 5 tests PASS

- [ ] **Step 5: Commit**

```bash
git add app/miniflux_client.py tests/test_miniflux_client.py
git commit -m "feat: MinifluxClient with get_unread_entries and mark_entries_read"
```

---

## Task 3: epub_builder

**Files:**
- Modify: `app/epub_builder.py`
- Create: `tests/test_epub_builder.py`

`build_epub(entries, digest_date)` sorts entries by `published_at` ascending, creates one `EpubHtml` chapter per entry, builds a flat TOC, writes to a temp file, reads back as bytes.

Key ebooklib pattern:
- `epub.EpubBook()` — create book
- `epub.EpubHtml(title, file_name, lang)` — one per article
- `book.toc` — list of `epub.Link` objects
- `book.spine = ['nav', chapter1, chapter2, ...]`
- `epub.write_epub(path, book)` — write to file path

- [ ] **Step 1: Write failing tests**

`tests/test_epub_builder.py`:
```python
import io
import zipfile

from epub_builder import build_epub

ENTRIES = [
    {
        'id': 1,
        'title': 'Article One',
        'url': 'http://ex.com/1',
        'content': '<p>Content one</p>',
        'published_at': '2026-04-30T09:00:00+00:00',
    },
    {
        'id': 2,
        'title': 'Article Two',
        'url': 'http://ex.com/2',
        'content': '<p>Content two</p>',
        'published_at': '2026-04-30T08:00:00+00:00',
    },
]


def test_build_epub_returns_bytes():
    result = build_epub(ENTRIES, '2026-04-30')
    assert isinstance(result, bytes)
    assert len(result) > 0


def test_build_epub_is_valid_epub_zip():
    result = build_epub(ENTRIES, '2026-04-30')
    with zipfile.ZipFile(io.BytesIO(result)) as zf:
        assert 'mimetype' in zf.namelist()
        assert zf.read('mimetype') == b'application/epub+zip'


def test_build_epub_contains_all_article_titles():
    result = build_epub(ENTRIES, '2026-04-30')
    with zipfile.ZipFile(io.BytesIO(result)) as zf:
        full_text = ' '.join(
            zf.read(name).decode('utf-8', errors='ignore')
            for name in zf.namelist()
        )
    assert 'Article One' in full_text
    assert 'Article Two' in full_text


def test_build_epub_sorts_by_published_at():
    # Article Two has earlier published_at; it should be article_0000
    result = build_epub(ENTRIES, '2026-04-30')
    with zipfile.ZipFile(io.BytesIO(result)) as zf:
        first_files = [n for n in zf.namelist() if n.endswith('article_0000.xhtml')]
        assert first_files, f"article_0000.xhtml not found in {zf.namelist()}"
        first_content = zf.read(first_files[0]).decode('utf-8')
    assert 'Article Two' in first_content


def test_build_epub_handles_empty_entries():
    result = build_epub([], '2026-04-30')
    assert isinstance(result, bytes)
    assert len(result) > 0
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_epub_builder.py -v
```

Expected: all FAIL (`build_epub` returns `None`)

- [ ] **Step 3: Implement build_epub**

`app/epub_builder.py`:
```python
import io
import os
import tempfile
from datetime import datetime
from ebooklib import epub


def build_epub(entries: list[dict], digest_date: str) -> bytes:
    entries_sorted = sorted(
        entries,
        key=lambda e: datetime.fromisoformat(e['published_at'])
    )

    book = epub.EpubBook()
    book.set_title(f'Daily Digest — {digest_date}')
    book.set_language('en')

    chapters = []
    toc_links = []

    for i, entry in enumerate(entries_sorted):
        file_name = f'article_{i:04d}.xhtml'
        chapter = epub.EpubHtml(title=entry['title'], file_name=file_name, lang='en')
        chapter.content = (
            f'<h1>{entry["title"]}</h1>'
            f'<p><a href="{entry["url"]}">{entry["url"]}</a></p>'
            f'{entry["content"]}'
        )
        book.add_item(chapter)
        chapters.append(chapter)
        toc_links.append(epub.Link(file_name, entry['title'], f'article_{i:04d}'))

    book.toc = toc_links
    book.add_item(epub.EpubNcx())
    book.add_item(epub.EpubNav())
    book.spine = ['nav'] + chapters

    with tempfile.NamedTemporaryFile(suffix='.epub', delete=False) as f:
        tmp_path = f.name
    try:
        epub.write_epub(tmp_path, book)
        with open(tmp_path, 'rb') as f:
            return f.read()
    finally:
        os.unlink(tmp_path)
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_epub_builder.py -v
```

Expected: 5 tests PASS

- [ ] **Step 5: Commit**

```bash
git add app/epub_builder.py tests/test_epub_builder.py
git commit -m "feat: epub_builder producing valid EPUB 3 with flat TOC sorted by date"
```

---

## Task 4: email_sender

**Files:**
- Modify: `app/email_sender.py`
- Create: `tests/test_email_sender.py`

Sends EPUB as a MIME attachment via Gmail SMTP with STARTTLS on port 587. Uses Python stdlib only (`smtplib`, `email`).

- [ ] **Step 1: Write failing tests**

`tests/test_email_sender.py`:
```python
import smtplib
from unittest.mock import MagicMock, patch

import pytest

from email_sender import send_epub


def call_send(epub_bytes=b'epub', filename='digest-2026-04-30.epub',
              gmail_user='u@gmail.com', password='pass', kindle='k@kindle.com'):
    send_epub(epub_bytes, filename, gmail_user, password, kindle)


def mock_smtp():
    m = MagicMock()
    m.__enter__ = MagicMock(return_value=m)
    m.__exit__ = MagicMock(return_value=False)
    return m


def test_send_epub_connects_to_gmail_smtp():
    smtp = mock_smtp()
    with patch('email_sender.smtplib.SMTP', return_value=smtp) as mock_cls:
        call_send()
    mock_cls.assert_called_once_with('smtp.gmail.com', 587)


def test_send_epub_uses_starttls():
    smtp = mock_smtp()
    with patch('email_sender.smtplib.SMTP', return_value=smtp):
        call_send()
    smtp.starttls.assert_called_once()


def test_send_epub_authenticates_with_credentials():
    smtp = mock_smtp()
    with patch('email_sender.smtplib.SMTP', return_value=smtp):
        call_send(gmail_user='user@gmail.com', password='apppass')
    smtp.login.assert_called_once_with('user@gmail.com', 'apppass')


def test_send_epub_sends_to_kindle_address():
    smtp = mock_smtp()
    with patch('email_sender.smtplib.SMTP', return_value=smtp):
        call_send(gmail_user='user@gmail.com', kindle='kindle@kindle.com')
    args = smtp.sendmail.call_args[0]
    assert args[0] == 'user@gmail.com'
    assert args[1] == 'kindle@kindle.com'


def test_send_epub_raises_on_auth_failure():
    smtp = mock_smtp()
    smtp.login.side_effect = smtplib.SMTPAuthenticationError(535, b'Bad credentials')
    with patch('email_sender.smtplib.SMTP', return_value=smtp):
        with pytest.raises(smtplib.SMTPAuthenticationError):
            call_send()
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_email_sender.py -v
```

Expected: all FAIL (`send_epub` returns `None`, assertions fail or `AttributeError`)

- [ ] **Step 3: Implement send_epub**

`app/email_sender.py`:
```python
import smtplib
from email import encoders
from email.mime.base import MIMEBase
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText


def send_epub(
    epub_bytes: bytes,
    filename: str,
    gmail_user: str,
    gmail_app_password: str,
    kindle_email: str,
) -> None:
    msg = MIMEMultipart()
    msg['From'] = gmail_user
    msg['To'] = kindle_email
    msg['Subject'] = filename.replace('.epub', '')

    msg.attach(MIMEText('Daily digest attached.', 'plain'))

    attachment = MIMEBase('application', 'epub+zip')
    attachment.set_payload(epub_bytes)
    encoders.encode_base64(attachment)
    attachment.add_header('Content-Disposition', 'attachment', filename=filename)
    msg.attach(attachment)

    with smtplib.SMTP('smtp.gmail.com', 587) as smtp:
        smtp.ehlo()
        smtp.starttls()
        smtp.login(gmail_user, gmail_app_password)
        smtp.sendmail(gmail_user, kindle_email, msg.as_string())
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_email_sender.py -v
```

Expected: 5 tests PASS

- [ ] **Step 5: Commit**

```bash
git add app/email_sender.py tests/test_email_sender.py
git commit -m "feat: email_sender sending EPUB via Gmail SMTP with STARTTLS"
```

---

## Task 5: sync.run_sync

**Files:**
- Modify: `app/sync.py`
- Create: `tests/test_sync.py`

Orchestrates one cycle. Imports `build_epub` and `send_epub` directly (mocked in tests). Uses `clients[0]` to mark all entries read (all clients share the same Miniflux API key).

- [ ] **Step 1: Write failing tests**

`tests/test_sync.py`:
```python
from unittest.mock import MagicMock, patch

from sync import run_sync


def make_entries(id_offset=0):
    return [{
        'id': 1 + id_offset,
        'title': f'Article {1 + id_offset}',
        'url': f'http://ex.com/{1 + id_offset}',
        'content': '<p>Content</p>',
        'published_at': '2026-04-30T08:00:00+00:00',
    }]


def test_run_sync_fetches_all_feeds():
    c1, c2 = MagicMock(), MagicMock()
    c1.get_unread_entries.return_value = make_entries(0)
    c2.get_unread_entries.return_value = make_entries(10)

    with patch('sync.build_epub', return_value=b'epub'), patch('sync.send_epub'):
        run_sync([c1, c2], 'u@gmail.com', 'pass', 'k@kindle.com')

    c1.get_unread_entries.assert_called_once()
    c2.get_unread_entries.assert_called_once()


def test_run_sync_skips_when_no_entries():
    client = MagicMock()
    client.get_unread_entries.return_value = []

    with patch('sync.build_epub') as mock_epub, patch('sync.send_epub') as mock_send:
        run_sync([client], 'u@gmail.com', 'pass', 'k@kindle.com')

    mock_epub.assert_not_called()
    mock_send.assert_not_called()
    client.mark_entries_read.assert_not_called()


def test_run_sync_marks_all_entries_read_after_send():
    c1, c2 = MagicMock(), MagicMock()
    c1.get_unread_entries.return_value = make_entries(0)
    c2.get_unread_entries.return_value = make_entries(10)

    with patch('sync.build_epub', return_value=b'epub'), patch('sync.send_epub'):
        run_sync([c1, c2], 'u@gmail.com', 'pass', 'k@kindle.com')

    c1.mark_entries_read.assert_called_once_with([1, 11])


def test_run_sync_does_not_mark_read_on_email_failure():
    client = MagicMock()
    client.get_unread_entries.return_value = make_entries()

    with patch('sync.build_epub', return_value=b'epub'), \
         patch('sync.send_epub', side_effect=Exception('SMTP error')):
        run_sync([client], 'u@gmail.com', 'pass', 'k@kindle.com')

    client.mark_entries_read.assert_not_called()


def test_run_sync_does_not_mark_read_on_epub_failure():
    client = MagicMock()
    client.get_unread_entries.return_value = make_entries()

    with patch('sync.build_epub', side_effect=Exception('EPUB error')), \
         patch('sync.send_epub') as mock_send:
        run_sync([client], 'u@gmail.com', 'pass', 'k@kindle.com')

    mock_send.assert_not_called()
    client.mark_entries_read.assert_not_called()


def test_run_sync_skips_failed_feed_and_continues():
    c1, c2 = MagicMock(), MagicMock()
    c1.get_unread_entries.side_effect = Exception('Connection refused')
    c2.get_unread_entries.return_value = make_entries(10)

    with patch('sync.build_epub', return_value=b'epub') as mock_epub, \
         patch('sync.send_epub'):
        run_sync([c1, c2], 'u@gmail.com', 'pass', 'k@kindle.com')

    mock_epub.assert_called_once()
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_sync.py -v
```

Expected: all FAIL (`ImportError` for `run_sync`)

- [ ] **Step 3: Implement run_sync**

`app/sync.py`:
```python
import logging
from datetime import date

from epub_builder import build_epub
from email_sender import send_epub
from miniflux_client import MinifluxClient

logger = logging.getLogger(__name__)


def run_sync(
    clients: list[MinifluxClient],
    gmail_user: str,
    gmail_app_password: str,
    kindle_email: str,
) -> None:
    all_entries = []

    for client in clients:
        try:
            entries = client.get_unread_entries()
            all_entries.extend(entries)
        except Exception as exc:
            logger.error("Failed to fetch feed: %s", exc)

    if not all_entries:
        logger.info("No unread entries, skipping digest")
        return

    logger.info("Fetched %d entries across %d feeds", len(all_entries), len(clients))

    digest_date = date.today().isoformat()
    filename = f'digest-{digest_date}.epub'

    try:
        epub_bytes = build_epub(all_entries, digest_date)
    except Exception as exc:
        logger.error("EPUB build failed: %s", exc)
        return

    try:
        send_epub(epub_bytes, filename, gmail_user, gmail_app_password, kindle_email)
        logger.info("Sent digest: %s", filename)
    except Exception as exc:
        logger.error("Email send failed, entries not marked read: %s", exc)
        return

    all_ids = [e['id'] for e in all_entries]
    try:
        clients[0].mark_entries_read(all_ids)
        logger.info("Marked %d entries as read", len(all_ids))
    except Exception as exc:
        logger.error("Failed to mark entries as read: %s", exc)
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_sync.py -v
```

Expected: 6 tests PASS

- [ ] **Step 5: Commit**

```bash
git add app/sync.py tests/test_sync.py
git commit -m "feat: run_sync orchestrating fetch, EPUB build, email, and mark-read"
```

---

## Task 6: main.py

**Files:**
- Modify: `app/main.py`
- Create: `tests/test_main.py`

`load_config()` validates all required vars, parses `MINIFLUX_FEED_IDS` to a list of ints, validates `DIGEST_HOUR` is 0–23 (default 6). `main()` creates one `MinifluxClient` per feed ID and runs the daily schedule.

- [ ] **Step 1: Write failing tests**

`tests/test_main.py`:
```python
import os

import pytest
from unittest.mock import patch

from main import load_config

FULL_ENV = {
    'MINIFLUX_BASE_URL': 'http://localhost:8080',
    'MINIFLUX_API_KEY': 'mk',
    'MINIFLUX_FEED_IDS': '55,12',
    'GMAIL_USER': 'user@gmail.com',
    'GMAIL_APP_PASSWORD': 'apppass',
    'KINDLE_EMAIL': 'kindle@kindle.com',
}


def test_load_config_returns_all_values():
    with patch.dict(os.environ, FULL_ENV, clear=True):
        config = load_config()
    assert config['miniflux_base_url'] == 'http://localhost:8080'
    assert config['miniflux_api_key'] == 'mk'
    assert config['feed_ids'] == [55, 12]
    assert config['gmail_user'] == 'user@gmail.com'
    assert config['gmail_app_password'] == 'apppass'
    assert config['kindle_email'] == 'kindle@kindle.com'
    assert config['digest_hour'] == 6


def test_load_config_parses_feed_ids_as_int_list():
    with patch.dict(os.environ, FULL_ENV, clear=True):
        config = load_config()
    assert isinstance(config['feed_ids'], list)
    assert all(isinstance(x, int) for x in config['feed_ids'])


def test_load_config_uses_custom_digest_hour():
    env = {**FULL_ENV, 'DIGEST_HOUR': '8'}
    with patch.dict(os.environ, env, clear=True):
        config = load_config()
    assert config['digest_hour'] == 8


def test_load_config_raises_on_missing_vars():
    with patch.dict(os.environ, {}, clear=True):
        with pytest.raises(SystemExit) as exc:
            load_config()
    assert 'MINIFLUX_BASE_URL' in str(exc.value)


def test_load_config_raises_on_invalid_feed_ids():
    bad = {**FULL_ENV, 'MINIFLUX_FEED_IDS': 'abc,def'}
    with patch.dict(os.environ, bad, clear=True):
        with pytest.raises(SystemExit) as exc:
            load_config()
    assert 'MINIFLUX_FEED_IDS' in str(exc.value)


def test_load_config_raises_on_empty_feed_ids():
    bad = {**FULL_ENV, 'MINIFLUX_FEED_IDS': ''}
    with patch.dict(os.environ, bad, clear=True):
        with pytest.raises(SystemExit) as exc:
            load_config()
    assert 'MINIFLUX_FEED_IDS' in str(exc.value)


def test_load_config_raises_on_out_of_range_digest_hour():
    bad = {**FULL_ENV, 'DIGEST_HOUR': '25'}
    with patch.dict(os.environ, bad, clear=True):
        with pytest.raises(SystemExit) as exc:
            load_config()
    assert 'DIGEST_HOUR' in str(exc.value)


def test_load_config_raises_on_non_integer_digest_hour():
    bad = {**FULL_ENV, 'DIGEST_HOUR': 'noon'}
    with patch.dict(os.environ, bad, clear=True):
        with pytest.raises(SystemExit) as exc:
            load_config()
    assert 'DIGEST_HOUR' in str(exc.value)
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_main.py -v
```

Expected: all FAIL (`ImportError: cannot import name 'load_config'`)

- [ ] **Step 3: Implement main.py**

`app/main.py`:
```python
import logging
import os
import time

import schedule

from miniflux_client import MinifluxClient
from sync import run_sync

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
logger = logging.getLogger(__name__)

REQUIRED_VARS = [
    'MINIFLUX_BASE_URL',
    'MINIFLUX_API_KEY',
    'MINIFLUX_FEED_IDS',
    'GMAIL_USER',
    'GMAIL_APP_PASSWORD',
    'KINDLE_EMAIL',
]


def load_config() -> dict:
    missing = [v for v in REQUIRED_VARS if not os.environ.get(v)]
    if missing:
        raise SystemExit(f"Missing required environment variables: {', '.join(missing)}")

    feed_ids_str = os.environ['MINIFLUX_FEED_IDS']
    try:
        feed_ids = [int(x.strip()) for x in feed_ids_str.split(',') if x.strip()]
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

    return {
        'miniflux_base_url': os.environ['MINIFLUX_BASE_URL'],
        'miniflux_api_key': os.environ['MINIFLUX_API_KEY'],
        'feed_ids': feed_ids,
        'gmail_user': os.environ['GMAIL_USER'],
        'gmail_app_password': os.environ['GMAIL_APP_PASSWORD'],
        'kindle_email': os.environ['KINDLE_EMAIL'],
        'digest_hour': digest_hour,
    }


def main() -> None:
    config = load_config()

    clients = [
        MinifluxClient(config['miniflux_base_url'], config['miniflux_api_key'], fid)
        for fid in config['feed_ids']
    ]

    def job() -> None:
        logger.info("Sync started")
        try:
            run_sync(
                clients,
                config['gmail_user'],
                config['gmail_app_password'],
                config['kindle_email'],
            )
        except Exception as exc:
            logger.error("Sync cycle failed: %s", exc)
        logger.info("Sync finished")

    job()
    schedule.every().day.at(f"{config['digest_hour']:02d}:00").do(job)
    logger.info("Scheduler running — next digest at %02d:00", config['digest_hour'])

    while True:
        schedule.run_pending()
        time.sleep(60)


if __name__ == '__main__':
    main()
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_main.py -v
```

Expected: 8 tests PASS

- [ ] **Step 5: Run full test suite**

```bash
pytest tests/ -v
```

Expected: 29 tests PASS, 0 failures

- [ ] **Step 6: Commit**

```bash
git add app/main.py tests/test_main.py
git commit -m "feat: main with load_config validation and daily schedule loop"
```

---

## Task 7: Dockerfile + Docker Compose

**Files:**
- Create: `Dockerfile`
- Create: `.dockerignore`
- Create: `~/docker/miniflux-to-kindle/docker-compose.yml`
- Create: `~/docker/miniflux-to-kindle/.env` (from .env.example)
- Create: `docker-compose.yml.example` (reference copy in repo)

- [ ] **Step 1: Write Dockerfile**

`Dockerfile`:
```dockerfile
FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app/ .

CMD ["python", "main.py"]
```

- [ ] **Step 2: Write .dockerignore**

`.dockerignore`:
```
venv/
tests/
docs/
requirements-dev.txt
.env
.pytest_cache/
__pycache__/
*.pyc
```

- [ ] **Step 3: Build to verify**

```bash
docker build -t miniflux-to-kindle .
```

Expected: successful build with no errors

- [ ] **Step 4: Create docker-compose.yml**

```bash
mkdir -p ~/docker/miniflux-to-kindle
```

`~/docker/miniflux-to-kindle/docker-compose.yml`:
```yaml
services:
  miniflux-to-kindle:
    build:
      context: /home/jac/miniflux-to-kindle
      dockerfile: Dockerfile
    env_file: .env
    restart: unless-stopped
```

- [ ] **Step 5: Create .env from example**

```bash
cp /home/jac/miniflux-to-kindle/.env.example ~/docker/miniflux-to-kindle/.env
```

Edit `~/docker/miniflux-to-kindle/.env` and fill in all seven values. For `GMAIL_APP_PASSWORD`, use a Gmail App Password (Google account → Security → 2-Step Verification → App passwords).

- [ ] **Step 6: Validate compose config**

```bash
cd ~/docker/miniflux-to-kindle && docker compose config
```

Expected: resolved config printed with no errors

- [ ] **Step 7: Commit reference copy to repo**

```bash
cp ~/docker/miniflux-to-kindle/docker-compose.yml /home/jac/miniflux-to-kindle/docker-compose.yml.example
git -C /home/jac/miniflux-to-kindle add Dockerfile .dockerignore docker-compose.yml.example
git -C /home/jac/miniflux-to-kindle commit -m "feat: Dockerfile, .dockerignore, and docker-compose example"
```

Do NOT run `docker compose up` until credentials are filled in `.env`.
