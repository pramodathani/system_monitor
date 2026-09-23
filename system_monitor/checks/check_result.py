"""The judgement one check makes about one part of UBI.

Collectors produce `CheckResult` objects, `MonitorState` stores them, and the front end only colours and arranges them.

Typical usage example:

  result = CheckResult(
      check_id='feeds:zerodha',
      area=CheckArea.FEEDS,
      subject='zerodha',
      name='Quote feed',
      status=CheckStatus.OK,
      message='12.5 ticks/s; last tick 0 s ago',
  )
"""

import dataclasses
import enum
from typing import Any


class CheckStatus(enum.StrEnum):
    """How healthy a checked thing is."""

    OK = 'ok'
    WARNING = 'warning'
    FAILURE = 'failure'
    IDLE = 'idle'
    UNKNOWN = 'unknown'


class CheckArea(enum.StrEnum):
    """Which part of the dashboard a check belongs to."""

    SERVICES = 'services'
    TIMERS = 'timers'
    SESSIONS = 'sessions'
    FEEDS = 'feeds'
    QUOTES_PIPELINE = 'quotes_pipeline'
    STREAMS = 'streams'
    PORTFOLIO = 'portfolio'
    REFERENCE_DATA = 'reference_data'
    DATA_STORES = 'data_stores'
    LOGS = 'logs'
    MONITOR = 'monitor'


@dataclasses.dataclass(frozen=True)
class CheckResult:
    """One check's latest judgement.

    Attributes:
        check_id: A stable identifier, such as "services:zerodha-instruments@websocket_quotes.service".
        area: The dashboard area the check belongs to.
        subject: The broker name, "unified", or "platform" for shared infrastructure.
        name: A short human label, such as "Quote feed".
        status: The judgement.
        message: One sentence explaining the judgement.
        value: The main measured number, such as ticks per second, or None.
        details: Further readings for the dashboard. It never holds an access token.
    """

    check_id: str
    area: CheckArea
    subject: str
    name: str
    status: CheckStatus
    message: str
    value: float | None = None
    details: dict[str, Any] = dataclasses.field(default_factory=dict)

    def to_dictionary(self) -> dict[str, Any]:
        """Converts the result to plain JSON-ready values.

        Returns:
            dict[str, Any]: The result's fields, with enums as their text values.
        """
        return {
            'check_id': self.check_id,
            'area': str(self.area),
            'subject': self.subject,
            'name': self.name,
            'status': str(self.status),
            'message': self.message,
            'value': self.value,
            'details': self.details,
        }


@dataclasses.dataclass(frozen=True)
class CollectionOutcome:
    """What one run of one collector produced.

    Attributes:
        collector_name: The collector's name, such as "services".
        results: The checks it produced; empty when it failed.
        error: A description of the exception that stopped it, or None when it succeeded.
        started_at: When the run started, in epoch seconds.
        duration_seconds: How long the run took.
    """

    collector_name: str
    results: list[CheckResult]
    error: str | None
    started_at: float
    duration_seconds: float
