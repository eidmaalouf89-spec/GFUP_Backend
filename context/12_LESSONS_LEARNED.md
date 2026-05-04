# 12 — Lessons Learned

## Lesson 1 — Cache Regeneration Can Expose Dormant Parser Bugs

### What happened
During Phase 6 smoke testing, the UI appeared corrupted:
- dashboard data changed unexpectedly
- consultants showed impossible answered counts
- contractors pass rates became zero/corrupted
- the app appeared to load too fast

Initial suspicion was Phase 6C UI wiring or Phase 6B bridge/API additions, but isolation showed:
- shell.jsx and jansa-connected.html rollback did not fix it
- removing Phase 6B data_bridge.js methods did not fix it
- removing Phase 6B app.py methods did not fix it
- backend API payloads were already corrupted

### Root cause
The FLAT_GED cache had been regenerated from an existing FLAT_GED.xlsx where response dates were read as integer nanosecond timestamps, for example:
```
1746576000000000000 → 2025-05-07
```

`src/normalize.py::interpret_date_field()` handled `datetime`/`date` and string cases, but did not handle `int`/`float` nanosecond timestamps.

As a result:
- real answered response dates became `date_answered = None`
- `date_status_type` became `NOT_CALLED`
- `date_status_type == ANSWERED` count became 0
- aggregator `answered` counts became 0
- VSO/VAO/REF/HM status counts remained non-zero (from `status_clean`)
- UI payloads became internally inconsistent

Example diagnostic signal:
```
consultants[0].answered = 0
consultants[0].vso / vao / ref / hm  non-zero   ← internal contradiction
```

### Fix
Minimal hotfix — two files changed, one test file added:

- `src/normalize.py`: add `int`/`float` nanosecond timestamp branch in `interpret_date_field()`
- `src/reporting/data_loader.py`: bump `CACHE_SCHEMA_VERSION` `v2` → `v3` to force cache rebuild
- `tests/test_normalize_interpret_date_field.py`: 12 unit tests covering all branches
- cache backup to `output/intermediate/_cache_backup_pre_date_hotfix/` before rebuild
- cache regenerated automatically via the existing schema-version invalidation mechanism

Validation after fix:

| Metric | Before | After |
|---|---|---|
| `date_status_type == ANSWERED` | 0 | 16,223 |
| `date_answered` non-null | 0 | 16,223 |
| `overview.visa_flow.answered` | 0 | 1,111 |
| `overview.refus_rate` | 0.0 % | 6.6 % |
| Contractors with `pass_rate > 0` | 0 / 30 | 21 / 30 |

### How to detect similar issues early
Add/keep diagnostic checks after any cache rebuild or parser change:

**1. Internal consistency checks**
- if `VSO + VAO + REF + HM > 0`, then `answered` must not be 0
- if `status_clean` has answer statuses, `date_status_type == ANSWERED` must be > 0
- `date_answered` non-null count should broadly align with answered status count

**2. Cache metadata checks**
- inspect `FLAT_GED_cache_meta.json` after rebuild
- verify `cache_schema_version`, `generated_at`, `source_flat_ged_mtime`
- verify `responses_df_rows` and `status_counts` are plausible

**3. Backend API smoke checks (run before launching UI)**
```python
from app import Api
api = Api()
api.get_overview_for_ui()      # check visa_flow.answered > 0
api.get_consultants_for_ui()   # check consultants[*].answered consistent with vso/vao/ref/hm
api.get_contractors_for_ui()   # check pass_rate not all zero
```

**4. Visual smoke checks**
- Overview: answered / pending / refus_rate plausible
- Consultants: answered counts non-zero
- Contractors: pass rates non-zero
- App load time: not suspiciously instant (may indicate cache miss or empty payload)

### Guardrail
After any future cache rebuild, parser update, data-loader change, or phase touching app startup:

- run backend payload sanity checks before trusting the UI
- do not assume a UI regression is caused by the latest UI change
- isolate in order: UI wiring → bridge → backend API payload → cache/data source
- always distinguish four failure layers:

```
1. UI display / WebView / bridge issue     (fix: UI files)
2. Backend API computation bug             (fix: aggregator / fiche logic)
3. Cache content corrupted                 (fix: parser / normalizer + cache rebuild)
4. Source data issue                       (fix: re-export / re-run pipeline)
```

### Status
Resolved.
Root cause fixed and smoke-test validated.
Phase 6 may resume only after baseline UI is confirmed green.

## Lesson 2 — `data_date` ≠ FLAT_GED cache `generated_at`

### What happened
During Phase 6X audits 6X.0B and 6X.A/B, we tried to reproduce 133005 indice C's
audited "15 days late" status using `data_date = 2026-05-04`. The reproduction
failed: in the actual run the indice was *not late at all* (deadline 2026-04-17,
7 days remaining). Several follow-on diagnostics drifted toward proposing a
`wait_days > N` threshold, which was the wrong direction.

### Root cause
We used the FLAT_GED cache `generated_at` field (a metadata timestamp written
when the cache pickle was last regenerated, currently 2026-05-04) as if it
were the GED export's business `data_date`. The actual `data_date` lives in
the raw GED Excel "Détails" sheet at cell `[15,4]` — currently 2026-04-10 —
and is read by `_read_ged_data_date` in `data_loader.py`. The two fields
agree on cache-rebuild day and drift apart on every other day. A single
business day of drift was enough to flip 133005 C's lateness verdict.

### Why this kept misleading
- Both fields are dates that look like a "freshness" stamp.
- `generated_at` is the more visible artifact (it's in `FLAT_GED_cache_meta.json`,
  inspected by every cache-freshness check).
- `ctx.data_date` is buried inside `RunContext` and not surfaced in any UI.
- Earlier audits silently assumed `today() ≈ data_date` because the cache had
  been regenerated that morning.

### Fix
- Phase 6X.A3 audit confirmed the distinction explicitly: the GED Détails
  sheet is the only authoritative source for `data_date`.
- Phase 6X.C / 6X.D removed every `date.today()` and `ctx.data_date or
  date.today()` business-fallback in `consultant_fiche.py` and
  `contractor_quality.py`. Functions now raise `ValueError` if `ctx.data_date`
  is None — failures are loud, not silent.
- Phase 6X.E exposed deadline truth (`min_open_consultant_deadline`,
  `consultant_days_remaining`) computed from `responses_df.date_limite`
  against `ctx.data_date`. No threshold, no `today()`.

### Guardrail
- **Never** treat `cache_meta_v2.generated_at` as the business `data_date`.
- **Never** introduce a `wait_days > N` threshold for consultant lateness —
  the answer is in the response's `date_limite`, not in elapsed time.
- New reporting code that needs a "today" reference must read it from
  `ctx.data_date` and must raise (not fall back) if it's None. The grep:
  ```bash
  grep -nE "date\.today|datetime\.today|datetime\.now|pd\.Timestamp\.today|pd\.Timestamp\.now" \
    src/reporting/*.py
  ```
  Expected matches: only display-only fallbacks (`ui_adapter.py:92`) and
  metadata timestamps (`consultant_report_builder.py:147`).

### Status
Closed by Phase 6X (2026-05-04).

---

## Lesson 3 — Untracked operational files have no git safety net

### What happened
During the 6X.F2-bis closure attempt, a consolidated Python patch script
intended to apply F1.5 + E2 + F2-bis in one pass corrupted
`src/reporting/counter_attack_builder.py` to 0 bytes. The script chained
three failures: an unsupported `Path.read_text(newline=...)` kwarg, a `sed`
substitution that mangled `\n` into `\\n`, and an `open(path, "w",
newline="\\n")` call. `open(..., "w")` truncates the file *at open time*
before the `newline=` argument is validated, so the resulting `ValueError`
left the file at 0 bytes.

### Why recovery was hard
- `counter_attack_builder.py` was **untracked in git** (`?? src/reporting/...`),
  added by pre-existing uncommitted Phase 6 work. `git checkout HEAD --`
  could not restore it.
- The local `backup/` and `backups/` folders only held April archives; the
  builder file post-dated them.
- A `/tmp/counter_attack_builder_pre_s3.py` snapshot existed (28 070 bytes,
  dated 2026-05-04 15:40) but was owned by `nobody:nogroup` and unreadable
  to the sandbox uid (`cat: Permission denied`).
- Reconstructing from conversation memory alone would have been partial and
  risky.
- Final recovery + R1/R2/R3 reconstruction was completed by Codex outside
  Cowork.

### Root cause
Two compounding mistakes:
1. **Multi-step patch script with no on-disk pre-patch backup.** The script
   touched two files and applied three independent patches; the first
   write succeeded but the third never reached disk in a valid state. No
   `.pre-<step>` snapshot was made before the script ran.
2. **Trusting that anchor-checked Python rewrites were sufficient safety.**
   The anchor checks defended against the wrong file getting patched, but
   not against an `open(..., "w", ...)` truncation between anchor verification
   and final write.

### Fix
- All untracked source files were inventoried after the incident. Only one
  was destroyed; `consultant_fiche.py`, `contractor_quality.py`, and
  `document_command_center.py` survived with their phase patches intact.
- A new operating rule: **for any patch on an untracked file, write an
  explicit `cp <file> /tmp/<basename>.pre-<step>` backup first.** Verify the
  backup is readable (UID-owned, non-zero size, `py_compile` clean if it's
  Python) before the patch runs.

### Guardrail
- Before any code-mutating script:
  ```bash
  if ! git ls-files --error-unmatch <file> >/dev/null 2>&1; then
    cp <file> /tmp/$(basename <file>).pre-<step-id>
  fi
  ```
- Never assume `open(..., "w", ...)` arg validation runs before truncation.
  Use `open(..., "x", ...)` to fail-on-exists when paranoid, or write to a
  temp path and `os.replace` atomically.
- For multi-file consolidated patches, prefer N small scripts each with its
  own pre-patch backup over one large script.
- Closing a phase against an untracked file requires either committing it
  first, or explicitly noting in the closure that the artifact is stash-only.

### Status
Closed by Phase 6X (2026-05-04). See `11_TOOLING_HAZARDS.md` 2026-05-04
change-log row for the operational hazard pairing.
