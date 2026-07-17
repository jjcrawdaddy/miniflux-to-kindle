import dataclasses
import os

import pytest
import schedule
from unittest.mock import MagicMock, patch

from config import Config, load_config
from main import compute_schedule_times, run_job, setup_schedule

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
    assert config.miniflux_base_url == 'http://localhost:8080'
    assert config.miniflux_api_key == 'mk'
    assert config.feed_ids == (55, 12)
    assert config.gmail_user == 'user@gmail.com'
    assert config.gmail_app_password == 'apppass'
    assert config.kindle_email == 'kindle@kindle.com'
    assert config.digest_hour == 6
    assert config.timezone == 'UTC'


def test_load_config_is_immutable():
    with patch.dict(os.environ, FULL_ENV, clear=True):
        config = load_config()
    with pytest.raises(dataclasses.FrozenInstanceError):
        config.gmail_user = 'other@gmail.com'


def test_load_config_parses_feed_ids_as_int_tuple():
    with patch.dict(os.environ, FULL_ENV, clear=True):
        config = load_config()
    assert isinstance(config.feed_ids, tuple)
    assert all(isinstance(x, int) for x in config.feed_ids)


def test_load_config_uses_custom_digest_hour():
    env = {**FULL_ENV, 'DIGEST_HOUR': '8'}
    with patch.dict(os.environ, env, clear=True):
        config = load_config()
    assert config.digest_hour == 8


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
    bad = {**FULL_ENV, 'MINIFLUX_FEED_IDS': '   '}
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


def test_load_config_defaults_timezone_to_utc():
    with patch.dict(os.environ, FULL_ENV, clear=True):
        config = load_config()
    assert config.timezone == 'UTC'


def test_load_config_uses_custom_timezone():
    env = {**FULL_ENV, 'TIMEZONE': 'America/Chicago'}
    with patch.dict(os.environ, env, clear=True):
        config = load_config()
    assert config.timezone == 'America/Chicago'


def test_load_config_raises_on_invalid_timezone():
    bad = {**FULL_ENV, 'TIMEZONE': 'Not/ATimezone'}
    with patch.dict(os.environ, bad, clear=True):
        with pytest.raises(SystemExit) as exc:
            load_config()
    assert 'TIMEZONE' in str(exc.value)


def test_load_config_run_on_startup_defaults_true():
    with patch.dict(os.environ, FULL_ENV, clear=True):
        config = load_config()
    assert config.run_on_startup is True


def test_load_config_run_on_startup_false():
    env = {**FULL_ENV, 'RUN_ON_STARTUP': 'false'}
    with patch.dict(os.environ, env, clear=True):
        config = load_config()
    assert config.run_on_startup is False


def test_load_config_raises_on_invalid_run_on_startup():
    bad = {**FULL_ENV, 'RUN_ON_STARTUP': 'maybe'}
    with patch.dict(os.environ, bad, clear=True):
        with pytest.raises(SystemExit) as exc:
            load_config()
    assert 'RUN_ON_STARTUP' in str(exc.value)


def test_load_config_healthcheck_url_defaults_to_none():
    with patch.dict(os.environ, FULL_ENV, clear=True):
        config = load_config()
    assert config.healthcheck_url is None


def test_load_config_reads_healthcheck_url():
    env = {**FULL_ENV, 'HEALTHCHECK_URL': 'https://hc-ping.com/uuid/'}
    with patch.dict(os.environ, env, clear=True):
        config = load_config()
    assert config.healthcheck_url == 'https://hc-ping.com/uuid'


def make_config(digest_hour=6, timezone='America/Chicago', healthcheck_url=None):
    return Config(
        miniflux_base_url='http://miniflux.lan:8080',
        miniflux_api_key='mk',
        feed_ids=(55,),
        gmail_user='u@gmail.com',
        gmail_app_password='pass',
        kindle_email='k@kindle.com',
        digest_hour=digest_hour,
        timezone=timezone,
        healthcheck_url=healthcheck_url,
    )


HC_URL = 'https://hc-ping.com/uuid'


def ping_calls(mock_ping):
    return [c.args for c in mock_ping.call_args_list]


def test_run_job_pings_start_then_success():
    config = make_config(healthcheck_url=HC_URL)
    with patch('main.run_sync', return_value=None), patch('main.ping') as mock_ping:
        run_job(MagicMock(), config)
    assert ping_calls(mock_ping) == [(HC_URL, '/start'), (HC_URL,)]


def test_run_job_pings_fail_with_error_message():
    config = make_config(healthcheck_url=HC_URL)
    with patch('main.run_sync', return_value='Email send failed: timed out'), \
         patch('main.ping') as mock_ping:
        run_job(MagicMock(), config)
    assert ping_calls(mock_ping) == [
        (HC_URL, '/start'),
        (HC_URL, '/fail', 'Email send failed: timed out'),
    ]


def test_run_job_pings_fail_on_unexpected_exception():
    config = make_config(healthcheck_url=HC_URL)
    with patch('main.run_sync', side_effect=RuntimeError('boom')), \
         patch('main.ping') as mock_ping:
        run_job(MagicMock(), config)
    assert (HC_URL, '/fail', 'boom') in ping_calls(mock_ping)


def test_compute_schedule_times_refresh_three_minutes_before_digest():
    assert compute_schedule_times(6) == ('06:00', '05:57')


def test_compute_schedule_times_wraps_around_midnight():
    assert compute_schedule_times(0) == ('00:00', '23:57')


def test_setup_schedule_registers_timezone_aware_jobs():
    schedule.clear()
    try:
        setup_schedule(make_config(), MagicMock(), lambda: None)
        assert len(schedule.jobs) == 2
        for job in schedule.jobs:
            # tz-aware jobs recompute next_run per day, so DST shifts are honored
            assert str(job.at_time_zone) == 'America/Chicago'
            assert job.next_run is not None
    finally:
        schedule.clear()
