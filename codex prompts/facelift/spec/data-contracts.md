# Data contracts — the shapes the API must return

These are copied verbatim from `prototype/jansa/data.js`. Any deviation will
break the frontend.

## GET /api/overview

```ts
interface OverviewPayload {
  week_num: number;              // e.g. 14
  data_date_str: string;         // "03/04/2026"
  run_number: number;
  total_runs: number;

  total_docs: number;
  total_docs_delta: number;      // vs prev week

  pending_blocking: number;
  pending_blocking_delta: number;

  refus_rate: number;            // percent, 1 decimal
  refus_rate_delta: number;

  best_consultant: { name: string; slug: string; pass_rate: number; delta: number };
  best_contractor: { code: string; name: string; pass_rate: number; delta: number };

  visa_flow: {
    submitted: number; answered: number;
    vso: number; vao: number; ref: number; hm: number;
    pending: number; on_time: number; late: number;
  };

  weekly: Array<{
    label: string;     // "26-S14" format — NOT "2026-S14"
    opened: number;
    closed: number;
    refused: number;
  }>;

  focus: {
    focused: number;
    p1_overdue: number; p2_urgent: number; p3_soon: number; p4_ok: number;
    total_dernier: number; excluded: number; stale: number; resolved: number;
    by_consultant: Array<{ slug: string; name: string; p1: number; p2: number; p3: number; p4: number }>;
  };
}
```

## GET /api/consultants

```ts
interface ConsultantRow {
  id: number;
  slug: string;
  name: string;             // full display name, e.g. "BET STRUCTURE — TERRELL"
  role: string;
  group: "MOEX" | "Primary" | "Secondary";
  total: number;
  answered: number;
  pending: number;
  pass_rate: number;
  trend: number[];          // length 8, pass_rate over 8 weeks
  badge: string | null;     // e.g. "Pilote" for MOEX
}

type ConsultantsResponse = ConsultantRow[];
```

## GET /api/consultants/{slug}/fiche

```ts
interface FicheData {
  consultant: { id: number; slug: string; display_name: string; role: string; merge_key: string };
  is_sas_fiche: boolean;
  header: {
    total: number;
    s1: "VSO" | "FAV"; s2: "VAO" | "SUS"; s3: "REF" | "DEF";
    s1_count: number; s2_count: number; s3_count: number; hm_count: number;
    open_count: number; open_ok: number; open_late: number;
    open_blocking: number; open_blocking_ok: number; open_blocking_late: number; open_non_blocking: number;
    answered: number; week_num: number; data_date_str: string;
  };
  week_delta: {
    total: number; s1: number; s2: number; s3: number; hm: number;
    open: number; open_late: number; open_blocking_late: number; refus_rate_pct: number;
  };
  bloc1: Array<{
    label: string;           // "Avr 26"
    nvx: number; doc_ferme: number;
    s1: number; s1_pct: number;
    s2: number; s2_pct: number;
    s3: number; s3_pct: number;
    hm: number; hm_pct: number;
    open_ok: number; open_late: number;
    open_blocking_ok: number; open_blocking_late: number; open_nb: number;
    is_current: boolean;
  }>;
  bloc2: {
    labels: string[];        // "24-S12" format
    totals: number[];
    s1_series: number[]; s2_series: number[]; s3_series: number[];
    hm_series: number[]; open_series: number[];
    open_blocking_series: number[]; open_nb_series: number[];
    has_hm: boolean;
    s1: string; s2: string; s3: string;
  };
  bloc3: {
    s1: string; s2: string; s3: string;
    lots: Array<{
      name: string;          // code e.g. "03-GOE-LGD"
      contractor: string;    // human name e.g. "LEGENDRE Gros Œuvre" — REQUIRED
      total: number;
      VSO: number; VAO: number; REF: number; HM: number;
      open_ok: number; open_late: number;
      open_blocking_ok: number; open_blocking_late: number; open_nb: number;
    }>;
    total_row: { name: "TOTAL"; total: number; VSO: number; VAO: number; REF: number; HM: number; open_ok: number; open_late: number };
    donut_ok: number; donut_late: number; donut_nb: number; donut_total: number;
    critical_lots: Array<{ name: string; open_late: number }>;
    refus_lots: Array<[{ name: string }, number]>;  // tuple: [{name}, pct]
  };
}
```

## GET /api/runs

```ts
interface Run {
  id: number;
  started_at: string;   // ISO
  finished_at: string;
  status: "success" | "failed" | "running";
  docs_processed: number;
  triggered_by: string; // "schedule" | user email
}
type RunsResponse = Run[];
```

## GET /api/health

```ts
{ ok: true, version: string }
```
