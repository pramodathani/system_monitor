"""The route that streams one UBI unit's journal to the log view.

Typical usage example:

  application.include_router(LogRoutes(inventory, journal_follower, guard).router)
"""

import json
from collections.abc import AsyncIterator

import fastapi
import fastapi.responses

from system_monitor.security.session_guard import SessionGuard
from system_monitor.sources.journal_follower import JournalFollower
from system_monitor.sources.log_line_parser import LogLineParser
from system_monitor.sources.unit_inventory import UnitInventory

_MAXIMUM_LINES = 2000


class LogRoutes:
    """The /api/logs routes.

    Attributes:
        router: The FastAPI router holding the routes.
    """

    def __init__(
        self,
        inventory: UnitInventory,
        journal_follower: JournalFollower,
        guard: SessionGuard,
    ):
        """Creates the routes.

        Args:
            inventory (UnitInventory): The units whose logs may be read.
            journal_follower (JournalFollower): Follows a unit's journal.
            guard (SessionGuard): Requires a logged-in session.
        """
        self.inventory = inventory
        self.journal_follower = journal_follower
        self.router = fastapi.APIRouter(
            dependencies=[
                fastapi.Depends(guard.require_session),
            ],
        )
        self.router.add_api_route(
            '/api/logs/{unit_name}/events',
            self.events,
            methods=[
                'GET',
            ],
        )

    def events(self, unit_name: str, lines: int = 200) -> fastapi.responses.StreamingResponse:
        """Streams a unit's last lines and then its new lines.

        Args:
            unit_name (str): The exact unit name.
            lines (int): How many earlier lines to send first, at most 2000.

        Returns:
            fastapi.responses.StreamingResponse: A text/event-stream response of "line" events.

        Raises:
            fastapi.HTTPException: 404 when the unit is not one of UBI's units.
        """
        if not self.inventory.has_unit(unit_name):
            raise fastapi.HTTPException(status_code=404, detail=f'Not a unified_broker_interface unit: {unit_name}')
        line_count = max(0, min(lines, _MAXIMUM_LINES))
        return fastapi.responses.StreamingResponse(
            self._line_stream(unit_name, line_count),
            media_type='text/event-stream',
            headers={
                'Cache-Control': 'no-cache',
                'X-Accel-Buffering': 'no',
            },
        )

    async def _line_stream(self, unit_name: str, line_count: int) -> AsyncIterator[str]:
        """Produces one event per journal line.

        The web server cancels this generator when the browser disconnects, which stops journalctl.

        Args:
            unit_name (str): The unit to follow.
            line_count (int): How many earlier lines to send first.

        Yields:
            str: The next "line" event.
        """
        parser = LogLineParser()
        async for entry in self.journal_follower.follow(unit_name, line_count):
            parsed = parser.parse(unit_name, entry.message)
            payload = json.dumps(
                {
                    'timestamp': entry.timestamp,
                    'level': parsed.level,
                    'text': entry.message,
                    'continuation': parsed.is_continuation,
                },
            )
            yield f'event: line\ndata: {payload}\n\n'
