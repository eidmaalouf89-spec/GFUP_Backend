from pathlib import Path
import json, pickle, hashlib
from datetime import datetime, timezone

flat = Path("output/intermediate/FLAT_GED.xlsx")
docs_p = Path("output/intermediate/FLAT_GED_cache_docs.pkl")
resp_p = Path("output/intermediate/FLAT_GED_cache_resp.pkl")
meta_p = Path("output/intermediate/FLAT_GED_cache_meta.json")

for p in [flat, docs_p, resp_p, meta_p]:
    print(p, "exists=", p.exists(), "mtime=", p.stat().st_mtime if p.exists() else None)

if not docs_p.exists() or not resp_p.exists() or not meta_p.exists():
    raise SystemExit("STOP: cache pickle files missing")

if docs_p.stat().st_mtime <= flat.stat().st_mtime or resp_p.stat().st_mtime <= flat.stat().st_mtime:
    raise SystemExit("STOP: pickle cache is older than FLAT_GED.xlsx; cannot safely refresh meta only")

def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()

with open(docs_p, "rb") as f:
    docs_df = pickle.load(f)

with open(resp_p, "rb") as f:
    responses_df = pickle.load(f)

old = json.loads(meta_p.read_text(encoding="utf-8"))

new = {
    "cache_schema_version": "v2",
    "approver_names": old.get("approver_names", []),
    "flat_doc_meta": old.get("flat_doc_meta", {}),
    "source_flat_ged_sha256": sha256(flat),
    "source_flat_ged_mtime": flat.stat().st_mtime,
    "docs_df_rows": int(len(docs_df)),
    "responses_df_rows": int(len(responses_df)),
    "active_version_count": int(docs_df["doc_id"].nunique()) if "doc_id" in docs_df.columns else None,
    "family_count": int(docs_df["numero"].nunique()) if "numero" in docs_df.columns else None,
    "status_counts": (
        {str(k): int(v) for k, v in responses_df["status_clean"].value_counts().items()}
        if "status_clean" in responses_df.columns else {}
    ),
    "generated_at": datetime.now(timezone.utc).isoformat(),
}

meta_p.write_text(json.dumps(new, ensure_ascii=False, default=str), encoding="utf-8")

print("DONE")
print("cache_schema_version:", new["cache_schema_version"])
print("docs_df_rows:", new["docs_df_rows"])
print("responses_df_rows:", new["responses_df_rows"])
print("active_version_count:", new["active_version_count"])
print("family_count:", new["family_count"])
print("status_counts:", new["status_counts"])
print("generated_at:", new["generated_at"])
