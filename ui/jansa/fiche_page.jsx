/* Wrapper page: renders the fiche inside the app shell with a back button.
   ── CONNECTED VERSION ──
   Uses window.FICHE_DATA loaded by data_bridge (per-consultant, from backend).
   Falls back to error state if data not loaded.

   Step 6 — BRIDGE layer: drilldown wiring.
   Calls bridge.api.get_doc_details and renders DrilldownDrawer.
   Generation counter prevents stale responses from overwriting newer ones.

   Step 11 — ExportTeamVersionButton added for parity with legacy fiche view. */

/* ── ExportTeamVersionButton (Step 11) ── */
function FicheExportButton() {
  const [exporting, setExporting] = React.useState(false);
  const [result, setResult] = React.useState(null);

  const handleExport = async () => {
    if (!window.jansaBridge || !window.jansaBridge.api) return;
    setExporting(true);
    setResult(null);
    try {
      const res = await window.jansaBridge.api.export_team_version();
      if (res && res.success) {
        setResult({ ok: true });
        if (window.jansaBridge.api.open_file_in_explorer && res.path) {
          window.jansaBridge.api.open_file_in_explorer(res.path);
        }
      } else {
        setResult({ ok: false });
      }
    } catch (e) {
      setResult({ ok: false });
    } finally {
      setExporting(false);
      setTimeout(() => setResult(null), 4000);
    }
  };

  return (
    <button
      onClick={handleExport}
      disabled={exporting}
      style={{
        padding: '6px 14px', borderRadius: 8,
        background: 'var(--accent-soft)',
        border: '1px solid rgba(10,132,255,0.35)',
        color: 'var(--accent)',
        fontFamily: window.JANSA_FONTS.ui, fontSize: 12, fontWeight: 500,
        cursor: exporting ? 'wait' : 'pointer',
        opacity: exporting ? 0.6 : 1,
        transition: 'opacity 0.15s',
      }}
    >
      {exporting ? 'Export\u2026'
        : result ? (result.ok ? '\u2713 Export\u00e9' : '\u2717 Erreur')
        : 'Tableau de Suivi VISA'}
    </button>
  );
}

function ConsultantFichePage({ consultant, onBack, focusMode }) {
  const base = window.FICHE_DATA;

  // ── Drilldown state ────────────────────────────────────────────────────────
  // null = closed. Otherwise: { loading, error, docs, count, title, filterKey, lotName }
  const [drilldown, setDrilldown] = React.useState(null);
  const drillGenRef = React.useRef(0);

  // The consultant canonical name used for backend calls
  const consultantName = (consultant && (consultant.canonical_name || consultant.name)) || '';

  // handleDrilldown is called from inside ConsultantFiche when a clickable number is clicked
  const handleDrilldown = async ({ filterKey, lotName, label }) => {
    if (!window.jansaBridge || !window.jansaBridge.api) return;

    // Claim a generation slot — any older request returning later will be discarded
    const gen = ++drillGenRef.current;

    setDrilldown({
      loading: true,
      error: null,
      docs: [],
      count: 0,
      title: label || filterKey,
      filterKey,
      lotName: lotName || null,
    });

    try {
      const result = await window.jansaBridge.api.get_doc_details(
        consultantName,
        filterKey,
        lotName || null,
        !!focusMode
      );

      if (gen !== drillGenRef.current) return; // stale — newer click happened

      if (!result || result.error) {
        setDrilldown(prev => ({
          ...prev,
          loading: false,
          error: result ? result.error : 'Erreur réseau',
        }));
      } else {
        setDrilldown(prev => ({
          ...prev,
          loading: false,
          docs: Array.isArray(result.docs) ? result.docs : [],
          count: result.count || 0,
        }));
      }
    } catch (e) {
      if (gen !== drillGenRef.current) return;
      setDrilldown(prev => ({
        ...prev,
        loading: false,
        error: e.message || 'Erreur inconnue',
      }));
    }
  };

  const closeDrilldown = () => {
    drillGenRef.current++; // invalidate any in-flight request
    setDrilldown(null);
  };

  const handleExport = async () => {
    if (!window.jansaBridge || !window.jansaBridge.api) return;
    if (!drilldown) return;
    try {
      const result = await window.jansaBridge.api.export_drilldown_xlsx(
        consultantName,
        drilldown.filterKey,
        drilldown.lotName || null,
        !!focusMode
      );
      if (!result || !result.success) {
        console.error("[export] Backend error:", result && result.error);
      }
    } catch (e) {
      console.error("[export] Exception:", e);
    }
  };

  // ── Error / not-loaded state ───────────────────────────────────────────────
  if (!base || base.error) {
    return (
      <div style={{
        padding: 48, color: 'var(--text-2)',
        animation: 'fadeInUp 0.4s cubic-bezier(.4,0,.2,1)',
      }}>
        <button onClick={onBack} style={{
          background: 'none', border: '1px solid var(--line)', borderRadius: 8,
          color: 'var(--text-2)', padding: '6px 14px', cursor: 'pointer',
          fontFamily: window.JANSA_FONTS.ui, fontSize: 12, marginBottom: 20,
        }}>{'\u2190'} Retour</button>
        <h1 style={{
          fontFamily: window.JANSA_FONTS.ui, fontSize: 32, fontWeight: 300,
          letterSpacing: '-.03em', color: 'var(--text)', margin: 0,
        }}>
          {consultant ? (consultant.name || 'Consultant') : 'Consultant'}
        </h1>
        <p style={{ marginTop: 14, fontSize: 14, color: 'var(--bad)' }}>
          {base && base.error ? base.error : 'Donn\u00e9es de fiche non disponibles.'}
        </p>
      </div>
    );
  }

  // Use fiche backend data as authoritative; only overlay id/slug from list card
  const data = consultant ? {
    ...base,
    consultant: {
      ...base.consultant,
      id: consultant.id ?? base.consultant.id,
      slug: consultant.slug ?? base.consultant.slug,
    },
  } : base;

  return (
    <div style={{ animation: 'fadeInUp 0.4s cubic-bezier(.4,0,.2,1)', position: 'relative' }}>
      {/* Fiche action bar — export team version (Step 11 parity) */}
      <div style={{
        position: 'absolute', top: 14, right: 28, zIndex: 10,
        display: 'flex', alignItems: 'center', gap: 8,
      }}>
        <FicheExportButton/>
      </div>
      <window.ConsultantFiche
        data={data}
        lang="fr"
        onBack={onBack}
        onDrilldown={handleDrilldown}
      />
      <window.DrilldownDrawer state={drilldown} onClose={closeDrilldown} onExport={handleExport}/>
    </div>
  );
}

window.ConsultantFichePage = ConsultantFichePage;
