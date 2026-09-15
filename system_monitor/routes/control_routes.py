"""The route that starts or restarts a UBI service.

Typical usage example:

  application.include_router(ControlRoutes(controller, guard).router)
"""

import dataclasses
from typing import Any

import fastapi
import starlette.concurrency

from system_monitor.controls.unit_controller import UnitController, UnitNotAllowedError
from system_monitor.security.session_guard import SessionGuard


class ControlRoutes:
    """The /api/units routes.

    Attributes:
        router: The FastAPI router holding the routes.
    """

    def __init__(self, controller: UnitController, guard: SessionGuard):
        """Creates the routes.

        Args:
            controller (UnitController): Performs the actions.
            guard (SessionGuard): Requires a logged-in session and the dashboard header.
        """
        self.controller = controller
        self.router = fastapi.APIRouter(
            dependencies=[
                fastapi.Depends(guard.require_session),
                fastapi.Depends(guard.require_dashboard_header),
            ],
        )
        self.router.add_api_route(
            '/api/units/{unit_name}/{action}',
            self.perform,
            methods=[
                'POST',
            ],
        )

    async def perform(self, request: fastapi.Request, unit_name: str, action: str) -> dict[str, Any]:
        """Starts or restarts a unit.

        Args:
            request (fastapi.Request): The request, for the client's address.
            unit_name (str): The exact unit name.
            action (str): "start" or "restart".

        Returns:
            dict[str, Any]: The recorded action.

        Raises:
            fastapi.HTTPException: 400 for an unsupported action, 403 for a unit outside UBI, 502 when systemctl refused.
        """
        address = 'unknown'
        if request.client is not None:
            address = request.client.host
        try:
            recorded = await starlette.concurrency.run_in_threadpool(
                self.controller.perform,
                unit_name,
                action,
                address,
            )
        except ValueError as error:
            raise fastapi.HTTPException(status_code=400, detail=str(error)) from error
        except UnitNotAllowedError as error:
            raise fastapi.HTTPException(status_code=403, detail=str(error)) from error
        if not recorded.succeeded:
            raise fastapi.HTTPException(status_code=502, detail=recorded.message)
        return dataclasses.asdict(recorded)
