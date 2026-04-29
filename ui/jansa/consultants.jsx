/* JANSA Consultants page — grouped MOEX / Primary / Secondary.
   Not a flat list. MOEX = hero orchestrator card (full-width).
   Primary = tall portrait cards w/ sparkline + KPIs.
   Secondary = compact chip grid.
   Click any card -> opens the Consultant Fiche. */

/* ── Phase 5: P1·P2·P3·P4 mini-bar (read-only viz of by_consultant/by_contractor entry).
   Always rendered when an entry exists. Width-proportional segments. ── */
function FocusPriBar({ entry, height = 4 }) {
  if (!entry) return null;
  const total = (entry.p1 || 0) + (entry.p2 || 0) + (entry.p3 || 0) + (entry.p4 || 0);
  if (total <= 0) return null;
  const segs = [
    { v: entry.p1 || 0, c: '#FF453A' },
    { v: entry.p2 || 0, c: '#FF9F0A' },
    { v: entry.p3 || 0, c: '#FFD60A' },
    { v: entry.p4 || 0, c: '#30D158' },
  ];
  return (
    <div style={{
      display: 'flex', width: '100%', height, borderRadius: 99,
      overflow: 'hidden', background: 'var(--line)', marginTop: 8,
    }}
    title={`P1 ${segs[0].v} · P2 ${segs[1].v} · P3 ${segs[2].v} · P4 ${segs[3].v}`}>
      {segs.map((s, i) => s.v > 0 && (
        <div key={i} style={{ flexBasis: `${(s.v / total) * 100}%`, background: s.c }}/>
      ))}
    </div>
  );
}

function ConsultantsPage({ onOpen, focusMode }) {
  const all = window.CONSULTANTS;
  const moex = all.filter(c => c.group === 'MOEX');
  const primary = all.filter(c => c.group === 'Primary');
  const secondary = all.filter(c => c.group === 'Secondary');

  const focusByName = ((window.OVERVIEW && window.OVERVIEW.focus && window.OVERVIEW.focus.by_consultant) || [])
    .reduce((m, c) => { m[c.name] = c; return m; }, {});

  const F = window.JANSA_FONTS;

  return (
    <div style={{
      padding: '32px 40px 60px',
      animation:'fadeInUp 0.4s cubic-bezier(.4,0,.2,1)',
    }}>
      {/* Page masthead */}
      <div style={{ marginBottom: 28 }}>
        <div style={{ fontSize: 11, color:'var(--text-3)', fontFamily: F.num, letterSpacing:'.08em' }}>
          CONSULTANTS · P17&CO · {all.length} ÉQUIPES
        </div>
        <h1 style={{
          fontFamily: F.ui, fontSize: 44, fontWeight: 300,
          letterSpacing:'-.035em', color:'var(--text)', margin:'6px 0 8px',
        }}>L'équipe d'études.</h1>
        <div style={{ fontSize: 13.5, color:'var(--text-2)', maxWidth: '52ch' }}>
          Organisée en trois cercles : la maîtrise d'œuvre au centre, les consultants principaux autour, les spécialistes en appui.
        </div>
      </div>

      {/* Cercle 1 — MOEX */}
      <Section num="01" title="Maîtrise d'œuvre d'exécution" sub="Pilotage central · coordonne tous les consultants">
        {moex.map(c => <MoexCard key={c.slug} c={c} onOpen={onOpen} focusMode={focusMode} focusEntry={focusByName[c.canonical_name]}/>)}
      </Section>

      {/* Cercle 2 — Primary */}
      <Section num="02" title="Consultants principaux" sub={`${primary.length} équipes · structure, fluides, électricité, architecture`}>
        <div style={{ display:'grid', gridTemplateColumns:'repeat(auto-fill, minmax(260px, 1fr))', gap: 14 }}>
          {primary.map(c => <PrimaryCard key={c.slug} c={c} onOpen={onOpen} focusMode={focusMode} focusEntry={focusByName[c.canonical_name]}/>)}
        </div>
      </Section>

      {/* Cercle 3 — Secondary */}
      <Section num="03" title="Spécialistes" sub={`${secondary.length} expertises ponctuelles · appels ponctuels sur documents`}>
        <div style={{ display:'grid', gridTemplateColumns:'repeat(auto-fill, minmax(220px, 1fr))', gap: 10 }}>
          {secondary.map(c => <SecondaryChip key={c.slug} c={c} onOpen={onOpen} focusMode={focusMode} focusEntry={focusByName[c.canonical_name]}/>)}
        </div>
      </Section>
    </div>
  );
}

function Section({ num, title, sub, children }) {
  const F = window.JANSA_FONTS;
  return (
    <section style={{ marginTop: 40 }}>
      <div style={{
        display:'flex', alignItems:'baseline', gap: 16, marginBottom: 18,
        paddingBottom: 14, borderBottom:'1px solid var(--line)',
      }}>
        <span style={{ fontFamily: F.num, fontSize: 12, color:'var(--text-3)', letterSpacing:'.04em' }}>{num}</span>
        <div style={{ flex: 1 }}>
          <h2 style={{
            fontFamily: F.ui, fontSize: 24, fontWeight: 600,
            letterSpacing:'-.02em', color:'var(--text)', margin: 0,
          }}>{title}</h2>
          {sub && <div style={{ fontSize: 12.5, color:'var(--text-3)', marginTop: 4 }}>{sub}</div>}
        </div>
      </div>
      {children}
    </section>
  );
}

/* ── Mini sparkline ── */
function MiniSpark({ values, color = 'var(--accent)', width = 120, height = 30 }) {
  if (!values || values.length < 2) return null;
  const max = Math.max(...values), min = Math.min(...values);
  const span = max - min || 1;
  const n = values.length;
  const xs = values.map((_, i) => (i * width) / (n - 1));
  const ys = values.map(v => height - 2 - ((v - min) / span) * (height - 4));
  const line = values.map((_, i) => `${i ? 'L' : 'M'}${xs[i].toFixed(1)},${ys[i].toFixed(1)}`).join(' ');
  const last = { x: xs[n-1], y: ys[n-1] };
  return (
    <svg viewBox={`0 0 ${width} ${height}`} style={{ width: '100%', height, display:'block' }}>
      <path d={line} fill="none" stroke={color} strokeWidth="1.4" strokeLinejoin="round"/>
      <circle cx={last.x} cy={last.y} r="2.5" fill={color}/>
    </svg>
  );
}

/* ── Compact visa breakdown: s1 / s2 / s3 + avg days ──
   Labels come from the adapter (VSO/VAO/REF for most consultants;
   FAV/SUS/DEF for Bureau de Contrôle / SOCOTEC). */
function CnBreakdown({ vso, vao, ref_, avg_days, s1_label, s2_label, s3_label }) {
  const F = window.JANSA_FONTS;
  const l1 = s1_label || 'VSO';
  const l2 = s2_label || 'VAO';
  const l3 = s3_label || 'REF';
  const items = [
    { label: l1, value: vso ?? 0, color: 'var(--good)' },
    { label: l2, value: vao ?? 0, color: 'var(--accent)' },
    { label: l3, value: ref_ ?? 0, color: 'var(--bad)' },
  ];
  return (
    <div style={{ display:'flex', gap: 12, flexWrap:'wrap', alignItems:'center' }}>
      {items.map(it => (
        <span key={it.label} style={{ display:'flex', gap: 4, alignItems:'baseline' }}>
          <span style={{
            fontSize: 9, color: it.color, fontWeight: 700,
            letterSpacing:'.08em', textTransform:'uppercase',
          }}>{it.label}</span>
          <span style={{
            fontFamily: F.num, fontSize: 11, color: 'var(--text-2)',
            fontVariantNumeric:'tabular-nums',
          }}>{it.value.toLocaleString('fr-FR')}</span>
        </span>
      ))}
      {avg_days != null && (
        <span style={{ fontSize: 10, color:'var(--text-3)' }}>
          {'·'}{' '}
          <span style={{ fontFamily: F.num, fontVariantNumeric:'tabular-nums' }}>{avg_days}j</span>
          {' moy.'}
        </span>
      )}
    </div>
  );
}

/* ── MOEX — hero orchestrator card ── */
function MoexCard({ c, onOpen, focusMode, focusEntry }) {
  const F = window.JANSA_FONTS;
  return (
    <div onClick={() => onOpen(c)} style={{
      cursor:'pointer',
      background:'linear-gradient(135deg, var(--bg-elev) 0%, var(--bg-elev-2) 100%)',
      border:'1px solid var(--line)',
      borderRadius: 20, padding: 28,
      display:'grid', gridTemplateColumns:'auto 1fr auto', gap: 28,
      alignItems:'center', position:'relative', overflow:'hidden',
      transition:'border-color 0.2s, transform 0.2s',
    }}
    onMouseEnter={e => { e.currentTarget.style.borderColor = 'var(--accent)'; e.currentTarget.style.transform = 'translateY(-2px)'; }}
    onMouseLeave={e => { e.currentTarget.style.borderColor = 'var(--line)'; e.currentTarget.style.transform = 'translateY(0)'; }}
    >
      {/* ambient halo */}
      <div style={{
        position:'absolute', top:-120, right:-120, width: 320, height: 320,
        background:'radial-gradient(circle, rgba(10,132,255,0.18), transparent 60%)',
        pointerEvents:'none',
      }}/>

      {/* Orbit glyph */}
      <svg viewBox="0 0 120 120" width="120" height="120" style={{ flexShrink: 0 }}>
        <defs>
          <linearGradient id="moex-core" x1="0" y1="0" x2="1" y2="1">
            <stop offset="0%" stopColor="#0A84FF"/>
            <stop offset="50%" stopColor="#5E5CE6"/>
            <stop offset="100%" stopColor="#BF5AF2"/>
          </linearGradient>
        </defs>
        <circle cx="60" cy="60" r="50" fill="none" stroke="var(--line)" strokeWidth="1" strokeDasharray="3 3"/>
        <circle cx="60" cy="60" r="34" fill="none" stroke="var(--line)" strokeWidth="1"/>
        <circle cx="60" cy="60" r="22" fill="url(#moex-core)"/>
        {/* orbiting dots */}
        {[0, 72, 144, 216, 288].map((deg, i) => {
          const rad = deg * Math.PI / 180;
          const r = i % 2 ? 50 : 34;
          const x = 60 + Math.cos(rad) * r, y = 60 + Math.sin(rad) * r;
          return <circle key={i} cx={x} cy={y} r="3.5" fill={i === 0 ? '#FF453A' : i === 1 ? '#FFD60A' : '#30D158'}/>;
        })}
        <text x="60" y="64" textAnchor="middle" fontFamily={F.ui} fontWeight="700" fontSize="11" fill="#fff" letterSpacing=".08em">MOEX</text>
      </svg>

      <div style={{ minWidth: 0 }}>
        <div style={{ display:'flex', alignItems:'center', gap: 10, marginBottom: 10 }}>
          <span style={{
            fontSize: 10, padding:'3px 9px', borderRadius: 99,
            background:'var(--accent-soft)', color:'var(--accent)',
            fontFamily: F.ui, fontWeight: 700, letterSpacing:'.12em',
          }}>CERCLE 1 · PILOTE</span>
          {c.badge && <span style={{
            fontSize: 10, padding:'3px 9px', borderRadius: 99,
            background:'var(--good-soft)', color:'var(--good)',
            fontFamily: F.ui, fontWeight: 700, letterSpacing:'.12em',
          }}>{c.badge.toUpperCase()}</span>}
          {c.focus_owned > 0 && <span style={{
            fontSize: 10, padding:'3px 9px', borderRadius: 99,
            background:'rgba(10,132,255,0.12)', color:'var(--accent)',
            fontFamily: F.ui, fontWeight: 700, letterSpacing:'.1em',
          }}>FOCUS {c.focus_owned}</span>}
        </div>
        <h3 style={{
          fontFamily: F.ui, fontSize: 28, fontWeight: 600,
          letterSpacing:'-.025em', color:'var(--text)', margin: '0 0 4px',
        }}>{c.name}</h3>
        <div style={{ fontSize: 13, color:'var(--text-2)' }}>{c.role}</div>
      </div>

      {/* KPIs */}
      <div style={{ display:'flex', gap: 24, flexShrink: 0, alignItems:'flex-end' }}>
        {focusMode
          ? <StatBlock label="À traiter" value={(c.focus_owned || 0).toLocaleString('fr-FR')} color="var(--accent)"/>
          : <StatBlock label="Documents" value={c.total.toLocaleString('fr-FR').replace(/,/g,' ')}/>
        }
        {focusMode && <StatBlock label="Total docs" value={c.total.toLocaleString('fr-FR').replace(/,/g,' ')}/>}
        <StatBlock label="Répondus" value={c.answered.toLocaleString('fr-FR').replace(/,/g,' ')}/>
        <StatBlock label="En attente" value={c.pending} color="var(--bad)"/>
        <StatBlock label="Conformité" value={`${c.pass_rate}%`} color="var(--good)" spark={c.trend}/>
      </div>

      {/* Visa breakdown row — full width */}
      <div style={{
        gridColumn: '1 / -1',
        paddingTop: 14, borderTop: '1px solid var(--line)', marginTop: -4,
      }}>
        <CnBreakdown vso={c.vso} vao={c.vao} ref_={c.ref} avg_days={c.avg_response_days}
          s1_label={c.s1_label} s2_label={c.s2_label} s3_label={c.s3_label}/>
      </div>

      {/* P1·P2·P3·P4 mini-bar — full width, always shown when entry exists */}
      <div style={{ gridColumn: '1 / -1' }}>
        <FocusPriBar entry={focusEntry}/>
      </div>
    </div>
  );
}

function StatBlock({ label, value, color, spark }) {
  const F = window.JANSA_FONTS;
  return (
    <div style={{ textAlign:'right', minWidth: 80 }}>
      <div style={{ fontSize: 10, color:'var(--text-3)', letterSpacing:'.1em', textTransform:'uppercase' }}>{label}</div>
      <div style={{
        fontFamily: F.ui, fontSize: 26, fontWeight: 300, letterSpacing:'-.02em',
        color: color || 'var(--text)', marginTop: 4, lineHeight: 1,
      }}>{value}</div>
      {spark && <div style={{ width: 80, marginTop: 6, marginLeft:'auto' }}>
        <MiniSpark values={spark} color={color || 'var(--accent)'} width={80} height={20}/>
      </div>}
    </div>
  );
}

/* ── Primary — portrait card ── */
function PrimaryCard({ c, onOpen, focusMode, focusEntry }) {
  const F = window.JANSA_FONTS;
  const initials = c.name.split(/[·—\s]+/).filter(Boolean).slice(0, 2).map(w => w[0]).join('').toUpperCase();
  const tone = c.pass_rate >= 90 ? 'var(--good)' : c.pass_rate >= 85 ? 'var(--accent)' : 'var(--warn)';

  return (
    <div onClick={() => onOpen(c)} style={{
      cursor:'pointer', background:'var(--bg-elev)',
      border:'1px solid var(--line)', borderRadius: 16,
      padding: 20, display:'flex', flexDirection:'column', gap: 12,
      position:'relative', overflow:'hidden',
      transition:'border-color 0.2s, transform 0.2s',
    }}
    onMouseEnter={e => { e.currentTarget.style.borderColor = 'var(--line-2)'; e.currentTarget.style.transform = 'translateY(-2px)'; }}
    onMouseLeave={e => { e.currentTarget.style.borderColor = 'var(--line)'; e.currentTarget.style.transform = 'translateY(0)'; }}
    >
      {/* Avatar + name */}
      <div style={{ display:'flex', alignItems:'center', gap: 12 }}>
        <div style={{
          width: 44, height: 44, borderRadius: 10,
          background: `linear-gradient(135deg, ${tone}, ${tone}99)`,
          display:'flex', alignItems:'center', justifyContent:'center',
          color:'#fff', fontSize: 14, fontWeight: 700, letterSpacing:'-.02em',
          boxShadow: `0 6px 16px -6px ${tone}80`,
          flexShrink: 0,
        }}>{initials}</div>
        <div style={{ minWidth: 0, flex: 1 }}>
          <div style={{ fontSize: 13.5, fontWeight: 600, color:'var(--text)', letterSpacing:'-.01em', whiteSpace:'nowrap', overflow:'hidden', textOverflow:'ellipsis' }}>
            {c.name}
          </div>
          <div style={{ fontSize: 11, color:'var(--text-3)', marginTop: 2 }}>{c.role}</div>
        </div>
        {c.focus_owned > 0 && (
          <span style={{
            fontSize: 9, padding:'2px 7px', borderRadius: 99, flexShrink: 0,
            background:'rgba(10,132,255,0.12)', color:'var(--accent)',
            fontWeight: 700, letterSpacing:'.08em',
          }}>F{c.focus_owned}</span>
        )}
      </div>

      {/* Spark */}
      <div style={{ height: 40, marginTop: 4 }}>
        <MiniSpark values={c.trend} color={tone} width={220} height={40}/>
      </div>

      {/* Stats bar */}
      <div style={{ display:'flex', justifyContent:'space-between', alignItems:'baseline', paddingTop: 10, borderTop:'1px solid var(--line)' }}>
        <div>
          <div style={{ fontFamily: F.ui, fontSize: 22, fontWeight: 300, letterSpacing:'-.02em', color:'var(--text)' }}>{c.pass_rate}<span style={{ fontSize: 13, color:'var(--text-2)' }}>%</span></div>
          <div style={{ fontSize: 10, color:'var(--text-3)', letterSpacing:'.1em', textTransform:'uppercase' }}>Conformité</div>
        </div>
        <div style={{ textAlign:'center' }}>
          {focusMode ? (
            <div>
              <div style={{ fontFamily: F.ui, fontSize: 18, fontWeight: 500, color:'var(--accent)' }}>{c.focus_owned || 0}</div>
              <div style={{ fontSize: 10, color:'var(--text-3)', letterSpacing:'.1em', textTransform:'uppercase' }}>À traiter</div>
              <div style={{ fontSize: 10, color:'var(--text-3)', marginTop: 2 }}>{c.total} total</div>
            </div>
          ) : (
            <div>
              <div style={{ fontFamily: F.ui, fontSize: 18, fontWeight: 500, color:'var(--text)' }}>{c.total.toLocaleString('fr-FR').replace(/,/g,' ')}</div>
              <div style={{ fontSize: 10, color:'var(--text-3)', letterSpacing:'.1em', textTransform:'uppercase' }}>Docs</div>
            </div>
          )}
        </div>
        <div style={{ textAlign:'right' }}>
          <div style={{ fontFamily: F.ui, fontSize: 18, fontWeight: 500, color: c.pending > 100 ? 'var(--bad)' : 'var(--text)' }}>{c.pending}</div>
          <div style={{ fontSize: 10, color:'var(--text-3)', letterSpacing:'.1em', textTransform:'uppercase' }}>Attente</div>
        </div>
      </div>

      {/* Visa breakdown */}
      <div style={{ paddingTop: 8, borderTop: '1px solid var(--line)' }}>
        <CnBreakdown vso={c.vso} vao={c.vao} ref_={c.ref} avg_days={c.avg_response_days}
          s1_label={c.s1_label} s2_label={c.s2_label} s3_label={c.s3_label}/>
      </div>

      {/* P1·P2·P3·P4 mini-bar — always shown when entry exists */}
      <FocusPriBar entry={focusEntry}/>
    </div>
  );
}

/* ── Secondary — compact chip ── */
function SecondaryChip({ c, onOpen, focusMode, focusEntry }) {
  const F = window.JANSA_FONTS;
  const initials = c.name.split(/[·—\s]+/).filter(Boolean).slice(0, 2).map(w => w[0]).join('').toUpperCase();
  const tone = c.pass_rate >= 92 ? 'var(--good)' : 'var(--accent)';

  return (
    <div onClick={() => onOpen(c)} style={{
      cursor:'pointer', background:'var(--bg-elev)',
      border:'1px solid var(--line)', borderRadius: 12,
      padding:'12px 14px', display:'flex', alignItems:'center', gap: 12,
      transition:'border-color 0.2s, transform 0.15s, background 0.2s',
    }}
    onMouseEnter={e => { e.currentTarget.style.borderColor = tone; e.currentTarget.style.background = 'var(--bg-elev-2)'; }}
    onMouseLeave={e => { e.currentTarget.style.borderColor = 'var(--line)'; e.currentTarget.style.background = 'var(--bg-elev)'; }}
    >
      <div style={{
        width: 32, height: 32, borderRadius: 8,
        background: `linear-gradient(135deg, ${tone}, ${tone}99)`,
        color:'#fff', fontSize: 11, fontWeight: 700, letterSpacing:'-.02em',
        display:'flex', alignItems:'center', justifyContent:'center',
        flexShrink: 0,
      }}>{initials}</div>
      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{ fontSize: 12, fontWeight: 600, color:'var(--text)', letterSpacing:'-.005em', whiteSpace:'nowrap', overflow:'hidden', textOverflow:'ellipsis' }}>
          {c.name}
        </div>
        <div style={{ fontSize: 10.5, color:'var(--text-3)', marginTop: 2, whiteSpace:'nowrap', overflow:'hidden', textOverflow:'ellipsis' }}>{c.role}</div>
      </div>
      <div style={{ textAlign:'right', flexShrink: 0 }}>
        {focusMode ? (
          <div>
            <div style={{ fontFamily: F.ui, fontSize: 15, fontWeight: 600, color:'var(--accent)', letterSpacing:'-.01em' }}>{c.focus_owned || 0}</div>
            <div style={{ fontSize: 9, color:'var(--text-3)' }}>à traiter</div>
            <div style={{ fontFamily: F.num, fontSize: 10, color:'var(--text-3)', fontVariantNumeric:'tabular-nums' }}>{c.total} total</div>
          </div>
        ) : (
          <div>
            <div style={{ fontFamily: F.ui, fontSize: 15, fontWeight: 600, color: tone, letterSpacing:'-.01em' }}>{c.pass_rate}%</div>
            <div style={{ fontFamily: F.num, fontSize: 10, color:'var(--text-3)', fontVariantNumeric:'tabular-nums' }}>{c.total}</div>
          </div>
        )}
        {/* Mini-bar — before VSO/VAO/REF line */}
        <div style={{ marginTop: 4 }}><FocusPriBar entry={focusEntry} height={3}/></div>
        {/* Visa micro breakdown — uses per-consultant labels */}
        {c.vso != null && (
          <div style={{ fontSize: 9, color:'var(--text-3)', fontVariantNumeric:'tabular-nums', marginTop: 2 }}
               title={`${c.s1_label||'VSO'} ${c.vso} / ${c.s2_label||'VAO'} ${c.vao??0} / ${c.s3_label||'REF'} ${c.ref??0}`}>
            <span style={{ color:'var(--good)' }}>{c.vso}</span>
            <span style={{ color:'var(--text-3)' }}>{' / '}</span>
            <span style={{ color:'var(--accent)' }}>{c.vao ?? 0}</span>
            <span style={{ color:'var(--text-3)' }}>{' / '}</span>
            <span style={{ color:'var(--bad)' }}>{c.ref ?? 0}</span>
          </div>
        )}
        {c.focus_owned > 0 && (
          <div style={{
            fontSize: 9, marginTop: 3, color:'var(--accent)', fontWeight: 700, letterSpacing:'.06em',
          }}>F{c.focus_owned}</div>
        )}
      </div>
    </div>
  );
}

Object.assign(window, { ConsultantsPage });
