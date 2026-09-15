# frontend/

## Shape

```
src/
├── main.tsx                     mounts <App/>
├── App.tsx                      session check → LoginPage or Dashboard (header, navigation, routes)
├── api/types.ts                 the snapshot document's TypeScript shape, mirroring the Python CheckResult
├── api/apiClient.ts             ApiClient class: every fetch, and the X-Requested-With header
├── hooks/useMonitorSnapshot.ts  EventSource on /api/events, reconnect, notices logout
├── hooks/useNow.ts              one-second clock for "updated N s ago"
├── utilities/checkIndex.ts      CheckIndex class: grouping, worst status, problem ordering
├── utilities/formatter.ts       Formatter class: durations, India times, numbers
├── components/                  StatusBadge + StatusIcon, Sparkline, UnitActionButton
└── pages/                       Overview, Services, SessionsAndFeeds, Pipeline, Logs, Login
```

## Why function components while the user prefers object-oriented code

React's supported style is function components with hooks; class components are legacy and do not work with hooks. So the parts React owns are functions, and everything that is ordinary logic (API calls, grouping and ranking checks, formatting) lives in classes: `ApiClient`, `CheckIndex`, `Formatter`. That keeps the object-oriented rule where it has meaning without fighting the framework.

## The front end never judges

Every status comes from the Python collectors. Pages only group, sort and colour. If a rule needs to change ("stoxkart feeds may be quiet for longer"), it changes in `thresholds.toml` or a collector, and every page and the desktop alerts agree automatically.

## Colour and accessibility

The status colours and surfaces come from the dataviz reference palette: good `#0ca30c`, warning `#fab219`, critical `#d03b3b`, neutral `#898781`; light surface `#fcfcfb` on page `#f9f9f7`, dark surface `#1a1a19` on page `#0d0d0d`. Status is never colour alone: every status has a distinct icon shape (circle with tick, triangle, octagon with cross, hollow circle with dash, hollow circle with question mark) and a text label in ordinary ink. Failing and warning rows get a faint tint for scanning, not for meaning.

The sparklines follow the reference mark specs: a 2 px line in the single series blue, a 10 % area wash, a 4 px-radius end dot with a 2 px surface ring, a hover crosshair with a value-first tooltip, and an `aria-label` that states the latest and peak values so the trend is available without hovering. No categorical palette is used, so there was nothing to run through the palette validator.

Dark mode follows the operating system through `prefers-color-scheme`.

## Dates

`Intl.DateTimeFormat` in current Chrome writes September as "Sept" for both `en-IN` and `en-GB`, while the server's Python messages write "Sep". `Formatter.dayAndMonth` builds the month from a fixed list so the two never disagree on the same page.

## Services page layout

With 122 services, a fully expanded page was 7,686 px tall on a 1440 px wide screenshot. Each broker's services are now a `<details>` section that opens by itself only when it contains a warning, failure or unknown check, which brought the page to 1,700 px.

## Log view

`LogStream` is keyed by unit name so switching units closes the old EventSource (and therefore the server's journalctl) and opens a new one. Pausing buffers lines instead of dropping them. At most 2,000 lines are kept in the browser.

## Build

`npm run build` runs `tsc --noEmit` and then Vite. The output in `dist/` is git-ignored; FastAPI serves it from `SYSTEM_MONITOR_FRONTEND_DIRECTORY`. Node is only needed to build; it was installed with nvm into `~/.nvm` without touching `.bashrc`, so a new shell needs `source ~/.nvm/nvm.sh` first.

## How it was checked

The Chrome extension was not connected on 2026-09-15, so a headless Chrome driven by `puppeteer-core` (installed in the session scratchpad, not the project) logged in through the real form against the live system and captured every page at 1440 px, in dark mode and at 400 px. It confirmed no console errors, no horizontal page overflow at 400 px, live header updates, the sparkline tooltip, the log stream, and that the restart dialog closes on Cancel without acting.
