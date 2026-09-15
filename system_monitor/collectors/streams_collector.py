"""Checks that every Redis stream's consumer groups keep up.

Streams are trimmed to an approximate cap. A group whose lag approaches the cap is about to lose entries it has not read, which for a persister means rows missing from TimescaleDB.

Typical usage example:

  collector = StreamsCollector(redis_reader, inventory, thresholds.streams, clock)
  outcome = collector.run_once()
"""

from typing import Any

from system_monitor.checks.check_result import CheckArea, CheckResult, CheckStatus
from system_monitor.collectors.base_collector import BaseCollector
from system_monitor.configuration.thresholds import StreamThresholds
from system_monitor.sources.redis_reader import RedisReader
from system_monitor.sources.unit_inventory import UNIFIED_SUBJECT, UnitInventory
from system_monitor.utilities.clock import SystemClock

_STREAM_KINDS = [
    (
        'quotes',
        'quotes:stream',
        'Quotes stream',
    ),
    (
        'order_updates',
        'order-updates:stream',
        'Order updates stream',
    ),
    (
        'positions_updates',
        'positions_updates:stream',
        'Position updates stream',
    ),
]


class StreamsCollector(BaseCollector):
    """Judges consumer group lag and pending counts on every UBI stream."""

    name = 'streams'
    area = CheckArea.STREAMS

    def __init__(
        self,
        redis_reader: RedisReader,
        inventory: UnitInventory,
        thresholds: StreamThresholds,
        clock: SystemClock,
        interval_seconds: float = 10.0,
    ):
        """Creates the collector.

        Args:
            redis_reader (RedisReader): Reads stream and group information.
            inventory (UnitInventory): Supplies the subject names.
            thresholds (StreamThresholds): The lag fractions, pending limit and caps.
            clock (SystemClock): The source of the current time.
            interval_seconds (float): How long to wait between runs.
        """
        super().__init__(interval_seconds, clock)
        self.redis_reader = redis_reader
        self.inventory = inventory
        self.thresholds = thresholds

    def collect(self) -> list[CheckResult]:
        """Reads and judges every existing stream's groups.

        Returns:
            list[CheckResult]: One result per consumer group, and one per stream that has no groups.

        Raises:
            redis.RedisError: Redis could not be read.
        """
        results = []
        for subject in self.inventory.subjects():
            for kind, key_suffix, label in _STREAM_KINDS:
                stream = f'{subject}:{key_suffix}'
                info = self.redis_reader.stream_info(stream)
                if info is None:
                    continue
                owner = 'unified' if subject == UNIFIED_SUBJECT else 'broker'
                cap = self.thresholds.cap_for(f'{owner}_{kind}')
                groups = self.redis_reader.stream_groups(stream)
                if not groups:
                    results.append(
                        self.result(
                            stream,
                            subject,
                            label,
                            CheckStatus.WARNING,
                            'No consumer group reads this stream, so nothing persists or combines it.',
                            details={
                                'stream': stream,
                                'length': info.get('length'),
                                'cap': cap,
                            },
                        ),
                    )
                    continue
                for group in groups:
                    results.append(self._judge_group(subject, stream, label, info, group, cap))
        return results

    def _judge_group(
        self,
        subject: str,
        stream: str,
        label: str,
        info: dict[str, Any],
        group: dict[str, Any],
        cap: int,
    ) -> CheckResult:
        """Judges one consumer group.

        Args:
            subject (str): The broker name or "unified".
            stream (str): The stream key.
            label (str): The stream's human label.
            info (dict[str, Any]): The stream's XINFO STREAM reply.
            group (dict[str, Any]): The group's XINFO GROUPS entry.
            cap (int): The stream's approximate length cap.

        Returns:
            CheckResult: The group's result.
        """
        group_name = str(group.get('name', ''))
        lag = group.get('lag')
        pending = group.get('pending') or 0
        consumers = group.get('consumers') or 0
        warning_lag = cap * self.thresholds.warning_lag_fraction
        failure_lag = cap * self.thresholds.failure_lag_fraction
        details = {
            'stream': stream,
            'group': group_name,
            'lag': lag,
            'pending': pending,
            'consumers': consumers,
            'length': info.get('length'),
            'cap': cap,
            'last_delivered_id': group.get('last-delivered-id'),
            'last_generated_id': info.get('last-generated-id'),
        }

        if lag is None:
            status = CheckStatus.WARNING
            message = 'The lag cannot be measured because entries were trimmed or deleted past the group.'
        elif lag >= failure_lag:
            status = CheckStatus.FAILURE
            message = f'{lag:,} entries behind with a cap of {cap:,}; unread entries will be trimmed and lost.'
        elif lag >= warning_lag:
            status = CheckStatus.WARNING
            message = f'{lag:,} entries behind with a cap of {cap:,}.'
        elif pending > self.thresholds.pending_warning:
            status = CheckStatus.WARNING
            message = f'{pending:,} entries were delivered but not acknowledged.'
        elif consumers == 0 and lag > 0:
            status = CheckStatus.WARNING
            message = f'No consumer is connected and {lag:,} entries are waiting.'
        else:
            status = CheckStatus.OK
            message = f'Up to date: {lag:,} behind, {pending:,} pending.'

        value = None
        if lag is not None:
            value = float(lag)
        return self.result(
            f'{stream}:{group_name}',
            subject,
            f'{label}, {group_name} group',
            status,
            message,
            value=value,
            details=details,
        )
