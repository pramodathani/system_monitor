"""When the exchanges UBI streams from are trading.

The calendars come from the `exchange_details` documents in UBI's MongoDB, which `import-api-details` fills with each exchange's trading hours, holidays and special sessions. Until MongoDB has been read, or when it cannot be, built-in normal hours for NSE and MCX are used without holidays.

A calendar is a set of segments that close together: "equity", "currency" or "commodity". A commodity holiday can close only the "morning" or "evening" session. A special session, such as Muhurat trading, opens a window on its date in addition to any normal sessions.

Typical usage example:

  calendar = MarketCalendar(mongo_connection, SystemClock())
  calendar.refresh_if_due()
  if calendar.is_market_open(time.time()):
      ...
"""

import dataclasses
import datetime
import logging
import threading
import zoneinfo
from typing import Any

import pymongo.errors

from system_monitor.sources.mongo_connection import MongoConnection
from system_monitor.utilities.clock import SystemClock
from system_monitor.utilities.timestamp_parser import INDIA_TIMEZONE, TimestampParser

_LOGGER = logging.getLogger(__name__)
_NEW_YORK_TIMEZONE = zoneinfo.ZoneInfo('America/New_York')

_COMMODITY_HOURS = {
    'sessions': [
        {
            'name': 'morning',
            'opens': '09:00',
            'closes': '17:00',
        },
        {
            'name': 'evening',
            'opens': '17:00',
            'closes': '23:30',
            'closes_during_us_standard_time': '23:55',
        },
    ],
}

BUILT_IN_CALENDARS = [
    {
        'exchange': 'nse',
        'trading_hours': {
            'equity': {
                'sessions': [
                    {
                        'name': 'normal',
                        'opens': '09:15',
                        'closes': '15:30',
                    },
                ],
            },
        },
    },
    {
        'exchange': 'mcx',
        'trading_hours': {
            'commodity': _COMMODITY_HOURS,
        },
    },
]


@dataclasses.dataclass(frozen=True)
class SessionWindow:
    """One trading session on one day.

    Attributes:
        exchange: The exchange, such as "nse".
        calendar: The calendar, such as "equity".
        name: The session name, such as "normal" or "evening".
        opens_at: When the session opens, in epoch seconds.
        closes_at: When the session closes, in epoch seconds.
    """

    exchange: str
    calendar: str
    name: str
    opens_at: float
    closes_at: float


class MarketCalendar:
    """Answers whether markets are open, from UBI's exchange calendars."""

    def __init__(
        self,
        mongo_connection: MongoConnection | None,
        clock: SystemClock,
        refresh_seconds: float = 3600.0,
        retry_seconds: float = 60.0,
    ):
        """Creates a calendar that starts with the built-in hours.

        Args:
            mongo_connection (MongoConnection | None): Where to read the calendars, or None to keep the built-in hours.
            clock (SystemClock): The source of the current time.
            refresh_seconds (float): How often to read MongoDB again after a successful read.
            retry_seconds (float): How soon to try again after a failed read.
        """
        self.mongo_connection = mongo_connection
        self.clock = clock
        self.refresh_seconds = refresh_seconds
        self.retry_seconds = retry_seconds
        self._lock = threading.Lock()
        self._documents = BUILT_IN_CALENDARS
        self._source = 'built-in hours'
        self._next_refresh_at = 0.0

    def refresh_if_due(self) -> None:
        """Reads the calendars from MongoDB when the last read is old enough.

        A failed read is logged and the previous calendars are kept.
        """
        if self.mongo_connection is None:
            return
        now = self.clock.now()
        if now < self._next_refresh_at:
            return
        try:
            documents = self.mongo_connection.exchange_calendars()
        except pymongo.errors.PyMongoError as error:
            _LOGGER.warning('Could not read exchange calendars from MongoDB (reason: %r); keeping %s.', error, self._source)
            self._next_refresh_at = now + self.retry_seconds
            return
        if documents:
            self.load_documents(documents, 'MongoDB exchange_details')
        self._next_refresh_at = now + self.refresh_seconds

    def load_documents(self, documents: list[dict[str, Any]], source: str) -> None:
        """Replaces the calendars.

        Args:
            documents (list[dict[str, Any]]): One document per exchange, shaped like UBI's exchange_details.
            source (str): Where the documents came from, shown on the dashboard.
        """
        with self._lock:
            self._documents = documents
            self._source = source

    def source(self) -> str:
        """Names where the current calendars came from.

        Returns:
            str: "MongoDB exchange_details" or "built-in hours".
        """
        with self._lock:
            return self._source

    def windows_for_day(self, day: datetime.date) -> list[SessionWindow]:
        """Lists every trading session on an India date.

        Args:
            day (datetime.date): The date in India.

        Returns:
            list[SessionWindow]: The sessions of every exchange and calendar that trade that day.
        """
        with self._lock:
            documents = self._documents
        windows = []
        for document in documents:
            exchange = document.get('exchange', '')
            trading_hours = document.get('trading_hours') or {}
            for calendar, calendar_hours in trading_hours.items():
                if not isinstance(calendar_hours, dict):
                    continue
                windows.extend(self._calendar_windows(document, exchange, calendar, calendar_hours, day))
        return windows

    def open_windows(self, epoch: float) -> list[SessionWindow]:
        """Lists the sessions open at a moment.

        Args:
            epoch (float): The moment, in epoch seconds.

        Returns:
            list[SessionWindow]: The sessions whose window contains the moment.
        """
        day = TimestampParser.india_date(epoch)
        open_windows = []
        for window in self.windows_for_day(day):
            if window.opens_at <= epoch < window.closes_at:
                open_windows.append(window)
        return open_windows

    def is_market_open(self, epoch: float) -> bool:
        """Checks whether any session of any exchange is open.

        Args:
            epoch (float): The moment, in epoch seconds.

        Returns:
            bool: True when at least one session is open.
        """
        return bool(self.open_windows(epoch))

    def seconds_since_open(self, epoch: float) -> float | None:
        """Measures how long markets have been continuously open.

        Sessions of one calendar that follow each other without a gap, such as the commodity morning and evening sessions, count as one open period.

        Args:
            epoch (float): The moment, in epoch seconds.

        Returns:
            float | None: Seconds since the earliest continuous open period began, or None when no session is open.
        """
        day = TimestampParser.india_date(epoch)
        windows = self.windows_for_day(day)
        earliest_start = None
        for window in windows:
            if not window.opens_at <= epoch < window.closes_at:
                continue
            start = self._continuous_start(window, windows)
            if earliest_start is None or start < earliest_start:
                earliest_start = start
        if earliest_start is None:
            return None
        return epoch - earliest_start

    def is_trading_day(
        self,
        exchange: str,
        calendar: str,
        day: datetime.date,
    ) -> bool:
        """Checks whether one exchange's calendar has any session on a date.

        Args:
            exchange (str): The exchange, such as "nse".
            calendar (str): The calendar, such as "equity".
            day (datetime.date): The date in India.

        Returns:
            bool: True when the calendar trades that day.
        """
        for window in self.windows_for_day(day):
            if window.exchange == exchange and window.calendar == calendar:
                return True
        return False

    def _calendar_windows(
        self,
        document: dict[str, Any],
        exchange: str,
        calendar: str,
        calendar_hours: dict[str, Any],
        day: datetime.date,
    ) -> list[SessionWindow]:
        """Builds one calendar's sessions for one date.

        Args:
            document (dict[str, Any]): The exchange's document, for its holidays and special sessions.
            exchange (str): The exchange name.
            calendar (str): The calendar name.
            calendar_hours (dict[str, Any]): The calendar's trading hours.
            day (datetime.date): The date in India.

        Returns:
            list[SessionWindow]: The calendar's sessions that day.
        """
        windows = []
        for special in document.get('special_sessions') or []:
            if special.get('date') == day.isoformat() and calendar in special.get('calendars', []):
                windows.append(
                    SessionWindow(
                        exchange=exchange,
                        calendar=calendar,
                        name=special.get('name', 'special'),
                        opens_at=self._epoch(day, special['opens']),
                        closes_at=self._epoch(day, special['closes']),
                    ),
                )
        if day.weekday() >= 5:
            return windows
        closure = self._closure(document, calendar, day)
        if closure == 'all':
            return windows
        for session in calendar_hours.get('sessions', []):
            if session.get('name') == closure:
                continue
            closes_text = session['closes']
            if 'closes_during_us_standard_time' in session and not self._is_us_daylight_saving(day):
                closes_text = session['closes_during_us_standard_time']
            windows.append(
                SessionWindow(
                    exchange=exchange,
                    calendar=calendar,
                    name=session.get('name', 'normal'),
                    opens_at=self._epoch(day, session['opens']),
                    closes_at=self._epoch(day, closes_text),
                ),
            )
        return windows

    def _closure(
        self,
        document: dict[str, Any],
        calendar: str,
        day: datetime.date,
    ) -> str | None:
        """Finds whether a calendar is closed for a holiday on a date.

        Args:
            document (dict[str, Any]): The exchange's document.
            calendar (str): The calendar name.
            day (datetime.date): The date in India.

        Returns:
            str | None: "all", "morning" or "evening" for a holiday, or None for a normal day.
        """
        holidays = document.get('holidays') or {}
        for holiday in holidays.get(calendar, []):
            if holiday.get('date') == day.isoformat():
                return holiday.get('closed', 'all')
        return None

    def _continuous_start(
        self,
        window: SessionWindow,
        windows: list[SessionWindow],
    ) -> float:
        """Walks back through sessions of the same calendar that end exactly when the next begins.

        Args:
            window (SessionWindow): The open session.
            windows (list[SessionWindow]): Every session of the same day.

        Returns:
            float: When the continuous open period that contains the session began, in epoch seconds.
        """
        start = window.opens_at
        found_earlier = True
        while found_earlier:
            found_earlier = False
            for other in windows:
                same_calendar = other.exchange == window.exchange and other.calendar == window.calendar
                if same_calendar and other.closes_at == start and other.opens_at < start:
                    start = other.opens_at
                    found_earlier = True
        return start

    def _is_us_daylight_saving(self, day: datetime.date) -> bool:
        """Checks whether New York is on daylight saving time on a date.

        Args:
            day (datetime.date): The date.

        Returns:
            bool: True during United States daylight saving time.
        """
        noon = datetime.datetime.combine(day, datetime.time(12, 0), tzinfo=_NEW_YORK_TIMEZONE)
        offset = noon.dst()
        return offset is not None and offset != datetime.timedelta(0)

    def _epoch(self, day: datetime.date, clock_text: str) -> float:
        """Converts an India date and a clock time to epoch seconds.

        Args:
            day (datetime.date): The date in India.
            clock_text (str): A time such as "09:15" or "23:59:59".

        Returns:
            float: Seconds since the Unix epoch.
        """
        clock_time = datetime.time.fromisoformat(clock_text)
        moment = datetime.datetime.combine(day, clock_time, tzinfo=INDIA_TIMEZONE)
        return moment.timestamp()
