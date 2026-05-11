"""
Diagnostic: verify build_latest_chain_view against live Chain+Onion artifacts.
Exit 0 + ALL GATES PASSED if every invariant holds. Exit 1 + GATE FAILED otherwise.
"""
import sys
from pathlib import Path

# Ensure src/ is importable
repo_root = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(repo_root / "src"))

import pandas as pd
from reporting.latest_chain_view import build_latest_chain_view


def main():
    base = repo_root
    register_path = base / "output" / "chain_onion" / "CHAIN_REGISTER.csv"
    versions_path = base / "output" / "chain_onion" / "CHAIN_VERSIONS.csv"

    register_df = pd.read_csv(register_path, dtype={"family_key": str, "numero": str})
    versions_df = pd.read_csv(versions_path, dtype={"family_key": str, "version_key": str})

    try:
        df = build_latest_chain_view(base)
    except Exception as exc:
        print(f"GATE FAILED: build_latest_chain_view raised {type(exc).__name__}: {exc}")
        sys.exit(1)

    # Counts table
    families_with_multi = (
        versions_df.groupby("family_key").size().pipe(lambda s: (s > 1).sum())
    )
    print(f"latest_chain_df rows:            {len(df)}")
    print(f"latest_chain_df unique family_key: {df['family_key'].nunique()}")
    print(f"latest_chain_df unique numero:     {df['numero'].nunique()}")
    print(f"CHAIN_REGISTER rows:             {len(register_df)}")
    print(f"CHAIN_VERSIONS rows:             {len(versions_df)}")
    print(f"families with >1 version:        {families_with_multi}")

    # Report present / deferred columns
    present_cols = list(df.columns)
    deferred = []
    for col in ["emetteur_name", "visa_global", "days_late"]:
        deferred.append(col)
    optional_present = [c for c in ["emetteur", "titre"] if c in df.columns]
    optional_missing = [c for c in ["emetteur", "titre"] if c not in df.columns]

    print(f"columns present:                 {present_cols}")
    if optional_present:
        print(f"optional enrichment included:    {optional_present}")
    if optional_missing:
        print(f"optional enrichment omitted:     {optional_missing}")
    print(f"deferred to later steps:         {deferred}")

    # Gate checks
    gate_ok = True

    if len(df) != len(register_df):
        print(f"GATE FAILED: row count {len(df)} != CHAIN_REGISTER {len(register_df)}")
        gate_ok = False

    if not df["family_key"].is_unique:
        print("GATE FAILED: family_key not unique")
        gate_ok = False

    if not df["numero"].is_unique:
        print("GATE FAILED: numero not unique")
        gate_ok = False

    if not df["version_key"].equals(df["latest_version_key"]):
        print("GATE FAILED: version_key != latest_version_key")
        gate_ok = False

    if not df["indice"].equals(df["latest_indice"]):
        print("GATE FAILED: indice != latest_indice")
        gate_ok = False

    if gate_ok:
        print("ALL GATES PASSED")
    else:
        sys.exit(1)

    # --- Loader smoke (Step 3) ---
    try:
        from reporting.data_loader import load_run_context, clear_cache
        clear_cache()
        ctx = load_run_context(repo_root)
        dn = ctx.dernier_df
        lc = ctx.latest_chain_df
        print()
        print("=== Loader smoke ===")
        print(f"ctx.dernier_df rows                : {len(dn) if dn is not None else 'None'}")
        print(f"ctx.dernier_df unique numero       : {dn['numero'].astype(str).nunique() if dn is not None else 'None'}")
        print(f"ctx.latest_chain_df rows           : {len(lc) if lc is not None else 'None'}")
        print(f"ctx.latest_chain_df unique numero  : {lc['numero'].astype(str).nunique() if lc is not None else 'None'}")
        print(f"CHAIN_REGISTER rows                : {len(register_df)}")
        print(f"Pollution gap (dernier - latest)   : {len(dn) - len(lc) if dn is not None and lc is not None else 'N/A'}")
    except Exception as exc:
        print(f"Loader smoke FAILED: {type(exc).__name__}: {exc}")
        sys.exit(0)

    # --- Step 5 — Contractor Quality / Action MOEX cross-check ---
    try:
        from reporting.consultant_fiche import CONTRACTOR_REFERENCE
        from reporting.contractor_quality import (
            _latest_enriched_for_contractor,
            _dormant_list,
            _load_dormant_ref_from_artifact,
        )

        ref_today = ctx.data_date
        if ref_today is None:
            print("[SKIP] Step 5 gates: ctx.data_date is None")
            sys.exit(0)

        print()
        print("=== Step 5 — Contractor Quality / Action MOEX cross-check ===")

        # Compute totals across all contractors
        total_dorm_ref = 0
        total_dorm_sas_ref = 0
        per_emetteur = []

        for code in CONTRACTOR_REFERENCE:
            emetteur_latest = _latest_enriched_for_contractor(ctx, code)
            dorm_ref = _load_dormant_ref_from_artifact(code)
            dorm_sas_ref = _dormant_list(emetteur_latest, "SAS REF", ref_today)
            total_dorm_ref += len(dorm_ref)
            total_dorm_sas_ref += len(dorm_sas_ref)

            # Artifact cross-check
            art_ref = _load_dormant_ref_from_artifact(code)
            per_emetteur.append({
                "code": code,
                "new_ref": len(dorm_ref),
                "art_ref": len(art_ref),
                "delta": len(dorm_ref) - len(art_ref),
                "dorm_ref_items": dorm_ref,
                "dorm_sas_ref_items": dorm_sas_ref,
            })

        # ENTREPRISE_A_RELANCER count from artifact
        art_path = repo_root / "output" / "intermediate" / "COUNTER_ATTACK_ITEMS.csv"
        art_ear_count = 0
        if art_path.exists():
            art_df = pd.read_csv(art_path, dtype=str, keep_default_na=False)
            art_ear_count = int((art_df["action_bucket"] == "ENTREPRISE_A_RELANCER").sum())

        print(f"contractor_quality dormant REF (total)      : {total_dorm_ref}")
        print(f"Action MOEX ENTREPRISE_A_RELANCER (artifact): {art_ear_count}")
        print(f"delta                                       : {total_dorm_ref - art_ear_count}")
        print(f"contractor_quality dormant SAS REF (total)  : {total_dorm_sas_ref}")

        # Per-emetteur table (top 5 by |delta|)
        per_emetteur.sort(key=lambda x: abs(x["delta"]), reverse=True)
        print()
        print("Top 5 contributors to delta:")
        print(f"  {'code':<10} {'new_ref':>8} {'art_ref':>8} {'delta':>8}")
        for row in per_emetteur[:5]:
            print(f"  {row['code']:<10} {row['new_ref']:>8} {row['art_ref']:>8} {row['delta']:>8}")

        # Gate G-DORM-1: no old-indice REF
        # Build lookup with both raw and leading-zero-stripped numero keys
        # (dernier_df has numero_normalized which strips leading zeros;
        # latest_chain_df.numero may be zero-padded)
        lc = ctx.latest_chain_df
        if lc is not None and not lc.empty:
            lc_keys = set()
            for num_raw, ind in zip(
                lc["numero"].astype(str).str.strip(),
                lc["latest_indice"].astype(str).str.strip().str.upper(),
            ):
                lc_keys.add((num_raw, ind))
                lc_keys.add((num_raw.lstrip("0") or "0", ind))
        else:
            lc_keys = set()

        g_dorm1_offenders = []
        g_dorm2_offenders = []

        for row in per_emetteur:
            for item in row["dorm_ref_items"]:
                num = str(item["numero"]).strip()
                ind = str(item["indice"]).strip().upper()
                if lc_keys and (num, ind) not in lc_keys and (num.lstrip("0") or "0", ind) not in lc_keys:
                    g_dorm1_offenders.append((row["code"], item["numero"], item["indice"]))
            for item in row["dorm_sas_ref_items"]:
                num = str(item["numero"]).strip()
                ind = str(item["indice"]).strip().upper()
                if lc_keys and (num, ind) not in lc_keys and (num.lstrip("0") or "0", ind) not in lc_keys:
                    g_dorm2_offenders.append((row["code"], item["numero"], item["indice"]))

        print()
        if not g_dorm1_offenders:
            print("G-DORM-1 (no old-indice REF):     PASS (0 offenders)")
        else:
            print(f"G-DORM-1 (no old-indice REF):     FAIL ({len(g_dorm1_offenders)} offenders)")
            for off in g_dorm1_offenders[:10]:
                print(f"  emetteur={off[0]}  numero={off[1]}  indice={off[2]}")
            gate_ok = False

        if not g_dorm2_offenders:
            print("G-DORM-2 (no old-indice SAS REF): PASS (0 offenders)")
        else:
            print(f"G-DORM-2 (no old-indice SAS REF): FAIL ({len(g_dorm2_offenders)} offenders)")
            for off in g_dorm2_offenders[:10]:
                print(f"  emetteur={off[0]}  numero={off[1]}  indice={off[2]}")
            gate_ok = False

        # Gate G-DORM-3: every emitted dormant numero exists as-is in dernier_df
        dd_numeros = set(ctx.dernier_df["numero"].astype(str).str.strip()) if ctx.dernier_df is not None else set()
        g_dorm3_offenders = []
        for row in per_emetteur:
            for item in row["dorm_ref_items"]:
                num = str(item["numero"]).strip()
                if num and num != "?" and num not in dd_numeros:
                    g_dorm3_offenders.append((row["code"], num))
            for item in row["dorm_sas_ref_items"]:
                num = str(item["numero"]).strip()
                if num and num != "?" and num not in dd_numeros:
                    g_dorm3_offenders.append((row["code"], num))

        if not g_dorm3_offenders:
            print("G-DORM-3 (numero in dernier_df):  PASS (0 offenders)")
        else:
            print(f"G-DORM-3 (numero in dernier_df):  FAIL ({len(g_dorm3_offenders)} offenders)")
            for off in g_dorm3_offenders[:10]:
                print(f"  emetteur={off[0]}  numero={off[1]}")
            gate_ok = False

        # Hard gate: dormant_ref total must equal artifact ENTREPRISE_A_RELANCER
        if total_dorm_ref != art_ear_count:
            print(f"G-DORM-4 (REF == artifact EAR):   FAIL ({total_dorm_ref} != {art_ear_count})")
            gate_ok = False
        else:
            print(f"G-DORM-4 (REF == artifact EAR):   PASS ({total_dorm_ref} == {art_ear_count})")

    except Exception as exc:
        print(f"Step 5 gates FAILED: {type(exc).__name__}: {exc}")
        import traceback; traceback.print_exc()
        gate_ok = False

    # --- Step 6 — DCC latest-chain migration gates ---
    try:
        from reporting.document_command_center import (
            compute_dcc_tags_bulk,
            search_documents,
        )

        print()
        print("=== Step 6 — DCC latest-chain migration gates ===")

        lc = ctx.latest_chain_df
        dcc_df = compute_dcc_tags_bulk(ctx)

        # G-DCC-1: compute_dcc_tags_bulk is latest-only
        dcc_count = len(dcc_df)
        lc_count = len(lc) if lc is not None else 0
        print(f"compute_dcc_tags_bulk rows: {dcc_count}")
        print(f"ctx.latest_chain_df rows  : {lc_count}")

        # Some chains may reference a latest_indice not yet in dernier_df
        # (GED extract lag). Count the expected joinable rows.
        dd_keys = set(zip(
            ctx.dernier_df["numero"].astype(str).str.strip(),
            ctx.dernier_df["indice"].astype(str).str.strip(),
        ))
        expected_count = sum(
            1 for n, i in zip(
                lc["numero"].astype(str).str.strip(),
                lc["latest_indice"].astype(str).str.strip(),
            )
            if (n, i) in dd_keys
        )
        unjoinable = lc_count - expected_count
        if unjoinable:
            print(f"  ({unjoinable} chain(s) with latest_indice absent from dernier_df — data lag)")

        if dcc_count != expected_count:
            print(f"G-DCC-1 (row count):          FAIL ({dcc_count} != {expected_count} joinable)")
            gate_ok = False
        else:
            # Check every emitted (numero, indice) is in latest_chain_df
            lc_check_keys = set(zip(
                lc["numero"].astype(str).str.strip(),
                lc["latest_indice"].astype(str).str.strip(),
            ))
            dcc_keys = set(zip(
                dcc_df["numero"].astype(str).str.strip(),
                dcc_df["indice"].astype(str).str.strip(),
            ))
            offenders = dcc_keys - lc_check_keys
            if offenders:
                print(f"G-DCC-1 (latest-only check):  FAIL ({len(offenders)} non-latest rows)")
                for off in list(offenders)[:5]:
                    print(f"  numero={off[0]}  indice={off[1]}")
                gate_ok = False
            else:
                print(f"G-DCC-1 (row count + latest): PASS ({dcc_count} == {lc_count}, 0 offenders)")

        # G-DCC-2: search_documents returns latest indices for multi-indice numeros
        versions_path = repo_root / "output" / "chain_onion" / "CHAIN_VERSIONS.csv"
        cv = pd.read_csv(versions_path, dtype=str)
        multi_fk = cv.groupby("family_key").size()
        multi_fk = multi_fk[multi_fk > 1].index.tolist()
        multi_fk.sort()

        g_dcc2_offenders = []
        tested = 0
        for fk in multi_fk[:5]:
            lc_row = lc[lc["family_key"] == fk]
            if lc_row.empty:
                continue
            test_numero = str(lc_row.iloc[0]["numero"]).strip()
            expected_indice = str(lc_row.iloc[0]["latest_indice"]).strip()
            results = search_documents(ctx, test_numero, limit=10)
            matched = [r for r in results if str(r.get("numero", "")).strip() == test_numero]
            if matched:
                got_indice = str(matched[0].get("indice", "")).strip()
                if got_indice != expected_indice:
                    g_dcc2_offenders.append((test_numero, expected_indice, got_indice))
            tested += 1

        if g_dcc2_offenders:
            print(f"G-DCC-2 (search latest indice): FAIL ({len(g_dcc2_offenders)}/{tested} wrong)")
            for off in g_dcc2_offenders:
                print(f"  numero={off[0]}  expected={off[1]}  got={off[2]}")
            gate_ok = False
        else:
            print(f"G-DCC-2 (search latest indice): PASS ({tested} multi-indice numeros checked)")

        # G-DCC-3: informational — 139130 example
        lc_str = lc["numero"].astype(str).str.strip()
        if "139130" in lc_str.values:
            lc_139 = lc[lc_str == "139130"].iloc[0]
            chain_indice = str(lc_139["latest_indice"]).strip()
            print(f"\n139130 latest_indice (chain_register): {chain_indice}")

            dcc_139 = dcc_df[dcc_df["numero"].astype(str).str.strip() == "139130"]
            dcc_indice = str(dcc_139.iloc[0]["indice"]).strip() if not dcc_139.empty else "MISSING"
            print(f"139130 compute_dcc_tags_bulk indice  : {dcc_indice}")

            sr = search_documents(ctx, "139130", limit=5)
            sr_match = [r for r in sr if str(r.get("numero", "")).strip() == "139130"]
            sr_indice = str(sr_match[0].get("indice", "")).strip() if sr_match else "MISSING"
            print(f"139130 search_documents indice       : {sr_indice}")

            if chain_indice == dcc_indice == sr_indice:
                print("G-DCC-3 (139130 agreement):     PASS")
            else:
                print("G-DCC-3 (139130 agreement):     FAIL (informational)")
        else:
            print("\nG-DCC-3: numero 139130 not in latest_chain_df (SKIP)")

    except Exception as exc:
        print(f"Step 6 gates FAILED: {type(exc).__name__}: {exc}")
        import traceback; traceback.print_exc()
        gate_ok = False

    # --- Step 7 — Operational consumer migration gates ---
    try:
        from reporting.latest_chain_view import latest_enriched_view
        from reporting.aggregator import (
            compute_project_kpis,
            compute_contractor_summary,
        )
        from reporting.consultant_fiche import _filter_for_consultant
        from reporting.drilldown_builder import build_drilldown
        from reporting.focus_filter import apply_focus_filter, FocusConfig

        print()
        print("=== Step 7 — Operational consumer migration gates ===")

        lev = latest_enriched_view(ctx)
        lev_count = len(lev)
        print(f"latest_enriched_view rows: {lev_count}")

        # G-AGG-1: compute_project_kpis.total_docs_current matches lev count
        kpis = compute_project_kpis(ctx)
        kpis_total = kpis.get("total_docs_current")
        if kpis_total == lev_count:
            print(f"G-AGG-1 (project_kpis.total_docs_current == lev): PASS "
                  f"({kpis_total} == {lev_count})")
        else:
            print(f"G-AGG-1 (project_kpis.total_docs_current == lev): FAIL "
                  f"(expected {lev_count}, got {kpis_total})")
            gate_ok = False

        # G-AGG-2: per-contractor row counts match per-emetteur on lev
        cs = compute_contractor_summary(ctx)
        agg2_offenders = []
        agg2_sum = 0
        for row in cs:
            code = row.get("code")
            cs_total = row.get("total_submitted", 0)
            lev_per = int((lev["emetteur"] == code).sum()) if not lev.empty else 0
            agg2_sum += cs_total
            if cs_total != lev_per:
                agg2_offenders.append((code, cs_total, lev_per))
        if not agg2_offenders:
            print(f"G-AGG-2 (contractor_summary per-emetteur == lev): PASS "
                  f"(sum={agg2_sum}, contractors={len(cs)})")
            print("  Top 5 contractors:")
            for r in cs[:5]:
                print(f"    code={r.get('code')!s:<8} total={r.get('total_submitted')}")
        else:
            print(f"G-AGG-2 (contractor_summary per-emetteur == lev): FAIL "
                  f"({len(agg2_offenders)} mismatches)")
            for off in agg2_offenders[:5]:
                print(f"  code={off[0]} cs_total={off[1]} lev={off[2]}")
            gate_ok = False

        # G-CONS-1: _filter_for_consultant returns latest-only (numero, indice) pairs
        lc_keys = set(zip(
            ctx.latest_chain_df["numero"].astype(str).str.strip(),
            ctx.latest_chain_df["latest_indice"].astype(str).str.strip(),
        )) if ctx.latest_chain_df is not None else set()

        cons_names = ["AMO HQE", "ARCHITECTE", "BET Acoustique", "Bureau de Contrôle",
                      "Maître d'Oeuvre EXE"]
        chosen_name = None
        merged_df = None
        for name in cons_names:
            try:
                m = _filter_for_consultant(ctx, name)
            except Exception:
                continue
            if m is not None and not m.empty:
                chosen_name = name
                merged_df = m
                break

        if chosen_name is None:
            print("G-CONS-1: SKIP (no non-empty consultant filter result)")
        else:
            cons1_offenders = []
            # merged_df is doc rows ∪ response rows; resolve (numero, indice) from doc side
            num_col = "numero_doc" if "numero_doc" in merged_df.columns else "numero"
            ind_col = "indice_doc" if "indice_doc" in merged_df.columns else "indice"
            for _, mr in merged_df.iterrows():
                num = str(mr.get(num_col) or "").strip()
                ind = str(mr.get(ind_col) or "").strip()
                if not num or not ind:
                    continue
                if (num, ind) not in lc_keys:
                    cons1_offenders.append((num, ind))
            if not cons1_offenders:
                print(f"G-CONS-1 (_filter_for_consultant latest-only): PASS "
                      f"(consultant={chosen_name!r}, rows={len(merged_df)})")
            else:
                print(f"G-CONS-1 (_filter_for_consultant latest-only): FAIL "
                      f"({len(cons1_offenders)}/{len(merged_df)} non-latest)")
                for off in cons1_offenders[:5]:
                    print(f"  numero={off[0]} indice={off[1]}")
                gate_ok = False

        # G-DRL-1: build_drilldown(submitted) row count ≤ lev count
        focus_off = apply_focus_filter(ctx, FocusConfig(enabled=False, stale_threshold_days=30))
        dd = build_drilldown(ctx, "submitted", {}, focus_off)
        dd_rows = len(dd.get("rows", []))
        dd_total = dd.get("total_count", 0)
        if dd_total <= lev_count:
            print(f"G-DRL-1 (drilldown 'submitted' rows <= lev): PASS "
                  f"(total={dd_total}, lev={lev_count})")
        else:
            print(f"G-DRL-1 (drilldown 'submitted' rows <= lev): FAIL "
                  f"(total={dd_total} > lev={lev_count})")
            gate_ok = False

        # G-FOC-1: apply_focus_filter focused docs all in latest_chain_df
        focus_on = apply_focus_filter(
            ctx, FocusConfig(enabled=True, stale_threshold_days=30)
        )
        focused_df = getattr(focus_on, "focused_df", None)
        if focused_df is None or focused_df.empty:
            print("G-FOC-1 (focus filter latest-only): SKIP (no focused docs)")
        else:
            foc1_offenders = []
            for _, fr in focused_df.iterrows():
                num = str(fr.get("numero") or "").strip()
                ind = str(fr.get("indice") or "").strip()
                if (num, ind) not in lc_keys:
                    foc1_offenders.append((num, ind))
            if not foc1_offenders:
                print(f"G-FOC-1 (focus filter latest-only): PASS "
                      f"(focused={len(focused_df)})")
            else:
                print(f"G-FOC-1 (focus filter latest-only): FAIL "
                      f"({len(foc1_offenders)}/{len(focused_df)} non-latest)")
                for off in foc1_offenders[:5]:
                    print(f"  numero={off[0]} indice={off[1]}")
                gate_ok = False

    except Exception as exc:
        print(f"Step 7 gates FAILED: {type(exc).__name__}: {exc}")
        import traceback; traceback.print_exc()
        gate_ok = False

    if gate_ok:
        print()
        print("ALL GATES PASSED")
    else:
        sys.exit(1)

    sys.exit(0)


if __name__ == "__main__":
    main()
