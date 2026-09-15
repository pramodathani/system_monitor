# session_guard.py

## Threat model

The dashboard is reachable from the home network and has restart buttons, so two things matter:

1. **Someone on the network without the password.** Every data, log and control route requires a session. Logs are included because UBI's logs can contain account identifiers and broker responses.
2. **A malicious web page open in the user's own browser (cross-site request forgery).** The browser would attach the session cookie to a request that page sends. Two defences stack:
   - The cookie is `SameSite=Strict`, so browsers do not send it on requests started by another site.
   - State-changing routes (login, logout, unit actions) require the `X-Requested-With: system-monitor` header. A plain HTML form cannot set custom headers, and a script on another origin would need a CORS preflight, which this server never approves because it has no CORS middleware.

## The cookie

Starlette's `SessionMiddleware` signs the session with `itsdangerous` using `SYSTEM_MONITOR_SESSION_SECRET` and always sets `HttpOnly`, so scripts in the page cannot read it. `https_only` is off because the server speaks plain HTTP on the LAN; see the known limitation in the plan and README.

Logging in clears the session first, so a session value set before login cannot survive into the logged-in session.
