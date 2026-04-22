/* JANSA mock — full app data. P17&CO · Tranche 2.
   Shape for ConsultantFiche kept identical to calculator.py output.
   Added: overview stats, consultants directory (MOEX / Primary / Secondary),
          weekly focus series, contractor name lookup. */

(function(){

/* ── Contractor name lookup (replaces numeric codes per user feedback) ── */
const CONTRACTORS = {
  "03-GOE-LGD":    "LEGENDRE Gros Œuvre",
  "31-34-SNIE":    "SNIE Électricité",
  "41-CVC":        "AXIMA Génie Climatique",
  "42-PLB":        "HYDRAULIQUE DE FRANCE",
  "51-ASC":        "OTIS Ascenseurs",
  "04-06-ETANCH":  "SMAC Étanchéité",
  "05-MEN EXT":    "PERMASTEELISA Menuiserie",
  "B06-BFUP":      "LAFARGE BFUP",
  "12A-LAC":       "COLAS Ouvrages d'Art",
  "AH06-RVT FAC":  "NOVÉA Revêtement Façade",
  "08-MUR-RID":    "WICONA Mur Rideau",
  "13BAH-SERR":    "BLANCHET Serrurerie",
  "35-GTB":        "SCHNEIDER GTB",
  "6162-VRD":      "EUROVIA VRD",
};
window.CONTRACTORS = CONTRACTORS;

/* ── Consultant directory (grouped as MOEX / Primary / Secondary) ── */
window.CONSULTANTS = [
  // MOEX — maîtrise d'œuvre d'exécution
  { id: 1, slug: "MOEX_P17",            name: "MOEX · P17&CO",           role: "Maîtrise d'œuvre exécution", group: "MOEX",
    total: 2841, answered: 2498, pending: 268, pass_rate: 87, trend: [82,84,85,83,86,87,88,87], badge: "Pilote" },

  // Primary consultants — structural / architectural backbone
  { id: 2, slug: "ARCH_PRINCIPAL",      name: "ARCH · ATELIER MARC",     role: "Architecte principal",      group: "Primary",
    total: 1893, answered: 1674, pending: 189, pass_rate: 84, trend: [78,80,79,81,82,83,84,84], badge: null },
  { id: 3, slug: "BET_STRUCTURE_TERRELL", name: "BET STRUCTURE — TERRELL", role: "BET Structure",            group: "Primary",
    total: 1247, answered: 1066, pending: 181, pass_rate: 89, trend: [85,86,87,86,88,88,89,89], badge: null },
  { id: 4, slug: "BET_FLUIDES",         name: "BET FLUIDES — INGÉRO",    role: "BET Fluides (CVC/PLB)",     group: "Primary",
    total: 984,  answered: 832,  pending: 108, pass_rate: 85, trend: [80,82,81,83,84,84,85,85], badge: null },
  { id: 5, slug: "BET_ELEC",            name: "BET ÉLEC — VOLTEA",       role: "BET Électricité / CFO/CFA", group: "Primary",
    total: 742,  answered: 632,  pending: 78,  pass_rate: 86, trend: [82,83,84,84,85,85,86,86], badge: null },

  // Secondary — specialists
  { id: 6, slug: "ACOUSTIQUE",          name: "ACOUSTIQUE — TISSEYRE",   role: "Acoustique",                 group: "Secondary",
    total: 186,  answered: 164,  pending: 18,  pass_rate: 91, trend: [88,89,89,90,90,91,91,91], badge: null },
  { id: 7, slug: "FACADE",              name: "FAÇADE — T/E/S/S",        role: "BET Façade",                 group: "Secondary",
    total: 421,  answered: 378,  pending: 36,  pass_rate: 88, trend: [84,85,86,87,87,88,88,88], badge: null },
  { id: 8, slug: "PAYSAGISTE",          name: "PAYSAGISTE — MÉTROPOLIS", role: "Paysage",                    group: "Secondary",
    total: 98,   answered: 89,   pending: 7,   pass_rate: 93, trend: [90,91,91,92,92,92,93,93], badge: null },
  { id: 9, slug: "SECURITE_INCENDIE",   name: "SÉCURITÉ INCENDIE — CSSI",role: "SSI / Sécurité incendie",    group: "Secondary",
    total: 142,  answered: 126,  pending: 13,  pass_rate: 90, trend: [86,87,88,88,89,89,90,90], badge: null },
  { id:10, slug: "GTB",                 name: "GTB — ELITHIS",           role: "Gestion technique bâtiment", group: "Secondary",
    total: 67,   answered: 58,   pending: 8,   pass_rate: 87, trend: [83,84,85,86,86,87,87,87], badge: null },
  { id:11, slug: "CUISINES",            name: "CUISINES — AFTER",        role: "Cuisines collectives",       group: "Secondary",
    total: 54,   answered: 47,   pending: 6,   pass_rate: 89, trend: [84,85,87,88,88,89,89,89], badge: null },
  { id:12, slug: "SIGNALETIQUE",        name: "SIGNALÉTIQUE — DES SIGNES",role: "Signalétique",              group: "Secondary",
    total: 38,   answered: 32,   pending: 5,   pass_rate: 92, trend: [88,89,90,91,91,92,92,92], badge: null },
  { id:13, slug: "AMIANTE",             name: "AMIANTE — APAVE",         role: "Diagnostic amiante",         group: "Secondary",
    total: 22,   answered: 20,   pending: 2,   pass_rate: 95, trend: [91,92,93,94,94,95,95,95], badge: null },
  { id:14, slug: "ECLAIRAGE",           name: "ÉCLAIRAGE — LIGHT COGS",  role: "Conception lumière",         group: "Secondary",
    total: 73,   answered: 64,   pending: 8,   pass_rate: 88, trend: [84,85,86,87,87,88,88,88], badge: null },
];

/* ── Contractors (for "best contractor" KPI on overview) ── */
window.CONTRACTORS_LIST = [
  { code: "03-GOE-LGD",    name: CONTRACTORS["03-GOE-LGD"],    docs: 214, pass_rate: 93, delta: +2 },
  { code: "31-34-SNIE",    name: CONTRACTORS["31-34-SNIE"],    docs: 178, pass_rate: 81, delta: -1 },
  { code: "41-CVC",        name: CONTRACTORS["41-CVC"],        docs: 142, pass_rate: 88, delta: +1 },
  { code: "42-PLB",        name: CONTRACTORS["42-PLB"],        docs: 128, pass_rate: 86, delta: 0  },
  { code: "51-ASC",        name: CONTRACTORS["51-ASC"],        docs: 98,  pass_rate: 90, delta: +3 },
];

/* ── Overview KPI payload (replaces current Overview cards) ── */
window.OVERVIEW = {
  week_num: 14,
  data_date_str: "03/04/2026",
  run_number: 42,
  total_runs: 42,
  total_docs: 8412,
  total_docs_delta: +134,
  pending_blocking: 412,
  pending_blocking_delta: -23,
  refus_rate: 8.4,
  refus_rate_delta: -0.3,
  best_consultant: { name: "ACOUSTIQUE — TISSEYRE", slug: "ACOUSTIQUE", pass_rate: 91, delta: +1 },
  best_contractor: { code: "03-GOE-LGD", name: CONTRACTORS["03-GOE-LGD"], pass_rate: 93, delta: +2 },

  // Visa flow (replaces plain bar): a Sankey-ish 3-stage flow
  visa_flow: {
    submitted: 8412,
    answered:  7216,
    vso:       4826,
    vao:       1794,
    ref:        596,
    hm:         230,
    pending:   1196,
    on_time:    784,
    late:       412,
  },

  // Weekly activity — 24-S14 format (NOT 2026-S14)
  weekly: [
    { label:"24-S42", opened: 84, closed: 72, refused: 8 },
    { label:"24-S46", opened: 92, closed: 81, refused: 9 },
    { label:"24-S50", opened: 76, closed: 88, refused: 6 },
    { label:"25-S02", opened: 101, closed: 94, refused: 11 },
    { label:"25-S06", opened: 118, closed: 107, refused: 9 },
    { label:"25-S10", opened: 124, closed: 119, refused: 12 },
    { label:"25-S14", opened: 134, closed: 128, refused: 10 },
    { label:"25-S18", opened: 142, closed: 138, refused: 14 },
    { label:"25-S22", opened: 128, closed: 141, refused: 11 },
    { label:"25-S26", opened: 116, closed: 124, refused: 9  },
    { label:"25-S30", opened: 98,  closed: 112, refused: 8  },
    { label:"25-S34", opened: 132, closed: 118, refused: 13 },
    { label:"25-S38", opened: 148, closed: 134, refused: 16 },
    { label:"25-S42", opened: 156, closed: 148, refused: 15 },
    { label:"25-S46", opened: 164, closed: 152, refused: 18 },
    { label:"25-S50", opened: 142, closed: 168, refused: 14 },
    { label:"26-S02", opened: 128, closed: 144, refused: 11 },
    { label:"26-S06", opened: 136, closed: 132, refused: 12 },
    { label:"26-S10", opened: 124, closed: 128, refused: 10 },
    { label:"26-S14", opened: 118, closed: 121, refused: 9  },
  ],

  // Focus-mode KPIs
  focus: {
    focused: 412,
    p1_overdue: 47,
    p2_urgent: 89,
    p3_soon:   154,
    p4_ok:     122,
    total_dernier: 896,
    excluded: 484,
    stale: 312,
    resolved: 172,
    by_consultant: [
      { slug:"BET_STRUCTURE_TERRELL", name:"BET STRUCTURE — TERRELL", p1:14, p2:28, p3:46, p4:38 },
      { slug:"ARCH_PRINCIPAL",        name:"ARCH · ATELIER MARC",     p1:12, p2:22, p3:38, p4:31 },
      { slug:"BET_FLUIDES",           name:"BET FLUIDES — INGÉRO",    p1:9,  p2:18, p3:28, p4:22 },
      { slug:"BET_ELEC",              name:"BET ÉLEC — VOLTEA",       p1:7,  p2:12, p3:22, p4:16 },
      { slug:"FACADE",                name:"FAÇADE — T/E/S/S",        p1:3,  p2:7,  p3:12, p4:9  },
      { slug:"ACOUSTIQUE",            name:"ACOUSTIQUE — TISSEYRE",   p1:1,  p2:1,  p3:4,  p4:3  },
      { slug:"SECURITE_INCENDIE",     name:"SÉCURITÉ INCENDIE — CSSI",p1:1,  p2:1,  p3:4,  p4:3  },
    ],
  },
};

/* ── Consultant Fiche data (kept identical to calculator.py shape, but:
      · week labels reformatted to 24-S14 form
      · bloc3 lots enriched with contractor name
      · added open_blocking_* fields to match current ConsultantFiche.jsx) ── */
window.FICHE_DATA = {
  consultant: {
    id: 3, slug: "BET_STRUCTURE_TERRELL",
    display_name: "BET STRUCTURE — TERRELL",
    role: "BET Structure", merge_key: "TERRELL"
  },
  is_sas_fiche: false,
  header: {
    total: 1247, s1:"VSO", s2:"VAO", s3:"REF",
    s1_count: 612, s2_count: 341, s3_count: 89, hm_count: 24,
    open_count: 181, open_ok: 112, open_late: 69,
    open_blocking: 156, open_blocking_ok: 96, open_blocking_late: 60, open_non_blocking: 25,
    answered: 1066, week_num: 14, data_date_str: "03/04/2026",
  },
  week_delta: { total:+34, s1:+22, s2:+9, s3:+2, hm:+1, open:0, open_late:-5, open_blocking_late:-4, refus_rate_pct:-0.3 },
  bloc1: [
    { label:"Jan 24", nvx:12, doc_ferme:4,  s1:2,  s1_pct:50,   s2:1,  s2_pct:25,   s3:1,  s3_pct:25,   hm:0, hm_pct:0,   open_ok:8,  open_late:0,  open_blocking_ok:8,  open_blocking_late:0,  open_nb:0, is_current:false },
    { label:"Fév 24", nvx:22, doc_ferme:9,  s1:6,  s1_pct:66.7, s2:2,  s2_pct:22.2, s3:1,  s3_pct:11.1, hm:0, hm_pct:0,   open_ok:13, open_late:2,  open_blocking_ok:11, open_blocking_late:2,  open_nb:2, is_current:false },
    { label:"Mar 24", nvx:47, doc_ferme:31, s1:19, s1_pct:61.3, s2:8,  s2_pct:25.8, s3:3,  s3_pct:9.7,  hm:1, hm_pct:3.2, open_ok:14, open_late:2,  open_blocking_ok:12, open_blocking_late:2,  open_nb:2, is_current:false },
    { label:"Jun 24", nvx:52, doc_ferme:34, s1:21, s1_pct:61.8, s2:9,  s2_pct:26.5, s3:3,  s3_pct:8.8,  hm:1, hm_pct:2.9, open_ok:15, open_late:3,  open_blocking_ok:13, open_blocking_late:3,  open_nb:2, is_current:false },
    { label:"Sep 24", nvx:71, doc_ferme:58, s1:38, s1_pct:65.5, s2:14, s2_pct:24.1, s3:4,  s3_pct:6.9,  hm:2, hm_pct:3.4, open_ok:11, open_late:2,  open_blocking_ok:10, open_blocking_late:2,  open_nb:1, is_current:false },
    { label:"Déc 24", nvx:84, doc_ferme:72, s1:44, s1_pct:61.1, s2:20, s2_pct:27.8, s3:6,  s3_pct:8.3,  hm:2, hm_pct:2.8, open_ok:10, open_late:2,  open_blocking_ok:9,  open_blocking_late:2,  open_nb:1, is_current:false },
    { label:"Mar 25", nvx:112,doc_ferme:91, s1:56, s1_pct:61.5, s2:25, s2_pct:27.5, s3:8,  s3_pct:8.8,  hm:2, hm_pct:2.2, open_ok:18, open_late:3,  open_blocking_ok:16, open_blocking_late:3,  open_nb:2, is_current:false },
    { label:"Jun 25", nvx:128,doc_ferme:103,s1:64, s1_pct:62.1, s2:28, s2_pct:27.2, s3:9,  s3_pct:8.7,  hm:2, hm_pct:1.9, open_ok:21, open_late:4,  open_blocking_ok:18, open_blocking_late:4,  open_nb:3, is_current:false },
    { label:"Sep 25", nvx:141,doc_ferme:118,s1:72, s1_pct:61.0, s2:34, s2_pct:28.8, s3:10, s3_pct:8.5,  hm:2, hm_pct:1.7, open_ok:19, open_late:4,  open_blocking_ok:17, open_blocking_late:4,  open_nb:2, is_current:false },
    { label:"Déc 25", nvx:159,doc_ferme:134,s1:81, s1_pct:60.4, s2:38, s2_pct:28.4, s3:12, s3_pct:9.0,  hm:3, hm_pct:2.2, open_ok:22, open_late:3,  open_blocking_ok:19, open_blocking_late:3,  open_nb:3, is_current:false },
    { label:"Jan 26", nvx:61, doc_ferme:47, s1:28, s1_pct:59.6, s2:13, s2_pct:27.7, s3:5,  s3_pct:10.6, hm:1, hm_pct:2.1, open_ok:17, open_late:4,  open_blocking_ok:15, open_blocking_late:4,  open_nb:2, is_current:false },
    { label:"Fév 26", nvx:67, doc_ferme:52, s1:31, s1_pct:59.6, s2:15, s2_pct:28.8, s3:5,  s3_pct:9.6,  hm:1, hm_pct:1.9, open_ok:20, open_late:5,  open_blocking_ok:18, open_blocking_late:5,  open_nb:2, is_current:false },
    { label:"Mar 26", nvx:58, doc_ferme:41, s1:24, s1_pct:58.5, s2:13, s2_pct:31.7, s3:3,  s3_pct:7.3,  hm:1, hm_pct:2.4, open_ok:16, open_late:5,  open_blocking_ok:14, open_blocking_late:5,  open_nb:2, is_current:false },
    { label:"Avr 26", nvx:40, doc_ferme:31, s1:18, s1_pct:58.1, s2:9,  s2_pct:29.0, s3:3,  s3_pct:9.7,  hm:1, hm_pct:3.2, open_ok:22, open_late:7,  open_blocking_ok:18, open_blocking_late:6,  open_nb:4, is_current:true  },
  ],
  bloc2: {
    labels:     ["24-S12","24-S24","24-S36","24-S50","25-S10","25-S22","25-S36","25-S50","26-S10","26-S14"],
    totals:     [   81,    172,     298,     456,     612,     784,     938,     1095,    1213,    1247 ],
    s1_series:  [   41,     90,     162,     253,     338,     432,     518,      601,     628,     612 ],
    s2_series:  [   22,     50,      90,     140,     186,     238,     281,      322,     338,     341 ],
    s3_series:  [    7,     15,      27,      41,      55,      71,      84,       97,      88,      89 ],
    hm_series:  [    2,      5,       9,      15,      19,      24,      24,       24,      24,      24 ],
    open_series:[    9,     12,      10,       7,      14,      19,      31,       51,     135,     181 ],
    open_blocking_series:[ 8, 10, 8, 6, 12, 16, 26, 44, 116, 156 ],
    open_nb_series:      [ 1,  2, 2, 1,  2,  3,  5,  7,  19,  25 ],
    has_hm: true, s1:"VSO", s2:"VAO", s3:"REF"
  },
  bloc3: {
    s1:"VSO", s2:"VAO", s3:"REF",
    lots: [
      { name:"03-GOE-LGD",   contractor: CONTRACTORS["03-GOE-LGD"],   total:214, VSO:124, VAO:58, REF:12, HM:4, open_ok:12, open_late:4, open_blocking_ok:11, open_blocking_late:4, open_nb:1 },
      { name:"31-34-SNIE",   contractor: CONTRACTORS["31-34-SNIE"],   total:178, VSO:96,  VAO:52, REF:14, HM:3, open_ok:9,  open_late:4, open_blocking_ok:8,  open_blocking_late:4, open_nb:1 },
      { name:"41-CVC",       contractor: CONTRACTORS["41-CVC"],       total:142, VSO:78,  VAO:38, REF:9,  HM:2, open_ok:11, open_late:4, open_blocking_ok:9,  open_blocking_late:4, open_nb:2 },
      { name:"42-PLB",       contractor: CONTRACTORS["42-PLB"],       total:128, VSO:71,  VAO:34, REF:8,  HM:2, open_ok:9,  open_late:4, open_blocking_ok:8,  open_blocking_late:4, open_nb:1 },
      { name:"51-ASC",       contractor: CONTRACTORS["51-ASC"],       total:98,  VSO:52,  VAO:28, REF:6,  HM:2, open_ok:7,  open_late:3, open_blocking_ok:6,  open_blocking_late:3, open_nb:1 },
      { name:"04-06-ETANCH", contractor: CONTRACTORS["04-06-ETANCH"], total:89,  VSO:48,  VAO:24, REF:7,  HM:1, open_ok:6,  open_late:3, open_blocking_ok:5,  open_blocking_late:3, open_nb:1 },
      { name:"05-MEN EXT",   contractor: CONTRACTORS["05-MEN EXT"],   total:76,  VSO:41,  VAO:21, REF:5,  HM:1, open_ok:6,  open_late:2, open_blocking_ok:5,  open_blocking_late:2, open_nb:1 },
      { name:"B06-BFUP",     contractor: CONTRACTORS["B06-BFUP"],     total:68,  VSO:36,  VAO:19, REF:5,  HM:1, open_ok:5,  open_late:2, open_blocking_ok:4,  open_blocking_late:2, open_nb:1 },
      { name:"12A-LAC",      contractor: CONTRACTORS["12A-LAC"],      total:58,  VSO:29,  VAO:17, REF:4,  HM:1, open_ok:5,  open_late:2, open_blocking_ok:4,  open_blocking_late:2, open_nb:1 },
      { name:"AH06-RVT FAC", contractor: CONTRACTORS["AH06-RVT FAC"], total:52,  VSO:27,  VAO:15, REF:3,  HM:1, open_ok:4,  open_late:2, open_blocking_ok:3,  open_blocking_late:2, open_nb:1 },
      { name:"08-MUR-RID",   contractor: CONTRACTORS["08-MUR-RID"],   total:48,  VSO:25,  VAO:14, REF:3,  HM:1, open_ok:4,  open_late:1, open_blocking_ok:3,  open_blocking_late:1, open_nb:1 },
      { name:"13BAH-SERR",   contractor: CONTRACTORS["13BAH-SERR"],   total:42,  VSO:22,  VAO:12, REF:3,  HM:0, open_ok:4,  open_late:1, open_blocking_ok:3,  open_blocking_late:1, open_nb:1 },
      { name:"35-GTB",       contractor: CONTRACTORS["35-GTB"],       total:32,  VSO:17,  VAO:9,  REF:2,  HM:1, open_ok:2,  open_late:1, open_blocking_ok:2,  open_blocking_late:1, open_nb:0 },
      { name:"6162-VRD",     contractor: CONTRACTORS["6162-VRD"],     total:22,  VSO:12,  VAO:6,  REF:1,  HM:1, open_ok:2,  open_late:0, open_blocking_ok:2,  open_blocking_late:0, open_nb:0 },
    ],
    total_row: { name:"TOTAL", total:1247, VSO:612, VAO:341, REF:89, HM:24, open_ok:86, open_late:33 },
    donut_ok: 112, donut_late: 69, donut_nb: 25, donut_total: 181,
    critical_lots: [
      { name:"LEGENDRE Gros Œuvre",    open_late:4 },
      { name:"SNIE Électricité",       open_late:4 },
      { name:"AXIMA Génie Climatique", open_late:4 },
      { name:"HYDRAULIQUE DE FRANCE",  open_late:4 },
      { name:"OTIS Ascenseurs",        open_late:3 },
    ],
    refus_lots: [
      [{ name:"SNIE Électricité"       }, 10.5],
      [{ name:"SMAC Étanchéité"        }, 9.3 ],
      [{ name:"LEGENDRE Gros Œuvre"    }, 6.2 ],
      [{ name:"OTIS Ascenseurs"        }, 6.2 ],
      [{ name:"LAFARGE BFUP"           }, 6.1 ],
    ]
  }
};

})();
