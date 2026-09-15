"""Short human wording for durations and times in check messages.

Typical usage example:

  TextFormatter.duration(195)            # '3 min 15 s'
  TextFormatter.india_time(epoch, now)   # '08:30' today, '14 Sep 08:30' otherwise
"""

from system_monitor.utilities.timestamp_parser import TimestampParser


class TextFormatter:
    """Formats numbers of seconds and moments for people."""

    @staticmethod
    def duration(seconds: float) -> str:
        """Describes a length of time in its two largest units.

        Args:
            seconds (float): The length of time. Negative values are treated as zero.

        Returns:
            str: A description such as "45 s", "3 min 15 s", "2 h 5 min" or "3 d 4 h".
        """
        whole_seconds = max(0, int(seconds))
        if whole_seconds < 60:
            return f'{whole_seconds} s'
        minutes, remaining_seconds = divmod(whole_seconds, 60)
        if minutes < 60:
            if remaining_seconds == 0:
                return f'{minutes} min'
            return f'{minutes} min {remaining_seconds} s'
        hours, remaining_minutes = divmod(minutes, 60)
        if hours < 24:
            return f'{hours} h {remaining_minutes} min'
        days, remaining_hours = divmod(hours, 24)
        return f'{days} d {remaining_hours} h'

    @staticmethod
    def india_time(epoch: float, now: float) -> str:
        """Describes a moment in India time, adding the date when it is not today.

        Args:
            epoch (float): The moment, in epoch seconds.
            now (float): The current time, in epoch seconds, to decide whether the moment is today.

        Returns:
            str: "HH:MM" for today, or "DD Mon HH:MM" for another day.
        """
        moment = TimestampParser.india_datetime(epoch)
        if moment.date() == TimestampParser.india_date(now):
            return moment.strftime('%H:%M')
        return moment.strftime('%d %b %H:%M')
