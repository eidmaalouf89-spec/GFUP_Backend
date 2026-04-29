/* Document Command Center Panel — Phase 4B FRONTEND
   Pure rendering of backend payload produced by Phase 4A.
   NO business logic: no tag computation, no status derivation, no sorting.
   All data comes from window.jansaBridge.loadDocumentCommandCenter /
   window.jansaBridge.searchDocuments.

   Exposes: window.DocumentCommandCenterPanel
   Requires: window.jansaBridge (data_bridge.js), window.JANSA_FONTS (tokens.js)
*/

const { useState, useEffect, useRef, useCallback } = React;

// ── Keyframe injection (once) ────────────────────────────────────────────────
(function () {
  if (document.getElementById('dcc-styles')) return;
  var s = document.createElement('style');
  s.id = 'dcc-styles';
  s.textContent = [
    '@keyframes dccSlideIn { from { transform: translateX(100%); } to { transform: translateX(0); } }',
    '@keyframes dccFadeIn  { from { opacity: 0; } to { opacity: 1; } }',
  ].join('\n');
  document.head.appendChild(s);
})();

// ── Tag color palette (locked — matches spec) ────────────────────────────────
var DCC_TAG_COLORS = {
  'Att Entreprise — Dans les délais': { ink: 'var(--good)', bg: 'var(--good-soft)' },
  'Att Entreprise — Hors délais':    { ink: 'var(--bad)',  bg: 'var(--bad-soft)'  },
  'Att BET Primaire':           { ink: '#0A84FF', bg: 'rgba(10,132,255,0.12)' },
  'Att BET Secondaire':         { ink: '#5E5CE6', bg: 'rgba(94,92,230,0.12)'  },
  'Att MOEX — Facile':     { ink: 'var(--good)', bg: 'var(--good-soft)'  },
  'Att MOEX — Arbitrage':  { ink: '#FF9F0A', bg: 'rgba(255,159,10,0.12)' },
  'Clos / Visé':           { ink: 'var(--text-3)', bg: 'rgba(99,99,102,0.14)' },
};

function dccTagStyle(tag, large) {
  var c = DCC_TAG_COLORS[tag] || { ink: 'var(--text-3)', bg: 'rgba(99,99,102,0.14)' };
  return {
    display: 'inline-block',
    padding: large ? '4px 12px' : '2px 8px',
    borderRadius: 99,
    background: c.bg,
    color: c.ink,
    fontFamily: window.JANSA_FONTS.ui,
    fontSize: large ? 12 : 10.5,
    fontWeight: 600,
    letterSpacing: '0.01em',
  };
}

// Status → ink colour (same semantics as fiche_base)
var STATUS_COLOR = {
  VSO: 'var(--good)', 'VSO-SAS': 'var(--good)', FAV: 'var(--good)',
  VAO: 'var(--warn)', SUS: 'var(--warn)',
  REF: 'var(--bad)',  DEF: 'var(--bad)',
  HM:  'var(--neutral)',
};

function statusInk(s) { return STATUS_COLOR[s] || 'var(--text-2)'; }

// closure_type → colour
var CLOSURE_COLOR = {
  VSO: 'var(--good)', 'VSO-SAS': 'var(--good)', FAV: 'var(--good)',
  VAO: 'var(--warn)', HM: 'var(--neutral)',
  REF: 'var(--bad)',  DEF: 'var(--bad)',
};

// Tier → short label
var TIER_LABEL = {
  PRIMARY: 'BET Primaire', SECONDARY: 'BET Second.',
  MOEX: 'MOEX', CONTRACTOR: 'Entreprise', CLOSED: 'Clos',
};

// ── Shared style constants ───────────────────────────────────────────────────
var dccSectionHead = {
  fontSize: 10.5, fontWeight: 700,
  letterSpacing: '.10em', textTransform: 'uppercase',
  color: 'var(--text-3)',
  marginBottom: 8, marginTop: 20,
  fontFamily: window.JANSA_FONTS.ui,
};

// ── Section 1: Header ────────────────────────────────────────────────────────
function HeaderSection({ header, tags }) {
  if (!header) return null;
  return (
    <section>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap', marginBottom: 6 }}>
        <span style={{ fontFamily: window.JANSA_FONTS.num, fontSize: 11, color: 'var(--accent)', fontWeight: 600 }}>
          {header.numero}
        </span>
        {header.indice_latest && (
          <span style={{ fontFamily: window.JANSA_FONTS.num, fontSize: 11, color: 'var(--text-3)', background: 'var(--bg-chip)', padding: '1px 7px', borderRadius: 4 }}>
            {header.indice_latest}
          </span>
        )}
        {tags && tags.primary && (
          <span style={dccTagStyle(tags.primary, true)}>{tags.primary}</span>
        )}
      </div>
      <div style={{ fontSize: 14, fontWeight: 600, color: 'var(--text)', lineHeight: 1.4, marginBottom: 6, fontFamily: window.JANSA_FONTS.ui }}>
        {header.titre || '—'}
      </div>
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 12, fontSize: 12, color: 'var(--text-2)', fontFamily: window.JANSA_FONTS.ui }}>
        {header.emetteur && <span>{header.emetteur}</span>}
        {header.lot      && <span>Lot {header.lot}</span>}
      </div>
      {tags && tags.secondary && tags.secondary.length > 0 && (
        <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap', marginTop: 8 }}>
          {tags.secondary.map(function (t, i) {
            return <span key={i} style={dccTagStyle(t, false)}>{t}</span>;
          })}
        </div>
      )}
    </section>
  );
}

// ── Section 2: Latest status ─────────────────────────────────────────────────
function LatestStatusSection({ data }) {
  if (!data) return null;
  return (
    <section>
      <div style={dccSectionHead}>Statut courant</div>
      <div style={{
        padding: '10px 14px', borderRadius: 8,
        background: 'var(--bg-elev-2)', border: '1px solid var(--line)',
        fontSize: 13, color: 'var(--text)', fontFamily: window.JANSA_FONTS.ui, lineHeight: 1.5,
      }}>
        {data.summary}
      </div>
    </section>
  );
}

// ── Section 3: Responses ─────────────────────────────────────────────────────
function ResponsesSection({ data }) {
  if (!data || data.length === 0) return null;
  return (
    <section>
      <div style={dccSectionHead}>Réponses ({data.length})</div>
      <div style={{ overflowX: 'auto' }}>
        <table style={{ width: '100%', borderCollapse: 'collapse', fontFamily: window.JANSA_FONTS.ui, fontSize: 12 }}>
          <thead>
            <tr>
              {['Intervenant', 'Tier', 'Statut', 'Réponse', 'Échéance', 'Commentaire'].map(function (h) {
                return (
                  <th key={h} style={{
                    textAlign: 'left', padding: '5px 8px',
                    borderBottom: '1px solid var(--line)',
                    fontSize: 10, fontWeight: 600, letterSpacing: '.06em',
                    textTransform: 'uppercase', color: 'var(--text-3)', whiteSpace: 'nowrap',
                  }}>{h}</th>
                );
              })}
            </tr>
          </thead>
          <tbody>
            {data.map(function (r, i) {
              var comment = r.comment || '';
              if (comment.length > 120) comment = comment.slice(0, 120) + '…';
              var tierLabel = TIER_LABEL[r.tier] || r.tier || '—';
              return (
                <tr key={i} style={{ borderBottom: '1px solid var(--line)' }}>
                  <td style={{ padding: '7px 8px', color: 'var(--text)', maxWidth: 140, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                    {r.reviewer || '—'}
                  </td>
                  <td style={{ padding: '7px 8px', whiteSpace: 'nowrap' }}>
                    <span style={{ fontSize: 10.5, padding: '2px 7px', borderRadius: 99, background: 'var(--bg-chip)', color: 'var(--text-2)' }}>{tierLabel}</span>
                  </td>
                  <td style={{ padding: '7px 8px', color: statusInk(r.status), fontWeight: r.status ? 600 : 400, fontFamily: window.JANSA_FONTS.num, whiteSpace: 'nowrap' }}>
                    {r.status || (r.is_open ? 'En attente' : '—')}
                  </td>
                  <td style={{ padding: '7px 8px', color: 'var(--text-2)', fontFamily: window.JANSA_FONTS.num, fontSize: 11, whiteSpace: 'nowrap' }}>{r.response_date || '—'}</td>
                  <td style={{ padding: '7px 8px', color: 'var(--text-2)', fontFamily: window.JANSA_FONTS.num, fontSize: 11, whiteSpace: 'nowrap' }}>{r.deadline || '—'}</td>
                  <td style={{ padding: '7px 8px', color: 'var(--text-3)', maxWidth: 160, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                    {comment || '—'}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </section>
  );
}

// ── Section 4: Comments (accordion by reviewer) ──────────────────────────────
function CommentsSection({ data }) {
  var [expanded, setExpanded] = useState({});
  if (!data || data.length === 0) return null;
  return (
    <section>
      <div style={dccSectionHead}>Commentaires</div>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
        {data.map(function (item, i) {
          var hasEarlier = item.earlier_comments && item.earlier_comments.length > 0;
          var isOpen = !!expanded[i];
          return (
            <div key={i} style={{ background: 'var(--bg-elev-2)', border: '1px solid var(--line)', borderRadius: 8, padding: '10px 12px' }}>
              <div style={{ fontSize: 11, fontWeight: 700, color: 'var(--text-2)', marginBottom: 6, fontFamily: window.JANSA_FONTS.ui }}>
                {item.reviewer}
              </div>
              {item.latest_comment
                ? <div style={{ fontSize: 12, color: 'var(--text)', lineHeight: 1.5, fontFamily: window.JANSA_FONTS.ui }}>{item.latest_comment}</div>
                : <div style={{ fontSize: 12, color: 'var(--text-3)', fontStyle: 'italic', fontFamily: window.JANSA_FONTS.ui }}>Aucun commentaire récent</div>
              }
              {hasEarlier && (
                <div style={{ marginTop: 8 }}>
                  <button
                    onClick={() => setExpanded(function (e) { return Object.assign({}, e, { [i]: !e[i] }); })}
                    style={{ fontSize: 11, color: 'var(--accent)', background: 'none', border: 'none', cursor: 'pointer', padding: 0, fontFamily: window.JANSA_FONTS.ui }}
                  >
                    {isOpen ? '▲ Masquer les précédents' : '▼ Voir les précédents (' + item.earlier_comments.length + ')'}
                  </button>
                  {isOpen && (
                    <div style={{ marginTop: 8, display: 'flex', flexDirection: 'column', gap: 6 }}>
                      {item.earlier_comments.map(function (ec, j) {
                        return (
                          <div key={j} style={{ borderLeft: '2px solid var(--line-2)', paddingLeft: 8 }}>
                            <span style={{ fontSize: 10, fontFamily: window.JANSA_FONTS.num, color: 'var(--text-3)', marginRight: 6 }}>{ec.indice + (ec.status ? ') ' + ec.status + ':' : '')}</span>
                            <span style={{ fontSize: 11, color: 'var(--text-2)', fontFamily: window.JANSA_FONTS.ui }}>{ec.comment}</span>
                          </div>
                        );
                      })}
                    </div>
                  )}
                </div>
              )}
            </div>
          );
        })}
      </div>
    </section>
  );
}

// ── Section 5: Revision history ──────────────────────────────────────────────
function RevisionHistorySection({ data }) {
  if (!data || data.length === 0) return null;
  return (
    <section>
      <div style={dccSectionHead}>Historique des révisions</div>
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
        {data.map(function (rev, i) {
          var ct = rev.closure_type;
          var ink = ct ? (CLOSURE_COLOR[ct] || 'var(--text-3)') : 'var(--text-3)';
          return (
            <div key={i}
              title={'Créé le ' + (rev.created_at || '?') + ' · ' + (rev.response_count || 0) + ' réponse(s)'}
              style={{
                display: 'flex', flexDirection: 'column', alignItems: 'center',
                padding: '5px 10px', borderRadius: 8,
                background: 'var(--bg-elev-2)', border: '1px solid var(--line)',
                minWidth: 56,
              }}
            >
              <span style={{ fontFamily: window.JANSA_FONTS.num, fontSize: 13, fontWeight: 600, color: 'var(--text)' }}>{rev.indice}</span>
              <span style={{ fontSize: 10, color: ink, fontFamily: window.JANSA_FONTS.ui, marginTop: 2 }}>
                {ct || rev.status_summary || 'open'}
              </span>
            </div>
          );
        })}
      </div>
    </section>
  );
}

// ── Section 6: Chronologie ───────────────────────────────────────────────────
function ChronologieSection({ data }) {
  if (!data) {
    return (
      <section>
        <div style={dccSectionHead}>Chronologie de la chaîne</div>
        <div style={{ fontSize: 12, color: 'var(--text-3)', fontFamily: window.JANSA_FONTS.ui, fontStyle: 'italic' }}>
          Chronologie non disponible
        </div>
      </section>
    );
  }
  var indices = data.indices || [];
  return (
    <section>
      <div style={dccSectionHead}>Chronologie de la chaîne</div>
      {data.totals && (
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 16, marginBottom: 10, fontSize: 12, fontFamily: window.JANSA_FONTS.ui }}>
          <span style={{ color: 'var(--text-2)' }}>
            Total : <strong style={{ fontFamily: window.JANSA_FONTS.num, color: data.totals.delay_days > 0 ? 'var(--bad)' : 'var(--good)' }}>{data.totals.days_actual}j</strong>
            <span style={{ color: 'var(--text-3)' }}> / {data.totals.days_expected}j attendus</span>
          </span>
          {data.attribution_cap_reattributed > 0 && (
            <span style={{ color: 'var(--text-3)' }}>Cap réattribué : {data.attribution_cap_reattributed}j</span>
          )}
        </div>
      )}
      <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
        {indices.map(function (idx, i) {
          return (
            <div key={i} style={{ padding: '8px 12px', borderRadius: 8, background: 'var(--bg-elev-2)', border: '1px solid var(--line)' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 5, flexWrap: 'wrap' }}>
                <span style={{ fontFamily: window.JANSA_FONTS.num, fontSize: 12, fontWeight: 600, color: 'var(--accent)' }}>{idx.indice}</span>
                {idx.closure_type && (
                  <span style={{ fontSize: 10, color: CLOSURE_COLOR[idx.closure_type] || 'var(--text-3)', fontFamily: window.JANSA_FONTS.ui }}>
                    {idx.closure_type}
                  </span>
                )}
                {idx.is_dernier && (
                  <span style={{ fontSize: 10, color: 'var(--text-3)', background: 'var(--bg-chip)', padding: '1px 5px', borderRadius: 4, fontFamily: window.JANSA_FONTS.ui }}>
                    dernier
                  </span>
                )}
              </div>
              {idx.review && (
                <div style={{ display: 'flex', gap: 8, alignItems: 'center', marginBottom: 3, flexWrap: 'wrap', fontSize: 12 }}>
                  <span style={{ fontFamily: window.JANSA_FONTS.ui, color: 'var(--text-3)', minWidth: 50 }}>Revue :</span>
                  <span style={{ fontFamily: window.JANSA_FONTS.num, color: idx.review.delay_days > 0 ? 'var(--bad)' : 'var(--good)' }}>
                    {idx.review.days_actual}j
                  </span>
                  <span style={{ fontFamily: window.JANSA_FONTS.num, color: 'var(--text-3)', fontSize: 11 }}>/ {idx.review.days_expected}j</span>
                  {idx.review.delay_days > 0 && (
                    <span style={{ fontFamily: window.JANSA_FONTS.num, color: 'var(--bad)', fontSize: 11 }}>+{idx.review.delay_days}j retard</span>
                  )}
                </div>
              )}
              {idx.rework && (
                <div style={{ display: 'flex', gap: 8, alignItems: 'center', marginBottom: 3, flexWrap: 'wrap', fontSize: 12 }}>
                  <span style={{ fontFamily: window.JANSA_FONTS.ui, color: 'var(--text-3)', minWidth: 50 }}>Reprise :</span>
                  <span style={{ fontFamily: window.JANSA_FONTS.num, color: idx.rework.delay_days > 0 ? 'var(--bad)' : 'var(--good)' }}>
                    {idx.rework.days_actual}j
                  </span>
                  <span style={{ fontFamily: window.JANSA_FONTS.num, color: 'var(--text-3)', fontSize: 11 }}>/ {idx.rework.days_expected}j</span>
                  {idx.rework.delay_days > 0 && (
                    <span style={{ fontFamily: window.JANSA_FONTS.num, color: 'var(--bad)', fontSize: 11 }}>+{idx.rework.delay_days}j retard</span>
                  )}
                </div>
              )}
              {idx.review && idx.review.attributed_to && idx.review.attributed_to.length > 0 && (
                <div style={{ display: 'flex', flexWrap: 'wrap', gap: 4, marginTop: 4 }}>
                  {idx.review.attributed_to.map(function (a, j) {
                    return (
                      <span key={j} style={{ fontSize: 10, color: 'var(--text-3)', background: 'var(--bg-chip)', padding: '1px 6px', borderRadius: 4, fontFamily: window.JANSA_FONTS.ui }}>
                        {a.actor} +{a.days}j
                      </span>
                    );
                  })}
                </div>
              )}
            </div>
          );
        })}
      </div>
      {data.attribution_breakdown && Object.keys(data.attribution_breakdown).length > 0 && (
        <div style={{ marginTop: 8, padding: '8px 12px', background: 'var(--bg-elev-2)', borderRadius: 8, border: '1px solid var(--line)' }}>
          <div style={{ fontSize: 10.5, fontWeight: 600, color: 'var(--text-3)', marginBottom: 6, fontFamily: window.JANSA_FONTS.ui, letterSpacing: '.08em', textTransform: 'uppercase' }}>
            Répartition des délais
          </div>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 10 }}>
            {Object.entries(data.attribution_breakdown).map(function (entry, i) {
              return (
                <span key={i} style={{ fontSize: 12, color: 'var(--text-2)', fontFamily: window.JANSA_FONTS.ui }}>
                  {entry[0]} : <strong style={{ fontFamily: window.JANSA_FONTS.num }}>{entry[1]}j</strong>
                </span>
              );
            })}
          </div>
        </div>
      )}
    </section>
  );
}

// ── Section 7: Tags strip ────────────────────────────────────────────────────
function TagsSection({ tags }) {
  if (!tags) return null;
  return (
    <section style={{ marginTop: 20, paddingTop: 16, borderTop: '1px solid var(--line)' }}>
      <div style={dccSectionHead}>Tags</div>
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
        {tags.primary && <span style={dccTagStyle(tags.primary, false)}>{tags.primary}</span>}
        {tags.secondary && tags.secondary.map(function (t, i) {
          return <span key={i} style={dccTagStyle(t, false)}>{t}</span>;
        })}
      </div>
    </section>
  );
}

// ── Doc payload loader (renders 7 sections) ──────────────────────────────────
function DocPayload({ numero, indice, focusMode, staleDays, onSearchClick }) {
  var [loading, setLoading] = useState(true);
  var [payload, setPayload] = useState(null);

  useEffect(function () {
    if (!numero) return;
    setLoading(true);
    setPayload(null);
    window.jansaBridge
      .loadDocumentCommandCenter(numero, indice || null, !!focusMode, staleDays != null ? staleDays : 30)
      .then(function (r) { setPayload(r); setLoading(false); })
      .catch(function () { setPayload({ error: 'Erreur lors du chargement.' }); setLoading(false); });
  }, [numero, indice]);

  if (loading) {
    return (
      <div style={{ display: 'flex', alignItems: 'center', gap: 12, padding: '24px 0', color: 'var(--text-3)', fontFamily: window.JANSA_FONTS.ui, fontSize: 13 }}>
        <div style={{ width: 16, height: 16, borderRadius: '50%', border: '2px solid var(--line-2)', borderTopColor: 'var(--accent)', animation: 'ddSpin 0.7s linear infinite', flexShrink: 0 }}/>
        Chargement…
      </div>
    );
  }

  if (!payload || payload.error) {
    return (
      <div style={{ padding: '16px 0' }}>
        <div style={{ color: 'var(--bad)', fontSize: 13, fontFamily: window.JANSA_FONTS.ui }}>
          ⚠ {(payload && payload.error) || 'Document non trouvé.'}
        </div>
        <button
          onClick={onSearchClick}
          style={{ marginTop: 10, fontSize: 12, color: 'var(--accent)', background: 'none', border: 'none', cursor: 'pointer', padding: 0, fontFamily: window.JANSA_FONTS.ui }}
        >
          ← Retour à la recherche
        </button>
      </div>
    );
  }

  return (
    <div>
      <HeaderSection header={payload.header} tags={payload.tags} />
      <LatestStatusSection data={payload.latest_status} />
      <ResponsesSection data={payload.responses} />
      <CommentsSection data={payload.comments} />
      <RevisionHistorySection data={payload.revision_history} />
      <ChronologieSection data={payload.chronologie} />
      <TagsSection tags={payload.tags} />
    </div>
  );
}

// ── Search input bar ─────────────────────────────────────────────────────────
function SearchInputBar({ value, onChange, onFocus }) {
  return (
    <div style={{
      display: 'flex', alignItems: 'center', gap: 8,
      padding: '7px 12px', borderRadius: 8, marginBottom: 12,
      background: 'var(--bg-elev-2)', border: '1px solid var(--line-2)',
    }}>
      <svg width="13" height="13" viewBox="0 0 14 14" fill="none" stroke="var(--text-3)" strokeWidth="1.4" strokeLinecap="round" strokeLinejoin="round">
        <circle cx="6" cy="6" r="4.2"/><path d="M9.2 9.2 L12.5 12.5"/>
      </svg>
      <input
        autoFocus
        value={value}
        onChange={function (e) { onChange(e.target.value); }}
        onFocus={onFocus}
        placeholder="Numéro, titre, émetteur…"
        style={{
          flex: 1, border: 'none', outline: 'none', background: 'transparent',
          fontFamily: window.JANSA_FONTS.ui, fontSize: 13, color: 'var(--text)',
        }}
      />
      {value && (
        <button
          onClick={() => onChange('')}
          style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'var(--text-3)', padding: 0, fontSize: 14, lineHeight: 1 }}
        >✕</button>
      )}
    </div>
  );
}

// ── Search results list ──────────────────────────────────────────────────────
function SearchResultsList({ results, loading, query, onSelect }) {
  if (!query) {
    return (
      <div style={{ color: 'var(--text-3)', fontSize: 12, fontFamily: window.JANSA_FONTS.ui, padding: '8px 0' }}>
        Saisissez un numéro, un titre ou un émetteur.
      </div>
    );
  }
  if (loading) {
    return (
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '8px 0', color: 'var(--text-3)', fontFamily: window.JANSA_FONTS.ui, fontSize: 12 }}>
        <div style={{ width: 12, height: 12, borderRadius: '50%', border: '2px solid var(--line-2)', borderTopColor: 'var(--accent)', animation: 'ddSpin 0.7s linear infinite' }}/>
        Recherche…
      </div>
    );
  }
  if (results.length === 0) {
    return <div style={{ color: 'var(--text-3)', fontSize: 12, fontFamily: window.JANSA_FONTS.ui, padding: '8px 0' }}>Aucun résultat.</div>;
  }
  return (
    <div>
      <div style={{ fontSize: 10.5, color: 'var(--text-3)', fontFamily: window.JANSA_FONTS.ui, marginBottom: 6 }}>
        {results.length} résultat{results.length !== 1 ? 's' : ''}
      </div>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
        {results.map(function (r, i) {
          return (
            <button
              key={i}
              onClick={() => onSelect(r)}
              style={{
                width: '100%', textAlign: 'left',
                background: 'var(--bg-elev-2)', border: '1px solid var(--line)',
                borderRadius: 8, padding: '9px 12px', cursor: 'pointer',
                display: 'flex', flexDirection: 'column', gap: 4,
                transition: 'border-color 0.15s',
                fontFamily: window.JANSA_FONTS.ui,
              }}
              onMouseEnter={function (e) { e.currentTarget.style.borderColor = 'var(--line-2)'; }}
              onMouseLeave={function (e) { e.currentTarget.style.borderColor = 'var(--line)'; }}
            >
              <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
                <span style={{ fontFamily: window.JANSA_FONTS.num, fontSize: 11, color: 'var(--accent)', fontWeight: 600 }}>{r.numero}</span>
                {r.indice && (
                  <span style={{ fontFamily: window.JANSA_FONTS.num, fontSize: 10, color: 'var(--text-3)', background: 'var(--bg-chip)', padding: '1px 5px', borderRadius: 3 }}>{r.indice}</span>
                )}
                {r.primary_tag && <span style={dccTagStyle(r.primary_tag, false)}>{r.primary_tag}</span>}
              </div>
              <div style={{ fontSize: 12, color: 'var(--text)', lineHeight: 1.3 }}>{r.titre || '—'}</div>
              <div style={{ fontSize: 11, color: 'var(--text-3)', display: 'flex', gap: 8, flexWrap: 'wrap' }}>
                {r.emetteur && <span>{r.emetteur}</span>}
                {r.lot      && <span>Lot {r.lot}</span>}
                {r.latest_status && <span style={{ color: 'var(--text-2)' }}>· {r.latest_status}</span>}
              </div>
            </button>
          );
        })}
      </div>
    </div>
  );
}

// ── Main panel ───────────────────────────────────────────────────────────────
function DocumentCommandCenterPanel({ state, onClose, focusMode, staleDays }) {
  // state: null | {mode:"search"} | {mode:"doc", numero, indice?}
  var [innerState, setInnerState] = useState(state);
  var [searchQuery, setSearchQuery] = useState('');
  var [searchResults, setSearchResults] = useState([]);
  var [searchLoading, setSearchLoading] = useState(false);
  var debounceRef = useRef(null);

  // Sync inner state when App pushes a new state (new panel invocation)
  useEffect(function () {
    setInnerState(state);
    setSearchQuery('');
    setSearchResults([]);
    setSearchLoading(false);
  }, [state]);

  // Esc handler
  useEffect(function () {
    if (!state) return;
    function handler(e) { if (e.key === 'Escape') onClose(); }
    window.addEventListener('keydown', handler);
    return function () { window.removeEventListener('keydown', handler); };
  }, [state, onClose]);

  // Debounced search
  var handleSearchChange = useCallback(function (q) {
    setSearchQuery(q);
    if (debounceRef.current) clearTimeout(debounceRef.current);
    if (!q.trim()) {
      setSearchResults([]);
      setSearchLoading(false);
      return;
    }
    setSearchLoading(true);
    debounceRef.current = setTimeout(function () {
      window.jansaBridge
        .searchDocuments(q, !!focusMode, staleDays != null ? staleDays : 30)
        .then(function (r) { setSearchResults(Array.isArray(r) ? r : []); setSearchLoading(false); })
        .catch(function ()  { setSearchResults([]); setSearchLoading(false); });
    }, 250);
  }, [focusMode, staleDays]);

  var handleSelect = useCallback(function (r) {
    setInnerState({ mode: 'doc', numero: r.numero, indice: r.indice || null });
  }, []);

  var handleSearchFocus = useCallback(function () {
    if (innerState && innerState.mode === 'doc') {
      setInnerState({ mode: 'search' });
    }
  }, [innerState]);

  var handleSearchClick = useCallback(function () {
    setInnerState({ mode: 'search' });
  }, []);

  if (!state) return null;

  return (
    <>
      {/* Backdrop */}
      <div
        onClick={onClose}
        style={{
          position: 'fixed', inset: 0, zIndex: 209,
          background: 'rgba(0,0,0,0.35)',
          animation: 'dccFadeIn 0.2s ease-out',
        }}
      />
      {/* Drawer */}
      <aside
        style={{
          position: 'fixed', top: 0, right: 0, bottom: 0,
          width: '42vw', minWidth: 480, maxWidth: 720,
          zIndex: 210,
          background: 'var(--bg-elev)',
          borderLeft: '1px solid var(--line)',
          padding: 24,
          overflowY: 'auto',
          fontFamily: window.JANSA_FONTS.ui,
          animation: 'dccSlideIn 0.25s ease-out',
        }}
      >
        {/* Drawer header row */}
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 16 }}>
          <div style={{ fontSize: 11, fontWeight: 700, letterSpacing: '.10em', textTransform: 'uppercase', color: 'var(--text-3)', fontFamily: window.JANSA_FONTS.ui }}>
            Centre de commande
          </div>
          <button
            onClick={onClose}
            style={{
              display: 'inline-flex', alignItems: 'center', gap: 5,
              background: 'var(--bg-elev-2)', border: '1px solid var(--line)',
              borderRadius: 99, padding: '4px 10px',
              color: 'var(--text-2)', cursor: 'pointer',
              fontFamily: window.JANSA_FONTS.ui, fontSize: 11,
            }}
          >✕ Fermer</button>
        </div>

        {/* Search input — always visible */}
        <SearchInputBar
          value={searchQuery}
          onChange={handleSearchChange}
          onFocus={handleSearchFocus}
        />

        {/* Search mode */}
        {innerState && innerState.mode === 'search' && (
          <SearchResultsList
            results={searchResults}
            loading={searchLoading}
            query={searchQuery}
            onSelect={handleSelect}
          />
        )}

        {/* Doc mode */}
        {innerState && innerState.mode === 'doc' && (
          <DocPayload
            numero={innerState.numero}
            indice={innerState.indice || null}
            focusMode={focusMode}
            staleDays={staleDays}
            onSearchClick={handleSearchClick}
          />
        )}
      </aside>
    </>
  );
}

window.DocumentCommandCenterPanel = DocumentCommandCenterPanel;
