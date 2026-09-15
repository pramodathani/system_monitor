"""Runs every collector on its own interval and passes the outcomes on.

Collectors are ordinary blocking code, so each run happens in a worker thread while the event loop keeps serving web requests.

Typical usage example:

  scheduler = CollectorScheduler(collectors, state, listeners=[alert_policy])
  await scheduler.run()
"""

import asyncio
import logging
import time
from collections.abc import Sequence
from typing import Protocol

from system_monitor.checks.check_result import CheckResult, CollectionOutcome
from system_monitor.collectors.base_collector import BaseCollector
from system_monitor.state.monitor_state import MonitorState

_LOGGER = logging.getLogger(__name__)
_MINIMUM_SLEEP_SECONDS = 1.0


class ResultListener(Protocol):
    """Something that wants every batch of results, such as the alert policy."""

    def observe(self, results: list[CheckResult]) -> None:
        """Receives one collector's latest results.

        Args:
            results (list[CheckResult]): The results.
        """


class CollectorScheduler:
    """Keeps every collector running forever."""

    def __init__(
        self,
        collectors: Sequence[BaseCollector],
        state: MonitorState,
        listeners: Sequence[ResultListener] = (),
    ):
        """Creates the scheduler.

        Args:
            collectors (Sequence[BaseCollector]): The collectors to run.
            state (MonitorState): Receives every outcome.
            listeners (Sequence[ResultListener]): Also receive every successful run's results.
        """
        self.collectors = collectors
        self.state = state
        self.listeners = listeners

    async def run(self) -> None:
        """Runs every collector on its interval until cancelled."""
        async with asyncio.TaskGroup() as task_group:
            for collector in self.collectors:
                task_group.create_task(self._run_forever(collector))

    async def run_all_once(self) -> None:
        """Runs every collector once, concurrently, and applies the outcomes."""
        tasks = []
        for collector in self.collectors:
            tasks.append(self._run_one(collector))
        await asyncio.gather(*tasks)

    async def _run_forever(self, collector: BaseCollector) -> None:
        """Runs one collector, waits for its interval, and repeats.

        Args:
            collector (BaseCollector): The collector.
        """
        while True:
            started = time.monotonic()
            await self._run_one(collector)
            elapsed = time.monotonic() - started
            await asyncio.sleep(max(_MINIMUM_SLEEP_SECONDS, collector.interval_seconds - elapsed))

    async def _run_one(self, collector: BaseCollector) -> CollectionOutcome:
        """Runs one collector in a worker thread and hands its outcome on.

        Args:
            collector (BaseCollector): The collector.

        Returns:
            CollectionOutcome: The run's outcome.
        """
        outcome = await asyncio.to_thread(collector.run_once)
        self.state.apply(outcome)
        if outcome.error is None:
            for listener in self.listeners:
                try:
                    listener.observe(outcome.results)
                except Exception:
                    _LOGGER.exception('Result listener %r failed', listener)
        return outcome
