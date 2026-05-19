from __future__ import annotations

import argparse
import json
import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urlparse


PROJECT_DIR = Path(__file__).resolve().parents[1]
DEFAULT_DB_PATH = PROJECT_DIR / "database" / "nmr.db"
DEFAULT_EXPORT_DIR = PROJECT_DIR / "data" / "exports"
DEFAULT_JSON_PATH = DEFAULT_EXPORT_DIR / "data_integrity_audit.json"
DEFAULT_MD_PATH = DEFAULT_EXPORT_DIR / "data_integrity_audit.md"


def is_external_or_storage_path(value: str) -> bool:
    text = str(value or "").strip()
    if not text:
        return False
    parsed = urlparse(text)
    if parsed.scheme in {"http", "https"}:
        return True
    return text.startswith("supabase://") or text.startswith("storage://")


def project_file_exists(value: str) -> bool:
    text = str(value or "").strip()
    if not text or is_external_or_storage_path(text):
        return True
    path = Path(text)
    if path.is_absolute():
        return path.exists()
    return (PROJECT_DIR / path).exists()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run a reusable NPDB data integrity audit and write a JSON/Markdown report."
    )
    parser.add_argument("--db", type=Path, default=DEFAULT_DB_PATH, help="Path to the SQLite database.")
    parser.add_argument(
        "--json-output",
        type=Path,
        default=DEFAULT_JSON_PATH,
        help="Path to the JSON audit report.",
    )
    parser.add_argument(
        "--md-output",
        type=Path,
        default=DEFAULT_MD_PATH,
        help="Path to the Markdown audit report.",
    )
    return parser.parse_args()


def fetch_scalar(cursor: sqlite3.Cursor, query: str) -> int:
    return int(cursor.execute(query).fetchone()[0])


def fetch_rows(cursor: sqlite3.Cursor, query: str, limit: int = 10) -> list[dict]:
    rows = cursor.execute(query).fetchmany(limit)
    columns = [item[0] for item in cursor.description] if cursor.description else []
    return [dict(zip(columns, row)) for row in rows]


def build_report(db_path: Path) -> dict:
    if not db_path.exists():
        raise SystemExit(f"Database not found: {db_path}")

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        cur = conn.cursor()
        generated_at = datetime.now(UTC).isoformat()

        counts = {
            "compounds": fetch_scalar(cur, "SELECT COUNT(*) FROM compounds"),
            "proton_nmr": fetch_scalar(cur, "SELECT COUNT(*) FROM proton_nmr"),
            "carbon_nmr": fetch_scalar(cur, "SELECT COUNT(*) FROM carbon_nmr"),
            "spectra_files": fetch_scalar(cur, "SELECT COUNT(*) FROM spectra_files"),
            "bioactivity_records": fetch_scalar(cur, "SELECT COUNT(*) FROM bioactivity_records"),
        }

        quality = {
            "missing_trivial_name": fetch_scalar(
                cur, "SELECT COUNT(*) FROM compounds WHERE COALESCE(TRIM(trivial_name), '') = ''"
            ),
            "missing_any_structure_identifier": fetch_scalar(
                cur,
                """
                SELECT COUNT(*)
                FROM compounds
                WHERE COALESCE(TRIM(smiles), '') = ''
                  AND COALESCE(TRIM(inchikey), '') = ''
                  AND COALESCE(TRIM(inchi), '') = ''
                """,
            ),
            "missing_all_structure_assets": fetch_scalar(
                cur,
                """
                SELECT COUNT(*)
                FROM compounds
                WHERE COALESCE(TRIM(smiles), '') = ''
                  AND COALESCE(TRIM(inchikey), '') = ''
                  AND COALESCE(TRIM(inchi), '') = ''
                  AND COALESCE(TRIM(structure_image_path), '') = ''
                """,
            ),
            "missing_reference": fetch_scalar(
                cur,
                """
                SELECT COUNT(*)
                FROM compounds
                WHERE COALESCE(TRIM(article_title), '') = ''
                  AND COALESCE(TRIM(doi), '') = ''
                  AND COALESCE(TRIM(journal_name), '') = ''
                """,
            ),
            "missing_source": fetch_scalar(
                cur,
                """
                SELECT COUNT(*)
                FROM compounds
                WHERE COALESCE(TRIM(source_organism), '') = ''
                  AND COALESCE(TRIM(source_category), '') = ''
                """,
            ),
        }

        relationships = {
            "orphan_proton": fetch_scalar(
                cur,
                """
                SELECT COUNT(*)
                FROM proton_nmr p
                LEFT JOIN compounds c ON c.id = p.compound_id
                WHERE c.id IS NULL
                """,
            ),
            "orphan_carbon": fetch_scalar(
                cur,
                """
                SELECT COUNT(*)
                FROM carbon_nmr c
                LEFT JOIN compounds cp ON cp.id = c.compound_id
                WHERE cp.id IS NULL
                """,
            ),
            "orphan_spectra": fetch_scalar(
                cur,
                """
                SELECT COUNT(*)
                FROM spectra_files s
                LEFT JOIN compounds c ON c.id = s.compound_id
                WHERE c.id IS NULL
                """,
            ),
            "orphan_bioactivity": fetch_scalar(
                cur,
                """
                SELECT COUNT(*)
                FROM bioactivity_records b
                LEFT JOIN compounds c ON c.id = b.compound_id
                WHERE c.id IS NULL
                """,
            ),
        }

        duplicates = {
            "duplicate_inchikey_groups": fetch_scalar(
                cur,
                """
                SELECT COUNT(*)
                FROM (
                    SELECT LOWER(TRIM(inchikey))
                    FROM compounds
                    WHERE COALESCE(TRIM(inchikey), '') <> ''
                    GROUP BY LOWER(TRIM(inchikey))
                    HAVING COUNT(*) > 1
                )
                """,
            ),
            "duplicate_proton_peak_groups": fetch_scalar(
                cur,
                """
                SELECT COUNT(*)
                FROM (
                    SELECT compound_id,
                           ROUND(CAST(delta_ppm AS REAL), 4) AS delta_key,
                           LOWER(TRIM(COALESCE(assignment, ''))) AS assignment_key,
                           LOWER(TRIM(COALESCE(solvent, ''))) AS solvent_key,
                           LOWER(TRIM(COALESCE(note, ''))) AS note_key
                    FROM proton_nmr
                    WHERE delta_ppm IS NOT NULL
                      AND COALESCE(TRIM(assignment), '') <> ''
                    GROUP BY compound_id, delta_key, assignment_key, solvent_key, note_key
                    HAVING COUNT(*) > 1
                )
                """,
            ),
            "duplicate_carbon_peak_groups": fetch_scalar(
                cur,
                """
                SELECT COUNT(*)
                FROM (
                    SELECT compound_id,
                           ROUND(CAST(delta_ppm AS REAL), 4) AS delta_key,
                           LOWER(TRIM(COALESCE(assignment, ''))) AS assignment_key,
                           LOWER(TRIM(COALESCE(solvent, ''))) AS solvent_key,
                           LOWER(TRIM(COALESCE(note, ''))) AS note_key
                    FROM carbon_nmr
                    WHERE delta_ppm IS NOT NULL
                      AND COALESCE(TRIM(assignment), '') <> ''
                    GROUP BY compound_id, delta_key, assignment_key, solvent_key, note_key
                    HAVING COUNT(*) > 1
                )
                """,
            ),
        }

        coverage = {
            "compounds_without_1h": fetch_scalar(
                cur,
                """
                SELECT COUNT(*)
                FROM compounds c
                LEFT JOIN proton_nmr p ON p.compound_id = c.id
                WHERE p.id IS NULL
                """,
            ),
            "compounds_without_13c": fetch_scalar(
                cur,
                """
                SELECT COUNT(*)
                FROM compounds c
                LEFT JOIN carbon_nmr cn ON cn.compound_id = c.id
                WHERE cn.id IS NULL
                """,
            ),
            "compounds_without_spectra_file_records": fetch_scalar(
                cur,
                """
                SELECT COUNT(*)
                FROM compounds c
                LEFT JOIN spectra_files s ON s.compound_id = c.id
                WHERE s.id IS NULL
                """,
            ),
            "compounds_without_bioactivity_records": fetch_scalar(
                cur,
                """
                SELECT COUNT(*)
                FROM compounds c
                LEFT JOIN bioactivity_records b ON b.compound_id = c.id
                WHERE b.id IS NULL
                """,
            ),
        }

        structure_asset_rows = fetch_rows(
            cur,
            """
            SELECT id, trivial_name, structure_image_path
            FROM compounds
            WHERE COALESCE(TRIM(structure_image_path), '') <> ''
            ORDER BY id ASC
            """,
            limit=100000,
        )
        spectra_asset_rows = fetch_rows(
            cur,
            """
            SELECT s.id, s.compound_id, c.trivial_name, s.spectrum_type, s.file_path
            FROM spectra_files s
            LEFT JOIN compounds c ON c.id = s.compound_id
            WHERE COALESCE(TRIM(s.file_path), '') <> ''
            ORDER BY s.id ASC
            """,
            limit=100000,
        )

        structure_local_missing = [
            row for row in structure_asset_rows if not is_external_or_storage_path(row["structure_image_path"])
            and not project_file_exists(row["structure_image_path"])
        ]
        spectra_local_missing = [
            row for row in spectra_asset_rows if not is_external_or_storage_path(row["file_path"])
            and not project_file_exists(row["file_path"])
        ]
        asset_quality = {
            "structure_refs_total": len(structure_asset_rows),
            "structure_storage_or_url_refs": sum(
                1 for row in structure_asset_rows if is_external_or_storage_path(row["structure_image_path"])
            ),
            "structure_local_missing": len(structure_local_missing),
            "spectra_refs_total": len(spectra_asset_rows),
            "spectra_storage_or_url_refs": sum(
                1 for row in spectra_asset_rows if is_external_or_storage_path(row["file_path"])
            ),
            "spectra_local_missing": len(spectra_local_missing),
        }

        curation_status = {
            row["curation_status"] or "unknown": int(row["count"])
            for row in cur.execute(
                """
                SELECT COALESCE(NULLIF(TRIM(curation_status), ''), 'unknown') AS curation_status,
                       COUNT(*) AS count
                FROM compounds
                GROUP BY 1
                ORDER BY count DESC, curation_status ASC
                """
            ).fetchall()
        }

        samples = {
            "missing_structure_identifier": fetch_rows(
                cur,
                """
                SELECT id, trivial_name, data_source, source_organism, doi
                FROM compounds
                WHERE COALESCE(TRIM(smiles), '') = ''
                  AND COALESCE(TRIM(inchikey), '') = ''
                  AND COALESCE(TRIM(inchi), '') = ''
                ORDER BY updated_at DESC, id DESC
                """,
            ),
            "missing_reference": fetch_rows(
                cur,
                """
                SELECT id, trivial_name, data_source, source_organism, curation_status
                FROM compounds
                WHERE COALESCE(TRIM(article_title), '') = ''
                  AND COALESCE(TRIM(doi), '') = ''
                  AND COALESCE(TRIM(journal_name), '') = ''
                ORDER BY id DESC
                """,
            ),
            "missing_source": fetch_rows(
                cur,
                """
                SELECT id, trivial_name, data_source, molecular_formula, curation_status
                FROM compounds
                WHERE COALESCE(TRIM(source_organism), '') = ''
                  AND COALESCE(TRIM(source_category), '') = ''
                ORDER BY id DESC
                """,
            ),
            "duplicate_inchikey_groups": fetch_rows(
                cur,
                """
                SELECT LOWER(TRIM(inchikey)) AS inchikey,
                       COUNT(*) AS duplicate_count,
                       GROUP_CONCAT(id) AS compound_ids
                FROM compounds
                WHERE COALESCE(TRIM(inchikey), '') <> ''
                GROUP BY LOWER(TRIM(inchikey))
                HAVING COUNT(*) > 1
                ORDER BY duplicate_count DESC, inchikey ASC
                """,
            ),
            "duplicate_proton_peak_groups": fetch_rows(
                cur,
                """
                SELECT compound_id,
                       ROUND(CAST(delta_ppm AS REAL), 4) AS delta_ppm,
                       COALESCE(assignment, '') AS assignment,
                       COALESCE(solvent, '') AS solvent,
                       COALESCE(note, '') AS note,
                       COUNT(*) AS duplicate_count
                FROM proton_nmr
                WHERE delta_ppm IS NOT NULL
                  AND COALESCE(TRIM(assignment), '') <> ''
                GROUP BY compound_id,
                         ROUND(CAST(delta_ppm AS REAL), 4),
                         LOWER(TRIM(COALESCE(assignment, ''))),
                         LOWER(TRIM(COALESCE(solvent, ''))),
                         LOWER(TRIM(COALESCE(note, '')))
                HAVING COUNT(*) > 1
                ORDER BY duplicate_count DESC, compound_id ASC
                """,
            ),
            "duplicate_carbon_peak_groups": fetch_rows(
                cur,
                """
                SELECT compound_id,
                       ROUND(CAST(delta_ppm AS REAL), 4) AS delta_ppm,
                       COALESCE(assignment, '') AS assignment,
                       COALESCE(solvent, '') AS solvent,
                       COALESCE(note, '') AS note,
                       COUNT(*) AS duplicate_count
                FROM carbon_nmr
                WHERE delta_ppm IS NOT NULL
                  AND COALESCE(TRIM(assignment), '') <> ''
                GROUP BY compound_id,
                         ROUND(CAST(delta_ppm AS REAL), 4),
                         LOWER(TRIM(COALESCE(assignment, ''))),
                         LOWER(TRIM(COALESCE(solvent, ''))),
                         LOWER(TRIM(COALESCE(note, '')))
                HAVING COUNT(*) > 1
                ORDER BY duplicate_count DESC, compound_id ASC
                """,
            ),
            "compounds_without_1h": fetch_rows(
                cur,
                """
                SELECT c.id, c.trivial_name, c.compound_class, c.curation_status
                FROM compounds c
                LEFT JOIN proton_nmr p ON p.compound_id = c.id
                WHERE p.id IS NULL
                ORDER BY c.id DESC
                """,
            ),
            "compounds_without_13c": fetch_rows(
                cur,
                """
                SELECT c.id, c.trivial_name, c.compound_class, c.curation_status
                FROM compounds c
                LEFT JOIN carbon_nmr cn ON cn.compound_id = c.id
                WHERE cn.id IS NULL
                ORDER BY c.id DESC
                """,
            ),
            "structure_local_missing": structure_local_missing[:10],
            "spectra_local_missing": spectra_local_missing[:10],
        }

        source_category_breakdown = {
            (row["source_category"] or "Unspecified"): int(row["count"])
            for row in cur.execute(
                """
                SELECT COALESCE(NULLIF(TRIM(source_category), ''), 'Unspecified') AS source_category,
                       COUNT(*) AS count
                FROM compounds
                GROUP BY 1
                ORDER BY count DESC, source_category ASC
                LIMIT 12
                """
            ).fetchall()
        }

        data_source_breakdown = {
            (row["data_source"] or "Unspecified"): int(row["count"])
            for row in cur.execute(
                """
                SELECT COALESCE(NULLIF(TRIM(data_source), ''), 'Unspecified') AS data_source,
                       COUNT(*) AS count
                FROM compounds
                GROUP BY 1
                ORDER BY count DESC, data_source ASC
                LIMIT 12
                """
            ).fetchall()
        }

        return {
            "generated_at_utc": generated_at,
            "database_path": str(db_path),
            "counts": counts,
            "quality": quality,
            "relationships": relationships,
            "duplicates": duplicates,
            "coverage": coverage,
            "asset_quality": asset_quality,
            "curation_status": curation_status,
            "source_category_breakdown": source_category_breakdown,
            "data_source_breakdown": data_source_breakdown,
            "samples": samples,
        }
    finally:
        conn.close()


def write_markdown(report: dict, path: Path):
    counts = report["counts"]
    quality = report["quality"]
    relationships = report["relationships"]
    duplicates = report["duplicates"]
    coverage = report["coverage"]
    asset_quality = report["asset_quality"]
    curation_status = report["curation_status"]

    def row_block(title: str, mapping: dict) -> str:
        lines = [f"## {title}", ""]
        for key, value in mapping.items():
            lines.append(f"- `{key}`: `{value}`")
        lines.append("")
        return "\n".join(lines)

    lines = [
        "# NPDB Data Integrity Audit",
        "",
        f"- Generated (UTC): `{report['generated_at_utc']}`",
        f"- Database: `{report['database_path']}`",
        "",
        row_block("Counts", counts),
        row_block("Quality Checks", quality),
        row_block("Relationship Checks", relationships),
        row_block("Duplicate Checks", duplicates),
        row_block("Coverage Checks", coverage),
        row_block("Asset Checks", asset_quality),
        row_block("Curation Status", curation_status),
        row_block("Top Source Categories", report["source_category_breakdown"]),
        row_block("Top Data Sources", report["data_source_breakdown"]),
        "## Sample Records Requiring Attention",
        "",
    ]

    for sample_name, rows in report["samples"].items():
        lines.append(f"### {sample_name}")
        lines.append("")
        if not rows:
            lines.append("- None")
            lines.append("")
            continue
        for row in rows:
            compact = ", ".join(f"{key}={value!r}" for key, value in row.items())
            lines.append(f"- {compact}")
        lines.append("")

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def main():
    args = parse_args()
    report = build_report(args.db)

    args.json_output.parent.mkdir(parents=True, exist_ok=True)
    args.json_output.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    write_markdown(report, args.md_output)

    summary = {
        **report["counts"],
        **report["quality"],
        **report["relationships"],
        **report["duplicates"],
        **report["coverage"],
        **report["asset_quality"],
    }
    print(json.dumps(summary, indent=2))
    print(f"JSON report: {args.json_output}")
    print(f"Markdown report: {args.md_output}")


if __name__ == "__main__":
    main()
