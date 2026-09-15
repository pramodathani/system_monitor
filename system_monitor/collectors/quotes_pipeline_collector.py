"""Checks the unified quotes pipeline: its statistics heartbeat and stale live quotes.

`bin/unified/quotes` writes `unified:quotes:stats` every ten seconds with running counters. The collector turns the counters into rates, and every half minute it scans `unified:quotes:live` for quotes marked stale while their market is open.

Typical usage example:

  collector = QuotesPipelineCollector(redis_reader, inventory, market_calendar, thresholds.quotes_pipeline, clock)
  outcome = collector.run_once()
"""

import json
from typing import Any

from system_monitor.checks.check_result import CheckArea, CheckResult, CheckStatus
from system_monitor.collectors.base_collector import BaseCollector
from system_monitor.configuration.thresholds import QuotesPipelineThresholds
from system_monitor.sources.market_calendar import MarketCalendar
from system_monitor.sources.redis_reader import RedisReader
from system_monitor.sources.tick_exchange_classifier import TickExchangeClassifier
from system_monitor.sources.unit_inventory import UNIFIED_SUBJECT, UnitInventory
from system_monitor.utilities.clock import SystemClock
from system_monitor.utilities.text_formatter import TextFormatter

_STATS_KEY = 'unified:quotes:stats'
_LIVE_KEY = 'unified:quotes:live'


class QuotesPipelineCollector(BaseCollector):
    """Judges the unified quotes pipeline."""

    name = 'quotes_pipeline'
    area = CheckArea.QUOTES_PIPELINE

    def __init__(
        self,
        redis_reader: RedisReader,
        inventory: UnitInventory,
        market_calendar: MarketCalendar,
        thresholds: QuotesPipelineThresholds,
        clock: SystemClock,
        interval_seconds: float = 10.0,
    ):
        """Creates the collector.

        Args:
            redis_reader (RedisReader): Reads the statistics and live quotes.
            inventory (UnitInventory): Says whether the unified quotes service exists.
            market_calendar (MarketCalendar): Says whether a stale quote's market is open.
            thresholds (QuotesPipelineThresholds): The heartbeat age limit and scan interval.
            clock (SystemClock): The source of the current time.
            interval_seconds (float): How long to wait between runs.
        """
        super().__init__(interval_seconds, clock)
        self.redis_reader = redis_reader
        self.inventory = inventory
        self.market_calendar = market_calendar
        self.thresholds = thresholds
        self.classifier = TickExchangeClassifier()
        self._previous_stats = None
        self._previous_rates = {}
        self._stale_result = None
        self._stale_scanned_at = None

    def collect(self) -> list[CheckResult]:
        """Reads and judges the pipeline statistics and, when due, the stale quotes.

        Returns:
            list[CheckResult]: The statistics result and the stale quotes result, or nothing when UBI runs no unified quotes service.

        Raises:
            redis.RedisError: Redis could not be read.
            ValueError: The statistics document is not JSON.
        """
        if not self.inventory.has_unit('unified@quotes.service'):
            return []
        now = self.clock.now()
        results = [
            self._judge_stats(now),
        ]
        due = self._stale_scanned_at is None or now - self._stale_scanned_at >= self.thresholds.stale_scan_interval_seconds
        if due:
            self._stale_result = self._judge_stale_quotes(now)
            self._stale_scanned_at = now
        results.append(self._stale_result)
        return results

    def _judge_stats(self, now: float) -> CheckResult:
        """Judges the statistics heartbeat and computes rates.

        Args:
            now (float): The current time, in epoch seconds.

        Returns:
            CheckResult: The pipeline statistics result.
        """
        label = 'Quotes pipeline'
        stats = self.redis_reader.get_json(_STATS_KEY)
        if not isinstance(stats, dict):
            return self.result(
                'stats',
                UNIFIED_SUBJECT,
                label,
                CheckStatus.FAILURE,
                f'{_STATS_KEY} is missing; bin/unified/quotes has not written statistics.',
            )
        written_at = stats.get('at')
        age = None
        if isinstance(written_at, (int, float)):
            age = now - written_at
        counters = self._counters(stats)
        rates = self._rates(counters, written_at)
        undecodable_increase = self._increase('undecodable', counters)
        self._previous_stats = (written_at, counters)

        details = {
            'at': written_at,
            'age_seconds': age,
            'counters': counters,
            'rates': rates,
            'plans': stats.get('plans'),
            'mapping_date': stats.get('mapping_date'),
        }
        written_rate = rates.get('written')
        received_rate = rates.get('received')

        if age is None or age > self.thresholds.stats_failure_age_seconds:
            age_text = 'of unknown age' if age is None else f'{TextFormatter.duration(age)} old'
            status = CheckStatus.FAILURE
            message = f'The pipeline statistics are {age_text}; bin/unified/quotes may be stuck.'
        elif undecodable_increase > 0:
            status = CheckStatus.WARNING
            message = f'{TextFormatter.count(undecodable_increase, "tick")} could not be decoded since the last reading.'
        elif written_rate is not None and received_rate is not None:
            status = CheckStatus.OK
            message = f'{written_rate:.1f} quotes/s written from {received_rate:.1f} ticks/s received.'
        else:
            status = CheckStatus.OK
            message = 'Statistics are current; rates appear after the next reading.'
        return self.result(
            'stats',
            UNIFIED_SUBJECT,
            label,
            status,
            message,
            value=written_rate,
            details=details,
        )

    def _judge_stale_quotes(self, now: float) -> CheckResult:
        """Counts live quotes marked stale, separating those whose market is open.

        Args:
            now (float): The current time, in epoch seconds.

        Returns:
            CheckResult: The stale quotes result.
        """
        total = 0
        stale_while_open = 0
        stale_while_closed = 0
        stale_by_broker = {}
        for _instrument_id, value in self.redis_reader.scan_hash(_LIVE_KEY):
            total += 1
            quote = self._parse(value)
            if quote is None or quote.get('stale') is not True:
                continue
            broker = str(quote.get('broker', 'unknown'))
            stale_by_broker[broker] = stale_by_broker.get(broker, 0) + 1
            calendar_key = self.classifier.calendar_key(quote.get('exchange'))
            calendar_keys = None
            if calendar_key is not None:
                calendar_keys = {
                    calendar_key,
                }
            if self.market_calendar.is_market_open(now, calendar_keys):
                stale_while_open += 1
            else:
                stale_while_closed += 1

        details = {
            'live_quotes': total,
            'stale_while_open': stale_while_open,
            'stale_while_closed': stale_while_closed,
            'stale_by_broker': stale_by_broker,
            'scanned_at': now,
        }
        if stale_while_open > 0:
            status = CheckStatus.WARNING
            message = f'{stale_while_open} of {total} live quotes are stale while their market is open.'
        elif stale_while_closed > 0:
            status = CheckStatus.OK
            message = f'{total} live quotes; {stale_while_closed} are stale only because their market is closed.'
        else:
            status = CheckStatus.OK
            message = f'{total} live quotes, none stale.'
        return self.result(
            'stale_quotes',
            UNIFIED_SUBJECT,
            'Stale live quotes',
            status,
            message,
            value=float(stale_while_open),
            details=details,
        )

    def _counters(self, stats: dict[str, Any]) -> dict[str, int]:
        """Collects the numeric counters from a statistics document.

        Args:
            stats (dict[str, Any]): The statistics document.

        Returns:
            dict[str, int]: The pipeline counters plus "undecodable".
        """
        counters = {}
        pipeline = stats.get('pipeline')
        if isinstance(pipeline, dict):
            for counter_name, count in pipeline.items():
                if isinstance(count, int):
                    counters[counter_name] = count
        undecodable = stats.get('undecodable')
        if isinstance(undecodable, int):
            counters['undecodable'] = undecodable
        return counters

    def _rates(self, counters: dict[str, int], written_at: Any) -> dict[str, float]:
        """Works out per-second rates between this and the previous statistics document.

        The document's own `at` time is used, so a stuck writer produces no rate rather than a falling one.

        Args:
            counters (dict[str, int]): The current counters.
            written_at (Any): The document's `at` time.

        Returns:
            dict[str, float]: Rates per counter, or the previous rates when the document has not changed.
        """
        if self._previous_stats is None or not isinstance(written_at, (int, float)):
            return {}
        previous_at, previous_counters = self._previous_stats
        if not isinstance(previous_at, (int, float)):
            return {}
        elapsed = written_at - previous_at
        if elapsed <= 0:
            return self._previous_rates
        rates = {}
        for counter_name, count in counters.items():
            previous_count = previous_counters.get(counter_name)
            if previous_count is None or count < previous_count:
                continue
            rates[counter_name] = (count - previous_count) / elapsed
        self._previous_rates = rates
        return rates

    def _increase(self, counter_name: str, counters: dict[str, int]) -> int:
        """Measures how much one counter grew since the previous document.

        Args:
            counter_name (str): The counter.
            counters (dict[str, int]): The current counters.

        Returns:
            int: The growth, or 0 when it did not grow or cannot be compared.
        """
        if self._previous_stats is None:
            return 0
        previous_count = self._previous_stats[1].get(counter_name)
        count = counters.get(counter_name)
        if previous_count is None or count is None:
            return 0
        return max(0, count - previous_count)

    def _parse(self, value: str) -> dict[str, Any] | None:
        """Parses one stored quote.

        Args:
            value (str): The quote's JSON text.

        Returns:
            dict[str, Any] | None: The quote, or None when it is not a JSON object.
        """
        try:
            quote = json.loads(value)
        except ValueError:
            return None
        if not isinstance(quote, dict):
            return None
        return quote
