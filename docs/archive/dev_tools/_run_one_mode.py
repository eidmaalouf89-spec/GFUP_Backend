"""Helper: run one pipeline mode for parity harness."""
import sys
import shutil
import time
from pathlib import Path

mode = sys.argv[1]  # "raw" or "flat"
run_id = sys.argv[2] if len(sys.argv) > 2 else str(int(time.time()))
project = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project))
sys.path.insert(0, str(project / "src"))

tag = "parity_" + mode + "_" + run_id
out_dir = project / "output" / tag
out_dir.mkdir(parents=True, exist_ok=True)
(out_dir / "debug").mkdir(exist_ok=True)

# Isolated DB — create fresh copies via sqlite3 backup API to avoid
# FUSE corruption from raw file copy
import sqlite3

data_dir = out_dir / "data"
data_dir.mkdir(exist_ok=True)
(out_dir / "runs").mkdir(exist_ok=True)

for db_name in ("run_memory.db", "report_memory.db"):
    src_path = str(project / "data" / db_name)
    dst_path = str(data_dir / db_name)
    src_conn = sqlite3.connect(src_path)
    dst_conn = sqlite3.connect(dst_path)
    src_conn.backup(dst_conn)
    src_conn.close()
    dst_conn.close()

# Ensure FLAT_GED.xlsx
flat_input = project / "input" / "FLAT_GED.xlsx"
if not flat_input.exists():
    builder = project.parent / "GED_FLAT_Builder"
    src = builder / "ged_flat_builder" / "output" / "batch_run" / "FLAT_GED.xlsx"
    shutil.copy2(src, flat_input)

import main as main_module

main_module.FLAT_GED_MODE = mode
main_module.OUTPUT_DIR = out_dir
main_module.DEBUG_DIR = out_dir / "debug"
main_module.OUTPUT_GF = out_dir / "GF_V0_CLEAN.xlsx"
main_module.RUN_MEMORY_DB = str(data_dir / "run_memory.db")
main_module.REPORT_MEMORY_DB = str(data_dir / "report_memory.db")

orig_output = project / "output"
for attr in dir(main_module):
    if attr.startswith("OUTPUT_") and attr not in ("OUTPUT_DIR", "OUTPUT_GF"):
        val = getattr(main_module, attr)
        if isinstance(val, Path):
            try:
                rel = val.relative_to(orig_output)
                setattr(main_module, attr, out_dir / rel)
            except ValueError:
                pass

main_module._ACTIVE_RUN_NUMBER = None
main_module._ACTIVE_RUN_FINALIZED = False
main_module._RUN_CONTROL_CONTEXT = None

start = time.time()
main_module.run_pipeline(verbose=True)
elapsed = time.time() - start

gf = out_dir / "GF_V0_CLEAN.xlsx"
if gf.exists():
    (out_dir / "_DONE").write_text(str(gf))
    msg = "SUCCESS in %.1fs" % elapsed
    print(msg)
    print(str(gf))
else:
    (out_dir / "_FAIL").write_text("GF not produced")
    msg = "FAIL in %.1fs" % elapsed
    print(msg)
# end of script
