"""Calls one of UBI's GET endpoints and brings back exactly what it answered.

The application token is read from the Redis hash `last_login`, field `unified_broker_interface`, which is where a login leaves the token in force. Reusing it is what lets the monitor make an authenticated call without ever calling `POST /api/session/connect`: UBI allows one token for the whole application, so minting a second one would revoke the one `tradingmachine` is using. When the stored token is missing or has expired, the call is made without one and the API's own 401 is shown, because recovering from that is a login's job and not the monitor's.

Only endpoints named in `ApiCatalogue` can be reached, and the path always comes from the catalogue rather than from the request, so the browser cannot steer a call anywhere else.

The body is read in chunks and abandoned past a size limit, because `/instruments/master` over every segment and `/instruments/ticks` over a wide range both answer with far more than a page can show.

Typical usage example:

  caller = ApiCaller(catalogue, redis_reader, 'http://127.0.0.1:8080/api', timeout_seconds=30)
  answer = caller.call('instruments_quote', {'exchange': 'nse', 'segment': 'equities', 'symbol': 'RELIANCE'})
"""

import json
import time
from typing import Any

import httpx
import redis

from system_monitor.live.api_catalogue import ApiCatalogue
from system_monitor.sources.redis_reader import RedisReader

_TOKEN_KEY = 'last_login'
_TOKEN_FIELD = 'unified_broker_interface'
_TOKEN_HEADER = 'access-token'
_MAXIMUM_BYTES = 4 * 1024 * 1024


class ApiCaller:
    """Issues one whitelisted GET against UBI's REST API."""

    def __init__(
        self,
        catalogue: ApiCatalogue,
        redis_reader: RedisReader,
        base_url: str,
        timeout_seconds: float,
        maximum_bytes: int = _MAXIMUM_BYTES,
    ):
        """Creates the caller.

        Args:
            catalogue (ApiCatalogue): The endpoints that may be called.
            redis_reader (RedisReader): Reads the application token from Redis.
            base_url (str): The API's address up to and including "/api", without a trailing slash.
            timeout_seconds (float): How long a call may take.
            maximum_bytes (int): How much of the answer to keep before abandoning the rest.
        """
        self.catalogue = catalogue
        self.redis_reader = redis_reader
        self.base_url = base_url.rstrip('/')
        self.timeout_seconds = timeout_seconds
        self.maximum_bytes = maximum_bytes

    def call(self, name: str, parameters: dict[str, str]) -> dict[str, Any]:
        """Calls one endpoint and describes what came back.

        Args:
            name (str): The endpoint's name, which must be one the catalogue holds.
            parameters (dict[str, str]): The query parameters to send. Empty values are left out.

        Returns:
            dict[str, Any]: The keys "endpoint", "url", "status_code", "elapsed_milliseconds", "byte_size", "truncated", "document", "text", "token_used" and "error".

        Raises:
            ValueError: No endpoint has that name.
        """
        endpoint = self.catalogue.find(name)
        if endpoint is None:
            raise ValueError(f'Not a UBI endpoint: {name}')
        wanted = self._wanted_parameters(endpoint, parameters)
        headers = {}
        token = None
        if endpoint['authenticated']:
            token = self._token()
            if token is not None:
                headers[_TOKEN_HEADER] = token
        url = f'{self.base_url}{endpoint["path"]}'
        started = time.perf_counter()
        try:
            status_code, body, truncated = self._fetch(url, wanted, headers)
        except httpx.HTTPError as error:
            return self._answer(
                endpoint,
                url,
                None,
                (time.perf_counter() - started) * 1000,
                0,
                False,
                None,
                None,
                token is not None,
                f'{type(error).__name__}: {error}',
            )
        elapsed = (time.perf_counter() - started) * 1000
        document = None
        text = None
        decoded = body.decode('utf-8', errors='replace')
        try:
            document = json.loads(decoded)
        except ValueError:
            text = decoded
        return self._answer(
            endpoint,
            url,
            status_code,
            elapsed,
            len(body),
            truncated,
            document,
            text,
            token is not None,
            None,
        )

    def _wanted_parameters(
        self,
        endpoint: dict[str, Any],
        parameters: dict[str, str],
    ) -> dict[str, str]:
        """Keeps only the parameters the endpoint declares, and only those with a value.

        Args:
            endpoint (dict[str, Any]): The endpoint being called.
            parameters (dict[str, str]): What the browser sent.

        Returns:
            dict[str, str]: The query parameters to put on the request.
        """
        allowed = {parameter['name'] for parameter in endpoint['parameters']}
        wanted = {}
        for name, value in parameters.items():
            if name not in allowed:
                continue
            if value is None or str(value).strip() == '':
                continue
            wanted[name] = str(value).strip()
        return wanted

    def _token(self) -> str | None:
        """Reads the application token that a login left in Redis.

        Returns:
            str | None: The token, or None when there is none stored or Redis could not be read.
        """
        try:
            document = self.redis_reader.hash_get_json(_TOKEN_KEY, _TOKEN_FIELD)
        except (redis.RedisError, ValueError):
            return None
        if not isinstance(document, dict):
            return None
        token = document.get('access_token')
        if not token:
            return None
        return str(token)

    def _fetch(
        self,
        url: str,
        parameters: dict[str, str],
        headers: dict[str, str],
    ) -> tuple[int, bytes, bool]:
        """Makes the request and reads the answer up to the size limit.

        Args:
            url (str): The full address to call.
            parameters (dict[str, str]): The query parameters.
            headers (dict[str, str]): The request headers.

        Returns:
            tuple[int, bytes, bool]: The status code, the body read, and whether the body was cut short.

        Raises:
            httpx.HTTPError: The request could not be made or finished.
        """
        collected = bytearray()
        truncated = False
        with (
            httpx.Client(timeout=self.timeout_seconds) as client,
            client.stream('GET', url, params=parameters, headers=headers) as response,
        ):
            status_code = response.status_code
            for chunk in response.iter_bytes():
                room = self.maximum_bytes - len(collected)
                if room <= 0:
                    truncated = True
                    break
                if len(chunk) > room:
                    collected.extend(chunk[:room])
                    truncated = True
                    break
                collected.extend(chunk)
        return status_code, bytes(collected), truncated

    def _answer(
        self,
        endpoint: dict[str, Any],
        url: str,
        status_code: int | None,
        elapsed_milliseconds: float,
        byte_size: int,
        truncated: bool,
        document: Any,
        text: str | None,
        token_used: bool,
        error: str | None,
    ) -> dict[str, Any]:
        """Assembles the answer the route returns.

        Args:
            endpoint (dict[str, Any]): The endpoint that was called.
            url (str): The address called.
            status_code (int | None): The HTTP status, or None when the request never completed.
            elapsed_milliseconds (float): How long the call took.
            byte_size (int): How many bytes of the answer were read.
            truncated (bool): Whether the answer was cut short at the size limit.
            document (Any): The parsed JSON answer, or None when it was not JSON.
            text (str | None): The raw answer when it was not JSON.
            token_used (bool): Whether a stored application token was sent.
            error (str | None): Why the call failed, or None when it did not.

        Returns:
            dict[str, Any]: The answer.
        """
        return {
            'endpoint': endpoint['name'],
            'url': url,
            'status_code': status_code,
            'elapsed_milliseconds': elapsed_milliseconds,
            'byte_size': byte_size,
            'truncated': truncated,
            'document': document,
            'text': text,
            'token_used': token_used,
            'error': error,
        }
