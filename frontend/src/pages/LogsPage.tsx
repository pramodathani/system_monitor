import { useEffect, useLayoutEffect, useRef, useState } from 'react';
import { useSearchParams } from 'react-router';

import { apiClient } from '../api/apiClient';
import type { Check, LogLine, Snapshot } from '../api/types';
import { StatusIcon } from '../components/StatusBadge';
import { Formatter } from '../utilities/formatter';

const MAXIMUM_LINES = 2000;
const INITIAL_LINES = 200;

type LevelFilter = 'all' | 'warnings' | 'errors';

/** Props for LogsPage. */
interface LogsPageProps {
  snapshot: Snapshot;
}

/**
 * A live view of one UBI unit's journal, with units ranked by recent errors.
 * @param props The latest snapshot, for the unit list and counts.
 * @returns The page.
 */
export function LogsPage(props: LogsPageProps) {
  const { snapshot } = props;
  const [searchParameters, setSearchParameters] = useSearchParams();
  const selectedUnit = searchParameters.get('unit');
  const [search, setSearch] = useState('');

  const logChecks: Check[] = [];
  for (const check of snapshot.checks) {
    if (check.area === 'logs') {
      logChecks.push(check);
    }
  }
  logChecks.sort((first, second) => {
    const byErrors = (Formatter.asNumber(second.details.errors) ?? 0) - (Formatter.asNumber(first.details.errors) ?? 0);
    if (byErrors !== 0) {
      return byErrors;
    }
    const byWarnings = (Formatter.asNumber(second.details.warnings) ?? 0) - (Formatter.asNumber(first.details.warnings) ?? 0);
    if (byWarnings !== 0) {
      return byWarnings;
    }
    return first.name.localeCompare(second.name);
  });
  const shownChecks = logChecks.filter((check) => check.name.includes(search.trim()));

  return (
    <div className="page logs-page">
      <aside className="card unit-list" aria-label="Units">
        <h2>Units</h2>
        <input type="search" placeholder="Filter units" value={search} onChange={(event) => setSearch(event.target.value)} aria-label="Filter units" />
        <ul>
          {shownChecks.map((check) => {
            const unitName = Formatter.asText(check.details.unit);
            const errors = Formatter.asNumber(check.details.errors) ?? 0;
            const warnings = Formatter.asNumber(check.details.warnings) ?? 0;
            return (
              <li key={check.check_id}>
                <button
                  type="button"
                  className="unit-button"
                  aria-current={unitName === selectedUnit}
                  onClick={() => setSearchParameters({ unit: unitName })}
                >
                  <StatusIcon status={errors > 0 ? 'warning' : 'ok'} />
                  <span className="unit-name">{check.name}</span>
                  <span className="muted numeric">
                    {errors}E {warnings}W
                  </span>
                </button>
              </li>
            );
          })}
        </ul>
        <p className="card-hint">E and W count errors and warnings in the last 15 minutes.</p>
      </aside>
      <section className="card log-view">
        {selectedUnit ? <LogStream key={selectedUnit} unitName={selectedUnit} /> : <p className="empty">Choose a unit to follow its journal live.</p>}
      </section>
    </div>
  );
}

/** Props for LogStream. */
interface LogStreamProps {
  unitName: string;
}

/**
 * Follows one unit's journal over server-sent events.
 * @param props The unit to follow.
 * @returns The controls and the lines.
 */
function LogStream(props: LogStreamProps) {
  const { unitName } = props;
  const [lines, setLines] = useState<LogLine[]>([]);
  const [paused, setPaused] = useState(false);
  const [filter, setFilter] = useState<LevelFilter>('all');
  const [connected, setConnected] = useState(false);
  const pausedReference = useRef(false);
  const bufferReference = useRef<LogLine[]>([]);
  const [bufferedCount, setBufferedCount] = useState(0);
  const scrollReference = useRef<HTMLDivElement>(null);
  const stickToBottomReference = useRef(true);

  useEffect(() => {
    const source = new EventSource(apiClient.logStreamUrl(unitName, INITIAL_LINES));
    source.addEventListener('open', () => setConnected(true));
    source.addEventListener('error', () => setConnected(false));
    source.addEventListener('line', (event) => {
      const line = JSON.parse((event as MessageEvent<string>).data) as LogLine;
      if (pausedReference.current) {
        bufferReference.current.push(line);
        setBufferedCount(bufferReference.current.length);
        return;
      }
      setLines((previous) => {
        const next = previous.concat(line);
        return next.length > MAXIMUM_LINES ? next.slice(next.length - MAXIMUM_LINES) : next;
      });
    });
    return () => source.close();
  }, [unitName]);

  useLayoutEffect(() => {
    const container = scrollReference.current;
    if (container && stickToBottomReference.current) {
      container.scrollTop = container.scrollHeight;
    }
  }, [lines, filter]);

  const togglePause = () => {
    if (pausedReference.current) {
      const buffered = bufferReference.current;
      bufferReference.current = [];
      setBufferedCount(0);
      setLines((previous) => {
        const next = previous.concat(buffered);
        return next.length > MAXIMUM_LINES ? next.slice(next.length - MAXIMUM_LINES) : next;
      });
    }
    pausedReference.current = !pausedReference.current;
    setPaused(pausedReference.current);
  };

  const visible = lines.filter((line) => {
    if (filter === 'errors') {
      return line.level === 'ERROR' || line.level === 'CRITICAL';
    }
    if (filter === 'warnings') {
      return line.level !== 'INFO' && line.level !== 'DEBUG';
    }
    return true;
  });

  return (
    <>
      <div className="log-toolbar">
        <h2>{unitName}</h2>
        <span className="muted">{connected ? 'Following live' : 'Connecting…'}</span>
        <label>
          Show{' '}
          <select value={filter} onChange={(event) => setFilter(event.target.value as LevelFilter)}>
            <option value="all">All lines</option>
            <option value="warnings">Warnings and errors</option>
            <option value="errors">Errors only</option>
          </select>
        </label>
        <button type="button" className="button" onClick={togglePause}>
          {paused ? `Resume${bufferedCount > 0 ? ` (${bufferedCount} new)` : ''}` : 'Pause'}
        </button>
        <button type="button" className="button" onClick={() => setLines([])}>
          Clear
        </button>
      </div>
      <div
        className="log-lines"
        ref={scrollReference}
        onScroll={(event) => {
          const container = event.currentTarget;
          stickToBottomReference.current = container.scrollHeight - container.scrollTop - container.clientHeight < 40;
        }}
      >
        {visible.length === 0 ? (
          <p className="empty">No lines to show yet.</p>
        ) : (
          visible.map((line, lineIndex) => (
            <div key={`${line.timestamp}-${lineIndex}`} className={`log-line log-line-${line.level.toLowerCase()}`}>
              <span className="log-time">{Formatter.clockWithSeconds(line.timestamp)}</span>
              <span className="log-level">{line.continuation ? '' : line.level}</span>
              <span className="log-text">{line.text}</span>
            </div>
          ))
        )}
      </div>
    </>
  );
}
