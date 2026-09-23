"""Tests for SessionsCollector."""

import json

from system_monitor.checks.check_result import CheckStatus
from system_monitor.collectors.sessions_collector import SessionsCollector
from tests.fakes import FakeRedisReader, FakeUnitInventory, FixedClock


class TestSessionsCollector:
    """Tests for SessionsCollector."""

    def _collect(self, reader: FakeRedisReader) -> dict:
        """Runs the collector for zerodha and kotak at 15 Sep 2026 10:00 India time.

        Args:
            reader (FakeRedisReader): The prepared Redis contents.

        Returns:
            dict: The results keyed by check_id.
        """
        inventory = FakeUnitInventory(
            {
                'kotak': [
                    'kotak-instruments@websocket_quotes.service',
                ],
                'zerodha': [
                    'zerodha-instruments@websocket_quotes.service',
                ],
                'unified': [
                    'unified-instruments@websocket_quotes.service',
                ],
            },
        )
        clock = FixedClock.at_india_time(2026, 9, 15, 10, 0)
        indexed = {}
        for result in SessionsCollector(reader, inventory, clock).collect():
            indexed[result.check_id] = result
        return indexed

    def test_collect_judges_statuses_without_leaking_tokens(self):
        """Checks success, failure and a missing session, and that no token reaches a result.

        Raises:
            AssertionError: A status is wrong or a token appears in the results.
        """
        reader = FakeRedisReader()
        reader.set_json(
            'zerodha:session:status',
            {
                'status': 'success',
                'access-token': 'SECRET-TOKEN',
                'last_login': '2026-09-15 06:30:07.753403',
            },
        )
        reader.set_hash_json(
            'last_login',
            'unified_broker_interface',
            {
                'broker_name': 'unified_broker_interface',
                'access_token': 'SECRET-APPLICATION-TOKEN',
                'last_login': '2026-09-15 09:00:00',
                'expires_at': '2026-09-16 09:00:00',
            },
        )
        results = self._collect(reader)
        assert results['sessions:zerodha'].status == CheckStatus.OK
        assert results['sessions:zerodha'].message == 'Logged in at 06:30.'
        assert results['sessions:kotak'].status == CheckStatus.FAILURE
        assert results['sessions:application_token'].status == CheckStatus.OK
        serialised = json.dumps([result.to_dictionary() for result in results.values()])
        assert 'SECRET' not in serialised

    def test_collect_failed_login_is_failure(self):
        """Checks a recorded login failure.

        Raises:
            AssertionError: The result is not a failure.
        """
        reader = FakeRedisReader()
        reader.set_json(
            'kotak:session:status',
            {
                'status': 'failure',
                'access-token': None,
                'last_login': '2026-09-15 08:20:00',
            },
        )
        result = self._collect(reader)['sessions:kotak']
        assert result.status == CheckStatus.FAILURE
        assert result.message == 'The last login attempt at 08:20 failed.'

    def test_collect_expired_application_token_is_warning(self):
        """Checks an application token past its expiry.

        Raises:
            AssertionError: The result is not a warning.
        """
        reader = FakeRedisReader()
        reader.set_hash_json(
            'last_login',
            'unified_broker_interface',
            {
                'access_token': 'x',
                'expires_at': '2026-09-15 09:00:00',
            },
        )
        result = self._collect(reader)['sessions:application_token']
        assert result.status == CheckStatus.WARNING
        assert 'expired' in result.message
