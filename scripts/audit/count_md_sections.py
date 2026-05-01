"""Per-section word count for the knowledge MD."""
import re

text = open(r"docs/RAW_TO_FLAT_GED_KNOWLEDGE.md", "r", encoding="utf-8").read()
parts = re.split(r"^(## .+)$", text, flags=re.MULTILINE)
# parts[0] = preamble; then alternating (header, body)
print(f"Preamble words: {len(parts[0].split())}")
for i in range(1, len(parts), 2):
    header = parts[i].strip()
    body = parts[i+1] if i+1 < len(parts) else ""
    print(f"{header}  -> {len(body.split())} words")
