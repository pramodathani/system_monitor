import type { StoreHealth } from '../api/liveTypes';
import { StatusIcon } from './StatusBadge';
import { Formatter } from '../utilities/formatter';

/** Props for DatabaseCard. */
interface DatabaseCardProps {
  store: StoreHealth;
  now: number;
}

/**
 * One data store: whether it answers, when it last restarted and its own health readings.
 *
 * Two start times are shown where they differ. The store's own is when its server process began,
 * and the container's is when Docker last started the container around it. A store restarted
 * inside a container that kept running has a short uptime and an old container, which is worth
 * being able to see.
 * @param props The store's reading and the time it was read.
 * @returns The card.
 */
export function DatabaseCard(props: DatabaseCardProps) {
  const { store, now } = props;
  const container = store.container;
  const groups = groupParameters(store);

  return (
    <section className="card database-card">
      <h2>
        <StatusIcon status={store.online ? 'ok' : 'failure'} /> {store.label}
        {store.version === null ? null : <span className="muted database-version">{store.version}</span>}
      </h2>

      {store.error === null ? null : <p className="live-error">{store.error}</p>}

      <dl className="database-facts">
        <div>
          <dt>Status</dt>
          <dd>{store.online ? 'Online' : 'Not answering'}</dd>
        </div>
        <div>
          <dt>Server started</dt>
          <dd>{store.started_at === null ? '—' : Formatter.indiaTime(store.started_at, now)}</dd>
        </div>
        <div>
          <dt>Up for</dt>
          <dd>{store.uptime_seconds === null ? '—' : Formatter.duration(store.uptime_seconds)}</dd>
        </div>
        {store.response_milliseconds === null ? null : (
          <div>
            <dt>Answered in</dt>
            <dd>{store.response_milliseconds.toFixed(1)} ms</dd>
          </div>
        )}
        <div>
          <dt>Container started</dt>
          <dd>
            {container === null || container.started_at === null
              ? '—'
              : Formatter.indiaTime(container.started_at, now)}
          </dd>
        </div>
        <div>
          <dt>Container</dt>
          <dd>
            {container === null
              ? 'not found'
              : `${container.state}${container.health === null ? '' : `, ${container.health}`}, restarted ${container.restart_count ?? 0} times`}
          </dd>
        </div>
      </dl>

      {groups.length === 0 ? null : (
        <div className="database-parameters">
          {groups.map((group) => (
            <div key={group.name} className="database-group">
              <h3>{group.name}</h3>
              <table className="data-table compact">
                <tbody>
                  {group.readings.map((reading) => (
                    <tr key={reading.name}>
                      <th scope="row">{reading.name}</th>
                      <td className={typeof reading.value === 'number' ? 'numeric' : undefined}>
                        {readingText(reading.value, reading.kind, now)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ))}
        </div>
      )}
    </section>
  );
}

/** One heading of readings within a store's card. */
interface ParameterGroup {
  name: string;
  readings: Array<{ name: string; value: unknown; kind: string | null }>;
}

/**
 * Gathers a store's readings under their headings, keeping the server's order.
 * @param store The store's reading.
 * @returns One group per heading.
 */
function groupParameters(store: StoreHealth): ParameterGroup[] {
  const groups: ParameterGroup[] = [];
  for (const parameter of store.parameters) {
    let group = groups.find((candidate) => candidate.name === parameter.group);
    if (group === undefined) {
      group = { name: parameter.group, readings: [] };
      groups.push(group);
    }
    group.readings.push({ name: parameter.name, value: parameter.value, kind: parameter.kind });
  }
  return groups;
}

/**
 * The text one reading shows.
 *
 * A reading of kind "epoch" is a moment rather than a quantity, and is shown as a time. Redis
 * reports its last snapshot as epoch seconds, and 1,790,076,654 tells a reader nothing that
 * "11:53" does not tell them better.
 * @param value Whatever the store reported.
 * @param kind The reading's kind, which is "epoch" for a moment and null for a plain value.
 * @param now The time the reading was taken, used to decide how much of the date to show.
 * @returns A readable rendering, with large numbers grouped and a missing value shown as a dash.
 */
function readingText(value: unknown, kind: string | null, now: number): string {
  if (value === null || value === undefined) {
    return '—';
  }
  if (kind === 'epoch') {
    const moment = Number(value);
    return Number.isNaN(moment) ? String(value) : Formatter.indiaTime(moment, now);
  }
  if (typeof value === 'number') {
    return Formatter.number(value);
  }
  return String(value);
}
