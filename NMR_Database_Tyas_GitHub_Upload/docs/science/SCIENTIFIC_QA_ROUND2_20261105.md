# NPDB scientific QA — round 2 (stack #52 → #56; Issues #17, #18, #25, #27, #44; PRs #40, #41, #52, #53, #56)

**Lane:** independent scientific QA. **Date:** 2026-11-05 JST. **Scope:** scientific accuracy and trustworthiness only.
Outside this review: backend security (Codex), backup/restore and browser acceptance (ChatGPT Work).
No production access; no research data, coordinates or credentials read; no third-party dataset imported; no curated structure touched; `app.py` not edited.

## 0. Status

> **Public release approval: BLOCKED. Real production restore: BLOCKED** (unchanged; nothing in this review argues for lifting either).
>
> Round-1's two CRITICAL labelling defects (presence-based "% Verified"; prefilled experimental defaults / fail-open "curated") are **fixed in the drafts #52/#53** and I re-verified the fixes by execution. **No new CRITICAL finding.** **Eleven HIGH findings remain** (§3), most of them *about the fixes' limits* (stereo search, NMR input, NMR provenance, bioactivity semantics, FAIR) rather than new defects in them. All drafts are unmerged, so none of the corrections is yet in any candidate that could be released.

Heads reviewed: QA `606ba8f`; stack #51 `ab1720a` → #52 `0840226` → #53 `2e884ed` → #54 `9a2091d` → #55 `eff14ad` → #56 `02484b6`. #40 `adca766` and #41 `df5f566` are already integrated upstream (#47); their scientific effects were re-checked in round 1.
Execution environment: Python 3.12.3, RDKit 2026.09.1, pandas 3.0.2 (the stack bounds pandas below 3; my suites also ran green on 3.0.2 except where noted by #54).

**Evidence classes.** **V-EXEC** reproduced by running the live function/source on synthetic data (test names in `tests/test_science_qa_round2.py`, 45 tests, 16 expected failures, each verified in strict mode to fail by assertion only). **V-CODE** read in code. **REPORTED** aggregate from Issues #25/#44 that I could not re-verify. **PROPOSAL** needs validation before adoption. **CURATOR** a scientist must decide.

## 1. Corrections to my own round-1 report
| Round-1 statement | Correction |
|---|---|
| "% Verified … likely near 100 %" (SCI-C1) | Speculation. Issue #25 reports Work saw **27 %** in production. The defect (presence ≠ verification) stands; the magnitude guess was wrong. |
| Default `data_source = "Experimental"` pollutes records (SCI-C2) | **REPORTED:** only **2** production rows have `data_source = "Experimental"`; 12 blank. The default was a code hazard, not a measured contamination. |
| Blank `curation_status` exported as "Curated" | **REPORTED:** production has **0 blank**; labels are 79 curated / 14 reviewed / 3,970 imported. The hazard is the code path plus the **database column default `'curated'`** (nullable), now proposed for change in #54. |
| NMR defaults 500/125/CDCl3 might explain the "no missing solvent/MHz" result | **REPORTED:** 664/1,288 ¹H rows at 500 MHz, 654/1,266 ¹³C at 125 MHz, ~half CDCl3-like, and the **database has no defaults** on those columns. Counts are equally compatible with genuine common settings; **do not attribute to defaults without row-level evidence.** |
| Generated depictions were an unknown share of images (SCI-H1) | **REPORTED: 4,035 of 4,043 (99.80 %) registered image references are app-generated.** This is far larger than I assumed (§3, SCI2-H6). |

## 2. Verification of the fixes (V-EXEC; all pass)
| Change | Verdict |
|---|---|
| #52 sidebar "Core Metadata Coverage: X % with name, class & source" | Honest. The `% Verified` label no longer appears in `app.py` (other uses of the word, e.g. error messages, are unrelated). |
| #52 `normalize_curation_status` fails closed to `imported`; wizard/editor/import/backend paths | Correct for **new** writes. Existing labels are untouched by design (see SCI2-H6). |
| #52 no prefilled `Experimental`, `CDCl3`, 500/125 | Correct; placeholders say "reported solvent / frequency". |
| #52 `is_explicit_positive_outcome` | Exact-match whitelist; `inactive`, `not active`, `not potent`, `moderately active`, `weak`, blank → not counted. Correct and conservative (a *lower bound*, so "Explicit Positive Outcomes" is the right name). |
| #52 ZIP `structure_asset_origin_class`, `embedded_generated_unverified` | Correct for `generated/` references (closes round-1 SCI-H1). |
| #53 NMR coverage denominators; "Heuristic NMR Rank (0–100)"; unit status `Not recorded` with the raw unit untouched | Correct and honest; see wording limits SCI2-M3/H8. |
| #56 chirality-aware Morgan + `HasSubstructMatch(useChirality=True)` | Fixes the enantiomer/E-Z blindness it targets; **does not make search stereo-reliable** (SCI2-H1/H2). Fingerprints are invariant to atom order, SMILES spelling, Molfile round-trip and InChI round-trip (0 mismatches over 50 variants). |

## 3. Prioritized findings

Legend: **[CONFIRMED]** scientific error reproduced; **[PROPOSAL]** correction needs validation; **[CURATOR]** judgement needed. Areas refer to the assignment (1 identity … 8 labels).

### HIGH

**SCI2-H1 — Chirality-aware Morgan fingerprints are blind to some single-centre epimers [CONFIRMED] (areas 1, 2)**
- *Evidence (V-EXEC; app's live `molecule_fingerprint`, legacy API and the new generator agree):* across 10 synthetic stereo-rich fixtures, **8 of 62 single-centre epimers (12.9 %) score Tanimoto 1.000** although their isomeric SMILES and InChIKey stereo block differ (cholesterol 1/8, testosterone-like 1/6, progesterone-like 1/6, cholic-acid-like 2/11, disaccharide-like 1/9, aryl glycoside 1/5, peroxide-lactone 1/7; menthol, camphor, morphinan-like 0). Where distinguishable, epimers still score 0.62–0.96. E/Z flips of an all-E polyene score 0.77–0.79.
- *Risk:* a chemist is shown an epimer as an equally good "similar" hit; epimers (the typical ambiguity in marine natural products) cannot be separated by score. #56's test `high_similarity_threshold_excludes_opposite_stereoisomers` is true for alanine-sized molecules only.
- *Correction:* treat the fingerprint as **retrieval only**; always compute and show the exact stereo relationship to the query (identical / enantiomer / diastereomer / unspecified, from isomeric SMILES or InChIKey block 2; implemented and tested in `npdb_structure_identity.py`, 44 tests).
- *Test:* `test_some_single_centre_epimers_are_indistinguishable…` (characterization), `test_desired_every_single_centre_epimer_is_distinguishable…` (expected failure), `test_exact_isomeric_identity_does_distinguish…` (passes).

**SCI2-H2 — Stereo-free queries lose recall after #56 [CONFIRMED] (area 2)**
- *Evidence (V-EXEC):* a skeleton drawn without stereo scores **0.31–0.57** against its own correct stereo-defined record, the same value as that record's enantiomer (old stereo-blind configuration: 1.000). For the disaccharide-like fixture the correct compound scores **0.306 < the default 0.35 threshold and is not returned**. Enantiomers score 0.31–0.57 and 9 of 10 pass the default threshold.
- *Risk:* the most common query (an unspecified-stereo sketch) now ranks the correct compound no higher than its mirror image and can drop it entirely; the caption "unspecified configuration remains ambiguous" does not fix ranking.
- *Correction [PROPOSAL, validate on an approved natural-product benchmark]:* two scores per hit — connectivity similarity (achiral fingerprint) and stereo-aware similarity — rank by connectivity when the query stereo is incomplete; add an "ignore stereochemistry" option; keep the stereo-relation label. Do not give a single percentage.
- *Test:* `test_a_stereo_free_query_scores_the_correct_record_no_higher_than_its_enantiomer` (characterization), `…offers_connectivity_level_similarity…` (expected failure).

**SCI2-H3 — JCAMP-DX / peak-file parsing silently returns wrong "peaks" [CONFIRMED] (areas 3, 4)**
- *Location:* `parse_peak_upload`. *Evidence (V-EXEC, synthetic files):* (a) a processed spectrum (`##XYDATA=(X++(Y..Y))`) returns every second number — x values and intensities — as peak positions (`[3000, 20, 40, 2000, 60, 80]`); (b) a peak table in **Hz** (`##XUNITS=HZ`, 500 MHz) is returned as if ppm (`[3630, 3425]` instead of 7.26, 6.85); (c) `PEAK TABLE=(XYW..XYW)` returns **widths as peaks** (`[7.26, 0.01, 6.85, 0.02]`); `##.OBSERVE NUCLEUS`, `##XFACTOR` and solvent are ignored; no length cap.
- *Risk:* a correct upload yields nonsense candidate rankings with no warning; a ¹³C file can be matched as ¹H; huge inputs also cost O(n·m) per compound.
- *Correction:* accept only explicit peak tables; read `##XUNITS`, `##.OBSERVE FREQUENCY`, `##.OBSERVE NUCLEUS`, `##XFACTOR`; convert Hz→ppm only when the observe frequency is present, otherwise reject; reject processed spectra with a message (peak picking is a separate, parameterised step); cap peaks; show the parsed list for confirmation. `npdb_nmr_input.py` supplies the plain-text parser (decimal comma, typographic minus, ranges, annotations, plausibility).
- *Tests:* three characterization + three expected-failure tests (`NmrInputAndQuality`).

**SCI2-H4 — Unassigned peak lists cannot be stored [CONFIRMED] (areas 3, 6)**
- *Evidence (V-CODE/V-EXEC):* `st.error("Assignment is required.")` ×4 (add/edit ¹H and ¹³C), `delta_ppm and assignment are required` in both importers; required columns `["delta_ppm","assignment"]`.
- *Risk:* the dominant real-world case (peak lists reported without assignments, and NP-MRD's *unassigned* peak-list archive from Issue #27) can only be entered by typing placeholders or **inventing assignments** — fabricated data. Assigned and unassigned lists become indistinguishable.
- *Correction:* make assignment optional; store `assignment` NULL and a dataset-level `assignment_status` (assigned / partially / unassigned). *Test:* `test_unassigned_peak_lists_cannot_be_stored`, `test_desired_peaks_can_be_stored_as_explicitly_unassigned`.

**SCI2-H5 — NMR datasets have no conditions/provenance layer [CONFIRMED design gap] (areas 3, 6)**
- Peak rows carry per-peak `solvent` and `instrument_mhz` only. Missing: dataset identity, referencing (TMS/residual solvent and value), temperature, observed-nucleus vs spectrometer frequency basis, origin (experimental / literature / imported / predicted), source accession and licence, reference link. NP-MRD spectrum pages cite CDCl₃ references of 7.25/77.0 and 7.26/77.0 ppm whereas Fulmer et al. (Organometallics 2010) tabulate 7.26/77.16, with free-form reference text, and "simulated" spectra whose "experimental conditions" are simulation settings. The search index **pools all datasets of a compound** (a second solvent halves its own score).
- *Correction [PROPOSAL, already designed and validated on real PostgreSQL + SQLite]:* `docs/science/proposed_migrations/009_*` (verbatim conditions, per-condition provenance, fail-closed rights, evidence-bearing curation events). *Test:* the schema suite (16 tests).

**SCI2-H6 — The structure layer is largely machine-generated and imported [REPORTED + V-CODE] (areas 1, 6, 8)**
- **99.80 % (4,035/4,043) of image references are `storage://structures/generated/…`; 97.7 % (3,970) of records are `imported`; only 79 (1.9 %) carry "curated" and 14 "reviewed"** (REPORTED). The 79 "curated" labels were created while the UI defaulted to curated (round-1 SCI-C2), so they are **labels, not evidence** (Issue #44 says the same).
- *Risk:* a generated image is a drawing of the stored SMILES — it **cannot cross-validate the SMILES**, so image counts, `Structures` (any of SMILES/InChI/InChIKey/image path), the presence-based completeness score (still 100 % for junk, V-EXEC: `test_completeness_percentage_is_presence_only…`) and viewer text ("curated compound dossiers", "a read-only workspace for curated records", V-CODE) all overstate structural evidence.
- *Correction:* display legacy "curated" as "curated (legacy label, not audited)" until a curator audit; stop counting generated images as completeness; replace viewer wording; make the database default `imported` (proposal in #54, needs the restore gate); record structure evidence tier (§5). **CURATOR:** audit the 79 + 14; decide whether the 8 external HTTPS depictions (PubChem/NCI host classes) are curated.
- *Tests:* `test_viewer_text_describes_the_whole_database_as_curated`, `test_desired_viewer_text_does_not_claim_curation…`.

**SCI2-H7 — Bioactivity semantics remain unsafe for interpretation [CONFIRMED] (area 5)**
- *Evidence (V-CODE/V-EXEC):* outcome is free text with no controlled values and **no "not tested" state** (negative and untested data cannot be distinguished from absent data); relation defaults to `=` (an unreported `<`/`>` becomes an equality); one value/unit slot (no test concentration for % inhibition); the unit dropdown offers `mm` but **not `mM`** (millimolar entries invite selecting millimetre); `Unit Status` says "Recorded" for *any* non-blank unit (an `IC50` in `%`, a zone size in `uM`).
- *Risk:* misread potencies; negative results lost; unit/endpoint contradictions look validated.
- *Correction [CURATOR + PROPOSAL]:* controlled outcome vocabulary {active, inactive, inconclusive, not tested}; relation "unreported" state; test concentration for percent endpoints; `mM`/`M`/`pM`/`ng/mL` in the vocabulary; replace "Recorded" with "Recorded (compatibility not validated)" or use the endpoint-aware classifier (`npdb_bioactivity_units.py`: whole-token endpoints, `pIC50`/ratios dimensionless, `mM` ≠ `mm`, calculated values flagged; 17 tests). The 84 concentration-like rows are the first review queue; **never auto-fill units**.
- *Tests:* `BioactivityAndLabels` (3 characterization + 4 expected failures).

**SCI2-H8 — NMR entries are never checked for plausibility against the formula [CONFIRMED absence] (areas 1, 3)**
- No NMR-vs-formula consistency check exists (no validator in `app.py`); stored formula, mass and InChIKey format are not validated either (verified at #56: zero uses of `CalcMolFormula`, `MolWt`, `ExactMolWt`, `rdMolDescriptors`; `is_inchikey_like` is used only on the query path). This also governs the **3 missing formulas**.
- *Correction:* entry/import QC (specified in §6: ¹³C peak count ≤ carbon count, ¹H integral sum ≤ hydrogen count, shift windows, H-count from carbon types). Formulas: use the proposal-only tool in `npdb_identifier_validation.py` (corroborated by InChI/InChIKey or recorded mass; salts, enhanced stereo, conflicts and disagreeing masses block; always needs a curator). *Test:* `test_desired_nmr_entries_are_checked_against_the_molecular_formula` (expected failure) + 32 identifier tests.

**SCI2-H9 — Stereochemical configuration status is not representable [CONFIRMED] (area 1)** — unchanged from round 1 (no absolute / relative / unassigned field, no method such as X-ray, ECD, Mosher, synthesis). `curated` structures with relative stereo look authoritative.

**SCI2-H10 — FAIR/attribution gaps [CONFIRMED] (area 7)** — exports carry only an owner credit line (`OWNER_CREDIT`); no licence, citation text, release/version, persistent resolvable identifier (internal integer id only), or third-party attribution field, while 97.7 % of records are imported from external sources (free-text `data_source`). See §7. *Tests:* `test_exports_carry_no_licence_citation_or_version_information`, `test_desired_manifest_states_licence_citation_and_export_version`.

**SCI2-H11 — Location privacy remains an open scientific policy [CONFIRMED] (carried from round 1; #43)** — withheld GPS is a silent blank; locality text, depth and sample code are unprotected. Policy tiers and an explicit "withheld" marker are still needed (round-1 SCI-H7).

### MEDIUM
- **SCI2-M1 [CONFIRMED]: regioisomers are indistinguishable by similarity** — 5- vs 6-bromoindole **0.680**, 4- vs 5-bromopyrrole-2-COOH 0.414, 3- vs 4- 0.355, o-/p-cresol 0.333; all have the same formula, distinct identity. Results should flag "constitutional isomer of the query (same formula)". *Test:* `test_regioisomers…`, `test_desired_search_results_flag_constitutional_isomers…`.
- **SCI2-M2 [CONFIRMED, policy → CURATOR]: a stereo-specified substructure query excludes candidates whose stereo is unspecified.** (2-butanol fragment in 2-pentanol: specified query → specified candidate True/False for same/opposite; **unspecified candidate False for both**; unspecified query → True.) Correct strictness but silently hides incompletely curated records; offer "include records with unspecified configuration" and show the excluded count.
- **SCI2-M3 [CONFIRMED]: unit-status wording** — "may be dimensionless" is wrong for IC50/MIC-type endpoints (a unit is *required*); use endpoint-aware text (required / may be dimensionless / not applicable).
- **SCI2-M4 [CONFIRMED]: percent labels for non-probabilities** — "Top Similarity / Match {x}%" and the structure export "Score (%)" show Tanimoto×100; one slider (default 35) drives two different metrics (Tanimoto and NMR heuristic).
- **SCI2-M5 [PROPOSAL]: tautomer / charge / salt policy** — identity is exact isomeric SMILES (correct as "exact"); no standardized or parent mode. If added, it must be stereo-preserving (RDKit's tautomer canonicalization silently deletes sp3/E-Z stereo by default; reproduced). *Policy is CURATOR.*
- **SCI2-M6 [CONFIRMED]: presence-based completeness** — `calculate_completeness_score` reaches 100 % for junk and counts a generated image path and a default `data_source` (V-EXEC).
- **SCI2-M7 [CONFIRMED, carried]: ZIP manifest** — no reason codes (all failures collapse), no file list/digests, XLSX dropped silently, no NMR-origin / location-withheld / licence statements.
- **SCI2-M8 [CONFIRMED, decision requested in #18]: exact-zero tolerance** — `optimal_nmr_peak_matches([0],[5e-13],0)` matches (absolute slack 1e-12). *Decision in §4.*
- **SCI2-M9 [PROPOSAL]: legacy RDKit API and legacy stereo perception** — `GetMorganFingerprintAsBitVect` is deprecated (warnings suppressed) and `Chem.GetUseLegacyStereoPerception()` is `True` in 2026.09.1; chirality bits derive from that perception. Keep RDKit pinned and re-run §6 tests on every upgrade.

### LOW
`Mr` label vs stored mass basis (average vs monoisotopic); free-text `j_value` / `proton_count` / `carbon_type`; header "Residue / Note" (peptide wording) on natural-product tables; `calculate_workspace_health` hard-coded zeros (unused); no DOI normalization or resolvable links (DOI on 104/4,063 reported); exported `Structure Image Link` exposes an internal storage path (security lane).

## 4. Decisions requested of the science lane in Issue #18

1. **Exact-zero tolerance.** NMR shifts are reported to ≤ 0.001 ppm, so 1e-12 ppm slack is physically irrelevant for `tolerance > 0` (keep the inclusive rule fixed in #30). For `tolerance == 0`, define the match as **equality of the reported decimal values** (e.g. equality after rounding both to 9 decimals). Test: `test_desired_zero_tolerance_means_equality_at_reporting_precision`.
2. **Stereo-aware substructure / standardization contract.** (a) Query with specified stereo matches only identical specified configuration by default; an explicit option includes unspecified-configuration records and reports how many were excluded; unspecified query matches all. (b) No standardization is ever applied to stored records; standardized/parent/tautomer comparison uses *derived keys only*, with `RemoveSp3Stereo=False`, `RemoveBondStereo=False`, a stereo-loss guard and recorded protocol/RDKit versions (implemented, `npdb_structure_identity.py`). (c) Every hit shows identity mode, stereo relation, and whether the formula equals the query's. (d) Enhanced (AND/OR) stereo is never treated as absolute.
3. **Curator validation policy** (§5): evidence tiers and what each permits the UI to say.

## 5. Evidence-quality ladder (PROPOSAL, curator-approved wording)
| Tier | Evidence recorded | May be called |
|---|---|---|
| E0 | generated depiction of stored text; no source | "Computed from SMILES (unverified)" |
| E1 | imported record from a named external database + its record id, licence, retrieval date | "Imported (not independently reviewed)" |
| E2 | structure + reference (DOI/URL) checked against the article by a named reviewer | "Reference-checked" |
| E3 | E2 + NMR/HRMS reported in the article match the stored data | "Spectroscopically consistent with the reference" |
| E4 | E3 + configuration established (X-ray/CCDC, ECD with calculation, synthesis) with method | "Configuration assigned (method)" |
"Curated/verified" should be a *derived* label from E2+ events with reviewer and date (`curation_events` in the schema proposal), never a free selection.

## 6. Synthetic regression test catalogue
✔ = implemented here or in a companion suite; ○ = specified (executable `desired` test exists where noted) for a future implementation PR.

| ID | Scenario (synthetic) | Expected | Status |
|---|---|---|---|
| T-ID-01…03 | enantiomer / epimer / E-Z exact identity | distinct canonical isomeric SMILES and InChIKey block 2 | ✔ #56 tests, C13 suite, R2 |
| T-ID-04 | regioisomer pair (bromoindoles) | identity distinct; hit annotated "same formula" | ✔ characterization + desired (R2) |
| T-ID-05 | tautomers (2-pyridone/2-hydroxypyridine; keto/enol); ring-chain not merged | exact: differ; standardized mode: stereo-preserving merge | ✔ C13 suite |
| T-ID-06 | salt / zwitterion vs parent | parent mode links them; stereo preserved | ✔ C13 suite |
| T-ID-07 | stereo-free query vs defined record | connectivity-level hit with stereo relation "unspecified in query" | ✔ desired (R2) |
| T-ID-08 | specified substructure vs unspecified candidate | policy option + excluded count | ✔ characterization (R2) |
| T-ID-09 | atom order / spelling / Molfile / InChI round-trip | identical fingerprint and keys | ✔ R2, C13 |
| T-ID-10 | AND/OR enhanced stereo | never equal to absolute; InChI flagged | ✔ C13 suite |
| T-SIM-01 | every single-centre flip of stereo-rich fixtures | fingerprint < 1 **or** exact stereo label shown | ✔ R2 (fingerprint fails; exact passes) |
| T-SIM-02 | enantiomer / flat query vs default threshold | stereo relation shown; connectivity score offered | ✔ R2 |
| T-SIM-03 | threshold protocol | per-metric thresholds validated on an approved benchmark (§8) | ○ |
| T-NMR-01…03 | JCAMP XYDATA / Hz table / XYW widths | reject / convert with observe frequency / ignore widths | ✔ desired (R2) |
| T-NMR-04 | file nucleus (`##.OBSERVE NUCLEUS=^13C`) vs ¹H search mode | warn or block | ○ |
| T-NMR-05 | unassigned peak list | stored with `assignment` NULL, `assignment_status = unassigned` | ✔ desired (R2) |
| T-NMR-06 | formula C15H24O2: 16 distinct ¹³C peaks; ¹H integrals summing to 26; 12 ¹³C peaks; ¹³C carbon types giving 27 H | flag, flag, accept (symmetry), flag | ○ (validator absent; desired test asserts one exists) |
| T-NMR-07 | shift windows: ¹H outside −5…20 ppm, ¹³C outside −30…300, ¹³C list pasted into ¹H | warn on entry | ✔ `npdb_nmr_input.py` suite |
| T-NMR-08 | multiplicity vocabulary (s, d, t, q, m, br s, dd, dt, td, ddd…), `J = 8.0, 2.5 Hz` numeric list, integral as integer | accepted / numeric list; `8..0` rejected | ○ |
| T-NMR-09 | tolerance budget: ¹³C CDCl₃ 77.0 vs 77.16 (Δ 0.16) + 0.1-ppm rounding; ¹H 7.25 vs 7.26 | tolerance ≥ budget within one solvent; never pool solvents | ○ (documented) |
| T-NMR-10 | `tolerance == 0` | equality at reporting precision | ✔ desired (R2) |
| T-NMR-11 | matcher optimality / boundary / negatives | oracle-equal; no float misses | ✔ QA #30 + science suite |
| T-NMR-12 | score semantics (one peak = 81; sparse decoy; pooled datasets; absent data) | per-dataset E-value ranking, "no data" ≠ 0 | ✔ characterization + prototype suites |
| T-BIO-01 | outcomes `inactive`, `not active`, `moderately active` | not counted as positive | ✔ R2 (passes) |
| T-BIO-02…04 | blank unit; unit/endpoint compatibility; `mM` vs `mm` | marker; compatibility flag; both units available | ✔ R2 |
| T-BIO-05 | `pIC50`, `IC50 ratio`, `SI` | dimensionless; blank unit not a defect | ✔ classifier suite |
| T-BIO-06…07 | relation unreported; outcome "not tested" | explicit states | ✔ desired (R2) |
| T-BIO-08 | `% inhibition` row | test concentration required | ✔ classifier suite |
| T-BIO-09 | docking/ΔG rows | flagged calculated, never mixed with measured potency | ✔ classifier suite |
| T-LAB-01…03 | "Verified" absent; curated claims; denominators shown | honest wording | ✔ R2 |
| T-PROV-01 | generated / external / storage / local / absent image | origin class + status | ✔ R2 (passes) |
| T-PROV-02 | legacy "curated" label | shown as unaudited until E2 evidence | ○ |
| T-FAIR-01 | export manifest | licence, citation text, version/snapshot id, source attribution | ✔ desired (R2) |
| T-FAIR-02…04 | persistent resolvable id; JSON-LD/Bioschemas record; third-party attribution preserved (NP-MRD: CC BY-NC 4.0, accession, source link, modification note) | present | ○ |

## 7. FAIR assessment (evidence-based)
| Principle | State | Evidence | Recommendation |
|---|---|---|---|
| F1 persistent identifier | ✗ internal integer id | exports show "Compound ID" only | stable `NPDB:` accession + InChIKey; resolvable URL |
| F2/F3 rich, linked metadata | partial | free-text `data_source`; no dataset layer | schema proposal 009 (source, accession, licence, conditions) |
| F4 findable | partial | in-app search only | machine-readable landing metadata |
| A1 retrievable | gated (login) | access gate | state the access policy and what is open |
| I1/I2 standard vocabularies | ✗ | free-text solvent, units, outcome, spectrum type | controlled vocabularies (UCUM units; nmrML/NMReDATA terms) |
| I3 qualified references | ✗ | DOI on 104/4,063 (reported); URL-form DOIs | normalized DOI links; reference per dataset |
| R1.1 licence | ✗ | none in app or exports | licence per source and per export |
| R1.2 provenance | partial | origin class in ZIP; no dataset provenance | §5 tiers; `curation_events` |
| R1.3 community standards | ✗ | no NMReDATA/nmrML/JCAMP export | export an NMReDATA/nmrML record per dataset |
Third-party data: NP-MRD is CC BY-NC 4.0 (attribution, source link, licence notice, modification statement, noncommercial limits — verified from np-mrd.org); its "simulated" spectra must never be presented as measured. The licences of the other external sources behind the 3,970 imported records are **not established** here — a label-only aggregate of `data_source` (counts per label) would settle which licences are involved.

## 8. Proposals requiring validation before adoption
1. **Representative benchmark (owner-approved, no raw data in CI):** ≥ 200 stereo-rich marine natural products with known epimer/enantiomer pairs; measure (a) recall@k of the correct compound for stereo-defined and stereo-free queries under the old, chirality-aware, and dual-score methods; (b) the blind-centre rate (here 12.9 % on synthetic fixtures); (c) false-inclusion rates of epimers at candidate thresholds. Acceptance: stereo-defined recall@1 unchanged, stereo-free recall@1 restored, every epimer labelled.
2. **NMR ranking:** per-dataset, null-calibrated E-value ranking (prototype tested on synthetic data only) must be validated on approved real datasets before replacing the heuristic.
3. **Tautomer/parent policy** and **evidence tiers** require curator sign-off.
4. **Controlled vocabularies** (outcome, units, multiplicity, solvent) need the owner's term lists.

## 9. Read-only aggregate queries that would settle open facts (counts only; none executed by me)
`data_source` label counts; count of `curation_status='curated'` rows having any reference/DOI; share of `generated/` references per `curation_status`; ¹H/¹³C rows per (solvent, MHz) pair; for the 84 concentration-like rows the exact `potency_type` label counts and whether they cluster in few `assay_source` values; compounds whose `molecular_formula` is blank (ids only).

## 10. Release position
Keep **release approval BLOCKED** and **production restore BLOCKED**. Scientific conditions for moving from BLOCK to CONDITIONAL PASS: merge-ready fixes #52/#53/#56 after independent review; resolve SCI2-H1/H2 (stereo relation + dual score), SCI2-H3 (peak-file parsing), SCI2-H4 (unassigned peaks), SCI2-H6 wording and legacy-label audit, SCI2-H7 vocabularies and unit compatibility, SCI2-H10 licence/citation/version in exports; plus the earlier location-policy decision. The P0 gates owned by others (#24, #19, #22, #43 sign-offs) are additional.

## 11. Reproduction
`git fetch origin '+refs/pull/56/head:refs/remotes/origin/pr/56'`; `git checkout -b qa origin/pr/56`; apply the round-2 patch; `cd NMR_Database_Tyas_GitHub_Upload && python -m unittest tests.test_science_qa_round2` (45 tests, 16 expected failures); `NPDB_STRICT_DESIRED=1 …` runs the 16 desired-property tests as ordinary tests (all fail by `AssertionError`). Companion modules from earlier lanes (structure identity, identifier validation, NMR validation/prototype/parser, cache freshness, schema proposal, bioactivity unit classifier) merge cleanly onto QA `606ba8f`; with the existing suite the combined run was 311 tests green.
