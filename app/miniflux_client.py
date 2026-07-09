from urllib.parse import urlparse

import requests

REQUEST_TIMEOUT = 30


class MinifluxClient:
    def __init__(self, base_url: str, api_key: str):
        self._base_url = base_url.rstrip('/')
        self.session = requests.Session()
        self.session.headers['X-Auth-Token'] = api_key

    @property
    def hostname(self) -> str | None:
        return urlparse(self._base_url).hostname

    def get_unread_entries(self, feed_id: int) -> list[dict]:
        resp = self.session.get(
            f'{self._base_url}/v1/feeds/{feed_id}/entries',
            params={'status': 'unread', 'limit': 100},
            timeout=REQUEST_TIMEOUT,
        )
        resp.raise_for_status()
        return resp.json().get('entries', [])

    def mark_entries_read(self, entry_ids: list[int]) -> None:
        if not entry_ids:
            return
        resp = self.session.put(
            f'{self._base_url}/v1/entries',
            json={'entry_ids': entry_ids, 'status': 'read'},
            timeout=REQUEST_TIMEOUT,
        )
        resp.raise_for_status()

    def refresh_feed(self, feed_id: int) -> None:
        resp = self.session.put(
            f'{self._base_url}/v1/feeds/{feed_id}/refresh',
            timeout=REQUEST_TIMEOUT,
        )
        resp.raise_for_status()
