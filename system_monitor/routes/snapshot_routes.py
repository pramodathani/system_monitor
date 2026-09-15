"""The routes that deliver the dashboard's data: one snapshot, and a stream of snapshots.

The stream uses server-sent events. It checks for changes every couple of seconds, sends the whole snapshot when something changed, and sends a comment line every fifteen seconds otherwise so the connection is not considered dead.

Typical usage example:

  application.include_router(SnapshotRoutes(snapshot_builder, guard).router)
"""

import asyncio
import json
import time
from collections.abc import AsyncIterator
from typing import Any

import fastapi
import fastapi.responses

from system_monitor.security.session_guard import SessionGuard
from system_monitor.state.dashboard_snapshot import DashboardSnapshot

_KEEPALIVE_SECONDS = 15.0


class SnapshotRoutes:
    """The /api/snapshot and /api/events routes.

    Attributes:
        router: The FastAPI router holding the routes.
    """

    def __init__(
        self,
        snapshot_builder: DashboardSnapshot,
        guard: SessionGuard,
        check_interval_seconds: float = 2.0,
    ):
        """Creates the routes.

        Args:
            snapshot_builder (DashboardSnapshot): Builds the document.
            guard (SessionGuard): Requires a logged-in session.
            check_interval_seconds (float): How often the event stream looks for changes.
        """
        self.snapshot_builder = snapshot_builder
        self.check_interval_seconds = check_interval_seconds
        self.router = fastapi.APIRouter(
            dependencies=[
                fastapi.Depends(guard.require_session),
            ],
        )
        self.router.add_api_route(
            '/api/snapshot',
            self.snapshot,
            methods=[
                'GET',
            ],
        )
        self.router.add_api_route(
            '/api/events',
            self.events,
            methods=[
                'GET',
            ],
        )

    def snapshot(self) -> dict[str, Any]:
        """Returns the current document.

        Returns:
            dict[str, Any]: The dashboard snapshot.
        """
        return self.snapshot_builder.build()

    def events(self, request: fastapi.Request) -> fastapi.responses.StreamingResponse:
        """Streams the document whenever it changes.

        Args:
            request (fastapi.Request): The request, to notice when the browser leaves.

        Returns:
            fastapi.responses.StreamingResponse: A text/event-stream response.
        """
        return fastapi.responses.StreamingResponse(
            self._event_stream(request),
            media_type='text/event-stream',
            headers={
                'Cache-Control': 'no-cache',
                'X-Accel-Buffering': 'no',
            },
        )

    async def _event_stream(self, request: fastapi.Request) -> AsyncIterator[str]:
        """Produces server-sent event messages until the browser disconnects.

        Args:
            request (fastapi.Request): The request.

        Yields:
            str: The next event or keepalive comment.
        """
        last_marker = None
        last_sent = 0.0
        while not await request.is_disconnected():
            marker = self.snapshot_builder.change_marker()
            now = time.monotonic()
            if marker != last_marker:
                payload = json.dumps(self.snapshot_builder.build())
                yield f'event: snapshot\ndata: {payload}\n\n'
                last_marker = marker
                last_sent = now
            elif now - last_sent >= _KEEPALIVE_SECONDS:
                yield ': keepalive\n\n'
                last_sent = now
            await asyncio.sleep(self.check_interval_seconds)
