/* Consultant fiche — Apple/Tesla dark aesthetic
   Data shape unchanged (window.FICHE_DATA from calculator.py).
   Exposes <ConsultantFiche data={…} lang="fr"/>.
*/
const { useMemo, useState, useEffect, useRef } = React;

// ── i18n ────────────────────────────────────────────────────────────────────
const L = {
  fr: {
    project: "P17&CO · Tranche 2", section: "Bilan Visa",
    week: "Semaine", total: "Documents soumis",
    rendered: "Avis rendus", pending: "En attente", refus: "Taux de refus",
    onTime: "dans les délais", late: "en retard",
    vs_lw: "vs sem. précédente", narrative: "Cette semaine",
    b1: "Activité mensuelle", b2: "Évolution cumulative", b3: "Performance par lot",
    month: "Mois", opened: "Ouverts", closed: "Fermés",
    ok: "ok", lateShort: "retard", noActivity: "aucune activité",
    lot: "Lot", tot: "Total",
    healthLots: "Santé par lot", pendingDonut: "en attente",
    critical: "Lots critiques — ouverts en retard",
    refRate: "Taux de refus — top 5",
    source: "Source",
    merged: "GED AxeoBIM + Rapports PDF", gedOnly: "GED AxeoBIM",
    fiche: "Fiche",
    blocking: "Bloquants", nonBlocking: "Non-bloq.",
    blocOk: "bloq. ok", blocLate: "bloq. retard", nbShort: "non-bloq.",
    sasFiche: "Fiche SAS", sasSection: "Conformité SAS",
    sasChecked: "Docs contrôlés", sasPassed: "Conformes",
    sasRefused: "Refusés SAS", sasPassRate: "Taux de conformité",
    sasPending: "En attente SAS", sasContractor: "Entreprise",
    sasRefRate: "Taux refus SAS — par entreprise",
    sasPendingQueue: "File d'attente SAS"
  },
  en: {
    project: "P17&CO · Phase 2", section: "Visa Report",
    week: "Week", total: "Submitted documents",
    rendered: "Responses issued", pending: "Pending", refus: "Rejection rate",
    onTime: "on time", late: "overdue",
    vs_lw: "vs prev. week", narrative: "This week",
    b1: "Monthly activity", b2: "Cumulative trend", b3: "Performance by lot",
    month: "Month", opened: "Opened", closed: "Closed",
    ok: "ok", lateShort: "late", noActivity: "no activity",
    lot: "Lot", tot: "Total",
    healthLots: "Lot health", pendingDonut: "pending",
    critical: "Critical lots — overdue",
    refRate: "Rejection rate — top 5",
    source: "Source",
    merged: "AxeoBIM DMS + PDF reports", gedOnly: "AxeoBIM DMS",
    fiche: "Report",
    blocking: "Blocking", nonBlocking: "Non-blocking",
    blocOk: "blocking ok", blocLate: "blocking late", nbShort: "non-blocking",
    sasFiche: "SAS Report", sasSection: "SAS Conformity",
    sasChecked: "Docs checked", sasPassed: "Conformant",
    sasRefused: "SAS refused", sasPassRate: "Conformity rate",
    sasPending: "Awaiting SAS", sasContractor: "Contractor",
    sasRefRate: "SAS refusal rate — by contractor",
    sasPendingQueue: "SAS queue"
  }
};

// ── Tokens — use CSS custom props so theme swap works ───────────────────────
const C = {
  bg:       "var(--bg)",
  surf:     "var(--bg-elev)",
  surf2:    "var(--bg-elev-2)",
  surf3:    "var(--bg-chip)",
  line:     "var(--line)",
  line2:    "var(--line-2)",
  text:     "var(--text)",
  text2:    "var(--text-2)",
  text3:    "var(--text-3)",
  accent:   "var(--accent)",
};
// Status — muted, luminous, neon-restrained; match existing semantics
const TOK = {
  VSO:{ ink:"var(--good)", tint:"var(--good-soft)",  bar:"#30D158" },
  FAV:{ ink:"var(--good)", tint:"var(--good-soft)",  bar:"#30D158" },
  VAO:{ ink:"var(--warn)", tint:"var(--warn-soft)",  bar:"#FFD60A" },
  SUS:{ ink:"var(--warn)", tint:"var(--warn-soft)",  bar:"#FFD60A" },
  REF:{ ink:"var(--bad)",  tint:"var(--bad-soft)",   bar:"#FF453A" },
  DEF:{ ink:"var(--bad)",  tint:"var(--bad-soft)",   bar:"#FF453A" },
  HM: { ink:"var(--neutral)", tint:"var(--neutral-soft)", bar:"#8E8E93" },
  OPEN:{ink:"var(--accent)", tint:"var(--accent-soft)",  bar:"#0A84FF" },
  NB:  {ink:"var(--text-3)",  tint:"rgba(99,99,102,.14)", bar:"#636366" }
};
const tokFor = (code) => TOK[code] || TOK.HM;

// ── Helpers ─────────────────────────────────────────────────────────────────
const fmt = (n) => (n ?? 0).toLocaleString("fr-FR").replace(/,/g, "\u202f");
const pct = (n, d) => (d ? Math.round((n / d) * 1000) / 10 : 0);
const signed = (n) => (n > 0 ? `+${n}` : `${n}`);

// Typography stacks
const FONT_UI = "'SF Pro Display','SF Pro Text','Inter',-apple-system,BlinkMacSystemFont,'Helvetica Neue',sans-serif";
const FONT_NUM = "'SF Mono','JetBrains Mono','Menlo',monospace";

// ── Atoms ───────────────────────────────────────────────────────────────────
function Dot({ c, size = 8 }) {
  return <span style={{
    display:"inline-block", width:size, height:size, borderRadius:99,
    background:c, verticalAlign:"middle"
  }}/>;
}

function Eyebrow({ children, style }) {
  return <div style={{
    fontFamily: FONT_UI, fontSize: 11, fontWeight: 500,
    letterSpacing: ".08em", textTransform: "uppercase", color: C.text3,
    ...style
  }}>{children}</div>;
}

function BlockHead({ num, title, right }) {
  return (
    <div style={{
      display:"flex", alignItems:"baseline", justifyContent:"space-between",
      marginBottom: 24, paddingBottom: 16,
      borderBottom: `1px solid ${C.line}`
    }}>
      <div style={{ display:"flex", alignItems:"baseline", gap: 16 }}>
        <span style={{
          fontFamily: FONT_NUM, fontSize: 12, color: C.text3, letterSpacing:".04em"
        }}>{num}</span>
        <h2 style={{
          fontFamily: FONT_UI, fontSize: 28, fontWeight: 600, letterSpacing: "-.02em",
          color: C.text, margin: 0
        }}>{title}</h2>
      </div>
      {right}
    </div>
  );
}

// ── Masthead ────────────────────────────────────────────────────────────────
function Masthead({ data, t, onBack }) {
  const c = data.consultant;
  const h = data.header;
  const isSas = data.is_sas_fiche;
  return (
    <header style={{
      padding: "32px 0 40px",
      borderBottom: `1px solid ${C.line}`
    }}>
      {onBack && (
        <button onClick={onBack} style={{
          display:"inline-flex", alignItems:"center", gap: 6,
          padding:"6px 12px 6px 10px", borderRadius: 99,
          background: C.surf2, border: `1px solid ${C.line}`,
          color: C.text2, fontFamily: FONT_UI, fontSize: 12, fontWeight: 500,
          cursor:"pointer", marginBottom: 20,
          transition:"border-color 0.2s, color 0.2s"
        }}
          onMouseEnter={e => { e.currentTarget.style.borderColor = "var(--line-2)"; e.currentTarget.style.color = C.text; }}
          onMouseLeave={e => { e.currentTarget.style.borderColor = C.line; e.currentTarget.style.color = C.text2; }}
        >
          <svg width="12" height="12" viewBox="0 0 12 12" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round">
            <path d="M7.5 2 L3.5 6 L7.5 10"/>
          </svg>
          Retour aux consultants
        </button>
      )}
      <div style={{
        display:"flex", justifyContent:"space-between",
        fontFamily: FONT_NUM, fontSize: 11, color: C.text3, letterSpacing:".08em"
      }}>
        <span>{t.project.toUpperCase()} — {(isSas ? t.sasSection : t.section).toUpperCase()}</span>
        <span>W{String(h.week_num).padStart(2,"0")} · {h.data_date_str}</span>
      </div>

      <div style={{ display:"flex", alignItems:"flex-end", gap:48, marginTop: 36 }}>
        <div style={{ flex: 1 }}>
          <Eyebrow style={{ marginBottom: 12 }}>
            {isSas ? t.sasFiche : `${t.fiche} · ${String(c.id).padStart(2,"0")} / 14`}
          </Eyebrow>
          <h1 style={{
            fontFamily: FONT_UI, fontWeight: 600, color: C.text,
            fontSize: 72, letterSpacing: "-.035em", lineHeight: 1,
            margin: "6px 0 14px"
          }}>{c.display_name}</h1>
          <div style={{
            fontFamily: FONT_UI, fontWeight: 400, fontSize: 17, color: C.text2
          }}>
            {isSas ? t.sasSection : `${c.role} · ${c.merge_key ? t.merged : t.gedOnly}`}
          </div>
        </div>

        <div style={{ textAlign: "right", minWidth: 240 }}>
          <Eyebrow>{isSas ? t.sasChecked : t.total}</Eyebrow>
          <div style={{
            fontFamily: FONT_UI, fontWeight: 200, color: C.text,
            fontSize: 104, letterSpacing: "-.05em", lineHeight: .92,
            marginTop: 6,
            background: "linear-gradient(180deg, #FFFFFF 0%, #9A9AA0 100%)",
            WebkitBackgroundClip: "text", WebkitTextFillColor: "transparent"
          }}>{fmt(isSas ? (h.checked ?? h.total) : h.total)}</div>
        </div>
      </div>
    </header>
  );
}

// ── Hero KPI band — Apple-style glass cards ─────────────────────────────────
function HeroStats({ data, t, onDrilldown }) {
  const h = data.header;
  const d = data.week_delta || {};
  const isSas = data.is_sas_fiche;
  const refusRate = pct(h.s3_count, h.answered);

  const last = (data.bloc1 || []).slice(-12);
  const sparkRendered = last.map(r => r.doc_ferme);
  const sparkOpen = last.map(r => r.open_ok + r.open_late);
  const sparkRefus = last.map(r => (r.doc_ferme ? Math.round((r.s3/r.doc_ferme)*1000)/10 : 0));
  const sparkPass = last.map(r => r.pass_rate ?? 0);

  const stats = isSas ? [
    {
      eyebrow: t.sasPassed,
      value: fmt((h.vso_count ?? 0) + (h.vao_count ?? 0)),
      mainDrillKey: "answered",
      chips: [
        { label: "VSO", n: h.vso_count ?? h.s1_count, tone: TOK.VSO, drillKey: "s1" },
        { label: "VAO", n: h.vao_count ?? h.s2_count, tone: TOK.VAO, drillKey: "s2" },
        { label: "REF", n: h.ref_count ?? h.s3_count, tone: TOK.REF, drillKey: "s3" }
      ],
      delta: (d.vso||0)+(d.vao||0),
      spark: sparkRendered, tone: TOK.VSO
    },
    {
      eyebrow: t.sasPending,
      value: fmt(h.pending_count ?? h.open_count),
      mainDrillKey: "open_count",
      chips: [
        { label: t.onTime, n: h.pending_ok ?? h.open_ok, tone: TOK.OPEN, drillKey: "open_ok" },
        { label: t.late,   n: h.pending_late ?? h.open_late, tone: TOK.REF, drillKey: "open_late" }
      ],
      delta: d.pending ?? d.open ?? 0, invertDelta: true,
      spark: sparkOpen, tone: TOK.OPEN
    },
    {
      eyebrow: t.sasPassRate,
      value: `${h.pass_rate ?? 0}%`,
      mainDrillKey: null,
      chips: [
        { label: `${(h.vso_count??0)+(h.vao_count??0)}/${h.checked??h.answered}`, n: null, tone: TOK.VSO, drillKey: null }
      ],
      delta: d.ref_rate != null ? -d.ref_rate : 0, deltaSuffix: "pt", invertDelta: false,
      spark: sparkPass, tone: TOK.VSO
    }
  ] : [
    {
      eyebrow: t.rendered,
      value: fmt(h.answered),
      mainDrillKey: "answered",
      chips: [
        { label: h.s1, n: h.s1_count, tone: TOK.VSO, drillKey: "s1" },
        { label: h.s2, n: h.s2_count, tone: TOK.VAO, drillKey: "s2" },
        { label: h.s3, n: h.s3_count, tone: TOK.REF, drillKey: "s3" },
        { label: "HM", n: h.hm_count, tone: TOK.HM,  drillKey: "hm" }
      ],
      delta: (d.s1||0)+(d.s2||0)+(d.s3||0)+(d.hm||0),
      spark: sparkRendered, tone: TOK.VSO
    },
    {
      eyebrow: t.pending,
      value: fmt(h.open_blocking ?? h.open_count),
      mainDrillKey: "open_blocking",
      chips: [
        { label: t.onTime, n: h.open_blocking_ok ?? h.open_ok, tone: TOK.OPEN, drillKey: "open_blocking_ok" },
        { label: t.late,   n: h.open_blocking_late ?? h.open_late, tone: TOK.REF, drillKey: "open_blocking_late" },
        ...(h.open_non_blocking ? [{ label: "non-bloq.", n: h.open_non_blocking, tone: TOK.NB, drillKey: "open_non_blocking" }] : [])
      ],
      delta: d.open_blocking ?? d.open ?? 0, invertDelta: true,
      spark: sparkOpen, tone: TOK.OPEN
    },
    {
      eyebrow: t.refus,
      value: `${refusRate}%`,
      mainDrillKey: null,
      chips: [
        { label: `${h.s3_count}/${h.answered}`, n: null, tone: TOK.REF, drillKey: "s3" }
      ],
      delta: d.refus_rate_pct ?? 0, deltaSuffix: "pt", invertDelta: true,
      spark: sparkRefus, tone: TOK.REF
    }
  ];

  return (
    <section style={{
      display:"grid", gridTemplateColumns:"1fr 1fr 1fr", gap: 14,
      marginTop: 40
    }}>
      {stats.map((s, i) => (
        <div key={i} style={{
          position: "relative",
          background: `linear-gradient(180deg, ${C.surf2} 0%, ${C.surf} 100%)`,
          border: `1px solid ${C.line}`,
          borderRadius: 20,
          padding: "22px 22px 20px",
          overflow: "hidden"
        }}>
          {/* Corner accent */}
          <div style={{
            position:"absolute", top:-80, right:-80, width:180, height:180,
            background:`radial-gradient(circle, ${s.tone.tint} 0%, transparent 60%)`,
            pointerEvents:"none"
          }}/>

          <div style={{ display:"flex", justifyContent:"space-between", alignItems:"center" }}>
            <Eyebrow>{s.eyebrow}</Eyebrow>
            {s.delta !== 0 && s.delta != null ? (
              <DeltaBadge value={s.delta} suffix={s.deltaSuffix||""} invert={s.invertDelta}/>
            ) : <span style={{color:C.text3, fontFamily:FONT_NUM, fontSize:11}}>—</span>}
          </div>

          <div
            onClick={s.mainDrillKey && onDrilldown ? () => onDrilldown({ filterKey: s.mainDrillKey, label: s.eyebrow }) : undefined}
            title={s.mainDrillKey && onDrilldown ? "Voir les documents" : undefined}
            style={{
              fontFamily: FONT_UI, fontWeight: 300, color: C.text,
              fontSize: 72, letterSpacing: "-.035em", lineHeight: 1,
              margin: "14px 0 6px",
              cursor: s.mainDrillKey && onDrilldown ? "pointer" : "default",
          }}>{s.value}</div>

          <Sparkline values={s.spark} color={s.tone.bar}/>

          <div style={{
            display:"flex", flexWrap:"wrap", gap: 6, marginTop: 14
          }}>
            {s.chips.map((c, j) => (
              <Chip key={j} label={c.label} n={c.n} tone={c.tone}
                onClick={c.drillKey && onDrilldown ? () => onDrilldown({ filterKey: c.drillKey, label: `${s.eyebrow} — ${c.label}` }) : undefined}
              />
            ))}
          </div>
        </div>
      ))}
    </section>
  );
}

function Chip({ label, n, tone, onClick }) {
  return (
    <span onClick={onClick} style={{
      display:"inline-flex", alignItems:"center", gap: 6,
      padding: "4px 10px", borderRadius: 99,
      background: tone.tint,
      color: tone.ink,
      fontFamily: FONT_UI, fontSize: 11.5, fontWeight: 500,
      border: `1px solid ${tone.tint}`,
      cursor: onClick ? "pointer" : "default",
    }}>
      <Dot c={tone.bar} size={6}/>
      <span>{label}</span>
      {n != null && (
        <span style={{ fontFamily: FONT_NUM, color: tone.ink, opacity:.85 }}>{n}</span>
      )}
    </span>
  );
}

function DeltaBadge({ value, suffix, invert }) {
  const good = invert ? value < 0 : value > 0;
  const neut = value === 0;
  const tone = neut ? TOK.HM : good ? TOK.VSO : TOK.REF;
  const arrow = neut ? "—" : value > 0 ? "↑" : "↓";
  return (
    <span style={{
      display:"inline-flex", alignItems:"center", gap: 4,
      padding:"3px 9px", borderRadius: 99,
      background: tone.tint, color: tone.ink,
      fontFamily: FONT_NUM, fontSize: 11, fontWeight: 500
    }}>
      {arrow} {signed(value)}{suffix}
    </span>
  );
}

// ── Sparkline with gradient fill ────────────────────────────────────────────
function Sparkline({ values, color = C.accent, height = 32 }) {
  if (!values || !values.length) return null;
  const max = Math.max(...values), min = Math.min(...values);
  const W = 240, H = height, pad = 2;
  const n = values.length;
  const xs = values.map((_, i) => pad + (i * (W - 2*pad)) / (n - 1 || 1));
  const ys = values.map(v => max === min ? H/2 :
    pad + (H - 2*pad) * (1 - (v - min) / (max - min)));
  const line = values.map((_, i) => `${i?"L":"M"}${xs[i].toFixed(1)},${ys[i].toFixed(1)}`).join(" ");
  const area = `${line} L${xs[n-1]},${H} L${xs[0]},${H} Z`;
  const gid = "sg-" + Math.random().toString(36).slice(2,8);
  return (
    <svg viewBox={`0 0 ${W} ${H}`} style={{ width:"100%", height, display:"block" }}>
      <defs>
        <linearGradient id={gid} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor={color} stopOpacity=".32"/>
          <stop offset="100%" stopColor={color} stopOpacity="0"/>
        </linearGradient>
      </defs>
      <path d={area} fill={`url(#${gid})`}/>
      <path d={line} fill="none" stroke={color} strokeWidth="1.4" strokeLinejoin="round"/>
      <circle cx={xs[n-1]} cy={ys[n-1]} r="2.6" fill={color}/>
    </svg>
  );
}

// ── Narrative ───────────────────────────────────────────────────────────────
function Narrative({ data, t, lang }) {
  const h = data.header;
  const d = data.week_delta || {};

  if (data.is_sas_fiche) {
    const sasText = lang === "fr"
      ? `Semaine ${h.week_num} — ${signed(d.total||0)} document${Math.abs(d.total||0)>1?"s":""} soumis au SAS, ${signed(d.checked||0)} contrôlé${Math.abs(d.checked||0)>1?"s":""}. Taux de conformité ${h.pass_rate ?? 0}% (${signed(-(d.ref_rate||0))} pt). En attente : ${h.pending_count ?? h.open_count}.`
      : `Week ${h.week_num} — ${signed(d.total||0)} document${Math.abs(d.total||0)>1?"s":""} submitted to SAS, ${signed(d.checked||0)} checked. Conformity rate ${h.pass_rate ?? 0}% (${signed(-(d.ref_rate||0))} pt). Pending: ${h.pending_count ?? h.open_count}.`;
    return (
      <section style={{ padding:"48px 0 8px" }}>
        <Eyebrow style={{ marginBottom: 14 }}>— {t.narrative}</Eyebrow>
        <p style={{
          fontFamily: FONT_UI, fontWeight: 400, color: C.text,
          fontSize: 28, lineHeight: 1.35, letterSpacing: "-.015em",
          maxWidth: "58ch", margin: 0
        }}>{sasText}</p>
      </section>
    );
  }

  const refusRate = pct(h.s3_count, h.answered);
  const text = lang === "fr"
    ? `Semaine ${h.week_num} — ${signed(d.total||0)} document${Math.abs(d.total||0)>1?"s":""} soumis, ${signed((d.s1||0)+(d.s2||0)+(d.s3||0)+(d.hm||0))} avis rendus. Taux de refus ${refusRate}% (${signed(d.refus_rate_pct||0)} pt). Backlog bloquant en retard : ${h.open_blocking_late ?? h.open_late} (${signed((d.open_blocking_late ?? d.open_late)||0)}).`
    : `Week ${h.week_num} — ${signed(d.total||0)} document${Math.abs(d.total||0)>1?"s":""} submitted, ${signed((d.s1||0)+(d.s2||0)+(d.s3||0)+(d.hm||0))} responses issued. Rejection rate ${refusRate}% (${signed(d.refus_rate_pct||0)} pt). Blocking overdue backlog: ${h.open_blocking_late ?? h.open_late} (${signed((d.open_blocking_late ?? d.open_late)||0)}).`;

  return (
    <section style={{ padding:"48px 0 8px" }}>
      <Eyebrow style={{ marginBottom: 14 }}>— {t.narrative}</Eyebrow>
      <p style={{
        fontFamily: FONT_UI, fontWeight: 400, color: C.text,
        fontSize: 28, lineHeight: 1.35, letterSpacing: "-.015em",
        maxWidth: "58ch", margin: 0
      }}>{text}</p>
    </section>
  );
}

// ── Tables: shared style tokens ─────────────────────────────────────────────
const TH = {
  fontFamily: FONT_UI, fontSize: 11, fontWeight: 600,
  letterSpacing: ".06em", textTransform: "uppercase", color: C.text3,
  padding: "12px 10px", textAlign: "right",
  borderBottom: `1px solid ${C.line2}`
};
const TD = {
  fontFamily: FONT_NUM, fontSize: 13,
  padding: "10px 10px", textAlign: "right",
  borderBottom: `1px solid ${C.line}`,
  color: C.text, fontVariantNumeric: "tabular-nums"
};

// ── Bloc 1 ──────────────────────────────────────────────────────────────────
function Bloc1({ data, t }) {
  const rows = data.bloc1;
  const s1 = TOK.VSO, s2 = TOK.VAO, s3 = TOK.REF, hm = TOK.HM;

  return (
    <section style={{ marginTop: 64 }}>
      <BlockHead num="01" title={t.b1}/>

      <div style={{
        background: C.surf, border: `1px solid ${C.line}`,
        borderRadius: 16, overflow: "hidden"
      }}>
        <table style={{ width:"100%", borderCollapse:"collapse", tableLayout:"fixed" }}>
          <colgroup>
            <col style={{width:"11%"}}/>
            <col style={{width:"8%"}}/><col style={{width:"8%"}}/>
            <col style={{width:"8%"}}/><col style={{width:"6%"}}/>
            <col style={{width:"8%"}}/><col style={{width:"6%"}}/>
            <col style={{width:"8%"}}/><col style={{width:"6%"}}/>
            <col style={{width:"8%"}}/><col style={{width:"6%"}}/>
            <col style={{width:"9%"}}/>
            <col style={{width:"8%"}}/>
          </colgroup>
          <thead>
            <tr>
              <th style={{...TH, textAlign:"left", paddingLeft:20}}>{t.month}</th>
              <th style={TH}>{t.opened}</th>
              <th style={TH}>{t.closed}</th>
              <th style={{...TH, color:s1.ink}} colSpan="2">{data.header.s1}</th>
              <th style={{...TH, color:s2.ink}} colSpan="2">{data.header.s2}</th>
              <th style={{...TH, color:s3.ink}} colSpan="2">{data.header.s3}</th>
              <th style={TH} colSpan="2">HM</th>
              <th style={{...TH, textAlign:"left", paddingLeft:16, color:TOK.OPEN.ink}}>Bloquants</th>
              <th style={{...TH, color:TOK.NB.ink}}>Non-bloq.</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r, i) => {
              const hiBg = r.is_current ? "rgba(10,132,255,0.06)" : "transparent";
              return (
                <tr key={i} style={{ background: hiBg }}>
                  <td style={{
                    ...TD, textAlign:"left", paddingLeft: 20,
                    fontFamily: FONT_UI, fontSize: 13.5,
                    fontWeight: r.is_current ? 600 : 400,
                    color: r.is_current ? C.accent : C.text
                  }}>
                    {r.label}
                  </td>
                  <td style={{...TD, color: TOK.OPEN.ink}}>{r.nvx || <span style={{color:C.text3}}>·</span>}</td>
                  <td style={{...TD, color: TOK.VSO.ink}}>{r.doc_ferme || <span style={{color:C.text3}}>·</span>}</td>

                  <td style={{...TD, color:s1.ink, fontWeight:500}}>{r.s1 || <span style={{color:C.text3}}>·</span>}</td>
                  <td style={{...TD, color:C.text3, fontSize:11}}>{r.s1_pct != null ? `${r.s1_pct}%` : "—"}</td>

                  <td style={{...TD, color:s2.ink, fontWeight:500}}>{r.s2 || <span style={{color:C.text3}}>·</span>}</td>
                  <td style={{...TD, color:C.text3, fontSize:11}}>{r.s2_pct != null ? `${r.s2_pct}%` : "—"}</td>

                  <td style={{...TD, color:s3.ink, fontWeight:500}}>{r.s3 || <span style={{color:C.text3}}>·</span>}</td>
                  <td style={{...TD, color:C.text3, fontSize:11}}>{r.s3_pct != null ? `${r.s3_pct}%` : "—"}</td>

                  <td style={{...TD, color:hm.ink}}>{r.hm || <span style={{color:C.text3}}>·</span>}</td>
                  <td style={{...TD, color:C.text3, fontSize:11}}>{r.hm_pct != null ? `${r.hm_pct}%` : "—"}</td>

                  <td style={{...TD, textAlign:"left", paddingLeft:16}}>
                    <span style={{display:"inline-flex", gap:8, fontFamily:FONT_NUM, fontSize:11.5}}>
                      <span style={{color:TOK.OPEN.ink}}>{r.open_blocking_ok ?? r.open_ok}</span>
                      <span style={{color:C.text3}}>·</span>
                      <span style={{color:TOK.REF.ink}}>{r.open_blocking_late ?? r.open_late}</span>
                    </span>
                  </td>
                  <td style={{...TD, color:TOK.NB.ink, opacity:0.7}}>{r.open_nb ?? 0}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      <div style={{
        display:"flex", gap:24, marginTop:16, flexWrap:"wrap",
        fontFamily: FONT_UI, fontSize:11, color: C.text2
      }}>
        <span style={{display:"inline-flex",gap:6,alignItems:"center"}}>
          <Dot c={TOK.OPEN.bar}/> bloquants dans les délais
        </span>
        <span style={{display:"inline-flex",gap:6,alignItems:"center"}}>
          <Dot c={TOK.REF.bar}/> bloquants en retard
        </span>
        <span style={{display:"inline-flex",gap:6,alignItems:"center"}}>
          <Dot c={TOK.NB.bar}/> non-bloquants
        </span>
      </div>
    </section>
  );
}

// ── Bloc 2 — stacked area chart ─────────────────────────────────────────────
function Bloc2({ data, t }) {
  const b2 = data.bloc2;
  const [hover, setHover] = useState(null);

  const W = 960, H = 320, pad = { l:56, r:24, t:24, b:36 };
  const n = b2.labels.length;
  const maxY = Math.max(...b2.totals);
  const xOf = (i) => pad.l + (i * (W - pad.l - pad.r)) / (n - 1);
  const yOf = (v) => pad.t + (H - pad.t - pad.b) * (1 - v / maxY);

  const stack = b2.labels.map((_, i) => {
    const s1 = b2.s1_series[i], s2 = b2.s2_series[i], s3 = b2.s3_series[i];
    const hm = b2.hm_series[i];
    const ob = (b2.open_blocking_series || b2.open_series)[i];
    const nb = (b2.open_nb_series || [])[i] || 0;
    return {
      s1, s2:s1+s2, s3:s1+s2+s3, hm:s1+s2+s3+hm,
      ob:s1+s2+s3+hm+ob,
      total:s1+s2+s3+hm+ob+nb
    };
  });

  const area = (keyLo, keyHi, color) => {
    const top = b2.labels.map((_, i) => `${xOf(i)},${yOf(stack[i][keyHi])}`).join(" L");
    const bot = b2.labels.slice().reverse().map((_, i) => {
      const idx = n - 1 - i;
      return `${xOf(idx)},${keyLo ? yOf(stack[idx][keyLo]) : yOf(0)}`;
    }).join(" L");
    return <path d={`M${top} L${bot} Z`} fill={color} opacity=".85"/>;
  };

  const yTicks = [0,.25,.5,.75,1].map(k => Math.round(maxY * k));

  return (
    <section style={{ marginTop: 64 }}>
      <BlockHead num="02" title={t.b2}/>

      <div style={{
        background: C.surf,
        border: `1px solid ${C.line}`,
        borderRadius: 16,
        padding: "24px 16px 12px"
      }}>
        <svg viewBox={`0 0 ${W} ${H}`} style={{ width:"100%", display:"block" }}>
          {yTicks.map((v, i) => (
            <g key={i}>
              <line x1={pad.l} x2={W-pad.r} y1={yOf(v)} y2={yOf(v)}
                    stroke={C.line} strokeWidth="1"/>
              <text x={pad.l-10} y={yOf(v)+3} textAnchor="end"
                    fontFamily={FONT_NUM} fontSize="10" fill={C.text3}>
                {fmt(v)}
              </text>
            </g>
          ))}

          {area(null,    "s1",   TOK.VSO.bar)}
          {area("s1",    "s2",   TOK.VAO.bar)}
          {area("s2",    "s3",   TOK.REF.bar)}
          {area("s3",    "hm",   TOK.HM.bar)}
          {area("hm",    "ob",   TOK.OPEN.bar)}
          {area("ob",  "total",  TOK.NB.bar)}

          <path
            d={b2.totals.map((v,i) => `${i?"L":"M"}${xOf(i)},${yOf(v)}`).join(" ")}
            fill="none" stroke={C.text} strokeWidth="1.5" opacity=".9"
          />

          {b2.totals.map((v, i) => (
            <g key={i}
               onMouseEnter={() => setHover(i)}
               onMouseLeave={() => setHover(null)}
               style={{cursor:"pointer"}}>
              <circle cx={xOf(i)} cy={yOf(v)} r="4" fill={C.bg} stroke={C.text} strokeWidth="1.5"/>
              <circle cx={xOf(i)} cy={yOf(v)} r="14" fill="transparent"/>
            </g>
          ))}

          {b2.labels.map((l, i) => (
            <text key={i} x={xOf(i)} y={H-pad.b+18} textAnchor="middle"
                  fontFamily={FONT_NUM} fontSize="10" fill={C.text3}>
              {l}
            </text>
          ))}

          {hover != null && (
            <g>
              <line x1={xOf(hover)} x2={xOf(hover)} y1={pad.t} y2={H-pad.b}
                    stroke={C.text2} strokeDasharray="2 4" strokeWidth="1"/>
              <g transform={`translate(${Math.min(xOf(hover)+12, W-190)}, ${pad.t+8})`}>
                <rect width="178" height="122" rx="10" fill={C.surf2} stroke={C.line2} strokeWidth="1"/>
                <text x="12" y="22" fontFamily={FONT_UI} fontWeight="600" fontSize="13" fill={C.text}>
                  {b2.labels[hover]} · {fmt(b2.totals[hover])}
                </text>
                {[
                  {k:"s1_series",            c:TOK.VSO,  lbl:data.header.s1},
                  {k:"s2_series",            c:TOK.VAO,  lbl:data.header.s2},
                  {k:"s3_series",            c:TOK.REF,  lbl:data.header.s3},
                  {k:"hm_series",            c:TOK.HM,   lbl:"HM"},
                  {k:"open_blocking_series", c:TOK.OPEN, lbl:"Bloquants"},
                  {k:"open_nb_series",       c:TOK.NB,   lbl:"Non-bloq."}
                ].map((row,i) => (
                  <g key={i} transform={`translate(12, ${42+i*14})`}>
                    <circle cx="4" cy="-4" r="3" fill={row.c.bar}/>
                    <text x="14" y="0" fontFamily={FONT_NUM} fontSize="10.5" fill={C.text2}>
                      {row.lbl}
                    </text>
                    <text x="168" y="0" textAnchor="end" fontFamily={FONT_NUM} fontSize="10.5" fill={C.text}>
                      {fmt(b2[row.k] ? b2[row.k][hover] : 0)}
                    </text>
                  </g>
                ))}
              </g>
            </g>
          )}
        </svg>

        <div style={{
          display:"flex", gap:18, marginTop:4, padding:"14px 8px 6px",
          borderTop: `1px solid ${C.line}`,
          fontFamily: FONT_UI, fontSize:11, color: C.text2, flexWrap:"wrap"
        }}>
          {[
            {c:TOK.VSO,  l:data.header.s1},
            {c:TOK.VAO,  l:data.header.s2},
            {c:TOK.REF,  l:data.header.s3},
            {c:TOK.HM,   l:"HM"},
            {c:TOK.OPEN, l:"Bloquants"},
            {c:TOK.NB,   l:"Non-bloq."}
          ].map((x,i)=>(
            <span key={i} style={{display:"inline-flex", gap:6, alignItems:"center"}}>
              <Dot c={x.c.bar}/> {x.l}
            </span>
          ))}
        </div>
      </div>
    </section>
  );
}

// ── Bloc 3 ──────────────────────────────────────────────────────────────────
function Bloc3({ data, t, onDrilldown }) {
  const b3 = data.bloc3;
  const isSas = data.is_sas_fiche;
  return (
    <section style={{ marginTop: 64 }}>
      <BlockHead num="03" title={t.b3}/>

      {/* Legend for the lot health bar — so readers know what the colored slices are */}
      <div style={{
        display:"flex", gap:18, flexWrap:"wrap", marginBottom: 14,
        fontFamily: FONT_UI, fontSize: 11, color: C.text2
      }}>
        <span style={{display:"inline-flex",gap:6,alignItems:"center"}}><Dot c={TOK.VSO.bar}/> {b3.s1}</span>
        <span style={{display:"inline-flex",gap:6,alignItems:"center"}}><Dot c={TOK.VAO.bar}/> {b3.s2}</span>
        <span style={{display:"inline-flex",gap:6,alignItems:"center"}}><Dot c={TOK.REF.bar}/> {b3.s3}</span>
        <span style={{display:"inline-flex",gap:6,alignItems:"center"}}><Dot c={TOK.HM.bar}/> HM</span>
        <span style={{display:"inline-flex",gap:6,alignItems:"center"}}><Dot c={TOK.OPEN.bar}/> {t.onTime}</span>
        <span style={{display:"inline-flex",gap:6,alignItems:"center"}}>
          <span style={{
            display:"inline-block", width:10, height:10, borderRadius:2,
            background:`repeating-linear-gradient(45deg, #FF453A 0 2px, rgba(255,69,58,.35) 2px 4px)`
          }}/> {t.late}
        </span>
      </div>

      <div style={{ display:"grid", gridTemplateColumns:"1.7fr 1fr", gap:28 }}>
        <div style={{
          background: C.surf, border: `1px solid ${C.line}`,
          borderRadius: 16, overflow: "hidden"
        }}>
          <table style={{ width:"100%", borderCollapse:"collapse" }}>
            <thead>
              <tr>
                <th style={{...TH, textAlign:"left", paddingLeft:20}}>{isSas ? t.sasContractor : t.lot}</th>
                <th style={TH}>{t.tot}</th>
                <th style={{...TH, color:TOK.VSO.ink}}>{b3.s1}</th>
                <th style={{...TH, color:TOK.VAO.ink}}>{b3.s2}</th>
                <th style={{...TH, color:TOK.REF.ink}}>{b3.s3}</th>
                <th style={TH}>HM</th>
                <th style={{...TH, textAlign:"left", paddingLeft:18, width:"32%"}}>
                  Bloquants · Non-bloq.
                </th>
              </tr>
            </thead>
            <tbody>
              {b3.lots.map((l, i) => (
                <tr key={i}>
                  <td style={{
                    ...TD, textAlign:"left", paddingLeft:20,
                    fontFamily: FONT_UI, fontSize: 13.5, fontWeight: 500,
                    lineHeight: 1.3
                  }}>
                    <div style={{ color: C.text }}>{l.contractor || l.name}</div>
                    <div style={{ fontFamily: FONT_NUM, fontSize: 10.5, color: C.text3, marginTop: 2, letterSpacing: ".02em" }}>{l.name}</div>
                  </td>
                  <td style={{...TD, cursor: onDrilldown ? "pointer" : "default"}}
                    onClick={onDrilldown ? () => onDrilldown({ filterKey:"total", lotName:l.name, label:`${l.name} — Total` }) : undefined}
                    title={onDrilldown ? "Voir les documents" : undefined}>
                    {fmt(l.total)}
                  </td>
                  <td style={{...TD, color:TOK.VSO.ink, fontWeight:500, cursor: onDrilldown ? "pointer" : "default"}}
                    onClick={onDrilldown ? () => onDrilldown({ filterKey:"s1", lotName:l.name, label:`${l.name} — ${b3.s1}` }) : undefined}
                    title={onDrilldown ? "Voir les documents" : undefined}>
                    {l[b3.s1]}
                  </td>
                  <td style={{...TD, color:TOK.VAO.ink, fontWeight:500, cursor: onDrilldown ? "pointer" : "default"}}
                    onClick={onDrilldown ? () => onDrilldown({ filterKey:"s2", lotName:l.name, label:`${l.name} — ${b3.s2}` }) : undefined}
                    title={onDrilldown ? "Voir les documents" : undefined}>
                    {l[b3.s2]}
                  </td>
                  <td style={{...TD, color:TOK.REF.ink, fontWeight:500, cursor: onDrilldown ? "pointer" : "default"}}
                    onClick={onDrilldown ? () => onDrilldown({ filterKey:"s3", lotName:l.name, label:`${l.name} — ${b3.s3}` }) : undefined}
                    title={onDrilldown ? "Voir les documents" : undefined}>
                    {l[b3.s3]}
                  </td>
                  <td style={{...TD, color:TOK.HM.ink, cursor: onDrilldown ? "pointer" : "default"}}
                    onClick={onDrilldown ? () => onDrilldown({ filterKey:"hm", lotName:l.name, label:`${l.name} — HM` }) : undefined}
                    title={onDrilldown ? "Voir les documents" : undefined}>
                    {l.HM}
                  </td>
                  <td style={{...TD, padding:"10px 0 10px 18px"}}>
                    <LotHealthBar l={l} keys={b3}/>
                    <span style={{display:"inline-flex", gap:8, fontFamily:FONT_NUM, fontSize:11.5, marginTop:4}}>
                      <span style={{color:TOK.OPEN.ink, cursor: onDrilldown ? "pointer" : "default"}}
                        onClick={onDrilldown ? (e) => { e.stopPropagation(); onDrilldown({ filterKey:"open_blocking_ok", lotName:l.name, label:`${l.name} — Bloquants OK` }); } : undefined}>
                        {l.open_blocking_ok ?? l.open_ok}
                      </span>
                      <span style={{color:C.text3}}>·</span>
                      <span style={{color:TOK.REF.ink, cursor: onDrilldown ? "pointer" : "default"}}
                        onClick={onDrilldown ? (e) => { e.stopPropagation(); onDrilldown({ filterKey:"open_blocking_late", lotName:l.name, label:`${l.name} — Bloquants retard` }); } : undefined}>
                        {l.open_blocking_late ?? l.open_late}
                      </span>
                      {(l.open_nb ?? 0) > 0 && (
                        <React.Fragment>
                          <span style={{color:C.text3}}>|</span>
                          <span style={{color:TOK.NB.ink, opacity:0.7, cursor: onDrilldown ? "pointer" : "default"}}
                            onClick={onDrilldown ? (e) => { e.stopPropagation(); onDrilldown({ filterKey:"open_non_blocking", lotName:l.name, label:`${l.name} — Non-bloquants` }); } : undefined}>
                            {l.open_nb}
                          </span>
                        </React.Fragment>
                      )}
                    </span>
                  </td>
                </tr>
              ))}
              <tr>
                <td style={{
                  ...TD, textAlign:"left", paddingLeft:20,
                  fontFamily: FONT_UI, fontSize: 14, fontWeight: 600,
                  borderTop: `1px solid ${C.line2}`
                }}>{t.tot}</td>
                <td style={{...TD, fontWeight:600, borderTop:`1px solid ${C.line2}`}}>{fmt(b3.total_row.total)}</td>
                <td style={{...TD, color:TOK.VSO.ink, fontWeight:600, borderTop:`1px solid ${C.line2}`}}>{b3.total_row[b3.s1]}</td>
                <td style={{...TD, color:TOK.VAO.ink, fontWeight:600, borderTop:`1px solid ${C.line2}`}}>{b3.total_row[b3.s2]}</td>
                <td style={{...TD, color:TOK.REF.ink, fontWeight:600, borderTop:`1px solid ${C.line2}`}}>{b3.total_row[b3.s3]}</td>
                <td style={{...TD, color:TOK.HM.ink, fontWeight:600, borderTop:`1px solid ${C.line2}`}}>{b3.total_row.HM}</td>
                <td style={{
                  ...TD, padding:"10px 0 10px 18px",
                  borderTop: `1px solid ${C.line2}`
                }}>
                  <span style={{
                    display:"inline-flex", gap:10, fontFamily:FONT_NUM, fontSize:11.5
                  }}>
                    <span style={{color:TOK.OPEN.ink}}>{b3.total_row.open_ok} {t.ok}</span>
                    <span style={{color:C.text3}}>·</span>
                    <span style={{color:TOK.REF.ink}}>{b3.total_row.open_late} {t.lateShort}</span>
                  </span>
                </td>
              </tr>
            </tbody>
          </table>
        </div>

        <div style={{ display:"flex", flexDirection:"column", gap:18 }}>
          <Donut b3={b3} t={t}/>
          <SideList
            title={isSas ? t.sasPendingQueue : t.critical}
            items={b3.critical_lots.map(c => ({
              name:c.name, value:c.open_late,
              max:Math.max(...b3.critical_lots.map(x=>x.open_late))
            }))}
            tone={isSas ? TOK.OPEN : TOK.REF}
          />
          <SideList
            title={isSas ? t.sasRefRate : t.refRate}
            items={b3.refus_lots.map(([c,p]) => ({
              name:c.name, value:p,
              max:Math.max(...b3.refus_lots.map(([_,q])=>q)),
              suffix:"%"
            }))}
            tone={TOK.REF}
          />
        </div>
      </div>
    </section>
  );
}

function LotHealthBar({ l, keys }) {
  const t = l.total;
  const seg = [
    { v:l[keys.s1], c:TOK.VSO.bar },
    { v:l[keys.s2], c:TOK.VAO.bar },
    { v:l[keys.s3], c:TOK.REF.bar },
    { v:l.HM,       c:TOK.HM.bar, alpha:.7 },
    { v:l.open_blocking_ok ?? l.open_ok,   c:TOK.OPEN.bar, alpha:.6 },
    { v:l.open_blocking_late ?? l.open_late, c:TOK.REF.bar, hatch:true },
    { v:l.open_nb ?? 0,  c:TOK.NB.bar, alpha:.4 }
  ];
  return (
    <div style={{
      display:"flex", height: 8, width:"100%",
      background: C.surf3, borderRadius: 99, overflow:"hidden"
    }}>
      {seg.map((s,i) => s.v > 0 ? (
        <div key={i} title={`${s.v}`} style={{
          width:`${(s.v/t)*100}%`,
          background: s.hatch
            ? `repeating-linear-gradient(45deg, ${s.c} 0 3px, rgba(255,69,58,.25) 3px 6px)`
            : s.c,
          opacity: s.alpha ?? 1
        }}/>
      ) : null)}
    </div>
  );
}

function Donut({ b3, t }) {
  const total = b3.donut_total;
  const r = 54, K = 2 * Math.PI * r;
  const lateDash = total ? (b3.donut_late / total) * K : 0;
  const okDash   = total ? (b3.donut_ok   / total) * K : 0;

  return (
    <div style={{
      padding: 20, background: C.surf,
      border: `1px solid ${C.line}`, borderRadius: 16
    }}>
      <Eyebrow style={{ marginBottom: 14 }}>{t.pending}</Eyebrow>

      <div style={{ display:"flex", alignItems:"center", gap:18 }}>
        <svg viewBox="0 0 160 160" style={{ width:128, flexShrink:0 }}>
          <circle cx="80" cy="80" r={r} fill="none" stroke={C.surf3} strokeWidth="12"/>
          {b3.donut_late > 0 && (
            <circle cx="80" cy="80" r={r} fill="none"
                    stroke={TOK.REF.bar} strokeWidth="12" strokeLinecap="round"
                    strokeDasharray={`${lateDash} ${K}`}
                    transform="rotate(-90 80 80)"/>
          )}
          {b3.donut_ok > 0 && (
            <circle cx="80" cy="80" r={r} fill="none"
                    stroke={TOK.OPEN.bar} strokeWidth="12" strokeLinecap="round"
                    strokeDasharray={`${okDash} ${K}`}
                    strokeDashoffset={-lateDash}
                    transform="rotate(-90 80 80)"/>
          )}
          <text x="80" y="80" textAnchor="middle" dominantBaseline="central"
                fontFamily={FONT_UI} fontWeight="300" fontSize="34"
                letterSpacing="-0.02em" fill={C.text}>{total}</text>
          <text x="80" y="102" textAnchor="middle"
                fontFamily={FONT_UI} fontSize="9" fontWeight="500"
                letterSpacing=".1em" fill={C.text3}>{t.pendingDonut.toUpperCase()}</text>
        </svg>

        <div style={{ fontFamily: FONT_UI, fontSize:12, lineHeight:1.9 }}>
          <div style={{ color: TOK.OPEN.ink, display:"flex", gap:8, alignItems:"center" }}>
            <Dot c={TOK.OPEN.bar}/>
            <span style={{fontFamily:FONT_NUM}}>{b3.donut_ok}</span>
            <span style={{color:C.text2}}>{t.onTime}</span>
          </div>
          <div style={{ color: TOK.REF.ink, display:"flex", gap:8, alignItems:"center" }}>
            <Dot c={TOK.REF.bar}/>
            <span style={{fontFamily:FONT_NUM}}>{b3.donut_late}</span>
            <span style={{color:C.text2}}>{t.late}</span>
          </div>
          {(b3.donut_nb ?? 0) > 0 && (
            <div style={{ color: TOK.NB.ink, display:"flex", gap:8, alignItems:"center", opacity:0.7 }}>
              <Dot c={TOK.NB.bar}/>
              <span style={{fontFamily:FONT_NUM}}>{b3.donut_nb}</span>
              <span style={{color:C.text2}}>non-bloq.</span>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

function SideList({ title, items, tone }) {
  if (!items || !items.length) return null;
  return (
    <div style={{
      padding: 20, background: C.surf,
      border: `1px solid ${C.line}`, borderRadius: 16
    }}>
      <Eyebrow style={{ marginBottom: 14 }}>{title}</Eyebrow>
      <div style={{ display:"flex", flexDirection:"column", gap: 10 }}>
        {items.map((it, i) => (
          <div key={i} style={{
            display:"grid", gridTemplateColumns:"38% 1fr auto",
            alignItems:"center", gap:12
          }}>
            <span style={{
              fontFamily: FONT_UI, fontSize: 12.5, color: C.text,
              whiteSpace:"nowrap", overflow:"hidden", textOverflow:"ellipsis"
            }}>{it.name}</span>
            <div style={{
              height: 4, background: C.surf3, borderRadius: 99, overflow:"hidden"
            }}>
              <div style={{
                width: `${(it.value/it.max)*100}%`, height:"100%",
                background: tone.bar, borderRadius: 99
              }}/>
            </div>
            <span style={{
              fontFamily: FONT_NUM, fontSize: 11.5, color: tone.ink,
              fontWeight:500, minWidth: 38, textAlign:"right"
            }}>
              {it.value}{it.suffix || ""}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}

// ── Footer ──────────────────────────────────────────────────────────────────
function Colophon({ data, t }) {
  const h = data.header, c = data.consultant;
  return (
    <footer style={{
      marginTop: 80, paddingTop: 24,
      borderTop: `1px solid ${C.line}`,
      display:"flex", justifyContent:"space-between", flexWrap:"wrap", gap:12,
      fontFamily: FONT_NUM, fontSize: 10.5, color: C.text3, letterSpacing:".06em"
    }}>
      <span>JANSA · {t.source.toUpperCase()} {(c.merge_key ? t.merged : t.gedOnly).toUpperCase()}</span>
      <span>{c.slug} · W{h.week_num} · {h.data_date_str}</span>
    </footer>
  );
}

// ── Main ────────────────────────────────────────────────────────────────────
function ConsultantFiche({ data, lang = "fr", onBack, onDrilldown }) {
  const t = L[lang];
  return (
    <article style={{
      maxWidth: 1200, margin: "0 auto", padding: "0 56px 60px",
      background: "transparent", color: C.text, fontFamily: FONT_UI
    }}>
      <Masthead data={data} t={t} onBack={onBack}/>
      <HeroStats data={data} t={t} onDrilldown={onDrilldown}/>
      <Narrative data={data} t={t} lang={lang}/>
      <Bloc1 data={data} t={t}/>
      <Bloc2 data={data} t={t}/>
      <Bloc3 data={data} t={t} onDrilldown={onDrilldown}/>
      <Colophon data={data} t={t}/>
    </article>
  );
}

// ── Drilldown Drawer — bottom sheet overlay ──────────────────────────────────
// state: { loading, error, docs, count, title, filterKey, lotName } | null
function DrilldownDrawer({ state, onClose, onExport }) {
  const [exporting, setExporting] = useState(false);

  useEffect(() => {
    if (!state) return;
    const handler = (e) => { if (e.key === "Escape") onClose(); };
    document.addEventListener("keydown", handler);
    return () => document.removeEventListener("keydown", handler);
  }, [state, onClose]);

  if (!state) return null;

  const { loading, error, docs, count, title } = state;

  const H_CELL = {
    fontFamily: FONT_UI, fontSize: 10, fontWeight: 600,
    letterSpacing: ".06em", textTransform: "uppercase", color: C.text3,
    padding: "10px 10px", textAlign: "right",
    borderBottom: `1px solid ${C.line2}`,
    position: "sticky", top: 0, background: C.surf, zIndex: 1,
  };
  const D_CELL = {
    fontFamily: FONT_NUM, fontSize: 12,
    padding: "8px 10px", textAlign: "right",
    borderBottom: `1px solid ${C.line}`,
    color: C.text, verticalAlign: "middle",
    maxWidth: 0, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap",
  };

  const daysBadge = (d) => {
    if (d == null) return <span style={{ color: C.text3, fontFamily: FONT_NUM }}>—</span>;
    const color = d < 0 ? TOK.REF.ink : d <= 7 ? TOK.VAO.ink : TOK.VSO.ink;
    return <span style={{ color, fontFamily: FONT_NUM, fontWeight: d < 0 ? 600 : 400 }}>{d < 0 ? d : `+${d}`}j</span>;
  };

  const statusChip = (s) => {
    if (!s) return null;
    const tok = TOK[s] || TOK.HM;
    return (
      <span style={{
        display: "inline-block", padding: "2px 8px", borderRadius: 99,
        background: tok.tint, color: tok.ink,
        fontFamily: FONT_UI, fontSize: 10.5, fontWeight: 500,
      }}>{s}</span>
    );
  };

  const docCount = count ?? (docs ? docs.length : 0);

  return (
    <div style={{ position: "fixed", inset: 0, zIndex: 200, display: "flex", flexDirection: "column", justifyContent: "flex-end" }}>
      {/* Backdrop */}
      <div onClick={onClose} style={{
        position: "absolute", inset: 0,
        background: "rgba(0,0,0,0.52)",
        backdropFilter: "blur(4px)", WebkitBackdropFilter: "blur(4px)",
      }}/>

      {/* Drawer panel */}
      <div style={{
        position: "relative", zIndex: 1,
        height: "60vh", display: "flex", flexDirection: "column",
        background: C.surf,
        borderTop: `1px solid ${C.line2}`,
        borderRadius: "16px 16px 0 0",
        boxShadow: "0 -8px 40px -4px rgba(0,0,0,0.5)",
        animation: "drawerSlideUp 0.26s cubic-bezier(.4,0,.2,1)",
      }}>
        {/* Header */}
        <div style={{
          display: "flex", alignItems: "center", justifyContent: "space-between",
          padding: "16px 24px 14px",
          borderBottom: `1px solid ${C.line}`,
          flexShrink: 0,
        }}>
          <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
            <span style={{ fontFamily: FONT_UI, fontWeight: 600, fontSize: 15, color: C.text }}>{title}</span>
            {!loading && !error && (
              <span style={{
                fontFamily: FONT_NUM, fontSize: 11,
                padding: "2px 9px", borderRadius: 99,
                background: C.surf3, color: C.text2,
              }}>{docCount} doc{docCount !== 1 ? "s" : ""}</span>
            )}
          </div>
          <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
            {onExport && !loading && !error && docs && docs.length > 0 && (
              <button
                disabled={exporting}
                onClick={async () => {
                  if (exporting) return;
                  setExporting(true);
                  try { await onExport(); } catch (e) { console.error("Export failed:", e); } finally { setExporting(false); }
                }}
                style={{
                  display: "inline-flex", alignItems: "center", gap: 6,
                  background: C.surf2, border: `1px solid ${C.line}`,
                  borderRadius: 99, padding: "5px 12px",
                  color: exporting ? C.text3 : C.text2,
                  fontFamily: FONT_UI, fontSize: 12,
                  cursor: exporting ? "default" : "pointer",
                  opacity: exporting ? 0.6 : 1,
                  transition: "border-color 0.2s, opacity 0.2s",
                }}
                onMouseEnter={e => { if (!exporting) e.currentTarget.style.borderColor = C.line2; }}
                onMouseLeave={e => { e.currentTarget.style.borderColor = C.line; }}
              >
                <svg width="12" height="12" viewBox="0 0 12 12" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round">
                  <path d="M6 1v7M3 6l3 3 3-3M2 10h8"/>
                </svg>
                <span>{exporting ? "Export en cours…" : "Exporter Excel"}</span>
              </button>
            )}
            <button onClick={onClose} style={{
              display: "inline-flex", alignItems: "center", gap: 6,
              background: C.surf2, border: `1px solid ${C.line}`,
              borderRadius: 99, padding: "5px 12px",
              color: C.text2, fontFamily: FONT_UI, fontSize: 12, cursor: "pointer",
              transition: "border-color 0.2s",
            }}
              onMouseEnter={e => e.currentTarget.style.borderColor = C.line2}
              onMouseLeave={e => e.currentTarget.style.borderColor = C.line}
            >
              <span style={{ fontSize: 13, lineHeight: 1 }}>✕</span>
              <span>Fermer</span>
            </button>
          </div>
        </div>

        {/* Body */}
        <div style={{ flex: 1, overflowY: "auto", overflowX: "hidden" }}>
          {loading && (
            <div style={{
              display: "flex", alignItems: "center", justifyContent: "center",
              height: "100%", gap: 12,
              color: C.text3, fontFamily: FONT_UI, fontSize: 13,
            }}>
              <div style={{
                width: 18, height: 18, borderRadius: "50%",
                border: `2px solid ${C.line2}`, borderTopColor: C.accent,
                animation: "ddSpin 0.7s linear infinite", flexShrink: 0,
              }}/>
              Chargement des documents…
            </div>
          )}

          {!loading && error && (
            <div style={{ padding: "24px 24px", color: TOK.REF.ink, fontFamily: FONT_UI, fontSize: 13 }}>
              ⚠ {error}
            </div>
          )}

          {!loading && !error && (!docs || docs.length === 0) && (
            <div style={{
              display: "flex", alignItems: "center", justifyContent: "center",
              height: "100%", color: C.text3, fontFamily: FONT_UI, fontSize: 13,
            }}>
              Aucun document pour ce filtre.
            </div>
          )}

          {!loading && !error && docs && docs.length > 0 && (
            <table style={{ width: "100%", borderCollapse: "collapse", tableLayout: "fixed" }}>
              <colgroup>
                <col style={{ width: "11%" }}/>
                <col style={{ width: "5%" }}/>
                <col style={{ width: "10%" }}/>
                <col style={{ width: "34%" }}/>
                <col style={{ width: "11%" }}/>
                <col style={{ width: "9%" }}/>
                <col style={{ width: "9%" }}/>
                <col style={{ width: "6%" }}/>
                <col style={{ width: "7%" }}/>
              </colgroup>
              <thead>
                <tr>
                  <th style={{...H_CELL, textAlign:"left", paddingLeft:20}}>Numéro</th>
                  <th style={H_CELL}>Ind.</th>
                  <th style={H_CELL}>Émetteur</th>
                  <th style={{...H_CELL, textAlign:"left", paddingLeft:10}}>Titre</th>
                  <th style={H_CELL}>Lot</th>
                  <th style={H_CELL}>Soumission</th>
                  <th style={H_CELL}>Échéance</th>
                  <th style={H_CELL}>Jours</th>
                  <th style={H_CELL}>Statut</th>
                </tr>
              </thead>
              <tbody>
                {docs.map((d, i) => {
                  const isLate = d.remaining_days != null && d.remaining_days < 0;
                  return (
                    <tr key={i}
                      onClick={state.onRowClick ? () => state.onRowClick(d) : undefined}
                      style={{ cursor: state.onRowClick ? "pointer" : "default", background: isLate ? "rgba(255,69,58,0.04)" : "transparent" }}>
                      <td style={{...D_CELL, textAlign:"left", paddingLeft:20, color: C.accent, fontWeight:500}}>{d.numero || "—"}</td>
                      <td style={{...D_CELL, textAlign:"center"}}>{d.indice || "—"}</td>
                      <td style={D_CELL}>{d.emetteur || "—"}</td>
                      <td style={{...D_CELL, textAlign:"left", paddingLeft:10, whiteSpace:"normal", lineHeight:1.3, fontFamily:FONT_UI, fontSize:12}}>{d.titre || "—"}</td>
                      <td style={{...D_CELL, textAlign:"center", fontSize:11, color:C.text2}}>{d.lot || "—"}</td>
                      <td style={{...D_CELL, textAlign:"center", fontSize:11, color:C.text2}}>{d.date_soumission || "—"}</td>
                      <td style={{...D_CELL, textAlign:"center", fontSize:11}}>{d.date_limite || "—"}</td>
                      <td style={{...D_CELL, textAlign:"center"}}>{daysBadge(d.remaining_days)}</td>
                      <td style={{...D_CELL, textAlign:"center"}}>{statusChip(d.status)}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          )}
        </div>
      </div>

      <style>{`
        @keyframes drawerSlideUp {
          from { transform: translateY(100%); }
          to   { transform: translateY(0); }
        }
        @keyframes ddSpin {
          to { transform: rotate(360deg); }
        }
      `}</style>
    </div>
  );
}

Object.assign(window, { ConsultantFiche, DrilldownDrawer });
