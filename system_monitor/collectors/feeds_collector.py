"""Checks that each broker's quote feed, and the unified feed, keep ticking while their markets trade.

The newest entry ID of `<subject>:quotes:stream` is a millisecond timestamp, which gives the age of the last tick, and the stream's entries-added counter gives the tick rate. Which markets a feed covers is learned from the `exchange` field of the ticks in `<subject>:quotes:live`, so an NSE-only feed is idle, not failed, during the MCX evening session.

Typical usage example:

  collector = FeedsCollector(redis_reader, inventory, market_calendar, thresholds.feeds, clock)
  outcome = collector.run_once()
"""

import itertools
import json
from typing import Any

from system_monitor.checks.check_result import CheckArea, CheckResult, CheckStatus
from system_monitor.collectors.base_collector import BaseCollector
from system_monitor.configuration.thresholds import FeedThresholds
from system_monitor.sources.market_calendar import MarketCalendar
from system_monitor.sources.redis_reader import RedisReader
from system_monitor.sources.tick_exchange_classifier import TickExchangeClassifier
from system_monitor.sources.unit_inventory import UNIFIED_SUBJECT, UnitInventory
from system_monitor.utilities.clock import SystemClock
from system_monitor.utilities.text_formatter import TextFormatter

_EXCHANGE_SCAN_LIMIT = 2000


class FeedsCollector(BaseCollector):
    """Judges the age and rate of every quote stream."""

    name = 'feeds'
    area = CheckArea.FEEDS

    def __init__(
        self,
        redis_reader: RedisReader,
        inventory: UnitInventory,
        market_calendar: MarketCalendar,
        thresholds: FeedThresholds,
        clock: SystemClock,
        interval_seconds: float = 5.0,
        exchange_refresh_seconds: float = 300.0,
    ):
        """Creates the collector.

        Args:
            redis_reader (RedisReader): Reads the quote streams and live hashes.
            inventory (UnitInventory): Supplies the subjects that run a quotes service.
            market_calendar (MarketCalendar): Says when each market trades.
            thresholds (FeedThresholds): The age limits and the grace period after opening.
            clock (SystemClock): The source of the current time.
            interval_seconds (float): How long to wait between runs.
            exchange_refresh_seconds (float): How often to learn each feed's exchanges again.
        """
        super().__init__(interval_seconds, clock)
        self.redis_reader = redis_reader
        self.inventory = inventory
        self.market_calendar = market_calendar
        self.thresholds = thresholds
        self.exchange_refresh_seconds = exchange_refresh_seconds
        self.classifier = TickExchangeClassifier()
        self._previous_counts = {}
        self._calendar_keys = {}
        self._calendar_keys_read_at = {}

    def collect(self) -> list[CheckResult]:
        """Reads and judges every quote stream.

        Returns:
            list[CheckResult]: One result per subject with a quotes service.

        Raises:
            redis.RedisError: Redis could not be read.
        """
        self.market_calendar.refresh_if_due()
        now = self.clock.now()
        results = []
        for subject in self.inventory.subjects():
            if not self.inventory.has_script(subject, 'instruments', 'websocket_quotes'):
                continue
            results.append(self._judge(subject, now))
        return results

    def _judge(self, subject: str, now: float) -> CheckResult:
        """Judges one subject's quote stream.

        Args:
            subject (str): The broker name or "unified".
            now (float): The current time, in epoch seconds.

        Returns:
            CheckResult: The feed's result.
        """
        calendar_keys = self._calendar_keys_for(subject, now)
        market_open = self.market_calendar.is_market_open(now, calendar_keys)
        seconds_since_open = self.market_calendar.seconds_since_open(now, calendar_keys)
        limits = self.thresholds.limits_for(subject)
        label = 'Unified quote feed' if subject == UNIFIED_SUBJECT else 'Quote feed'

        stream = f'{subject}:quotes:stream'
        info = self.redis_reader.stream_info(stream)
        if info is None:
            status = CheckStatus.FAILURE if market_open else CheckStatus.IDLE
            return self.result(
                subject,
                subject,
                label,
                status,
                f'The stream {stream} does not exist in Redis.',
                details={
                    'market_open': market_open,
                },
            )

        last_tick_at = self._last_tick_epoch(info.get('last-generated-id', '0-0'))
        age = None
        if last_tick_at is not None:
            age = now - last_tick_at
        rate = self._rate(subject, info.get('entries-added'), now)
        exchanges = []
        if calendar_keys is not None:
            for exchange, calendar in sorted(calendar_keys):
                exchanges.append(f'{exchange} {calendar}')

        details = {
            'stream': stream,
            'last_tick_at': last_tick_at,
            'age_seconds': age,
            'ticks_per_second': rate,
            'stream_length': info.get('length'),
            'market_open': market_open,
            'exchanges': exchanges,
            'calendar_source': self.market_calendar.source(),
            'warning_age_seconds': limits.warning_age_seconds,
            'failure_age_seconds': limits.failure_age_seconds,
        }

        age_text = 'never'
        if age is not None:
            age_text = f'{TextFormatter.duration(age)} ago'
        rate_text = ''
        if rate is not None:
            rate_text = f'{rate:.1f} ticks/s; '

        in_grace = seconds_since_open is not None and seconds_since_open < self.thresholds.grace_after_open_seconds
        if not market_open:
            status = CheckStatus.IDLE
            message = f'Its markets are closed; last tick {age_text}.'
        elif age is not None and age <= limits.warning_age_seconds:
            status = CheckStatus.OK
            message = f'{rate_text}last tick {age_text}.'
        elif in_grace:
            status = CheckStatus.IDLE
            message = f'Markets opened {TextFormatter.duration(seconds_since_open)} ago; waiting for ticks (last tick {age_text}).'
        elif age is None or age > limits.failure_age_seconds:
            status = CheckStatus.FAILURE
            message = f'No tick while its markets are open; last tick {age_text}.'
        else:
            status = CheckStatus.WARNING
            message = f'Ticks are slow; last tick {age_text}.'

        return self.result(
            subject,
            subject,
            label,
            status,
            message,
            value=rate,
            details=details,
        )

    def _calendar_keys_for(self, subject: str, now: float) -> set[tuple[str, str]] | None:
        """Learns which exchange calendars a feed covers, refreshing every few minutes.

        Args:
            subject (str): The broker name or "unified".
            now (float): The current time, in epoch seconds.

        Returns:
            set[tuple[str, str]] | None: The (exchange, calendar) pairs seen in the live ticks, or None when none could be recognised, meaning every market counts.
        """
        read_at = self._calendar_keys_read_at.get(subject)
        if read_at is not None and now - read_at < self.exchange_refresh_seconds:
            return self._calendar_keys.get(subject)
        keys = set()
        live_ticks = self.redis_reader.scan_hash(f'{subject}:quotes:live')
        for _field, value in itertools.islice(live_ticks, _EXCHANGE_SCAN_LIMIT):
            key = self.classifier.calendar_key(self._exchange_of(value))
            if key is not None:
                keys.add(key)
        learned = keys or None
        self._calendar_keys[subject] = learned
        self._calendar_keys_read_at[subject] = now
        return learned

    def _exchange_of(self, value: str) -> Any:
        """Reads the exchange field of a stored tick.

        Args:
            value (str): The tick's JSON text.

        Returns:
            Any: The exchange value, or None when the tick is not JSON or has none.
        """
        try:
            tick = json.loads(value)
        except ValueError:
            return None
        if not isinstance(tick, dict):
            return None
        return tick.get('exchange')

    def _last_tick_epoch(self, stream_id: str) -> float | None:
        """Reads the time of a stream entry from its ID.

        Args:
            stream_id (str): An ID such as "1789464187238-1".

        Returns:
            float | None: The entry's time in epoch seconds, or None for "0-0" or an unreadable ID.
        """
        milliseconds_text = str(stream_id).split('-', 1)[0]
        try:
            milliseconds = int(milliseconds_text)
        except ValueError:
            return None
        if milliseconds == 0:
            return None
        return milliseconds / 1000

    def _rate(self, subject: str, entries_added: Any, now: float) -> float | None:
        """Works out ticks per second from the change in the entries-added counter.

        Args:
            subject (str): The broker name or "unified".
            entries_added (Any): The stream's entries-added counter.
            now (float): The current time, in epoch seconds.

        Returns:
            float | None: Ticks per second since the previous run, or None on the first run or after the counter went backwards.
        """
        if not isinstance(entries_added, int):
            return None
        previous = self._previous_counts.get(subject)
        self._previous_counts[subject] = (now, entries_added)
        if previous is None:
            return None
        previous_time, previous_count = previous
        elapsed = now - previous_time
        if elapsed <= 0 or entries_added < previous_count:
            return None
        return (entries_added - previous_count) / elapsed
