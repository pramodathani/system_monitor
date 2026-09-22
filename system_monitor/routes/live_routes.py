"""The routes behind the live view page: Redis values, store health and UBI's REST API.

These routes read on demand rather than from the collectors' state, because the live view shows what Redis holds at the moment it is asked rather than what a check last judged. Every read is a blocking call into Redis, a database or the REST API, so each route is a plain method and FastAPI runs it in its worker threadpool.

Nothing here accepts a Redis key or a URL from the browser. A tab is named, and the catalogues turn that name into a key or a path, so the page cannot be used to read an arbitrary key or call an arbitrary address.

Typical usage example:

  application.include_router(LiveRoutes(live_view_reader, database_health, api_catalogue, api_caller, guard).router)
"""

from typing import Any

import fastapi
import redis

from system_monitor.live.api_caller import ApiCaller
from system_monitor.live.api_catalogue import ApiCatalogue
from system_monitor.live.database_health import DatabaseHealth
from system_monitor.live.live_view_reader import LiveViewReader, UnknownViewError
from system_monitor.security.session_guard import SessionGuard

_DEFAULT_PAGE_ROWS = 100


class LiveRoutes:
    """The /api/live routes.

    Attributes:
        router: The FastAPI router holding the routes.
    """

    def __init__(
        self,
        live_view_reader: LiveViewReader,
        database_health: DatabaseHealth,
        api_catalogue: ApiCatalogue,
        api_caller: ApiCaller,
        guard: SessionGuard,
    ):
        """Creates the routes.

        Args:
            live_view_reader (LiveViewReader): Reads the Redis tabs.
            database_health (DatabaseHealth): Reads the three data stores.
            api_catalogue (ApiCatalogue): The UBI endpoints that may be called.
            api_caller (ApiCaller): Calls one of them.
            guard (SessionGuard): Requires a logged-in session.
        """
        self.live_view_reader = live_view_reader
        self.database_health = database_health
        self.api_catalogue = api_catalogue
        self.api_caller = api_caller
        self.router = fastapi.APIRouter(
            dependencies=[
                fastapi.Depends(guard.require_session),
            ],
        )
        self.router.add_api_route(
            '/api/live/catalogue',
            self.catalogue,
            methods=[
                'GET',
            ],
        )
        self.router.add_api_route(
            '/api/live/databases',
            self.databases,
            methods=[
                'GET',
            ],
        )
        self.router.add_api_route(
            '/api/live/view/{scope}/{name}',
            self.view,
            methods=[
                'GET',
            ],
        )
        self.router.add_api_route(
            '/api/live/table/{scope}/{name}',
            self.table,
            methods=[
                'GET',
            ],
        )
        self.router.add_api_route(
            '/api/live/api/{name}',
            self.call_api,
            methods=[
                'GET',
            ],
        )

    def catalogue(self) -> dict[str, Any]:
        """Describes every tab, broker and API endpoint the page can show.

        Returns:
            dict[str, Any]: The keys "brokers", "broker_views", "unified_views", "api_endpoints" and "mapping_date".

        Raises:
            fastapi.HTTPException: 503 when Redis could not be read.
        """
        view_catalogue = self.live_view_reader.view_catalogue
        try:
            mapping_date = self.live_view_reader.mapping_meta.mapping_date()
        except (redis.RedisError, ValueError):
            mapping_date = None
        return {
            'brokers': self.live_view_reader.brokers(),
            'broker_views': view_catalogue.views('broker'),
            'unified_views': view_catalogue.views('unified'),
            'api_endpoints': self.api_catalogue.endpoints(),
            'mapping_date': mapping_date,
        }

    def databases(self) -> dict[str, Any]:
        """Reads Redis, MongoDB and TimescaleDB and the containers they run in.

        Returns:
            dict[str, Any]: The reading, as `DatabaseHealth.read` describes it.
        """
        return self.database_health.read()

    def view(
        self,
        scope: str,
        name: str,
        broker: str | None = None,
    ) -> dict[str, Any]:
        """Reads one tab that shows a document.

        Args:
            scope (str): Either "broker" or "unified".
            name (str): The tab's name.
            broker (str | None): The broker chosen, for a tab that needs one.

        Returns:
            dict[str, Any]: The tab and its value.

        Raises:
            fastapi.HTTPException: 404 when the tab is unknown, 400 when the broker is wrong or a stored value is not JSON, 503 when Redis could not be read.
        """
        try:
            return self.live_view_reader.read_view(scope, name, broker)
        except UnknownViewError as error:
            raise fastapi.HTTPException(status_code=404, detail=str(error)) from error
        except ValueError as error:
            raise fastapi.HTTPException(status_code=400, detail=str(error)) from error
        except redis.RedisError as error:
            raise self._unreachable('Redis', error) from error

    def table(
        self,
        scope: str,
        name: str,
        broker: str | None = None,
        cursor: str = '0',
        limit: int = _DEFAULT_PAGE_ROWS,
        search: str | None = None,
    ) -> dict[str, Any]:
        """Reads one page of a tab that shows a table, or searches the whole table.

        Args:
            scope (str): Either "broker" or "unified".
            name (str): The tab's name.
            broker (str | None): The broker chosen, for a table that needs one.
            cursor (str): The cursor to continue from. "0" starts at the beginning.
            limit (int): How many rows to gather, at most 500.
            search (str | None): Text to look for in every row, or nothing to page through instead.

        Returns:
            dict[str, Any]: The tab and its page of rows.

        Raises:
            fastapi.HTTPException: 404 when the tab is unknown, 400 when the broker or the cursor is wrong, 503 when Redis could not be read.
        """
        try:
            return self.live_view_reader.read_table(scope, name, broker, cursor, limit, search)
        except UnknownViewError as error:
            raise fastapi.HTTPException(status_code=404, detail=str(error)) from error
        except ValueError as error:
            raise fastapi.HTTPException(status_code=400, detail=str(error)) from error
        except redis.RedisError as error:
            raise self._unreachable('Redis', error) from error

    def call_api(self, name: str, request: fastapi.Request) -> dict[str, Any]:
        """Calls one of UBI's GET endpoints and returns what it answered.

        Every query parameter of this request other than the endpoint's own is ignored, and the path called comes from the catalogue rather than from the request.

        Args:
            name (str): The endpoint's name, such as "instruments_quote".
            request (fastapi.Request): The request, whose query parameters are passed on.

        Returns:
            dict[str, Any]: The call's outcome, as `ApiCaller.call` describes it.

        Raises:
            fastapi.HTTPException: 404 when the endpoint is unknown.
        """
        parameters = dict(request.query_params)
        try:
            return self.api_caller.call(name, parameters)
        except ValueError as error:
            raise fastapi.HTTPException(status_code=404, detail=str(error)) from error

    def _unreachable(self, store: str, error: Exception) -> fastapi.HTTPException:
        """Builds the refusal for a store that could not be read.

        Args:
            store (str): The store's name, for the message.
            error (Exception): What went wrong.

        Returns:
            fastapi.HTTPException: A 503 naming the store and the error.
        """
        return fastapi.HTTPException(
            status_code=503,
            detail=f'{store} could not be read: {type(error).__name__}: {error}',
        )
