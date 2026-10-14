import { useCallback, useEffect, useRef, useState } from 'react';
import { MotionConfig } from 'framer-motion';
import { AlertCircle, History, Loader2, Moon, Sun } from 'lucide-react';
import { SearchBar } from './components/SearchBar';
import { ProgressSteps } from './components/ProgressSteps';
import { ReportView } from './components/ReportView';
import { HistoryDrawer } from './components/HistoryDrawer';
import { StatusBadge } from './components/StatusBadge';
import {
  deleteReport,
  followResearch,
  getErrorMessage,
  getReport,
  listReports,
  startResearch,
} from './api/client';
import type { MarketResearchReport, RunSummary } from './types';
import { relativeTime } from './lib/format';
import { normalizeReport } from './lib/report';

type View =
  | { kind: 'home' }
  | { kind: 'loading' }
  | { kind: 'running'; id: string; topic: string; stage: string | null; message: string | null; startedAt: number }
  | { kind: 'report'; id: string; report: MarketResearchReport; createdAt: string; duration: number | null }
  | { kind: 'error'; topic?: string; message: string };

type Theme = 'light' | 'dark';

// Each run has its own address (#/r/<id>), so reloading or sharing the tab reopens it
const runIdFromHash = () => window.location.hash.match(/^#\/r\/([\w-]+)$/)?.[1] ?? null;
const navigate = (runId: string | null) => {
  window.location.hash = runId ? `#/r/${runId}` : '';
};

const readTheme = (): Theme | null => {
  try {
    const saved = localStorage.getItem('markey.theme');
    return saved === 'light' || saved === 'dark' ? saved : null;
  } catch {
    return null;
  }
};

function App() {
  const [view, setView] = useState<View>({ kind: 'home' });
  const [runs, setRuns] = useState<RunSummary[]>([]);
  const [historyOpen, setHistoryOpen] = useState(false);
  const [theme, setTheme] = useState<Theme | null>(readTheme);
  const following = useRef<AbortController | null>(null);

  const refreshHistory = useCallback(() => {
    listReports().then(setRuns).catch(() => undefined);
  }, []);

  const openRun = useCallback(
    async (id: string) => {
      following.current?.abort();
      const controller = new AbortController();
      following.current = controller;
      setView({ kind: 'loading' });
      try {
        let run = await getReport(id);
        if (run.status === 'running') {
          setView({
            kind: 'running', id, topic: run.topic, stage: null, message: null,
            startedAt: new Date(run.created_at).getTime(),
          });
          await followResearch(
            id,
            (stage, message) => setView(v => (v.kind === 'running' && v.id === id ? { ...v, stage, message } : v)),
            controller.signal,
          );
          run = await getReport(id);
          refreshHistory();
        }
        if (controller.signal.aborted) return;
        if (run.report) {
          setView({ kind: 'report', id, report: normalizeReport(run.report), createdAt: run.created_at, duration: run.duration_seconds });
        } else {
          setView({ kind: 'error', topic: run.topic, message: run.error ?? 'This report did not finish.' });
        }
      } catch (err) {
        if (controller.signal.aborted) return;
        setView({ kind: 'error', message: getErrorMessage(err) });
        refreshHistory();
      }
    },
    [refreshHistory],
  );

  // The address decides what is shown
  useEffect(() => {
    const sync = () => {
      const id = runIdFromHash();
      if (id) {
        openRun(id);
      } else {
        following.current?.abort();
        setView({ kind: 'home' });
      }
    };
    sync();
    refreshHistory();
    window.addEventListener('hashchange', sync);
    return () => window.removeEventListener('hashchange', sync);
  }, [openRun, refreshHistory]);

  useEffect(() => {
    const root = document.documentElement;
    if (theme) root.dataset.theme = theme;
    else delete root.dataset.theme;
  }, [theme]);

  const toggleTheme = () => {
    const systemDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
    const next: Theme = (theme ?? (systemDark ? 'dark' : 'light')) === 'dark' ? 'light' : 'dark';
    setTheme(next);
    try {
      localStorage.setItem('markey.theme', next);
    } catch {
      // The choice just won't be remembered
    }
  };

  const handleSearch = async (topic: string) => {
    setView({ kind: 'loading' });
    try {
      const id = await startResearch(topic);
      navigate(id);
      refreshHistory();
    } catch (err) {
      setView({ kind: 'error', topic, message: getErrorMessage(err) });
    }
  };

  const goHome = () => navigate(null);

  const openFromHistory = (id: string) => {
    setHistoryOpen(false);
    if (runIdFromHash() === id) openRun(id);
    else navigate(id);
  };

  const handleDelete = async (run: RunSummary) => {
    if (!window.confirm(`Delete the report on "${run.topic}"?`)) return;
    try {
      await deleteReport(run.id);
      setRuns(rs => rs.filter(r => r.id !== run.id));
      if (runIdFromHash() === run.id) goHome();
    } catch (err) {
      window.alert(getErrorMessage(err));
    }
  };

  const activeId = view.kind === 'running' || view.kind === 'report' ? view.id : null;
  const recent = runs.slice(0, 6);

  return (
    <MotionConfig reducedMotion="user">
      <div className="backdrop" aria-hidden="true" />
      <div className="app">
        <header className="topbar">
          <button className="icon-button" onClick={() => setHistoryOpen(true)} aria-label="Open history">
            <History size={18} />
          </button>
          <button className="brand" onClick={goHome}>
            <span className="brand-mark" aria-hidden="true">M</span>
            Markey
          </button>
          <div className="spacer" />
          <button className="icon-button" onClick={toggleTheme} aria-label="Switch light or dark appearance">
            <Sun size={18} className="theme-light-icon" />
            <Moon size={18} className="theme-dark-icon" />
          </button>
        </header>

        <main className="main">
          {view.kind === 'home' && (
            <>
              <section className="hero">
                <h1>
                  Market research,
                  <br />
                  <span className="hero-gradient">backed by sources.</span>
                </h1>
                <p>Name any market, product or industry. Markey reads the web and writes a brief where every claim links to its evidence.</p>
              </section>
              <SearchBar onSearch={handleSearch} />
              {recent.length > 0 && (
                <section className="recent">
                  <h2 className="section-title">Recent reports</h2>
                  <div className="recent-grid">
                    {recent.map(run => (
                      <button key={run.id} className="recent-card glass" onClick={() => openFromHistory(run.id)}>
                        <strong>{run.industry_name ?? run.topic}</strong>
                        <span className="history-meta">
                          <StatusBadge status={run.status} />
                          <span className="meta">
                            {relativeTime(run.created_at)}
                            {run.source_count > 0 && ` · ${run.source_count} sources`}
                          </span>
                        </span>
                      </button>
                    ))}
                  </div>
                </section>
              )}
            </>
          )}

          {view.kind === 'loading' && (
            <div style={{ display: 'grid', placeItems: 'center', paddingTop: '20vh', color: 'var(--text-muted)' }}>
              <Loader2 size={28} className="spin" aria-label="Loading" />
            </div>
          )}

          {view.kind === 'running' && (
            <ProgressSteps topic={view.topic} stage={view.stage} message={view.message} startedAt={view.startedAt} />
          )}

          {view.kind === 'report' && (
            <ReportView report={view.report} createdAt={view.createdAt} durationSeconds={view.duration} onNew={goHome} />
          )}

          {view.kind === 'error' && (
            <section className="error-card glass" role="alert">
              <div className="error-icon">
                <AlertCircle size={24} aria-hidden="true" />
              </div>
              <h2>{view.topic ? `Couldn't finish "${view.topic}"` : 'Something went wrong'}</h2>
              <p>{view.message}</p>
              <div className="actions">
                {view.topic && (
                  <button className="button button-primary" onClick={() => handleSearch(view.topic!)}>
                    Try again
                  </button>
                )}
                <button className="button button-secondary" onClick={goHome}>
                  New research
                </button>
              </div>
            </section>
          )}
        </main>
      </div>

      <HistoryDrawer
        open={historyOpen}
        runs={runs}
        activeId={activeId}
        onClose={() => setHistoryOpen(false)}
        onOpen={openFromHistory}
        onDelete={handleDelete}
      />
    </MotionConfig>
  );
}

export default App;
