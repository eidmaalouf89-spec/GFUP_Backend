import { useState, useEffect } from 'react'
import ConsultantFicheComponent from './components/ConsultantFiche'

/* ── Design Tokens ──────────────────────────────────────────── */
const T = {
  bg:          'var(--bg)',
  bgElev:      'var(--bg-elev)',
  bgElev2:     'var(--bg-elev-2)',
  chip:        'var(--bg-chip)',
  glass:       'var(--bg-elev)',
  glassBorder: 'var(--line)',
  line2:       'var(--line-2)',
  text:        'var(--text)',
  muted:       'var(--text-2)',
  dim:         'var(--text-3)',
  accent:      'var(--accent)',
  accentSoft:  'var(--accent-soft)',
  green:       'var(--good)',
  amber:       'var(--warn)',
  red:         'var(--bad)',
  neutral:     'var(--neutral)',
  sidebarW:    232,
}

const S = {
  accent: 'var(--accent-soft)',
  good: 'var(--good-soft)',
  warn: 'var(--warn-soft)',
  bad: 'var(--bad-soft)',
  neutral: 'var(--neutral-soft)',
}

const VISA_TONE = {
  VSO: { color: T.green, bg: S.good },
  VAO: { color: T.amber, bg: S.warn },
  REF: { color: T.red, bg: S.bad },
  'SAS REF': { color: T.red, bg: S.bad },
  HM: { color: T.neutral, bg: S.neutral },
  Open: { color: T.accent, bg: S.accent },
}

/* ── Shared Styles ──────────────────────────────────────────── */
const glassCard = {
  background: T.glass,
  border: `1px solid ${T.glassBorder}`,
  borderRadius: 16,
  boxShadow: 'none',
}

/* ── PyWebView bridge — waits for .api to be injected ──────── */
const _bridgeReady = new Promise((resolve) => {
  const check = () => {
    if (window.pywebview && window.pywebview.api) {
      resolve(window.pywebview.api)
      return true
    }
    return false
  }
  // Already available?
  if (check()) return
  // Listen for the official event
  const onReady = () => { check(); window.removeEventListener('pywebviewready', onReady) }
  window.addEventListener('pywebviewready', onReady)
  // Safety poll: pywebviewready can fire before React hydrates
  const iv = setInterval(() => { if (check()) clearInterval(iv) }, 80)
  // Give up after 8s — dev mode without PyWebView
  setTimeout(() => { clearInterval(iv); console.warn('[JANSA] PyWebView bridge not detected after 8s — entering dev mode'); resolve(null) }, 8000)
})

const api = {
  /** Await bridge readiness, then call. Returns null if bridge unavailable. */
  call: async (method, ...args) => {
    const bridge = await _bridgeReady
    if (bridge && bridge[method]) {
      return await bridge[method](...args)
    }
    console.warn(`API not available: ${method}`)
    return null
  },
  /** Resolves to true if bridge connected, false if dev/timeout. */
  ready: _bridgeReady.then(b => !!b),
}

/* ── SVG Icons (inline, no deps) ────────────────────────────── */
function ExportTeamVersionButton() {
  const [exporting, setExporting] = useState(false)
  const [result, setResult] = useState(null)

  const handleExport = async () => {
    setExporting(true)
    setResult(null)
    try {
      const res = await api.call("export_team_version")
      if (res && res.success) {
        setResult({ ok: true })
        api.call("open_file_in_explorer", res.path)
      } else {
        setResult({ ok: false, msg: res?.error || "Export failed" })
      }
    } catch (e) {
      setResult({ ok: false, msg: String(e) })
    } finally {
      setExporting(false)
      setTimeout(() => setResult(null), 4000)
    }
  }

  return (
    <button onClick={handleExport} disabled={exporting} style={{
      background: S.accent, color: T.accent,
      border: '1px solid var(--accent-border)',
      borderRadius: 8, padding: '8px 16px',
      fontFamily: 'inherit', fontSize: 12, fontWeight: 500,
      cursor: exporting ? 'wait' : 'pointer',
      opacity: exporting ? 0.5 : 1,
      display: 'inline-flex', alignItems: 'center', gap: 6,
    }}>
      {exporting ? 'Export en cours...' : result ? (result.ok ? '✓ Exporté' : '✗ Erreur') : 'Tableau de Suivi VISA'}
    </button>
  )
}

function DrawerBackdrop({ visible, onClose }) {
  if (!visible) return null
  return <div onClick={onClose} style={{
    position: 'fixed', top: 0, left: 0, right: 0, bottom: 0,
    background: 'rgba(0,0,0,0.42)', zIndex: 999,
  }} />
}

function DocDetailDrawer({ visible, onClose, docs, title, loading, onExport, exporting }) {
  if (!visible) return null
  return (
    <div style={{
      position: 'fixed', top: 0, right: 0, bottom: 0, width: 560,
      background: '#111113', borderLeft: `1px solid ${T.glassBorder}`,
      zIndex: 1000, display: 'flex', flexDirection: 'column',
      boxShadow: '-8px 0 40px rgba(0,0,0,0.5)',
    }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '16px 20px', borderBottom: `1px solid ${T.glassBorder}` }}>
        <div>
          <div style={{ fontSize: 14, fontWeight: 600, color: T.text }}>{title || 'Documents'}</div>
          <div style={{ fontSize: 11, color: T.dim, marginTop: 2 }}>{loading ? 'Loading...' : `${(docs || []).length} documents`}</div>
        </div>
        <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
          {onExport && docs && docs.length > 0 && !loading && (
            <button onClick={onExport} disabled={exporting} style={{
              background: S.accent, color: T.accent,
              border: '1px solid var(--accent-border)',
              borderRadius: 8, padding: '6px 12px',
              fontFamily: 'inherit', fontSize: 11, fontWeight: 500,
              cursor: exporting ? 'wait' : 'pointer',
              opacity: exporting ? 0.5 : 1,
              display: 'inline-flex', alignItems: 'center', gap: 4,
              whiteSpace: 'nowrap',
            }}>
              {exporting ? 'Export...' : 'Export Excel'}
            </button>
          )}
          <button onClick={onClose} style={{ background: T.glass, border: `1px solid ${T.glassBorder}`, borderRadius: 8, width: 32, height: 32, cursor: 'pointer', color: T.muted, fontSize: 16 }}>x</button>
        </div>
      </div>
      <div style={{ flex: 1, overflowY: 'auto', padding: '8px 0' }}>
        {loading ? (
          <div style={{ padding: 40, textAlign: 'center', color: T.dim }}>Loading...</div>
        ) : (!docs || docs.length === 0) ? (
          <div style={{ padding: 40, textAlign: 'center', color: T.dim }}>No documents</div>
        ) : (
          <table style={{ width: '100%', borderCollapse: 'collapse' }}>
            <thead>
              <tr style={{ position: 'sticky', top: 0, background: '#111113', zIndex: 1 }}>
                {['Numero', 'Ind', 'Emetteur', 'Soumis', 'Echeance', 'Jours', 'Statut'].map(h => (
                  <th key={h} style={{ fontSize: 10, fontWeight: 500, color: T.dim, padding: 8, textAlign: 'left', borderBottom: `1px solid ${T.glassBorder}`, whiteSpace: 'nowrap', textTransform: 'uppercase' }}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {docs.map((d, i) => {
                const isLate = d.remaining_days != null && d.remaining_days < 0
                const isUrgent = d.remaining_days != null && d.remaining_days >= 0 && d.remaining_days <= 5
                return (
                  <tr key={i} style={{ background: i % 2 === 0 ? 'transparent' : 'rgba(255,255,255,.02)', borderBottom: `1px solid ${T.glassBorder}` }}>
                    <td style={{ fontSize: 12, color: T.text, padding: 8, fontWeight: 500 }}>{d.numero || '-'}</td>
                    <td style={{ fontSize: 12, color: T.muted, padding: 8 }}>{d.indice || '-'}</td>
                    <td style={{ fontSize: 12, color: T.muted, padding: 8 }}>{d.emetteur || '-'}</td>
                    <td style={{ fontSize: 11, color: T.dim, padding: 8, whiteSpace: 'nowrap' }}>{d.date_soumission || '-'}</td>
                    <td style={{ fontSize: 11, color: T.dim, padding: 8, whiteSpace: 'nowrap' }}>{d.date_limite || '-'}</td>
                    <td style={{ fontSize: 12, fontWeight: 600, padding: 8, color: isLate ? T.red : isUrgent ? T.amber : T.green }}>
                      {d.remaining_days != null ? (d.remaining_days < 0 ? `${Math.abs(d.remaining_days)}j retard` : `${d.remaining_days}j`) : '-'}
                    </td>
                    <td style={{ fontSize: 11, color: T.muted, padding: 8 }}>{d.status || 'OPEN'}</td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        )}
      </div>
    </div>
  )
}

const icons = {
  Overview: (
    <svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
      <rect x="1" y="1" width="6" height="6" rx="1"/>
      <rect x="9" y="1" width="6" height="6" rx="1"/>
      <rect x="1" y="9" width="6" height="6" rx="1"/>
      <rect x="9" y="9" width="6" height="6" rx="1"/>
    </svg>
  ),
  Runs: (
    <svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
      <path d="M2 2v12h12"/><path d="M5 10l3-4 3 3 3-5"/>
    </svg>
  ),
  Executer: (
    <svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
      <polygon points="5,2 14,8 5,14" fill="currentColor" stroke="none" opacity="0.7"/>
    </svg>
  ),
  Consultants: (
    <svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
      <circle cx="8" cy="5" r="3"/><path d="M2 14c0-3 2.7-5 6-5s6 2 6 5"/>
    </svg>
  ),
  Contractors: (
    <svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
      <rect x="2" y="6" width="12" height="8" rx="1"/><path d="M4 6V4a4 4 0 018 0v2"/>
    </svg>
  ),
  Discrepancies: (
    <svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
      <path d="M8 1l7 13H1L8 1z"/><path d="M8 6v3"/><circle cx="8" cy="11.5" r="0.5" fill="currentColor"/>
    </svg>
  ),
  Reports: (
    <svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
      <path d="M3 1h7l4 4v10a1 1 0 01-1 1H3a1 1 0 01-1-1V2a1 1 0 011-1z"/><path d="M10 1v4h4"/><path d="M5 8h6"/><path d="M5 11h4"/>
    </svg>
  ),
  Settings: (
    <svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
      <circle cx="8" cy="8" r="2.5"/><path d="M13.5 8a5.5 5.5 0 00-.4-1.4l1.2-1.2-1.1-1.1-1.2 1.2A5.5 5.5 0 0010.6 4.1V2.5h-1.6v1.6a5.5 5.5 0 00-1.4.4L6.4 3.3 5.3 4.4l1.2 1.2A5.5 5.5 0 005.1 7H3.5v1.6h1.6c.1.5.2 1 .4 1.4l-1.2 1.2 1.1 1.1 1.2-1.2c.4.2.9.3 1.4.4v1.6h1.6v-1.6c.5-.1 1-.2 1.4-.4l1.2 1.2 1.1-1.1-1.2-1.2c.2-.4.3-.9.4-1.4h1.6V8z"/>
    </svg>
  ),
}

const NAV_ITEMS = ['Overview', 'Executer', 'Runs', 'Consultants', 'Contractors', 'Discrepancies', 'Reports', 'Settings']

/* ── Focus Mode Toggle ──────────────────────────────────────── */
function FocusModeToggle({ focusMode, setFocusMode, staleDays, setStaleDays, focusStats }) {
  const [showPopover, setShowPopover] = useState(false)

  const totalFocused = focusStats?.focused ?? null
  const overdue = focusStats?.p1_overdue ?? 0

  return (
    <div style={{ position: 'relative' }}>
      <div style={{
        display: 'flex', alignItems: 'center', gap: 8,
        padding: '6px 14px', borderRadius: 10,
        background: focusMode ? 'linear-gradient(135deg, var(--accent-soft), rgba(94,92,230,0.12))' : T.bgElev2,
        border: `1px solid ${focusMode ? 'var(--accent-border)' : T.glassBorder}`,
        cursor: 'pointer',
        transition: 'background 0.2s, border-color 0.2s, box-shadow 0.2s',
        boxShadow: focusMode ? '0 0 0 4px rgba(10,132,255,0.08), 0 4px 12px -3px rgba(10,132,255,0.3)' : 'none',
      }} onClick={() => setFocusMode(m => !m)}>
        {/* Toggle pill */}
        <div style={{
          width: 32, height: 18, borderRadius: 9,
          background: focusMode ? T.accent : T.chip,
          position: 'relative', transition: 'background 0.2s', flexShrink: 0,
        }}>
          <div style={{
            position: 'absolute', top: 3, left: focusMode ? 17 : 3,
            width: 12, height: 12, borderRadius: '50%', background: '#fff',
            transition: 'left 0.2s', boxShadow: '0 1px 3px rgba(0,0,0,0.3)',
          }} />
        </div>
        <span style={{ fontSize: 12, fontWeight: 600, color: focusMode ? T.accent : T.muted, letterSpacing: '0.06em', textTransform: 'uppercase' }}>
          Mode Focus
        </span>
        {focusMode && totalFocused !== null && (
          <span style={{ fontSize: 12, fontWeight: 600, color: T.text, fontVariantNumeric: 'tabular-nums' }}>
            {totalFocused}
            {overdue > 0 && <span style={{ color: T.red, marginLeft: 4 }}>· {overdue} 🔴</span>}
          </span>
        )}
      </div>

      {/* Gear icon to open popover */}
      {focusMode && (
        <button
          onClick={e => { e.stopPropagation(); setShowPopover(p => !p) }}
          style={{
            position: 'absolute', top: -6, right: -6,
            width: 18, height: 18, borderRadius: '50%',
            background: T.accentSoft, border: `1px solid ${T.accent}`,
            color: T.accent, fontSize: 10, cursor: 'pointer', display: 'flex',
            alignItems: 'center', justifyContent: 'center', lineHeight: 1,
            fontFamily: 'inherit',
          }}
          title="Paramètres Focus"
        >⚙</button>
      )}

      {/* Popover */}
      {showPopover && focusMode && (
        <div style={{
          position: 'absolute', top: '110%', right: 0, zIndex: 100,
          ...glassCard,
          padding: 20, width: 280,
          border: `1px solid var(--accent-border)`,
          background: T.bgElev,
        }}>
          <div style={{ fontSize: 12, fontWeight: 600, color: T.text, marginBottom: 14, letterSpacing: '0.04em', textTransform: 'uppercase' }}>
            Seuil de péremption
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 16 }}>
            <input
              type="range" min={30} max={365} step={15}
              value={staleDays}
              onChange={e => setStaleDays(Number(e.target.value))}
              style={{ flex: 1, accentColor: T.accent }}
            />
            <span style={{ fontSize: 12, fontWeight: 600, color: T.accent, fontVariantNumeric: 'tabular-nums', minWidth: 50, textAlign: 'right' }}>
              {staleDays} j
            </span>
          </div>
          {focusStats && (
            <div style={{ borderTop: `1px solid ${T.glassBorder}`, paddingTop: 12 }}>
              <div style={{ fontSize: 11, color: T.muted, marginBottom: 8 }}>Documents exclus : {focusStats.excluded_total ?? '—'}</div>
              <div style={{ fontSize: 11, color: T.dim, marginBottom: 4 }}>· Résolus : {focusStats.resolved ?? 0}</div>
              <div style={{ fontSize: 11, color: T.dim, marginBottom: 4 }}>· Périmés (&gt;{staleDays}j) : {focusStats.stale ?? 0}</div>
              <div style={{ fontSize: 11, color: T.dim }}>· Total traçés : {focusStats.total_dernier ?? 0}</div>
            </div>
          )}
          <button
            onClick={() => setShowPopover(false)}
            style={{ marginTop: 14, fontSize: 11, color: T.accent, background: 'none', border: 'none', cursor: 'pointer', fontFamily: 'inherit', padding: 0 }}
          >
            Fermer
          </button>
        </div>
      )}
    </div>
  )
}

/* ── Priority Queue Panel ────────────────────────────────────── */
const PRIORITY_META = {
  1: { emoji: '🔴', label: 'EN RETARD', color: T.red, bg: S.bad, border: 'rgba(255,69,58,0.28)' },
  2: { emoji: '🟠', label: 'URGENT ≤5j', color: T.red, bg: S.bad, border: 'rgba(255,69,58,0.22)' },
  3: { emoji: '🟡', label: 'BIENTÔT ≤15j', color: T.amber, bg: S.warn, border: 'rgba(255,214,10,0.22)' },
  4: { emoji: '🟢', label: 'OK', color: T.green, bg: S.good, border: 'rgba(48,209,88,0.22)' },
  5: { emoji: '⚪', label: 'SANS DÉLAI', color: T.neutral, bg: S.neutral, border: T.glassBorder },
}

function PriorityQueuePanel({ queue, stats, setActivePage }) {
  const [expanded, setExpanded] = useState({ 1: true, 2: true, 3: false, 4: false, 5: false })

  if (!queue || queue.length === 0) {
    return (
      <div style={{ ...glassCard, padding: 20, marginBottom: 24, borderColor: 'rgba(48,209,88,0.24)', background: S.good }}>
        <div style={{ fontSize: 13, color: T.green }}>✓ Aucune action urgente — tous les documents sont sous contrôle</div>
      </div>
    )
  }

  // Group by priority
  const byPriority = {}
  for (let p = 1; p <= 5; p++) byPriority[p] = queue.filter(r => r.priority === p)

  const countBadge = (p) => {
    const meta = PRIORITY_META[p]
    const n = (stats ? stats[`p${p}_overdue`] || stats[`p${p}_urgent`] || stats[`p${p}_soon`] || stats[`p${p}_ok`] || stats[`p${p}_no_deadline`] : null) ?? byPriority[p].length
    return n
  }

  return (
    <div style={{ ...glassCard, padding: 0, marginBottom: 28, overflow: 'hidden' }}>
      {/* Panel header */}
      <div style={{ padding: '14px 20px', borderBottom: `1px solid ${T.glassBorder}`, display: 'flex', alignItems: 'center', gap: 10 }}>
        <div style={{ fontSize: 13, fontWeight: 600, color: T.text, letterSpacing: '0.02em' }}>
          File d'attente prioritaire
        </div>
        {stats && (
          <div style={{ display: 'flex', gap: 8, marginLeft: 8 }}>
            {[1,2,3].map(p => {
              const meta = PRIORITY_META[p]
              const n = byPriority[p].length
              if (!n) return null
              return (
                <span key={p} style={{ fontSize: 11, padding: '2px 8px', borderRadius: 100, background: meta.bg, border: `1px solid ${meta.border}`, color: meta.color, fontVariantNumeric: 'tabular-nums' }}>
                  {meta.emoji} {n}
                </span>
              )
            })}
          </div>
        )}
      </div>

      {/* Priority groups */}
      {[1, 2, 3, 4, 5].map(p => {
        const rows = byPriority[p]
        if (!rows || rows.length === 0) return null
        const meta = PRIORITY_META[p]
        const isOpen = expanded[p]

        return (
          <div key={p} style={{ borderBottom: `1px solid ${T.glassBorder}` }}>
            {/* Group header */}
            <button
              onClick={() => setExpanded(prev => ({ ...prev, [p]: !prev[p] }))}
              style={{
                display: 'flex', alignItems: 'center', gap: 10,
                width: '100%', padding: '10px 20px',
                background: isOpen ? meta.bg : 'transparent',
                border: 'none', cursor: 'pointer', textAlign: 'left', fontFamily: 'inherit',
                transition: 'background 0.15s',
              }}
            >
              <span style={{ fontSize: 12 }}>{meta.emoji}</span>
              <span style={{ fontSize: 11, fontWeight: 700, color: meta.color, letterSpacing: '0.06em', textTransform: 'uppercase' }}>
                {meta.label}
              </span>
              <span style={{ fontSize: 11, color: meta.color, fontVariantNumeric: 'tabular-nums', opacity: 0.8 }}>
                ({rows.length})
              </span>
              <span style={{ marginLeft: 'auto', fontSize: 10, color: T.dim }}>
                {isOpen ? '▲' : '▼'}
              </span>
            </button>

            {/* Rows table */}
            {isOpen && (
              <div style={{ padding: '0 0 4px 0' }}>
                {/* Table header */}
                <div style={{
                  display: 'grid', gridTemplateColumns: '2fr 1fr 1.5fr 1.5fr 1fr 1fr',
                  gap: 8, padding: '6px 20px',
                  fontSize: 10, color: T.dim, textTransform: 'uppercase', letterSpacing: '0.04em',
                  borderBottom: `1px solid ${T.glassBorder}`,
                }}>
                  <span>N° / Indice</span>
                  <span>Émetteur</span>
                  <span>Spécialité</span>
                  <span>Responsable</span>
                  <span style={{ textAlign: 'right' }}>Délai</span>
                  <span style={{ textAlign: 'right' }}>Date limite</span>
                </div>

                {rows.slice(0, 20).map((row, i) => (
                  <div
                    key={row.doc_id || i}
                    style={{
                      display: 'grid', gridTemplateColumns: '2fr 1fr 1.5fr 1.5fr 1fr 1fr',
                      gap: 8, padding: '7px 20px',
                      fontSize: 12, color: T.text,
                      background: i % 2 === 0 ? 'transparent' : 'rgba(255,255,255,0.015)',
                      transition: 'background 0.1s',
                      cursor: 'default',
                    }}
                    onMouseEnter={e => e.currentTarget.style.background = S.accent}
                    onMouseLeave={e => e.currentTarget.style.background = i % 2 === 0 ? 'transparent' : 'rgba(255,255,255,0.015)'}
                  >
                    <span style={{ fontVariantNumeric: 'tabular-nums', fontWeight: 500 }}>
                      {row.numero}
                      {row.indice && <span style={{ color: T.dim, marginLeft: 5, fontSize: 11 }}>{row.indice}</span>}
                    </span>
                    <span style={{ color: T.muted, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                      {row.emetteur}
                    </span>
                    <span style={{ color: T.muted, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                      {row.specialite || row.lot}
                    </span>
                    <span style={{
                      color: row.responsible === 'MOEX' ? T.accent :
                             row.responsible === 'CONTRACTOR' ? T.amber :
                             row.responsible === 'MULTIPLE_CONSULTANTS' ? '#c084fc' : T.text,
                      overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', fontSize: 11,
                    }}>
                      {row.responsible}
                    </span>
                    <span style={{
                      textAlign: 'right', fontVariantNumeric: 'tabular-nums', fontWeight: 600,
                      color: row.delta_days !== null && row.delta_days < 0 ? T.red :
                             row.delta_days <= 5 ? T.red : T.muted,
                    }}>
                      {row.delta_days !== null ? `${row.delta_days > 0 ? '+' : ''}${row.delta_days}j` : '—'}
                    </span>
                    <span style={{ textAlign: 'right', fontSize: 11, color: T.dim, fontVariantNumeric: 'tabular-nums' }}>
                      {row.date_limite || '—'}
                    </span>
                  </div>
                ))}
                {rows.length > 20 && (
                  <div style={{ padding: '8px 20px', fontSize: 11, color: T.dim }}>
                    +{rows.length - 20} de plus…
                  </div>
                )}
              </div>
            )}
          </div>
        )
      })}
    </div>
  )
}

/* ── KPI Card ───────────────────────────────────────────────── */
function KpiCard({ label, value, sub, color }) {
  const toneBg =
    color === T.accent ? S.accent :
    color === T.green ? S.good :
    color === T.amber ? S.warn :
    color === T.red ? S.bad :
    color === T.neutral ? S.neutral :
    'transparent'
  const isEmphasized = color && color !== T.text && color !== T.dim
  return (
    <div style={{
      ...glassCard,
      padding: '20px 24px',
      flex: '1 1 200px',
      minWidth: 180,
      position: 'relative',
      overflow: 'hidden',
      borderColor: isEmphasized ? color : T.glassBorder,
    }}>
      {isEmphasized && (
        <div style={{
          position: 'absolute', top: -70, right: -70, width: 160, height: 160,
          background: `radial-gradient(circle, ${toneBg}, transparent 64%)`,
          pointerEvents: 'none',
        }} />
      )}
      <div style={{ fontSize: 12, color: T.muted, marginBottom: 8, letterSpacing: '0.04em', textTransform: 'uppercase' }}>
        {label}
      </div>
      <div style={{ fontSize: 32, fontWeight: 650, color: color || T.text, fontVariantNumeric: 'tabular-nums', lineHeight: 1.1, position: 'relative' }}>
        {value}
      </div>
      {sub && (
        <div style={{ fontSize: 12, color: T.dim, marginTop: 6, fontVariantNumeric: 'tabular-nums' }}>
          {sub}
        </div>
      )}
    </div>
  )
}

/* ── Status Row ─────────────────────────────────────────────── */
function StatusRow({ label, value, ok }) {
  return (
    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '8px 0', borderBottom: `1px solid ${T.glassBorder}` }}>
      <span style={{ fontSize: 13, color: T.muted }}>{label}</span>
      <span style={{ fontSize: 13, color: ok ? T.green : T.amber, fontVariantNumeric: 'tabular-nums' }}>{value}</span>
    </div>
  )
}

/* ── Spinner ────────────────────────────────────────────────── */
function Spinner({ text }) {
  return (
    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100%', gap: 12 }}>
      <div style={{
        width: 24, height: 24, border: `2px solid ${T.glassBorder}`, borderTopColor: T.accent,
        borderRadius: '50%', animation: 'spin 0.8s linear infinite',
      }} />
      <div style={{ fontSize: 13, color: T.muted }}>{text || 'Loading...'}</div>
      <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>
    </div>
  )
}

/* ── Degraded Mode Banner ──────────────────────────────────── */
function DegradedBanner() {
  return (
    <div style={{ ...glassCard, padding: '12px 20px', marginBottom: 20, borderColor: 'rgba(255,214,10,0.25)', background: S.warn, display: 'flex', alignItems: 'center', gap: 10 }}>
      <div style={{ width: 8, height: 8, borderRadius: '50%', background: T.amber, boxShadow: `0 0 6px ${T.amber}`, flexShrink: 0 }} />
      <span style={{ fontSize: 13, color: T.amber }}>Limited data — GED provenance could not be verified for this run</span>
    </div>
  )
}

/* ── Mini Bar Chart (visa distribution) ────────────────────── */
function VisaBar({ data }) {
  if (!data || Object.keys(data).length === 0) return null
  const total = Object.values(data).reduce((a, b) => a + b, 0)
  if (total === 0) return null
  const colorMap = {
    VSO: VISA_TONE.VSO.color,
    VAO: VISA_TONE.VAO.color,
    REF: VISA_TONE.REF.color,
    'SAS REF': VISA_TONE['SAS REF'].color,
    Open: VISA_TONE.Open.color,
    HM: VISA_TONE.HM.color,
  }
  return (
    <div>
      <div style={{ display: 'flex', height: 8, borderRadius: 4, overflow: 'hidden', marginBottom: 10 }}>
        {Object.entries(data).map(([k, v]) => (
          <div key={k} style={{ width: `${(v / total) * 100}%`, background: colorMap[k] || T.dim, minWidth: v > 0 ? 3 : 0 }} />
        ))}
      </div>
      <div style={{ display: 'flex', gap: 16, flexWrap: 'wrap' }}>
        {Object.entries(data).map(([k, v]) => (
          <div key={k} style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
            <div style={{ width: 8, height: 8, borderRadius: 2, background: colorMap[k] || T.dim }} />
            <span style={{ fontSize: 12, color: T.muted }}>{k}</span>
            <span style={{ fontSize: 12, color: T.text, fontWeight: 500, fontVariantNumeric: 'tabular-nums' }}>{v}</span>
          </div>
        ))}
      </div>
    </div>
  )
}

/* ── Overview Page ──────────────────────────────────────────── */
function OverviewPage({ appState, setActivePage, focusMode, setFocusMode, staleDays, setStaleDays, onFocusStatsUpdate }) {
  const s = appState
  const [dash, setDash] = useState(null)
  const [loading, setLoading] = useState(true)

  // Reload dashboard whenever focus mode or stale threshold changes
  useEffect(() => {
    const load = async () => {
      setLoading(true)
      try {
        const data = await api.call("get_dashboard_data", focusMode, staleDays)
        if (data) {
          setDash(data)
          // Bubble focus stats up to App for sidebar badge
          if (onFocusStatsUpdate) {
            onFocusStatsUpdate(data.kpis?.focus_stats ?? null)
          }
        }
      } catch (e) {
        console.error('Dashboard load error:', e)
      } finally {
        setLoading(false)
      }
    }
    load()
  }, [focusMode, staleDays])

  if (loading) return <Spinner text="Loading dashboard data..." />

  const kpis = dash?.kpis || {}
  const monthly = dash?.monthly || []
  const isDegraded = kpis.degraded_mode
  const focusStats = kpis.focus_stats || null
  const priorityQueue = kpis.focus_priority_queue || []

  return (
    <div style={{
      padding: 32, overflowY: 'auto', height: '100%',
      // Subtle accent border when Focus Mode is ON
      borderLeft: focusMode ? `3px solid ${T.accent}` : '3px solid transparent',
      transition: 'border-left 0.3s',
    }}>
      {/* Degraded mode banner */}
      {isDegraded && <DegradedBanner />}

      {/* KPI Row */}
      <div style={{ display: 'flex', gap: 16, flexWrap: 'wrap', marginBottom: 28 }}>
        <KpiCard label="Total Runs" value={s.total_runs} sub="pipeline executions" color={T.accent} />
        <KpiCard label="Current Run" value={s.current_run != null ? `#${s.current_run}` : '\u2014'} sub={s.current_run_date ? formatDate(s.current_run_date) : 'no completed run'} color={T.green} />

        {focusMode && focusStats ? (
          // Focus Mode KPIs
          <>
            <KpiCard
              label="Actions"
              value={focusStats.focused ?? '\u2014'}
              sub={`sur ${focusStats.total_dernier ?? '?'} docs actifs`}
              color={T.accent}
            />
            <KpiCard
              label="En retard"
              value={focusStats.p1_overdue ?? 0}
              sub="dépassement délai"
              color={focusStats.p1_overdue > 0 ? T.red : T.green}
            />
            <KpiCard
              label="Urgent ≤5j"
              value={focusStats.p2_urgent ?? 0}
              sub="à traiter rapidement"
              color={focusStats.p2_urgent > 0 ? T.red : T.green}
            />
            <KpiCard
              label="Exclus (périmés)"
              value={focusStats.excluded_total ?? 0}
              sub={`dont ${focusStats.stale ?? 0} périmés, ${focusStats.resolved ?? 0} résolus`}
              color={T.dim}
            />
          </>
        ) : (
          // Normal Mode KPIs
          <>
            <KpiCard label="Documents" value={kpis.total_docs_current || '\u2014'} sub={kpis.total_docs_all_indices ? `${kpis.total_docs_all_indices} all indices` : 'dernier indice'} color={T.text} />
            <KpiCard label="Discrepancies" value={kpis.discrepancies_count || 0} sub="pending review" color={T.amber} />
          </>
        )}
      </div>

      {/* Priority Queue Panel — visible only in Focus Mode */}
      {focusMode && (
        <PriorityQueuePanel queue={priorityQueue} stats={focusStats} setActivePage={setActivePage} />
      )}

      {/* Visa Distribution + Stats Row */}
      <div style={{ display: 'flex', gap: 16, flexWrap: 'wrap', marginBottom: 28 }}>
        {/* Visa Distribution */}
        <div style={{ ...glassCard, padding: 24, flex: '2 1 400px', minWidth: 300 }}>
          <div style={{ fontSize: 14, fontWeight: 500, marginBottom: 16, color: T.text }}>Visa Distribution</div>
          {kpis.by_visa_global && Object.keys(kpis.by_visa_global).length > 0 ? (
            <VisaBar data={kpis.by_visa_global} />
          ) : (
            <div style={{ fontSize: 13, color: T.dim }}>No visa data available</div>
          )}
        </div>

        {/* Stats */}
        <div style={{ ...glassCard, padding: 24, flex: '1 1 200px', minWidth: 200 }}>
          <div style={{ fontSize: 14, fontWeight: 500, marginBottom: 16, color: T.text }}>Project Stats</div>
          <StatusRow label="Consultants" value={kpis.total_consultants || 0} ok={true} />
          <StatusRow label="Contractors" value={kpis.total_contractors || 0} ok={true} />
          <StatusRow label="Avg Days to Visa" value={kpis.avg_days_to_visa != null ? `${kpis.avg_days_to_visa}d` : '\u2014'} ok={kpis.avg_days_to_visa != null} />
          {kpis.docs_pending_sas != null && (
            <StatusRow label="SAS Pending" value={kpis.docs_pending_sas} ok={kpis.docs_pending_sas === 0} />
          )}
        </div>
      </div>

      {/* Monthly Timeseries */}
      {monthly.length > 0 && (
        <div style={{ ...glassCard, padding: 24, marginBottom: 28 }}>
          <div style={{ fontSize: 14, fontWeight: 500, marginBottom: 16, color: T.text }}>{focusMode ? 'Weekly Activity (Focus)' : 'Monthly Activity'}</div>
          <div style={{ display: 'flex', alignItems: 'flex-end', gap: 2, height: 100, paddingBottom: 20, position: 'relative' }}>
            {monthly.map((m, i) => {
              const maxTotal = Math.max(...monthly.map(x => x.total), 1)
              const h = (m.total / maxTotal) * 80
              return (
                <div key={i} style={{ flex: 1, display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 4 }}>
                  <div style={{ fontSize: 10, color: T.dim, fontVariantNumeric: 'tabular-nums' }}>{m.total}</div>
                  <div style={{
                    width: '100%', maxWidth: 32, height: h, borderRadius: '4px 4px 0 0',
                    background: 'linear-gradient(to top, var(--accent-soft), var(--good-soft))',
                  }} />
                  <div style={{ fontSize: focusMode ? 8 : 9, color: T.dim, transform: 'rotate(-45deg)', transformOrigin: 'center', whiteSpace: 'nowrap' }}>
                    {m.month.slice(5)}
                  </div>
                </div>
              )
            })}
          </div>
        </div>
      )}

      {/* System Status Card */}
      <div style={{ ...glassCard, padding: 24, marginBottom: 28 }}>
        <div style={{ fontSize: 14, fontWeight: 500, marginBottom: 16, color: T.text }}>System Status</div>
        <StatusRow label="Baseline (Run 0)" value={s.has_baseline ? 'Available' : 'Missing'} ok={s.has_baseline} />
        <StatusRow label="GED Export" value={s.ged_file_detected ? 'Detected' : 'Not found'} ok={!!s.ged_file_detected} />
        <StatusRow label="GrandFichier" value={s.gf_file_detected ? 'Detected' : 'Not found'} ok={!!s.gf_file_detected} />
        <StatusRow label="Mapping File" value={s.mapping_detected ? 'Detected' : 'Not found'} ok={!!s.mapping_detected} />
        <StatusRow label="Pipeline" value={s.pipeline_running ? 'Running' : 'Idle'} ok={!s.pipeline_running} />
      </div>

      {/* Warnings */}
      {((s.warnings && s.warnings.length > 0) || (kpis.warnings && kpis.warnings.length > 0)) && (
        <div style={{ ...glassCard, padding: 20, borderColor: 'rgba(255,214,10,0.22)', background: S.warn, marginBottom: 28 }}>
          <div style={{ fontSize: 13, fontWeight: 500, color: T.amber, marginBottom: 10 }}>Warnings</div>
          {[...(s.warnings || []), ...(kpis.warnings || [])].map((w, i) => (
            <div key={i} style={{ fontSize: 13, color: T.muted, marginBottom: 4, paddingLeft: 12, position: 'relative' }}>
              <span style={{ position: 'absolute', left: 0, color: T.amber }}>{'\u2022'}</span>
              {w}
            </div>
          ))}
        </div>
      )}

      {/* Quick Actions */}
      <div style={{ ...glassCard, padding: 24 }}>
        <div style={{ fontSize: 14, fontWeight: 500, marginBottom: 12, color: T.text }}>Quick Actions</div>
        <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap' }}>
          {[
            { label: 'Run Pipeline', target: 'Executer' },
            { label: 'View Runs', target: 'Runs' },
            { label: 'View Consultants', target: 'Consultants' },
            { label: 'View Contractors', target: 'Contractors' },
          ].map(action => (
            <button key={action.label} onClick={() => setActivePage(action.target)} style={{
              ...glassCard,
              padding: '10px 20px',
              fontSize: 13,
              color: T.muted,
              cursor: 'pointer',
              border: `1px solid ${T.glassBorder}`,
              background: T.glass,
              borderRadius: 8,
              transition: 'all 0.15s',
              fontFamily: 'inherit',
            }}
            onMouseEnter={e => { e.currentTarget.style.borderColor = T.accent; e.currentTarget.style.color = T.text }}
            onMouseLeave={e => { e.currentTarget.style.borderColor = T.glassBorder; e.currentTarget.style.color = T.muted }}
            >
              {action.label}
            </button>
          ))}
          <ExportTeamVersionButton />
        </div>
      </div>
    </div>
  )
}

/* ══════════════════════════════════════════════════════════════
   Runs Page — displays real run history from run_memory.db
   ══════════════════════════════════════════════════════════════ */
function RunsPage() {
  const [runs, setRuns] = useState([])
  const [loading, setLoading] = useState(true)
  const [exporting, setExporting] = useState(null) // run_number being exported

  useEffect(() => {
    const loadRuns = async () => {
      setLoading(true)
      try {
        const data = await api.call("get_all_runs")
        if (Array.isArray(data)) {
          setRuns(data)
        } else if (data && !data.error) {
          setRuns([])
        }
      } catch (e) {
        console.error('Runs load error:', e)
      } finally {
        setLoading(false)
      }
    }
    loadRuns()
  }, [])

  const handleExportZip = async (runNumber) => {
    setExporting(runNumber)
    const result = await api.call("export_run_bundle", runNumber)
    if (result && result.success) {
      await api.call("open_file_in_explorer", result.path)
    }
    setExporting(null)
  }

  if (loading) {
    return (
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100%', gap: 12 }}>
        <div style={{
          width: 24, height: 24, border: `2px solid ${T.glassBorder}`, borderTopColor: T.accent,
          borderRadius: '50%', animation: 'spin 0.8s linear infinite',
        }} />
        <div style={{ fontSize: 13, color: T.muted }}>Loading runs...</div>
        <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>
      </div>
    )
  }

  if (runs.length === 0) {
    return (
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100%', flexDirection: 'column', gap: 12 }}>
        <div style={{ fontSize: 18, color: T.muted, fontWeight: 500 }}>No runs found</div>
        <div style={{ fontSize: 13, color: T.dim }}>Run the pipeline to create your first run</div>
      </div>
    )
  }

  return (
    <div style={{ padding: 32, overflowY: 'auto', height: '100%' }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 24 }}>
        <div style={{ fontSize: 14, fontWeight: 500, color: T.text }}>{runs.length} run{runs.length !== 1 ? 's' : ''} registered</div>
      </div>

      <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
        {runs.map(run => {
          const isBaseline = run.is_baseline || run.run_number === 0
          const isCurrent = run.is_current
          const isStale = run.is_stale

          let statusColor = T.green
          let statusLabel = run.status || 'COMPLETED'
          if (isStale) { statusColor = T.amber; statusLabel = 'STALE' }
          if (run.status === 'FAILED') { statusColor = T.red; statusLabel = 'FAILED' }
          if (run.status === 'RUNNING') { statusColor = T.accent; statusLabel = 'RUNNING' }

          return (
            <div key={run.run_number} style={{
              ...glassCard,
              padding: '18px 24px',
              display: 'flex',
              alignItems: 'center',
              gap: 20,
              borderColor: isCurrent ? 'rgba(48,209,88,0.28)' : T.glassBorder,
            }}>
              {/* Run number badge */}
              <div style={{
                width: 48, height: 48, borderRadius: 10,
                background: isBaseline ? S.accent : isCurrent ? S.good : T.chip,
                display: 'flex', alignItems: 'center', justifyContent: 'center',
                fontSize: 18, fontWeight: 700, color: isBaseline ? T.accent : isCurrent ? T.green : T.muted,
                fontVariantNumeric: 'tabular-nums', flexShrink: 0,
              }}>
                {run.run_number}
              </div>

              {/* Info */}
              <div style={{ flex: 1, minWidth: 0 }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 4 }}>
                  <span style={{ fontSize: 14, fontWeight: 500, color: T.text }}>
                    {run.run_label || `Run ${run.run_number}`}
                  </span>
                  {isBaseline && (
                    <span style={{ fontSize: 10, padding: '2px 8px', borderRadius: 100, background: S.accent, color: T.accent, fontWeight: 600, letterSpacing: '0.05em' }}>
                      BASELINE
                    </span>
                  )}
                  {isCurrent && !isBaseline && (
                    <span style={{ fontSize: 10, padding: '2px 8px', borderRadius: 100, background: S.good, color: T.green, fontWeight: 600, letterSpacing: '0.05em' }}>
                      CURRENT
                    </span>
                  )}
                </div>
                <div style={{ fontSize: 12, color: T.dim, display: 'flex', gap: 16, flexWrap: 'wrap' }}>
                  {run.run_type && <span>Mode: {run.run_type}</span>}
                  {run.created_at && <span>Created: {formatDate(run.created_at)}</span>}
                  {run.completed_at && <span>Completed: {formatDate(run.completed_at)}</span>}
                  {run.core_version && <span>v{run.core_version}</span>}
                </div>
                {isStale && run.stale_reason && (
                  <div style={{ fontSize: 11, color: T.amber, marginTop: 4 }}>
                    Stale: {run.stale_reason}
                  </div>
                )}
              </div>

              {/* Status */}
              <div style={{
                fontSize: 11, fontWeight: 600, padding: '4px 12px', borderRadius: 100,
                color: statusColor,
                background: statusColor === T.green ? S.good :
                            statusColor === T.amber ? S.warn :
                            statusColor === T.red ? S.bad :
                            S.accent,
                letterSpacing: '0.05em', flexShrink: 0,
              }}>
                {statusLabel}
              </div>

              {/* Export button */}
              <button
                onClick={() => handleExportZip(run.run_number)}
                disabled={exporting === run.run_number}
                style={{
                  padding: '8px 14px', fontSize: 12, fontWeight: 500,
                  border: `1px solid ${T.glassBorder}`, borderRadius: 8,
                  background: T.glass, color: T.muted,
                  cursor: exporting === run.run_number ? 'wait' : 'pointer',
                  fontFamily: 'inherit', transition: 'all 0.15s', flexShrink: 0,
                  opacity: exporting === run.run_number ? 0.5 : 1,
                }}
                onMouseEnter={e => { if (exporting !== run.run_number) { e.currentTarget.style.borderColor = T.accent; e.currentTarget.style.color = T.text }}}
                onMouseLeave={e => { e.currentTarget.style.borderColor = T.glassBorder; e.currentTarget.style.color = T.muted }}
              >
                {exporting === run.run_number ? 'Exporting...' : 'Export ZIP'}
              </button>
            </div>
          )
        })}
      </div>
    </div>
  )
}

/* ══════════════════════════════════════════════════════════════
   Executer Page — pipeline execution with validation + progress
   ══════════════════════════════════════════════════════════════ */
const RUN_MODES = [
  { value: 'GED_GF', label: 'GED + GF', desc: 'Full run with GED export and GrandFichier' },
  { value: 'GED_ONLY', label: 'GED Only', desc: 'GED export only, GF inherited from latest run' },
  { value: 'GED_REPORT', label: 'GED + Report', desc: 'GED export with existing reports directory' },
]

function ExecuterPage({ appState }) {
  const [runMode, setRunMode] = useState('GED_GF')
  const [gedPath, setGedPath] = useState(appState?.ged_file_detected || '')
  const [gfPath, setGfPath] = useState(appState?.gf_file_detected || '')
  const [mappingPath, setMappingPath] = useState(appState?.mapping_detected || '')
  const [reportsDir, setReportsDir] = useState('')

  // Validation state
  const [validation, setValidation] = useState(null)
  const [validating, setValidating] = useState(false)

  // Pipeline execution state
  const [pipelineRunning, setPipelineRunning] = useState(false)
  const [pipelineMsg, setPipelineMsg] = useState('')
  const [pipelineDone, setPipelineDone] = useState(false)
  const [completedRun, setCompletedRun] = useState(null)
  const [pipelineError, setPipelineError] = useState(null)
  const [pipelineWarnings, setPipelineWarnings] = useState([])

  // Validate on mode/file change
  useEffect(() => {
    const doValidate = async () => {
      setValidating(true)
      const result = await api.call("validate_inputs", runMode,
        gedPath || null, gfPath || null, mappingPath || null, reportsDir || null)
      if (result) setValidation(result)
      setValidating(false)
    }
    doValidate()
  }, [runMode, gedPath, gfPath, mappingPath, reportsDir])

  // Poll pipeline status
  useEffect(() => {
    if (!pipelineRunning) return
    const interval = setInterval(async () => {
      const status = await api.call("get_pipeline_status")
      if (!status) return
      setPipelineMsg(status.message || '')
      setPipelineWarnings(status.warnings || [])
      if (!status.running) {
        setPipelineRunning(false)
        if (status.completed_run != null) {
          setPipelineDone(true)
          setCompletedRun(status.completed_run)
        }
        if (status.error) {
          setPipelineError(status.error)
        }
        clearInterval(interval)
      }
    }, 500)
    return () => clearInterval(interval)
  }, [pipelineRunning])

  const handleBrowse = async (type) => {
    const path = await api.call("select_file", type)
    if (path) {
      if (type === 'ged') setGedPath(path)
      else if (type === 'gf') setGfPath(path)
      else if (type === 'mapping') setMappingPath(path)
      else if (type === 'report_dir') setReportsDir(path)
    }
  }

  const handleRun = async () => {
    setPipelineError(null)
    setPipelineDone(false)
    setCompletedRun(null)
    setPipelineMsg('Starting...')
    setPipelineWarnings([])

    const result = await api.call("run_pipeline_async", runMode,
      gedPath || null, gfPath || null, mappingPath || null, reportsDir || null)
    if (!result) return

    if (result.started) {
      setPipelineRunning(true)
      if (result.warnings?.length) setPipelineWarnings(result.warnings)
    } else {
      setPipelineError((result.errors || []).join('; '))
    }
  }

  const fileName = (p) => p ? p.split(/[\\/]/).pop() : null

  const hasErrors = validation && !validation.valid && validation.errors?.length > 0
  const hasWarnings = validation && validation.warnings?.length > 0

  // Shared styles
  const inputRowStyle = {
    display: 'flex', alignItems: 'center', gap: 12, marginBottom: 14,
  }
  const inputLabelStyle = {
    fontSize: 12, color: T.muted, width: 90, flexShrink: 0, textTransform: 'uppercase',
    letterSpacing: '0.04em',
  }
  const inputPathStyle = {
    flex: 1, fontSize: 13, color: T.text, padding: '9px 14px',
    background: 'rgba(255,255,255,0.03)', border: `1px solid ${T.glassBorder}`,
    borderRadius: 8, fontFamily: 'inherit', overflow: 'hidden',
    textOverflow: 'ellipsis', whiteSpace: 'nowrap',
  }
  const browseBtn = {
    padding: '8px 14px', fontSize: 12, fontWeight: 500,
    border: `1px solid ${T.glassBorder}`, borderRadius: 8,
    background: T.glass, color: T.muted, cursor: 'pointer',
    fontFamily: 'inherit', transition: 'all 0.15s', flexShrink: 0,
  }

  return (
    <div style={{ padding: 32, overflowY: 'auto', height: '100%' }}>
      {/* Mode selector */}
      <div style={{ ...glassCard, padding: 24, marginBottom: 20 }}>
        <div style={{ fontSize: 14, fontWeight: 500, marginBottom: 16, color: T.text }}>Run Mode</div>
        <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap' }}>
          {RUN_MODES.map(m => (
            <button key={m.value} onClick={() => setRunMode(m.value)} style={{
              padding: '10px 20px', fontSize: 13, fontWeight: 500,
              border: `1px solid ${runMode === m.value ? T.accent : T.glassBorder}`,
              borderRadius: 8,
              background: runMode === m.value ? S.accent : T.glass,
              color: runMode === m.value ? T.accent : T.muted,
              cursor: 'pointer', fontFamily: 'inherit', transition: 'all 0.15s',
            }}>
              {m.label}
            </button>
          ))}
        </div>
        <div style={{ fontSize: 12, color: T.dim, marginTop: 10 }}>
          {RUN_MODES.find(m => m.value === runMode)?.desc}
        </div>
      </div>

      {/* File inputs */}
      <div style={{ ...glassCard, padding: 24, marginBottom: 20 }}>
        <div style={{ fontSize: 14, fontWeight: 500, marginBottom: 16, color: T.text }}>Input Files</div>

        {/* GED */}
        <div style={inputRowStyle}>
          <div style={inputLabelStyle}>GED</div>
          <div style={{
            ...inputPathStyle,
            borderColor: gedPath ? 'rgba(48,209,88,0.3)' : 'rgba(255,69,58,0.3)',
          }}>
            {fileName(gedPath) || <span style={{ color: T.dim }}>No file selected</span>}
          </div>
          <button onClick={() => handleBrowse('ged')} style={browseBtn}
            onMouseEnter={e => { e.currentTarget.style.borderColor = T.accent }}
            onMouseLeave={e => { e.currentTarget.style.borderColor = T.glassBorder }}
          >Parcourir</button>
        </div>

        {/* GF */}
        <div style={inputRowStyle}>
          <div style={inputLabelStyle}>GF</div>
          <div style={{
            ...inputPathStyle,
            borderColor: gfPath ? 'rgba(48,209,88,0.3)' : T.glassBorder,
            opacity: runMode === 'GED_ONLY' ? 0.4 : 1,
          }}>
            {fileName(gfPath) || <span style={{ color: T.dim }}>{runMode === 'GED_ONLY' ? 'Inherited from previous run' : 'No file selected'}</span>}
          </div>
          <button onClick={() => handleBrowse('gf')} style={{ ...browseBtn, opacity: runMode === 'GED_ONLY' ? 0.4 : 1 }}
            disabled={runMode === 'GED_ONLY'}
            onMouseEnter={e => { if (runMode !== 'GED_ONLY') e.currentTarget.style.borderColor = T.accent }}
            onMouseLeave={e => { e.currentTarget.style.borderColor = T.glassBorder }}
          >Parcourir</button>
        </div>

        {/* Mapping */}
        <div style={inputRowStyle}>
          <div style={inputLabelStyle}>Mapping</div>
          <div style={{
            ...inputPathStyle,
            borderColor: mappingPath ? 'rgba(48,209,88,0.3)' : 'rgba(255,69,58,0.3)',
          }}>
            {fileName(mappingPath) || <span style={{ color: T.dim }}>No file selected</span>}
          </div>
          <button onClick={() => handleBrowse('mapping')} style={browseBtn}
            onMouseEnter={e => { e.currentTarget.style.borderColor = T.accent }}
            onMouseLeave={e => { e.currentTarget.style.borderColor = T.glassBorder }}
          >Parcourir</button>
        </div>

        {/* Reports dir (only for GED_REPORT) */}
        {runMode === 'GED_REPORT' && (
          <div style={inputRowStyle}>
            <div style={inputLabelStyle}>Reports</div>
            <div style={{
              ...inputPathStyle,
              borderColor: reportsDir ? 'rgba(48,209,88,0.3)' : 'rgba(255,69,58,0.3)',
            }}>
              {reportsDir || <span style={{ color: T.dim }}>No directory selected</span>}
            </div>
            <button onClick={() => handleBrowse('report_dir')} style={browseBtn}
              onMouseEnter={e => { e.currentTarget.style.borderColor = T.accent }}
              onMouseLeave={e => { e.currentTarget.style.borderColor = T.glassBorder }}
            >Parcourir</button>
          </div>
        )}
      </div>

      {/* Validation messages */}
      {validation && hasErrors && (
        <div style={{ ...glassCard, padding: 16, marginBottom: 16, borderColor: 'rgba(255,69,58,0.25)', background: S.bad }}>
          <div style={{ fontSize: 12, fontWeight: 600, color: T.red, marginBottom: 8, letterSpacing: '0.04em' }}>VALIDATION ERRORS</div>
          {validation.errors.map((e, i) => (
            <div key={i} style={{ fontSize: 13, color: T.red, marginBottom: 3, paddingLeft: 12, position: 'relative' }}>
              <span style={{ position: 'absolute', left: 0 }}>{'\u2022'}</span>{e}
            </div>
          ))}
        </div>
      )}
      {validation && hasWarnings && (
        <div style={{ ...glassCard, padding: 16, marginBottom: 16, borderColor: 'rgba(255,214,10,0.22)', background: S.warn }}>
          <div style={{ fontSize: 12, fontWeight: 600, color: T.amber, marginBottom: 8, letterSpacing: '0.04em' }}>WARNINGS</div>
          {validation.warnings.map((w, i) => (
            <div key={i} style={{ fontSize: 13, color: T.amber, marginBottom: 3, paddingLeft: 12, position: 'relative' }}>
              <span style={{ position: 'absolute', left: 0 }}>{'\u2022'}</span>{w}
            </div>
          ))}
        </div>
      )}

      {/* Info box for GED_ONLY */}
      {runMode === 'GED_ONLY' && !hasErrors && (
        <div style={{ ...glassCard, padding: 16, marginBottom: 16, borderColor: 'var(--accent-border)', background: S.accent }}>
          <div style={{ fontSize: 13, color: T.accent }}>
            GF will be inherited from the latest completed run.
          </div>
        </div>
      )}

      {/* Run button + progress */}
      <div style={{ ...glassCard, padding: 24 }}>
        {!pipelineRunning && !pipelineDone && (
          <button
            onClick={handleRun}
            disabled={hasErrors || validating || pipelineRunning}
            style={{
              padding: '12px 32px', fontSize: 14, fontWeight: 600,
              border: 'none', borderRadius: 10,
              background: hasErrors ? T.chip : 'linear-gradient(135deg, var(--accent), #5E5CE6)',
              color: hasErrors ? T.dim : '#fff',
              cursor: hasErrors ? 'not-allowed' : 'pointer',
              fontFamily: 'inherit', transition: 'all 0.2s',
              letterSpacing: '0.03em',
              boxShadow: hasErrors ? 'none' : '0 4px 20px rgba(10,132,255,0.3)',
            }}
          >
            Lancer le pipeline
          </button>
        )}

        {/* Progress display */}
        {(pipelineRunning || pipelineMsg) && !pipelineDone && !pipelineError && (
          <div style={{ marginTop: pipelineRunning ? 0 : 20, display: 'flex', alignItems: 'center', gap: 14 }}>
            {pipelineRunning && (
              <div style={{
                width: 20, height: 20, border: `2px solid ${T.glassBorder}`, borderTopColor: T.accent,
                borderRadius: '50%', animation: 'spin 0.8s linear infinite', flexShrink: 0,
              }} />
            )}
            <div style={{ fontSize: 13, color: T.muted }}>{pipelineMsg}</div>
            <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>
          </div>
        )}

        {/* Success */}
        {pipelineDone && completedRun != null && (
          <div style={{ marginTop: 0 }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 12 }}>
              <div style={{ width: 8, height: 8, borderRadius: '50%', background: T.green, boxShadow: `0 0 8px ${T.green}` }} />
              <span style={{ fontSize: 14, fontWeight: 500, color: T.green }}>{pipelineMsg || `Run ${completedRun} completed`}</span>
            </div>
            {pipelineWarnings.length > 0 && (
              <div style={{ marginBottom: 12 }}>
                {pipelineWarnings.map((w, i) => (
                  <div key={i} style={{ fontSize: 12, color: T.amber, marginBottom: 2 }}>{w}</div>
                ))}
              </div>
            )}
            <button onClick={() => { setPipelineDone(false); setPipelineMsg(''); setCompletedRun(null) }} style={{
              padding: '8px 20px', fontSize: 12, fontWeight: 500,
              border: `1px solid rgba(48,209,88,0.3)`, borderRadius: 8,
              background: S.good, color: T.green,
              cursor: 'pointer', fontFamily: 'inherit',
            }}>
              New run
            </button>
          </div>
        )}

        {/* Error */}
        {pipelineError && (
          <div style={{ marginTop: 0 }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 12 }}>
              <div style={{ width: 8, height: 8, borderRadius: '50%', background: T.red, boxShadow: `0 0 8px ${T.red}` }} />
              <span style={{ fontSize: 14, fontWeight: 500, color: T.red }}>Pipeline failed</span>
            </div>
            <div style={{ fontSize: 13, color: T.red, background: S.bad, padding: 14, borderRadius: 8, marginBottom: 12 }}>
              {pipelineError}
            </div>
            <button onClick={() => { setPipelineError(null); setPipelineMsg('') }} style={{
              padding: '8px 20px', fontSize: 12, fontWeight: 500,
              border: `1px solid rgba(255,69,58,0.3)`, borderRadius: 8,
              background: S.bad, color: T.red,
              cursor: 'pointer', fontFamily: 'inherit',
            }}>
              Try again
            </button>
          </div>
        )}
      </div>
    </div>
  )
}

/* ══════════════════════════════════════════════════════════════
   Consultant Fiche — wrapper that fetches data and renders
   the Apple/Tesla dark ConsultantFiche component
   ══════════════════════════════════════════════════════════════ */
function ConsultantFicheView({ consultantName, onBack, focusMode, staleDays }) {
  const [data, setData] = useState(null)
  const [error, setError] = useState(null)
  const [loading, setLoading] = useState(true)
  const [drawerVisible, setDrawerVisible] = useState(false)
  const [drawerDocs, setDrawerDocs] = useState([])
  const [drawerTitle, setDrawerTitle] = useState("")
  const [drawerLoading, setDrawerLoading] = useState(false)
  const [drawerFilterKey, setDrawerFilterKey] = useState("")
  const [drawerExporting, setDrawerExporting] = useState(false)

  useEffect(() => {
    let cancelled = false
    api.call("get_consultant_fiche", consultantName, focusMode, staleDays)
      .then((d) => {
        if (cancelled) return
        if (d && d.error) {
          setError(d.error)
        } else {
          setData(d)
        }
      })
      .catch((e) => {
        if (!cancelled) setError(String(e))
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })
    return () => { cancelled = true }
  }, [consultantName, focusMode, staleDays])

  const handleCellClick = async (filterKey) => {
    setDrawerVisible(true)
    setDrawerLoading(true)
    setDrawerTitle(filterKey)
    setDrawerDocs([])
    setDrawerFilterKey(filterKey)
    try {
      const res = await api.call("get_doc_details", consultantName, filterKey, null, focusMode, staleDays)
      if (res && res.docs) {
        setDrawerDocs(res.docs)
        setDrawerTitle(`${filterKey} - ${res.count} docs`)
      } else if (res && res.error) {
        setDrawerTitle(`Error: ${res.error}`)
      }
    } catch (e) {
      setDrawerTitle(`Error: ${e}`)
    } finally {
      setDrawerLoading(false)
    }
  }

  const handleExportDrilldown = async () => {
    setDrawerExporting(true)
    try {
      const res = await api.call("export_drilldown_xlsx", consultantName, drawerFilterKey, null, focusMode, staleDays)
      if (res && res.success) {
        api.call("open_file_in_explorer", res.path)
      } else {
        console.error("Export failed:", res?.error)
      }
    } catch (e) {
      console.error("Export error:", e)
    } finally {
      setDrawerExporting(false)
    }
  }

  if (loading) {
    return <Spinner text={`Loading fiche for ${consultantName}...`} />
  }

  if (error) {
    return (
      <div style={{ padding: 40, color: "#FF453A", fontFamily: "SF Pro Display" }}>
        Error loading fiche: {error}
        <button onClick={onBack} style={{ marginLeft: 12, background: 'rgba(255,255,255,.06)', color: '#F5F5F7', border: '1px solid rgba(255,255,255,.14)', borderRadius: 8, padding: '6px 12px', fontFamily: 'SF Pro Text', fontSize: 13, cursor: 'pointer' }}>Back</button>
      </div>
    )
  }
  if (!data) {
    return (
      <div style={{ padding: 40, color: "#A1A1A6" }}>Loading fiche…</div>
    )
  }
  if (data.degraded_mode) {
    return (
      <div style={{ background: "#0A0A0B", minHeight: "100vh", overflowY: 'auto', height: '100%' }}>
        <div style={{ padding: "12px 56px", background: "rgba(255,214,10,.12)",
                      borderBottom: "1px solid rgba(255,214,10,.3)",
                      color: "#FFD60A", fontFamily: "SF Pro Text", fontSize: 13 }}>
          Mode dégradé — {(data.warnings || []).join(" · ") || "GED source unavailable"}
        </div>
        <button onClick={onBack} style={{
          position: "fixed", top: 16, left: 216, zIndex: 10,
          background: "rgba(255,255,255,.06)", color: "#F5F5F7",
          border: "1px solid rgba(255,255,255,.14)",
          borderRadius: 8, padding: "6px 12px",
          fontFamily: "SF Pro Text", fontSize: 13, cursor: "pointer",
        }}>← Back</button>
        <ExportTeamVersionButton />
        <ConsultantFicheComponent data={data} lang="fr" onCellClick={handleCellClick} />
        <DrawerBackdrop visible={drawerVisible} onClose={() => setDrawerVisible(false)} />
        <DocDetailDrawer visible={drawerVisible} onClose={() => setDrawerVisible(false)} docs={drawerDocs} title={drawerTitle} loading={drawerLoading} onExport={handleExportDrilldown} exporting={drawerExporting} />
      </div>
    )
  }

  return (
    <div style={{ background: "#0A0A0B", minHeight: "100vh", overflowY: 'auto', height: '100%' }}>
      <button onClick={onBack} style={{
        position: "fixed", top: 16, left: 216, zIndex: 10,
        background: "rgba(255,255,255,.06)", color: "#F5F5F7",
        border: "1px solid rgba(255,255,255,.14)",
        borderRadius: 8, padding: "6px 12px",
        fontFamily: "SF Pro Text", fontSize: 13, cursor: "pointer",
      }}>← Back</button>
      <div style={{ position: "fixed", top: 16, left: 288, zIndex: 10 }}>
        <ExportTeamVersionButton />
      </div>
      <ConsultantFicheComponent data={data} lang="fr" onCellClick={handleCellClick} />
      <DrawerBackdrop visible={drawerVisible} onClose={() => setDrawerVisible(false)} />
      <DocDetailDrawer visible={drawerVisible} onClose={() => setDrawerVisible(false)} docs={drawerDocs} title={drawerTitle} loading={drawerLoading} onExport={handleExportDrilldown} exporting={drawerExporting} />
    </div>
  )
}

/* ══════════════════════════════════════════════════════════════
   Consultants Page — real data from get_consultant_list
   ══════════════════════════════════════════════════════════════ */
function ConsultantsPage({ focusMode, staleDays }) {
  const [consultants, setConsultants] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [selectedConsultant, setSelectedConsultant] = useState(null)

  useEffect(() => {
    const load = async () => {
      setLoading(true)
      setError(null)
      try {
        const data = await api.call("get_consultant_list", focusMode, staleDays)
        if (Array.isArray(data)) {
          setConsultants(data)
        } else if (data && data.error) {
          setError(data.error)
        } else {
          setConsultants([])
        }
      } catch (e) {
        setError(e.message || "Failed to load consultants")
      } finally {
        setLoading(false)
      }
    }
    load()
  }, [focusMode, staleDays])

  // If a consultant is selected, show their fiche
  if (selectedConsultant) {
    return <ConsultantFicheView key={selectedConsultant} consultantName={selectedConsultant} onBack={() => setSelectedConsultant(null)} focusMode={focusMode} staleDays={staleDays} />
  }

  if (loading) return <Spinner text="Loading consultants..." />

  if (error) {
    return (
      <div style={{ padding: 32 }}>
        <div style={{ ...glassCard, padding: 20, borderColor: 'rgba(255,69,58,0.25)', background: S.bad }}>
          <div style={{ fontSize: 13, color: T.red }}>{error}</div>
        </div>
      </div>
    )
  }

  if (consultants.length === 0) {
    return (
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100%', flexDirection: 'column', gap: 12 }}>
        <div style={{ fontSize: 18, color: T.muted, fontWeight: 500 }}>No consultant data</div>
        <div style={{ fontSize: 13, color: T.dim }}>Run a pipeline with GED data to see consultant performance</div>
      </div>
    )
  }

  return (
    <div style={{ padding: 32, overflowY: 'auto', height: '100%' }}>
      <div style={{ fontSize: 14, fontWeight: 500, color: T.text, marginBottom: 20 }}>
        {consultants.length} consultant{consultants.length !== 1 ? 's' : ''} active
      </div>

      {/* Header row */}
      <div style={{
        display: 'grid',
        gridTemplateColumns: '2fr repeat(8, 1fr)',
        gap: 8,
        padding: '10px 20px',
        fontSize: 11,
        color: T.dim,
        textTransform: 'uppercase',
        letterSpacing: '0.04em',
        borderBottom: `1px solid ${T.glassBorder}`,
        marginBottom: 4,
      }}>
        <span>Name</span>
        <span style={{ textAlign: 'right' }}>Called</span>
        <span style={{ textAlign: 'right' }}>Answered</span>
        <span style={{ textAlign: 'right' }}>Rate</span>
        <span style={{ textAlign: 'right' }}>Avg Days</span>
        <span style={{ textAlign: 'right' }}>VSO</span>
        <span style={{ textAlign: 'right' }}>VAO</span>
        <span style={{ textAlign: 'right' }}>REF</span>
        <span style={{ textAlign: 'right' }}>Open</span>
      </div>

      {/* Data rows */}
      {consultants.map((c, i) => {
        const rateColor = c.response_rate >= 0.8 ? T.green : c.response_rate >= 0.5 ? T.amber : T.red
        const isSas = c.is_sas || c.name === 'MOEX SAS'
        return (
          <div key={i} onClick={() => setSelectedConsultant(c.name)} style={{
            ...glassCard,
            display: 'grid',
            gridTemplateColumns: '2fr repeat(8, 1fr)',
            gap: 8,
            padding: '14px 20px',
            marginBottom: 4,
            alignItems: 'center',
            fontSize: 13,
            cursor: 'pointer',
            transition: 'border-color 0.15s',
            borderColor: isSas ? 'rgba(255,214,10,0.15)' : T.glassBorder,
          }}
          onMouseEnter={e => { e.currentTarget.style.borderColor = isSas ? 'rgba(255,214,10,0.35)' : 'var(--accent-border)' }}
          onMouseLeave={e => { e.currentTarget.style.borderColor = isSas ? 'rgba(255,214,10,0.15)' : T.glassBorder }}
          >
            <span style={{ color: isSas ? '#FFD60A' : T.accent, fontWeight: 500, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{isSas ? `◆ ${c.name}` : c.name}</span>
            <span style={{ textAlign: 'right', color: T.muted, fontVariantNumeric: 'tabular-nums' }}>{c.docs_called}</span>
            <span style={{ textAlign: 'right', color: T.muted, fontVariantNumeric: 'tabular-nums' }}>{c.docs_answered}</span>
            <span style={{ textAlign: 'right', color: rateColor, fontWeight: 500, fontVariantNumeric: 'tabular-nums' }}>
              {(c.response_rate * 100).toFixed(0)}%
            </span>
            <span style={{ textAlign: 'right', color: T.muted, fontVariantNumeric: 'tabular-nums' }}>
              {c.avg_response_days != null ? `${c.avg_response_days}d` : '\u2014'}
            </span>
            <span style={{ textAlign: 'right', color: T.green, fontVariantNumeric: 'tabular-nums' }}>{c.vso}</span>
            <span style={{ textAlign: 'right', color: T.amber, fontVariantNumeric: 'tabular-nums' }}>{c.vao}</span>
            <span style={{ textAlign: 'right', color: T.red, fontVariantNumeric: 'tabular-nums' }}>{c.ref}</span>
            <span style={{ textAlign: 'right', color: T.amber, fontVariantNumeric: 'tabular-nums' }}>{c.open}</span>
          </div>
        )
      })}
    </div>
  )
}

/* ══════════════════════════════════════════════════════════════
   Contractor Fiche — detail view for one contractor
   ══════════════════════════════════════════════════════════════ */
function ContractorFiche({ contractorCode, onBack, focusMode, staleDays }) {
  const [fiche, setFiche] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  useEffect(() => {
    const load = async () => {
      setLoading(true)
      setError(null)
      try {
        const data = await api.call("get_contractor_fiche", contractorCode, focusMode, staleDays)
        if (data && data.error) {
          setError(data.error)
        } else if (data) {
          setFiche(data)
        } else {
          setError("No data returned")
        }
      } catch (e) {
        setError(e.message || "Failed to load fiche")
      } finally {
        setLoading(false)
      }
    }
    load()
  }, [contractorCode, focusMode, staleDays])

  if (loading) return <Spinner text={`Loading fiche for ${contractorCode}...`} />

  if (error) {
    return (
      <div style={{ padding: 32 }}>
        <button onClick={onBack} style={{ fontSize: 11, color: T.accent, cursor: 'pointer', background: 'none', border: 'none', fontFamily: 'inherit', marginBottom: 16 }}>{'\u2190'} Back to list</button>
        <div style={{ ...glassCard, padding: 20, borderColor: 'rgba(255,69,58,0.25)', background: S.bad }}>
          <div style={{ fontSize: 13, color: T.red }}>{error}</div>
        </div>
      </div>
    )
  }

  if (!fiche) return null

  const q = fiche.block4_quality || {}
  const visaPillStyle = (status) => {
    const tone = VISA_TONE[status] || { color: T.muted, bg: S.neutral }
    return {
      display: 'inline-block', fontSize: 10, fontWeight: 600, padding: '2px 8px', borderRadius: 100,
      letterSpacing: '0.04em', color: tone.color, background: tone.bg,
    }
  }

  return (
    <div style={{ padding: 32, overflowY: 'auto', height: '100%' }}>
      {/* Back button */}
      <button onClick={onBack} style={{ fontSize: 11, color: T.accent, cursor: 'pointer', background: 'none', border: 'none', fontFamily: 'inherit', marginBottom: 16, padding: 0 }}>
        {'\u2190'} Back to contractors
      </button>
      <div style={{ marginBottom: 16 }}>
        <ExportTeamVersionButton />
      </div>

      {/* Title + metadata */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 16, marginBottom: 8 }}>
        <div style={{ fontSize: 20, fontWeight: 600, color: T.text }}>{fiche.contractor_name}</div>
        {fiche.lots && fiche.lots.length > 0 && (
          <div style={{ fontSize: 12, color: T.dim }}>Lots: {fiche.lots.join(', ')}</div>
        )}
      </div>
      {fiche.gf_sheets && fiche.gf_sheets.length > 0 && (
        <div style={{ fontSize: 11, color: T.dim, marginBottom: 20 }}>GF sheets: {fiche.gf_sheets.join(', ')}</div>
      )}

      {/* Degraded banner */}
      {fiche.degraded_mode && <DegradedBanner />}

      {/* Warnings */}
      {fiche.warnings && fiche.warnings.length > 0 && (
        <div style={{ ...glassCard, padding: 16, marginBottom: 16, borderColor: 'rgba(255,214,10,0.22)', background: S.warn }}>
          {fiche.warnings.map((w, i) => <div key={i} style={{ fontSize: 12, color: T.amber }}>{w}</div>)}
        </div>
      )}

      {/* Header KPIs */}
      <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap', marginBottom: 24 }}>
        <KpiCard label="Submitted" value={fiche.total_submitted} />
        <KpiCard label="Current" value={fiche.total_current} />
        <KpiCard label="SAS REF Rate" value={Math.round((q.sas_refusal_rate || 0) * 100) + '%'} color={q.sas_refusal_rate > 0.1 ? T.red : T.green} />
        <KpiCard label="Avg Delay" value={q.avg_days_to_visa != null ? q.avg_days_to_visa + 'd' : '\u2014'} />
      </div>

      {/* Block 4: Quality metrics cards */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 12, marginBottom: 24 }}>
        <div style={{ ...glassCard, padding: 20 }}>
          <div style={{ fontSize: 11, color: T.dim, textTransform: 'uppercase', letterSpacing: '0.04em', marginBottom: 8 }}>SAS Refusal Rate</div>
          <div style={{ fontSize: 28, fontWeight: 600, color: q.sas_refusal_rate > 0.1 ? T.red : T.green, fontVariantNumeric: 'tabular-nums' }}>
            {Math.round((q.sas_refusal_rate || 0) * 100)}%
          </div>
          <div style={{ fontSize: 11, color: T.dim, marginTop: 4 }}>{q.docs_a_reprendre || 0} docs to rework</div>
        </div>
        <div style={{ ...glassCard, padding: 20 }}>
          <div style={{ fontSize: 11, color: T.dim, textTransform: 'uppercase', letterSpacing: '0.04em', marginBottom: 8 }}>Avg Revisions</div>
          <div style={{ fontSize: 28, fontWeight: 600, color: q.avg_revision_cycles > 2 ? T.amber : T.text, fontVariantNumeric: 'tabular-nums' }}>
            {q.avg_revision_cycles || '\u2014'}
          </div>
          <div style={{ fontSize: 11, color: T.dim, marginTop: 4 }}>indices per document</div>
        </div>
        <div style={{ ...glassCard, padding: 20 }}>
          <div style={{ fontSize: 11, color: T.dim, textTransform: 'uppercase', letterSpacing: '0.04em', marginBottom: 8 }}>Avg Days to Visa</div>
          <div style={{ fontSize: 28, fontWeight: 600, color: T.text, fontVariantNumeric: 'tabular-nums' }}>
            {q.avg_days_to_visa != null ? q.avg_days_to_visa : '\u2014'}
          </div>
          <div style={{ fontSize: 11, color: T.dim, marginTop: 4 }}>{q.docs_pending_consultant || 0} pending</div>
        </div>
      </div>

      {/* Block 2: VISA chart */}
      {fiche.block2_visa_chart && fiche.block2_visa_chart.length > 0 && (
        <div style={{ ...glassCard, padding: 24, marginBottom: 24 }}>
          <div style={{ fontSize: 14, fontWeight: 500, marginBottom: 16, color: T.text }}>Monthly VISA Distribution</div>
          <div style={{ display: 'flex', alignItems: 'flex-end', gap: 3, height: 120, paddingBottom: 24, position: 'relative' }}>
            {fiche.block2_visa_chart.map((m, i) => {
              const maxT = Math.max(...fiche.block2_visa_chart.map(x => x.total), 1)
              const h = (m.total / maxT) * 90
              const t = Math.max(m.total, 1)
              return (
                <div key={i} style={{ flex: 1, display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 4 }}>
                  <div style={{ fontSize: 9, color: T.dim, fontVariantNumeric: 'tabular-nums' }}>{m.total}</div>
                  <div style={{ width: '100%', maxWidth: 28, height: Math.max(h, 2), borderRadius: '3px 3px 0 0', overflow: 'hidden', display: 'flex', flexDirection: 'column' }}>
                    {m.vso > 0 && <div style={{ height: `${(m.vso / t) * 100}%`, background: T.green }} />}
                    {m.vao > 0 && <div style={{ height: `${(m.vao / t) * 100}%`, background: T.amber }} />}
                    {m.ref > 0 && <div style={{ height: `${(m.ref / t) * 100}%`, background: T.red }} />}
                    {m.sas_ref > 0 && <div style={{ height: `${(m.sas_ref / t) * 100}%`, background: T.red }} />}
                    {m.open > 0 && <div style={{ height: `${(m.open / t) * 100}%`, background: T.accent }} />}
                  </div>
                  <div style={{ fontSize: 8, color: T.dim, transform: 'rotate(-45deg)', transformOrigin: 'center', whiteSpace: 'nowrap' }}>
                    {m.month.slice(5)}
                  </div>
                </div>
              )
            })}
          </div>
          {/* Legend */}
          <div style={{ display: 'flex', gap: 16, flexWrap: 'wrap', marginTop: 8 }}>
            {[['VSO', T.green], ['VAO', T.amber], ['REF', T.red], ['SAS REF', T.red], ['Open', T.accent]].map(([label, color]) => (
              <div key={label} style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                <div style={{ width: 8, height: 8, borderRadius: 2, background: color }} />
                <span style={{ fontSize: 11, color: T.muted }}>{label}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Block 3: Document table */}
      {fiche.block3_document_table && fiche.block3_document_table.length > 0 && (
        <div style={{ ...glassCard, padding: 24 }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 16 }}>
            <div style={{ fontSize: 14, fontWeight: 500, color: T.text }}>Documents ({fiche.block3_document_table.length})</div>
            <button style={{ background: T.accent, color: '#fff', borderRadius: 10, padding: '8px 18px', fontSize: 12, fontWeight: 600, border: 'none', cursor: 'pointer', fontFamily: 'inherit', opacity: 0.7 }} title="Coming soon">
              Export .xlsx
            </button>
          </div>

          {/* Table header */}
          <div style={{
            display: 'grid', gridTemplateColumns: '2fr 0.5fr 3fr 0.8fr 0.8fr 1fr 1fr 0.8fr',
            gap: 6, padding: '8px 12px', fontSize: 11, color: T.dim, textTransform: 'uppercase', letterSpacing: '0.04em',
            borderBottom: `1px solid ${T.glassBorder}`, marginBottom: 4,
          }}>
            <span>Numero</span>
            <span>Ind</span>
            <span>Titre</span>
            <span>SAS</span>
            <span>VISA</span>
            <span>Submitted</span>
            <span>Visa Date</span>
            <span>Status</span>
          </div>

          {/* Table body — scrollable if many docs */}
          <div style={{ maxHeight: 400, overflowY: 'auto' }}>
            {fiche.block3_document_table.map((doc, i) => (
              <div key={i} style={{
                display: 'grid', gridTemplateColumns: '2fr 0.5fr 3fr 0.8fr 0.8fr 1fr 1fr 0.8fr',
                gap: 6, padding: '8px 12px', fontSize: 12, alignItems: 'center',
                background: i % 2 === 0 ? 'transparent' : 'rgba(255,255,255,0.02)',
                borderRadius: 4,
              }}>
                <span style={{ color: T.text, fontWeight: 500, fontVariantNumeric: 'tabular-nums', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{doc.numero}</span>
                <span style={{ color: T.muted, fontVariantNumeric: 'tabular-nums' }}>{doc.indice}</span>
                <span style={{ color: T.muted, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }} title={doc.titre}>{doc.titre}</span>
                <span>{doc.sas_result !== '-' ? <span style={visaPillStyle(doc.sas_result)}>{doc.sas_result}</span> : <span style={{ color: T.dim }}>{'\u2014'}</span>}</span>
                <span>{doc.visa_global !== '-' ? <span style={visaPillStyle(doc.visa_global)}>{doc.visa_global}</span> : <span style={{ color: T.dim }}>{'\u2014'}</span>}</span>
                <span style={{ color: T.dim, fontVariantNumeric: 'tabular-nums', fontSize: 11 }}>{doc.date_submitted}</span>
                <span style={{ color: T.dim, fontVariantNumeric: 'tabular-nums', fontSize: 11 }}>{doc.date_visa}</span>
                <span style={visaPillStyle(doc.status)}>{doc.status}</span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}

/* ══════════════════════════════════════════════════════════════
   Contractors Page — real data from get_contractor_list
   ══════════════════════════════════════════════════════════════ */
function ContractorsPage({ focusMode, staleDays }) {
  const [contractors, setContractors] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [selectedContractor, setSelectedContractor] = useState(null)

  useEffect(() => {
    const load = async () => {
      setLoading(true)
      setError(null)
      try {
        const data = await api.call("get_contractor_list", focusMode, staleDays)
        if (Array.isArray(data)) {
          setContractors(data)
        } else if (data && data.error) {
          setError(data.error)
        } else {
          setContractors([])
        }
      } catch (e) {
        setError(e.message || "Failed to load contractors")
      } finally {
        setLoading(false)
      }
    }
    load()
  }, [focusMode, staleDays])

  // If a contractor is selected, show their fiche
  if (selectedContractor) {
    return <ContractorFiche contractorCode={selectedContractor} onBack={() => setSelectedContractor(null)} focusMode={focusMode} staleDays={staleDays} />
  }

  if (loading) return <Spinner text="Loading contractors..." />

  if (error) {
    return (
      <div style={{ padding: 32 }}>
        <div style={{ ...glassCard, padding: 20, borderColor: 'rgba(255,69,58,0.25)', background: S.bad }}>
          <div style={{ fontSize: 13, color: T.red }}>{error}</div>
        </div>
      </div>
    )
  }

  if (contractors.length === 0) {
    return (
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100%', flexDirection: 'column', gap: 12 }}>
        <div style={{ fontSize: 18, color: T.muted, fontWeight: 500 }}>No contractor data</div>
        <div style={{ fontSize: 13, color: T.dim }}>Run a pipeline with GED data to see contractor submissions</div>
      </div>
    )
  }

  return (
    <div style={{ padding: 32, overflowY: 'auto', height: '100%' }}>
      <div style={{ fontSize: 14, fontWeight: 500, color: T.text, marginBottom: 20 }}>
        {contractors.length} contractor{contractors.length !== 1 ? 's' : ''} tracked
      </div>

      {/* Header row */}
      <div style={{
        display: 'grid',
        gridTemplateColumns: '1.5fr 1fr repeat(6, 1fr)',
        gap: 8,
        padding: '10px 20px',
        fontSize: 11,
        color: T.dim,
        textTransform: 'uppercase',
        letterSpacing: '0.04em',
        borderBottom: `1px solid ${T.glassBorder}`,
        marginBottom: 4,
      }}>
        <span>Contractor</span>
        <span>Lots</span>
        <span style={{ textAlign: 'right' }}>Submitted</span>
        <span style={{ textAlign: 'right' }}>VSO</span>
        <span style={{ textAlign: 'right' }}>VAO</span>
        <span style={{ textAlign: 'right' }}>REF</span>
        <span style={{ textAlign: 'right' }}>Open</span>
        <span style={{ textAlign: 'right' }}>Approval</span>
      </div>

      {/* Data rows */}
      {contractors.map((c, i) => {
        const approvalColor = c.approval_rate >= 0.7 ? T.green : c.approval_rate >= 0.4 ? T.amber : T.red
        return (
          <div key={i} onClick={() => setSelectedContractor(c.code || c.name)} style={{
            ...glassCard,
            display: 'grid',
            gridTemplateColumns: '1.5fr 1fr repeat(6, 1fr)',
            gap: 8,
            padding: '14px 20px',
            marginBottom: 4,
            alignItems: 'center',
            fontSize: 13,
            cursor: 'pointer',
            transition: 'border-color 0.15s',
          }}
          onMouseEnter={e => { e.currentTarget.style.borderColor = 'var(--accent-border)' }}
          onMouseLeave={e => { e.currentTarget.style.borderColor = T.glassBorder }}
          >
            <span style={{ color: T.accent, fontWeight: 500, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{c.name}</span>
            <span style={{ color: T.dim, fontSize: 12, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
              {Array.isArray(c.lots) ? c.lots.join(', ') : c.lots || '\u2014'}
            </span>
            <span style={{ textAlign: 'right', color: T.muted, fontWeight: 500, fontVariantNumeric: 'tabular-nums' }}>{c.total_submitted}</span>
            <span style={{ textAlign: 'right', color: T.green, fontVariantNumeric: 'tabular-nums' }}>{c.visa_vso}</span>
            <span style={{ textAlign: 'right', color: T.amber, fontVariantNumeric: 'tabular-nums' }}>{c.visa_vao}</span>
            <span style={{ textAlign: 'right', color: T.red, fontVariantNumeric: 'tabular-nums' }}>{c.visa_ref + (c.visa_sas_ref || 0)}</span>
            <span style={{ textAlign: 'right', color: T.amber, fontVariantNumeric: 'tabular-nums' }}>{c.visa_open}</span>
            <span style={{ textAlign: 'right', color: approvalColor, fontWeight: 500, fontVariantNumeric: 'tabular-nums' }}>
              {(c.approval_rate * 100).toFixed(0)}%
            </span>
          </div>
        )
      })}
    </div>
  )
}

/* ── Placeholder Pages ──────────────────────────────────────── */
function ReportsPage() {
  return (
    <div style={{ padding: 32, maxWidth: 900 }}>
      <div style={{ fontSize: 20, fontWeight: 600, color: T.text, marginBottom: 8 }}>
        Rapports & Exports
      </div>
      <div style={{ fontSize: 13, color: T.muted, marginBottom: 32 }}>
        Générer et exporter les documents de suivi du projet.
      </div>

      <div style={{
        ...glassCard, padding: 24, marginBottom: 20,
        display: 'flex', alignItems: 'center', justifyContent: 'space-between',
      }}>
        <div>
          <div style={{ fontSize: 14, fontWeight: 500, color: T.text, marginBottom: 4 }}>
            Tableau de Suivi VISA
          </div>
          <div style={{ fontSize: 12, color: T.muted }}>
            Exporte le Grand Fichier enrichi (version équipe) avec le nom
            <span style={{ fontFamily: 'monospace', fontSize: 11, marginLeft: 4, color: T.dim }}>
              Tableau de suivi de visa DD_MM_YYYY.xlsx
            </span>
          </div>
        </div>
        <ExportTeamVersionButton />
      </div>

      <div style={{ ...glassCard, padding: 24, opacity: 0.5 }}>
        <div style={{ fontSize: 14, fontWeight: 500, color: T.muted, marginBottom: 4 }}>
          Autres rapports
        </div>
        <div style={{ fontSize: 12, color: T.dim }}>
          Fiches consultants, bilans entreprises — à venir.
        </div>
      </div>
    </div>
  )
}

function PlaceholderPage({ name }) {
  return (
    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100%', flexDirection: 'column', gap: 12 }}>
      <div style={{ width: 48, height: 48, display: 'flex', alignItems: 'center', justifyContent: 'center', opacity: 0.15, transform: 'scale(3)' }}>
        {icons[name]}
      </div>
      <div style={{ fontSize: 18, color: T.muted, fontWeight: 500, marginTop: 24 }}>{name}</div>
      <div style={{ fontSize: 13, color: T.dim }}>Coming soon</div>
    </div>
  )
}

/* ── Helpers ─────────────────────────────────────────────────── */
function formatDate(iso) {
  if (!iso) return ''
  try {
    const d = new Date(iso)
    return d.toLocaleDateString('fr-FR', { year: 'numeric', month: '2-digit', day: '2-digit' })
  } catch {
    return iso.slice(0, 10)
  }
}

/* ════════════════════════════════════════════════════════════════
   App — Root Component
   ════════════════════════════════════════════════════════════════ */
export default function App() {
  const [activePage, setActivePage] = useState('Overview')
  const [appState, setAppState] = useState(null)
  const [loading, setLoading] = useState(true)

  // Focus Mode state — shared across Overview + sidebar badge
  const [focusMode, setFocusMode] = useState(false)
  const [staleDays, setStaleDays] = useState(90)
  const [focusStats, setFocusStats] = useState(null)

  useEffect(() => {
    const loadState = async () => {
      try {
        const bridgeAvailable = await api.ready
        if (bridgeAvailable) {
          const state = await api.call("get_app_state")
          if (state) {
            setAppState(state)
          } else {
            throw new Error("get_app_state returned null")
          }
        } else {
          // Dev mode fallback (no PyWebView after timeout)
          setAppState({
            has_baseline: true,
            current_run: 0,
            current_run_date: '2026-04-15',
            total_runs: 1,
            ged_file_detected: null,
            gf_file_detected: null,
            mapping_detected: null,
            data_dir: './data',
            pipeline_running: false,
            app_version: '1.0.0-dev',
            warnings: ['Dev mode \u2014 no PyWebView bridge'],
          })
        }
      } catch (err) {
        console.error('Failed to load app state:', err)
        setAppState({
          has_baseline: false,
          current_run: null,
          current_run_date: null,
          total_runs: 0,
          pipeline_running: false,
          warnings: ['Error loading app state: ' + err.message],
          app_version: '1.0.0',
        })
      } finally {
        setLoading(false)
      }
    }
    loadState()
  }, [])

  /* ── Render page content ─────────────────────────────────── */
  const renderPage = () => {
    if (loading) {
      return (
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100%', flexDirection: 'column', gap: 12 }}>
          <div style={{
            width: 24, height: 24, border: `2px solid ${T.glassBorder}`, borderTopColor: T.accent,
            borderRadius: '50%', animation: 'spin 0.8s linear infinite',
          }} />
          <div style={{ fontSize: 13, color: T.muted }}>Connecting to JANSA engine...</div>
          <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>
        </div>
      )
    }
    if (!appState) return null

    switch (activePage) {
      case 'Overview':
        return <OverviewPage
          appState={appState}
          setActivePage={setActivePage}
          focusMode={focusMode}
          setFocusMode={setFocusMode}
          staleDays={staleDays}
          setStaleDays={setStaleDays}
          onFocusStatsUpdate={setFocusStats}
        />
      case 'Runs':
        return <RunsPage />
      case 'Executer':
        return <ExecuterPage appState={appState} />
      case 'Consultants':
        return <ConsultantsPage focusMode={focusMode} staleDays={staleDays} />
      case 'Contractors':
        return <ContractorsPage focusMode={focusMode} staleDays={staleDays} />
      case 'Reports':
        return <ReportsPage />
      default:
        return <PlaceholderPage name={activePage} />
    }
  }

  /* ── Render ───────────────────────────────────────────────── */
  return (
    <div style={{ display: 'flex', height: '100vh', background: T.bg, position: 'relative', overflow: 'hidden' }}>

      {/* ── Ambient gradient orbs ───────────────────────────── */}
      {/* ── Sidebar ─────────────────────────────────────────── */}
      <aside style={{
        width: T.sidebarW,
        minWidth: T.sidebarW,
        height: '100vh',
        display: 'flex',
        flexDirection: 'column',
        background: T.bgElev,
        borderRight: `1px solid ${T.glassBorder}`,
        zIndex: 2,
        position: 'relative',
      }}>
        {/* Brand */}
        <div style={{ padding: '22px 18px 18px', borderBottom: `1px solid ${T.glassBorder}` }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
            <div style={{
              width: 32, height: 32, borderRadius: 10,
              background: 'linear-gradient(135deg, var(--accent), #5E5CE6)',
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              color: '#fff', fontSize: 12, fontWeight: 800, letterSpacing: '0.04em',
            }}>J</div>
            <div>
              <div style={{ fontSize: 14, fontWeight: 700, letterSpacing: '0.08em', color: T.text, lineHeight: 1 }}>JANSA</div>
              <div style={{ fontSize: 10, fontWeight: 600, letterSpacing: '0.14em', color: T.accent, marginTop: 4 }}>VISASIST</div>
            </div>
          </div>
        </div>

        {/* Nav Items */}
        <nav style={{ flex: 1, padding: '14px 10px', display: 'flex', flexDirection: 'column', gap: 3 }}>
          {NAV_ITEMS.map(item => {
            const isActive = activePage === item
            const showFocusBadge = item === 'Overview' && focusMode && focusStats && focusStats.focused != null
            return (
              <button
                key={item}
                onClick={() => setActivePage(item)}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: 10,
                  width: '100%',
                  padding: '10px 12px',
                  border: 'none',
                  borderRadius: 10,
                  cursor: 'pointer',
                  fontSize: 13,
                  fontWeight: isActive ? 600 : 400,
                  color: isActive ? T.accent : T.muted,
                  background: isActive ? 'linear-gradient(90deg, var(--accent-soft), transparent)' : 'transparent',
                  boxShadow: isActive ? `inset 3px 0 0 ${T.accent}` : 'inset 3px 0 0 transparent',
                  transition: 'background 0.15s, color 0.15s, box-shadow 0.15s',
                  textAlign: 'left',
                  fontFamily: 'inherit',
                }}
                onMouseEnter={e => {
                  if (!isActive) e.currentTarget.style.background = T.bgElev2
                }}
                onMouseLeave={e => {
                  if (!isActive) e.currentTarget.style.background = 'transparent'
                }}
              >
                <span style={{ color: isActive ? T.accent : T.dim, display: 'flex', alignItems: 'center' }}>
                  {icons[item]}
                </span>
                <span style={{ flex: 1 }}>{item}</span>
                {showFocusBadge && (
                  <span style={{
                    fontSize: 10, fontWeight: 700, color: T.accent,
                    fontVariantNumeric: 'tabular-nums',
                    background: T.accentSoft, borderRadius: 100,
                    padding: '1px 6px',
                  }}>
                    {focusStats.focused}
                  </span>
                )}
              </button>
            )
          })}
        </nav>

        {/* Sidebar Footer */}
        <div style={{ padding: '16px 16px 20px', borderTop: `1px solid ${T.glassBorder}`, background: T.bgElev }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 8 }}>
            <div style={{
              width: 6, height: 6, borderRadius: '50%',
              background: appState && !loading ? T.green : T.amber,
              boxShadow: appState && !loading ? `0 0 6px ${T.green}` : `0 0 6px ${T.amber}`,
            }} />
            <span style={{ fontSize: 11, color: T.muted }}>
              {loading ? 'Connecting...' : appState ? 'System Ready' : 'Error'}
            </span>
          </div>
          {appState && (
            <>
              <div style={{ fontSize: 11, color: T.dim, fontVariantNumeric: 'tabular-nums' }}>
                Run {appState.current_run != null ? appState.current_run : '\u2014'}
                {appState.current_run_date && ` | ${formatDate(appState.current_run_date)}`}
              </div>
              <div style={{ fontSize: 10, color: T.dim, marginTop: 4 }}>
                v{appState.app_version}
              </div>
            </>
          )}
        </div>
      </aside>

      {/* ── Main Area ───────────────────────────────────────── */}
      <main style={{ flex: 1, display: 'flex', flexDirection: 'column', zIndex: 1, position: 'relative', overflow: 'hidden' }}>

        {/* Top Bar */}
        <header style={{
          height: 60,
          minHeight: 60,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          padding: '0 28px',
          borderBottom: `1px solid ${T.glassBorder}`,
          background: 'var(--blur-bg)',
          backdropFilter: 'saturate(1.4) blur(20px)',
          WebkitBackdropFilter: 'saturate(1.4) blur(20px)',
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 14 }}>
            <span style={{ fontSize: 16, fontWeight: 600, color: T.text }}>{activePage}</span>
            {appState && appState.current_run != null && (
              <span style={{
                fontSize: 11,
                padding: '3px 10px',
                borderRadius: 100,
                background: S.good,
                color: T.green,
                fontWeight: 500,
                fontVariantNumeric: 'tabular-nums',
              }}>
                Run {appState.current_run} — COMPLETED
              </span>
            )}
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 16 }}>
            {/* Focus Mode Toggle — always visible in header */}
            <FocusModeToggle
              focusMode={focusMode}
              setFocusMode={setFocusMode}
              staleDays={staleDays}
              setStaleDays={setStaleDays}
              focusStats={focusStats}
            />
            {appState && (
              <span style={{ fontSize: 12, color: T.dim, fontVariantNumeric: 'tabular-nums' }}>
                {appState.total_runs} run{appState.total_runs !== 1 ? 's' : ''} registered
              </span>
            )}
          </div>
        </header>

        {/* Page Content */}
        <div style={{ flex: 1, overflow: 'hidden', position: 'relative' }}>
          {renderPage()}
        </div>

      </main>
    </div>
  )
}
