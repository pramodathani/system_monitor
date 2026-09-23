import { useState } from 'react';

import type { Check, Snapshot } from '../api/types';
import { StatusBadge } from '../components/StatusBadge';
import { UnitActionButton } from '../components/UnitActionButton';
import { CheckIndex } from '../utilities/checkIndex';
import { Formatter } from '../utilities/formatter';
import { ServiceOrder } from '../utilities/serviceOrder';
import { RecentActions } from './OverviewPage';

/** Props for ServicesPage. */
interface ServicesPageProps {
  snapshot: Snapshot;
}

/**
 * Every UBI service and daily job, with start and restart controls.
 * @param props The latest snapshot.
 * @returns The page.
 */
export function ServicesPage(props: ServicesPageProps) {
  const { snapshot } = props;
  const index = new CheckIndex(snapshot.checks);
  const [subjectFilter, setSubjectFilter] = useState('all');
  const [onlyProblems, setOnlyProblems] = useState(false);
  const subjects = index.subjects();
  const shownSubjects = subjectFilter === 'all' ? subjects : [subjectFilter];
  const now = snapshot.generated_at;

  const keep = (check: Check) => !onlyProblems || check.status === 'failure' || check.status === 'warning' || check.status === 'unknown';

  const timers: Check[] = [];
  for (const subject of shownSubjects) {
    for (const check of index.forSubject(subject, ['timers'])) {
      if (keep(check)) {
        timers.push(check);
      }
    }
  }

  return (
    <div className="page">
      <div className="filter-row">
        <label>
          Broker{' '}
          <select value={subjectFilter} onChange={(event) => setSubjectFilter(event.target.value)}>
            <option value="all">All</option>
            {subjects.map((subject) => (
              <option key={subject} value={subject}>
                {subject}
              </option>
            ))}
          </select>
        </label>
        <label className="checkbox">
          <input type="checkbox" checked={onlyProblems} onChange={(event) => setOnlyProblems(event.target.checked)} /> Only show problems
        </label>
      </div>

      <section className="card">
        <h2>Daily jobs</h2>
        <p className="card-hint">Starting a job runs it now, outside its schedule.</p>
        {timers.length === 0 ? (
          <p className="empty">No jobs match the filter.</p>
        ) : (
          <div className="table-scroll">
            <table className="data-table">
              <thead>
                <tr>
                  <th scope="col">Status</th>
                  <th scope="col">Job</th>
                  <th scope="col">What happened</th>
                  <th scope="col">Last run</th>
                  <th scope="col">Next run</th>
                  <th scope="col">
                    <span className="visually-hidden">Action</span>
                  </th>
                </tr>
              </thead>
              <tbody>
                {timers.map((check) => {
                  const serviceName = Formatter.asText(check.details.service);
                  const lastExit = Formatter.asNumber(check.details.last_exit);
                  const nextRun = Formatter.asNumber(check.details.next_run);
                  const running = Formatter.asText(check.details.service_state).startsWith('activating');
                  const isLogin = serviceName.endsWith('-login.service');
                  return (
                    <tr key={check.check_id} className={`row-${check.status}`}>
                      <td>
                        <StatusBadge status={check.status} />
                      </td>
                      <td className="nowrap">{check.name}</td>
                      <td>{check.message}</td>
                      <td className="nowrap numeric">{lastExit === null ? '—' : Formatter.indiaTime(lastExit, now)}</td>
                      <td className="nowrap numeric">{nextRun === null ? '—' : Formatter.indiaTime(nextRun, now)}</td>
                      <td className="nowrap">
                        {serviceName && (
                          <UnitActionButton
                            unitName={serviceName}
                            action="start"
                            buttonLabel="Run now"
                            disabled={running}
                            warning={isLogin ? 'This performs a real login with the broker, driving a browser session. Brokers may rate-limit repeated logins.' : undefined}
                          />
                        )}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </section>

      {shownSubjects.map((subject) => {
        const services = new ServiceOrder(subject).sort(index.forSubject(subject, ['services']).filter(keep));
        if (services.length === 0) {
          return null;
        }
        const worst = CheckIndex.worstStatus(services);
        const hasProblem = worst === 'failure' || worst === 'warning' || worst === 'unknown';
        let healthy = 0;
        for (const check of services) {
          if (check.status === 'ok') {
            healthy += 1;
          }
        }
        return (
          <details key={`${subject}-${hasProblem}-${subjectFilter}`} className="card collapsible" open={hasProblem || subjectFilter !== 'all'}>
            <summary>
              <h2>{subject} services</h2>
              {worst && <StatusBadge status={worst} label={`${healthy} of ${services.length} running normally`} />}
            </summary>
            <div className="table-scroll">
              <table className="data-table">
                <thead>
                  <tr>
                    <th scope="col">Status</th>
                    <th scope="col">Service</th>
                    <th scope="col">State</th>
                    <th scope="col" className="numeric">
                      Restarts
                    </th>
                    <th scope="col">
                      <span className="visually-hidden">Action</span>
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {services.map((check) => {
                    const unitName = Formatter.asText(check.details.unit) || check.check_id.replace('services:', '');
                    const activeState = Formatter.asText(check.details.active_state);
                    const stopped = activeState === 'inactive' || activeState === 'failed';
                    const recent = Formatter.asNumber(check.details.recent_restarts) ?? 0;
                    const total = Formatter.asNumber(check.details.restarts) ?? 0;
                    return (
                      <tr key={check.check_id} className={`row-${check.status}`}>
                        <td>
                          <StatusBadge status={check.status} />
                        </td>
                        <td className="nowrap">{check.name}</td>
                        <td>{check.message}</td>
                        <td className="numeric nowrap">
                          {recent > 0 ? `${recent} recent, ` : ''}
                          {total} total
                        </td>
                        <td className="nowrap">
                          {unitName.endsWith('.service') && (
                            <UnitActionButton
                              unitName={unitName}
                              action={stopped ? 'start' : 'restart'}
                              buttonLabel={stopped ? 'Start' : 'Restart'}
                              warning={
                                unitName.includes('-orders@') || unitName.includes('@store_')
                                  ? 'This service handles orders or persistence. Updates that arrive while it restarts are picked up from its Redis stream afterwards.'
                                  : undefined
                              }
                            />
                          )}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </details>
        );
      })}

      <section className="card">
        <h2>Recent actions</h2>
        <RecentActions snapshot={snapshot} />
      </section>
    </div>
  );
}
