"""Tests for the web routes, assembled with fake components."""

from collections.abc import AsyncIterator

import argon2
import fastapi.testclient

from system_monitor.alerts.alert_policy import AlertPolicy
from system_monitor.application import Application
from system_monitor.checks.check_result import (
    CheckArea,
    CheckResult,
    CheckStatus,
    CollectionOutcome,
)
from system_monitor.configuration.settings import Settings
from system_monitor.configuration.thresholds import AlertThresholds
from system_monitor.controls.unit_controller import UnitController
from system_monitor.security.authenticator import Authenticator
from system_monitor.sources.journal_client import JournalEntry
from system_monitor.sources.market_calendar import MarketCalendar
from system_monitor.state.dashboard_snapshot import DashboardSnapshot
from system_monitor.state.monitor_state import MonitorState
from tests.fakes import FakeSystemdClient, FakeUnitInventory, FixedClock

_PASSWORD = 'correct horse battery'
_HASH = argon2.PasswordHasher(time_cost=1, memory_cost=8, parallelism=1).hash(_PASSWORD)
_HEADERS = {
    'X-Requested-With': 'system-monitor',
}


class _FakeJournalFollower:
    """A follower that yields two prepared lines and ends."""

    async def follow(self, unit_name: str, line_count: int) -> AsyncIterator[JournalEntry]:
        """Yields two lines.

        Args:
            unit_name (str): The unit.
            line_count (int): Ignored.

        Yields:
            JournalEntry: A warning line and a plain line.
        """
        del line_count
        yield JournalEntry(unit_name, '', 1.0, '2026-09-15 07:06:20 WARNING  zerodha.quotes socket_0 disconnected.', 'c1')
        yield JournalEntry(unit_name, '', 2.0, 'continuation', 'c2')


class TestRoutes:
    """Tests for the routes through FastAPI's test client."""

    def _client(self, tmp_path) -> tuple[fastapi.testclient.TestClient, FakeSystemdClient]:
        """Builds the web application with fake components and a built front end.

        Args:
            tmp_path (pathlib.Path): pytest's temporary directory.

        Returns:
            tuple[fastapi.testclient.TestClient, FakeSystemdClient]: A tuple (client, systemd client).
        """
        frontend = tmp_path / 'dist'
        (frontend / 'assets').mkdir(parents=True)
        (frontend / 'index.html').write_text('<!doctype html><title>index</title>')
        (frontend / 'assets' / 'app-123.js').write_text('console.log(1)')
        settings = Settings(
            _env_file=None,
            password_hash=_HASH,
            session_secret='test-secret',
            frontend_directory=frontend,
        )
        clock = FixedClock.at_india_time(2026, 9, 15, 11, 0)
        inventory = FakeUnitInventory(
            {
                'zerodha': [
                    'zerodha@quotes.service',
                ],
            },
        )
        systemd_client = FakeSystemdClient()
        state = MonitorState(clock)
        state.apply(
            CollectionOutcome(
                collector_name='feeds',
                results=[
                    CheckResult(
                        check_id='feeds:zerodha',
                        area=CheckArea.FEEDS,
                        subject='zerodha',
                        name='Quote feed',
                        status=CheckStatus.OK,
                        message='Fine.',
                    ),
                ],
                error=None,
                started_at=0,
                duration_seconds=0,
            ),
        )
        controller = UnitController(systemd_client, inventory, clock)
        application = Application(settings)
        web_application = application.create_web_application(
            snapshot_builder=DashboardSnapshot(
                state,
                controller,
                AlertPolicy(
                    AlertThresholds(
                        consecutive_failures=2,
                        cooldown_seconds=600,
                        group_threshold=3,
                    ),
                    clock,
                ),
                MarketCalendar(None, clock),
                clock,
            ),
            controller=controller,
            authenticator=Authenticator(_HASH, clock),
            inventory=inventory,
            journal_follower=_FakeJournalFollower(),
            with_lifespan=False,
        )
        return fastapi.testclient.TestClient(web_application), systemd_client

    def _log_in(self, client: fastapi.testclient.TestClient) -> None:
        """Logs the client in.

        Args:
            client (fastapi.testclient.TestClient): The client.

        Raises:
            AssertionError: The login failed.
        """
        response = client.post(
            '/api/auth/login',
            json={
                'password': _PASSWORD,
            },
            headers=_HEADERS,
        )
        assert response.status_code == 200

    def test_data_routes_require_login(self, tmp_path):
        """Checks that data, logs and controls are refused without a session.

        Raises:
            AssertionError: A route answered without a session.
        """
        client, systemd_client = self._client(tmp_path)
        assert client.get('/api/snapshot').status_code == 401
        assert client.get('/api/events').status_code == 401
        assert client.get('/api/logs/zerodha@quotes.service/events').status_code == 401
        assert client.post('/api/units/zerodha@quotes.service/restart', headers=_HEADERS).status_code == 401
        assert systemd_client.actions == []
        assert client.get('/api/auth/session').json() == {
            'authenticated': False,
        }

    def test_login_checks_header_and_password(self, tmp_path):
        """Checks the header requirement, a wrong password, and a working login and logout.

        Raises:
            AssertionError: A response is wrong.
        """
        client, _systemd_client = self._client(tmp_path)
        no_header = client.post(
            '/api/auth/login',
            json={
                'password': _PASSWORD,
            },
        )
        assert no_header.status_code == 403
        wrong = client.post(
            '/api/auth/login',
            json={
                'password': 'wrong',
            },
            headers=_HEADERS,
        )
        assert wrong.status_code == 401
        self._log_in(client)
        cookie = client.cookies.get('system_monitor_session')
        assert cookie
        snapshot = client.get('/api/snapshot').json()
        assert snapshot['checks'][0]['check_id'] == 'feeds:zerodha'
        assert snapshot['actions'] == []
        assert client.post('/api/auth/logout', headers=_HEADERS).status_code == 200
        assert client.get('/api/snapshot').status_code == 401

    def test_login_sets_strict_http_only_cookie(self, tmp_path):
        """Checks the cookie attributes.

        Raises:
            AssertionError: An attribute is missing.
        """
        client, _systemd_client = self._client(tmp_path)
        response = client.post(
            '/api/auth/login',
            json={
                'password': _PASSWORD,
            },
            headers=_HEADERS,
        )
        set_cookie = response.headers['set-cookie'].lower()
        assert 'httponly' in set_cookie
        assert 'samesite=strict' in set_cookie

    def test_control_route_rules(self, tmp_path):
        """Checks the header requirement, a foreign unit, a bad action and a working restart.

        Raises:
            AssertionError: A response or the recorded actions are wrong.
        """
        client, systemd_client = self._client(tmp_path)
        self._log_in(client)
        assert client.post('/api/units/zerodha@quotes.service/restart').status_code == 403
        assert client.post('/api/units/ssh.service/restart', headers=_HEADERS).status_code == 403
        assert client.post('/api/units/zerodha@quotes.service/stop', headers=_HEADERS).status_code == 400
        assert systemd_client.actions == []
        response = client.post('/api/units/zerodha@quotes.service/restart', headers=_HEADERS)
        assert response.status_code == 200
        assert response.json()['succeeded']
        assert systemd_client.actions == [
            ('restart', 'zerodha@quotes.service'),
        ]
        assert client.get('/api/snapshot').json()['actions'][0]['unit'] == 'zerodha@quotes.service'

    def test_log_route_streams_parsed_lines(self, tmp_path):
        """Checks that log lines arrive as events with levels, and foreign units are refused.

        Raises:
            AssertionError: The stream or refusal is wrong.
        """
        client, _systemd_client = self._client(tmp_path)
        self._log_in(client)
        assert client.get('/api/logs/ssh.service/events').status_code == 404
        response = client.get('/api/logs/zerodha@quotes.service/events')
        assert response.status_code == 200
        assert response.headers['content-type'].startswith('text/event-stream')
        events = response.text.strip().split('\n\n')
        assert len(events) == 2
        assert '"level": "WARNING"' in events[0]
        assert '"continuation": true' in events[1]

    def test_frontend_routes(self, tmp_path):
        """Checks assets, client-side routes falling back to index.html, and unknown API paths.

        Raises:
            AssertionError: A response is wrong.
        """
        client, _systemd_client = self._client(tmp_path)
        asset = client.get('/assets/app-123.js')
        assert asset.status_code == 200
        assert 'immutable' in asset.headers['cache-control']
        page = client.get('/services')
        assert page.status_code == 200
        assert '<title>index</title>' in page.text
        assert client.get('/api/nothing').status_code == 404
        assert client.get('/../../etc/passwd').text == page.text
