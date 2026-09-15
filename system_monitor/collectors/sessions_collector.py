"""Checks each broker's login session and the REST API's application token.

Session documents carry the access token itself. Only the status and times are copied into results; the token never leaves this module.

Typical usage example:

  collector = SessionsCollector(redis_reader, inventory, clock)
  outcome = collector.run_once()
"""

from typing import Any

from system_monitor.checks.check_result import CheckArea, CheckResult, CheckStatus
from system_monitor.collectors.base_collector import BaseCollector
from system_monitor.sources.redis_reader import RedisReader
from system_monitor.sources.unit_inventory import UNIFIED_SUBJECT, UnitInventory
from system_monitor.utilities.clock import SystemClock
from system_monitor.utilities.text_formatter import TextFormatter
from system_monitor.utilities.timestamp_parser import TimestampParser


class SessionsCollector(BaseCollector):
    """Judges broker sessions and the application token from Redis."""

    name = 'sessions'
    area = CheckArea.SESSIONS

    def __init__(
        self,
        redis_reader: RedisReader,
        inventory: UnitInventory,
        clock: SystemClock,
        interval_seconds: float = 10.0,
    ):
        """Creates the collector.

        Args:
            redis_reader (RedisReader): Reads the session keys.
            inventory (UnitInventory): Supplies the broker names.
            clock (SystemClock): The source of the current time.
            interval_seconds (float): How long to wait between runs.
        """
        super().__init__(interval_seconds, clock)
        self.redis_reader = redis_reader
        self.inventory = inventory

    def collect(self) -> list[CheckResult]:
        """Reads and judges every session.

        Returns:
            list[CheckResult]: One result per broker and one for the application token.

        Raises:
            redis.RedisError: Redis could not be read.
            ValueError: A session document is not JSON.
        """
        now = self.clock.now()
        results = []
        for broker in self.inventory.brokers():
            document = self.redis_reader.get_json(f'{broker}:session:status')
            results.append(self._judge_broker(broker, document, now))
        token_document = self.redis_reader.hash_get_json('last_login', 'unified_broker_interface')
        results.append(self._judge_application_token(token_document, now))
        return results

    def _judge_broker(
        self,
        broker: str,
        document: Any,
        now: float,
    ) -> CheckResult:
        """Judges one broker's session document.

        Args:
            broker (str): The broker name.
            document (Any): The parsed `<broker>:session:status` document, or None.
            now (float): The current time, in epoch seconds.

        Returns:
            CheckResult: The broker's session result.
        """
        if not isinstance(document, dict):
            return self.result(
                broker,
                broker,
                'Login session',
                CheckStatus.FAILURE,
                'No session is recorded in Redis; the login job has not written one.',
            )
        status_text = document.get('status')
        last_login = self._epoch_or_none(document.get('last_login'))
        details = {
            'status': status_text,
            'last_login': last_login,
        }
        when = ''
        if last_login is not None:
            when = f' at {TextFormatter.india_time(last_login, now)}'

        if status_text == 'success':
            status = CheckStatus.OK
            message = f'Logged in{when}.'
        elif status_text == 'logged out':
            status = CheckStatus.WARNING
            message = 'Logged out.'
        elif status_text == 'failure':
            status = CheckStatus.FAILURE
            message = f'The last login attempt{when} failed.'
        else:
            status = CheckStatus.UNKNOWN
            message = f'Unrecognised session status {status_text!r}.'
        return self.result(
            broker,
            broker,
            'Login session',
            status,
            message,
            details=details,
        )

    def _judge_application_token(self, document: Any, now: float) -> CheckResult:
        """Judges the REST API's own application token.

        Args:
            document (Any): The parsed `last_login` hash field `unified_broker_interface`, or None.
            now (float): The current time, in epoch seconds.

        Returns:
            CheckResult: The token's result.
        """
        label = 'REST API token'
        if not isinstance(document, dict):
            return self.result(
                'application_token',
                UNIFIED_SUBJECT,
                label,
                CheckStatus.WARNING,
                'No application token is recorded; REST API clients have not connected.',
            )
        has_token = bool(document.get('access_token'))
        last_login = self._epoch_or_none(document.get('last_login'))
        expires_at = self._epoch_or_none(document.get('expires_at'))
        details = {
            'has_token': has_token,
            'last_login': last_login,
            'expires_at': expires_at,
        }
        if not has_token:
            status = CheckStatus.WARNING
            message = 'The application token is logged out.'
        elif expires_at is not None and expires_at <= now:
            status = CheckStatus.WARNING
            message = f'The application token expired at {TextFormatter.india_time(expires_at, now)}.'
        elif expires_at is not None:
            status = CheckStatus.OK
            message = f'Valid until {TextFormatter.india_time(expires_at, now)}.'
        else:
            status = CheckStatus.OK
            message = 'Connected, with no expiry recorded.'
        return self.result(
            'application_token',
            UNIFIED_SUBJECT,
            label,
            status,
            message,
            details=details,
        )

    def _epoch_or_none(self, value: Any) -> float | None:
        """Reads a UBI timestamp that may be missing, a number or a local time string.

        Args:
            value (Any): The stored value.

        Returns:
            float | None: Epoch seconds, or None when missing or unreadable.
        """
        if value is None:
            return None
        if isinstance(value, (int, float)):
            return float(value)
        try:
            return TimestampParser.india_text_to_epoch(value)
        except ValueError:
            return None
