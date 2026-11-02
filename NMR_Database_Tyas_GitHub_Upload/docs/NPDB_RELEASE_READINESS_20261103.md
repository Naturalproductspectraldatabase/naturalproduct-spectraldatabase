# NPDB scientific release criteria and responsible development plan

**Baseline date:** 2026-11-03 (JST)  
**Scope:** Natural Products Spectral Database / marine natural-products research.  
**Status:** Working development plan, not a statement of public-release readiness.  
**Data provenance:** Live Supabase read-only aggregate queries on 2026-11-03; do not copy production rows, credentials, geographic coordinates, or proprietary data into issues or tests.

## 1. Verified production baseline

| Metric | Verified count | Important interpretation |
| --- | ---: | --- |
| Compound rows | 4,063 | Not necessarily unique, fully curated chemical identities |
| Rows with structure identifiers | 4,045 | An identifier is not structural validation |
| Compounds with proton-NMR peak entries | 59 | 1.45% of compound records |
| Compounds with carbon-NMR peak entries | 59 | 1.45% of compound records |
| Compounds with spectrum files | 89 | 105 file references; 100 labeled 1H, 5 labeled 13C |
| Compounds with bioactivity records | 1,014 | 14,649 bioactivity rows |
| Compounds with DOI field | 104 | 2.56% of compound records |
| Compounds with a nonempty source-category field | 1,082 | 73.4% missing source category |
| Compounds with organism field | 106 | ~2.6%; distinguish organism producer from host/substrate |
| Duplicate nonempty InChIKey groups | 6 | Investigate, never automatically delete |

These are record-field completeness statistics, not verification statistics. The dataset currently has limited NMR coverage, so any tagline emphasizing searchable experimentally acquired NMR data must qualify coverage transparently.

## 2. Deployment gates, in strict order

### Gate A: integrity and security
- Confirm valid, restorable database and object-storage backups; perform restore rehearsal on staging, not production.
- Review RLS and direct grants and inspect exposed views, login fail-closed behavior, per-user server-side permissions, rate limiting, and sensitive fields.
- Restore-safe and concurrent-edit regression tests must pass. No cache-fallback write of stale data.
- Every New Submission step must persist and read back actual values in an isolated database.
- Ensure curation labels represent actual review evidence, never column completion alone.

### Gate B: integration
- Run full test suite on a temporary combined checkout of #3/#6/#4 and subsequent PRs.
- Run Streamlit AppTest and real-browser tests of owner, editor, viewer, search, result navigation, structured NMR, specimen visibility, and exports using **synthetic records only**.
- Test mobile widths, keyboard navigation, WCAG 2.2 AA contrast, browser zoom 80/100/125%, and error recovery.
- Verify scientific-image rendering does not override approved ChemDraw PNG images with a potentially incorrect SMILES structure.
- Benchmark 1k/4k/10k compound records, memory and cold starts, including cache, pagination, and image loads.

### Gate C: controlled release
- Prefer dedicated staging deployment with separate staging database, secrets and storage; never point staging at production write credentials.
- Review change log, rollback steps, release diff and confirmation that backups are restorable.
- Merge in staged increments with smoke tests after each release. Stop and rollback if any integrity gate fails.

### Gate D: public scientific service
- Publish About, Data sources and provenance, How to cite, License, Privacy, Terms, Contact, Data dictionary, Changelog, accessibility/help guide.
- Establish fixed record identifiers and stable permalinks before publishing a database DOI; version data releases separately from app releases.
- Publish transparent coverage and validation statistics and distinguish incomplete imported records from curated, source-confirmed records.
- Pilot with at least 3–5 external researchers using representative scientific tasks.
- Register with re3data/FAIRsharing and write a database article only after discovery, metadata, license, persistence, and curation policies are operational.

## 3. Scientific data architecture

The primary entity **Compound** should be separate from **Molecular identity representation**, **NMR dataset**, **NMR peak**, **Spectra file**, **Bioactivity assay**, **Specimen**, **Taxon/organism and host**, **Reference**, and **Curation event**. Each NMR dataset should record compound, nucleus/experiment, solvent, frequency, temperature if reported, reference and primary data provenance; search algorithms compare datasets under compatible conditions rather than pooling all peaks from all solvents.

Use reported precision and units: delta(H) and delta(C) ppm, coupling J in Hz, shift multiplicity, integrations, exact mass and adduct, HRMS mass error ppm, UV wavelength/log(epsilon), IR wavenumbers in inverse cm. Structure-derived formula, mass and InChIKey should be cross-checked, not blindly trusted. Explicitly distinguish absolute, relative and undetermined stereochemistry, evidence method and revisions.

No scientific record or source coordinates may be automatically 'corrected' or deleted based solely on a heuristic. Flag uncertain or duplicate records for curator review.

## 4. Recommended interface architecture

Public research navigation: **Home / Search & Match / Compounds / NMR & Spectra / Bioactivity / Specimens / Documentation**. Owner/editor only: **Curation / Quality & Operations / Administration**. Put primary search and truthful coverage statistics on Home, not above navigation inside a crowded sidebar.

Maintain one design system: compact semantic header, distinct brand colors and status colors, controlled typography, accessible light/dark modes, consistent notation, keyboard focus, responsive tables, meaningful loading/errors, concise row details and persistent links. Show source and status adjacent to scientific results; never use misleading '100% Verified' labels.

## 5. Owner and institution decisions (do not infer)

- Final database name/acronym, exact declared scientific scope and tagline; search for collisions across scholarly indexes and domains.
- Contact address; whether to represent university or laboratory affiliation, and any institutional approval.
- Which imported data may legally be redistributed; licenses for curated metadata, source spectra, original pictures and software may differ.
- Location visibility at **individual specimen/record level**, based on publication rights, conservation, collaborations and source context.
- Domain / hosting ownership and annual operating budget; backup storage and retention arrangements.
- Citation author/maintainer list, DOI release strategy, and scope for any public article.

## 6. Access needed for end-to-end QA

1. GitHub repository read/write integration plus protected merge checks (connected); offline tests run inside GitHub Actions. Local ChatGPT terminal DNS restrictions do not require sharing GitHub personal tokens.
2. Supabase connector (connected). For schema/live testing, use a **separate staging Supabase project or branch** with test-only records, and approve any incremental branch charges.
3. Streamlit Community Cloud **owner dashboard and logs** plus a separate staging app; access through a cloud browser/Work session when available, without posting secrets or account passwords into chat.
4. Test accounts for owner/editor/viewer with **disposable synthetic identities**, not actual users' passwords. No service-role credentials in CI or logs.
5. A reviewable record of brand assets and documentation licenses, including actual rights.

**Do not confuse CI success with production browser or staging validation.** No audit is 'perfect'; continuous regression, data curation, availability monitoring and owner-approved release procedures are required.
