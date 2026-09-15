"""Holds the latest result of every check, when each status began, and recent numeric history.

Each collector's outcome replaces that collector's previous results as a set, so a unit removed from UBI disappears from the dashboard. When a collector fails, its previous results are kept but marked unknown, so the page shows what is stale instead of going blank.

Typical usage example:

  state = MonitorState(SystemClock())
  state.apply(collector.run_once())
  snapshot = state.snapshot()
"""

import collections
import dataclasses
import threading
from typing import Any

from system_monitor.checks.check_result import (
    CheckArea,
    CheckResult,
    CheckStatus,
    CollectionOutcome,
)
from system_monitor.utilities.clock import SystemClock

_HISTORY_AREAS = (
    CheckArea.FEEDS,
    CheckArea.QUOTES_PIPELINE,
    CheckArea.STREAMS,
)


@dataclasses.dataclass(frozen=True)
class StoredCheck:
    """A check result with the times the state knows about it.

    Attributes:
        result: The latest result.
        status_since: When the check entered its current status, in epoch seconds.
        observed_at: When the result was produced, in epoch seconds.
        collector_name: The collector that produced it.
    """

    result: CheckResult
    status_since: float
    observed_at: float
    collector_name: str


class MonitorState:
    """The shared, thread-safe store of check results.

    Attributes:
        version: A number that grows every time results change.
    """

    def __init__(
        self,
        clock: SystemClock,
        history_seconds: float = 900.0,
        history_resolution_seconds: float = 10.0,
    ):
        """Creates an empty state.

        Args:
            clock (SystemClock): The source of the current time.
            history_seconds (float): How much numeric history to keep per check.
            history_resolution_seconds (float): The shortest gap between two history points.
        """
        self.clock = clock
        self.history_seconds = history_seconds
        self.history_resolution_seconds = history_resolution_seconds
        self.version = 0
        self._lock = threading.Lock()
        self._checks_by_collector = {}
        self._history = {}
        self._collector_runs = {}

    def apply(self, outcome: CollectionOutcome) -> None:
        """Replaces one collector's results with a new outcome.

        Args:
            outcome (CollectionOutcome): The collector's latest run.
        """
        now = self.clock.now()
        with self._lock:
            previous = self._checks_by_collector.get(outcome.collector_name, {})
            if outcome.error is None:
                results = outcome.results
            else:
                results = self._results_after_failure(outcome, previous)

            stored = {}
            for result in results:
                earlier = previous.get(result.check_id)
                status_since = now
                if earlier is not None and earlier.result.status == result.status:
                    status_since = earlier.status_since
                stored[result.check_id] = StoredCheck(
                    result=result,
                    status_since=status_since,
                    observed_at=now,
                    collector_name=outcome.collector_name,
                )
                if outcome.error is None:
                    self._record_history(result, now)

            for check_id in previous:
                if check_id not in stored:
                    self._history.pop(check_id, None)

            self._checks_by_collector[outcome.collector_name] = stored
            self._collector_runs[outcome.collector_name] = {
                'name': outcome.collector_name,
                'started_at': outcome.started_at,
                'duration_seconds': outcome.duration_seconds,
                'error': outcome.error,
                'check_count': len(stored),
            }
            self.version += 1

    def results(self) -> list[CheckResult]:
        """Lists every current result.

        Returns:
            list[CheckResult]: The results of every collector.
        """
        with self._lock:
            results = []
            for stored_checks in self._checks_by_collector.values():
                for stored in stored_checks.values():
                    results.append(stored.result)
            return results

    def snapshot(self) -> dict[str, Any]:
        """Builds the JSON-ready view the dashboard receives.

        Returns:
            dict[str, Any]: The version, generation time, every check with its times and history, and each collector's last run.
        """
        now = self.clock.now()
        with self._lock:
            checks = []
            for stored_checks in self._checks_by_collector.values():
                for stored in stored_checks.values():
                    entry = stored.result.to_dictionary()
                    entry['status_since'] = stored.status_since
                    entry['observed_at'] = stored.observed_at
                    entry['collector'] = stored.collector_name
                    history = self._history.get(stored.result.check_id)
                    if history:
                        points = []
                        for timestamp, value in history:
                            points.append(
                                [
                                    timestamp,
                                    value,
                                ],
                            )
                        entry['history'] = points
                    checks.append(entry)
            checks.sort(key=self._sort_key)
            collectors = []
            for name in sorted(self._collector_runs):
                collectors.append(dict(self._collector_runs[name]))
            return {
                'version': self.version,
                'generated_at': now,
                'checks': checks,
                'collectors': collectors,
            }

    def _results_after_failure(
        self,
        outcome: CollectionOutcome,
        previous: dict[str, StoredCheck],
    ) -> list[CheckResult]:
        """Keeps a failed collector's earlier results, marked unknown, plus one result naming the error.

        Args:
            outcome (CollectionOutcome): The failed run.
            previous (dict[str, StoredCheck]): The collector's earlier results.

        Returns:
            list[CheckResult]: The results to store.
        """
        results = []
        for stored in previous.values():
            if stored.result.area == CheckArea.MONITOR:
                continue
            results.append(
                dataclasses.replace(
                    stored.result,
                    status=CheckStatus.UNKNOWN,
                    message=f'Not updated because the {outcome.collector_name} collector failed; last known: {stored.result.message}',
                ),
            )
        results.append(
            CheckResult(
                check_id=f'monitor:{outcome.collector_name}',
                area=CheckArea.MONITOR,
                subject='monitor',
                name=f'{outcome.collector_name} collector',
                status=CheckStatus.UNKNOWN,
                message=f'The collector failed: {outcome.error}',
            ),
        )
        return results

    def _record_history(self, result: CheckResult, now: float) -> None:
        """Adds a result's value to its history when the area keeps history.

        Args:
            result (CheckResult): The result.
            now (float): The current time, in epoch seconds.
        """
        if result.area not in _HISTORY_AREAS or result.value is None:
            return
        history = self._history.get(result.check_id)
        if history is None:
            history = collections.deque()
            self._history[result.check_id] = history
        if history and now - history[-1][0] < self.history_resolution_seconds:
            return
        history.append((now, result.value))
        while history and history[0][0] < now - self.history_seconds:
            history.popleft()

    @staticmethod
    def _sort_key(entry: dict[str, Any]) -> tuple[str, str, str]:
        """Orders checks by area, subject and name.

        Args:
            entry (dict[str, Any]): A check as built for the snapshot.

        Returns:
            tuple[str, str, str]: The sort key.
        """
        return (entry['area'], entry['subject'], entry['name'])
