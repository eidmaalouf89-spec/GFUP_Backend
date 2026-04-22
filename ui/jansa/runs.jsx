/* JANSA Runs page — run history with current/baseline badges and export ZIP.
   Calls window.jansaBridge.api.get_all_runs() and export_run_bundle(n) directly.
   No new APIs: both methods already exist in app.py.
   Visual system matches JANSA design tokens — no new styling primitives. */

function RunsPage() {
  const { useState, useEffect } = React;
  const [runs, setRuns] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  // per-card export state: { [run_number]: null | 'loading' | 'done' | 'error' }
  const [exportState, setExportState] = useState({});

  useEffect(() => {
    let cancelled = false;
    async function load() {
      try {
        if (!window.jansaBridge || !window.jansaBridge.api) {
          if (!cancelled) setError("Backend non connecté — impossible de charger l'historique des runs.");
          return;
        }
        const result = await window.jansaBridge.api.get_all_runs();
        if (cancelled) return;
        if (result && result.error) {
          setError(result.error);
        } else if (Array.isArray(result)) {
          setRuns(result);
        } else {
          setError("Réponse invalide du backend.");
        }
      } catch (e) {
        if (!cancelled) setError(e.message || String(e));
      } finally {
        if (!cancelled) setLoading(false);
      }
    }
    load();
    return () => { cancelled = true; };
  }, []);

  const exportBundle = async (runNumber) => {
    // Guard: ignore repeated clicks while already exporting
    if (exportState[runNumber] === 'loading') return;

    setExportState(s => ({ ...s, [runNumber]: 'loading' }));
    try {
      if (!window.jansaBridge || !window.jansaBridge.api) {
        setExportState(s => ({ ...s, [runNumber]: 'error' }));
        return;
      }
      const result = await window.jansaBridge.api.export_run_bundle(runNumber);
      if (result && result.success) {
        setExportState(s => ({ ...s, [runNumber]: 'done' }));
        setTimeout(() => setExportState(s => ({ ...s, [runNumber]: null })), 3000);
      } else {
        setExportState(s => ({ ...s, [runNumber]: 'error' }));
        setTimeout(() => setExportState(s => ({ ...s, [runNumber]: null })), 4000);
      }
    } catch (e) {
      setExportState(s => ({ ...s, [runNumber]: 'error' }));
      setTimeout(() => setExportState(s => ({ ...s, [runNumber]: null })), 4000);
    }
  };

  const F = window.JANSA_FONTS;

  if (loading) {
    return (
      <div style={{
        padding: 48, display: 'flex', alignItems: 'center', gap: 12,
        color: 'var(--text-3)', fontFamily: F.ui, fontSize: 13,
      }}>
        <div style={{
          width: 16, height: 16, borderRadius: '50%',
          border: '2px solid var(--accent)', borderTopColor: 'transparent',
          animation: 'runsSpinner 0.7s linear infinite', flexShrink: 0,
        }}/>
        Chargement de l'historique…
      </div>
    );
  }

  if (error) {
    return (
      <div style={{ padding: 48, fontFamily: F.ui }}>
        <PageHeading runs={null}/>
        <div style={{
          marginTop: 20, padding: '14px 18px', borderRadius: 10,
          background: 'var(--bad-soft)', border: '1px solid rgba(255,69,58,0.35)',
          color: 'var(--bad)', fontSize: 13,
        }}>
          ⚠ {error}
        </div>
      </div>
    );
  }

  if (!runs || runs.length === 0) {
    return (
      <div style={{ padding: 48, fontFamily: F.ui }}>
        <PageHeading runs={[]}/>
        <p style={{ marginTop: 14, fontSize: 14, color: 'var(--text-2)' }}>
          Aucun run trouvé. Lancez d'abord le pipeline.
        </p>
      </div>
    );
  }

  return (
    <div style={{ padding: 48, fontFamily: F.ui }}>
      <PageHeading runs={runs}/>

      <div style={{ display: 'flex', flexDirection: 'column', gap: 10, marginTop: 28 }}>
        {runs.map(run => (
          <RunCard
            key={run.run_number}
            run={run}
            exportState={exportState[run.run_number] || null}
            onExport={exportBundle}
          />
        ))}
      </div>

      <style>{`
        @keyframes runsSpinner {
          to { transform: rotate(360deg); }
        }
      `}</style>
    </div>
  );
}

function PageHeading({ runs }) {
  const F = window.JANSA_FONTS;
  const count = runs ? runs.length : null;
  return (
    <div>
      <h1 style={{
        fontFamily: F.ui, fontSize: 40, fontWeight: 300,
        letterSpacing: '-.03em', color: 'var(--text)', margin: 0,
      }}>Runs</h1>
      {count !== null && (
        <p style={{ marginTop: 8, fontSize: 13, color: 'var(--text-3)' }}>
          {count} run{count !== 1 ? 's' : ''} enregistré{count !== 1 ? 's' : ''}
        </p>
      )}
    </div>
  );
}

function RunCard({ run, exportState, onExport }) {
  const F = window.JANSA_FONTS;
  const isBusy = exportState === 'loading';
  const status = _runStatusInfo(run.status);
  const createdLabel = _fmtDate(run.created_at);
  const completedLabel = run.completed_at ? _fmtDate(run.completed_at) : null;

  return (
    <div style={{
      background: 'var(--bg-elev)',
      border: run.is_current
        ? '1px solid rgba(10,132,255,0.35)'
        : '1px solid var(--line)',
      borderRadius: 12,
      padding: '16px 20px',
      display: 'flex',
      alignItems: 'center',
      gap: 18,
    }}>

      {/* Run number avatar */}
      <div style={{
        flexShrink: 0,
        width: 48, height: 48, borderRadius: 12,
        background: run.is_current ? 'var(--accent-soft)' : 'var(--bg-elev-2)',
        border: `1px solid ${run.is_current ? 'rgba(10,132,255,0.35)' : 'var(--line)'}`,
        display: 'flex', alignItems: 'center', justifyContent: 'center',
      }}>
        <span style={{
          fontFamily: F.num, fontSize: 15, fontWeight: 700,
          color: run.is_current ? 'var(--accent)' : 'var(--text)',
          letterSpacing: '-.02em',
        }}>
          #{run.run_number}
        </span>
      </div>

      {/* Label + badges + meta */}
      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{
          display: 'flex', alignItems: 'center', gap: 8,
          flexWrap: 'wrap', marginBottom: 6,
        }}>
          <span style={{ fontSize: 13, fontWeight: 600, color: 'var(--text)' }}>
            {run.run_label || `Run ${run.run_number}`}
          </span>
          {run.is_baseline === true  && <_Badge label="Baseline" color="#FF9500" bg="rgba(255,149,0,0.14)" />}
          {run.is_current === true   && <_Badge label="Current"  color="var(--accent)" bg="var(--accent-soft)" />}
          {run.is_stale === true     && <_Badge label="Périmé"   color="var(--bad)"    bg="var(--bad-soft)" />}
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 18, flexWrap: 'wrap' }}>
          <_Meta label="Mode"   value={_typeLabel(run.run_type)} />
          <_Meta label="Créé"   value={createdLabel} />
          {completedLabel && <_Meta label="Terminé" value={completedLabel} />}
          {run.is_stale && run.stale_reason && (
            <_Meta label="Raison péremption" value={run.stale_reason} valueColor="var(--bad)" />
          )}
        </div>
      </div>

      {/* Status chip */}
      <div style={{
        flexShrink: 0,
        padding: '5px 11px', borderRadius: 99,
        background: status.bg,
        border: `1px solid ${status.border}`,
        color: status.color,
        fontSize: 11, fontWeight: 600, letterSpacing: '.04em',
        textTransform: 'uppercase',
        fontFamily: F.ui,
      }}>
        {status.label}
      </div>

      {/* Export ZIP button */}
      <button
        onClick={() => onExport(run.run_number)}
        disabled={isBusy}
        title={`Exporter le bundle ZIP du Run ${run.run_number}`}
        style={{
          flexShrink: 0,
          padding: '7px 14px', borderRadius: 8,
          background: exportState === 'done'  ? 'var(--good-soft)'
                    : exportState === 'error' ? 'var(--bad-soft)'
                    : 'var(--bg-elev-2)',
          border: `1px solid ${
            exportState === 'done'  ? 'rgba(48,209,88,0.4)'
          : exportState === 'error' ? 'rgba(255,69,58,0.4)'
          : 'var(--line)'}`,
          color: exportState === 'done'  ? 'var(--good)'
               : exportState === 'error' ? 'var(--bad)'
               : 'var(--text-2)',
          fontFamily: F.ui, fontSize: 12, fontWeight: 500,
          cursor: isBusy ? 'not-allowed' : 'pointer',
          display: 'flex', alignItems: 'center', gap: 6,
          transition: 'background 0.18s, border-color 0.18s, color 0.18s',
          opacity: isBusy ? 0.65 : 1,
        }}
      >
        {isBusy ? (
          <>
            <span style={{
              width: 12, height: 12,
              border: '2px solid currentColor', borderTopColor: 'transparent',
              borderRadius: '50%', display: 'inline-block',
              animation: 'runsSpinner 0.7s linear infinite',
            }}/>
            Export…
          </>
        ) : exportState === 'done' ? (
          <>
            <svg width="12" height="12" viewBox="0 0 12 12" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M2 6.5 L4.5 9 L10 3"/>
            </svg>
            Exporté
          </>
        ) : exportState === 'error' ? (
          <>
            <svg width="12" height="12" viewBox="0 0 12 12" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M2 2 L10 10 M10 2 L2 10"/>
            </svg>
            Erreur
          </>
        ) : (
          <>
            <svg width="13" height="13" viewBox="0 0 13 13" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
              <path d="M6.5 1.5 v6"/>
              <path d="M3.5 5.5 l3 3 3-3"/>
              <path d="M1.5 10.5 H11.5"/>
            </svg>
            Export ZIP
          </>
        )}
      </button>
    </div>
  );
}

/* ── Shared sub-components ── */

function _Badge({ label, color, bg }) {
  return (
    <span style={{
      fontSize: 10, fontWeight: 600, letterSpacing: '.06em',
      padding: '2px 7px', borderRadius: 99,
      background: bg, color: color,
      border: `1px solid ${color === 'var(--accent)' ? 'rgba(10,132,255,0.35)' : color + '55'}`,
      textTransform: 'uppercase',
    }}>
      {label}
    </span>
  );
}

function _Meta({ label, value, valueColor }) {
  return (
    <span style={{
      fontSize: 11, color: 'var(--text-3)',
      display: 'flex', alignItems: 'center', gap: 4,
    }}>
      {label}:
      <span style={{ color: valueColor || 'var(--text-2)', fontWeight: 500 }}>
        {value}
      </span>
    </span>
  );
}

/* ── Pure helpers ── */

function _runStatusInfo(status) {
  switch ((status || '').toUpperCase()) {
    case 'COMPLETED':
      return { label: 'Complété', color: 'var(--good)', bg: 'var(--good-soft)', border: 'rgba(48,209,88,0.3)' };
    case 'FAILED':
      return { label: 'Échoué',   color: 'var(--bad)',  bg: 'var(--bad-soft)',  border: 'rgba(255,69,58,0.3)' };
    case 'STARTED':
      return { label: 'En cours', color: 'var(--warn)', bg: 'var(--warn-soft)', border: 'rgba(255,214,10,0.3)' };
    default:
      return { label: status || '—', color: 'var(--neutral)', bg: 'var(--neutral-soft)', border: 'rgba(142,142,147,0.3)' };
  }
}

function _typeLabel(run_type) {
  const map = { BASELINE: 'Baseline', INCREMENTAL: 'Incrémental', REBUILD: 'Rebuild' };
  return map[run_type] || run_type || '—';
}

function _fmtDate(isoStr) {
  if (!isoStr) return '—';
  try {
    const d = new Date(isoStr);
    return d.toLocaleDateString('fr-FR', {
      day: '2-digit', month: '2-digit', year: 'numeric',
      hour: '2-digit', minute: '2-digit',
    });
  } catch (e) {
    return isoStr.slice(0, 16).replace('T', ' ');
  }
}

Object.assign(window, { RunsPage });
