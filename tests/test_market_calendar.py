"""Tests for MarketCalendar."""

import datetime

from system_monitor.sources.market_calendar import MarketCalendar
from tests.fakes import FixedClock

_DOCUMENTS = [
    {
        'exchange': 'nse',
        'trading_hours': {
            'timezone': 'Asia/Kolkata',
            'equity': {
                'pre_open': {
                    'opens': '09:00',
                    'closes': '09:15',
                },
                'sessions': [
                    {
                        'name': 'normal',
                        'opens': '09:15',
                        'closes': '15:30',
                    },
                ],
            },
        },
        'holidays': {
            'equity': [
                {
                    'date': '2026-10-02',
                    'closed': 'all',
                    'name': 'Gandhi Jayanti',
                },
            ],
        },
        'special_sessions': [
            {
                'date': '2026-11-08',
                'name': 'Muhurat trading',
                'calendars': [
                    'equity',
                ],
                'opens': '18:00',
                'closes': '19:00',
            },
        ],
    },
    {
        'exchange': 'mcx',
        'trading_hours': {
            'commodity': {
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
            },
        },
        'holidays': {
            'commodity': [
                {
                    'date': '2026-10-02',
                    'closed': 'morning',
                    'name': 'Gandhi Jayanti',
                },
            ],
        },
    },
]


class TestMarketCalendar:
    """Tests for MarketCalendar."""

    def _calendar(self) -> MarketCalendar:
        """Builds a calendar over the test documents.

        Returns:
            MarketCalendar: The calendar.
        """
        calendar = MarketCalendar(None, FixedClock(0))
        calendar.load_documents(_DOCUMENTS, 'test')
        return calendar

    def test_is_market_open_on_weekday_afternoon(self):
        """Checks a Tuesday at 14:00, when both exchanges trade.

        Raises:
            AssertionError: The market is not open.
        """
        moment = FixedClock.at_india_time(2026, 9, 15, 14, 0).now()
        open_exchanges = set()
        for window in self._calendar().open_windows(moment):
            open_exchanges.add(window.exchange)
        assert open_exchanges == {
            'nse',
            'mcx',
        }

    def test_is_market_open_false_on_sunday_and_at_night(self):
        """Checks a Sunday afternoon and a weekday at 23:45 during US daylight saving.

        Raises:
            AssertionError: The market is open when it should be closed.
        """
        calendar = self._calendar()
        assert not calendar.is_market_open(FixedClock.at_india_time(2026, 9, 13, 14, 0).now())
        assert not calendar.is_market_open(FixedClock.at_india_time(2026, 9, 15, 23, 45).now())

    def test_evening_session_extends_during_us_standard_time(self):
        """Checks that MCX trades at 23:45 in December, when New York is on standard time.

        Raises:
            AssertionError: The extension was not applied.
        """
        moment = FixedClock.at_india_time(2026, 12, 15, 23, 45).now()
        assert self._calendar().is_market_open(moment)

    def test_holiday_closes_equity_and_commodity_morning_only(self):
        """Checks a holiday that closes NSE all day and MCX only in the morning.

        Raises:
            AssertionError: A closure was applied wrongly.
        """
        calendar = self._calendar()
        holiday = datetime.date(2026, 10, 2)
        assert not calendar.is_trading_day('nse', 'equity', holiday)
        assert calendar.is_trading_day('mcx', 'commodity', holiday)
        assert not calendar.is_market_open(FixedClock.at_india_time(2026, 10, 2, 11, 0).now())
        assert calendar.is_market_open(FixedClock.at_india_time(2026, 10, 2, 18, 0).now())

    def test_special_session_opens_a_sunday(self):
        """Checks that Muhurat trading opens NSE on a Sunday.

        Raises:
            AssertionError: The special session was not opened.
        """
        moment = FixedClock.at_india_time(2026, 11, 8, 18, 30).now()
        windows = self._calendar().open_windows(moment)
        assert [window.name for window in windows] == [
            'Muhurat trading',
        ]

    def test_seconds_since_open_joins_back_to_back_sessions(self):
        """Checks that at 17:05 MCX counts as open since 09:00, not since 17:00.

        Raises:
            AssertionError: The continuous period was not joined.
        """
        moment = FixedClock.at_india_time(2026, 9, 15, 17, 5).now()
        assert self._calendar().seconds_since_open(moment) == 8 * 3600 + 5 * 60

    def test_seconds_since_open_none_when_closed(self):
        """Checks that no open session gives None.

        Raises:
            AssertionError: A value was returned.
        """
        moment = FixedClock.at_india_time(2026, 9, 13, 12, 0).now()
        assert self._calendar().seconds_since_open(moment) is None
