# NPDB Structure Image Integrity — Curation Policy and Audit Notes

**Status:** Proposed policy; draft-only change. **Date:** 2026-11-02. No live database, Storage, account or deployment changes are authorized by this document.

## Owner's authoritative-source clarification

For compound IDs **1–5**, the manually curated **PNG files** under `structures/curated_structures/` are the **approved visual structures**. The owner drew/exported these PNGs **using ChemDraw**; they are PNG images, **not** ChemDraw `.cdx` or `.cdxml` source files. Do not assert that native ChemDraw structure files exist.

**Never override or replace a curated PNG with a depiction rendered from SMILES, InChI or RDKit**, including in the case of a low-resolution PNG, a network error, or an unavailable Storage signed URL. Normalize valid PNGs onto an opaque white background for legibility. If the reference is unavailable, give a visible warning and stop; preserve the original reference unchanged.

The rest of the existing dataset primarily uses images in `generated/` that originate from SMILES. These are **computed depictions**, not independently verified chemical structure illustrations. Display a truthful source label and make scientific review possible. A chemical depiction and machine-readable SMILES are not interchangeable proofs of chemical identity.

## Why this matters for NPDB

- The private Supabase Storage bucket `structures` requires authorized access or signed URLs. Current records 1–5 store public-style URLs that the app attempts to convert to signed URLs; failure must not switch silently to chemically incorrect SMILES.
- Existing code previously replaced even successfully loaded PNGs with computed structures if the shorter image edge threshold was not met. This is inappropriate for manually reviewed drawings.
- The app uses a SMILES-generated fallback on numerous image/display paths, which may silently expose a chemically wrong structure if its identifiers disagree with the curated original.
- For compounds 1–3, the database's SMILES/InChI are not chemically consistent with the approved curated amphilectane structures. **Do not overwrite them automatically**; confirm from a trusted atom-mapped MOL/SDF, manually reviewed source, or peer-reviewed structure before updating identifiers or assigning stereochemistry.

## Read-only audit baseline (2026-11-02)

Metadata-only SQL queries, without downloading private file bytes, found:

| Scope | Count |
| --- | ---: |
| Compounds | 4,063 |
| Compound image references to `generated/` | 4,035 |
| Compound image references to curated images | 5 |
| Compounds without a structure image reference | 20 |
| Records with other external HTTP structure image references | 3 |
| Structure bucket objects | 4,076 |
| Objects in `generated/` | 4,062 |
| Generated objects not currently directly referenced by a compound | 27 |
| ETag+size candidate duplicate groups | 29 (30 extra copies, ~2.55 MB potential saving) |
| Formula-to-InChI formula compared | 4,040 |
| Formula-to-InChI formula mismatches requiring review | 108 |
| Of those: simple/neutral candidate mismatches | 21 |
| Of those: charge/salt/multicomponent candidates | 87 |
| Trivial names consisting only of a CAS-like number | 64 |
| Empty or placeholder compound names | 13 |

The storage reference matching is based on metadata and URL decoding, **not an authenticated file read or hash verification**. ETags are not guaranteed cryptographic identity proofs in all situations, and the SQL formula comparison is a screening heuristic; salts, protonation, mixtures, adducts and nomenclature differences require scientific interpretation.

A small set of generated images with different compound IDs shares exactly the same stored ETag: IDs 3997/3998/3999 and 4043/4045. For 3997–3999, differing formula annotations accompany the same SMILES. These require manual source comparison rather than automated data correction.

The files in `curated_structures/` for IDs 1–5 should be **preserved**. No file deletion, database mutation, key/permission change, bulk rewrite, or automatic cleanup is proposed.

## Proposed acceptance checks before merging

1. A curated PNG smaller than 700 px displays as that PNG, not a regenerated SMILES depiction.
2. A nontransparent white canvas remains white; a transparent input gets an opaque white canvas.
3. If an uploaded/curated reference fails, no silent SMILES replacement is shown, and the UI gives an actionable warning.
4. Existing generated images are labeled as computed and not curator-verified.
5. Private Storage signed-URL failures do not crash the page; original paths are not rewritten.
6. Test the browse detail, search result card, summary thumbnail and download preview separately.
7. Check normal browsing memory use with 4,000+ records; do not fetch all images eagerly.
8. Validate using dummy files, no real service credentials. An independent reviewer must run complete test suite and UI tests on a checked-out repository.
9. Explicit owner review is required for merge and separately for any production deployment.

## Future safe data-model changes (not implemented here)

- Preserve `curated_image_reference` and `generated_preview_reference` separately, with an explicit provenance/source and reviewer ID/date.
- Store source-native molecular files **only if available and owner-approved**; PNG alone cannot establish atom-level stereochemistry.
- Add a structure/formula consistency flag and scientific curator review queue, not an automatic correction or deletion.
- Apply per-record privacy rules and file access checks for unpublished structures.
- After a verified independent backup, inspect potential duplicates/orphan files; **never delete based only on matching names, paths, file sizes or ETags**.

This branch changes visual safety behavior only. It intentionally does not change any live molecular formula, SMILES, InChI, CAS number, compound name, Storage object or user role.
