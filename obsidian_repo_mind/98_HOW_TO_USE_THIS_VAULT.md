#repo-map #vault-guide

# How to Use This Vault

---

## Opening the vault

1. Open **Obsidian**.
2. Click **Open folder as vault**.
3. Select the `obsidian_repo_mind/` folder inside this repo.
4. Obsidian will load the vault. Start from [[00_START_HERE]].

---

## Navigation

- **Start:** [[00_START_HERE]] is the central index — it links to every note.
- **Wiki links:** Click any `[[note name]]` to jump to that note.
- **Back navigation:** Every note has a *Back to [[00_START_HERE]]* footer.
- **Related links:** Notes with thematic neighbours list them under **Related:**.
- **Graph View:** Press `Ctrl+G` (or use the left ribbon) to see the link map.
- **Quick switcher:** Press `Ctrl+O` to open any note by name.
- **Search:** Press `Ctrl+Shift+F` to full-text search across all notes.

---

## What this vault is and isn't

| This vault is… | This vault is NOT… |
|---|---|
| A navigation aid and mental model | Source of truth for data or business rules |
| Derived from actual repo files | Authoritative for code behaviour |
| Useful for orientation and debugging | A replacement for README, context/, or docs/ |

**Authoritative sources** (always defer to these):
- `README.md` — project overview and implementation status
- `context/00–12` — guardrails, open items, hazards, data flow
- `docs/ARCHITECTURE.md` — architecture decisions
- `src/`, `ui/`, `app.py`, `main.py` — actual code
- `data/run_memory.db`, `data/report_memory.db` — persistent state

---

## Note numbering guide

| Range | Theme |
|---|---|
| 00 | Index (this vault's entry point) |
| 01–06 | Architecture and runtime |
| 07–09 | Intelligence layers (Chain+Onion, DCC, Action MOEX) |
| 10–13 | Persistence, debugging, safety |
| 14–16 | Reference indexes and open items |
| 98–99 | Meta and graphs |

---

*Back to [[00_START_HERE]]*
