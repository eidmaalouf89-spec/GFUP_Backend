/* =====================================================================
   contractor_fiche_page.jsx — Per-contractor quality fiche (V1).
   Reads window.CONTRACTOR_FICHE_DATA (populated by data_bridge.loadContractorFiche).
   Companion to ConsultantFichePage; visual continuity via inline-copied
   tokens from fiche_base.jsx. Does NOT depend on ConsultantFiche or any
   consultant-specific component.
   ===================================================================== */

const { useState } = React;

// ── A. Tokens (inline-copied verbatim from fiche_base.jsx lines 62–95) ────────
const FONT_UI  = "'SF Pro Display','SF Pro Text','Inter',-apple-system,BlinkMacSystemFont,'Helvetica Neue',sans-serif";
const FONT_NUM = "'SF Mono','JetBrains Mono','Menlo',monospace";

// C fields from fiche_base.jsx (bg through accent) plus semantic aliases
// needed for quality widgets (good/warn/bad and their soft variants).
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
  // semantic extensions (CSS vars already defined by the app theme)
  good:     "var(--good)",
  goodSoft: "var(--good-soft)",
  warn:     "var(--warn)",
  warnSoft: "var(--warn-soft)",
  bad:      "var(--bad)",
  badSoft:  "var(--bad-soft)",
};

// Formatters (inline-copied from fiche_base.jsx lines 88–90, plus pctFmt)
const fmt    = (n) => (n ?? 0).toLocaleString("fr-FR").replace(/,/g, " ");
const pct    = (n, d) => (d ? Math.round((n / d) * 1000) / 10 : 0);
const pctFmt = (v) => (v == null ? "—" : (Math.round(v * 1000) / 10).toLocaleString("fr-FR") + " %");

// ── B. Polar histogram color palette ──────────────────────────────────────────
// 13 sectors clockwise from 12 o'clock, green (0-10) → blue (40-60) → orange (80-100) → red (120+)
const POLAR_PALETTE = [
  "#34C759", // 0-10    green
  "#2ACE52", // 10-20   green
  "#1FC96A", // 20-30   teal-green
  "#0A84FF", // 30-40   blue
  "#1C87F5", // 40-50   blue
  "#2E8AE0", // 50-60   blue-indigo
  "#FF9F0A", // 60-70   orange
  "#FF8C00", // 70-80   deep orange
  "#FF6B00", // 80-90   amber-orange
  "#FF453A", // 90-100  red-orange
  "#FF3B30", // 100-110 red
  "#D63B30", // 110-120 dark red
  "#C0392B", // 120+    deep red catch-all
];

// ── C. KPI labels and formatters ──────────────────────────────────────────────
const KPI_LABELS = {
  sas_refusal_rate: {
    label: "Taux SAS REF historique",
    fmt: pctFmt,
    empty: "—",
    info: "Numérateur : nombre de réponses MOEX 0-SAS = REF.\n"
        + "Dénominateur : nombre total de réponses MOEX 0-SAS reçues (toutes statuts).\n"
        + "Lecture : « pourcentage de soumissions qui ont échoué au passage de la porte SAS ».",
  },
  dormant_ref_count: {
    label: "REF dormants",
    fmt: fmt,
    empty: "—",
    info: "Nombre de documents dont la dernière indice est REF et qui n’ont pas encore été resoumis.\n"
        + "Cliquez sur les lignes du panneau « REF en attente » pour ouvrir chaque document.",
  },
  pct_chains_long: {
    label: "Chaînes > 120j",
    fmt: pctFmt,
    empty: "—",
    info: "Pourcentage des chaînes (par numéro de document) dont la durée totale dépasse 120 jours.\n"
        + "Inclut les chaînes ouvertes ou fermées.",
  },
  avg_contractor_delay_days: {
    label: "Délai moyen entreprise (incl. REF dormants)",
    fmt: (v) => (v == null ? "—" : (Math.round(v * 10) / 10).toString() + " j"),
    empty: "—",
    info: "Moyenne, par chaîne de cette entreprise, des jours de retard attribuables :\n"
        + "  • cycles fermés : retard imputé à ENTREPRISE ou à l’entreprise nommée dans l’attribution_breakdown\n"
        + "  • + jours écoulés depuis le dernier REF/SAS REF dormant non resoumis\n"
        + "Reflète à la fois le retard sur cycles bouclés et la procrastination sur les REF en attente.",
  },
  socotec_sus_rate: {
    label: "Taux SUS SOCOTEC",
    fmt: pctFmt,
    empty: "Aucune réponse SOCOTEC enregistrée.",
    info: "Numérateur : réponses SOCOTEC (Bureau de Contrôle) = SUS pour cette entreprise.\n"
        + "Dénominateur : toutes les réponses SOCOTEC répondues pour cette entreprise.\n"
        + "Indique un risque réglementaire potentiel si élevé par rapport à la médiane projet.",
  },
};

// ── D. peerTone helper (all KPIs: lower-is-better) ────────────────────────────
function peerTone(value, peer) {
  if (value == null) return "neutral";
  if (value < peer.median) return "good";
  if (value > peer.p75)    return "bad";
  return "neutral";
}

function KpiInfoIcon({ text }) {
  if (!text) return null;
  const [open, setOpen] = React.useState(false);
  const show = () => setOpen(true);
  const hide = () => setOpen(false);
  return (
    <span
      tabIndex={0}
      onMouseEnter={show}
      onMouseLeave={hide}
      onFocus={show}
      onBlur={hide}
      style={{
        position: "relative",
        display: "inline-flex", alignItems: "center", justifyContent: "center",
        width: 14, height: 14, marginLeft: 6, borderRadius: "50%",
        border: "1px solid " + C.line2, color: C.text3,
        fontSize: 10, fontFamily: FONT_UI, fontWeight: 500,
        cursor: "help", userSelect: "none",
        outline: "none",
      }}
    >
      ⓘ
      {open && (
        <span
          role="tooltip"
          style={{
            position: "absolute",
            top: "calc(100% + 8px)",
            left: "50%",
            transform: "translateX(-50%)",
            minWidth: 240,
            maxWidth: 320,
            padding: "10px 12px",
            background: C.surf2,
            border: "1px solid " + C.line2,
            borderRadius: 8,
            boxShadow: "0 6px 24px rgba(0,0,0,0.35)",
            color: C.text2,
            fontFamily: FONT_UI,
            fontSize: 11.5,
            lineHeight: 1.45,
            fontWeight: 400,
            whiteSpace: "pre-line",
            textAlign: "left",
            zIndex: 100,
            pointerEvents: "none",
          }}
        >
          {text}
        </span>
      )}
    </span>
  );
}

// ── E. KpiTile ────────────────────────────────────────────────────────────────
function KpiTile({ label, value, peer, formatter, emptyLabel, info }) {
  const tone  = peerTone(value, peer);
  const color = tone === "good" ? C.good : tone === "bad" ? C.bad : C.text2;
  const isNull = value == null;

  // Peer band: 80px bar. Position contractor dot relative to p25–p75 range.
  const barW   = 80;
  const dotPos = (() => {
    if (isNull || !peer) return barW / 2;
    const lo    = peer.p25 != null ? peer.p25 : 0;
    const hi    = peer.p75 != null ? peer.p75 : 1;
    const range = hi - lo || 1;
    return Math.max(0, Math.min(barW, ((value - lo) / range) * barW));
  })();

  return (
    <div style={{
      background: C.surf, borderRadius: 14, padding: "18px 20px",
      display: "flex", flexDirection: "column", gap: 8,
      flex: 1, minWidth: 160,
    }}>
      <div style={{
        fontFamily: FONT_UI, fontSize: 10, fontWeight: 600,
        letterSpacing: ".08em", textTransform: "uppercase", color: C.text3,
        display: "flex", alignItems: "center",
      }}>
        <span>{label}</span>
        <KpiInfoIcon text={info}/>
      </div>

      {isNull ? (
        <span style={{ fontFamily: FONT_UI, fontSize: 12, color: C.text3, fontStyle: "italic" }}>
          {emptyLabel || "—"}
        </span>
      ) : (
        <>
          <span style={{
            fontFamily: FONT_NUM, fontSize: 28, fontWeight: 600,
            letterSpacing: "-.02em", color,
          }}>
            {formatter(value)}
          </span>

          {peer && (
            <div style={{ position: "relative", height: 8, marginTop: 2, width: barW }}>
              {/* p25–p75 background bar */}
              <div style={{
                position: "absolute", top: 3, left: 0,
                width: barW, height: 2,
                background: C.line2, borderRadius: 2,
              }} />
              {/* median tick */}
              <div style={{
                position: "absolute", top: 0, left: barW / 2 - 1,
                width: 2, height: 8,
                background: C.text3, borderRadius: 1,
              }} />
              {/* contractor value dot */}
              <div style={{
                position: "absolute", top: 1, left: dotPos - 4,
                width: 8, height: 8, borderRadius: 99,
                background: color, boxShadow: "0 0 4px " + color,
              }} />
            </div>
          )}
        </>
      )}
    </div>
  );
}

// ── F. PolarHistogram ─────────────────────────────────────────────────────────
function PolarHistogram({ buckets, maxCount }) {
  if (!maxCount || maxCount === 0) {
    return (
      <div style={{
        display: "flex", alignItems: "center", justifyContent: "center",
        height: 200, color: C.text3, fontFamily: FONT_UI,
        fontSize: 14, fontStyle: "italic",
      }}>
        Pas encore de chaînes attribuées.
      </div>
    );
  }

  const cx = 240, cy = 240, inner = 60, outerMax = 200;
  const n   = buckets.length;
  const arc = 360 / n;
  const totalCount = buckets.reduce(function (s, b) { return s + (b.count || 0); }, 0);

  const sectors = buckets.map(function (b, i) {
    const count = b.count || 0;
    const outer = count > 0
      ? inner + Math.max(8, (outerMax - inner) * (count / maxCount))
      : inner + 4;
    const sa  = (-90 + i * arc) * Math.PI / 180;
    const ea  = (-90 + (i + 1) * arc) * Math.PI / 180;
    const x1  = cx + inner * Math.cos(sa);
    const y1  = cy + inner * Math.sin(sa);
    const x2  = cx + outer * Math.cos(sa);
    const y2  = cy + outer * Math.sin(sa);
    const x3  = cx + outer * Math.cos(ea);
    const y3  = cy + outer * Math.sin(ea);
    const x4  = cx + inner * Math.cos(ea);
    const y4  = cy + inner * Math.sin(ea);
    const laf = arc > 180 ? 1 : 0;
    const d   = [
      "M " + x1.toFixed(2) + " " + y1.toFixed(2),
      "L " + x2.toFixed(2) + " " + y2.toFixed(2),
      "A " + outer.toFixed(2) + " " + outer.toFixed(2) + " 0 " + laf + " 1 " + x3.toFixed(2) + " " + y3.toFixed(2),
      "L " + x4.toFixed(2) + " " + y4.toFixed(2),
      "A " + inner.toFixed(2) + " " + inner.toFixed(2) + " 0 " + laf + " 0 " + x1.toFixed(2) + " " + y1.toFixed(2),
      "Z",
    ].join(" ");
    return { d: d, color: POLAR_PALETTE[i] || "#8E8E93", label: b.label, count: count };
  });

  return (
    <svg viewBox="0 0 480 480" style={{ width: "100%", maxWidth: 420, display: "block", margin: "0 auto" }}>
      {sectors.map(function (s, i) {
        return (
          <path key={i} d={s.d} fill={s.color} stroke={C.surf2} strokeWidth={1}>
            <title>{s.label + " : " + s.count}</title>
          </path>
        );
      })}
      <text
        x={cx} y={cy - 10}
        textAnchor="middle"
        fontFamily={FONT_NUM}
        fontSize={32}
        fontWeight={600}
        fill={C.text}
      >
        {fmt(totalCount)}
      </text>
      <text
        x={cx} y={cy + 16}
        textAnchor="middle"
        fontFamily={FONT_UI}
        fontSize={13}
        fill={C.text3}
      >
        chaînes
      </text>
    </svg>
  );
}

// ── G. DormantQueueRow ────────────────────────────────────────────────────────
function DormantQueueRow({ doc, onOpen }) {
  const [hovered, setHovered] = useState(false);
  const days     = doc.days_dormant || 0;
  const badgeClr = days > 90 ? C.bad : C.warn;
  const badgeBg  = days > 90 ? C.badSoft : C.warnSoft;
  const rawTitle = doc.titre || "";
  const titre    = rawTitle.length > 40 ? rawTitle.slice(0, 40) + "…" : rawTitle;

  return (
    <div
      onClick={function () { onOpen(doc.numero, doc.indice); }}
      onMouseEnter={function () { setHovered(true); }}
      onMouseLeave={function () { setHovered(false); }}
      style={{
        display: "flex", alignItems: "center", gap: 12,
        padding: "8px 12px", cursor: "pointer", borderRadius: 8,
        background: hovered ? C.surf2 : "transparent",
        transition: "background 0.12s",
      }}
    >
      <span style={{
        fontFamily: FONT_NUM, fontSize: 12, color: C.text3,
        minWidth: 80, flexShrink: 0,
      }}>
        {doc.numero}{doc.indice ? "/" + doc.indice : ""}
      </span>
      <span style={{
        fontFamily: FONT_UI, fontSize: 13, color: C.text,
        flex: 1, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap",
      }}>
        {titre}
      </span>
      <span style={{
        fontFamily: FONT_NUM, fontSize: 11, fontWeight: 600,
        padding: "2px 8px", borderRadius: 99,
        background: badgeBg, color: badgeClr, flexShrink: 0,
      }}>
        {days}j
      </span>
      {doc.lot_normalized && (
        <span style={{
          fontFamily: FONT_UI, fontSize: 11, color: C.text3,
          flexShrink: 0, minWidth: 28, textAlign: "right",
        }}>
          {doc.lot_normalized}
        </span>
      )}
    </div>
  );
}

// ── H. DormantQueue ───────────────────────────────────────────────────────────
function DormantQueue({ title, docs, emptyLabel, onOpen }) {
  const isEmpty = !docs || docs.length === 0;
  return (
    <div style={{
      background: C.surf, borderRadius: 14, padding: "20px 0",
      flex: 1, overflow: "hidden",
    }}>
      <div style={{
        fontFamily: FONT_UI, fontSize: 13, fontWeight: 600,
        color: C.text3, letterSpacing: ".04em", textTransform: "uppercase",
        padding: "0 20px 12px", borderBottom: "1px solid " + C.line,
      }}>
        {title}
      </div>

      {isEmpty ? (
        <div style={{
          display: "flex", alignItems: "center", justifyContent: "center",
          height: 80, color: C.text3, fontFamily: FONT_UI, fontSize: 13,
        }}>
          {"✓ " + emptyLabel}
        </div>
      ) : (
        <div style={{ maxHeight: 400, overflowY: "auto", paddingTop: 4 }}>
          {docs.map(function (doc, i) {
            return <DormantQueueRow key={i} doc={doc} onOpen={onOpen} />;
          })}
        </div>
      )}
    </div>
  );
}

// ── I. OpenFinishedCard ───────────────────────────────────────────────────────
function OpenFinishedCard({ data }) {
  const open     = data.open     || 0;
  const finished = data.finished || 0;
  const total    = data.total    || 0;
  const openPct  = total > 0 ? (open / total) * 100 : 0;

  return (
    <div style={{
      background: C.surf, borderRadius: 14, padding: "20px 24px", flex: 1,
    }}>
      <div style={{
        fontFamily: FONT_UI, fontSize: 11, fontWeight: 600,
        letterSpacing: ".06em", textTransform: "uppercase",
        color: C.text3, marginBottom: 14,
      }}>
        Chaînes ouvertes vs finalisées
      </div>

      {total === 0 ? (
        <div style={{ fontFamily: FONT_UI, fontSize: 14, color: C.text3, fontStyle: "italic" }}>
          Aucune chaîne.
        </div>
      ) : (
        <>
          <div style={{ display: "flex", gap: 32, marginBottom: 16 }}>
            <div>
              <div style={{
                fontFamily: FONT_NUM, fontSize: 40, fontWeight: 700,
                color: C.warn, letterSpacing: "-.02em",
              }}>
                {fmt(open)}
              </div>
              <div style={{ fontFamily: FONT_UI, fontSize: 11, color: C.text3 }}>
                ouvertes
              </div>
            </div>
            <div>
              <div style={{
                fontFamily: FONT_NUM, fontSize: 40, fontWeight: 700,
                color: C.good, letterSpacing: "-.02em",
              }}>
                {fmt(finished)}
              </div>
              <div style={{ fontFamily: FONT_UI, fontSize: 11, color: C.text3 }}>
                finalisées
              </div>
            </div>
          </div>
          <div style={{
            height: 8, borderRadius: 4, background: C.line2, overflow: "hidden",
          }}>
            <div style={{
              height: "100%", borderRadius: 4,
              background: C.warn,
              width: openPct.toFixed(1) + "%",
              transition: "width 0.4s",
            }} />
          </div>
        </>
      )}
    </div>
  );
}

// ── J. LongChainsCard ─────────────────────────────────────────────────────────
function LongChainsCard({ data }) {
  return (
    <div style={{
      background: C.surf, borderRadius: 14, padding: "20px 24px", flex: 1,
    }}>
      <div style={{
        fontFamily: FONT_UI, fontSize: 11, fontWeight: 600,
        letterSpacing: ".06em", textTransform: "uppercase",
        color: C.text3, marginBottom: 14,
      }}>
        Chaînes longues (&gt;120 jours)
      </div>
      <div style={{ fontFamily: FONT_UI, fontSize: 14, color: C.text, lineHeight: 1.8 }}>
        <div>
          {pctFmt(data.pct_long)} des chaînes dépassent 120 jours.
        </div>
        <div style={{ marginTop: 8 }}>
          Sur ces chaînes longues, l’entreprise a causé{" "}
          {pctFmt(data.share_contractor_in_long_chains)} du retard total cumulé.
        </div>
      </div>
    </div>
  );
}

// ── K. KpiStrip ───────────────────────────────────────────────────────────────
function KpiStrip({ kpis }) {
  const keys = [
    "sas_refusal_rate",
    "dormant_ref_count",
    "pct_chains_long",
    "avg_contractor_delay_days",
    "socotec_sus_rate",
  ];
  return (
    <div style={{
      display: "flex", gap: 12, flexWrap: "wrap", margin: "32px 0 24px",
    }}>
      {keys.map(function (k) {
        const meta = KPI_LABELS[k];
        const kpi  = (kpis && kpis[k]) || {};
        const val  = kpi.value != null ? kpi.value : null;
        const peer = kpi.peer  || { median: 0, p25: 0, p75: 1 };
        return (
          <KpiTile
            key={k}
            label={meta.label}
            value={val}
            peer={peer}
            formatter={meta.fmt}
            emptyLabel={meta.empty}
            info={meta.info}
          />
        );
      })}
    </div>
  );
}

// ── L. PolarHistogramSection ──────────────────────────────────────────────────
function PolarHistogramSection({ histogram }) {
  return (
    <div style={{
      background: C.surf, borderRadius: 14, padding: "24px", margin: "0 0 24px",
    }}>
      <div style={{
        fontFamily: FONT_UI, fontSize: 13, fontWeight: 600, color: C.text2,
        marginBottom: 20, textAlign: "center", letterSpacing: ".01em",
      }}>
        Délai attribuable à l’entreprise par chaîne (jours)
      </div>
      <PolarHistogram
        buckets={histogram.buckets || []}
        maxCount={histogram.max_count || 0}
      />
      {histogram.under_10_count > 0 && (
        <div style={{
          textAlign: "center", marginTop: 12,
          color: C.text3, fontFamily: FONT_UI, fontSize: 12, fontStyle: "italic",
        }}>
          {fmt(histogram.under_10_count)} chaîne{histogram.under_10_count > 1 ? "s" : ""}
          {" avec moins de 10 jours de délai entreprise (non affichée"}
          {histogram.under_10_count > 1 ? "s" : ""})
        </div>
      )}
    </div>
  );
}

// ── M. Layout helpers ─────────────────────────────────────────────────────────
function SecondaryRow({ children }) {
  return (
    <div style={{ display: "flex", gap: 20, margin: "0 0 24px", flexWrap: "wrap" }}>
      {children}
    </div>
  );
}

function DormantRow({ children }) {
  return (
    <div style={{ display: "flex", gap: 20, flexWrap: "wrap" }}>
      {children}
    </div>
  );
}

// ── N. HeaderCard ─────────────────────────────────────────────────────────────
function HeaderCard({ data, onBack }) {
  const q        = data.quality;
  const docTotal = (q && !q.error && q.open_finished) ? q.open_finished.total : null;

  return (
    <header style={{
      display: "flex", alignItems: "flex-end", justifyContent: "space-between",
      borderBottom: "1px solid " + C.line, padding: "32px 0 40px",
    }}>
      <div>
        <button
          onClick={onBack}
          style={{
            background: "none", border: "1px solid " + C.line, borderRadius: 8,
            color: C.text2, padding: "6px 14px", cursor: "pointer",
            fontFamily: FONT_UI, fontSize: 12, marginBottom: 20, display: "block",
          }}
        >
          ← Retour aux entreprises
        </button>
        <div style={{
          fontFamily: FONT_UI, fontSize: 10, fontWeight: 600,
          letterSpacing: ".12em", textTransform: "uppercase",
          color: C.text3, marginBottom: 8,
        }}>
          ENTREPRISE
        </div>
        <div style={{
          fontFamily: FONT_UI, fontWeight: 200, fontSize: 72,
          letterSpacing: "-.04em", lineHeight: 0.92, color: C.text,
        }}>
          {data.contractor_name}
        </div>
        <div style={{
          fontFamily: FONT_UI, fontSize: 14, color: C.text2, marginTop: 12,
        }}>
          {data.contractor_code}
          {data.lots && data.lots.length > 0 && (
            <span> · Lots {data.lots.join(", ")}</span>
          )}
          {data.buildings && data.buildings.length > 0 && (
            <span> · Bâtiments {data.buildings.join(", ")}</span>
          )}
        </div>
      </div>

      {docTotal != null && (
        <div style={{ textAlign: "right", minWidth: 200 }}>
          <div style={{
            fontFamily: FONT_UI, fontSize: 10, fontWeight: 600,
            letterSpacing: ".12em", textTransform: "uppercase",
            color: C.text3, marginBottom: 6,
          }}>
            DOCUMENTS ACTIFS
          </div>
          <div style={{
            fontFamily: FONT_NUM, fontWeight: 200, fontSize: 80,
            letterSpacing: "-.04em", lineHeight: 0.92,
            background: "linear-gradient(180deg, #FFFFFF 0%, #9A9AA0 100%)",
            WebkitBackgroundClip: "text", WebkitTextFillColor: "transparent",
          }}>
            {fmt(docTotal)}
          </div>
        </div>
      )}
    </header>
  );
}

// ── O. QualityErrorBanner ─────────────────────────────────────────────────────
function QualityErrorBanner({ message }) {
  return (
    <div style={{
      background: C.surf2, borderRadius: 12,
      borderLeft: "4px solid " + C.bad,
      padding: "16px 20px", margin: "24px 0",
      fontFamily: FONT_UI, fontSize: 14, color: C.text,
    }}>
      {"⚠ Données qualité indisponibles : " + message}
    </div>
  );
}

// ── P. Loading / error placeholders (mirror fiche_page.jsx error block) ───────
function FicheLoadingPlaceholder({ onBack, contractor }) {
  return (
    <div style={{
      padding: 48, color: C.text2,
      animation: "fadeInUp 0.4s cubic-bezier(.4,0,.2,1)",
    }}>
      <button
        onClick={onBack}
        style={{
          background: "none", border: "1px solid " + C.line, borderRadius: 8,
          color: C.text2, padding: "6px 14px", cursor: "pointer",
          fontFamily: FONT_UI, fontSize: 12, marginBottom: 20,
        }}
      >
        ← Retour aux entreprises
      </button>
      <h1 style={{
        fontFamily: FONT_UI, fontSize: 32, fontWeight: 300,
        letterSpacing: "-.03em", color: C.text, margin: 0,
      }}>
        {contractor ? (contractor.name || "Entreprise") : "Entreprise"}
      </h1>
      <p style={{ marginTop: 14, fontSize: 14, color: C.text3 }}>
        Chargement des données…
      </p>
    </div>
  );
}

function FicheErrorPlaceholder({ onBack, contractor, message }) {
  return (
    <div style={{
      padding: 48, color: C.text2,
      animation: "fadeInUp 0.4s cubic-bezier(.4,0,.2,1)",
    }}>
      <button
        onClick={onBack}
        style={{
          background: "none", border: "1px solid " + C.line, borderRadius: 8,
          color: C.text2, padding: "6px 14px", cursor: "pointer",
          fontFamily: FONT_UI, fontSize: 12, marginBottom: 20,
        }}
      >
        ← Retour aux entreprises
      </button>
      <h1 style={{
        fontFamily: FONT_UI, fontSize: 32, fontWeight: 300,
        letterSpacing: "-.03em", color: C.text, margin: 0,
      }}>
        {contractor ? (contractor.name || "Entreprise") : "Entreprise"}
      </h1>
      <p style={{ marginTop: 14, fontSize: 14, color: C.bad }}>
        {message || "Données de fiche non disponibles."}
      </p>
    </div>
  );
}

// ── Q. Main page ──────────────────────────────────────────────────────────────
function ContractorFichePage({ contractor, onBack, focusMode }) {
  const data = window.CONTRACTOR_FICHE_DATA;

  if (!data) {
    return <FicheLoadingPlaceholder onBack={onBack} contractor={contractor} />;
  }

  if (data.error) {
    return <FicheErrorPlaceholder onBack={onBack} contractor={contractor} message={data.error} />;
  }

  const q            = data.quality;
  const qualityError = !q || !!q.error;

  return (
    <article style={{
      maxWidth: 1200, margin: "0 auto", padding: "0 56px 60px",
      background: "transparent", color: C.text, fontFamily: FONT_UI,
      animation: "fadeInUp 0.4s cubic-bezier(.4,0,.2,1)",
    }}>
      <HeaderCard data={data} onBack={onBack} />

      {qualityError && (
        <QualityErrorBanner message={q ? q.error : "Données indisponibles"} />
      )}

      {!qualityError && (
        <>
          {focusMode && (
            <div style={{
              background: C.surf2, border: "1px solid " + C.line,
              borderRadius: 10, padding: "10px 14px",
              color: C.text3, fontFamily: FONT_UI, fontSize: 12,
              marginBottom: 16,
            }}>
              Mode focus actif — sans effet sur cette fiche (prévu pour la V2).
            </div>
          )}
          <KpiStrip kpis={q.kpis} />
          <PolarHistogramSection histogram={q.polar_histogram} />
          <SecondaryRow>
            <LongChainsCard data={q.long_chains} />
            <OpenFinishedCard data={q.open_finished} />
          </SecondaryRow>
          <DormantRow>
            <DormantQueue
              title="REF en attente"
              docs={q.dormant_ref}
              emptyLabel="Aucun document REF en attente."
              onOpen={function (n, i) {
                if (window.openDocumentCommandCenter) {
                  window.openDocumentCommandCenter(n, i);
                }
              }}
            />
            <DormantQueue
              title="SAS REF en attente"
              docs={q.dormant_sas_ref}
              emptyLabel="Aucun SAS REF en attente."
              onOpen={function (n, i) {
                if (window.openDocumentCommandCenter) {
                  window.openDocumentCommandCenter(n, i);
                }
              }}
            />
          </DormantRow>
        </>
      )}
    </article>
  );
}

// ── R. Export ─────────────────────────────────────────────────────────────────
Object.assign(window, { ContractorFichePage });
