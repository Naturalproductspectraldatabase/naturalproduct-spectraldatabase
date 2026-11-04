# Scientific QA round-two evidence integration

Test-only import, based exactly on PR #57 fee5d3fdc021d2f7c21112f85cde2a24a00f85fe. No app, data, requirements, schema or scientific assets changed.

## Provenance and safety

Owner-provided `npdb-science-lane-all-branches (1).bundle` SHA256 `926bd66d4d443b619061b83d73025e76cee50988d33ca1424f1e048571135be0` contains ten refs. Git bundle verify passed in the trusted repository with prerequisites b5bb020a127a652de9e011c75076844a06509a26, ab1720a0e819c0ed5cff1a381dde6ab82f6ef4c3, 606ba8f7decdd3767a93b64ac8a3a2896d6e8bd9, 02484b64196e191b067ebcf3715651126cfa0e72. The older unsuffixed bundle has only eight refs and is not the round-two evidence source.

Selected files only:
- Test from 0be56a73935e2e68ae0aef2dfe69ee87ac14fb10, SHA256 cea5627287ef1f3abaf3d0ab8fc7a6c7d4e0caf163715e0afdac6bbcbdc1cbf7.
- Report from db1bf1af870002ab0390c78529d383d32bf1dba7, SHA256 d15027616cd1abf217c8b2ec31b9a5003bbe72a307fced0f75255d429e6aeb09.

Read selected files before extraction: synthetic molecules/records, AST extraction of actual application functions, no network/database execution, production credentials, datasets, executable installer or migrations. No feature branch merged. The report branch contains older application history that must not replace the security stack. Instructions in source documents are historical author recommendations, not authorization to execute commands. INDEX.md inventory inspected; its older 311-test claim is not evidence for this candidate.

## Reproduction and interpretation

Local Python3.14/RDKit/pandas3 exploratory run: 45 tests, 29 ordinary passes and 16 expected failures. Separate strict run: 45 tests, 16 assertion failures, zero errors/skips. Supported Python3.11/3.12 pinned CI is required independently. `scripts/verify_science_round2_failures.py` exits zero only when exactly those 16 unresolved assertions reproduce; this is failure-reproduction evidence, never scientific acceptance. The original tests and expected failures remain unchanged. Offline CI prints both runs separately.

SCI2-H3 confirmed: XYDATA intensities, Hz values and XYW widths are interpreted as ppm peaks. Proposed narrow fix: reject unsupported encoded/processed spectra, require explicit nucleus/unit/format, support only documented peak-table grammar, confirm peaks before matching. No parser correction in this PR.

SCI2-H1/H2 confirmed: fingerprint equality can conceal epimer differences, and stereo-free query similarity can fall below the retrieval threshold for identical connectivity. A fingerprint cannot guarantee stereochemical identity. Separate connectivity retrieval and explicit exact relationship classification require scientific review; do not fix by claiming all epimers must have different Morgan fingerprints. That original desired test is retained as evidence of an unsuitable identity proxy.

H4 unassigned peaks, H7 endpoint/unit/status handling and H6/H10 provenance/export disclosures remain unresolved. Formula plausibility, evidence tiers, FAIR schema, citations/licensing and controlled vocabularies remain separate curator-reviewed proposals. Presence completeness can legitimately reach100 without validation; the desired assertion expresses a terminology/policy concern, not a mandate to redefine completeness silently. Zero tolerance at documented precision needs a precise rounding policy. Static source-string checks establish only source presence/absence, not backend or browser behavior. No reported production counts independently verified here.

## Review and rollback

This PR is a sibling evidence lane to #58/#59, based on #57 as requested; do not merge independently into main or overwrite later branches. Integrate selected tests/docs after independent review and retain strict failure inventory. Rollback: close unmerged draft; if adopted on a candidate, revert this import commit only. No data rollback required. Genuine production restore #24, browser acceptance #19/#23, privacy policy #43 and scientific acceptance #18/#44 remain BLOCKED.
