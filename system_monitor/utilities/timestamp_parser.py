"""Conversions between the timestamp formats UBI and systemd write and epoch seconds.

UBI writes local India times without a zone, such as "2026-09-15 14:53:07.206668" and "2026-09-15T14:53:06". systemd, asked with `--timestamp=unix`, writes "@1789441221", or an empty string when the event never happened.

Typical usage example:

  epoch = TimestampParser.india_text_to_epoch('2026-09-15 14:53:07.206668')
  day = TimestampParser.india_date(epoch)
"""

import datetime
import zoneinfo

INDIA_TIMEZONE = zoneinfo.ZoneInfo('Asia/Kolkata')


class TimestampParser:
    """Converts timestamps between text, epoch seconds and India dates."""

    @staticmethod
    def india_text_to_epoch(text: str) -> float:
        """Converts a UBI timestamp to epoch seconds.

        A timestamp without a zone is read as India time; one with a zone keeps its own.

        Args:
            text (str): An ISO-like timestamp, with a space or "T" between date and time.

        Returns:
            float: Seconds since the Unix epoch.

        Raises:
            ValueError: The text is not a timestamp.
        """
        if not isinstance(text, str):
            raise ValueError(f'Not a timestamp: {text!r}')
        moment = datetime.datetime.fromisoformat(text)
        if moment.tzinfo is None:
            moment = moment.replace(tzinfo=INDIA_TIMEZONE)
        return moment.timestamp()

    @staticmethod
    def systemd_value_to_epoch(text: str) -> float | None:
        """Converts a systemd timestamp printed with --timestamp=unix.

        Args:
            text (str): A value such as "@1789441221", or an empty string or "n/a".

        Returns:
            float | None: Seconds since the Unix epoch, or None when the event never happened.

        Raises:
            ValueError: The text is neither empty nor an "@" followed by a number.
        """
        if not text or text == 'n/a':
            return None
        if not text.startswith('@'):
            raise ValueError(f'Not a systemd unix timestamp: {text!r}')
        epoch = float(text[1:])
        if epoch == 0:
            return None
        return epoch

    @staticmethod
    def india_datetime(epoch: float) -> datetime.datetime:
        """Converts epoch seconds to an India date and time.

        Args:
            epoch (float): Seconds since the Unix epoch.

        Returns:
            datetime.datetime: The moment in India time, with its zone set.
        """
        return datetime.datetime.fromtimestamp(epoch, tz=INDIA_TIMEZONE)

    @staticmethod
    def india_date(epoch: float) -> datetime.date:
        """Finds the India calendar date of a moment.

        Args:
            epoch (float): Seconds since the Unix epoch.

        Returns:
            datetime.date: The date in India.
        """
        return TimestampParser.india_datetime(epoch).date()
