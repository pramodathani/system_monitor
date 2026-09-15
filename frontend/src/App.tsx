import { useCallback, useEffect, useState } from 'react';
import { BrowserRouter, NavLink, Navigate, Route, Routes } from 'react-router';

import { apiClient } from './api/apiClient';
import type { Snapshot } from './api/types';
import { StatusIcon } from './components/StatusBadge';
import { useMonitorSnapshot } from './hooks/useMonitorSnapshot';
import { useNow } from './hooks/useNow';
import { LoginPage } from './pages/LoginPage';
import { LogsPage } from './pages/LogsPage';
import { OverviewPage } from './pages/OverviewPage';
import { PipelinePage } from './pages/PipelinePage';
import { ServicesPage } from './pages/ServicesPage';
import { SessionsAndFeedsPage } from './pages/SessionsAndFeedsPage';
import { CheckIndex } from './utilities/checkIndex';
import { Formatter } from './utilities/formatter';

type SessionState = 'checking' | 'logged-out' | 'logged-in';

const STALE_AFTER_SECONDS = 20;

/**
 * The application root: checks the session, then shows the login page or the dashboard.
 * @returns The application.
 */
export function App() {
  const [sessionState, setSessionState] = useState<SessionState>('checking');

  useEffect(() => {
    apiClient
      .isLoggedIn()
      .then((loggedIn) => setSessionState(loggedIn ? 'logged-in' : 'logged-out'))
      .catch(() => setSessionState('logged-out'));
  }, []);

  const handleLoggedOut = useCallback(() => setSessionState('logged-out'), []);

  if (sessionState === 'checking') {
    return <p className="empty centered">Loading…</p>;
  }
  if (sessionState === 'logged-out') {
    return <LoginPage onLoggedIn={() => setSessionState('logged-in')} />;
  }
  return (
    <BrowserRouter>
      <Dashboard onLoggedOut={handleLoggedOut} />
    </BrowserRouter>
  );
}

/** Props for Dashboard. */
interface DashboardProps {
  onLoggedOut: () => void;
}

/**
 * The logged-in layout: header, navigation and the current page.
 * @param props Called when the session ends.
 * @returns The dashboard.
 */
function Dashboard(props: DashboardProps) {
  const { onLoggedOut } = props;
  const { snapshot, connected } = useMonitorSnapshot(onLoggedOut);

  const logOut = async () => {
    try {
      await apiClient.logOut();
    } finally {
      onLoggedOut();
    }
  };

  return (
    <div className="shell">
      <header className="header">
        <div className="header-top">
          <h1>System monitor</h1>
          <ConnectionState snapshot={snapshot} connected={connected} />
          <button type="button" className="button button-quiet log-out" onClick={logOut}>
            Log out
          </button>
        </div>
        <nav className="navigation" aria-label="Pages">
          <NavLink to="/" end>
            Overview
          </NavLink>
          <NavLink to="/services">Services</NavLink>
          <NavLink to="/feeds">Sessions & feeds</NavLink>
          <NavLink to="/pipeline">Pipeline</NavLink>
          <NavLink to="/logs">Logs</NavLink>
        </nav>
      </header>
      <main className={connected ? 'content' : 'content content-stale'}>
        {snapshot === null ? (
          <p className="empty centered">Waiting for the first readings from the server…</p>
        ) : (
          <Routes>
            <Route path="/" element={<OverviewPage snapshot={snapshot} />} />
            <Route path="/services" element={<ServicesPage snapshot={snapshot} />} />
            <Route path="/feeds" element={<SessionsAndFeedsPage snapshot={snapshot} />} />
            <Route path="/pipeline" element={<PipelinePage snapshot={snapshot} />} />
            <Route path="/logs" element={<LogsPage snapshot={snapshot} />} />
            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
        )}
      </main>
    </div>
  );
}

/** Props for ConnectionState. */
interface ConnectionStateProps {
  snapshot: Snapshot | null;
  connected: boolean;
}

/**
 * The header's summary: how fresh the data is and how many checks are failing.
 * @param props The latest snapshot and whether the stream is connected.
 * @returns The summary.
 */
function ConnectionState(props: ConnectionStateProps) {
  const { snapshot, connected } = props;
  const now = useNow(1000);
  if (snapshot === null) {
    return <span className="connection muted">{connected ? 'Connected' : 'Connecting…'}</span>;
  }
  const age = now - snapshot.generated_at;
  const counts = new CheckIndex(snapshot.checks).countByStatus();
  const live = connected && age < STALE_AFTER_SECONDS;
  return (
    <span className="connection">
      <span className={live ? 'connection-dot connection-live' : 'connection-dot'} aria-hidden="true" />
      <span>{live ? 'Live' : 'Not updating'}</span>
      <span className="muted">updated {Formatter.duration(age)} ago</span>
      <span className="connection-counts">
        <StatusIcon status="failure" /> {counts.failure} failing
        <StatusIcon status="warning" /> {counts.warning} warnings
      </span>
    </span>
  );
}
