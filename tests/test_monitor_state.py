"""Tests for MonitorState and CollectorScheduler."""

import asyncio

from system_monitor.checks.check_result import (
    CheckArea,
    CheckResult,
    CheckStatus,
    CollectionOutcome,
)
from system_monitor.collectors.base_collector import BaseCollector
from system_monitor.state.collector_scheduler import CollectorScheduler
from system_monitor.state.monitor_state import MonitorState
from tests.fakes import FixedClock


class _Builder:
    """Builds minimal results and outcomes for these tests."""

    @staticmethod
    def result(check_id: str, status: CheckStatus, area: CheckArea = CheckArea.FEEDS, value: float | None = None) -> CheckResult:
        """Builds a minimal result.

        Args:
            check_id (str): The check id.
            status (CheckStatus): The status.
            area (CheckArea): The area.
            value (float | None): The value.

        Returns:
            CheckResult: The result.
        """
        return CheckResult(
            check_id=check_id,
            area=area,
            subject='zerodha',
            name=check_id,
            status=status,
            message='message',
            value=value,
        )

    @staticmethod
    def outcome(results: list[CheckResult], error: str | None = None) -> CollectionOutcome:
        """Builds an outcome for a collector named "feeds".

        Args:
            results (list[CheckResult]): The results.
            error (str | None): The error, or None.

        Returns:
            CollectionOutcome: The outcome.
        """
        return CollectionOutcome(
            collector_name='feeds',
            results=results,
            error=error,
            started_at=0,
            duration_seconds=0.01,
        )


class TestMonitorState:
    """Tests for MonitorState."""

    def _checks(self, state: MonitorState) -> dict:
        """Indexes the snapshot's checks.

        Args:
            state (MonitorState): The state.

        Returns:
            dict: The snapshot checks keyed by check_id.
        """
        indexed = {}
        for check in state.snapshot()['checks']:
            indexed[check['check_id']] = check
        return indexed

    def test_apply_keeps_status_since_until_status_changes(self):
        """Checks that the status start time moves only when the status changes.

        Raises:
            AssertionError: A time is wrong.
        """
        clock = FixedClock(100.0)
        state = MonitorState(clock)
        state.apply(_Builder.outcome([_Builder.result('feeds:a', CheckStatus.OK)]))
        clock.advance(10)
        state.apply(_Builder.outcome([_Builder.result('feeds:a', CheckStatus.OK)]))
        assert self._checks(state)['feeds:a']['status_since'] == 100.0
        clock.advance(10)
        state.apply(_Builder.outcome([_Builder.result('feeds:a', CheckStatus.FAILURE)]))
        assert self._checks(state)['feeds:a']['status_since'] == 120.0
        assert state.version == 3

    def test_apply_removes_vanished_checks(self):
        """Checks that a check missing from a new outcome disappears.

        Raises:
            AssertionError: The old check remains.
        """
        state = MonitorState(FixedClock(0))
        state.apply(
            _Builder.outcome(
                [
                    _Builder.result('feeds:a', CheckStatus.OK),
                    _Builder.result('feeds:b', CheckStatus.OK),
                ],
            ),
        )
        state.apply(_Builder.outcome([_Builder.result('feeds:a', CheckStatus.OK)]))
        assert set(self._checks(state)) == {
            'feeds:a',
        }

    def test_apply_failure_marks_previous_results_unknown(self):
        """Checks that a failed collector keeps its checks as unknown and adds a monitor check.

        Raises:
            AssertionError: The stored results are wrong.
        """
        state = MonitorState(FixedClock(0))
        state.apply(_Builder.outcome([_Builder.result('feeds:a', CheckStatus.OK)]))
        state.apply(_Builder.outcome([], error='ConnectionError: refused'))
        checks = self._checks(state)
        assert checks['feeds:a']['status'] == 'unknown'
        assert checks['monitor:feeds']['status'] == 'unknown'
        assert 'refused' in checks['monitor:feeds']['message']
        state.apply(_Builder.outcome([_Builder.result('feeds:a', CheckStatus.OK)]))
        assert 'monitor:feeds' not in self._checks(state)

    def test_apply_records_history_at_resolution(self):
        """Checks that history keeps one point per resolution step and only for history areas.

        Raises:
            AssertionError: The history is wrong.
        """
        clock = FixedClock(0.0)
        state = MonitorState(clock, history_seconds=60, history_resolution_seconds=10)
        for value in range(10):
            state.apply(
                _Builder.outcome(
                    [
                        _Builder.result('feeds:a', CheckStatus.OK, value=float(value)),
                        _Builder.result('services:x', CheckStatus.OK, area=CheckArea.SERVICES, value=1.0),
                    ],
                ),
            )
            clock.advance(5)
        checks = self._checks(state)
        assert checks['feeds:a']['history'] == [
            [
                0.0,
                0.0,
            ],
            [
                10.0,
                2.0,
            ],
            [
                20.0,
                4.0,
            ],
            [
                30.0,
                6.0,
            ],
            [
                40.0,
                8.0,
            ],
        ]
        assert 'history' not in checks['services:x']


class _CountingCollector(BaseCollector):
    """A collector that returns one ok result."""

    name = 'feeds'
    area = CheckArea.FEEDS

    def collect(self) -> list[CheckResult]:
        """Returns one result.

        Returns:
            list[CheckResult]: The result.
        """
        return [
            _Builder.result('feeds:a', CheckStatus.OK),
        ]


class _BrokenCollector(BaseCollector):
    """A collector that always raises."""

    name = 'broken'
    area = CheckArea.STREAMS

    def collect(self) -> list[CheckResult]:
        """Raises an error.

        Returns:
            list[CheckResult]: Never returns.

        Raises:
            RuntimeError: Always.
        """
        raise RuntimeError('boom')


class _RecordingListener:
    """A listener that remembers what it observed."""

    def __init__(self):
        """Creates an empty listener."""
        self.observed = []

    def observe(self, results: list[CheckResult]) -> None:
        """Records results.

        Args:
            results (list[CheckResult]): The results.
        """
        self.observed.append(results)


class TestCollectorScheduler:
    """Tests for CollectorScheduler."""

    def test_run_all_once_applies_outcomes_and_notifies_listeners(self):
        """Checks that outcomes reach the state and only successful ones reach listeners.

        Raises:
            AssertionError: The state or listener is wrong.
        """
        clock = FixedClock(0)
        state = MonitorState(clock)
        listener = _RecordingListener()
        scheduler = CollectorScheduler(
            [
                _CountingCollector(5, clock),
                _BrokenCollector(5, clock),
            ],
            state,
            [
                listener,
            ],
        )
        asyncio.run(scheduler.run_all_once())
        snapshot = state.snapshot()
        check_ids = set()
        for check in snapshot['checks']:
            check_ids.add(check['check_id'])
        assert check_ids == {
            'feeds:a',
            'monitor:broken',
        }
        assert len(listener.observed) == 1
        errors = {}
        for collector in snapshot['collectors']:
            errors[collector['name']] = collector['error']
        assert errors == {
            'broken': 'RuntimeError: boom',
            'feeds': None,
        }
