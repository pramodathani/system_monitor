"""The limits every check compares its readings against, loaded from thresholds.toml.

Each section of the file becomes one small dataclass, and `Thresholds` holds one of each. A missing key fails at startup with the section and key named, rather than at the first reading.

Typical usage example:

  thresholds = Thresholds.load(Path('thresholds.toml'))
  print(thresholds.feeds.warning_age_seconds)
"""

import dataclasses
import datetime
import tomllib
from pathlib import Path
from typing import Any


class _SectionReader:
    """Reads typed values out of one section of the thresholds file."""

    def __init__(self, section_name: str, values: dict[str, Any]):
        """Wraps one section's values.

        Args:
            section_name (str): The section name, used in error messages.
            values (dict[str, Any]): The section's keys and values.
        """
        self.section_name = section_name
        self.values = values

    def number(self, key: str) -> float:
        """Reads a number.

        Args:
            key (str): The key to read.

        Returns:
            float: The value as a float.

        Raises:
            ValueError: The key is missing or its value is not a number.
        """
        value = self._value(key)
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ValueError(f'Not a number in thresholds [{self.section_name}]: {key}={value!r}')
        return float(value)

    def whole_number(self, key: str) -> int:
        """Reads a whole number.

        Args:
            key (str): The key to read.

        Returns:
            int: The value.

        Raises:
            ValueError: The key is missing or its value is not a whole number.
        """
        value = self._value(key)
        if isinstance(value, bool) or not isinstance(value, int):
            raise ValueError(f'Not a whole number in thresholds [{self.section_name}]: {key}={value!r}')
        return value

    def clock_time(self, key: str) -> datetime.time:
        """Reads a time of day written as "HH:MM".

        Args:
            key (str): The key to read.

        Returns:
            datetime.time: The time of day.

        Raises:
            ValueError: The key is missing or its value is not a "HH:MM" time.
        """
        value = self._value(key)
        try:
            return datetime.time.fromisoformat(value)
        except (TypeError, ValueError) as error:
            raise ValueError(f'Not an HH:MM time in thresholds [{self.section_name}]: {key}={value!r}') from error

    def table(self, key: str) -> dict[str, Any]:
        """Reads a nested table, which may be absent.

        Args:
            key (str): The key to read.

        Returns:
            dict[str, Any]: The nested table, or an empty dictionary when it is absent.

        Raises:
            ValueError: The value is present but is not a table.
        """
        value = self.values.get(key, {})
        if not isinstance(value, dict):
            raise ValueError(f'Not a table in thresholds [{self.section_name}]: {key}={value!r}')
        return value

    def _value(self, key: str) -> Any:
        """Reads a raw value that must be present.

        Args:
            key (str): The key to read.

        Returns:
            Any: The raw value.

        Raises:
            ValueError: The key is missing.
        """
        if key not in self.values:
            raise ValueError(f'Missing key in thresholds [{self.section_name}]: {key}')
        return self.values[key]


@dataclasses.dataclass(frozen=True)
class ServiceThresholds:
    """Limits for the services check.

    Attributes:
        restart_window_seconds: How far back a rise in a unit's restart count still counts as recent.
    """

    restart_window_seconds: float


@dataclasses.dataclass(frozen=True)
class FeedAgeLimits:
    """How old a broker's newest tick may be.

    Attributes:
        warning_age_seconds: The age above which the feed is a warning.
        failure_age_seconds: The age above which the feed is a failure.
    """

    warning_age_seconds: float
    failure_age_seconds: float


@dataclasses.dataclass(frozen=True)
class FeedThresholds:
    """Limits for the quote feed checks.

    Attributes:
        default_limits: The age limits used for a broker without an override.
        grace_after_open_seconds: How long after a session opens a silent feed is not yet judged.
        broker_overrides: Age limits for particular brokers, keyed by broker name.
    """

    default_limits: FeedAgeLimits
    grace_after_open_seconds: float
    broker_overrides: dict[str, FeedAgeLimits]

    def limits_for(self, broker: str) -> FeedAgeLimits:
        """Finds the age limits for one broker.

        Args:
            broker (str): The broker name.

        Returns:
            FeedAgeLimits: The broker's override, or the default limits.
        """
        if broker in self.broker_overrides:
            return self.broker_overrides[broker]
        return self.default_limits


@dataclasses.dataclass(frozen=True)
class QuotesPipelineThresholds:
    """Limits for the unified quotes pipeline check.

    Attributes:
        stats_failure_age_seconds: The age of unified:quotes:stats above which the pipeline is a failure.
        stale_scan_interval_seconds: How often unified:quotes:live is scanned for stale quotes.
    """

    stats_failure_age_seconds: float
    stale_scan_interval_seconds: float


@dataclasses.dataclass(frozen=True)
class StreamThresholds:
    """Limits for the Redis stream consumer group checks.

    Attributes:
        warning_lag_fraction: The share of a stream's cap a group may lag before it is a warning.
        failure_lag_fraction: The share of a stream's cap a group may lag before it is a failure.
        pending_warning: The number of unacknowledged entries above which a group is a warning.
        caps: The approximate length cap of each kind of stream, keyed by kind name.
    """

    warning_lag_fraction: float
    failure_lag_fraction: float
    pending_warning: int
    caps: dict[str, int]

    def cap_for(self, kind: str) -> int:
        """Finds the length cap for one kind of stream.

        Args:
            kind (str): The stream kind, such as "broker_quotes".

        Returns:
            int: The cap.

        Raises:
            ValueError: The thresholds file names no cap for this kind.
        """
        if kind not in self.caps:
            raise ValueError(f'Missing key in thresholds [streams.caps]: {kind}')
        return self.caps[kind]


@dataclasses.dataclass(frozen=True)
class PortfolioThresholds:
    """Limits for the orders and portfolio freshness checks.

    Attributes:
        warning_age_seconds: The age above which a polled dataset is a warning.
        failure_age_seconds: The age above which a polled dataset is a failure.
        holdings_warning_age_seconds: The warning age for holdings, which are polled once a minute.
        holdings_failure_age_seconds: The failure age for holdings.
    """

    warning_age_seconds: float
    failure_age_seconds: float
    holdings_warning_age_seconds: float
    holdings_failure_age_seconds: float


@dataclasses.dataclass(frozen=True)
class ReferenceDataThresholds:
    """Limits for the instruments, mapping and prices checks.

    Attributes:
        expected_by: The time of day by which today's instrument download and mapping should exist.
    """

    expected_by: datetime.time


@dataclasses.dataclass(frozen=True)
class DataStoreThresholds:
    """Limits for the data store reachability checks.

    Attributes:
        slow_warning_milliseconds: The response time above which a store is a warning.
        timeout_seconds: How long a probe waits before the store counts as unreachable.
    """

    slow_warning_milliseconds: float
    timeout_seconds: float


@dataclasses.dataclass(frozen=True)
class LogThresholds:
    """Limits for the journal error counts.

    Attributes:
        window_seconds: How far back warnings and errors are counted.
    """

    window_seconds: float


@dataclasses.dataclass(frozen=True)
class LiveViewThresholds:
    """Limits for the live view page's on-demand reads.

    Attributes:
        api_timeout_seconds: How long a call to UBI's REST API may take before it is abandoned.
    """

    api_timeout_seconds: float


@dataclasses.dataclass(frozen=True)
class AlertThresholds:
    """Limits for desktop notifications.

    Attributes:
        consecutive_failures: How many collections in a row a check must fail before it alerts.
        cooldown_seconds: The shortest time between two alerts for the same check.
        group_threshold: The number of simultaneous failures above which they share one notification.
    """

    consecutive_failures: int
    cooldown_seconds: float
    group_threshold: int


@dataclasses.dataclass(frozen=True)
class Thresholds:
    """Every limit the checks use, one attribute per section of thresholds.toml.

    Attributes:
        services: Limits for the services check.
        feeds: Limits for the quote feed checks.
        quotes_pipeline: Limits for the unified quotes pipeline check.
        streams: Limits for the stream consumer group checks.
        portfolio: Limits for the orders and portfolio freshness checks.
        reference_data: Limits for the instruments, mapping and prices checks.
        data_stores: Limits for the data store checks.
        logs: Limits for the journal error counts.
        live_view: Limits for the live view page's on-demand reads.
        alerts: Limits for desktop notifications.
    """

    services: ServiceThresholds
    feeds: FeedThresholds
    quotes_pipeline: QuotesPipelineThresholds
    streams: StreamThresholds
    portfolio: PortfolioThresholds
    reference_data: ReferenceDataThresholds
    data_stores: DataStoreThresholds
    logs: LogThresholds
    live_view: LiveViewThresholds
    alerts: AlertThresholds

    @classmethod
    def load(cls, path: Path) -> Thresholds:
        """Reads the thresholds from a TOML file.

        Args:
            path (Path): The thresholds file.

        Returns:
            Thresholds: The limits read from the file.

        Raises:
            FileNotFoundError: The file does not exist.
            ValueError: The file is not valid TOML, or a section or key is missing or has the wrong type.
        """
        with path.open('rb') as file:
            try:
                document = tomllib.load(file)
            except tomllib.TOMLDecodeError as error:
                raise ValueError(f'Thresholds file is not valid TOML: {path}: {error}') from error
        return cls.from_dictionary(document)

    @classmethod
    def from_dictionary(cls, document: dict[str, Any]) -> Thresholds:
        """Builds the thresholds from an already parsed document.

        Args:
            document (dict[str, Any]): The parsed TOML document.

        Returns:
            Thresholds: The limits read from the document.

        Raises:
            ValueError: A section or key is missing or has the wrong type.
        """
        services = cls._section(document, 'services')
        feeds = cls._section(document, 'feeds')
        quotes_pipeline = cls._section(document, 'quotes_pipeline')
        streams = cls._section(document, 'streams')
        portfolio = cls._section(document, 'portfolio')
        reference_data = cls._section(document, 'reference_data')
        data_stores = cls._section(document, 'data_stores')
        logs = cls._section(document, 'logs')
        live_view = cls._section(document, 'live_view')
        alerts = cls._section(document, 'alerts')

        broker_overrides = {}
        overrides_table = feeds.table('broker_overrides')
        for broker, override_values in overrides_table.items():
            override = _SectionReader(f'feeds.broker_overrides.{broker}', override_values)
            broker_overrides[broker] = FeedAgeLimits(
                warning_age_seconds=override.number('warning_age_seconds'),
                failure_age_seconds=override.number('failure_age_seconds'),
            )

        caps = {}
        caps_reader = _SectionReader('streams.caps', streams.table('caps'))
        for kind in caps_reader.values:
            caps[kind] = caps_reader.whole_number(kind)

        return cls(
            services=ServiceThresholds(
                restart_window_seconds=services.number('restart_window_seconds'),
            ),
            feeds=FeedThresholds(
                default_limits=FeedAgeLimits(
                    warning_age_seconds=feeds.number('warning_age_seconds'),
                    failure_age_seconds=feeds.number('failure_age_seconds'),
                ),
                grace_after_open_seconds=feeds.number('grace_after_open_seconds'),
                broker_overrides=broker_overrides,
            ),
            quotes_pipeline=QuotesPipelineThresholds(
                stats_failure_age_seconds=quotes_pipeline.number('stats_failure_age_seconds'),
                stale_scan_interval_seconds=quotes_pipeline.number('stale_scan_interval_seconds'),
            ),
            streams=StreamThresholds(
                warning_lag_fraction=streams.number('warning_lag_fraction'),
                failure_lag_fraction=streams.number('failure_lag_fraction'),
                pending_warning=streams.whole_number('pending_warning'),
                caps=caps,
            ),
            portfolio=PortfolioThresholds(
                warning_age_seconds=portfolio.number('warning_age_seconds'),
                failure_age_seconds=portfolio.number('failure_age_seconds'),
                holdings_warning_age_seconds=portfolio.number('holdings_warning_age_seconds'),
                holdings_failure_age_seconds=portfolio.number('holdings_failure_age_seconds'),
            ),
            reference_data=ReferenceDataThresholds(
                expected_by=reference_data.clock_time('expected_by'),
            ),
            data_stores=DataStoreThresholds(
                slow_warning_milliseconds=data_stores.number('slow_warning_milliseconds'),
                timeout_seconds=data_stores.number('timeout_seconds'),
            ),
            logs=LogThresholds(
                window_seconds=logs.number('window_seconds'),
            ),
            live_view=LiveViewThresholds(
                api_timeout_seconds=live_view.number('api_timeout_seconds'),
            ),
            alerts=AlertThresholds(
                consecutive_failures=alerts.whole_number('consecutive_failures'),
                cooldown_seconds=alerts.number('cooldown_seconds'),
                group_threshold=alerts.whole_number('group_threshold'),
            ),
        )

    @staticmethod
    def _section(document: dict[str, Any], name: str) -> _SectionReader:
        """Finds one section of the document.

        Args:
            document (dict[str, Any]): The parsed TOML document.
            name (str): The section name.

        Returns:
            _SectionReader: A reader over the section's values.

        Raises:
            ValueError: The section is missing or is not a table.
        """
        values = document.get(name)
        if not isinstance(values, dict):
            raise ValueError(f'Missing section in thresholds file: [{name}]')
        return _SectionReader(name, values)
