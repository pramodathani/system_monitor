import { useEffect, useMemo, useState } from 'react';

import { ApiError, apiClient } from '../api/apiClient';
import type { ApiCallResult, ApiEndpoint } from '../api/liveTypes';
import { Formatter } from '../utilities/formatter';
import { JsonView } from './JsonView';

/** Props for UbiApiConsole. */
interface UbiApiConsoleProps {
  endpoints: ApiEndpoint[];
}

/**
 * Calls one of UBI's GET endpoints and shows what it answered.
 *
 * Only the endpoints the server's own catalogue lists can be chosen, and only GET endpoints are in
 * it, so nothing here can place, change or cancel an order. The call is made by the monitor rather
 * than by the browser, reusing the application token a login already left in Redis.
 * @param props The endpoints that may be called.
 * @returns The console.
 */
export function UbiApiConsole(props: UbiApiConsoleProps) {
  const { endpoints } = props;
  const [chosen, setChosen] = useState(endpoints[0]?.name ?? '');
  const [values, setValues] = useState<Record<string, string>>({});
  const [result, setResult] = useState<ApiCallResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const endpoint = useMemo(
    () => endpoints.find((candidate) => candidate.name === chosen) ?? null,
    [endpoints, chosen],
  );

  useEffect(() => {
    setValues({});
    setResult(null);
    setError(null);
  }, [chosen]);

  const groups = useMemo(() => groupEndpoints(endpoints), [endpoints]);

  const send = async (event: React.FormEvent) => {
    event.preventDefault();
    if (endpoint === null) {
      return;
    }
    setLoading(true);
    setError(null);
    try {
      setResult(await apiClient.callUbiApi(endpoint.name, values));
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : String(caught));
      setResult(null);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="page">
      <section className="card">
        <h2>Call an endpoint</h2>
        <p className="card-hint">
          These are every GET endpoint UBI's REST API serves. The monitor makes the call using the
          application token already stored in Redis, so no new session is created and the token
          held elsewhere is not disturbed. Nothing that places or changes an order is listed here.
        </p>
        <form className="api-form" onSubmit={send}>
          <div className="filter-row">
            <label>
              Endpoint{' '}
              <select value={chosen} onChange={(event) => setChosen(event.target.value)}>
                {groups.map((group) => (
                  <optgroup key={group.name} label={group.name}>
                    {group.endpoints.map((candidate) => (
                      <option key={candidate.name} value={candidate.name}>
                        {candidate.label}
                      </option>
                    ))}
                  </optgroup>
                ))}
              </select>
            </label>
            <code className="api-path">GET /api{endpoint?.path ?? ''}</code>
            <button type="submit" className="button button-primary" disabled={loading}>
              {loading ? 'Calling…' : 'Send'}
            </button>
          </div>

          {endpoint === null ? null : <p className="card-hint">{endpoint.note}</p>}

          {endpoint === null || endpoint.parameters.length === 0 ? null : (
            <div className="api-parameters">
              {endpoint.parameters.map((parameter) => (
                <label key={parameter.name} className="api-parameter">
                  <span className="api-parameter-name">
                    {parameter.name}
                    {parameter.required ? <span className="api-required"> required</span> : null}
                  </span>
                  <input
                    type="search"
                    value={values[parameter.name] ?? ''}
                    placeholder={parameter.example}
                    onChange={(event) =>
                      setValues({ ...values, [parameter.name]: event.target.value })
                    }
                  />
                  <span className="api-parameter-note">{parameter.note}</span>
                </label>
              ))}
            </div>
          )}
        </form>
      </section>

      {error === null ? null : (
        <section className="card">
          <p className="live-error">{error}</p>
        </section>
      )}

      {result === null ? null : <ApiResult result={result} />}
    </div>
  );
}

/** Props for ApiResult. */
interface ApiResultProps {
  result: ApiCallResult;
}

/**
 * What one call returned: its status line, then its body.
 * @param props The call's outcome.
 * @returns The answer.
 */
function ApiResult(props: ApiResultProps) {
  const { result } = props;
  const failed = result.error !== null || result.status_code === null || result.status_code >= 400;
  return (
    <section className="card">
      <h2>Answer</h2>
      <p className="card-hint">
        <code>{result.url}</code>
      </p>
      <div className="stat-row">
        <div className={failed ? 'stat-tile stat-tile-failure' : 'stat-tile'}>
          <span className="stat-label">Status</span>
          <span className="stat-value">{result.status_code ?? 'no answer'}</span>
        </div>
        <div className="stat-tile">
          <span className="stat-label">Took</span>
          <span className="stat-value">{result.elapsed_milliseconds.toFixed(0)} ms</span>
        </div>
        <div className="stat-tile">
          <span className="stat-label">Size</span>
          <span className="stat-value">{Formatter.number(result.byte_size)} bytes</span>
        </div>
        <div className="stat-tile">
          <span className="stat-label">Token</span>
          <span className="stat-value">{result.token_used ? 'sent' : 'none sent'}</span>
        </div>
      </div>
      {result.error === null ? null : <p className="live-error">{result.error}</p>}
      {result.truncated ? (
        <p className="live-warning">
          The answer was longer than the monitor will hold and was cut short, so what follows is
          incomplete. Narrow the request to see all of it.
        </p>
      ) : null}
      {result.document !== null && result.document !== undefined ? (
        <div className="json-root">
          <JsonView value={result.document} />
        </div>
      ) : null}
      {result.text === null ? null : <pre className="live-raw">{result.text}</pre>}
    </section>
  );
}

/** One heading in the endpoint dropdown. */
interface EndpointGroup {
  name: string;
  endpoints: ApiEndpoint[];
}

/**
 * Gathers the endpoints under their headings, keeping the server's order.
 * @param endpoints Every endpoint the catalogue offered.
 * @returns One group per heading.
 */
function groupEndpoints(endpoints: ApiEndpoint[]): EndpointGroup[] {
  const groups: EndpointGroup[] = [];
  for (const endpoint of endpoints) {
    let group = groups.find((candidate) => candidate.name === endpoint.group);
    if (group === undefined) {
      group = { name: endpoint.group, endpoints: [] };
      groups.push(group);
    }
    group.endpoints.push(endpoint);
  }
  return groups;
}
