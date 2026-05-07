"""
Source-level exclusions for the Flat GED batch builder.

These rules run before Raw GED rows are grouped into Flat GED documents.
They are intentionally narrow: only the Bentin positive-inclusion rule lives
here, because Bentin old rows are now a true source exclusion.
"""

from __future__ import annotations

import csv
import datetime as _dt
import io
import re
import unicodedata
from pathlib import Path


BENTIN_CUTOFF_DATE = _dt.date(2026, 3, 10)
BENTIN_EXCLUSION_CODE = "BENTIN_SOURCE_OLD_NOT_LISTED"
BENTIN_EXCLUSION_REASON = (
    "Bentin document before 2026-03-10 and not listed in remaining bentin.csv"
)
_BENTIN_CODES = {"BEN", "BENTIN"}
_SOURCE_MODULE = "flat_ged.source_exclusions"


def _label(value) -> str:
    text = "" if value is None else str(value)
    text = "".join(
        ch for ch in unicodedata.normalize("NFKD", text)
        if not unicodedata.combining(ch)
    )
    return re.sub(r"\s+", " ", text).strip().upper()


def _compact(value) -> str:
    if value is None:
        return ""
    text = str(value).strip()
    if text.endswith(".0"):
        try:
            text = str(int(float(text)))
        except Exception:
            pass
    return re.sub(r"\s+", "", text).upper()


def _numero_forms(value) -> set[str]:
    numero = _compact(value)
    if not numero:
        return set()
    return {numero, numero.lstrip("0") or "0"}


def _indice(value) -> str:
    return _compact(value)


def _parse_document_tail(document) -> str:
    text = "" if document is None else str(document).strip()
    if "_" not in text:
        return ""
    return _compact(text.rsplit("_", 1)[-1])


def _parse_date(value) -> _dt.date | None:
    if value is None:
        return None
    if isinstance(value, _dt.datetime):
        return value.date()
    if isinstance(value, _dt.date):
        return value
    text = str(value).strip()
    if not text:
        return None
    for fmt in ("%d/%m/%Y", "%d-%m-%Y", "%Y-%m-%d", "%Y-%m-%d %H:%M:%S"):
        try:
            parsed = _dt.datetime.strptime(text, fmt)
            return parsed.date()
        except ValueError:
            continue
    return None


def _get(row_data: list, columns: dict[str, int], logical_name: str):
    idx = columns.get(logical_name)
    if idx is None or idx >= len(row_data):
        return None
    return row_data[idx]


class BentinSourceExclusionPolicy:
    """Recomputed source policy for BEN/BENTIN rows in the current GED import."""

    def __init__(self, registry_path: Path):
        self.registry_path = Path(registry_path)
        self.registry_keys: dict[tuple[str, str], list[str]] = {}
        self.reference_rows = 0
        self.source_exclusions: list[dict[str, object]] = []
        self.summary = {
            "registry_path": str(self.registry_path),
            "cutoff_date": BENTIN_CUTOFF_DATE.isoformat(),
            "reference_rows": 0,
            "raw_ben_total": 0,
            "included_listed_remaining_bentin": 0,
            "included_new_after_2026_03_10": 0,
            "excluded_bentin_source_old_not_listed": 0,
            "unresolved_ben_rows": 0,
        }
        self._load_registry()

    @classmethod
    def from_output_dir(cls, output_dir: Path) -> "BentinSourceExclusionPolicy":
        start = Path(output_dir).resolve()
        candidates = [start, *start.parents]
        for root in candidates:
            registry = root / "context" / "source_exclusions" / "remaining bentin.csv"
            if registry.exists():
                return cls(registry)
        fallback_root = start.parents[1] if len(start.parents) > 1 else start.parent
        return cls(fallback_root / "context" / "source_exclusions" / "remaining bentin.csv")

    def _load_registry(self) -> None:
        if not self.registry_path.exists():
            raise FileNotFoundError(
                f"Bentin positive-inclusion registry not found: {self.registry_path}"
            )

        data = self.registry_path.read_bytes()
        try:
            text = data.decode("utf-8-sig")
        except UnicodeDecodeError:
            text = data.decode("cp1252")

        rows = list(csv.reader(io.StringIO(text), delimiter=";"))
        header_index = next(
            (i for i, row in enumerate(rows) if row and row[0] == "DOCUMENT"),
            None,
        )
        if header_index is None:
            raise ValueError(
                f"Cannot find DOCUMENT header in Bentin registry: {self.registry_path}"
            )

        header = rows[header_index]
        header_map = {name: i for i, name in enumerate(header) if name}
        required = ["DOCUMENT", "IND"]
        if not all(name in header_map for name in required) or len(header) <= 5:
            raise ValueError(f"Bentin registry has an unexpected header: {header}")

        n_doc_col = 5  # "N° Doc" in the validated registry export.
        for source_row, row in enumerate(rows[header_index + 1:], start=header_index + 2):
            document = row[header_map["DOCUMENT"]] if header_map["DOCUMENT"] < len(row) else ""
            if not str(document).strip():
                continue
            self.reference_rows += 1
            ref_id = str(source_row)
            ind = _indice(row[header_map["IND"]] if header_map["IND"] < len(row) else "")

            n_doc = row[n_doc_col] if n_doc_col < len(row) else ""
            for numero in _numero_forms(n_doc):
                self.registry_keys.setdefault((numero, ind), []).append(ref_id)

            tail = _parse_document_tail(document)
            for numero in _numero_forms(tail):
                self.registry_keys.setdefault((numero, ind), []).append(ref_id)

        self.summary["reference_rows"] = self.reference_rows

    def should_exclude(self, raw_row_id: int, row_data: list, base_cols: dict) -> bool:
        columns = {_label(name): idx for idx, name in base_cols.items()}
        emetteur = _get(row_data, columns, "EMETTEUR")
        if _label(emetteur) not in _BENTIN_CODES:
            return False

        self.summary["raw_ben_total"] += 1
        numero = _get(row_data, columns, "NUMERO")
        indice = _indice(_get(row_data, columns, "INDICE"))
        matched_refs = self._matched_reference_ids(numero, indice)

        if matched_refs:
            self.summary["included_listed_remaining_bentin"] += 1
            return False

        created_at = _parse_date(_get(row_data, columns, "CREE LE"))
        if created_at is not None and created_at >= BENTIN_CUTOFF_DATE:
            self.summary["included_new_after_2026_03_10"] += 1
            return False

        self.summary["excluded_bentin_source_old_not_listed"] += 1
        self.source_exclusions.append(
            {
                "exclusion_code": BENTIN_EXCLUSION_CODE,
                "exclusion_reason": BENTIN_EXCLUSION_REASON,
                "raw_row_id": raw_row_id,
                "source_sheet": "Doc. sous workflow, x versions",
                "NUMERO": numero,
                "INDICE": _get(row_data, columns, "INDICE"),
                "Créé le": _get(row_data, columns, "CREE LE"),
                "EMETTEUR": emetteur,
                "LOT": _get(row_data, columns, "LOT"),
                "Libellé du document": _get(row_data, columns, "LIBELLE DU DOCUMENT"),
                "matched_policy": "EXCLUDE_BENTIN_SOURCE_OLD_NOT_LISTED",
                "matched_reference_id": "",
                "source_module": _SOURCE_MODULE,
            }
        )
        return True

    def _matched_reference_ids(self, numero, indice: str) -> list[str]:
        matches: list[str] = []
        for candidate in _numero_forms(numero):
            matches.extend(self.registry_keys.get((candidate, indice), []))
        return sorted(set(matches), key=str)

    def write_ledger(self, output_dir: Path) -> Path:
        path = Path(output_dir) / "RAW_GED_SOURCE_EXCLUSIONS.csv"
        path.parent.mkdir(parents=True, exist_ok=True)
        fields = [
            "exclusion_code",
            "exclusion_reason",
            "raw_row_id",
            "source_sheet",
            "NUMERO",
            "INDICE",
            "Créé le",
            "EMETTEUR",
            "LOT",
            "Libellé du document",
            "matched_policy",
            "matched_reference_id",
            "source_module",
        ]
        with path.open("w", newline="", encoding="utf-8-sig") as fh:
            writer = csv.DictWriter(fh, fieldnames=fields, extrasaction="ignore")
            writer.writeheader()
            writer.writerows(self.source_exclusions)
        return path
