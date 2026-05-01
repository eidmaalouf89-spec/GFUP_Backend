"""Inspect report_memory.db distributions for Step 2 design."""
import sqlite3
con = sqlite3.connect("file:data/report_memory.db?mode=ro", uri=True)
print("match_method distribution:")
for r in con.execute("SELECT match_method, COUNT(*) FROM persisted_report_responses GROUP BY match_method ORDER BY 2 DESC"):
    print(f"  {r}")
print()
print("match_confidence histogram:")
sql = (
    "SELECT CASE "
    "WHEN match_confidence >= 0.95 THEN 'HIGH' "
    "WHEN match_confidence >= 0.75 THEN 'MEDIUM' "
    "WHEN match_confidence IS NULL THEN 'UNKNOWN' "
    "ELSE 'LOW' END AS bucket, COUNT(*) "
    "FROM persisted_report_responses GROUP BY bucket"
)
for r in con.execute(sql):
    print(f"  {r}")
print()
print("consultant top-10:")
for r in con.execute("SELECT consultant, COUNT(*) FROM persisted_report_responses GROUP BY consultant ORDER BY 2 DESC LIMIT 10"):
    print(f"  {r}")
print()
print("doc_id sample (first 5):")
for r in con.execute("SELECT doc_id FROM persisted_report_responses LIMIT 5"):
    print(f"  {r}")
con.close()
