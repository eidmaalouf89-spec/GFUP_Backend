/* JANSA Contractors page — reads window.CONTRACTORS_LIST and window.CONTRACTORS.
   CONTRACTORS_LIST: top-5 enriched contractors (code, name, docs, pass_rate).
   CONTRACTORS: full code→name lookup for all emetteurs.
   No fiche drill-down yet — get_contractor_fiche is in the backend but
   the bridge method is not wired; this is a future step. */

function ContractorsPage() {
  const list   = window.CONTRACTORS_LIST || [];  // enriched top-N
  const lookup = window.CONTRACTORS     || {};  // full code→name

  // Build a set of codes already in the enriched list
  const inList = new Set(list.map(c => c.code));

  // Remaining contractors from lookup — no KPI data
  const extras = Object.entries(lookup)
    .filter(([code]) => !inList.has(code))
    .sort(([, a], [, b]) => a.localeCompare(b, 'fr'))
    .map(([code, name]) => ({ code, name, docs: null, pass_rate: null }));

  const totalCount = Object.keys(lookup).length || list.length;
  const F = window.JANSA_FONTS;

  return (
    <div style={{
      padding: '32px 40px 60px',
      animation: 'fadeInUp 0.4s cubic-bezier(.4,0,.2,1)',
    }}>
      {/* Page masthead */}
      <div style={{ marginBottom: 28 }}>
        <div style={{
          fontSize: 11, color: 'var(--text-3)',
          fontFamily: F.num, letterSpacing: '.08em',
        }}>
          ENTREPRISES · P17&CO · {totalCount} INTERVENANTS
        </div>
        <h1 style={{
          fontFamily: F.ui, fontSize: 44, fontWeight: 300,
          letterSpacing: '-.035em', color: 'var(--text)', margin: '6px 0 8px',
        }}>Entreprises intervenantes.</h1>
        <div style={{ fontSize: 13.5, color: 'var(--text-2)', maxWidth: '52ch' }}>
          Emetteurs de documents soumis au visa. Classés par taux de conformité,
          seuil minimum 5 documents.
        </div>
      </div>

      {/* Section 01 — enriched cards */}
      {list.length > 0 && (
        <CtSection
          num="01"
          title="Classement par conformité"
          sub={`${list.length} entreprise${list.length > 1 ? 's' : ''} · ≥ 5 documents soumis`}
        >
          <div style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fill, minmax(260px, 1fr))',
            gap: 14,
          }}>
            {list.map(c => <ContractorCard key={c.code} c={c} />)}
          </div>
        </CtSection>
      )}

      {/* Section 02 — plain chips from lookup */}
      {extras.length > 0 && (
        <CtSection
          num={list.length > 0 ? '02' : '01'}
          title="Autres intervenants"
          sub={`${extras.length} entreprise${extras.length > 1 ? 's' : ''} · données en cours d'agrégation`}
        >
          <div style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fill, minmax(220px, 1fr))',
            gap: 10,
          }}>
            {extras.map(c => <ContractorChip key={c.code} c={c} />)}
          </div>
        </CtSection>
      )}

      {/* Empty state */}
      {list.length === 0 && extras.length === 0 && (
        <div style={{
          marginTop: 60, textAlign: 'center',
          color: 'var(--text-3)', fontFamily: F.ui, fontSize: 14,
        }}>
          Aucun emetteur trouvé. Lancez le pipeline pour charger les données.
        </div>
      )}
    </div>
  );
}

/* ── Section header — mirrors consultants.jsx Section ── */
function CtSection({ num, title, sub, children }) {
  const F = window.JANSA_FONTS;
  return (
    <section style={{ marginTop: 40 }}>
      <div style={{
        display: 'flex', alignItems: 'baseline', gap: 16, marginBottom: 18,
        paddingBottom: 14, borderBottom: '1px solid var(--line)',
      }}>
        <span style={{
          fontFamily: F.num, fontSize: 12, color: 'var(--text-3)', letterSpacing: '.04em',
        }}>{num}</span>
        <div style={{ flex: 1 }}>
          <h2 style={{
            fontFamily: F.ui, fontSize: 24, fontWeight: 600,
            letterSpacing: '-.02em', color: 'var(--text)', margin: 0,
          }}>{title}</h2>
          {sub && <div style={{ fontSize: 12.5, color: 'var(--text-3)', marginTop: 4 }}>{sub}</div>}
        </div>
      </div>
      {children}
    </section>
  );
}

/* ── Enriched contractor card (has pass_rate + docs from CONTRACTORS_LIST) ── */
function ContractorCard({ c }) {
  const F = window.JANSA_FONTS;
  const rate = c.pass_rate != null ? c.pass_rate : null;
  const tone = rate == null ? 'var(--text-3)'
    : rate >= 90 ? 'var(--good)'
    : rate >= 80 ? 'var(--accent)'
    : 'var(--warn)';

  // Code initials — up to 3 chars
  const codeLabel = (c.code || c.name || '?').slice(0, 4).toUpperCase();

  return (
    <div style={{
      background: 'var(--bg-elev)',
      border: '1px solid var(--line)', borderRadius: 16,
      padding: 20, display: 'flex', flexDirection: 'column', gap: 12,
      position: 'relative', overflow: 'hidden',
      cursor: 'default',
      transition: 'border-color 0.2s, transform 0.2s',
    }}
    onMouseEnter={e => {
      e.currentTarget.style.borderColor = 'var(--line-2)';
      e.currentTarget.style.transform = 'translateY(-2px)';
    }}
    onMouseLeave={e => {
      e.currentTarget.style.borderColor = 'var(--line)';
      e.currentTarget.style.transform = 'translateY(0)';
    }}
    >
      {/* Code badge + name */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
        <div style={{
          width: 44, height: 44, borderRadius: 10, flexShrink: 0,
          background: `linear-gradient(135deg, ${tone}, ${tone}99)`,
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          color: '#fff', fontSize: 11, fontWeight: 700, letterSpacing: '.04em',
          boxShadow: `0 6px 16px -6px ${tone}80`,
        }}>{codeLabel}</div>
        <div style={{ minWidth: 0, flex: 1 }}>
          <div style={{
            fontSize: 13.5, fontWeight: 600, color: 'var(--text)',
            letterSpacing: '-.01em', whiteSpace: 'nowrap',
            overflow: 'hidden', textOverflow: 'ellipsis',
          }}>{c.name}</div>
          <div style={{ fontSize: 11, color: 'var(--text-3)', marginTop: 2 }}>
            Code émetteur : {c.code}
          </div>
        </div>
      </div>

      {/* KPIs */}
      <div style={{
        display: 'flex', justifyContent: 'space-between', alignItems: 'baseline',
        paddingTop: 10, borderTop: '1px solid var(--line)',
      }}>
        <div>
          <div style={{
            fontFamily: F.ui, fontSize: 22, fontWeight: 300,
            letterSpacing: '-.02em', color: tone,
          }}>
            {rate != null ? rate : '—'}
            {rate != null && <span style={{ fontSize: 13, color: 'var(--text-2)' }}>%</span>}
          </div>
          <div style={{ fontSize: 10, color: 'var(--text-3)', letterSpacing: '.1em', textTransform: 'uppercase' }}>
            Conformité
          </div>
        </div>
        <div style={{ textAlign: 'right' }}>
          <div style={{
            fontFamily: F.ui, fontSize: 18, fontWeight: 500, color: 'var(--text)',
            fontVariantNumeric: 'tabular-nums', fontFamily: F.num,
          }}>
            {c.docs != null ? c.docs.toLocaleString('fr-FR') : '—'}
          </div>
          <div style={{ fontSize: 10, color: 'var(--text-3)', letterSpacing: '.1em', textTransform: 'uppercase' }}>
            Documents
          </div>
        </div>
      </div>
    </div>
  );
}

/* ── Plain chip for contractors without KPI data ── */
function ContractorChip({ c }) {
  const F = window.JANSA_FONTS;
  const codeLabel = (c.code || c.name || '?').slice(0, 4).toUpperCase();

  return (
    <div style={{
      background: 'var(--bg-elev)',
      border: '1px solid var(--line)', borderRadius: 12,
      padding: '12px 14px', display: 'flex', alignItems: 'center', gap: 12,
      cursor: 'default',
      transition: 'background 0.2s, border-color 0.15s',
    }}
    onMouseEnter={e => {
      e.currentTarget.style.background = 'var(--bg-elev-2)';
      e.currentTarget.style.borderColor = 'var(--line-2)';
    }}
    onMouseLeave={e => {
      e.currentTarget.style.background = 'var(--bg-elev)';
      e.currentTarget.style.borderColor = 'var(--line)';
    }}
    >
      <div style={{
        width: 32, height: 32, borderRadius: 8, flexShrink: 0,
        background: 'var(--bg-elev-2)', border: '1px solid var(--line)',
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        color: 'var(--text-3)', fontSize: 10, fontWeight: 700, letterSpacing: '.04em',
      }}>{codeLabel}</div>
      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{
          fontSize: 12, fontWeight: 600, color: 'var(--text)',
          whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis',
        }}>{c.name}</div>
        <div style={{ fontSize: 10.5, color: 'var(--text-3)', marginTop: 2 }}>
          {c.code}
        </div>
      </div>
    </div>
  );
}

Object.assign(window, { ContractorsPage });
