"""Checks that orders, positions, trades, funds and holdings keep being read, per broker and combined.

Broker scripts record a successful read either as a `polled_at` epoch key (orders and positions) or as the `timestamp` of a `{timestamp, status, code, data}` document (trades, funds and holdings). The unified combiners write documents with `as_of` and a `brokers` list saying which brokers were ok, stale, missing or unreadable.

Typical usage example:

  collector = PortfolioFreshnessCollector(redis_reader, inventory, thresholds.portfolio, clock)
  outcome = collector.run_once()
"""

from typing import Any

from system_monitor.checks.check_result import CheckArea, CheckResult, CheckStatus
from system_monitor.collectors.base_collector import BaseCollector
from system_monitor.configuration.thresholds import PortfolioThresholds
from system_monitor.sources.redis_reader import RedisReader
from system_monitor.sources.unit_inventory import UNIFIED_SUBJECT, UnitInventory
from system_monitor.utilities.clock import SystemClock
from system_monitor.utilities.text_formatter import TextFormatter
from system_monitor.utilities.timestamp_parser import TimestampParser


class PortfolioFreshnessCollector(BaseCollector):
    """Judges how recently each order and portfolio dataset was read."""

    name = 'portfolio'
    area = CheckArea.PORTFOLIO

    def __init__(
        self,
        redis_reader: RedisReader,
        inventory: UnitInventory,
        thresholds: PortfolioThresholds,
        clock: SystemClock,
        interval_seconds: float = 10.0,
    ):
        """Creates the collector.

        Args:
            redis_reader (RedisReader): Reads the dataset keys.
            inventory (UnitInventory): Says which datasets each subject runs a service for.
            thresholds (PortfolioThresholds): The age limits.
            clock (SystemClock): The source of the current time.
            interval_seconds (float): How long to wait between runs.
        """
        super().__init__(interval_seconds, clock)
        self.redis_reader = redis_reader
        self.inventory = inventory
        self.thresholds = thresholds

    def collect(self) -> list[CheckResult]:
        """Reads and judges every dataset.

        Returns:
            list[CheckResult]: One result per dataset whose service exists.

        Raises:
            redis.RedisError: Redis could not be read.
            ValueError: A document is not JSON.
        """
        now = self.clock.now()
        results = []
        for broker in self.inventory.brokers():
            if self.inventory.has_unit(f'{broker}@orders.service'):
                results.append(self._polled_at_check(broker, 'orders', 'Orders', f'{broker}:orders:orders:polled_at', now))
            if self.inventory.has_unit(f'{broker}@positions.service'):
                results.append(self._polled_at_check(broker, 'positions', 'Positions', f'{broker}:portfolio:positions:polled_at', now))
            if self.inventory.has_unit(f'{broker}@trades.service'):
                results.append(self._document_check(broker, 'trades', 'Trades', f'{broker}:orders:trades', now))
            if self.inventory.has_unit(f'{broker}@funds.service'):
                results.append(self._document_check(broker, 'funds', 'Funds', f'{broker}:portfolio:funds', now))
            if self.inventory.has_unit(f'{broker}@holdings.service'):
                results.append(self._document_check(broker, 'holdings', 'Holdings', f'{broker}:portfolio:holdings', now))

        if self.inventory.has_unit('unified@orders.service'):
            results.append(self._unified_check('orders', 'Orders', 'unified:orders:orders', now))
        if self.inventory.has_unit('unified@trades.service'):
            results.append(self._unified_check('trades', 'Trades', 'unified:orders:trades', now))
        if self.inventory.has_unit('unified@positions.service'):
            results.append(self._unified_check('positions', 'Positions', 'unified:portfolio:positions', now))
        if self.inventory.has_unit('unified@funds.service'):
            results.append(self._unified_check('funds', 'Funds', 'unified:portfolio:funds', now))
        if self.inventory.has_unit('unified@holdings.service'):
            results.append(self._unified_check('holdings', 'Holdings', 'unified:portfolio:holdings', now))
        return results

    def _polled_at_check(
        self,
        broker: str,
        dataset: str,
        label: str,
        key: str,
        now: float,
    ) -> CheckResult:
        """Judges a dataset recorded by an epoch `polled_at` key.

        Args:
            broker (str): The broker name.
            dataset (str): The dataset name, such as "orders".
            label (str): The human label.
            key (str): The polled_at key.
            now (float): The current time, in epoch seconds.

        Returns:
            CheckResult: The dataset's result.
        """
        text = self.redis_reader.get_text(key)
        polled_at = None
        if text is not None:
            try:
                polled_at = float(text)
            except ValueError:
                polled_at = None
        details = {
            'key': key,
            'read_at': polled_at,
        }
        if polled_at is None:
            return self.result(
                f'{broker}:{dataset}',
                broker,
                label,
                CheckStatus.FAILURE,
                f'Never read successfully today ({key} is missing).',
                details=details,
            )
        age = now - polled_at
        details['age_seconds'] = age
        status, message = self._judge_age(dataset, age)
        return self.result(
            f'{broker}:{dataset}',
            broker,
            label,
            status,
            message,
            value=age,
            details=details,
        )

    def _document_check(
        self,
        broker: str,
        dataset: str,
        label: str,
        key: str,
        now: float,
    ) -> CheckResult:
        """Judges a dataset stored as a `{timestamp, status, code, data}` document.

        Args:
            broker (str): The broker name.
            dataset (str): The dataset name, such as "funds".
            label (str): The human label.
            key (str): The document key.
            now (float): The current time, in epoch seconds.

        Returns:
            CheckResult: The dataset's result.
        """
        document = self.redis_reader.get_json(key)
        if not isinstance(document, dict):
            return self.result(
                f'{broker}:{dataset}',
                broker,
                label,
                CheckStatus.FAILURE,
                f'Never read ({key} is missing).',
                details={
                    'key': key,
                },
            )
        read_at = self._epoch_or_none(document.get('timestamp'))
        poll_status = document.get('status')
        details = {
            'key': key,
            'read_at': read_at,
            'poll_status': poll_status,
            'code': document.get('code'),
        }
        if read_at is None:
            return self.result(
                f'{broker}:{dataset}',
                broker,
                label,
                CheckStatus.UNKNOWN,
                f'{key} has no readable timestamp.',
                details=details,
            )
        age = now - read_at
        details['age_seconds'] = age
        status, message = self._judge_age(dataset, age)
        if status == CheckStatus.OK and poll_status != 'success':
            status = CheckStatus.WARNING
            message = f'The last poll answered {poll_status!r} (code {document.get("code")}).'
        return self.result(
            f'{broker}:{dataset}',
            broker,
            label,
            status,
            message,
            value=age,
            details=details,
        )

    def _unified_check(
        self,
        dataset: str,
        label: str,
        key: str,
        now: float,
    ) -> CheckResult:
        """Judges a unified combiner's document by its `as_of` and broker statuses.

        Args:
            dataset (str): The dataset name, such as "positions".
            label (str): The human label.
            key (str): The unified document key.
            now (float): The current time, in epoch seconds.

        Returns:
            CheckResult: The combined dataset's result.
        """
        document = self.redis_reader.get_json(key)
        if not isinstance(document, dict):
            return self.result(
                f'unified:{dataset}',
                UNIFIED_SUBJECT,
                label,
                CheckStatus.FAILURE,
                f'The combined document {key} is missing.',
                details={
                    'key': key,
                },
            )
        written_at = self._epoch_or_none(document.get('as_of'))
        brokers = []
        not_ok = []
        for entry in document.get('brokers') or []:
            if not isinstance(entry, dict):
                continue
            broker_status = entry.get('status')
            brokers.append(
                {
                    'broker': entry.get('broker'),
                    'status': broker_status,
                    'as_of': self._epoch_or_none(entry.get('as_of')),
                },
            )
            if broker_status != 'ok':
                not_ok.append(f'{entry.get("broker")} {broker_status}')
        details = {
            'key': key,
            'read_at': written_at,
            'brokers': brokers,
            'summary': document.get('summary'),
        }
        if written_at is None:
            return self.result(
                f'unified:{dataset}',
                UNIFIED_SUBJECT,
                label,
                CheckStatus.UNKNOWN,
                f'{key} has no readable as_of time.',
                details=details,
            )
        age = now - written_at
        details['age_seconds'] = age
        status, message = self._judge_age(dataset, age)
        if status == CheckStatus.OK and not_ok:
            status = CheckStatus.WARNING
            message = f'Combined without fresh data from: {", ".join(not_ok)}.'
        return self.result(
            f'unified:{dataset}',
            UNIFIED_SUBJECT,
            label,
            status,
            message,
            value=age,
            details=details,
        )

    def _judge_age(self, dataset: str, age: float) -> tuple[CheckStatus, str]:
        """Judges how old a dataset's last read is.

        Args:
            dataset (str): The dataset name; holdings have longer limits.
            age (float): Seconds since the last read.

        Returns:
            tuple[CheckStatus, str]: A tuple (status, message).
        """
        warning_age = self.thresholds.warning_age_seconds
        failure_age = self.thresholds.failure_age_seconds
        if dataset == 'holdings':
            warning_age = self.thresholds.holdings_warning_age_seconds
            failure_age = self.thresholds.holdings_failure_age_seconds
        age_text = TextFormatter.duration(age)
        if age > failure_age:
            return CheckStatus.FAILURE, f'Not read for {age_text}.'
        if age > warning_age:
            return CheckStatus.WARNING, f'Last read {age_text} ago, later than expected.'
        return CheckStatus.OK, f'Read {age_text} ago.'

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
