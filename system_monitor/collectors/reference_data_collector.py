"""Checks the morning's reference data: each broker's instrument download, the unified mapping and the prices run.

UBI's `unified-mapping.timer` fires at 07:45 India time every day, weekends and holidays included, because the brokers publish a master every day and a missed one can never be fetched again. Today's download and mapping are therefore expected every day, with no reference to the trading calendar.

Typical usage example:

  collector = ReferenceDataCollector(redis_reader, inventory, thresholds.reference_data, clock)
  outcome = collector.run_once()
"""

from typing import Any

from system_monitor.checks.check_result import CheckArea, CheckResult, CheckStatus
from system_monitor.collectors.base_collector import BaseCollector
from system_monitor.configuration.thresholds import ReferenceDataThresholds
from system_monitor.sources.redis_reader import RedisReader
from system_monitor.sources.unit_inventory import UNIFIED_SUBJECT, UnitInventory
from system_monitor.utilities.clock import SystemClock
from system_monitor.utilities.timestamp_parser import TimestampParser


class ReferenceDataCollector(BaseCollector):
    """Judges whether today's instruments, mapping and prices exist."""

    name = 'reference_data'
    area = CheckArea.REFERENCE_DATA

    def __init__(
        self,
        redis_reader: RedisReader,
        inventory: UnitInventory,
        thresholds: ReferenceDataThresholds,
        clock: SystemClock,
        interval_seconds: float = 300.0,
    ):
        """Creates the collector.

        Args:
            redis_reader (RedisReader): Reads the meta documents.
            inventory (UnitInventory): Supplies the broker names.
            thresholds (ReferenceDataThresholds): The time by which today's data should exist.
            clock (SystemClock): The source of the current time.
            interval_seconds (float): How long to wait between runs.
        """
        super().__init__(interval_seconds, clock)
        self.redis_reader = redis_reader
        self.inventory = inventory
        self.thresholds = thresholds

    def collect(self) -> list[CheckResult]:
        """Reads and judges the reference data.

        Returns:
            list[CheckResult]: One result per broker's instruments, one for the mapping and one for the prices run.

        Raises:
            redis.RedisError: Redis could not be read.
            ValueError: A document is not JSON.
        """
        now = self.clock.now()
        moment = TimestampParser.india_datetime(now)
        today = moment.date().isoformat()
        expected_now = moment.time() >= self.thresholds.expected_by

        results = []
        for broker in self.inventory.brokers():
            meta = self.redis_reader.get_json(f'{broker}:instruments:meta')
            results.append(
                self._judge_dated(
                    f'{broker}:instruments',
                    broker,
                    'Instrument download',
                    meta,
                    'download_date',
                    'rows',
                    'instruments',
                    today,
                    expected_now,
                ),
            )
        mapping = self.redis_reader.get_json('unified:mapping:meta')
        results.append(
            self._judge_dated(
                'unified:mapping',
                UNIFIED_SUBJECT,
                'Instrument mapping',
                mapping,
                'mapping_date',
                'instruments',
                'instruments mapped',
                today,
                expected_now,
            ),
        )
        results.append(self._judge_prices(self.redis_reader.get_json('unified:prices:last_run')))
        return results

    def _judge_dated(
        self,
        identifier: str,
        subject: str,
        label: str,
        meta: Any,
        date_field: str,
        count_field: str,
        count_noun: str,
        today: str,
        expected_now: bool,
    ) -> CheckResult:
        """Judges a meta document that carries the date it was produced for.

        Args:
            identifier (str): The check identifier after the area.
            subject (str): The broker name or "unified".
            label (str): The human label.
            meta (Any): The parsed meta document, or None.
            date_field (str): The field holding the date, such as "download_date".
            count_field (str): The field holding the row count.
            count_noun (str): What the count counts, for the message.
            today (str): Today's India date as YYYY-MM-DD.
            expected_now (bool): Whether today's data should already exist.

        Returns:
            CheckResult: The result.
        """
        if not isinstance(meta, dict):
            status = CheckStatus.FAILURE if expected_now else CheckStatus.WARNING
            return self.result(
                identifier,
                subject,
                label,
                status,
                'No run is recorded in Redis.',
            )
        produced_for = meta.get(date_field)
        count = meta.get(count_field)
        details = {
            'date': produced_for,
            'count': count,
            'written_at': meta.get('written_at'),
        }
        count_text = ''
        if isinstance(count, int):
            count_text = f', {count:,} {count_noun}'
        if produced_for == today:
            status = CheckStatus.OK
            message = f'Done for today{count_text}.'
        elif expected_now:
            status = CheckStatus.FAILURE
            message = f'Today\'s run is missing; the latest is for {produced_for}.'
        else:
            status = CheckStatus.OK
            message = f'Latest run is for {produced_for}{count_text}; today\'s is not due yet.'
        return self.result(
            identifier,
            subject,
            label,
            status,
            message,
            details=details,
        )

    def _judge_prices(self, last_run: Any) -> CheckResult:
        """Judges the outcome of the last historical prices run.

        Args:
            last_run (Any): The parsed `unified:prices:last_run` document, or None.

        Returns:
            CheckResult: The prices run result.
        """
        label = 'Historical prices run'
        if not isinstance(last_run, dict):
            return self.result(
                'unified:prices',
                UNIFIED_SUBJECT,
                label,
                CheckStatus.WARNING,
                'No prices run is recorded in Redis.',
            )
        exit_code = last_run.get('exit_code')
        failed_steps = []
        for step in last_run.get('steps') or []:
            if isinstance(step, dict) and step.get('exit_code') not in (0, None):
                failed_steps.append(f'{step.get("step")} (exit {step.get("exit_code")})')
        finished = last_run.get('finished')
        details = {
            'step': last_run.get('step'),
            'started': last_run.get('started'),
            'finished': finished,
            'exit_code': exit_code,
            'failed_steps': failed_steps,
        }
        finished_text = f'finished {finished}' if finished else 'has no finish time'
        if exit_code not in (0, None):
            status = CheckStatus.FAILURE
            message = f'The last run failed with exit code {exit_code}; it {finished_text}.'
        elif failed_steps:
            status = CheckStatus.WARNING
            message = f'The last run {finished_text} with failed steps: {", ".join(failed_steps)}.'
        else:
            status = CheckStatus.OK
            message = f'The last run {finished_text} successfully.'
        return self.result(
            'unified:prices',
            UNIFIED_SUBJECT,
            label,
            status,
            message,
            details=details,
        )
