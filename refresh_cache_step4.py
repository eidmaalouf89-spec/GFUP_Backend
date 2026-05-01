import sys, time, json, logging
from pathlib import Path

sys.path.insert(0, "src")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

from reporting.data_loader import load_run_context, clear_cache, CACHE_SCHEMA_VERSION

base = Path(".").resolve()
print("BASE:", base)
print("CACHE_SCHEMA_VERSION in code:", CACHE_SCHEMA_VERSION, flush=True)

clear_cache()

t0 = time.time()
ctx = load_run_context(base, run_number=0)
dt = time.time() - t0

print(f"load_run_context finished in {dt:.1f}s", flush=True)
print("docs_df rows:", ctx.docs_df.shape[0], flush=True)
print("responses_df rows:", ctx.responses_df.shape[0], flush=True)

meta_path = Path("output/intermediate/FLAT_GED_cache_meta.json")
meta = json.loads(meta_path.read_text(encoding="utf-8"))

print("cache_schema_version on disk:", meta.get("cache_schema_version"), flush=True)
print("docs_df_rows:", meta.get("docs_df_rows"), "ctx:", ctx.docs_df.shape[0], flush=True)
print("responses_df_rows:", meta.get("responses_df_rows"), "ctx:", ctx.responses_df.shape[0], flush=True)
print("active_version_count:", meta.get("active_version_count"), flush=True)
print("family_count:", meta.get("family_count"), flush=True)
print("status_counts:", meta.get("status_counts"), flush=True)
print("generated_at:", meta.get("generated_at"), flush=True)
