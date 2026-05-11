/* JANSA — ACTION MOEX (Plan d'action MOEX)
   Phase 6C — Counter-Attack Cockpit UI.

   Pure rendering of Phase 6B bridge payloads (loadCounterAttackHome /
   loadCounterAttackQueue / loadCounterAttackItem). NO business logic
   in JSX: bucket classification, ownership, deadlines, risk, MOEX
   exposure, attackability, and recommended action all come from the
   backend.

   ── Phase 6C.1 — STATIC SKELETON ──────────────────────────────────
   This revision is layout-only. Bridge wiring lands in 6C.3–6C.5.
   Numbers and rows below come from local placeholder objects and will
   be replaced by live calls in subsequent steps.

   User-facing labels follow the corrected ACTION MOEX naming. The
   legacy phase wording must NOT appear in any user-facing UI string;
   only "ACTION MOEX" / "action_moex" wording is rendered.

   Exposes: window.ActionMoexPage
   Requires: window.JANSA_FONTS (tokens.js)
*/

const { useState: useStateAm, useEffect: useEffectAm, useRef: useRefAm } = React;

const amFonts = window.JANSA_FONTS;

/* Inject responsive split-layout media query exactly once.
   Matches the IIFE pattern used in document_panel.jsx so the style
   tag is not reattached on every render. */
(function () {
  if (document.getElementById('action-moex-styles')) return;
  var s = document.createElement('style');
  s.id = 'action-moex-styles';
  s.textContent =
    '@media (max-width: 960px){' +
    '.am-action-split{grid-template-columns:1fr !important;}' +
    '}';
  document.head.appendChild(s);
})();

/* ═══════════════════════════════════════════════════════════════════
   Bucket presentation contract — APPROVED ORDER (UI override).
   The backend (Phase 6B) returns buckets in BUCKET_DISPLAY_ORDER. This
   array is the ACTION MOEX cockpit's own presentation order; backend
   order is unchanged. Counts are looked up by bucket enum, not index.
   ═══════════════════════════════════════════════════════════════════ */
const AM_BUCKET_PRESENTATION = [
  {
    bucket: 'FERMER_MAINTENANT',
    label: 'VISA facile',
    priority: 'Tous les avis alignés',
    description: 'Tous les avis sont alignés. MOEX peut émettre le visa.',
  },
  {
    bucket: 'DECISION_MOEX',
    label: 'Arbitrage MOEX',
    priority: 'Décision requise',
    description: 'Plusieurs avis existent. MOEX doit trancher.',
  },
  {
    bucket: 'ENTREPRISE_A_RELANCER',
    label: 'Entreprises à relancer',
    priority: 'Action externe',
    description: 'L’entreprise doit resoumettre ou corriger.',
  },
  {
    bucket: 'CONSULTANT_A_ATTAQUER',
    label: 'Consultants à relancer',
    priority: 'Relance BET',
    description: 'Un consultant bloque la chaîne documentaire.',
  },
];

/* Conditional priority/subtitle text for the two count-sensitive buckets. */
function amBucketPrioritySubtitle(preset, count) {
  return preset.priority;
}

/* User-facing copy for empty / error states.
   Phase 6B may pass through a legacy `message` field; the cockpit
   overrides it with ACTION MOEX wording. */
const AM_COPY = {
  selectBucket:        'Sélectionnez un bucket ci-dessus.',
  bucketEmpty:         'Aucun sujet dans ce bucket.',
  itemNotFound:        'Élément introuvable dans le plan d’action actuel.',
  detailEmpty:         'Sélectionnez une ligne dans la file pour voir le détail de l’action.',
  backendUnavailable:  'Le backend n’est pas connecté. Le module ACTION MOEX n’est pas disponible en mode aperçu.',
  artifactMissing:     'Le module ACTION MOEX n’est pas encore généré.',
  loading:             'Chargement…',
  totalEyebrow:        'Total affiché',
  pageEyebrow:         'ACTION MOEX',
  pageTitle:           'Plan d’action MOEX',
  pageSubtitle:        'Plan d\'action — sous-ensemble curé',
  detailHeader:        'Détail action',
  sec1:                'Ce que c’est',
  sec2:                'Pourquoi il est ici',
  sec3:                'Ce que MOEX doit faire',
  sec4:                'Preuves rapides',
  evidenceNone:        'Aucune preuve disponible.',
  btnOpenDetail:       'Ouvrir le détail',
  btnShowEvidence:     'Voir preuves',
  btnHideEvidence:     'Masquer preuves',
  queueSubtitle:       'File d’action — langage opérationnel uniquement',
  btnExport:           'Exporter Excel',
  btnExporting:        'Export en cours…',
  exportSuccess:       'Export terminé.',
  exportError:         'Échec de l’export.',
  exportEmptyOk:       'Bucket vide — fichier généré avec en-tête seul.',
};

/* Inline SVG bucket symbols — 22×22, stroke 1.4, matching shell.jsx style. */
const amBucketSymbols = {
  FERMER_MAINTENANT: (
    <svg width="22" height="22" viewBox="0 0 22 22" fill="none" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" strokeLinejoin="round">
      <circle cx="11" cy="11" r="8"/>
      <path d="M6.5 11.5 L9.5 14.5 L15 8.5"/>
    </svg>
  ),
  DECISION_MOEX: (
    <svg width="22" height="22" viewBox="0 0 22 22" fill="none" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" strokeLinejoin="round">
      <path d="M11 4 V18 M5 18 H17"/>
      <path d="M4 10 H10 L7 5 Z"/>
      <path d="M12 10 H18 L15 5 Z"/>
    </svg>
  ),
  ENTREPRISE_A_RELANCER: (
    <svg width="22" height="22" viewBox="0 0 22 22" fill="none" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" strokeLinejoin="round">
      <path d="M5 11 a6 6 0 0111-3"/>
      <path d="M17 11 a6 6 0 01-11 3"/>
      <path d="M16 5 V8 H13 M6 17 V14 H9"/>
    </svg>
  ),
  CONSULTANT_A_ATTAQUER: (
    <svg width="22" height="22" viewBox="0 0 22 22" fill="none" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" strokeLinejoin="round">
      <circle cx="11" cy="7.5" r="3"/>
      <path d="M5 19c0-3.3 2.7-5 6-5s6 1.7 6 5"/>
    </svg>
  ),
};

const amFmt = (n) => (n == null ? '0' : Number(n).toLocaleString('fr-FR').replace(/,/g, ' '));

function amRiskTone(risk) {
  const r = (risk || '').toString().toUpperCase();
  if (r === 'HIGH') return 'risk-high';
  if (r === 'MEDIUM' || r === 'MED') return 'risk-medium';
  if (r === 'LOW') return 'risk-low';
  return 'neutral';
}

/* ─── Visual primitives (inline; no cross-file dependencies) ───────── */

function AmCard({ children, style, padding, onClick, accent, interactive }) {
  const isInteractive = interactive || !!onClick;
  return (
    <div
      onClick={onClick}
      style={{
        background: 'var(--bg-elev)',
        border: '1px solid var(--line)',
        borderRadius: 18,
        padding: padding != null ? padding : 22,
        position: 'relative',
        overflow: 'hidden',
        cursor: isInteractive ? 'pointer' : 'default',
        transition: 'border-color 0.18s, box-shadow 0.18s',
        ...style,
      }}
      onMouseEnter={isInteractive ? (e) => { e.currentTarget.style.borderColor = 'var(--line-2)'; } : undefined}
      onMouseLeave={isInteractive ? (e) => {
        // Allow callers to override via style.borderColor (e.g. selected card)
        if (style && style.borderColor) {
          e.currentTarget.style.borderColor = style.borderColor;
        } else {
          e.currentTarget.style.borderColor = 'var(--line)';
        }
      } : undefined}
    >
      {accent && (
        <div style={{
          position: 'absolute', top: -80, right: -80, width: 200, height: 200,
          background: 'radial-gradient(circle, ' + accent + '33, transparent 60%)',
          pointerEvents: 'none',
        }}/>
      )}
      {children}
    </div>
  );
}

function AmEyebrow({ children, style }) {
  return (
    <div style={{
      fontFamily: amFonts.ui, fontSize: 10.5, fontWeight: 600,
      letterSpacing: '.12em', textTransform: 'uppercase',
      color: 'var(--text-3)', ...style,
    }}>{children}</div>
  );
}

function AmSectionHead({ children, style }) {
  return (
    <div style={{
      fontFamily: amFonts.ui, fontSize: 10.5, fontWeight: 700,
      letterSpacing: '.10em', textTransform: 'uppercase',
      color: 'var(--text-3)', marginTop: 18, marginBottom: 8, ...style,
    }}>{children}</div>
  );
}

function AmChip({ tone, children, style }) {
  const palette = {
    'risk-high':   { bg: 'var(--bad-soft)',    fg: 'var(--bad)' },
    'risk-medium': { bg: 'var(--warn-soft)',   fg: 'var(--warn)' },
    'risk-low':    { bg: 'var(--good-soft)',   fg: 'var(--good)' },
    'neutral':     { bg: 'var(--bg-chip)',     fg: 'var(--text-3)' },
    'accent':      { bg: 'var(--accent-soft)', fg: 'var(--accent)' },
  };
  const p = palette[tone] || palette.neutral;
  return (
    <span style={{
      display: 'inline-flex', alignItems: 'center',
      padding: '2px 8px', borderRadius: 99,
      background: p.bg, color: p.fg,
      fontFamily: amFonts.ui, fontSize: 10.5, fontWeight: 600,
      letterSpacing: '.02em', whiteSpace: 'nowrap',
      ...style,
    }}>{children}</span>
  );
}

/* ─── Header card ──────────────────────────────────────────────────── */

function AmHeaderCard({ totalToday }) {
  return (
    <AmCard accent="var(--accent)" padding={26} style={{ marginBottom: 22 }}>
      <div style={{
        display: 'flex', justifyContent: 'space-between',
        alignItems: 'flex-start', gap: 16, flexWrap: 'wrap',
      }}>
        <div style={{ minWidth: 0, flex: 1 }}>
          <AmEyebrow>{AM_COPY.pageEyebrow}</AmEyebrow>
          <h1 style={{
            fontFamily: amFonts.ui, fontSize: 38, fontWeight: 300,
            letterSpacing: '-.03em', color: 'var(--text)',
            margin: '8px 0 10px', lineHeight: 1.05,
          }}>{AM_COPY.pageTitle}</h1>
          <p style={{
            margin: 0, fontSize: 13, color: 'var(--text-2)',
            lineHeight: 1.55, maxWidth: 640,
          }}>{AM_COPY.pageSubtitle}</p>
        </div>
        {totalToday != null && (
          <div style={{
            padding: '10px 16px', borderRadius: 12,
            background: 'var(--bg-elev-2)', border: '1px solid var(--line)',
            display: 'flex', flexDirection: 'column', alignItems: 'flex-end',
            gap: 2, flexShrink: 0,
          }}>
            <span style={{
              fontFamily: amFonts.num, fontVariantNumeric: 'tabular-nums',
              fontSize: 22, fontWeight: 600, color: 'var(--text)',
              letterSpacing: '-.01em', lineHeight: 1.1,
            }}>{amFmt(totalToday)}</span>
            <span style={{
              fontSize: 10, color: 'var(--text-3)',
              letterSpacing: '.08em', textTransform: 'uppercase',
            }}>{AM_COPY.totalEyebrow}</span>
          </div>
        )}
      </div>
    </AmCard>
  );
}

/* ─── Bucket card grid (7 cards, approved order) ───────────────────── */

function AmBucketGrid({ buckets, selectedBucket, onSelect }) {
  // Lookup live counts by bucket enum.
  const lookup = {};
  for (let i = 0; i < buckets.length; i++) {
    lookup[buckets[i].bucket] = buckets[i];
  }

  return (
    <div style={{
      display: 'grid',
      gridTemplateColumns: 'repeat(auto-fit, minmax(230px, 1fr))',
      gap: 14, marginBottom: 22,
    }}>
      {AM_BUCKET_PRESENTATION.map((preset) => {
        const live = lookup[preset.bucket];
        const count = live ? Number(live.count) || 0 : 0;
        const subtitle = amBucketPrioritySubtitle(preset, count);
        const isActive = selectedBucket === preset.bucket;
        return (
          <AmCard
            key={preset.bucket}
            onClick={() => onSelect(preset.bucket)}
            padding={20}
            style={{
              borderColor: isActive ? 'rgba(10,132,255,0.45)' : 'var(--line)',
              boxShadow: isActive ? '0 0 0 4px rgba(10,132,255,0.08)' : 'none',
            }}
          >
            <div style={{
              display: 'flex', alignItems: 'flex-start',
              justifyContent: 'space-between', gap: 12,
            }}>
              <div style={{
                width: 36, height: 36, borderRadius: 10,
                background: isActive ? 'var(--accent-soft)' : 'var(--bg-elev-2)',
                color: isActive ? 'var(--accent)' : 'var(--text-2)',
                display: 'flex', alignItems: 'center', justifyContent: 'center',
                flexShrink: 0,
                transition: 'background 0.18s, color 0.18s',
              }}>{amBucketSymbols[preset.bucket]}</div>
              <span style={{
                fontFamily: amFonts.num, fontVariantNumeric: 'tabular-nums',
                fontSize: 28, fontWeight: 300, color: 'var(--text)',
                letterSpacing: '-.02em', lineHeight: 1,
              }}>{amFmt(count)}</span>
            </div>
            <div style={{
              marginTop: 14, fontSize: 14, fontWeight: 600,
              color: 'var(--text)', letterSpacing: '-.005em',
            }}>{preset.label}</div>
            {subtitle && (
              <div style={{
                marginTop: 4, fontSize: 11, fontWeight: 500,
                color: 'var(--accent)',
                letterSpacing: '.02em',
              }}>{subtitle}</div>
            )}
            <div style={{
              marginTop: 10, fontSize: 12, color: 'var(--text-2)',
              lineHeight: 1.45,
            }}>{preset.description}</div>
          </AmCard>
        );
      })}
    </div>
  );
}

/* ─── Queue row + queue panel (left column) ────────────────────────── */

function AmQueueRow({ row, isSelected, onSelect }) {
  return (
    <button
      onClick={onSelect}
      style={{
        width: '100%', textAlign: 'left',
        background: isSelected ? 'var(--bg-elev-2)' : 'transparent',
        border: 'none',
        borderBottom: '1px solid var(--line)',
        padding: '14px 18px',
        cursor: 'pointer', fontFamily: 'inherit',
        position: 'relative',
        transition: 'background 0.15s',
      }}
      onMouseEnter={(e) => { if (!isSelected) e.currentTarget.style.background = 'var(--bg-elev-2)'; }}
      onMouseLeave={(e) => { if (!isSelected) e.currentTarget.style.background = 'transparent'; }}
    >
      {isSelected && (
        <div style={{
          position: 'absolute', left: 0, top: 8, bottom: 8, width: 3,
          background: 'var(--accent)', borderRadius: '0 3px 3px 0',
        }}/>
      )}
      <div style={{
        fontSize: 13, fontWeight: 600, color: 'var(--text)',
        marginBottom: 4, letterSpacing: '-.005em',
      }}>{row.subject_label || '—'}</div>
      {row.reason && (
        <div style={{
          fontSize: 12, color: 'var(--text-2)', lineHeight: 1.45,
          marginBottom: 4,
        }}>{row.reason}</div>
      )}
      {row.recommended_action && (
        <div style={{
          fontSize: 12, color: 'var(--text-2)', lineHeight: 1.45,
          marginBottom: 8,
        }}>
          <span style={{ color: 'var(--text-3)', fontWeight: 600 }}>Action&nbsp;: </span>
          {row.recommended_action}
        </div>
      )}
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6, alignItems: 'center' }}>
        {row.risk_level && <AmChip tone={amRiskTone(row.risk_level)}>{row.risk_level}</AmChip>}
        {row.actor && <AmChip tone="neutral">{row.actor}</AmChip>}
        {row.days_open != null && row.days_open > 0 && (
          <AmChip tone="neutral">
            <span style={{ fontFamily: amFonts.num, fontVariantNumeric: 'tabular-nums' }}>
              {row.days_open}&nbsp;j ouv.
            </span>
          </AmChip>
        )}
        {row.days_late != null && row.days_late > 0 && (
          <AmChip tone="risk-high">
            <span style={{ fontFamily: amFonts.num, fontVariantNumeric: 'tabular-nums' }}>
              {row.days_late}&nbsp;j retard
            </span>
          </AmChip>
        )}
        {row.warning_tags && row.warning_tags.split(',').map(function(t) {
          var tag = t.trim();
          return tag ? <AmChip key={tag} tone="accent">{tag}</AmChip> : null;
        })}
        {(row.numero || row.indice) && (
          <span style={{
            fontFamily: amFonts.num, fontVariantNumeric: 'tabular-nums',
            fontSize: 10.5, color: 'var(--text-3)', marginLeft: 'auto',
          }}>
            {row.numero || ''}{row.indice ? ' · ' + row.indice : ''}
          </span>
        )}
      </div>
    </button>
  );
}

function AmQueuePanel({ bucketLabel, queue, selectedItemId, onSelectItem, loading, errorMessage,
                        onExport, exporting, exportNotice }) {
  const rendered = queue && queue.rows ? queue.rows.length : 0;
  const exportDisabled = !!exporting;
  return (
    <AmCard padding={0} style={{ overflow: 'hidden' }}>
      <div style={{
        padding: '16px 18px',
        borderBottom: '1px solid var(--line)',
        display: 'flex', justifyContent: 'space-between',
        alignItems: 'center', gap: 12,
      }}>
        <div style={{ minWidth: 0 }}>
          <div style={{
            fontSize: 14, fontWeight: 600, color: 'var(--text)',
            letterSpacing: '-.005em',
            whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis',
          }}>{bucketLabel || '—'}</div>
          <div style={{ fontSize: 11, color: 'var(--text-3)', marginTop: 2 }}>
            {AM_COPY.queueSubtitle}
          </div>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexShrink: 0 }}>
          {rendered > 0 && (
            <AmChip tone="neutral">
              <span style={{ fontFamily: amFonts.num, fontVariantNumeric: 'tabular-nums' }}>
                {amFmt(rendered)}
              </span>
            </AmChip>
          )}
          {onExport && (
            <button
              type="button"
              onClick={onExport}
              disabled={exportDisabled}
              style={{
                padding: '6px 12px',
                fontSize: 12,
                fontWeight: 500,
                fontFamily: amFonts.ui,
                color: exportDisabled ? 'var(--text-3)' : 'var(--text)',
                background: exportDisabled ? 'var(--bg-elev)' : 'var(--bg)',
                border: '1px solid var(--line)',
                borderRadius: 8,
                cursor: exportDisabled ? 'default' : 'pointer',
                whiteSpace: 'nowrap',
              }}
            >
              {exporting ? AM_COPY.btnExporting : AM_COPY.btnExport}
            </button>
          )}
        </div>
      </div>
      {exportNotice && (
        <div style={{
          padding: '8px 18px',
          borderBottom: '1px solid var(--line)',
          fontSize: 12,
          color: exportNotice.tone === 'error' ? 'var(--warn)' : 'var(--text-2)',
          background: exportNotice.tone === 'error' ? 'var(--warn-soft)' : 'var(--bg-elev)',
        }}>
          {exportNotice.text}
        </div>
      )}
      <div style={{ maxHeight: 'calc(100vh - 380px)', overflowY: 'auto' }}>
        {loading && (
          <div style={{ padding: 32, fontSize: 13, color: 'var(--text-3)', textAlign: 'center' }}>
            {AM_COPY.loading}
          </div>
        )}
        {!loading && errorMessage && (
          <div style={{ padding: 16, margin: 12, fontSize: 13, color: 'var(--warn)', background: 'var(--warn-soft)', border: '1px solid rgba(255,214,10,0.25)', borderRadius: 10, lineHeight: 1.55 }}>
            {errorMessage}
          </div>
        )}
        {!loading && !errorMessage && !queue && (
          <div style={{ padding: 32, fontSize: 13, color: 'var(--text-3)', textAlign: 'center' }}>
            {AM_COPY.selectBucket}
          </div>
        )}
        {!loading && !errorMessage && queue && queue.rows && queue.rows.length === 0 && (
          <div style={{ padding: 32, fontSize: 13, color: 'var(--text-3)', textAlign: 'center' }}>
            {AM_COPY.bucketEmpty}
          </div>
        )}
        {!loading && !errorMessage && queue && queue.rows && queue.rows.map((row, i) => (
          <AmQueueRow
            key={row.item_id || i}
            row={row}
            isSelected={!!(selectedItemId && row.item_id === selectedItemId)}
            onSelect={() => onSelectItem(row)}
          />
        ))}
      </div>
    </AmCard>
  );
}

/* ─── Detail panel (right column, sticky) ──────────────────────────── */

function AmDetailPanel({ item, row, evidenceOpen, onToggleEvidence, onOpenDcc, loading, errorMessage }) {
  // Empty state — nothing selected.
  if (!item && !row) {
    return (
      <AmCard padding={26} style={{ position: 'sticky', top: 24 }}>
        <AmEyebrow>{AM_COPY.detailHeader}</AmEyebrow>
        <div style={{
          marginTop: 18, fontSize: 13, color: 'var(--text-3)', lineHeight: 1.55,
        }}>{AM_COPY.detailEmpty}</div>
      </AmCard>
    );
  }

  const header = (item && item.header) || null;
  const subject = (header && header.subject_label) || (row && row.subject_label) || '—';
  const risk    = (header && header.risk_level)    || (row && row.risk_level)    || '';
  const numero  = (header && header.numero)        || (row && row.numero)        || null;
  const indice  = (header && header.indice)        || (row && row.indice)        || null;

  const whatIsIt = (item && item.what_is_it)
    ? item.what_is_it
    : (numero
        ? 'Sujet documentaire actif — document ' + numero
            + (indice ? ', indice ' + indice : '') + '.'
        : '—');

  const whyHere = (item && Array.isArray(item.why_here) && item.why_here.length > 0)
    ? item.why_here
    : ((row && row.reason) ? [row.reason] : []);

  const recommended = (item && item.recommended_action)
    || (row && row.recommended_action)
    || null;

  const evidence = (item && Array.isArray(item.evidence)) ? item.evidence : [];

  const dccRef = (item && item.open_dcc_ref) || (row && row.open_dcc_ref) || null;

  return (
    <AmCard padding={26} style={{ position: 'sticky', top: 24 }}>
      <AmEyebrow>{AM_COPY.detailHeader}</AmEyebrow>

      <div style={{
        marginTop: 8, display: 'flex', alignItems: 'flex-start',
        gap: 10, flexWrap: 'wrap',
      }}>
        <div style={{
          fontSize: 17, fontWeight: 600, color: 'var(--text)',
          letterSpacing: '-.005em', lineHeight: 1.3,
          flex: 1, minWidth: 0,
        }}>{subject}</div>
        {risk && <AmChip tone={amRiskTone(risk)}>{risk}</AmChip>}
      </div>

      {(numero || indice) && (
        <div style={{
          marginTop: 6,
          fontFamily: amFonts.num, fontVariantNumeric: 'tabular-nums',
          fontSize: 11, color: 'var(--text-3)',
        }}>
          {numero || ''}{indice ? ' · ' + indice : ''}
        </div>
      )}

      {loading && (
        <div style={{
          marginTop: 12, fontSize: 11.5, color: 'var(--text-3)',
          fontStyle: 'italic',
        }}>{AM_COPY.loading}</div>
      )}
      {!loading && errorMessage && (
        <div style={{
          marginTop: 12, padding: '8px 12px',
          background: 'var(--warn-soft)',
          border: '1px solid rgba(255,214,10,0.25)',
          borderRadius: 8,
          fontSize: 11.5, color: 'var(--warn)', lineHeight: 1.45,
        }}>{errorMessage}</div>
      )}

      <AmSectionHead>{AM_COPY.sec1}</AmSectionHead>
      <div style={{ fontSize: 13, color: 'var(--text-2)', lineHeight: 1.55 }}>
        {whatIsIt}
      </div>

      <AmSectionHead>{AM_COPY.sec2}</AmSectionHead>
      {whyHere.length > 0 ? (
        <ul style={{
          margin: 0, padding: 0, listStyle: 'none',
          fontSize: 13, color: 'var(--text-2)', lineHeight: 1.55,
        }}>
          {whyHere.map((reason, i) => (
            <li key={i} style={{
              padding: '4px 0 4px 14px', position: 'relative',
            }}>
              <span style={{
                position: 'absolute', left: 0, top: 11, width: 4, height: 4,
                borderRadius: 99, background: 'var(--text-3)',
              }}/>
              {reason}
            </li>
          ))}
        </ul>
      ) : (
        <div style={{ fontSize: 13, color: 'var(--text-3)' }}>—</div>
      )}

      <AmSectionHead>{AM_COPY.sec3}</AmSectionHead>
      <div style={{
        fontSize: 13, color: 'var(--text)', lineHeight: 1.55, fontWeight: 500,
        background: 'var(--accent-soft)', borderRadius: 10,
        padding: '10px 14px', border: '1px solid rgba(10,132,255,0.20)',
      }}>{recommended || '—'}</div>

      {evidenceOpen && (
        <React.Fragment>
          <AmSectionHead>{AM_COPY.sec4}</AmSectionHead>
          {evidence.length > 0 ? (
            <ul style={{
              margin: 0, padding: 0, listStyle: 'none',
              fontSize: 12, color: 'var(--text-2)', lineHeight: 1.5,
            }}>
              {evidence.map((e, i) => (
                <li key={i} style={{
                  padding: '6px 0 6px 14px', position: 'relative',
                  borderTop: i === 0 ? 'none' : '1px solid var(--line)',
                }}>
                  <span style={{
                    position: 'absolute', left: 0, top: 12, width: 4, height: 4,
                    borderRadius: 99, background: 'var(--text-3)',
                  }}/>
                  {e}
                </li>
              ))}
            </ul>
          ) : (
            <div style={{ fontSize: 12, color: 'var(--text-3)' }}>{AM_COPY.evidenceNone}</div>
          )}
        </React.Fragment>
      )}

      <div style={{
        display: 'flex', gap: 10, marginTop: 22, flexWrap: 'wrap',
      }}>
        <button
          onClick={onOpenDcc}
          disabled={!dccRef}
          style={{
            padding: '9px 18px', borderRadius: 9,
            background: dccRef ? 'var(--accent-soft)' : 'var(--bg-elev-2)',
            border: '1px solid ' + (dccRef ? 'rgba(10,132,255,0.35)' : 'var(--line)'),
            color: dccRef ? 'var(--accent)' : 'var(--text-3)',
            fontFamily: 'inherit', fontSize: 13, fontWeight: 500,
            cursor: dccRef ? 'pointer' : 'not-allowed',
            opacity: dccRef ? 1 : 0.55,
          }}
        >{AM_COPY.btnOpenDetail}</button>
        <button
          onClick={onToggleEvidence}
          style={{
            padding: '9px 18px', borderRadius: 9,
            background: 'var(--bg-elev-2)',
            border: '1px solid var(--line)',
            color: 'var(--text-2)',
            fontFamily: 'inherit', fontSize: 13, fontWeight: 500,
            cursor: 'pointer',
          }}
        >{evidenceOpen ? AM_COPY.btnHideEvidence : AM_COPY.btnShowEvidence}</button>
      </div>
    </AmCard>
  );
}

/* ─── Main page ────────────────────────────────────────────────────── */

function ActionMoexPage(/* props: focusMode (forwarded by shell, unused) */) {
  // Phase 6C — home wired (6C.3); queue wired (6C.4); item still placeholder (6C.5).
  const [home, setHome] = useStateAm(null);
  const [homeError, setHomeError] = useStateAm(null);

  // Queue state — caches per bucket; loading/error scoped to the SELECTED bucket.
  const [queueByBucket, setQueueByBucket] = useStateAm({});
  const [queueLoading, setQueueLoading] = useStateAm(false);
  const [queueError, setQueueError] = useStateAm(null);
  const queueGenRef = useRefAm(0);
  const itemGenRef = useRefAm(0);

  // 6C.6 — item-level loading/error feedback.
  const [itemLoading, setItemLoading] = useStateAm(false);
  const [itemError, setItemError] = useStateAm(null);

  // Step 5 — Excel export feedback per-bucket. Notice carries {tone, text}.
  const [exportingBucket, setExportingBucket] = useStateAm(null);
  const [exportNotice, setExportNotice] = useStateAm(null);

  useEffectAm(function () {
    var cancelled = false;
    if (!window.jansaBridge || typeof window.jansaBridge.loadCounterAttackHome !== 'function') {
      setHomeError(AM_COPY.backendUnavailable);
      setHome({ available: false, summary: { total_today: 0 }, buckets: [] });
      return undefined;
    }
    window.jansaBridge.loadCounterAttackHome().then(function (payload) {
      if (cancelled) return;
      if (!payload || payload.available === false) {
        // Distinguish bridge preview-mode ("Backend not connected.") from
        // backend artifact-missing ("Le module ... pas encore généré.").
        var msg = String((payload && payload.message) || '').toLowerCase();
        var isBackendDown = msg.indexOf('backend') >= 0 || msg.indexOf('preview') >= 0;
        setHomeError(isBackendDown ? AM_COPY.backendUnavailable : AM_COPY.artifactMissing);
        setHome({ available: false, summary: { total_today: 0 }, buckets: [] });
        return;
      }
      setHome(payload);
      setHomeError(null);
      // Auto-load the recommended (or default) bucket once the home payload arrives.
      var initialBucket = (payload.summary && payload.summary.recommended_first_bucket) || 'FERMER_MAINTENANT';
      setSelectedBucket(initialBucket);
      _amFetchQueue(initialBucket);
    }).catch(function (e) {
      if (cancelled) return;
      console.error('[ActionMoex] home load error:', e);
      setHomeError(AM_COPY.backendUnavailable);
      setHome({ available: false, summary: { total_today: 0 }, buckets: [] });
    });
    return function () { cancelled = true; };
  }, []);
  const [selectedBucket, setSelectedBucket] = useStateAm('FERMER_MAINTENANT');
  const [selectedRow, setSelectedRow] = useStateAm(null);
  const [selectedItem, setSelectedItem] = useStateAm(null);
  const [evidenceOpen, setEvidenceOpen] = useStateAm(false);

  // Queue fetch — bridge call with cache + generation guard. The home useEffect
  // calls this once on initial mount; clicking a bucket in the grid calls it
  // again. Cache hit returns immediately. Stale promise resolutions are dropped.
  const _amFetchQueue = function (bucket) {
    if (!bucket) return;
    if (queueByBucket[bucket]) return;
    if (!window.jansaBridge || typeof window.jansaBridge.loadCounterAttackQueue !== 'function') {
      setQueueByBucket(function (prev) { return Object.assign({}, prev, { [bucket]: { available: false, bucket: bucket, count: 0, rows: [] } }); });
      setQueueError(AM_COPY.backendUnavailable);
      return;
    }
    var myGen = ++queueGenRef.current;
    setQueueLoading(true);
    window.jansaBridge.loadCounterAttackQueue(bucket, 500).then(function (payload) {
      if (myGen !== queueGenRef.current) return;
      setQueueLoading(false);
      if (!payload || payload.available === false) {
        var msg = String((payload && payload.message) || '').toLowerCase();
        var isBackendDown = msg.indexOf('backend') >= 0 || msg.indexOf('preview') >= 0;
        setQueueError(isBackendDown ? AM_COPY.backendUnavailable : AM_COPY.artifactMissing);
        setQueueByBucket(function (prev) { return Object.assign({}, prev, { [bucket]: { available: false, bucket: bucket, count: 0, rows: [] } }); });
        return;
      }
      setQueueByBucket(function (prev) { return Object.assign({}, prev, { [bucket]: payload }); });
    }).catch(function (e) {
      if (myGen !== queueGenRef.current) return;
      console.error('[ActionMoex] queue load error:', e);
      setQueueLoading(false);
      setQueueError(AM_COPY.backendUnavailable);
      setQueueByBucket(function (prev) { return Object.assign({}, prev, { [bucket]: { available: false, bucket: bucket, count: 0, rows: [] } }); });
    });
  };

  // Bucket click — switch selection, clear stale queue + item UI state, fetch (cached).
  const onSelectBucket = (bucket) => {
    setSelectedBucket(bucket);
    setSelectedRow(null);
    setSelectedItem(null);
    setEvidenceOpen(false);
    setQueueLoading(false);
    setQueueError(null);
    setItemLoading(false);
    setItemError(null);
    setExportNotice(null);
    _amFetchQueue(bucket);
  };

  // Item fetch — bridge call with generation guard. Stale promise resolutions
  // (user clicked a different row before the previous fetch resolved) are dropped.
  // On not-found / unavailable / exception, selectedItem stays null and the
  // detail panel falls back to row-derived fields (subject, reason → why_here[0],
  // recommended_action) so the user still sees actionable info.
  // 6C.6 — surface a small loading/error notice in the detail panel without
  // hiding the row fallbacks.
  const _amFetchItem = function (itemId) {
    if (!itemId) return;
    if (!window.jansaBridge || typeof window.jansaBridge.loadCounterAttackItem !== 'function') {
      setItemError(AM_COPY.backendUnavailable);
      return;
    }
    var myGen = ++itemGenRef.current;
    setItemLoading(true);
    setItemError(null);
    window.jansaBridge.loadCounterAttackItem(itemId).then(function (payload) {
      if (myGen !== itemGenRef.current) return;
      setItemLoading(false);
      if (!payload || payload.available === false) {
        var msg = String((payload && payload.message) || '').toLowerCase();
        var isBackendDown = msg.indexOf('backend') >= 0 || msg.indexOf('preview') >= 0;
        setItemError(isBackendDown ? AM_COPY.backendUnavailable : AM_COPY.artifactMissing);
        return;
      }
      if (payload.found === false) {
        setItemError(AM_COPY.itemNotFound);
        return;
      }
      setSelectedItem(payload);
    }).catch(function (e) {
      if (myGen !== itemGenRef.current) return;
      console.error('[ActionMoex] item load error:', e);
      setItemLoading(false);
      setItemError(AM_COPY.backendUnavailable);
    });
  };

  // Row click — set selected row + clear stale item state + fetch enriched detail.
  const onSelectItem = (row) => {
    setSelectedRow(row);
    setSelectedItem(null);
    setItemLoading(false);
    setItemError(null);
    setEvidenceOpen(false);
    if (row && row.item_id) {
      _amFetchItem(row.item_id);
    }
  };

  const onToggleEvidence = () => setEvidenceOpen((v) => !v);

  const onOpenDcc = () => {
    const ref = (selectedItem && selectedItem.open_dcc_ref)
      || (selectedRow && selectedRow.open_dcc_ref)
      || null;
    if (ref && window.openDocumentCommandCenter) {
      window.openDocumentCommandCenter(ref.numero, ref.indice);
    }
  };

  // Step 5 — Excel export of the currently-selected bucket.
  const onExportBucket = async () => {
    const bucket = selectedBucket;
    if (!bucket) return;
    if (!window.jansaBridge || typeof window.jansaBridge.exportActionMoexBucket !== 'function') {
      setExportNotice({ tone: 'error', text: AM_COPY.backendUnavailable });
      return;
    }
    setExportingBucket(bucket);
    setExportNotice(null);
    try {
      const res = await window.jansaBridge.exportActionMoexBucket(bucket);
      if (res && res.success) {
        const baseText = res.message || AM_COPY.exportSuccess;
        setExportNotice({ tone: 'ok', text: baseText });
        if (res.path && window.pywebview && window.pywebview.api
            && typeof window.pywebview.api.open_file_in_explorer === 'function') {
          try { await window.pywebview.api.open_file_in_explorer(res.path); }
          catch (e) { console.warn('[ActionMoex] open_file_in_explorer failed:', e); }
        }
      } else {
        const msg = (res && res.error) ? String(res.error) : AM_COPY.exportError;
        setExportNotice({ tone: 'error', text: AM_COPY.exportError + ' ' + msg });
      }
    } catch (e) {
      console.error('[ActionMoex] export error:', e);
      setExportNotice({ tone: 'error', text: AM_COPY.exportError });
    } finally {
      setExportingBucket(null);
    }
  };

  const buckets = (home && home.buckets) || [];
  const totalToday = (home && home.available !== false && home.summary) ? home.summary.total_today : null;
  const currentQueue = queueByBucket[selectedBucket] || null;
  const currentBucketLabel = (() => {
    const preset = AM_BUCKET_PRESENTATION.find((p) => p.bucket === selectedBucket);
    return preset ? preset.label : '—';
  })();

  return (
    <div style={{
      padding: 32,
      animation: 'fadeInUp 0.4s cubic-bezier(.4,0,.2,1)',
      fontFamily: amFonts.ui,
    }}>
      <AmHeaderCard totalToday={totalToday}/>

      {home === null && !homeError && (
        <div style={{
          padding: 28, marginBottom: 22,
          background: 'var(--bg-elev)', border: '1px solid var(--line)',
          borderRadius: 18, textAlign: 'center',
          fontSize: 13, color: 'var(--text-3)',
        }}>{AM_COPY.loading}</div>
      )}

      {homeError && (
        <div style={{
          padding: 16, marginBottom: 22,
          background: 'var(--warn-soft)',
          border: '1px solid rgba(255,214,10,0.25)',
          borderRadius: 12,
          fontSize: 13, color: 'var(--warn)', lineHeight: 1.55,
        }}>{homeError}</div>
      )}

      {home !== null && (
        <AmBucketGrid
          buckets={buckets}
          selectedBucket={selectedBucket}
          onSelect={onSelectBucket}
        />
      )}

      {home !== null && home.available !== false && (
        <div className="am-action-split" style={{
          display: 'grid',
          gridTemplateColumns: 'minmax(0, 1.4fr) minmax(0, 1fr)',
          gap: 18, alignItems: 'flex-start',
        }}>
          <AmQueuePanel
            bucketLabel={currentBucketLabel}
            queue={currentQueue && currentQueue.available !== false ? currentQueue : null}
            loading={queueLoading}
            errorMessage={queueError}
            selectedItemId={selectedRow ? selectedRow.item_id : null}
            onSelectItem={onSelectItem}
            onExport={onExportBucket}
            exporting={exportingBucket === selectedBucket}
            exportNotice={exportNotice}
          />
          <AmDetailPanel
            item={selectedItem}
            row={selectedRow}
            evidenceOpen={evidenceOpen}
            onToggleEvidence={onToggleEvidence}
            onOpenDcc={onOpenDcc}
            loading={itemLoading}
            errorMessage={itemError}
          />
        </div>
      )}
    </div>
  );
}

Object.assign(window, { ActionMoexPage });
