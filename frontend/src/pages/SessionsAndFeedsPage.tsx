import type { Snapshot } from '../api/types';
import { Sparkline } from '../components/Sparkline';
import { StatusBadge, StatusIcon } from '../components/StatusBadge';
import { CheckIndex } from '../utilities/checkIndex';
import { Formatter } from '../utilities/formatter';

/** Props for SessionsAndFeedsPage. */
interface SessionsAndFeedsPageProps {
  snapshot: Snapshot;
}

/**
 * Broker logins, quote feeds and the unified quotes pipeline.
 * @param props The latest snapshot.
 * @returns The page.
 */
export function SessionsAndFeedsPage(props: SessionsAndFeedsPageProps) {
  const { snapshot } = props;
  const index = new CheckIndex(snapshot.checks);
  const now = snapshot.generated_at;
  const sessions = index.inAreas(['sessions']);
  const feeds = index.inAreas(['feeds']);
  const pipeline = index.find('quotes_pipeline:stats');
  const staleQuotes = index.find('quotes_pipeline:stale_quotes');
  const rates = (pipeline?.details.rates ?? {}) as Record<string, number>;
  const counters = (pipeline?.details.counters ?? {}) as Record<string, number>;

  return (
    <div className="page">
      <section className="card">
        <h2>Markets open now</h2>
        {snapshot.open_sessions.length === 0 ? (
          <p className="empty">No exchange session is open.</p>
        ) : (
          <ul className="chip-list">
            {snapshot.open_sessions.map((session) => (
              <li key={`${session.exchange}-${session.calendar}-${session.name}`} className="chip">
                <span className="upper">{session.exchange}</span>
                <span>
                  {session.calendar} {session.name}
                </span>
                <span className="muted">until {Formatter.indiaTime(session.closes_at, now)}</span>
              </li>
            ))}
          </ul>
        )}
        <p className="card-hint">Calendar source: {snapshot.calendar_source}.</p>
      </section>

      <section className="card">
        <h2>Unified quotes pipeline</h2>
        {pipeline ? (
          <>
            <div className="stat-row">
              <div className="stat-tile">
                <span className="stat-label">
                  <StatusIcon status={pipeline.status} /> Quotes written per second
                </span>
                <span className="stat-value">{rates.written === undefined ? '—' : Formatter.number(rates.written)}</span>
                <Sparkline points={pipeline.history} unit="quotes/s" label="Quotes written per second" width={180} />
              </div>
              <div className="stat-tile">
                <span className="stat-label">Ticks received per second</span>
                <span className="stat-value">{rates.received === undefined ? '—' : Formatter.number(rates.received)}</span>
              </div>
              {staleQuotes && (
                <div className="stat-tile">
                  <span className="stat-label">
                    <StatusIcon status={staleQuotes.status} /> Stale while market open
                  </span>
                  <span className="stat-value">{Formatter.asNumber(staleQuotes.details.stale_while_open) ?? 0}</span>
                  <span className="muted">of {Formatter.asNumber(staleQuotes.details.live_quotes) ?? 0} live quotes</span>
                </div>
              )}
            </div>
            <p>{pipeline.message}</p>
            <div className="table-scroll">
              <table className="data-table compact">
                <thead>
                  <tr>
                    <th scope="col">Counter</th>
                    <th scope="col" className="numeric">
                      Total since start
                    </th>
                    <th scope="col" className="numeric">
                      Per second
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {Object.keys(counters)
                    .sort()
                    .map((counterName) => (
                      <tr key={counterName}>
                        <td>{counterName.replaceAll('_', ' ')}</td>
                        <td className="numeric">{Formatter.number(counters[counterName])}</td>
                        <td className="numeric">{rates[counterName] === undefined ? '—' : Formatter.number(rates[counterName])}</td>
                      </tr>
                    ))}
                </tbody>
              </table>
            </div>
          </>
        ) : (
          <p className="empty">UBI runs no unified quotes service.</p>
        )}
      </section>

      <section className="card">
        <h2>Quote feeds</h2>
        <p className="card-hint">A feed is judged only while one of its own exchanges is trading; otherwise it is idle.</p>
        <div className="table-scroll">
          <table className="data-table">
            <thead>
              <tr>
                <th scope="col">Status</th>
                <th scope="col">Feed</th>
                <th scope="col" className="numeric">
                  Ticks/s
                </th>
                <th scope="col">Last 15 minutes</th>
                <th scope="col">Exchanges</th>
                <th scope="col">What it means</th>
              </tr>
            </thead>
            <tbody>
              {feeds.map((check) => {
                const exchanges = Array.isArray(check.details.exchanges) ? (check.details.exchanges as string[]).join(', ') : '';
                return (
                  <tr key={check.check_id} className={`row-${check.status}`}>
                    <td>
                      <StatusBadge status={check.status} />
                    </td>
                    <td className="nowrap">{check.subject}</td>
                    <td className="numeric">{check.value === null ? '—' : Formatter.number(check.value)}</td>
                    <td>
                      <Sparkline points={check.history} unit="ticks/s" label={`${check.subject} ticks per second`} />
                    </td>
                    <td className="nowrap">{exchanges || 'all'}</td>
                    <td>{check.message}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </section>

      <section className="card">
        <h2>Login sessions</h2>
        <div className="table-scroll">
          <table className="data-table">
            <thead>
              <tr>
                <th scope="col">Status</th>
                <th scope="col">Broker</th>
                <th scope="col">What it means</th>
                <th scope="col">Since</th>
              </tr>
            </thead>
            <tbody>
              {sessions.map((check) => (
                <tr key={check.check_id} className={`row-${check.status}`}>
                  <td>
                    <StatusBadge status={check.status} />
                  </td>
                  <td className="nowrap">{check.subject === 'unified' ? `unified · ${check.name}` : check.subject}</td>
                  <td>{check.message}</td>
                  <td className="nowrap muted">{Formatter.duration(now - check.status_since)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  );
}
