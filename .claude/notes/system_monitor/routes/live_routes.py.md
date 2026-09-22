# live_routes.py

## Why these routes do not use the collectors' state

Every other route answers from `MonitorState`, which the collectors fill on their own intervals. These read Redis, the databases and the REST API at the moment they are called. The difference is deliberate: the dashboard shows a judgement about a value, and the live view shows the value. A snapshot taken up to five minutes ago is right for the first and wrong for the second.

## Why the handlers are plain synchronous methods

Each one makes a blocking call into Redis, a database driver or httpx. FastAPI runs a non-async handler in its worker threadpool, so a slow read blocks a worker rather than the event loop that the server-sent event streams live on. Writing them as `async def` and blocking inside would stall every open dashboard.

## Why the API route ignores unknown query parameters

`call_api` passes the whole query string to `ApiCaller`, which keeps only the parameters the chosen endpoint declares. The alternative, declaring each endpoint's parameters as FastAPI arguments, would mean twenty route signatures that have to be kept in step with UBI's own. Filtering in one place against the catalogue is both shorter and the thing that stops an unexpected parameter reaching UBI.
