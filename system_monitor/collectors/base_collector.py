"""The behaviour every collector shares: running safely and building results.

A subclass sets `name` and `area`, and implements `collect()`. `run_once()` wraps `collect()` so that an exception in one collector becomes an error in its outcome instead of stopping the scheduler.

Typical usage example:

  class ExampleCollector(BaseCollector):
      name = 'example'
      area = CheckArea.SERVICES

      def collect(self):
          return [self.result('thing', 'platform', 'Thing', CheckStatus.OK, 'Fine')]
"""

import logging
import time
from typing import Any

from system_monitor.checks.check_result import (
    CheckArea,
    CheckResult,
    CheckStatus,
    CollectionOutcome,
)
from system_monitor.utilities.clock import SystemClock

_LOGGER = logging.getLogger(__name__)


class BaseCollector:
    """A collector of one kind of check.

    Attributes:
        name: The collector's name, set by each subclass.
        area: The dashboard area of the collector's checks, set by each subclass.
        interval_seconds: How long to wait between runs.
        clock: The source of the current time.
    """

    name = 'base'
    area = CheckArea.MONITOR

    def __init__(self, interval_seconds: float, clock: SystemClock):
        """Creates the collector.

        Args:
            interval_seconds (float): How long to wait between runs.
            clock (SystemClock): The source of the current time.
        """
        self.interval_seconds = interval_seconds
        self.clock = clock

    def collect(self) -> list[CheckResult]:
        """Reads the sources and judges them.

        Returns:
            list[CheckResult]: The checks produced by this run.

        Raises:
            NotImplementedError: The subclass did not implement it.
        """
        raise NotImplementedError

    def run_once(self) -> CollectionOutcome:
        """Runs collect() and captures any exception.

        Returns:
            CollectionOutcome: The results, or the error that stopped the run.
        """
        started_at = self.clock.now()
        started = time.perf_counter()
        error_text = None
        results = []
        try:
            results = self.collect()
        except Exception as error:
            _LOGGER.exception('Collector %s failed', self.name)
            error_text = f'{type(error).__name__}: {error}'
        return CollectionOutcome(
            collector_name=self.name,
            results=results,
            error=error_text,
            started_at=started_at,
            duration_seconds=time.perf_counter() - started,
        )

    def result(
        self,
        identifier: str,
        subject: str,
        label: str,
        status: CheckStatus,
        message: str,
        value: float | None = None,
        details: dict[str, Any] | None = None,
    ) -> CheckResult:
        """Builds a result in this collector's area.

        Args:
            identifier (str): The part of the check id after the area, such as "zerodha-instruments@websocket_quotes.service".
            subject (str): The broker name, "unified" or "platform".
            label (str): The short human label.
            status (CheckStatus): The judgement.
            message (str): One sentence explaining the judgement.
            value (float | None): The main measured number, or None.
            details (dict[str, Any] | None): Further readings, or None for none.

        Returns:
            CheckResult: The result, with check_id "<area>:<identifier>".
        """
        if details is None:
            details = {}
        return CheckResult(
            check_id=f'{self.area}:{identifier}',
            area=self.area,
            subject=subject,
            name=label,
            status=status,
            message=message,
            value=value,
            details=details,
        )
