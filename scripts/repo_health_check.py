"""
repo_health_check.py — CLEAN BASE Repo Health Audit (Step 1)

Checks:
  - Python syntax errors (ast.parse)
  - Null bytes in .py files (binary corruption)
  - Truncated .py files (ends with colon, backslash, stray expression)
  - Truncated .md files (ends without punctuation)
  - Committed binary/data files (.xlsx, .csv, .db, .parquet)
  - Generated output artifacts committed to repo
  - __pycache__ / .pyc / node_modules / dist folders
  - Files > 500 KB
  - FLAT_GED.xlsx referenced as manual input/
  - bet_report_merger active call sites
  - consultant_gf_writer active import/call sites
  - GF_TEAM_VERSION chain references (preservation check)
  - Architecture smell: raw-only patterns in data_loader

Usage:
    python scripts/repo_health_check.py [--root PATH]

Exits with code 1 if any BLOCKER is found, 0 otherwise.
"""

import ast
import os
import re
import sys
import argparse
from pathlib import Path

IGNORE_DIRS = {".git", "node_modules", "__pycache__", ".venv", "venv", ".pytest_cache"}
SEVERITY_ORDER = {"BLOCKER": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3, "INFO": 4}


def _sev(label):
    return SEVERITY_ORDER.get(label, 99)


class Finding:
    def __init__(self, severity, fid, path, summary, detail=""):
        self.severity = severity
        self.fid = fid
        self.path = path
        self.summary = summary
        self.detail = detail


def walk(root: Path):
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in IGNORE_DIRS]
        for f in filenames:
            yield Path(dirpath) / f


def rel(path: Path, root: Path) -> str:
    try:
        return str(path.relative_to(root))
    except ValueError:
        return str(path)


# ---------------------------------------------------------------------------
# Check: Python syntax + null bytes
# ---------------------------------------------------------------------------

def check_python_syntax(root: Path) -> list:
    findings = []
    for p in walk(root):
        if p.suffix != ".py":
            continue
        try:
            src = p.read_text(encoding="utf-8", errors="replace")
        except Exception as e:
            findings.append(Finding("BLOCKER", "UNREADABLE", rel(p, root), f"Cannot read file: {e}"))
            continue
        if "\x00" in src:
            findings.append(Finding(
                "BLOCKER", "NULL_BYTES", rel(p, root),
                "File contains null bytes — binary corruption or bad write",
            ))
            continue
        try:
            ast.parse(src, filename=str(p))
        except SyntaxError as e:
            findings.append(Finding(
                "BLOCKER", "SYNTAX", rel(p, root),
                f"SyntaxError at line {e.lineno}: {e.msg}",
                detail=f"Context: {e.text!r}" if e.text else "",
            ))
    return findings


# ---------------------------------------------------------------------------
# Check: truncated files
# ---------------------------------------------------------------------------

def check_truncation(root: Path) -> list:
    findings = []
    for p in walk(root):
        if p.suffix not in (".py", ".md"):
            continue
        try:
            lines = p.read_text(encoding="utf-8", errors="replace").splitlines()
        except Exception:
            continue

        non_blank = [l for l in lines if l.strip()]
        if not non_blank:
            findings.append(Finding("LOW", "TRUNC", rel(p, root), "File is empty or whitespace-only"))
            continue

        last = non_blank[-1].rstrip()

        if p.suffix == ".py":
            if re.match(r'^["\'].*["\'\)]+\s*$', last) and not last.strip().startswith(("def ", "return ", "print(")):
                if last.count("(") < last.count(")"):
                    findings.append(Finding(
                        "BLOCKER", "TRUNC_STRAY", rel(p, root),
                        "Stray unmatched expression on last line — likely truncation artifact",
                        detail=f"Last line: {last!r}",
                    ))
                    continue
            if last.endswith(":") and not last.strip().startswith("#"):
                findings.append(Finding(
                    "MEDIUM", "TRUNC_COLON", rel(p, root),
                    "Last non-blank line ends with ':' — file may end mid-block",
                    detail=f"Last line: {last!r}",
                ))
            elif last.endswith("\\"):
                findings.append(Finding(
                    "MEDIUM", "TRUNC_BACKSLASH", rel(p, root),
                    "Last non-blank line ends with backslash continuation",
                    detail=f"Last line: {last!r}",
                ))

        if p.suffix == ".md":
            if re.search(r'[a-zA-Z0-9]$', last) and not last.startswith(("#", "-", "*", "|", ">", "```", "~")):
                findings.append(Finding(
                    "LOW", "TRUNC_MD", rel(p, root),
                    "Markdown file ends without terminal punctuation — possible truncation",
                    detail=f"Last line: {last!r}",
                ))

    return findings


# ---------------------------------------------------------------------------
# Check: committed data / large files
# ---------------------------------------------------------------------------

LARGE_THRESHOLD_BYTES = 500 * 1024
DATA_SUFFIXES = {".xlsx", ".csv", ".db", ".sqlite", ".parquet", ".pkl", ".pickle"}
GENERATED_DIRS = {"output", "outputs", "runs", "dist", "build"}


def check_committed_data(root: Path) -> list:
    findings = []
    for p in walk(root):
        try:
            size = p.stat().st_size
        except OSError:
            continue
        if size > LARGE_THRESHOLD_BYTES:
            findings.append(Finding(
                "MEDIUM", "LARGE_FILE", rel(p, root),
                f"File is {size // 1024} KB — large committed file",
            ))
        if p.suffix.lower() in DATA_SUFFIXES:
            findings.append(Finding(
                "MEDIUM", "COMMITTED_DATA", rel(p, root),
                f"Committed data file ({p.suffix})",
            ))
    for d in GENERATED_DIRS:
        candidate = root / d
        if candidate.is_dir():
            findings.append(Finding(
                "HIGH", "COMMITTED_OUTPUT_DIR", d + "/",
                f"Generated output folder '{d}/' is committed — should be gitignored",
            ))
    return findings


# ---------------------------------------------------------------------------
# Check: stale build artifacts
# ---------------------------------------------------------------------------

def check_build_artifacts(root: Path) -> list:
    findings = []
    for dirpath, dirnames, _ in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in IGNORE_DIRS]
        for d in dirnames:
            if d in {"__pycache__", "node_modules", ".vite", ".npm-cache"}:
                findings.append(Finding(
                    "LOW", "BUILD_ARTIFACT",
                    rel(Path(dirpath) / d, root),
                    f"Build/cache folder '{d}' committed — should be gitignored",
                ))
    for p in walk(root):
        if p.suffix in {".pyc", ".pyo"}:
            findings.append(Finding(
                "LOW", "COMPILED_PY", rel(p, root),
                "Compiled Python file committed — should be gitignored",
            ))
    return findings


# ---------------------------------------------------------------------------
# Check: architecture smells (grep-based)
# ---------------------------------------------------------------------------

def _grep(root: Path, pattern: str, include_suffixes=(".py", ".md")) -> list:
    rx = re.compile(pattern)
    results = []
    for p in walk(root):
        if p.suffix not in include_suffixes:
            continue
        try:
            lines = p.read_text(encoding="utf-8", errors="replace").splitlines()
        except Exception:
            continue
        for i, line in enumerate(lines, 1):
            if rx.search(line):
                results.append((rel(p, root), i, line.strip()))
    return results


def check_flat_ged_manual_input(root: Path) -> list:
    findings = []
    hits = _grep(root, r'input[/\\].*FLAT_GED\.xlsx|FLAT_GED_FILE\s*=.*INPUT_DIR')
    for path, lineno, line in hits:
        if path.startswith("docs/") or path.startswith("FLAT_GED_INTEGRATION"):
            findings.append(Finding(
                "INFO", "FLAT_GED_DOC_REF", f"{path}:{lineno}",
                "Doc references manual FLAT_GED input path (stale, superseded by Step 7)",
                detail=line,
            ))
        else:
            findings.append(Finding(
                "HIGH", "FLAT_GED_INPUT_REF", f"{path}:{lineno}",
                "Code references FLAT_GED.xlsx in input/ — manual placement contract still active",
                detail=line,
            ))
    return findings


def check_bet_report_merger(root: Path) -> list:
    findings = []
    hits = _grep(root, r'bet_report_merger|merge_bet_reports')
    for path, lineno, line in hits:
        if "bet_report_merger.py" in path:
            continue
        if line.strip().startswith("#"):
            findings.append(Finding(
                "INFO", "BRM_COMMENTED", f"{path}:{lineno}",
                "bet_report_merger reference in comment (expected — DO NOT RESTORE guard)",
                detail=line,
            ))
        elif path.startswith("docs/"):
            findings.append(Finding(
                "INFO", "BRM_DOC", f"{path}:{lineno}",
                "bet_report_merger reference in docs (historical)",
                detail=line,
            ))
        else:
            findings.append(Finding(
                "HIGH", "BRM_ACTIVE", f"{path}:{lineno}",
                "ACTIVE reference to retired bet_report_merger — must not be called",
                detail=line,
            ))
    brm_file = root / "src" / "reporting" / "bet_report_merger.py"
    if brm_file.exists():
        findings.append(Finding(
            "MEDIUM", "BRM_FILE_EXISTS",
            "src/reporting/bet_report_merger.py",
            "Retired file still present in active source tree — Step 13 candidate",
        ))
    return findings


def check_consultant_gf_writer(root: Path) -> list:
    findings = []
    hits = _grep(root, r'from consultant_gf_writer import|import consultant_gf_writer|write_gf_enriched')
    for path, lineno, line in hits:
        if "consultant_gf_writer.py" in path:
            continue
        if line.strip().startswith("#"):
            findings.append(Finding(
                "INFO", "CGW_COMMENTED", f"{path}:{lineno}",
                "consultant_gf_writer reference in comment",
                detail=line,
            ))
        elif path.startswith("docs/"):
            continue
        else:
            findings.append(Finding(
                "MEDIUM", "CGW_ACTIVE_IMPORT", f"{path}:{lineno}",
                "Live import of deprecated consultant_gf_writer — risk of accidental invocation",
                detail=line,
            ))
    return findings


def check_gf_team_version(root: Path) -> list:
    findings = []
    required_hits = {
        "paths.py":              r'OUTPUT_GF_TEAM_VERSION',
        "stage_finalize_run.py": r'GF_TEAM_VERSION',
        "app.py":                r'export_team_version',
        "team_version_builder.py": r'build_team_version',
        "runner.py":             r'OUTPUT_GF_TEAM_VERSION',
    }
    for filename, pattern in required_hits.items():
        hits = _grep(root, pattern)
        matching = [h for h in hits if filename in h[0]]
        if matching:
            findings.append(Finding(
                "INFO", "TEAM_VER_OK", filename,
                f"GF_TEAM_VERSION chain confirmed: '{pattern}' present",
            ))
        else:
            findings.append(Finding(
                "HIGH", "TEAM_VER_MISSING", filename,
                f"GF_TEAM_VERSION chain break — '{pattern}' NOT found in {filename}",
            ))
    return findings


def check_raw_only_in_data_loader(root: Path) -> list:
    findings = []
    dl = root / "src" / "reporting" / "data_loader.py"
    if not dl.exists():
        return findings
    try:
        lines = dl.read_text(encoding="utf-8", errors="replace").splitlines()
    except Exception:
        return findings
    raw_patterns = [r'read_ged\(', r'normalize_docs\(', r'normalize_responses\(', r'VersionEngine\(']
    for i, line in enumerate(lines, 1):
        for pat in raw_patterns:
            if re.search(pat, line) and not line.strip().startswith("#"):
                findings.append(Finding(
                    "MEDIUM", "RAW_REBUILD_IN_LOADER",
                    f"src/reporting/data_loader.py:{i}",
                    f"data_loader still calls raw-rebuild function '{pat.strip('()')}' — Step 12 target",
                    detail=line.strip(),
                ))
    return findings


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def run_audit(root: Path) -> list:
    all_findings = []
    print(f"Auditing: {root}\n")
    checks = [
        ("Python syntax + null bytes",       check_python_syntax),
        ("Truncation detection",              check_truncation),
        ("Committed data / large files",      check_committed_data),
        ("Build artifacts",                   check_build_artifacts),
        ("FLAT_GED manual input refs",        check_flat_ged_manual_input),
        ("bet_report_merger status",          check_bet_report_merger),
        ("consultant_gf_writer status",       check_consultant_gf_writer),
        ("GF_TEAM_VERSION chain",             check_gf_team_version),
        ("Raw-only rebuild in data_loader",   check_raw_only_in_data_loader),
    ]
    for name, fn in checks:
        results = fn(root)
        all_findings.extend(results)
        sev_counts = {}
        for f in results:
            sev_counts[f.severity] = sev_counts.get(f.severity, 0) + 1
        summary = ", ".join(
            f"{k}:{v}" for k, v in sorted(sev_counts.items(), key=lambda x: _sev(x[0]))
        )
        print(f"  [{name}] → {summary or 'clean'}")
    return all_findings


def print_report(findings: list, root: Path) -> int:
    print()
    print("=" * 70)
    print("REPO HEALTH AUDIT — FINDINGS")
    print("=" * 70)

    by_sev = {}
    for f in findings:
        by_sev.setdefault(f.severity, []).append(f)

    total_files = sum(1 for _ in walk(root))

    for sev in ["BLOCKER", "HIGH", "MEDIUM", "LOW", "INFO"]:
        group = by_sev.get(sev, [])
        if not group:
            continue
        print(f"\n── {sev} ({len(group)}) {'─' * (60 - len(sev))}")
        for f in group:
            print(f"  [{f.fid}] {f.path}")
            print(f"    {f.summary}")
            if f.detail:
                print(f"    └─ {f.detail}")

    print()
    print("=" * 70)
    print("SUMMARY")
    print("=" * 70)
    print(f"  Files inspected (excl .git): {total_files}")
    for sev in ["BLOCKER", "HIGH", "MEDIUM", "LOW", "INFO"]:
        count = len(by_sev.get(sev, []))
        marker = " ◄" if sev == "BLOCKER" and count > 0 else ""
        print(f"  {sev:<10} {count}{marker}")
    print()

    blockers = by_sev.get("BLOCKER", [])
    if blockers:
        print("BLOCKERS FOUND — resolve before proceeding:")
        for f in blockers:
            print(f"  • [{f.fid}] {f.path}: {f.summary}")
        return 1
    else:
        print("No blockers found. Repo is clear to proceed.")
        return 0


def main():
    parser = argparse.ArgumentParser(description="GFUP Repo Health Check")
    parser.add_argument(
        "--root",
        default=str(Path(__file__).parent.parent),
        help="Repo root directory (default: parent of scripts/)",
    )
    args = parser.parse_args()
    root = Path(args.root).resolve()
    findings = run_audit(root)
    exit_code = print_report(findings, root)
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
