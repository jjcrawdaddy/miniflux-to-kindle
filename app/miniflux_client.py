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
