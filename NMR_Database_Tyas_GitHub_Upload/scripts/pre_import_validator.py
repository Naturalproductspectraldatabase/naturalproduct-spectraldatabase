#!/usr/bin/env python3
"""Validate NPDB batch-import files before Tyas uploads them.

This script is intentionally read-only: it never edits the reviewed Excel/CSV
files and never inserts anything into the database. It produces issue CSVs plus
a compact Markdown summary under `data/exports/validation_reports/`.
"""

from __future__ import annotations

import argparse
import csv
import importlib.util
import re
import sqlite3
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Callable

import pandas as pd


PROJECT_DIR = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = PROJECT_DIR / "scripts"
LOCAL_DB = PROJECT_DIR / "database" / "nmr.db"
DEFAULT_EXPORT_DIR = Path("/Users/triandatyas/Desktop/NMR_Database_Tyas/data/exports")
DEFAULT_REPORT_ROOT = PROJECT_DIR / "data" / "exports" / "validation_reports"


def load_app_module():
    sys.path.insert(0, str(SCRIPTS_DIR))
    spec = importlib.util.spec_from_file_location("npdb_streamlit_app_for_validation", SCRIPTS_DIR / "app.py")
    if spec is None or spec.loader is None:
        raise RuntimeError("Could not load app.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def read_table(path: Path) -> pd.DataFrame:
    if not path or not path.exists():
        return pd.DataFrame()
    if path.suffix.lower() in {".xlsx", ".xls"}:
        return pd.read_excel(path).fillna("")
    last_error: Exception | None = None
    for encoding in ("utf-8-sig", "utf-8", "cp1252", "latin1"):
        try:
            return pd.read_csv(path, encoding=encoding).fillna("")
        except UnicodeDecodeError as exc:
            last_error = exc
    if last_error:
        raise last_error
    return pd.read_csv(path).fillna("")


def maybe_blank(value) -> str:
    if value is None:
        return ""
    try:
        if pd.isna(value):
            return ""
    except Exception:
        pass
    return str(value).strip()


def safe_float(value):
    text = maybe_blank(value)
    if not text:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def compact_key(value: str) -> str:
    return re.sub(r"\s+", " ", maybe_blank(value)).casefold()


@dataclass
class ValidationContext:
    app: object
    existing_ids: set[int]
    existing_compound_keys: set[tuple[str, str, str]]
    existing_names: set[str]
    batch_compound_names: set[str]


def load_existing_context(app, compound_df: pd.DataFrame) -> ValidationContext:
    conn = sqlite3.connect(LOCAL_DB)
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute("SELECT id, trivial_name, sample_code, doi FROM compounds").fetchall()
    finally:
        conn.close()

    existing_ids = {int(row["id"]) for row in rows}
    existing_names = {compact_key(row["trivial_name"]) for row in rows if maybe_blank(row["trivial_name"])}
    existing_compound_keys = {
        (
            compact_key(row["trivial_name"]),
            compact_key(row["sample_code"]),
            compact_key(row["doi"]),
        )
        for row in rows
        if maybe_blank(row["trivial_name"])
    }
    batch_compound_names = set()
    if not compound_df.empty and "trivial_name" in compound_df.columns:
        batch_compound_names = {
            compact_key(value)
            for value in compound_df["trivial_name"].tolist()
            if maybe_blank(value) and not app.is_template_marker(value)
        }
    return ValidationContext(app, existing_ids, existing_compound_keys, existing_names, batch_compound_names)


def issue(row: int | str, severity: str, field: str, message: str, value: str = "") -> dict[str, str]:
    return {
        "spreadsheet_row": str(row),
        "severity": severity,
        "field": field,
        "message": message,
        "value": value,
    }


def validate_compounds(df: pd.DataFrame, ctx: ValidationContext) -> list[dict[str, str]]:
    app = ctx.app
    aligned = app.align_import_columns(df, app.COMPOUND_IMPORT_COLUMNS)
    issues: list[dict[str, str]] = []
    seen: dict[tuple[str, str, str], int] = {}
    for index, row in aligned.iterrows():
        row_no = int(index) + 2
        name = maybe_blank(row.get("trivial_name"))
        if not name or app.is_template_marker(name):
            continue
        key = (compact_key(name), compact_key(row.get("sample_code")), compact_key(row.get("doi")))
        if key in seen:
            issues.append(issue(row_no, "error", "trivial_name/sample_code/doi", f"Duplicate compound within this file; first seen on row {seen[key]}.", name))
        else:
            seen[key] = row_no
        if key in ctx.existing_compound_keys:
            issues.append(issue(row_no, "warning", "trivial_name/sample_code/doi", "Compound already exists in the current database; import will skip it as duplicate.", name))
        if maybe_blank(row.get("depth_m")) and safe_float(row.get("depth_m")) is None:
            issues.append(issue(row_no, "error", "depth_m", "Depth must be numeric.", maybe_blank(row.get("depth_m"))))
        if maybe_blank(row.get("molecular_weight")) and safe_float(row.get("molecular_weight")) is None:
            issues.append(issue(row_no, "error", "molecular_weight", "Molecular weight must be numeric.", maybe_blank(row.get("molecular_weight"))))
        if not any(maybe_blank(row.get(col)) for col in ("smiles", "inchi", "inchikey", "structure_image_path")):
            issues.append(issue(row_no, "warning", "structure", "No SMILES/InChI/InChIKey/structure image path. Structure search and preview may be incomplete.", name))
        if not any(maybe_blank(row.get(col)) for col in ("doi", "article_title", "journal_name")):
            issues.append(issue(row_no, "warning", "reference", "No DOI/article/journal reference fields.", name))
        if not any(maybe_blank(row.get(col)) for col in ("source_category", "source_organism", "source_material")):
            issues.append(issue(row_no, "warning", "source", "No source category/organism/material.", name))
    return issues


def compound_reference_exists(row, ctx: ValidationContext) -> bool:
    compound_id = maybe_blank(row.get("compound_id"))
    if compound_id:
        try:
            return int(float(compound_id)) in ctx.existing_ids
        except ValueError:
            return False
    name = compact_key(row.get("compound_name"))
    if not name:
        return False
    return name in ctx.existing_names or name in ctx.batch_compound_names


def validate_peak_table(df: pd.DataFrame, ctx: ValidationContext, kind: str) -> list[dict[str, str]]:
    app = ctx.app
    expected = app.PROTON_IMPORT_COLUMNS if kind == "1H" else app.CARBON_IMPORT_COLUMNS
    aligned = app.align_import_columns(df, expected)
    issues: list[dict[str, str]] = []
    seen: dict[tuple[str, str, str, str, str, str], int] = {}
    for index, row in aligned.iterrows():
        row_no = int(index) + 2
        name = maybe_blank(row.get("compound_name"))
        if app.is_template_marker(name):
            continue
        if not compound_reference_exists(row, ctx):
            issues.append(issue(row_no, "error", "compound_id/compound_name", "Compound could not be matched by ID or name in current DB/batch compound file.", name or maybe_blank(row.get("compound_id"))))
        delta = maybe_blank(row.get("delta_ppm"))
        if not delta:
            issues.append(issue(row_no, "error", "delta_ppm", "Chemical shift is required.", ""))
        elif safe_float(delta) is None:
            issues.append(issue(row_no, "error", "delta_ppm", "Chemical shift must be numeric.", delta))
        if not maybe_blank(row.get("assignment")):
            issues.append(issue(row_no, "error", "assignment", "Assignment is required.", ""))
        if maybe_blank(row.get("instrument_mhz")) and safe_float(row.get("instrument_mhz")) is None:
            issues.append(issue(row_no, "error", "instrument_mhz", "Instrument MHz must be numeric.", maybe_blank(row.get("instrument_mhz"))))
        key = (
            compact_key(row.get("compound_id")) or compact_key(name),
            str(round(safe_float(delta) or 0, 4)) if delta else "",
            compact_key(row.get("assignment")),
            compact_key(row.get("solvent")),
            compact_key(row.get("instrument_mhz")),
            compact_key(row.get("dataset_label")) or compact_key(row.get("reference")) or compact_key(row.get("note")),
        )
        if key in seen:
            issues.append(issue(row_no, "warning", "duplicate", f"Possible duplicate {kind} peak within this file; first seen on row {seen[key]}.", name))
        else:
            seen[key] = row_no
        if not any(maybe_blank(row.get(col)) for col in ("dataset_label", "reference", "note")):
            issues.append(issue(row_no, "warning", "reference", "No dataset/reference/note. This is allowed, but harder to curate when one compound has multiple papers.", name))
    return issues


def validate_spectra(df: pd.DataFrame, ctx: ValidationContext) -> list[dict[str, str]]:
    app = ctx.app
    aligned = app.align_import_columns(df, app.SPECTRA_IMPORT_COLUMNS)
    issues: list[dict[str, str]] = []
    seen: dict[tuple[str, str, str], int] = {}
    for index, row in aligned.iterrows():
        row_no = int(index) + 2
        name = maybe_blank(row.get("compound_name"))
        if app.is_template_marker(name):
            continue
        if not compound_reference_exists(row, ctx):
            issues.append(issue(row_no, "error", "compound_id/compound_name", "Compound could not be matched by ID or name in current DB/batch compound file.", name or maybe_blank(row.get("compound_id"))))
        file_path = maybe_blank(row.get("file_path"))
        if not file_path:
            issues.append(issue(row_no, "error", "file_path", "File path or URL is required.", ""))
        spectrum_type = maybe_blank(row.get("spectrum_type")) or app.infer_spectrum_type_from_name(file_path)
        key = (compact_key(row.get("compound_id")) or compact_key(name), compact_key(spectrum_type), compact_key(file_path))
        if key in seen:
            issues.append(issue(row_no, "warning", "duplicate", f"Possible duplicate spectra entry within this file; first seen on row {seen[key]}.", file_path))
        else:
            seen[key] = row_no
    return issues


def write_issues(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=["spreadsheet_row", "severity", "field", "message", "value"])
        writer.writeheader()
        writer.writerows(rows)


def markdown_summary(summary: list[dict[str, object]], report_dir: Path) -> str:
    lines = [
        "# NPDB Pre-Import Validation Report",
        "",
        f"- Generated: `{datetime.now().isoformat(timespec='seconds')}`",
        f"- Report folder: `{report_dir}`",
        "",
        "| File Type | Rows | Errors | Warnings | Issue CSV |",
        "| --- | ---: | ---: | ---: | --- |",
    ]
    for item in summary:
        lines.append(
            f"| {item['file_type']} | {item['rows']} | {item['errors']} | {item['warnings']} | `{item['issue_csv']}` |"
        )
    lines.extend(
        [
            "",
            "## How To Read This",
            "",
            "- `error`: likely import failure or wrong column/value.",
            "- `warning`: import may still work, but Tyas should review before upload.",
            "- The original Excel/CSV files were not modified.",
            "",
        ]
    )
    return "\n".join(lines)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate NPDB batch-import files without modifying them.")
    parser.add_argument("--compounds", type=Path, default=DEFAULT_EXPORT_DIR / "compounds_batch_import_template.csv")
    parser.add_argument("--proton", type=Path, default=DEFAULT_EXPORT_DIR / "proton_nmr_batch_import_template_20260515-2csv.xlsx")
    parser.add_argument("--carbon", type=Path, default=DEFAULT_EXPORT_DIR / "carbon_nmr_batch_import_template_20260515_2.xlsx")
    parser.add_argument("--spectra", type=Path, default=DEFAULT_EXPORT_DIR / "spectra_files_batch_import_template.csv")
    parser.add_argument("--report-root", type=Path, default=DEFAULT_REPORT_ROOT)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    report_dir = args.report_root / f"pre_import_validation_{timestamp}"
    report_dir.mkdir(parents=True, exist_ok=True)

    app = load_app_module()
    compound_df_raw = read_table(args.compounds)
    compound_df = app.normalize_import_dataframe(compound_df_raw) if not compound_df_raw.empty else pd.DataFrame()
    ctx = load_existing_context(app, app.align_import_columns(compound_df, app.COMPOUND_IMPORT_COLUMNS) if not compound_df.empty else pd.DataFrame())

    jobs: list[tuple[str, Path, pd.DataFrame, Callable[[pd.DataFrame, ValidationContext], list[dict[str, str]]]]] = [
        ("compounds", args.compounds, compound_df_raw, validate_compounds),
        ("proton_nmr", args.proton, read_table(args.proton), lambda df, context: validate_peak_table(df, context, "1H")),
        ("carbon_nmr", args.carbon, read_table(args.carbon), lambda df, context: validate_peak_table(df, context, "13C")),
    ]
    if args.spectra.exists():
        jobs.append(("spectra_files", args.spectra, read_table(args.spectra), validate_spectra))

    summary: list[dict[str, object]] = []
    exit_code = 0
    for file_type, source_path, frame, validator in jobs:
        issues = validator(frame, ctx) if not frame.empty else [issue("", "warning", "file", "File is empty or missing.", str(source_path))]
        issue_path = report_dir / f"{file_type}_validation_issues.csv"
        write_issues(issue_path, issues)
        errors = sum(1 for item in issues if item["severity"] == "error")
        warnings = sum(1 for item in issues if item["severity"] == "warning")
        if errors:
            exit_code = 1
        summary.append(
            {
                "file_type": file_type,
                "source_file": str(source_path),
                "rows": int(len(frame)),
                "errors": errors,
                "warnings": warnings,
                "issue_csv": str(issue_path),
            }
        )

    pd.DataFrame(summary).to_csv(report_dir / "validation_summary.csv", index=False)
    md_path = report_dir / "validation_summary.md"
    md_path.write_text(markdown_summary(summary, report_dir), encoding="utf-8")
    print(md_path)
    for item in summary:
        print(f"{item['file_type']}: rows={item['rows']} errors={item['errors']} warnings={item['warnings']}")
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
