"""FastAPI dependencies that protect routes with the login session.

Typical usage example:

  guard = SessionGuard()
  router.add_api_route('/api/snapshot', handler, dependencies=[Depends(guard.require_session)])
"""

import fastapi

REQUESTED_WITH_HEADER = 'X-Requested-With'
REQUESTED_WITH_VALUE = 'system-monitor'
AUTHENTICATED_KEY = 'authenticated'


class SessionGuard:
    """Checks the signed session cookie and the header that marks the dashboard's own requests."""

    def require_session(self, request: fastapi.Request) -> None:
        """Rejects a request without a logged-in session.

        Args:
            request (fastapi.Request): The incoming request.

        Raises:
            fastapi.HTTPException: 401 when the session is not logged in.
        """
        if request.session.get(AUTHENTICATED_KEY) is not True:
            raise fastapi.HTTPException(status_code=401, detail='Login required.')

    def require_dashboard_header(self, request: fastapi.Request) -> None:
        """Rejects a state-changing request that did not come from the dashboard's own script.

        A form on another website can post to this server with the user's cookie, but it cannot add a custom header without a CORS preflight, which this server never allows.

        Args:
            request (fastapi.Request): The incoming request.

        Raises:
            fastapi.HTTPException: 403 when the header is missing or wrong.
        """
        if request.headers.get(REQUESTED_WITH_HEADER) != REQUESTED_WITH_VALUE:
            raise fastapi.HTTPException(status_code=403, detail=f'Missing {REQUESTED_WITH_HEADER} header.')

    def log_in(self, request: fastapi.Request, now: float) -> None:
        """Marks the request's session as logged in.

        Args:
            request (fastapi.Request): The login request.
            now (float): The login time, in epoch seconds.
        """
        request.session.clear()
        request.session[AUTHENTICATED_KEY] = True
        request.session['logged_in_at'] = now

    def log_out(self, request: fastapi.Request) -> None:
        """Clears the request's session.

        Args:
            request (fastapi.Request): The logout request.
        """
        request.session.clear()

    def is_logged_in(self, request: fastapi.Request) -> bool:
        """Checks whether the request's session is logged in.

        Args:
            request (fastapi.Request): The incoming request.

        Returns:
            bool: True when logged in.
        """
        return request.session.get(AUTHENTICATED_KEY) is True
