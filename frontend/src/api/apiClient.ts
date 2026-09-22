import type {
  ApiCallResult,
  DatabaseHealth,
  LiveCatalogue,
  LiveDocument,
  LiveHashDocuments,
  LiveTablePage,
  LiveViewAnswer,
} from './liveTypes';
import type { Snapshot, UnitAction } from './types';

const REQUESTED_WITH_HEADER = 'X-Requested-With';
const REQUESTED_WITH_VALUE = 'system-monitor';

/** An error answer from the server, carrying its status code and message. */
export class ApiError extends Error {
  readonly statusCode: number;

  /**
   * Creates the error.
   * @param statusCode The HTTP status code.
   * @param message The server's explanation.
   */
  constructor(statusCode: number, message: string) {
    super(message);
    this.statusCode = statusCode;
  }
}

/** Calls the monitor's own server. */
export class ApiClient {
  /**
   * Asks whether this browser is logged in.
   * @returns True when the session is logged in.
   */
  async isLoggedIn(): Promise<boolean> {
    const response = await fetch('/api/auth/session', {
      credentials: 'same-origin',
    });
    const body = await this.readJson(response);
    return body.authenticated === true;
  }

  /**
   * Logs in with the dashboard password.
   * @param password The password typed in.
   * @throws ApiError when the password is wrong or the address is locked out.
   */
  async logIn(password: string): Promise<void> {
    const response = await fetch('/api/auth/login', {
      method: 'POST',
      credentials: 'same-origin',
      headers: {
        'Content-Type': 'application/json',
        [REQUESTED_WITH_HEADER]: REQUESTED_WITH_VALUE,
      },
      body: JSON.stringify({
        password,
      }),
    });
    await this.readJson(response);
  }

  /** Logs out. */
  async logOut(): Promise<void> {
    const response = await fetch('/api/auth/logout', {
      method: 'POST',
      credentials: 'same-origin',
      headers: {
        [REQUESTED_WITH_HEADER]: REQUESTED_WITH_VALUE,
      },
    });
    await this.readJson(response);
  }

  /**
   * Fetches the current snapshot once.
   * @returns The snapshot.
   */
  async fetchSnapshot(): Promise<Snapshot> {
    const response = await fetch('/api/snapshot', {
      credentials: 'same-origin',
    });
    return (await this.readJson(response)) as unknown as Snapshot;
  }

  /**
   * Starts or restarts one of UBI's services.
   * @param unitName The exact unit name.
   * @param action "start" or "restart".
   * @returns The recorded action.
   * @throws ApiError when the server refuses or systemctl fails.
   */
  async performUnitAction(unitName: string, action: 'start' | 'restart'): Promise<UnitAction> {
    const response = await fetch(`/api/units/${encodeURIComponent(unitName)}/${action}`, {
      method: 'POST',
      credentials: 'same-origin',
      headers: {
        [REQUESTED_WITH_HEADER]: REQUESTED_WITH_VALUE,
      },
    });
    return (await this.readJson(response)) as unknown as UnitAction;
  }

  /**
   * The address of the event stream for one unit's journal.
   * @param unitName The exact unit name.
   * @param lineCount How many earlier lines to send first.
   * @returns The URL.
   */
  logStreamUrl(unitName: string, lineCount: number): string {
    return `/api/logs/${encodeURIComponent(unitName)}/events?lines=${lineCount}`;
  }

  /**
   * Fetches the live view's list of brokers, tabs and UBI endpoints.
   * @returns The catalogue.
   * @throws ApiError when the server refuses.
   */
  async fetchLiveCatalogue(): Promise<LiveCatalogue> {
    const response = await fetch('/api/live/catalogue', {
      credentials: 'same-origin',
    });
    return (await this.readJson(response)) as unknown as LiveCatalogue;
  }

  /**
   * Reads Redis, MongoDB and TimescaleDB and the containers they run in.
   * @returns The health of all three.
   * @throws ApiError when the server refuses.
   */
  async fetchDatabaseHealth(): Promise<DatabaseHealth> {
    const response = await fetch('/api/live/databases', {
      credentials: 'same-origin',
    });
    return (await this.readJson(response)) as unknown as DatabaseHealth;
  }

  /**
   * Reads one live view tab that shows a document.
   * @param scope Either "broker" or "unified".
   * @param name The tab's name.
   * @param broker The broker chosen, for a tab that needs one.
   * @returns The tab and its value.
   * @throws ApiError when the tab is unknown or a store could not be read.
   */
  async fetchLiveView(
    scope: string,
    name: string,
    broker: string | null,
  ): Promise<LiveViewAnswer<LiveDocument | LiveHashDocuments>> {
    const query = new URLSearchParams();
    if (broker !== null) {
      query.set('broker', broker);
    }
    const response = await fetch(`/api/live/view/${scope}/${name}?${query.toString()}`, {
      credentials: 'same-origin',
    });
    return (await this.readJson(response)) as unknown as LiveViewAnswer<LiveDocument | LiveHashDocuments>;
  }

  /**
   * Reads one page of a live view table, or searches the whole table.
   * @param scope Either "broker" or "unified".
   * @param name The tab's name.
   * @param broker The broker chosen, for a table that needs one.
   * @param cursor The cursor to continue from, where "0" starts at the beginning.
   * @param limit How many rows to ask for.
   * @param search Text to look for in every row, or null to page through instead.
   * @returns The tab and its page of rows.
   * @throws ApiError when the tab is unknown or Redis could not be read.
   */
  async fetchLiveTable(
    scope: string,
    name: string,
    broker: string | null,
    cursor: string,
    limit: number,
    search: string | null,
  ): Promise<LiveViewAnswer<LiveTablePage>> {
    const query = new URLSearchParams();
    query.set('cursor', cursor);
    query.set('limit', String(limit));
    if (broker !== null) {
      query.set('broker', broker);
    }
    if (search !== null && search !== '') {
      query.set('search', search);
    }
    const response = await fetch(`/api/live/table/${scope}/${name}?${query.toString()}`, {
      credentials: 'same-origin',
    });
    return (await this.readJson(response)) as unknown as LiveViewAnswer<LiveTablePage>;
  }

  /**
   * Calls one of UBI's GET endpoints through the monitor and returns what it answered.
   * @param name The endpoint's name, as the catalogue gives it.
   * @param parameters The query parameters to send, where empty values are left out.
   * @returns The call's outcome, including a failing status rather than throwing on one.
   * @throws ApiError when the endpoint is unknown to the monitor.
   */
  async callUbiApi(name: string, parameters: Record<string, string>): Promise<ApiCallResult> {
    const query = new URLSearchParams();
    for (const [key, value] of Object.entries(parameters)) {
      if (value.trim() !== '') {
        query.set(key, value.trim());
      }
    }
    const response = await fetch(`/api/live/api/${encodeURIComponent(name)}?${query.toString()}`, {
      credentials: 'same-origin',
    });
    return (await this.readJson(response)) as unknown as ApiCallResult;
  }

  /**
   * Reads a JSON answer, turning an error status into an ApiError.
   * @param response The fetch response.
   * @returns The parsed body.
   * @throws ApiError when the status is not successful.
   */
  private async readJson(response: Response): Promise<Record<string, unknown>> {
    let body: Record<string, unknown> = {};
    try {
      body = await response.json();
    } catch {
      body = {};
    }
    if (!response.ok) {
      const detail = typeof body.detail === 'string' ? body.detail : response.statusText;
      throw new ApiError(response.status, detail);
    }
    return body;
  }
}

export const apiClient = new ApiClient();
