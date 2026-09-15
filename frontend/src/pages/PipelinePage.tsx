import type { Check, Snapshot } from '../api/types';
import { Sparkline } from '../components/Sparkline';
import { StatusBadge, StatusIcon } from '../components/StatusBadge';
import { CheckIndex } from '../utilities/checkIndex';
import { Formatter } from '../utilities/formatter';

const DATASETS = [
  'orders',
  'positions',
  'trades',
  'funds',
  'holdings',
];

/** Props for PipelinePage. */
interface PipelinePageProps {
  snapshot: Snapshot;
}

/**
 * Stream lag, order and portfolio freshness, reference data, data stores and the monitor's own collectors.
 * @param props The latest snapshot.
 * @returns The page.
 */
export function PipelinePage(props: PipelinePageProps) {
  const { snapshot } = props;
  const index = new CheckIndex(snapshot.checks);
  const now = snapshot.generated_at;
  const streams = [...index.inAreas(['streams'])].sort((first, second) => CheckIndex.severity(second.status) - CheckIndex.severity(first.status));
  const referenceData = index.inAreas(['reference_data']);
  const dataStores = index.inAreas(['data_stores']);

  return (
    <div className="page">
      <section className="card">
        <h2>Orders and portfolio freshness</h2>
        <p className="card-hint">Each cell shows how long ago the dataset was last read. Hover or focus a cell for the full explanation.</p>
        <div className="table-scroll">
          <table className="grid-table">
            <thead>
              <tr>
                <th scope="col">Broker</th>
                {DATASETS.map((dataset) => (
                  <th key={dataset} scope="col">
                    {dataset}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {index.subjects().map((subject) => (
                <tr key={subject}>
                  <th scope="row">{subject}</th>
                  {DATASETS.map((dataset) => {
                    const check = index.find(`portfolio:${subject}:${dataset}`);
                    return <td key={dataset}>{check ? <FreshnessCell check={check} /> : <span className="muted">—</span>}</td>;
                  })}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      <section className="card">
        <h2>Redis stream consumer groups</h2>
        <p className="card-hint">Lag is how many entries a group has not read yet. Entries older than the stream's cap are trimmed, so lag near the cap means lost data.</p>
        <div className="table-scroll">
          <table className="data-table">
            <thead>
              <tr>
                <th scope="col">Status</th>
                <th scope="col">Stream and group</th>
                <th scope="col" className="numeric">
                  Lag
                </th>
                <th scope="col">Last 15 minutes</th>
                <th scope="col" className="numeric">
                  Pending
                </th>
                <th scope="col" className="numeric">
                  Length / cap
                </th>
                <th scope="col">What it means</th>
              </tr>
            </thead>
            <tbody>
              {streams.map((check) => {
                const length = Formatter.asNumber(check.details.length);
                const cap = Formatter.asNumber(check.details.cap);
                const pending = Formatter.asNumber(check.details.pending);
                return (
                  <tr key={check.check_id} className={`row-${check.status}`}>
                    <td>
                      <StatusBadge status={check.status} />
                    </td>
                    <td>
                      {check.subject} · {check.name}
                    </td>
                    <td className="numeric">{check.value === null ? '—' : Formatter.number(check.value)}</td>
                    <td>
                      <Sparkline points={check.history} unit="entries" label={`${check.subject} ${check.name} lag`} />
                    </td>
                    <td className="numeric">{pending === null ? '—' : Formatter.number(pending)}</td>
                    <td className="numeric nowrap">
                      {length === null ? '—' : Formatter.number(length)} / {cap === null ? '—' : Formatter.number(cap)}
                    </td>
                    <td>{check.message}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </section>

      <div className="two-columns">
        <section className="card">
          <h2>Reference data</h2>
          <CheckList checks={referenceData} now={now} />
        </section>
        <section className="card">
          <h2>Data stores and containers</h2>
          <CheckList checks={dataStores} now={now} />
        </section>
      </div>

      <section className="card">
        <h2>Monitor collectors</h2>
        <p className="card-hint">How the monitor itself is doing: when each collector last ran and whether it could read its source.</p>
        <div className="table-scroll">
          <table className="data-table compact">
            <thead>
              <tr>
                <th scope="col">Status</th>
                <th scope="col">Collector</th>
                <th scope="col" className="numeric">
                  Checks
                </th>
                <th scope="col" className="numeric">
                  Last run
                </th>
                <th scope="col" className="numeric">
                  Took
                </th>
                <th scope="col">Error</th>
              </tr>
            </thead>
            <tbody>
              {snapshot.collectors.map((collector) => (
                <tr key={collector.name} className={collector.error ? 'row-unknown' : ''}>
                  <td>
                    <StatusBadge status={collector.error ? 'unknown' : 'ok'} label={collector.error ? 'Failed' : 'OK'} />
                  </td>
                  <td>{collector.name.replaceAll('_', ' ')}</td>
                  <td className="numeric">{collector.check_count}</td>
                  <td className="numeric nowrap">{Formatter.duration(now - collector.started_at)} ago</td>
                  <td className="numeric">{Formatter.number(collector.duration_seconds * 1000)} ms</td>
                  <td>{collector.error ?? ''}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  );
}

/** Props for FreshnessCell. */
interface FreshnessCellProps {
  check: Check;
}

/**
 * One dataset's freshness: its status icon and how long ago it was read.
 * @param props The dataset's check.
 * @returns The cell content.
 */
function FreshnessCell(props: FreshnessCellProps) {
  const { check } = props;
  const age = Formatter.asNumber(check.details.age_seconds);
  return (
    <span className={`grid-cell grid-cell-${check.status} grid-cell-static`} title={check.message} tabIndex={0}>
      <StatusIcon status={check.status} />
      <span>{age === null ? CheckIndex.label(check.status) : Formatter.duration(age)}</span>
    </span>
  );
}

/** Props for CheckList. */
interface CheckListProps {
  checks: Check[];
  now: number;
}

/**
 * A plain list of checks with status, subject, name and message.
 * @param props The checks and the snapshot time.
 * @returns The list.
 */
function CheckList(props: CheckListProps) {
  const { checks, now } = props;
  if (checks.length === 0) {
    return <p className="empty">No checks yet.</p>;
  }
  return (
    <ul className="problem-list">
      {checks.map((check) => (
        <li key={check.check_id} className={`problem problem-${check.status}`}>
          <StatusBadge status={check.status} />
          <span className="problem-title">
            {check.subject === 'platform' ? check.name : `${check.subject} · ${check.name}`}
          </span>
          <span className="problem-message">{check.message}</span>
          <span className="muted problem-since">for {Formatter.duration(now - check.status_since)}</span>
        </li>
      ))}
    </ul>
  );
}
