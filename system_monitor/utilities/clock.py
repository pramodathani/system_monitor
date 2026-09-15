"""The source of the current time for every check.

Collectors take a clock object instead of calling `time.time()` directly, so tests can run a check at any moment, such as a Sunday or ten seconds after the market opens.

Typical usage example:

  clock = SystemClock()
  now = clock.now()
"""

import time


class SystemClock:
    """The real wall clock."""

    def now(self) -> float:
        """Reads the current time.

        Returns:
            float: Seconds since the Unix epoch.
        """
        return time.time()
