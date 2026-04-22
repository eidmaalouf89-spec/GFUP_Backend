/* JANSA Overview — Apple/Tesla aesthetic.
   Replaces: old KPI cards (Current Run, Discrepancies, Visa distribution bar,
   Project stats card, poor monthly chart). In Focus Mode, the cue-list is
   replaced by graphical priority visuals. */

const { useState: useStateOv, useEffect: useEffectOv, useMemo } = React;

const ovFonts = window.JANSA_FONTS;

/* ── Number formatting & helpers ── */
const ovFmt = (n) => (n ?? 0).toLocaleString('fr-FR').replace(/,/g, '\u202f');
const ovSigned = (n) => n > 0 ? `+${n}` : `${n}`;

/* ── Shared card ── */
function OvCard({ children, style, padding = 22, dense }) {
  return (
    <div style={{
      background: 'var(--bg-elev)',
      border: '1px solid var(--line)',
      borderRadius: 18,
      padding: dense ? 16 : padding,
      position:'relative', overflow:'hidden',
      ...style,
    }}>{children}</div>
  );
}

function OvEyebrow({ children, style }) {
  return <div style={{
    fontFamily: ovFonts.ui, fontSize: 10.5, fontWeight: 600,
    letterSpacing:'.12em', textTransform:'uppercase',
    color:'var(--text-3)', ...style,
  }}>{children}</div>;
}

function OvDelta({ value, suffix = '', invert = false }) {
  const good = invert ? value < 0 : value > 0;
  const neut = value === 0 || value == null;
  const color = neut ? 'var(--text-3)' : good ? 'var(--good)' : 'var(--bad)';
  const bg    = neut ? 'var(--neutral-soft)' : good ? 'var(--good-soft)' : 'var(--bad-soft)';
  const arrow = neut ? '—' : value > 0 ? '↑' : '↓';
  return (
    <span style={{
      display:'inline-flex', alignItems:'center', gap: 4,
      padding:'3px 8px', borderRadius: 99,
      background: bg, color,
      fontFamily: ovFonts.num, fontSize: 11, fontWeight: 600,
      fontVariantNumeric:'tabular-nums',
    }}>{arrow} {ovSigned(value)}{suffix}</span>
  );
}

/* ── Hero KPI — large number, eyebrow, sparkline, delta ── */
function HeroKpi({ eyebrow, value, suffix, spark, delta, deltaSuffix, invertDelta, accent = 'var(--accent)', sub, onClick }) {
  return (
    <OvCard style={{ cursor: onClick ? 'pointer' : 'default', transition:'transform 0.2s, border-color 0.2s' }}
      {...(onClick ? { onClick, onMouseEnter: e => e.currentTarget.style.borderColor = 'var(--line-2)',
                       onMouseLeave: e => e.currentTarget.style.borderColor = 'var(--line)' } : {})}>
      {/* accent halo */}
      <div style={{
        position:'absolute', top: -80, right: -80, width: 200, height: 200,
        background: `radial-gradient(circle, ${accent}33, transparent 60%)`,
        pointerEvents:'none',
      }}/>
      <div style={{ display:'flex', justifyContent:'space-between', alignItems:'flex-start' }}>
        <OvEyebrow>{eyebrow}</OvEyebrow>
        {delta != null && <OvDelta value={delta} suffix={deltaSuffix} invert={invertDelta}/>}
      </div>
      <div style={{
        fontFamily: ovFonts.ui, fontWeight: 300, color:'var(--text)',
        fontSize: 56, letterSpacing:'-.03em', lineHeight: 1.05,
        margin: '12px 0 4px', position:'relative',
      }}>
        {value}{suffix && <span style={{ fontSize: 22, color:'var(--text-2)', marginLeft: 4, fontWeight: 400 }}>{suffix}</span>}
      </div>
      {sub && <div style={{ fontSize: 12, color: 'var(--text-3)', marginBottom: 10 }}>{sub}</div>}
      {spark && <OvSpark values={spark} color={accent}/>}
    </OvCard>
  );
}

/* ── Sparkline w/ gradient fill, animated path ── */
function OvSpark({ values, color = 'var(--accent)', height = 34 }) {
  const id = React.useId().replace(/:/g, '');
  if (!values || !values.length) return null;
  const max = Math.max(...values), min = Math.min(...values);
  const W = 280, H = height, pad = 2;
  const n = values.length;
  const xs = values.map((_, i) => pad + (i * (W - 2*pad)) / (n - 1 || 1));
  const ys = values.map(v => max === min ? H/2 : pad + (H - 2*pad) * (1 - (v - min) / (max - min)));
  const line = values.map((_, i) => `${i?'L':'M'}${xs[i].toFixed(1)},${ys[i].toFixed(1)}`).join(' ');
  const area = `${line} L${xs[n-1]},${H} L${xs[0]},${H} Z`;
  return (
    <svg viewBox={`0 0 ${W} ${H}`} style={{ width:'100%', height, display:'block' }}>
      <defs>
        <linearGradient id={id} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor={color} stopOpacity=".32"/>
          <stop offset="100%" stopColor={color} stopOpacity="0"/>
        </linearGradient>
      </defs>
      <path d={area} fill={`url(#${id})`}/>
      <path d={line} fill="none" stroke={color} strokeWidth="1.5" strokeLinejoin="round"
        strokeDasharray="1000" style={{ animation: 'drawLine 1.2s cubic-bezier(.4,0,.2,1) forwards' }}/>
      <circle cx={xs[n-1]} cy={ys[n-1]} r="3" fill={color}/>
    </svg>
  );
}

/* ── KPI Row (4 cards) — Total Docs · Pending · Best Consultant · Best Contractor ── */
function KpiRow({ data, onNavigate }) {
  const trend = (data.weekly || []).map(w => w.closed);
  const pendTrend = (data.weekly || []).map(w => w.opened - w.closed).map((_, i, a) => {
    // running pending estimate
    return Math.max(0, 400 + a.slice(0, i + 1).reduce((s, v) => s + v, 0));
  });

  // Late count: use visa_flow.late if available, else focus p1_overdue if focus active
  const lateCount = data.visa_flow && data.visa_flow.late != null
    ? data.visa_flow.late
    : null;
  const pendingSub = lateCount != null && lateCount > 0
    ? `dont ${ovFmt(lateCount)} en retard`
    : null;

  return (
    <div style={{ display:'grid', gridTemplateColumns:'repeat(4, 1fr)', gap: 14, marginBottom: 20 }}>
      <HeroKpi
        eyebrow="Documents soumis"
        value={ovFmt(data.total_docs)}
        delta={data.total_docs_delta}
        sub={`Semaine ${data.week_num} · run #${data.run_number}`}
        spark={trend}
        accent="#0A84FF"
      />
      <HeroKpi
        eyebrow="Bloquants en attente"
        value={ovFmt(data.pending_blocking)}
        delta={data.pending_blocking_delta}
        invertDelta
        sub={pendingSub}
        spark={pendTrend}
        accent="#FF453A"
      />
      <BestPerformerCard
        eyebrow="Consultant de la semaine"
        name={data.best_consultant.name}
        value={data.best_consultant.pass_rate}
        delta={data.best_consultant.delta}
        medal="A"
        accent="#30D158"
        onClick={() => onNavigate('Consultants')}
      />
      <BestPerformerCard
        eyebrow="Entreprise de la semaine"
        name={data.best_contractor.name}
        value={data.best_contractor.pass_rate}
        delta={data.best_contractor.delta}
        medal="B"
        accent="#FFD60A"
        onClick={() => onNavigate('Contractors')}
      />
    </div>
  );
}

/* ── Best performer card — avatar + gauge + trophy ribbon ── */
function BestPerformerCard({ eyebrow, name, value, delta, medal, accent, onClick }) {
  const initials = name.split(/[\s—·]+/).filter(Boolean).slice(0, 2).map(w => w[0]).join('').toUpperCase();
  return (
    <OvCard
      onClick={onClick}
      style={{ cursor:'pointer', transition:'transform 0.2s, border-color 0.2s' }}
    >
      <div style={{
        position:'absolute', top: -80, right: -80, width: 200, height: 200,
        background: `radial-gradient(circle, ${accent}33, transparent 60%)`,
        pointerEvents:'none',
      }}/>
      <div style={{ display:'flex', justifyContent:'space-between', alignItems:'flex-start' }}>
        <OvEyebrow>{eyebrow}</OvEyebrow>
        {delta != null && <OvDelta value={delta} suffix="pt"/>}
      </div>

      <div style={{ display:'flex', alignItems:'center', gap: 14, marginTop: 14 }}>
        {/* Avatar with rank ribbon */}
        <div style={{ position:'relative', flexShrink: 0 }}>
          <div style={{
            width: 56, height: 56, borderRadius: 14,
            background: `linear-gradient(135deg, ${accent}, ${accent}aa)`,
            display:'flex', alignItems:'center', justifyContent:'center',
            color:'#fff', fontWeight: 700, fontSize: 18, letterSpacing:'-.02em',
            boxShadow: `0 8px 24px -8px ${accent}88`,
          }}>{initials}</div>
          {/* crown */}
          <svg width="18" height="14" viewBox="0 0 18 14" style={{
            position:'absolute', top: -8, left: -4,
            filter: `drop-shadow(0 2px 4px ${accent}80)`,
          }}>
            <path d="M1 12 L3 4 L6 8 L9 2 L12 8 L15 4 L17 12 Z" fill={accent} stroke={accent} strokeWidth="0.5" strokeLinejoin="round"/>
            <circle cx="3" cy="4" r="1.2" fill="#fff"/>
            <circle cx="9" cy="2" r="1.2" fill="#fff"/>
            <circle cx="15" cy="4" r="1.2" fill="#fff"/>
          </svg>
        </div>

        <div style={{ minWidth: 0, flex: 1 }}>
          <div style={{
            fontSize: 14.5, fontWeight: 600, color:'var(--text)', letterSpacing:'-.01em',
            whiteSpace:'nowrap', overflow:'hidden', textOverflow:'ellipsis',
          }}>{name}</div>
          <div style={{
            display:'flex', alignItems:'baseline', gap: 6, marginTop: 6,
          }}>
            <span style={{
              fontFamily: ovFonts.ui, fontSize: 32, fontWeight: 300,
              letterSpacing:'-.03em', color:'var(--text)', lineHeight: 1,
            }}>{value}</span>
            <span style={{ fontSize: 13, color: 'var(--text-2)' }}>%</span>
            <span style={{ fontSize: 11, color:'var(--text-3)', marginLeft: 6 }}>taux de conformité</span>
          </div>
        </div>
      </div>

      {/* Gauge */}
      <div style={{ marginTop: 14, height: 6, borderRadius: 99, background:'var(--bg-chip)', overflow:'hidden' }}>
        <div style={{
          width: `${value}%`, height:'100%',
          background: `linear-gradient(90deg, ${accent}, ${accent}88)`,
          borderRadius: 99,
          animation:'fadeInUp 0.8s cubic-bezier(.4,0,.2,1)',
        }}/>
      </div>
    </OvCard>
  );
}

/* ── Visa flow — 3-stage Sankey-style (replaces old visa bar) ── */
function VisaFlow({ data }) {
  const f = data.visa_flow;
  const total = f.submitted;

  // Stage widths as % of total
  const stages = [
    { label: 'Soumis', value: f.submitted, color:'var(--accent)' },
    { label: 'Répondus', value: f.answered, color:'var(--good)' },
    { label: 'VSO', value: f.vso, color:'var(--good)' },
  ];

  const answeredPct = f.answered / total;
  const pendingPct  = f.pending  / total;

  // Pass ratio from answered
  const vsoPct = f.vso / f.answered;
  const vaoPct = f.vao / f.answered;
  const refPct = f.ref / f.answered;
  const hmPct  = f.hm  / f.answered;

  return (
    <OvCard>
      <div style={{ display:'flex', justifyContent:'space-between', alignItems:'baseline', marginBottom: 18 }}>
        <div>
          <OvEyebrow>Flux de visa · depuis R0</OvEyebrow>
          <div style={{ fontSize: 15, fontWeight: 600, color:'var(--text)', marginTop: 4 }}>
            Où vont les {ovFmt(total)} documents soumis
          </div>
        </div>
      </div>

      {/* Stage 1 → Stage 2 → Stage 3, each row is a stacked horizontal bar */}
      <div style={{ display:'flex', flexDirection:'column', gap: 14 }}>
        <VisaStage label="Tous soumis" value={total} total={total} segments={[
          { label:'Tous', value: total, color:'var(--accent)' },
        ]}/>

        <VisaStage label="Distribution" value={total} total={total} segments={[
          { label:'Répondus', value: f.answered, color:'var(--good)' },
          { label:'En attente', value: f.pending, color:'var(--accent)' },
        ]}/>

        <VisaStage label="Avis rendus" value={f.answered} total={f.answered} segments={[
          { label:'VSO', value: f.vso, color:'#30D158' },
          { label:'VAO', value: f.vao, color:'#FFD60A' },
          { label:'REF', value: f.ref, color:'#FF453A' },
          { label:'HM',  value: f.hm,  color:'#8E8E93' },
        ]}/>

        {f.on_time != null && f.late != null ? (
          <VisaStage label="En attente" value={f.pending} total={f.pending} segments={[
            { label:'Dans les délais', value: f.on_time, color:'#0A84FF' },
            { label:'En retard',       value: f.late,    color:'#FF453A' },
          ]}/>
        ) : (
          <div style={{ display:'flex', justifyContent:'space-between', alignItems:'center' }}>
            <span style={{ fontSize:11.5, color:'var(--text-2)', fontWeight:500 }}>En attente</span>
            <span style={{ fontSize:11.5, color:'var(--text-3)', fontVariantNumeric:'tabular-nums' }}>{ovFmt(f.pending)} · délais non calculés</span>
          </div>
        )}
      </div>
    </OvCard>
  );
}

function VisaStage({ label, value, total, segments }) {
  return (
    <div>
      <div style={{ display:'flex', justifyContent:'space-between', alignItems:'baseline', marginBottom: 6 }}>
        <span style={{ fontSize: 11.5, color:'var(--text-2)', fontWeight: 500 }}>{label}</span>
        <span style={{ fontFamily: ovFonts.num, fontSize: 11.5, color:'var(--text-3)', fontVariantNumeric:'tabular-nums' }}>{ovFmt(value)}</span>
      </div>
      <div style={{ display:'flex', height: 22, borderRadius: 6, overflow:'hidden', gap: 2, background:'var(--bg-chip)' }}>
        {segments.map((s, i) => {
          const pct = (s.value / total) * 100;
          return (
            <div key={i} title={`${s.label}: ${ovFmt(s.value)} (${pct.toFixed(1)}%)`} style={{
              width: `${pct}%`, height:'100%',
              background: s.color,
              display:'flex', alignItems:'center', justifyContent:'flex-start',
              paddingLeft: pct > 8 ? 10 : 0,
              fontSize: 11, fontWeight: 600, color:'#000', fontFamily: ovFonts.num,
              fontVariantNumeric:'tabular-nums',
              minWidth: s.value > 0 ? 3 : 0,
              transition:'width 0.6s cubic-bezier(.4,0,.2,1)',
            }}>
              {pct > 12 && `${s.label} ${ovFmt(s.value)}`}
            </div>
          );
        })}
      </div>
      {/* legend underneath */}
      <div style={{ display:'flex', gap: 14, flexWrap:'wrap', marginTop: 6 }}>
        {segments.map((s, i) => {
          const pct = (s.value / total) * 100;
          return (
            <span key={i} style={{ display:'inline-flex', gap: 6, alignItems:'center', fontSize: 11, color:'var(--text-2)' }}>
              <span style={{ width: 8, height: 8, borderRadius: 2, background: s.color, display:'inline-block' }}/>
              {s.label} · {ovFmt(s.value)} <span style={{ color:'var(--text-3)' }}>({pct.toFixed(1)}%)</span>
            </span>
          );
        })}
      </div>
    </div>
  );
}

/* ── Weekly activity chart (replaces monthly) — area + opened/closed bars ── */
function WeeklyActivity({ data, focusMode }) {
  const W = 820, H = 220, pad = { l: 36, r: 16, t: 20, b: 34 };
  const weekly = data.weekly || [];
  const weeks = focusMode ? weekly.slice(-12) : weekly;
  if (!weeks.length) return <OvCard padding={24}><OvEyebrow>Activit\u00e9</OvEyebrow><div style={{ fontSize: 12, color:'var(--text-3)', padding: '20px 0' }}>Aucune donn\u00e9e d\u2019activit\u00e9.</div></OvCard>;
  const maxVal = Math.max(...weeks.flatMap(w => [w.opened, w.closed]));
  const n = weeks.length;

  const xStep = (W - pad.l - pad.r) / n;
  const xBar = (i, offset = 0) => pad.l + i * xStep + offset;
  const yOf = (v) => pad.t + (H - pad.t - pad.b) * (1 - v / maxVal);

  // Closed area (smooth curve)
  const closedLine = weeks.map((w, i) => `${i ? 'L' : 'M'}${xBar(i, xStep/2)},${yOf(w.closed)}`).join(' ');
  const closedArea = `${closedLine} L${xBar(n-1, xStep/2)},${H - pad.b} L${xBar(0, xStep/2)},${H - pad.b} Z`;

  // Refused line
  const refLine = weeks.map((w, i) => `${i ? 'L' : 'M'}${xBar(i, xStep/2)},${yOf(w.refused * 8)}`).join(' '); // scaled for visibility

  const yTicks = [0, .25, .5, .75, 1].map(k => Math.round(maxVal * k));

  return (
    <OvCard>
      <div style={{ display:'flex', justifyContent:'space-between', alignItems:'baseline', marginBottom: 18 }}>
        <div>
          <OvEyebrow>{focusMode ? 'Activité · 12 dernières semaines' : 'Activité hebdomadaire'}</OvEyebrow>
          <div style={{ fontSize: 15, fontWeight: 600, color:'var(--text)', marginTop: 4 }}>
            Ouverts · Fermés · Refusés
          </div>
        </div>
        <div style={{ display:'flex', gap: 16, fontSize: 11.5, color:'var(--text-2)' }}>
          <span style={{ display:'inline-flex', gap: 6, alignItems:'center' }}>
            <span style={{ width: 10, height: 10, background:'var(--accent)', borderRadius: 2, display:'inline-block' }}/> Ouverts
          </span>
          <span style={{ display:'inline-flex', gap: 6, alignItems:'center' }}>
            <span style={{ width: 10, height: 10, background:'var(--good)', borderRadius: 2, display:'inline-block' }}/> Fermés
          </span>
          <span style={{ display:'inline-flex', gap: 6, alignItems:'center' }}>
            <span style={{ width: 12, height: 2, background:'var(--bad)', display:'inline-block' }}/> Refusés (×8)
          </span>
        </div>
      </div>

      <svg viewBox={`0 0 ${W} ${H}`} style={{ width:'100%', display:'block' }}>
        <defs>
          <linearGradient id="weeklyClosed" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="#30D158" stopOpacity=".5"/>
            <stop offset="100%" stopColor="#30D158" stopOpacity="0"/>
          </linearGradient>
          <linearGradient id="weeklyBar" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="#0A84FF" stopOpacity="1"/>
            <stop offset="100%" stopColor="#0A84FF" stopOpacity=".65"/>
          </linearGradient>
        </defs>

        {/* Grid */}
        {yTicks.map((v, i) => (
          <g key={i}>
            <line x1={pad.l} x2={W - pad.r} y1={yOf(v)} y2={yOf(v)}
              stroke="var(--line)" strokeWidth="1"/>
            <text x={pad.l - 8} y={yOf(v) + 3} textAnchor="end"
              fontFamily={ovFonts.num} fontSize="9.5" fill="var(--text-3)">{v}</text>
          </g>
        ))}

        {/* Opened as bars */}
        {weeks.map((w, i) => {
          const h = (H - pad.t - pad.b) * (w.opened / maxVal);
          return <rect key={i}
            x={xBar(i, xStep*0.2)} y={H - pad.b - h}
            width={xStep * 0.6} height={h}
            rx="2" fill="url(#weeklyBar)" opacity="0.85"/>;
        })}

        {/* Closed as area curve */}
        <path d={closedArea} fill="url(#weeklyClosed)"/>
        <path d={closedLine} fill="none" stroke="#30D158" strokeWidth="1.8"
          strokeDasharray="2000" style={{ animation: 'drawLine 1.4s cubic-bezier(.4,0,.2,1) forwards' }}/>

        {/* Refused line (scaled) */}
        <path d={refLine} fill="none" stroke="#FF453A" strokeWidth="1.4"
          strokeDasharray="4 3" opacity="0.85"/>

        {/* X labels (every other for density) */}
        {weeks.map((w, i) => {
          if (focusMode ? false : (i % 2 !== 0 && i !== weeks.length - 1)) return null;
          return <text key={i}
            x={xBar(i, xStep/2)} y={H - pad.b + 18}
            textAnchor="middle" fontFamily={ovFonts.num}
            fontSize="9.5" fill={w.label.includes('26-S14') ? 'var(--accent)' : 'var(--text-3)'}
            fontWeight={w.label.includes('26-S14') ? 600 : 400}>
            {w.label}
          </text>;
        })}
      </svg>
    </OvCard>
  );
}

/* ── FOCUS MODE visuals — replaces the old priority cue list ── */
function FocusPanel({ data, onNavigate }) {
  const f = data.focus || { focused: 0, p1_overdue: 0, p2_urgent: 0, p3_soon: 0, p4_ok: 0, by_consultant: [] };

  return (
    <div style={{ display:'grid', gridTemplateColumns:'1.4fr 1fr', gap: 14, marginBottom: 20 }}>
      {/* Triage wheel — radial priority */}
      <OvCard padding={24}>
        <div style={{ display:'flex', justifyContent:'space-between', alignItems:'flex-start', marginBottom: 14 }}>
          <div>
            <OvEyebrow style={{ color:'var(--accent)' }}>◎ Focus · Triage</OvEyebrow>
            <div style={{ fontSize: 16, fontWeight: 600, color:'var(--text)', marginTop: 4 }}>Répartition par urgence</div>
          </div>
          <span style={{ fontSize: 12, color:'var(--text-3)' }}>Total focus · <b style={{ color:'var(--text)' }}>{f.focused}</b></span>
        </div>
        <FocusRadial f={f}/>
      </OvCard>

      {/* Waterfall by consultant */}
      <OvCard padding={24}>
        <OvEyebrow style={{ color:'var(--accent)' }}>◎ Focus · par consultant</OvEyebrow>
        <div style={{ fontSize: 16, fontWeight: 600, color:'var(--text)', marginTop: 4, marginBottom: 14 }}>
          Qui doit faire quoi
        </div>
        <FocusByConsultant items={f.by_consultant} onNavigate={onNavigate}/>
      </OvCard>
    </div>
  );
}

/* Radial focus chart: concentric arcs for P1..P4 */
function FocusRadial({ f }) {
  const rings = [
    { key:'p1_overdue', label:'P1 · en retard',  value: f.p1_overdue, color:'#FF453A', r: 98 },
    { key:'p2_urgent',  label:'P2 · urgent ≤5j',  value: f.p2_urgent,  color:'#FF9F0A', r: 80 },
    { key:'p3_soon',    label:'P3 · bientôt ≤15j',value: f.p3_soon,    color:'#FFD60A', r: 62 },
    { key:'p4_ok',      label:'P4 · ok',          value: f.p4_ok,      color:'#30D158', r: 44 },
  ];
  const total = rings.reduce((s, r) => s + r.value, 0);
  const maxValue = Math.max(...rings.map(r => r.value));

  return (
    <div style={{ display:'flex', gap: 28, alignItems:'center' }}>
      <svg viewBox="0 0 240 240" style={{ width: 240, height: 240, flexShrink: 0 }}>
        {rings.map((ring, i) => {
          const pct = ring.value / maxValue;
          const circumference = 2 * Math.PI * ring.r;
          return (
            <g key={ring.key} style={{ transformOrigin:'120px 120px', transform: 'rotate(-90deg)' }}>
              <circle cx="120" cy="120" r={ring.r} fill="none"
                stroke="var(--bg-chip)" strokeWidth="9"/>
              <circle cx="120" cy="120" r={ring.r} fill="none"
                stroke={ring.color} strokeWidth="9" strokeLinecap="round"
                strokeDasharray={`${pct * circumference} ${circumference}`}
                style={{
                  transition:'stroke-dasharray 1s cubic-bezier(.4,0,.2,1)',
                  filter:`drop-shadow(0 0 6px ${ring.color}66)`,
                }}/>
            </g>
          );
        })}
        <text x="120" y="118" textAnchor="middle" dominantBaseline="central"
          fontFamily={ovFonts.ui} fontWeight="200" fontSize="42"
          letterSpacing="-0.03em" fill="var(--text)">{f.focused}</text>
        <text x="120" y="142" textAnchor="middle"
          fontFamily={ovFonts.ui} fontSize="10" fontWeight="600"
          letterSpacing=".12em" fill="var(--text-3)">ACTIONS</text>
      </svg>

      {/* Legend */}
      <div style={{ display:'flex', flexDirection:'column', gap: 10, flex: 1 }}>
        {rings.map(ring => {
          const pct = total ? Math.round((ring.value / total) * 100) : 0;
          return (
            <div key={ring.key} style={{ display:'flex', alignItems:'center', gap: 10 }}>
              <span style={{ width: 10, height: 10, borderRadius: 99, background: ring.color, flexShrink: 0, boxShadow:`0 0 6px ${ring.color}aa` }}/>
              <div style={{ flex: 1, minWidth: 0 }}>
                <div style={{ fontSize: 12, color:'var(--text)', fontWeight: 500 }}>{ring.label}</div>
                <div style={{ height: 3, marginTop: 4, borderRadius: 99, background:'var(--bg-chip)' }}>
                  <div style={{ width:`${pct}%`, height:'100%', background: ring.color, borderRadius: 99 }}/>
                </div>
              </div>
              <div style={{ fontFamily: ovFonts.num, fontSize: 13, fontWeight: 600, color: ring.color, fontVariantNumeric:'tabular-nums', minWidth: 28, textAlign:'right' }}>{ring.value}</div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

/* Stacked horizontal bar per consultant */
function FocusByConsultant({ items, onNavigate }) {
  if (!items || !items.length) return <div style={{ fontSize: 12, color:'var(--text-3)', padding: 12 }}>Aucune donn\u00e9e par consultant.</div>;
  const max = Math.max(...items.map(c => c.p1 + c.p2 + c.p3 + c.p4));
  return (
    <div style={{ display:'flex', flexDirection:'column', gap: 8 }}>
      {items.map((c, i) => {
        const total = c.p1 + c.p2 + c.p3 + c.p4;
        const pct = (total / max) * 100;
        return (
          <button key={c.slug}
            onClick={() => onNavigate('Consultants')}
            style={{
              display:'grid', gridTemplateColumns:'150px 1fr 36px', alignItems:'center', gap: 10,
              padding: '6px 8px', borderRadius: 8, border:'1px solid transparent',
              background:'transparent', cursor:'pointer', fontFamily:'inherit', textAlign:'left',
              transition:'background 0.15s, border-color 0.15s',
            }}
            onMouseEnter={e => { e.currentTarget.style.background = 'var(--bg-elev-2)'; e.currentTarget.style.borderColor = 'var(--line)'; }}
            onMouseLeave={e => { e.currentTarget.style.background = 'transparent'; e.currentTarget.style.borderColor = 'transparent'; }}
          >
            <span style={{ fontSize: 11.5, color:'var(--text-2)', whiteSpace:'nowrap', overflow:'hidden', textOverflow:'ellipsis' }}>{c.name}</span>
            <div style={{ display:'flex', height: 14, borderRadius: 4, overflow:'hidden', background:'var(--bg-chip)' }}>
              {[{ v:c.p1, c:'#FF453A' },{ v:c.p2, c:'#FF9F0A' },{ v:c.p3, c:'#FFD60A' },{ v:c.p4, c:'#30D158' }].map((s, k) => (
                <div key={k} style={{
                  width: `${(s.v / max) * 100}%`, height:'100%', background: s.c,
                  transition:'width 0.6s cubic-bezier(.4,0,.2,1)',
                }}/>
              ))}
            </div>
            <span style={{ fontFamily: ovFonts.num, fontSize: 12, fontWeight: 600, color:'var(--text)', textAlign:'right', fontVariantNumeric:'tabular-nums' }}>{total}</span>
          </button>
        );
      })}
    </div>
  );
}

/* ── Degraded Mode Banner ── */
function OvDegradedBanner() {
  return (
    <div style={{
      background:'var(--warn-soft)', border:'1px solid rgba(255,214,10,0.25)',
      borderRadius:12, padding:'12px 20px', marginBottom:20,
      display:'flex', alignItems:'center', gap:10,
    }}>
      <div style={{ width:8, height:8, borderRadius:'50%', background:'var(--warn)', boxShadow:'0 0 6px var(--warn)', flexShrink:0 }}/>
      <span style={{ fontSize:13, color:'var(--warn)' }}>Mode dégradé — données GED non vérifiées pour ce run</span>
    </div>
  );
}

/* ── Shared label/value row for stat cards ── */
function OvStatRow({ label, value, ok }) {
  const color = ok === true ? 'var(--good)' : ok === false ? 'var(--warn)' : 'var(--text-3)';
  return (
    <div style={{ display:'flex', justifyContent:'space-between', alignItems:'center',
      padding:'8px 0', borderBottom:'1px solid var(--line)' }}>
      <span style={{ fontSize:12.5, color:'var(--text-2)' }}>{label}</span>
      <span style={{ fontSize:12.5, fontWeight:500, color, fontVariantNumeric:'tabular-nums' }}>{value}</span>
    </div>
  );
}

/* ── Project Stats card ── */
function ProjectStatsCard({ stats }) {
  if (!stats) return null;
  return (
    <OvCard style={{ flex:'1 1 220px', minWidth:200 }}>
      <OvEyebrow style={{ marginBottom:12 }}>Statistiques projet</OvEyebrow>
      <OvStatRow label="Consultants" value={stats.total_consultants ?? 0} ok={true}/>
      <OvStatRow label="Entreprises" value={stats.total_contractors ?? 0} ok={true}/>
      <OvStatRow
        label="Délai moyen de visa"
        value={stats.avg_days_to_visa != null ? `${stats.avg_days_to_visa}j` : '—'}
        ok={stats.avg_days_to_visa != null}
      />
      {stats.docs_pending_sas != null && (
        <OvStatRow label="SAS en attente" value={stats.docs_pending_sas}
          ok={stats.docs_pending_sas === 0}/>
      )}
    </OvCard>
  );
}

/* ── System Status card ── */
function SystemStatusCard({ status }) {
  if (!status) return null;
  return (
    <OvCard style={{ flex:'1 1 220px', minWidth:200 }}>
      <OvEyebrow style={{ marginBottom:12 }}>État du système</OvEyebrow>
      <OvStatRow label="Baseline (Run 0)" value={status.has_baseline ? 'Disponible' : 'Manquant'} ok={status.has_baseline}/>
      <OvStatRow label="Export GED" value={status.ged_file_detected ? 'Détecté' : 'Introuvable'} ok={status.ged_file_detected}/>
      <OvStatRow label="GrandFichier" value={status.gf_file_detected ? 'Détecté' : 'Introuvable'} ok={status.gf_file_detected}/>
      <OvStatRow label="Pipeline" value={status.pipeline_running ? 'En cours' : 'Inactif'} ok={!status.pipeline_running}/>
    </OvCard>
  );
}

/* ── Warnings section ── */
function OvWarnings({ warnings }) {
  if (!warnings || warnings.length === 0) return null;
  return (
    <div style={{
      background:'var(--warn-soft)', border:'1px solid rgba(255,214,10,0.22)',
      borderRadius:14, padding:20, marginBottom:20,
    }}>
      <OvEyebrow style={{ color:'var(--warn)', marginBottom:10 }}>Avertissements</OvEyebrow>
      {warnings.map((w, i) => (
        <div key={i} style={{ fontSize:13, color:'var(--text-2)', marginBottom:4, paddingLeft:14, position:'relative' }}>
          <span style={{ position:'absolute', left:0, color:'var(--warn)' }}>•</span>
          {w}
        </div>
      ))}
    </div>
  );
}

/* ── Quick Actions ── */
function QuickActions({ onNavigate }) {
  const [exporting, setExporting] = useStateOv(false);
  const [exportResult, setExportResult] = useStateOv(null);

  const handleExport = async () => {
    if (!window.jansaBridge?.api) return;
    setExporting(true);
    setExportResult(null);
    try {
      const res = await window.jansaBridge.api.export_team_version();
      if (res && res.success) {
        setExportResult({ ok: true });
        if (window.jansaBridge.api.open_file_in_explorer) {
          window.jansaBridge.api.open_file_in_explorer(res.path);
        }
      } else {
        setExportResult({ ok: false });
      }
    } catch (e) {
      setExportResult({ ok: false });
    } finally {
      setExporting(false);
      setTimeout(() => setExportResult(null), 4000);
    }
  };

  const navActions = [
    { label: 'Lancer le pipeline', target: 'Executer' },
    { label: 'Historique des runs', target: 'Runs' },
    { label: 'Consultants', target: 'Consultants' },
    { label: 'Entreprises', target: 'Contractors' },
  ];

  return (
    <OvCard padding={24}>
      <OvEyebrow style={{ marginBottom:14 }}>Actions rapides</OvEyebrow>
      <div style={{ display:'flex', gap:10, flexWrap:'wrap' }}>
        {navActions.map(a => (
          <button key={a.target} onClick={() => onNavigate(a.target)} style={{
            padding:'9px 18px', fontSize:13, fontWeight:500,
            background:'var(--bg-elev-2)', color:'var(--text-2)',
            border:'1px solid var(--line)', borderRadius:9,
            cursor:'pointer', fontFamily:'inherit',
            transition:'border-color 0.15s, color 0.15s',
          }}
          onMouseEnter={e => { e.currentTarget.style.borderColor='var(--accent)'; e.currentTarget.style.color='var(--text)'; }}
          onMouseLeave={e => { e.currentTarget.style.borderColor='var(--line)'; e.currentTarget.style.color='var(--text-2)'; }}
          >{a.label}</button>
        ))}
        <button onClick={handleExport} disabled={exporting} style={{
          padding:'9px 18px', fontSize:13, fontWeight:500,
          background: exportResult ? (exportResult.ok ? 'var(--good-soft)' : 'var(--bad-soft)') : 'var(--accent-soft)',
          color: exportResult ? (exportResult.ok ? 'var(--good)' : 'var(--bad)') : 'var(--accent)',
          border:`1px solid ${exportResult ? (exportResult.ok ? 'rgba(48,209,88,0.3)' : 'rgba(255,69,58,0.3)') : 'var(--accent-border)'}`,
          borderRadius:9, cursor: exporting ? 'wait' : 'pointer',
          fontFamily:'inherit', opacity: exporting ? 0.6 : 1,
          transition:'opacity 0.15s',
        }}>
          {exporting ? 'Export en cours…' : exportResult ? (exportResult.ok ? '✓ Exporté' : '✗ Erreur') : 'Tableau de Suivi VISA'}
        </button>
      </div>
    </OvCard>
  );
}

/* ── Page ── */
function OverviewPage({ focusMode, onNavigate }) {
  const data = window.OVERVIEW;
  return (
    <div style={{ padding: 32, animation: 'fadeInUp 0.4s cubic-bezier(.4,0,.2,1)' }}>
      {/* Degraded mode banner */}
      {data.degraded_mode && <OvDegradedBanner/>}

      {/* Section header */}
      <div style={{ marginBottom: 24 }}>
        <div style={{ fontSize: 11, color:'var(--text-3)', fontFamily: ovFonts.num, letterSpacing:'.08em' }}>
          {focusMode ? 'MODE FOCUS · ' : ''}W{String(data.week_num).padStart(2,'0')} · {data.data_date_str}
        </div>
        <h1 style={{
          fontFamily: ovFonts.ui, fontSize: 44, fontWeight: 300,
          letterSpacing:'-.035em', color:'var(--text)', margin: '6px 0 0',
        }}>
          {focusMode ? 'Ce qui demande votre attention.' : 'Vue d\u2019ensemble.'}
        </h1>
      </div>

      {/* KPI row */}
      <KpiRow data={data} onNavigate={onNavigate}/>

      {/* Focus panel (replaces cue list) */}
      {focusMode && <FocusPanel data={data} onNavigate={onNavigate}/>}

      {/* Visa flow + Weekly activity */}
      <div style={{ display:'grid', gridTemplateColumns: focusMode ? '1fr' : '1.2fr 1fr', gap: 14, marginBottom: 20 }}>
        {!focusMode && <VisaFlow data={data}/>}
        <WeeklyActivity data={data} focusMode={focusMode}/>
      </div>

      {/* Project Stats + System Status (side by side) */}
      <div style={{ display:'flex', gap:14, flexWrap:'wrap', marginBottom:20 }}>
        <ProjectStatsCard stats={data.project_stats}/>
        <SystemStatusCard status={data.system_status}/>
      </div>

      {/* Warnings */}
      <OvWarnings warnings={data.warnings}/>

      {/* Quick Actions */}
      <QuickActions onNavigate={onNavigate}/>
    </div>
  );
}

Object.assign(window, { OverviewPage });
