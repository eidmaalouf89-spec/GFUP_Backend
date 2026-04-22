/* JANSA Executer page — pipeline launch with validation + polling.
   Calls window.jansaBridge.api directly:
     - get_app_state()           → auto-detected GED/GF paths
     - validate_inputs(...)      → pre-flight validation (errors/warnings)
     - run_pipeline_async(...)   → launch in backend worker thread
     - get_pipeline_status()     → polled every 600ms during execution
     - select_file(type)         → native file dialog

   Visual system: JANSA tokens only. No new CSS primitives.

   Safety model:
     - Single polling loop per run (cleanup on unmount + mode changes)
     - Gen counter: stale polls discarded after completion
     - Button disabled while validating, running, or invalid
     - Repeat-click guard: `launching` flag prevents double-launch race
     - After success: callback to shell refreshes global data
*/

function ExecuterPage({ onRunComplete }) {
  const { useState, useEffect, useRef } = React;
  const F = window.JANSA_FONTS;

  // ── Bridge guard ───────────────────────────────────────────────
  const api = (window.jansaBridge && window.jansaBridge.api) || null;

  // ── Form state ─────────────────────────────────────────────────
  const [runMode, setRunMode]       = useState('GED_GF');
  const [gedPath, setGedPath]       = useState('');
  const [gfPath, setGfPath]         = useState('');
  const [mappingPath, setMappingPath] = useState('');
  const [reportsDir, setReportsDir] = useState('');

  // ── Validation state ───────────────────────────────────────────
  const [validation, setValidation] = useState(null);
  const [validating, setValidating] = useState(false);

  // ── Execution state ────────────────────────────────────────────
  const [running, setRunning]       = useState(false);
  const [launching, setLaunching]   = useState(false);     // true between click and backend ack
  const [statusMsg, setStatusMsg]   = useState('');
  const [done, setDone]             = useState(false);
  const [completedRun, setCompletedRun] = useState(null);
  const [errorMsg, setErrorMsg]     = useState(null);
  const [warnings, setWarnings]     = useState([]);

  const validateGenRef = useRef(0);
  const pollGenRef     = useRef(0);

  // ── Initial app_state load (auto-detect GED/GF) ───────────────
  useEffect(() => {
    let cancelled = false;
    async function loadAppState() {
      if (!api) return;
      try {
        const s = await api.get_app_state();
        if (cancelled || !s) return;
        if (s.ged_file_detected && !gedPath) setGedPath(s.ged_file_detected);
        if (s.gf_file_detected  && !gfPath)  setGfPath(s.gf_file_detected);
      } catch (e) {
        // non-fatal — user can still browse manually
      }
    }
    loadAppState();
    return () => { cancelled = true; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // ── Reactive validation ───────────────────────────────────────
  useEffect(() => {
    if (!api) return;
    const gen = ++validateGenRef.current;
    let cancelled = false;
    async function doValidate() {
      setValidating(true);
      try {
        // Backend signature: validate_inputs(run_mode, ged_path, gf_path, reports_dir)
        // Mapping is NOT passed — backend does not consume it.
        const result = await api.validate_inputs(
          runMode,
          gedPath || null,
          gfPath  || null,
          reportsDir || null,
        );
        if (cancelled || gen !== validateGenRef.current) return;
        setValidation(result || null);
      } catch (e) {
        if (cancelled || gen !== validateGenRef.current) return;
        setValidation({ valid: false, errors: [String(e)], warnings: [] });
      } finally {
        if (!cancelled && gen === validateGenRef.current) setValidating(false);
      }
    }
    doValidate();
    return () => { cancelled = true; };
  }, [runMode, gedPath, gfPath, reportsDir, api]);

  // ── Polling loop — single active loop guarded by gen counter ──
  useEffect(() => {
    if (!running || !api) return;
    const gen = ++pollGenRef.current;
    let stopped = false;

    const interval = setInterval(async () => {
      if (stopped || gen !== pollGenRef.current) return;
      let status = null;
      try {
        status = await api.get_pipeline_status();
      } catch (e) {
        // network/backend flake — keep polling
        return;
      }
      // Superseded or unmounted: ignore result
      if (stopped || gen !== pollGenRef.current) return;
      if (!status) return;

      setStatusMsg(status.message || '');
      if (Array.isArray(status.warnings)) setWarnings(status.warnings);

      if (!status.running) {
        clearInterval(interval);
        stopped = true;
        setRunning(false);
        if (status.completed_run != null) {
          setDone(true);
          setCompletedRun(status.completed_run);
          // Refresh shell global data so Runs/Overview reflect the new run
          if (typeof onRunComplete === 'function') {
            try { onRunComplete(); } catch (e) { /* swallow */ }
          }
        }
        if (status.error) {
          setErrorMsg(status.error);
        }
      }
    }, 600);

    return () => {
      stopped = true;
      clearInterval(interval);
    };
  }, [running, api, onRunComplete]);

  // ── Cleanup on unmount: supersede any polling ─────────────────
  useEffect(() => {
    return () => { pollGenRef.current += 1; };
  }, []);

  // ── Handlers ──────────────────────────────────────────────────
  const handleBrowse = async (type) => {
    if (!api) return;
    try {
      const path = await api.select_file(type);
      if (!path) return;
      if      (type === 'ged')        setGedPath(path);
      else if (type === 'gf')         setGfPath(path);
      else if (type === 'mapping')    setMappingPath(path);
      else if (type === 'report_dir') setReportsDir(path);
    } catch (e) {
      // Dialog cancel or native error — no-op
    }
  };

  const handleLaunch = async () => {
    if (!api || launching || running) return;
    if (validation && !validation.valid) return;

    setLaunching(true);
    setErrorMsg(null);
    setDone(false);
    setCompletedRun(null);
    setStatusMsg('Démarrage…');
    setWarnings([]);

    try {
      const result = await api.run_pipeline_async(
        runMode,
        gedPath || null,
        gfPath  || null,
        reportsDir || null,
      );
      if (result && result.started) {
        setRunning(true);
        if (Array.isArray(result.warnings)) setWarnings(result.warnings);
      } else {
        const errs = (result && result.errors) || ['Lancement refusé par le backend'];
        setErrorMsg(errs.join(' ; '));
        setStatusMsg('');
      }
    } catch (e) {
      setErrorMsg(e.message || String(e));
      setStatusMsg('');
    } finally {
      setLaunching(false);
    }
  };

  const resetAfterSuccess = () => {
    setDone(false);
    setCompletedRun(null);
    setStatusMsg('');
    setWarnings([]);
    setErrorMsg(null);
  };

  const resetAfterError = () => {
    setErrorMsg(null);
    setStatusMsg('');
  };

  // ── Derived state ─────────────────────────────────────────────
  const hasErrors   = !!(validation && !validation.valid && (validation.errors || []).length);
  const hasWarnings = !!(validation && (validation.warnings || []).length);
  const canLaunch   = !!api && !launching && !running && !validating && !hasErrors;

  const gfDisabled = runMode === 'GED_ONLY';

  // ── Render ────────────────────────────────────────────────────
  if (!api) {
    return (
      <div style={{ padding: 48, fontFamily: F.ui }}>
        <PageHeading/>
        <div style={{
          marginTop: 20, padding: '14px 18px', borderRadius: 10,
          background: 'var(--bad-soft)', border: '1px solid rgba(255,69,58,0.35)',
          color: 'var(--bad)', fontSize: 13,
        }}>
          ⚠ Backend non connecté — impossible de lancer le pipeline.
        </div>
      </div>
    );
  }

  return (
    <div style={{ padding: 48, fontFamily: F.ui }}>
      <PageHeading/>

      {/* Run mode selector */}
      <_Card title="Mode d'exécution">
        <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap' }}>
          {RUN_MODES.map(m => (
            <_ModeButton
              key={m.value}
              mode={m}
              active={runMode === m.value}
              disabled={running || launching}
              onClick={() => setRunMode(m.value)}
            />
          ))}
        </div>
        <div style={{ fontSize: 12, color: 'var(--text-3)', marginTop: 12 }}>
          {RUN_MODES.find(m => m.value === runMode)?.desc}
        </div>
      </_Card>

      {/* File inputs */}
      <_Card title="Fichiers d'entrée">
        <_FileRow
          label="GED"
          path={gedPath}
          required
          onBrowse={() => handleBrowse('ged')}
          disabled={running || launching}
        />
        <_FileRow
          label="GF"
          path={gfPath}
          required={!gfDisabled}
          disabledValue={gfDisabled}
          placeholder={gfDisabled ? 'Hérité du dernier run' : null}
          onBrowse={() => handleBrowse('gf')}
          disabled={gfDisabled || running || launching}
        />
        <_FileRow
          label="Mapping"
          path={mappingPath}
          required={false}
          hint="(informatif — non transmis au backend)"
          onBrowse={() => handleBrowse('mapping')}
          disabled={running || launching}
        />
        {runMode === 'GED_REPORT' && (
          <_FileRow
            label="Rapports"
            path={reportsDir}
            required
            onBrowse={() => handleBrowse('report_dir')}
            disabled={running || launching}
          />
        )}
      </_Card>

      {/* Validation */}
      {hasErrors && (
        <_MessageCard
          tone="bad"
          title="Erreurs de validation"
          items={validation.errors}
        />
      )}
      {hasWarnings && (
        <_MessageCard
          tone="warn"
          title="Avertissements"
          items={validation.warnings}
        />
      )}
      {runMode === 'GED_ONLY' && !hasErrors && (
        <_InfoBanner
          text="GF sera hérité automatiquement du dernier run complété."
        />
      )}

      {/* Launch + execution */}
      <_Card title="Exécution">
        {/* Idle state — show launch button */}
        {!running && !done && !errorMsg && (
          <button
            onClick={handleLaunch}
            disabled={!canLaunch}
            style={{
              padding: '11px 28px', fontSize: 13, fontWeight: 600,
              border: 'none', borderRadius: 10,
              background: canLaunch
                ? 'linear-gradient(135deg, #0A84FF, #5E5CE6)'
                : 'var(--bg-chip)',
              color: canLaunch ? '#fff' : 'var(--text-3)',
              cursor: canLaunch ? 'pointer' : 'not-allowed',
              fontFamily: F.ui, letterSpacing: '.02em',
              boxShadow: canLaunch ? '0 4px 18px -4px rgba(10,132,255,0.4)' : 'none',
              transition: 'all 0.18s',
            }}
          >
            {launching ? 'Démarrage…' : 'Lancer le pipeline'}
          </button>
        )}

        {/* Running state */}
        {running && (
          <div style={{ display: 'flex', alignItems: 'center', gap: 14 }}>
            <div style={{
              width: 18, height: 18, borderRadius: '50%',
              border: '2px solid var(--accent)', borderTopColor: 'transparent',
              animation: 'execSpinner 0.7s linear infinite', flexShrink: 0,
            }}/>
            <div style={{ fontSize: 13, color: 'var(--text-2)' }}>
              {statusMsg || 'Exécution en cours…'}
            </div>
          </div>
        )}

        {/* Success state */}
        {done && completedRun != null && (
          <div>
            <div style={{
              display: 'flex', alignItems: 'center', gap: 10, marginBottom: 12,
            }}>
              <span style={{
                width: 8, height: 8, borderRadius: '50%',
                background: 'var(--good)', boxShadow: '0 0 8px var(--good)',
              }}/>
              <span style={{ fontSize: 14, fontWeight: 500, color: 'var(--good)' }}>
                {statusMsg || `Run ${completedRun} terminé`}
              </span>
            </div>
            {warnings.length > 0 && (
              <div style={{ marginBottom: 12 }}>
                {warnings.map((w, i) => (
                  <div key={i} style={{
                    fontSize: 12, color: 'var(--warn)', marginBottom: 2,
                    paddingLeft: 12, position: 'relative',
                  }}>
                    <span style={{ position: 'absolute', left: 0 }}>•</span>{w}
                  </div>
                ))}
              </div>
            )}
            <button onClick={resetAfterSuccess} style={{
              padding: '8px 18px', fontSize: 12, fontWeight: 500,
              border: '1px solid rgba(48,209,88,0.35)', borderRadius: 8,
              background: 'var(--good-soft)', color: 'var(--good)',
              cursor: 'pointer', fontFamily: F.ui,
            }}>
              Nouveau run
            </button>
          </div>
        )}

        {/* Error state */}
        {errorMsg && (
          <div>
            <div style={{
              display: 'flex', alignItems: 'center', gap: 10, marginBottom: 12,
            }}>
              <span style={{
                width: 8, height: 8, borderRadius: '50%',
                background: 'var(--bad)', boxShadow: '0 0 8px var(--bad)',
              }}/>
              <span style={{ fontSize: 14, fontWeight: 500, color: 'var(--bad)' }}>
                Pipeline échoué
              </span>
            </div>
            <div style={{
              fontSize: 12, color: 'var(--bad)',
              background: 'var(--bad-soft)',
              padding: '12px 14px', borderRadius: 8, marginBottom: 12,
              border: '1px solid rgba(255,69,58,0.3)',
              whiteSpace: 'pre-wrap', wordBreak: 'break-word',
            }}>
              {errorMsg}
            </div>
            <button onClick={resetAfterError} style={{
              padding: '8px 18px', fontSize: 12, fontWeight: 500,
              border: '1px solid rgba(255,69,58,0.35)', borderRadius: 8,
              background: 'var(--bad-soft)', color: 'var(--bad)',
              cursor: 'pointer', fontFamily: F.ui,
            }}>
              Réessayer
            </button>
          </div>
        )}
      </_Card>

      <style>{`
        @keyframes execSpinner {
          to { transform: rotate(360deg); }
        }
      `}</style>
    </div>
  );
}

/* ── Sub-components (JANSA-styled) ── */

const RUN_MODES = [
  { value: 'GED_GF',     label: 'GED + GF',       desc: 'Run complet avec export GED et GrandFichier.' },
  { value: 'GED_ONLY',   label: 'GED seul',       desc: 'Export GED uniquement — GF hérité du dernier run.' },
  { value: 'GED_REPORT', label: 'GED + Rapports', desc: 'Export GED avec un répertoire de rapports existant.' },
];

function PageHeading() {
  const F = window.JANSA_FONTS;
  return (
    <div>
      <h1 style={{
        fontFamily: F.ui, fontSize: 40, fontWeight: 300,
        letterSpacing: '-.03em', color: 'var(--text)', margin: 0,
      }}>Exécuter</h1>
      <p style={{ marginTop: 8, fontSize: 13, color: 'var(--text-3)' }}>
        Lance le pipeline de mise à jour du GrandFichier.
      </p>
    </div>
  );
}

function _Card({ title, children }) {
  return (
    <div style={{
      marginTop: 20,
      background: 'var(--bg-elev)',
      border: '1px solid var(--line)',
      borderRadius: 12,
      padding: '18px 22px',
    }}>
      <div style={{
        fontSize: 12, fontWeight: 600, color: 'var(--text-3)',
        letterSpacing: '.08em', textTransform: 'uppercase',
        marginBottom: 14,
      }}>
        {title}
      </div>
      {children}
    </div>
  );
}

function _ModeButton({ mode, active, disabled, onClick }) {
  const F = window.JANSA_FONTS;
  return (
    <button
      onClick={onClick}
      disabled={disabled}
      style={{
        padding: '9px 18px', fontSize: 12.5, fontWeight: 500,
        border: `1px solid ${active ? 'rgba(10,132,255,0.45)' : 'var(--line)'}`,
        borderRadius: 8,
        background: active ? 'var(--accent-soft)' : 'var(--bg-elev-2)',
        color: active ? 'var(--accent)' : 'var(--text-2)',
        cursor: disabled ? 'not-allowed' : 'pointer',
        fontFamily: F.ui, letterSpacing: '.01em',
        opacity: disabled ? 0.55 : 1,
        transition: 'all 0.15s',
      }}
    >
      {mode.label}
    </button>
  );
}

function _FileRow({ label, path, required, onBrowse, disabled, disabledValue, placeholder, hint }) {
  const F = window.JANSA_FONTS;
  const fileName = path ? path.split(/[\\/]/).pop() : null;
  const missing = required && !path;
  const borderColor = disabledValue
    ? 'var(--line)'
    : path
      ? 'rgba(48,209,88,0.3)'
      : missing
        ? 'rgba(255,69,58,0.3)'
        : 'var(--line)';

  return (
    <div style={{
      display: 'flex', alignItems: 'center', gap: 12, marginBottom: 12,
    }}>
      <div style={{
        fontSize: 11, color: 'var(--text-3)', width: 90, flexShrink: 0,
        textTransform: 'uppercase', letterSpacing: '.06em', fontWeight: 600,
      }}>{label}</div>
      <div style={{
        flex: 1, fontSize: 12.5,
        color: disabledValue ? 'var(--text-3)' : 'var(--text)',
        padding: '9px 14px',
        background: 'var(--bg-elev-2)',
        border: `1px solid ${borderColor}`,
        borderRadius: 8, fontFamily: F.ui,
        overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
      }}>
        {fileName ? fileName : (
          <span style={{ color: 'var(--text-3)' }}>
            {placeholder || (missing ? 'Aucun fichier sélectionné' : 'Optionnel')}
          </span>
        )}
        {hint && (
          <span style={{
            marginLeft: 10, fontSize: 10.5, color: 'var(--text-3)',
            letterSpacing: '.02em',
          }}>{hint}</span>
        )}
      </div>
      <button
        onClick={onBrowse}
        disabled={disabled}
        style={{
          padding: '8px 14px', fontSize: 11.5, fontWeight: 500,
          border: '1px solid var(--line)', borderRadius: 8,
          background: 'var(--bg-elev-2)', color: 'var(--text-2)',
          cursor: disabled ? 'not-allowed' : 'pointer',
          fontFamily: F.ui, opacity: disabled ? 0.5 : 1,
          flexShrink: 0, transition: 'all 0.15s',
        }}
      >Parcourir</button>
    </div>
  );
}

function _MessageCard({ tone, title, items }) {
  const palette = tone === 'bad'
    ? { color: 'var(--bad)',  bg: 'var(--bad-soft)',  border: 'rgba(255,69,58,0.35)' }
    : { color: 'var(--warn)', bg: 'var(--warn-soft)', border: 'rgba(255,214,10,0.35)' };
  return (
    <div style={{
      marginTop: 14,
      background: palette.bg,
      border: `1px solid ${palette.border}`,
      borderRadius: 10,
      padding: '12px 16px',
    }}>
      <div style={{
        fontSize: 11, fontWeight: 600, color: palette.color,
        letterSpacing: '.06em', textTransform: 'uppercase', marginBottom: 6,
      }}>{title}</div>
      {items.map((t, i) => (
        <div key={i} style={{
          fontSize: 12.5, color: palette.color, marginBottom: 2,
          paddingLeft: 12, position: 'relative',
        }}>
          <span style={{ position: 'absolute', left: 0 }}>•</span>{t}
        </div>
      ))}
    </div>
  );
}

function _InfoBanner({ text }) {
  return (
    <div style={{
      marginTop: 14,
      background: 'var(--accent-soft)',
      border: '1px solid rgba(10,132,255,0.35)',
      borderRadius: 10,
      padding: '12px 16px',
      fontSize: 12.5, color: 'var(--accent)',
    }}>
      {text}
    </div>
  );
}

Object.assign(window, { ExecuterPage });
