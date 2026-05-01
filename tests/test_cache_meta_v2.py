import json
from pathlib import Path


def test_cache_meta_v2_keys_present():
    meta = json.loads(Path("output/intermediate/FLAT_GED_cache_meta.json").read_text(encoding="utf-8"))
    required = {
        "cache_schema_version", "approver_names", "flat_doc_meta",
        "source_flat_ged_sha256", "source_flat_ged_mtime",
        "docs_df_rows", "responses_df_rows",
        "active_version_count", "family_count",
        "status_counts", "generated_at",
    }
    missing = required - set(meta)
    assert not missing, f"missing keys: {missing}"


def test_cache_schema_version_is_v2():
    meta = json.loads(Path("output/intermediate/FLAT_GED_cache_meta.json").read_text(encoding="utf-8"))
    assert meta["cache_schema_version"] == "v2"


def test_cache_meta_audit_field_types():
    meta = json.loads(Path("output/intermediate/FLAT_GED_cache_meta.json").read_text(encoding="utf-8"))
    assert isinstance(meta["docs_df_rows"], int) and meta["docs_df_rows"] > 0
    assert isinstance(meta["responses_df_rows"], int) and meta["responses_df_rows"] > 0
    assert isinstance(meta["active_version_count"], int) or meta["active_version_count"] is None
    assert isinstance(meta["family_count"], int) or meta["family_count"] is None
    assert isinstance(meta["status_counts"], dict)
    assert isinstance(meta["generated_at"], str) and meta["generated_at"].endswith(("Z", "+00:00"))
    assert isinstance(meta["source_flat_ged_sha256"], str) and len(meta["source_flat_ged_sha256"]) == 64
