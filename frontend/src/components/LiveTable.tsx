import { useCallback, useEffect, useRef, useState } from 'react';

import { ApiError, apiClient } from '../api/apiClient';
import type { LiveTablePage, LiveView } from '../api/liveTypes';
import { Formatter } from '../utilities/formatter';

const PAGE_ROWS = 100;
const SEARCH_ROWS = 200;

/** Props for LiveTable. */
interface LiveTableProps {
  scope: string;
  view: LiveView;
  broker: string | null;
}

/**
 * One of the three huge Redis hashes, shown a page at a time.
 *
 * These tables run to hundreds of thousands of rows, so nothing loads until the reader asks. Paging
 * follows the cursor Redis hands back, which is why there is a "next page" but no page numbers:
 * Redis can continue a walk but cannot jump to an arbitrary offset.
 * @param props The scope, the tab being shown and the broker chosen.
 * @returns The table with its controls.
 */
export function LiveTable(props: LiveTableProps) {
  const { scope, view, broker } = props;
  const [page, setPage] = useState<LiveTablePage | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [searchText, setSearchText] = useState('');
  const [pageNumber, setPageNumber] = useState(0);
  const cursors = useRef<string[]>(['0']);

  const load = useCallback(
    async (cursor: string, search: string | null, number: number) => {
      setLoading(true);
      setError(null);
      try {
        const answer = await apiClient.fetchLiveTable(
          scope,
          view.name,
          broker,
          cursor,
          search === null ? PAGE_ROWS : SEARCH_ROWS,
          search,
        );
        setPage(answer.value);
        setPageNumber(number);
      } catch (caught) {
        setError(caught instanceof ApiError ? caught.message : String(caught));
        setPage(null);
      } finally {
        setLoading(false);
      }
    },
    [scope, view.name, broker],
  );

  useEffect(() => {
    setPage(null);
    setError(null);
    setSearchText('');
    setPageNumber(0);
    cursors.current = ['0'];
  }, [scope, view.name, broker]);

  const start = () => {
    cursors.current = ['0'];
    void load('0', null, 1);
  };

  const next = () => {
    if (page?.cursor === null || page?.cursor === undefined) {
      return;
    }
    cursors.current.push(page.cursor);
    void load(page.cursor, null, pageNumber + 1);
  };

  const previous = () => {
    if (cursors.current.length < 2) {
      return;
    }
    cursors.current.pop();
    const cursor = cursors.current[cursors.current.length - 1];
    void load(cursor, null, pageNumber - 1);
  };

  const search = (event: React.FormEvent) => {
    event.preventDefault();
    cursors.current = ['0'];
    void load('0', searchText.trim() === '' ? null : searchText, 1);
  };

  return (
    <div className="live-table">
      <form className="filter-row live-table-controls" onSubmit={search}>
        <button type="button" className="button button-primary" onClick={start} disabled={loading}>
          {page === null ? 'Load first page' : 'Back to start'}
        </button>
        <input
          type="search"
          value={searchText}
          placeholder="Search every row"
          aria-label="Search every row of the table"
          onChange={(event) => setSearchText(event.target.value)}
        />
        <button type="submit" className="button" disabled={loading || searchText.trim() === ''}>
          Search
        </button>
        {page !== null && page.search === null ? (
          <>
            <button type="button" className="button" onClick={previous} disabled={loading || pageNumber <= 1}>
              Previous
            </button>
            <button type="button" className="button" onClick={next} disabled={loading || page.cursor === null}>
              Next
            </button>
            <span className="muted">page {pageNumber}</span>
          </>
        ) : null}
        {loading ? <span className="muted">Reading…</span> : null}
      </form>

      {error === null ? null : <p className="live-error">{error}</p>}

      {page === null ? (
        <p className="empty">
          This table holds too many rows to load on its own. Press “Load first page”, or search it.
        </p>
      ) : (
        <TableBody page={page} />
      )}
    </div>
  );
}

/** Props for TableBody. */
interface TableBodyProps {
  page: LiveTablePage;
}

/**
 * The rows themselves, under a line saying what was read.
 * @param props The page returned by the server.
 * @returns The table.
 */
function TableBody(props: TableBodyProps) {
  const { page } = props;
  if (!page.exists) {
    return <p className="empty">Redis holds no key {page.key}.</p>;
  }
  return (
    <>
      <p className="card-hint">
        <code>{page.key}</code> holds {Formatter.number(page.total_fields)} fields
        {page.field_prefix === null ? '' : `, of which this shows those beginning ${page.field_prefix}`}.{' '}
        {page.search === null
          ? `Showing ${Formatter.number(page.rows.length)} rows.`
          : `Found ${Formatter.number(page.rows.length)} rows matching “${page.search}” after examining ${Formatter.number(page.scanned_fields)} fields.`}
        {page.complete || page.search === null ? '' : ' There are more matches than are shown here.'}
      </p>
      {page.rows.length === 0 ? (
        <p className="empty">Nothing matched.</p>
      ) : (
        <div className="table-scroll">
          <table className="data-table compact">
            <thead>
              <tr>
                <th>{page.key_column}</th>
                {page.columns.map((column) => (
                  <th key={column}>{column}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {page.rows.map((row) => (
                <tr key={row.key}>
                  <th scope="row" className="live-table-key">
                    {row.key}
                  </th>
                  {page.columns.map((column, index) => (
                    <td key={column} className={typeof row.values[index] === 'number' ? 'numeric' : undefined}>
                      {cellText(row.values[index])}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </>
  );
}

/**
 * The text one cell shows.
 * @param value The cell's stored value.
 * @returns A readable rendering, with a missing value shown as a dash.
 */
function cellText(value: unknown): string {
  if (value === null || value === undefined) {
    return '—';
  }
  if (typeof value === 'object') {
    return JSON.stringify(value);
  }
  return String(value);
}
