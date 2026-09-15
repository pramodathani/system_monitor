import { useState } from 'react';

import type { Check, CheckStatus, Snapshot } from '../api/types';
import { StatusBadge, StatusIcon } from '../components/StatusBadge';
import { CheckIndex } from '../utilities/checkIndex';
import { Formatter } from '../utilities/formatter';

interface OverviewColumn {
  key: string;
  label: string;
  areas: string[];
}

const OVERVIEW_COLUMNS: OverviewColumn[] = [
  {
    key: 'services',
    label: 'Services',
    areas: [
      'services',
    ],
  },
  {
    key: 'timers',
    label: 'Daily jobs',
    areas: [
      'timers',
    ],
  },
  {
    key: 'sessions',
    label: 'Login',
    areas: [
      'sessions',
    ],
  },
  {
    key: 'feeds',
    label: 'Quote feed',
    areas: [
      'feeds',
      'quotes_pipeline',
    ],
  },
  {
    key: 'streams',
    label: 'Streams',
    areas: [
      'streams',
    ],
  },
  {
    key: 'portfolio',
    label: 'Orders & portfolio',
    areas: [
      'portfolio',
    ],
  },
  {
    key: 'reference',
    label: 'Reference data',
    areas: [
      'reference_data',
    ],
  },
  {
    key: 'logs',
    label: 'Logs',
    areas: [
      'logs',
    ],
  },
];

const SUMMARY_STATUSES: CheckStatus[] = [
  'failure',
  'warning',
  'unknown',
  'ok',
  'idle',
];

/** Props for OverviewPage. */
interface OverviewPageProps {
  snapshot: Snapshot;
}

/**
 * The landing page: counts, shared infrastructure, a broker-by-area grid and the list of problems.
 * @param props The latest snapshot.
 * @returns The page.
 */
export function OverviewPage(props: OverviewPageProps) {
  const { snapshot } = props;
  const index = new CheckIndex(snapshot.checks);
  const counts = index.countByStatus();
  const problems = index.problems();
  const [selected, setSelected] = useState<{ subject: string; column: OverviewColumn } | null>(null);
  const platformChecks = [...index.forSubject('platform', ['data_stores'])].sort((first, second) => {
    const firstIsContainer = first.name.startsWith('Container') ? 1 : 0;
    const secondIsContainer = second.name.startsWith('Container') ? 1 : 0;
    return firstIsContainer - secondIsContainer || first.name.localeCompare(second.name);
  });
  const now = snapshot.generated_at;

  return (
    <div className="page">
      <section className="stat-row" aria-label="Checks by status">
        {SUMMARY_STATUSES.map((status) => (
          <div key={status} className={`stat-tile stat-tile-${status}`}>
            <span className="stat-label">
              <StatusIcon status={status} /> {CheckIndex.label(status)}
            </span>
            <span className="stat-value">{counts[status]}</span>
          </div>
        ))}
      </section>

      <section className="card">
        <h2>Shared infrastructure</h2>
        <ul className="chip-list">
          {platformChecks.map((check) => (
            <li key={check.check_id} className="chip" title={check.message}>
              <StatusIcon status={check.status} />
              <span>{check.name}</span>
              {check.value !== null && check.name.indexOf('Container') !== 0 && <span className="muted">{Formatter.number(check.value)} ms</span>}
            </li>
          ))}
        </ul>
      </section>

      <section className="card">
        <h2>Brokers at a glance</h2>
        <p className="card-hint">Each cell shows the worst check in that area. Select a cell to see its checks.</p>
        <div className="table-scroll">
          <table className="grid-table">
            <thead>
              <tr>
                <th scope="col">Broker</th>
                {OVERVIEW_COLUMNS.map((column) => (
                  <th key={column.key} scope="col">
                    {column.label}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {index.subjects().map((subject) => (
                <tr key={subject}>
                  <th scope="row">{subject}</th>
                  {OVERVIEW_COLUMNS.map((column) => {
                    const checks = index.forSubject(subject, column.areas);
                    const isSelected = selected?.subject === subject && selected.column.key === column.key;
                    return (
                      <td key={column.key}>
                        <GridCell
                          checks={checks}
                          selected={isSelected}
                          onSelect={() => setSelected(isSelected ? null : { subject, column })}
                        />
                      </td>
                    );
                  })}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        {selected && (
          <CellDetails
            title={`${selected.subject} · ${selected.column.label}`}
            checks={index.forSubject(selected.subject, selected.column.areas)}
            now={now}
          />
        )}
      </section>

      <section className="card">
        <h2>Needs attention</h2>
        {problems.length === 0 ? (
          <p className="empty">Nothing is failing or warning.</p>
        ) : (
          <ul className="problem-list">
            {problems.slice(0, 40).map((check) => (
              <li key={check.check_id} className={`problem problem-${check.status}`}>
                <StatusBadge status={check.status} />
                <span className="problem-title">
                  {check.subject} · {check.name}
                </span>
                <span className="problem-message">{check.message}</span>
                <span className="muted problem-since">for {Formatter.duration(now - check.status_since)}</span>
              </li>
            ))}
          </ul>
        )}
        {problems.length > 40 && <p className="card-hint">{problems.length - 40} more are listed on the other pages.</p>}
      </section>

      <div className="two-columns">
        <section className="card">
          <h2>Recent notifications</h2>
          {snapshot.notifications.length === 0 ? (
            <p className="empty">No desktop notifications since the monitor started.</p>
          ) : (
            <ul className="event-list">
              {snapshot.notifications.map((notification) => (
                <li key={`${notification.created_at}-${notification.title}`}>
                  <StatusIcon status={notification.urgency === 'critical' ? 'failure' : 'ok'} />
                  <span>
                    <strong>{notification.title}</strong>
                    <span className="event-body">{notification.body}</span>
                  </span>
                  <span className="muted">{Formatter.indiaTime(notification.created_at, now)}</span>
                </li>
              ))}
            </ul>
          )}
        </section>
        <section className="card">
          <h2>Recent actions</h2>
          <RecentActions snapshot={snapshot} />
        </section>
      </div>
    </div>
  );
}

/** Props for GridCell. */
interface GridCellProps {
  checks: Check[];
  selected: boolean;
  onSelect: () => void;
}

/**
 * One cell of the broker grid.
 * @param props The cell's checks, whether it is selected, and the selection handler.
 * @returns The cell button, or a dash when the area has no checks.
 */
function GridCell(props: GridCellProps) {
  const { checks, selected, onSelect } = props;
  const worst = CheckIndex.worstStatus(checks);
  if (worst === null) {
    return <span className="muted">—</span>;
  }
  let bad = 0;
  for (const check of checks) {
    if (check.status === worst) {
      bad += 1;
    }
  }
  let text = CheckIndex.label(worst);
  if (worst === 'failure') {
    text = `${bad} failing`;
  } else if (worst === 'warning') {
    text = bad === 1 ? '1 warning' : `${bad} warnings`;
  } else if (worst === 'unknown') {
    text = `${bad} unknown`;
  }
  return (
    <button type="button" className={`grid-cell grid-cell-${worst}`} aria-pressed={selected} onClick={onSelect}>
      <StatusIcon status={worst} />
      <span>{text}</span>
    </button>
  );
}

/** Props for CellDetails. */
interface CellDetailsProps {
  title: string;
  checks: Check[];
  now: number;
}

/**
 * The checks behind a selected grid cell, worst first.
 * @param props The panel title, the checks and the snapshot time.
 * @returns The panel.
 */
function CellDetails(props: CellDetailsProps) {
  const { title, checks, now } = props;
  const ordered = [...checks].sort((first, second) => CheckIndex.severity(second.status) - CheckIndex.severity(first.status));
  return (
    <div className="cell-details">
      <h3>{title}</h3>
      <ul className="problem-list">
        {ordered.map((check) => (
          <li key={check.check_id} className={`problem problem-${check.status}`}>
            <StatusBadge status={check.status} />
            <span className="problem-title">{check.name}</span>
            <span className="problem-message">{check.message}</span>
            <span className="muted problem-since">for {Formatter.duration(now - check.status_since)}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}

/** Props for RecentActions. */
interface RecentActionsProps {
  snapshot: Snapshot;
}

/**
 * The starts and restarts requested from the dashboard, newest first.
 * @param props The latest snapshot.
 * @returns The list, or an empty-state sentence.
 */
export function RecentActions(props: RecentActionsProps) {
  const { snapshot } = props;
  if (snapshot.actions.length === 0) {
    return <p className="empty">No services have been started or restarted from the dashboard since the monitor started.</p>;
  }
  return (
    <ul className="event-list">
      {snapshot.actions.map((action) => (
        <li key={`${action.requested_at}-${action.unit}`}>
          <StatusIcon status={action.succeeded ? 'ok' : 'failure'} />
          <span>
            <strong>
              {action.action} {action.unit}
            </strong>
            <span className="event-body">
              {action.message} From {action.address}.
            </span>
          </span>
          <span className="muted">{Formatter.indiaTime(action.requested_at, snapshot.generated_at)}</span>
        </li>
      ))}
    </ul>
  );
}
