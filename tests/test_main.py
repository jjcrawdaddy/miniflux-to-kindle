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
