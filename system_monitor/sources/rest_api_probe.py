"""Checks that UBI's REST API answers its unauthenticated greeting route.

The probe calls only `GET /api/`. It never connects a session, because UBI allows one token for the whole application and connecting would log every other client out.

Typical usage example:

  probe = RestApiProbe('http://127.0.0.1:8080/api/', timeout_seconds=3)
  milliseconds = probe.greeting_milliseconds()
"""

import time

import httpx


class RestApiProbe:
    """Calls the REST API's greeting route and times it."""

    def __init__(self, url: str, timeout_seconds: float):
        """Creates the probe.

        Args:
            url (str): The greeting route's address.
            timeout_seconds (float): How long the request may take.
        """
        self.url = url
        self.timeout_seconds = timeout_seconds

    def greeting_milliseconds(self) -> float:
        """Requests the greeting route and measures the round trip.

        Returns:
            float: The time taken in milliseconds.

        Raises:
            httpx.HTTPError: The request failed or the response status was not successful.
        """
        started = time.perf_counter()
        response = httpx.get(self.url, timeout=self.timeout_seconds)
        response.raise_for_status()
        return (time.perf_counter() - started) * 1000
