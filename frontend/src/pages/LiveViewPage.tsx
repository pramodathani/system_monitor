import { useCallback, useEffect, useMemo, useState } from 'react';

import { ApiError, apiClient } from '../api/apiClient';
import type {
  DatabaseHealth,
  LiveCatalogue,
  LiveDocument,
  LiveHashDocuments,
  LiveView,
  LiveViewAnswer,
} from '../api/liveTypes';
import { DatabaseCard } from '../components/DatabaseCard';
import { JsonView } from '../components/JsonView';
import { LiveTable } from '../components/LiveTable';
import { UbiApiConsole } from '../components/UbiApiConsole';
import { Formatter } from '../utilities/formatter';

const REFRESH_SECONDS = 5;

type Section = 'databases' | 'broker' | 'unified' | 'api';

const SECTION_LABELS: Array<[Section, string]> = [
  ['databases', 'Databases'],
  ['broker', 'Broker'],
  ['unified', 'Unified'],
  ['api', 'REST API'],
];

/**
 * The live view: what Redis holds right now, how the three stores are doing, and UBI's own API.
 *
 * This page reads on demand rather than from the dashboard's snapshot, because it shows the stored
 * values themselves rather than a judgement about them. The small documents re-read on a timer,
 * which can be paused; the three instrument tables run to hundreds of thousands of rows and are
 * only read when asked.
 * @returns The page.
 */
export function LiveViewPage() {
  const [catalogue, setCatalogue] = useState<LiveCatalogue | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [section, setSection] = useState<Section>('databases');

  useEffect(() => {
    apiClient
      .fetchLiveCatalogue()
      .then(setCatalogue)
      .catch((caught) => setError(caught instanceof ApiError ? caught.message : String(caught)));
  }, []);

  if (error !== null) {
    return (
      <div className="page">
        <section className="card">
          <p className="live-error">{error}</p>
        </section>
      </div>
    );
  }
  if (catalogue === null) {
    return <p className="empty centered">Reading what is in Redis…</p>;
  }

  return (
    <div className="page">
      <nav className="section-tabs" aria-label="Live view sections">
        {SECTION_LABELS.map(([name, label]) => (
          <button
            key={name}
            type="button"
            className={section === name ? 'section-tab section-tab-current' : 'section-tab'}
            aria-pressed={section === name}
            onClick={() => setSection(name)}
          >
            {label}
          </button>
        ))}
      </nav>

      {section === 'databases' ? <DatabasesSection /> : null}
      {section === 'broker' ? (
        <ScopeSection scope="broker" views={catalogue.broker_views} brokers={catalogue.brokers} alwaysChooseBroker />
      ) : null}
      {section === 'unified' ? (
        <ScopeSection
          scope="unified"
          views={catalogue.unified_views}
          brokers={catalogue.brokers}
          alwaysChooseBroker={false}
          mappingDate={catalogue.mapping_date}
        />
      ) : null}
      {section === 'api' ? <UbiApiConsole endpoints={catalogue.api_endpoints} /> : null}
    </div>
  );
}

/**
 * The three data stores, re-read on a timer.
 * @returns The section.
 */
function DatabasesSection() {
  const [health, setHealth] = useState<DatabaseHealth | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [paused, setPaused] = useState(false);

  const read = useCallback(() => {
    apiClient
      .fetchDatabaseHealth()
      .then((answer) => {
        setHealth(answer);
        setError(null);
      })
      .catch((caught) => setError(caught instanceof ApiError ? caught.message : String(caught)));
  }, []);

  useEffect(() => {
    read();
    if (paused) {
      return undefined;
    }
    const timer = window.setInterval(read, REFRESH_SECONDS * 1000);
    return () => window.clearInterval(timer);
  }, [read, paused]);

  return (
    <>
      <section className="card">
        <div className="filter-row">
          <h2>Data stores</h2>
          <RefreshControl paused={paused} onToggle={() => setPaused(!paused)} onRefresh={read} />
          {health === null ? null : (
            <span className="muted">read at {Formatter.clockWithSeconds(health.read_at)}</span>
          )}
        </div>
        {error === null ? null : <p className="live-error">{error}</p>}
        {health?.docker_error === null || health?.docker_error === undefined ? null : (
          <p className="live-warning">Docker could not be read, so container details are missing: {health.docker_error}</p>
        )}
      </section>
      {health === null ? (
        <p className="empty">Reading the stores…</p>
      ) : (
        health.stores.map((store) => <DatabaseCard key={store.name} store={store} now={health.read_at} />)
      )}
    </>
  );
}

/** Props for ScopeSection. */
interface ScopeSectionProps {
  scope: string;
  views: LiveView[];
  brokers: string[];
  alwaysChooseBroker: boolean;
  mappingDate?: string | null;
}

/**
 * One group of tabs, with the broker dropdown the group needs.
 * @param props The scope, its tabs, the brokers to offer and whether every tab needs one.
 * @returns The section.
 */
function ScopeSection(props: ScopeSectionProps) {
  const { scope, views, brokers, alwaysChooseBroker, mappingDate } = props;
  const [chosen, setChosen] = useState(views[0]?.name ?? '');
  const [broker, setBroker] = useState(brokers[0] ?? '');

  const view = useMemo(() => views.find((candidate) => candidate.name === chosen) ?? null, [views, chosen]);
  const needsBroker = alwaysChooseBroker || (view?.needs_broker ?? false);

  return (
    <>
      <section className="card">
        <div className="filter-row">
          {needsBroker ? (
            <label>
              Broker{' '}
              <select value={broker} onChange={(event) => setBroker(event.target.value)}>
                {brokers.map((name) => (
                  <option key={name} value={name}>
                    {name}
                  </option>
                ))}
              </select>
            </label>
          ) : null}
          {mappingDate === undefined || mappingDate === null ? null : (
            <span className="muted">mapped for {mappingDate}</span>
          )}
        </div>
        <nav className="section-tabs section-tabs-inner" aria-label={`${scope} tabs`}>
          {views.map((candidate) => (
            <button
              key={candidate.name}
              type="button"
              className={chosen === candidate.name ? 'section-tab section-tab-current' : 'section-tab'}
              aria-pressed={chosen === candidate.name}
              onClick={() => setChosen(candidate.name)}
            >
              {candidate.label}
            </button>
          ))}
        </nav>
      </section>

      {view === null ? null : (
        <section className="card">
          <h2>{view.label}</h2>
          <p className="card-hint">{view.note}</p>
          {view.kind === 'table' ? (
            <LiveTable scope={scope} view={view} broker={needsBroker ? broker : null} />
          ) : (
            <DocumentPanel scope={scope} view={view} broker={needsBroker ? broker : null} />
          )}
        </section>
      )}
    </>
  );
}

/** Props for DocumentPanel. */
interface DocumentPanelProps {
  scope: string;
  view: LiveView;
  broker: string | null;
}

/**
 * One tab that shows a stored document, re-read on a timer.
 * @param props The scope, the tab and the broker chosen.
 * @returns The document.
 */
function DocumentPanel(props: DocumentPanelProps) {
  const { scope, view, broker } = props;
  const [answer, setAnswer] = useState<LiveViewAnswer<LiveDocument | LiveHashDocuments> | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [paused, setPaused] = useState(false);
  const [readAt, setReadAt] = useState<number | null>(null);

  const read = useCallback(() => {
    apiClient
      .fetchLiveView(scope, view.name, broker)
      .then((fetched) => {
        setAnswer(fetched);
        setReadAt(Date.now() / 1000);
        setError(null);
      })
      .catch((caught) => setError(caught instanceof ApiError ? caught.message : String(caught)));
  }, [scope, view.name, broker]);

  useEffect(() => {
    setAnswer(null);
    read();
    if (paused) {
      return undefined;
    }
    const timer = window.setInterval(read, REFRESH_SECONDS * 1000);
    return () => window.clearInterval(timer);
  }, [read, paused]);

  return (
    <div className="document-panel">
      <div className="filter-row">
        <RefreshControl paused={paused} onToggle={() => setPaused(!paused)} onRefresh={read} />
        {readAt === null ? null : <span className="muted">read at {Formatter.clockWithSeconds(readAt)}</span>}
      </div>
      {error === null ? null : <p className="live-error">{error}</p>}
      {answer === null ? <p className="empty">Reading…</p> : <DocumentBody answer={answer} />}
    </div>
  );
}

/** Props for DocumentBody. */
interface DocumentBodyProps {
  answer: LiveViewAnswer<LiveDocument | LiveHashDocuments>;
}

/**
 * The document itself, under a line saying which key it came from.
 * @param props The tab and its value.
 * @returns The body.
 */
function DocumentBody(props: DocumentBodyProps) {
  const { answer } = props;
  const value = answer.value;

  if ('entries' in value) {
    return <HashDocumentsBody value={value} />;
  }
  return (
    <>
      <p className="card-hint">
        <code>{value.key}</code>
        {value.field === undefined ? '' : ` field ${value.field}`}
        {value.exists ? `, ${Formatter.number(value.byte_size)} bytes` : ''}
        {value.expires_in_seconds === null
          ? ''
          : `, expiring in ${Formatter.duration(value.expires_in_seconds)}`}
        .
      </p>
      {!value.exists ? (
        <p className="empty">Redis holds no such key. Nothing has written it.</p>
      ) : value.text !== null ? (
        <pre className="live-raw">{value.text}</pre>
      ) : (
        <div className="json-root">
          <JsonView value={value.document} />
        </div>
      )}
    </>
  );
}

/** Props for HashDocumentsBody. */
interface HashDocumentsBodyProps {
  value: LiveHashDocuments;
}

/**
 * A hash with a document in every field, such as a broker's order book.
 * @param props The hash as the server read it.
 * @returns The entries.
 */
function HashDocumentsBody(props: HashDocumentsBodyProps) {
  const { value } = props;
  const polledAt = value.polled_at === null ? null : Number(value.polled_at);
  return (
    <>
      <p className="card-hint">
        <code>{value.key}</code> holds {Formatter.number(value.field_count)}{' '}
        {value.field_count === 1 ? 'entry' : 'entries'}
        {polledAt === null || Number.isNaN(polledAt)
          ? ''
          : `, last read at ${Formatter.clockWithSeconds(polledAt)}`}
        {value.expires_in_seconds === null
          ? ''
          : `, expiring in ${Formatter.duration(value.expires_in_seconds)}`}
        .
      </p>
      {value.entries.length === 0 ? (
        <p className="empty">
          {value.exists ? 'The hash is empty.' : 'Redis holds no such key. Nothing has written it.'}
        </p>
      ) : (
        <div className="json-root">
          {value.entries.map((entry) => (
            <details key={entry.field} className="json-branch" open={value.entries.length <= 3}>
              <summary>
                <span className="json-key">{entry.field}</span>
              </summary>
              <div className="json-children">
                {entry.text === null ? (
                  <JsonView value={entry.document} />
                ) : (
                  <pre className="live-raw">{entry.text}</pre>
                )}
              </div>
            </details>
          ))}
        </div>
      )}
    </>
  );
}

/** Props for RefreshControl. */
interface RefreshControlProps {
  paused: boolean;
  onToggle: () => void;
  onRefresh: () => void;
}

/**
 * The pause and refresh buttons every re-reading panel carries.
 * @param props Whether the timer is paused and what to do when each button is pressed.
 * @returns The controls.
 */
function RefreshControl(props: RefreshControlProps) {
  const { paused, onToggle, onRefresh } = props;
  return (
    <span className="refresh-control">
      <button type="button" className="button button-quiet" onClick={onToggle}>
        {paused ? 'Resume' : 'Pause'}
      </button>
      <button type="button" className="button button-quiet" onClick={onRefresh}>
        Refresh
      </button>
      <span className="muted">{paused ? 'paused' : `every ${REFRESH_SECONDS} s`}</span>
    </span>
  );
}
