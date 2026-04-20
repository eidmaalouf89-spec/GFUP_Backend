/* Consultant fiche — Apple/Tesla dark aesthetic
   Data shape unchanged (window.FICHE_DATA from calculator.py).
   Exposes <ConsultantFiche data={…} lang="fr"/>.
*/
import React, { useId, useState } from "react";

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
    fiche: "Fiche"
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
    fiche: "Report"
  }
};

// ── Tokens — Apple/Tesla dark ───────────────────────────────────────────────
const C = {
  bg:       "#0A0A0B",   // near-black canvas
  surf:     "#111113",   // primary surface
  surf2:    "#18181B",   // elevated surface
  surf3:    "#222226",   // chip
  line:     "rgba(255,255,255,0.08)",
  line2:    "rgba(255,255,255,0.14)",
  text:     "#F5F5F7",
  text2:    "#A1A1A6",
  text3:    "#6E6E73",
  accent:   "#0A84FF",   // Apple system blue
};
// Status — muted, luminous, neon-restrained; match existing semantics
const TOK = {
  VSO:{ ink:"#30D158", tint:"rgba(48,209,88,.14)",  bar:"#30D158", soft:"#0A3A1C" },
  FAV:{ ink:"#30D158", tint:"rgba(48,209,88,.14)",  bar:"#30D158", soft:"#0A3A1C" },
  VAO:{ ink:"#FFD60A", tint:"rgba(255,214,10,.14)", bar:"#FFD60A", soft:"#3A2E00" },
  SUS:{ ink:"#FFD60A", tint:"rgba(255,214,10,.14)", bar:"#FFD60A", soft:"#3A2E00" },
  REF:{ ink:"#FF453A", tint:"rgba(255,69,58,.16)",  bar:"#FF453A", soft:"#3A0F0D" },
  DEF:{ ink:"#FF453A", tint:"rgba(255,69,58,.16)",  bar:"#FF453A", soft:"#3A0F0D" },
  HM: { ink:"#8E8E93", tint:"rgba(142,142,147,.14)",bar:"#8E8E93", soft:"#232326" },
  OPEN:{ink:"#0A84FF", tint:"rgba(10,132,255,.16)", bar:"#0A84FF", soft:"#00284C"}
};
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
function Masthead({ data, t }) {
  const c = data.consultant;
  const h = data.header;
  return (
    <header style={{
      padding: "48px 0 40px",
      borderBottom: `1px solid ${C.line}`
    }}>
      <div style={{
        display:"flex", justifyContent:"space-between",
        fontFamily: FONT_NUM, fontSize: 11, color: C.text3, letterSpacing:".08em"
      }}>
        <span>{t.project.toUpperCase()} — {t.section.toUpperCase()}</span>
        <span>W{String(h.week_num).padStart(2,"0")} · {h.data_date_str}</span>
      </div>

      <div style={{ display:"flex", alignItems:"flex-end", gap:48, marginTop: 36 }}>
        <div style={{ flex: 1 }}>
          <Eyebrow style={{ marginBottom: 12 }}>
            {t.fiche} · {String(c.id).padStart(2,"0")} / 14
          </Eyebrow>
          <h1 style={{
            fontFamily: FONT_UI, fontWeight: 600, color: C.text,
            fontSize: 72, letterSpacing: "-.035em", lineHeight: 1,
            margin: "6px 0 14px"
          }}>{c.display_name}</h1>
          <div style={{
            fontFamily: FONT_UI, fontWeight: 400, fontSize: 17, color: C.text2
          }}>
            {c.role} · {c.merge_key ? t.merged : t.gedOnly}
          </div>
        </div>

        <div style={{ textAlign: "right", minWidth: 240 }}>
          <Eyebrow>{t.total}</Eyebrow>
          <div style={{
            fontFamily: FONT_UI, fontWeight: 200, color: C.text,
            fontSize: 104, letterSpacing: "-.05em", lineHeight: .92,
            marginTop: 6,
            background: "linear-gradient(180deg, #FFFFFF 0%, #9A9AA0 100%)",
            WebkitBackgroundClip: "text", WebkitTextFillColor: "transparent"
          }}>{fmt(h.total)}</div>
        </div>
      </div>
    </header>
  );
}

// ── Hero KPI band — Apple-style glass cards ─────────────────────────────────
function HeroStats({ data, t }) {
  const h = data.header;
  const d = data.week_delta || {};
  const refusRate = pct(h.s3_count, h.answered);

  const last = (data.bloc1 || []).slice(-12);
  const sparkRendered = last.map(r => r.doc_ferme);
  const sparkOpen = last.map(r => r.open_ok + r.open_late);
  const sparkRefus = last.map(r => (r.doc_ferme ? Math.round((r.s3/r.doc_ferme)*1000)/10 : 0));

  const stats = [
    {
      eyebrow: t.rendered,
      value: fmt(h.answered),
      chips: [
        { label: h.s1, n: h.s1_count, tone: TOK.VSO },
        { label: h.s2, n: h.s2_count, tone: TOK.VAO },
        { label: h.s3, n: h.s3_count, tone: TOK.REF },
        { label: "HM", n: h.hm_count, tone: TOK.HM }
      ],
      delta: (d.s1||0)+(d.s2||0)+(d.s3||0)+(d.hm||0),
      spark: sparkRendered, tone: TOK.VSO
    },
    {
      eyebrow: t.pending,
      value: fmt(h.open_count),
      chips: [
        { label: t.onTime, n: h.open_ok, tone: TOK.OPEN },
        { label: t.late,   n: h.open_late, tone: TOK.REF }
      ],
      delta: d.open ?? 0, invertDelta: true,
      spark: sparkOpen, tone: TOK.OPEN
    },
    {
      eyebrow: t.refus,
      value: `${refusRate}%`,
      chips: [
        { label: `${h.s3_count}/${h.answered}`, n: null, tone: TOK.REF }
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

          <div style={{
            fontFamily: FONT_UI, fontWeight: 300, color: C.text,
            fontSize: 72, letterSpacing: "-.035em", lineHeight: 1,
            margin: "14px 0 6px"
          }}>{s.value}</div>

          <Sparkline values={s.spark} color={s.tone.bar}/>

          <div style={{
            display:"flex", flexWrap:"wrap", gap: 6, marginTop: 14
          }}>
            {s.chips.map((c, j) => (
              <Chip key={j} label={c.label} n={c.n} tone={c.tone}/>
            ))}
          </div>
        </div>
      ))}
    </section>
  );
}

function Chip({ label, n, tone }) {
  return (
    <span style={{
      display:"inline-flex", alignItems:"center", gap: 6,
      padding: "4px 10px", borderRadius: 99,
      background: tone.tint,
      color: tone.ink,
      fontFamily: FONT_UI, fontSize: 11.5, fontWeight: 500,
      border: `1px solid ${tone.tint}`
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
  const gradientId = useId().replace(/:/g, "");
  if (!values || !values.length) return null;
  const max = Math.max(...values), min = Math.min(...values);
  const W = 240, H = height, pad = 2;
  const n = values.length;
  const xs = values.map((_, i) => pad + (i * (W - 2*pad)) / (n - 1 || 1));
  const ys = values.map(v => max === min ? H/2 :
    pad + (H - 2*pad) * (1 - (v - min) / (max - min)));
  const line = values.map((_, i) => `${i?"L":"M"}${xs[i].toFixed(1)},${ys[i].toFixed(1)}`).join(" ");
  const area = `${line} L${xs[n-1]},${H} L${xs[0]},${H} Z`;
  return (
    <svg viewBox={`0 0 ${W} ${H}`} style={{ width:"100%", height, display:"block" }}>
      <defs>
        <linearGradient id={gradientId} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor={color} stopOpacity=".32"/>
          <stop offset="100%" stopColor={color} stopOpacity="0"/>
        </linearGradient>
      </defs>
      <path d={area} fill={`url(#${gradientId})`}/>
      <path d={line} fill="none" stroke={color} strokeWidth="1.4" strokeLinejoin="round"/>
      <circle cx={xs[n-1]} cy={ys[n-1]} r="2.6" fill={color}/>
    </svg>
  );
}

// ── Narrative ───────────────────────────────────────────────────────────────
function Narrative({ data, t, lang }) {
  const h = data.header;
  const d = data.week_delta || {};
  const refusRate = pct(h.s3_count, h.answered);
  const text = lang === "fr"
    ? `Semaine ${h.week_num} — ${signed(d.total||0)} document${Math.abs(d.total||0)>1?"s":""} soumis, ${signed((d.s1||0)+(d.s2||0)+(d.s3||0)+(d.hm||0))} avis rendus. Taux de refus ${refusRate}% (${signed(d.refus_rate_pct||0)} pt). Backlog en retard : ${h.open_late} (${signed(d.open_late||0)}).`
    : `Week ${h.week_num} — ${signed(d.total||0)} document${Math.abs(d.total||0)>1?"s":""} submitted, ${signed((d.s1||0)+(d.s2||0)+(d.s3||0)+(d.hm||0))} responses issued. Rejection rate ${refusRate}% (${signed(d.refus_rate_pct||0)} pt). Overdue backlog: ${h.open_late} (${signed(d.open_late||0)}).`;

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
            <col style={{width:"17%"}}/>
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
              <th style={{...TH, textAlign:"left", paddingLeft:16}}>Δ backlog</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r, i) => {
              const bal = r.doc_ferme - r.nvx;
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

                  <td style={{...TD, textAlign:"left", paddingLeft: 16}}>
                    <BalanceGlyph delta={bal} active={r.nvx || r.doc_ferme}/>
                  </td>
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
          <Dot c={TOK.VSO.bar}/> backlog en réduction
        </span>
        <span style={{display:"inline-flex",gap:6,alignItems:"center"}}>
          <Dot c={TOK.REF.bar}/> backlog en accumulation
        </span>
        <span style={{display:"inline-flex",gap:6,alignItems:"center"}}>
          <Dot c={TOK.HM.bar}/> {t.noActivity}
        </span>
      </div>
    </section>
  );
}

function BalanceGlyph({ delta, active }) {
  if (!active) return <span style={{color:C.text3, fontFamily:FONT_NUM, fontSize:12}}>○</span>;
  if (delta > 0) return (
    <span style={{
      display:"inline-flex", alignItems:"center", gap:4,
      padding:"3px 9px", borderRadius:99,
      background: TOK.VSO.tint, color: TOK.VSO.ink,
      fontFamily: FONT_NUM, fontSize: 11.5, fontWeight:500
    }}>↑ +{delta}</span>
  );
  if (delta < 0) return (
    <span style={{
      display:"inline-flex", alignItems:"center", gap:4,
      padding:"3px 9px", borderRadius:99,
      background: TOK.REF.tint, color: TOK.REF.ink,
      fontFamily: FONT_NUM, fontSize: 11.5, fontWeight:500
    }}>↓ {delta}</span>
  );
  return <span style={{color:C.text3, fontFamily:FONT_NUM, fontSize:12}}>=</span>;
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
    const hm = b2.hm_series[i], op = b2.open_series[i];
    return { s1, s2:s1+s2, s3:s1+s2+s3, hm:s1+s2+s3+hm, total:s1+s2+s3+hm+op };
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

          {area(null,    "s1", TOK.VSO.bar)}
          {area("s1",    "s2", TOK.VAO.bar)}
          {area("s2",    "s3", TOK.REF.bar)}
          {area("s3",    "hm", TOK.HM.bar)}
          {area("hm", "total", TOK.OPEN.bar)}

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
                <rect width="178" height="108" rx="10" fill={C.surf2} stroke={C.line2} strokeWidth="1"/>
                <text x="12" y="22" fontFamily={FONT_UI} fontWeight="600" fontSize="13" fill={C.text}>
                  {b2.labels[hover]} · {fmt(b2.totals[hover])}
                </text>
                {[
                  {k:"s1_series", c:TOK.VSO, lbl:data.header.s1},
                  {k:"s2_series", c:TOK.VAO, lbl:data.header.s2},
                  {k:"s3_series", c:TOK.REF, lbl:data.header.s3},
                  {k:"hm_series", c:TOK.HM,  lbl:"HM"},
                  {k:"open_series",c:TOK.OPEN,lbl:t.pending}
                ].map((row,i) => (
                  <g key={i} transform={`translate(12, ${42+i*14})`}>
                    <circle cx="4" cy="-4" r="3" fill={row.c.bar}/>
                    <text x="14" y="0" fontFamily={FONT_NUM} fontSize="10.5" fill={C.text2}>
                      {row.lbl}
                    </text>
                    <text x="168" y="0" textAnchor="end" fontFamily={FONT_NUM} fontSize="10.5" fill={C.text}>
                      {fmt(b2[row.k][hover])}
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
            {c:TOK.VSO, l:data.header.s1},
            {c:TOK.VAO, l:data.header.s2},
            {c:TOK.REF, l:data.header.s3},
            {c:TOK.HM,  l:"HM"},
            {c:TOK.OPEN,l:t.pending}
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
function Bloc3({ data, t }) {
  const b3 = data.bloc3;
  return (
    <section style={{ marginTop: 64 }}>
      <BlockHead num="03" title={t.b3}/>

      <div style={{ display:"grid", gridTemplateColumns:"1.7fr 1fr", gap:28 }}>
        <div style={{
          background: C.surf, border: `1px solid ${C.line}`,
          borderRadius: 16, overflow: "hidden"
        }}>
          <table style={{ width:"100%", borderCollapse:"collapse" }}>
            <thead>
              <tr>
                <th style={{...TH, textAlign:"left", paddingLeft:20}}>{t.lot}</th>
                <th style={TH}>{t.tot}</th>
                <th style={{...TH, color:TOK.VSO.ink}}>{b3.s1}</th>
                <th style={{...TH, color:TOK.VAO.ink}}>{b3.s2}</th>
                <th style={{...TH, color:TOK.REF.ink}}>{b3.s3}</th>
                <th style={TH}>HM</th>
                <th style={{...TH, textAlign:"left", paddingLeft:18, width:"32%"}}>
                  {t.onTime} · {t.late}
                </th>
              </tr>
            </thead>
            <tbody>
              {b3.lots.map((l, i) => (
                <tr key={i}>
                  <td style={{
                    ...TD, textAlign:"left", paddingLeft:20,
                    fontFamily: FONT_UI, fontSize: 13.5, fontWeight: 500
                  }}>
                    {l.name}
                  </td>
                  <td style={TD}>{fmt(l.total)}</td>
                  <td style={{...TD, color:TOK.VSO.ink, fontWeight:500}}>{l[b3.s1]}</td>
                  <td style={{...TD, color:TOK.VAO.ink, fontWeight:500}}>{l[b3.s2]}</td>
                  <td style={{...TD, color:TOK.REF.ink, fontWeight:500}}>{l[b3.s3]}</td>
                  <td style={{...TD, color:TOK.HM.ink}}>{l.HM}</td>
                  <td style={{...TD, padding:"10px 0 10px 18px"}}>
                    <LotHealthBar l={l} keys={b3}/>
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
            title={t.critical}
            items={b3.critical_lots.map(c => ({
              name:c.name, value:c.open_late,
              max:Math.max(...b3.critical_lots.map(x=>x.open_late))
            }))}
            tone={TOK.REF}
          />
          <SideList
            title={t.refRate}
            items={b3.refus_lots.map(([c,p]) => ({
              name:c.name, value:p,
              max:Math.max(...b3.refus_lots.map(([, q]) => q)),
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
    { v:l.open_ok,  c:TOK.OPEN.bar, alpha:.6 },
    { v:l.open_late,c:TOK.REF.bar, hatch:true }
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
function ConsultantFiche({ data, lang = "fr" }) {
  const t = L[lang];
  return (
    <article style={{
      maxWidth: 1200, margin: "0 auto", padding: "0 56px 60px",
      background: C.bg, color: C.text, fontFamily: FONT_UI
    }}>
      <Masthead data={data} t={t}/>
      <HeroStats data={data} t={t}/>
      <Narrative data={data} t={t} lang={lang}/>
      <Bloc1 data={data} t={t}/>
      <Bloc2 data={data} t={t}/>
      <Bloc3 data={data} t={t}/>
      <Colophon data={data} t={t}/>
    </article>
  );
}

export default ConsultantFiche;
