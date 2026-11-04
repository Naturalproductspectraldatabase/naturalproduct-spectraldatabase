# UI audit handoff import review

Docs/test-only branch stacked on #59 exact272d502d6812f62bbb20acd2cf3106b203c0ea1c, preserving #58/#57. No app.py, theme, production config or records changed.

## Evidence validation

ZIP SHA25699e11c79a021eb09513333952c27ace4891dd2a3f070486f523f0a344c88eb0e; all six SHA256SUMS entries verified. Archive bounded below10MB uncompressed, no duplicate/absolute/traversal names or symbolic links. Bundle SHA25676ff9280978346283fa7aad5c5de14ac5fabdc8325c6b01608fb47f6883f53f2; Git verify passed with required606ba8f7decdd3767a93b64ac8a3a2896d6e8bd9. One ref48dee6e7edac7fcdd0df547b4dd4894c7ac2d37a,16 added docs/test/image files. No branch merge or patch application performed; APPLY.md targets old QA and was treated as untrusted historical instructions.

Selected report SHA25646375c159d0979489231bd1f9268567ad3cfed75400f0656e63599fc384a43b1 and measurements SHA25672ad4c51765177d8120724cc9b91f2381e0f5c187068037d0189e27235a86b04 are preserved verbatim. No credential/private-key patterns detected in selected text. Report findings describe #56, not current #59 and not deployed production. The author used repository CSV data; synthetic provenance has not been independently established.

All13 JPEG files decode and have no EXIF fields. Visual inspection found collection locality, sample-code/depth and scientific-record content. ALL screenshots are deliberately withheld from GitHub import pending #43 disclosure/provenance review; source report screenshot references therefore do not resolve. No image modified or scientific asset overwritten. They remain local owner-provided evidence, not CI fixtures. No bundle, patch, local path or backup uploaded.

Original browser script SHA256868352efe4dde5ac59eb39557bbbdf2a0253cbfdc240aaf1a64657216b5e258a inspected. Adapted copy adds numeric unprivileged loopback-port validation, synthetic_-prefixed dummy credentials, blocks non-loopback HTTP/WebSocket requests and service workers. It navigates curation pages but does not submit writes. Launch ONLY an isolated temporary synthetic app with no secrets, cloud configuration or real files. Browser request isolation does not isolate the backend: operator must enforce that launch boundary. It requires local Playwright and local axe; it downloads neither. Default query is synthetic10,20,30; fixture must contain matching peaks. Do not use repository CSV snapshots or real accounts.

## Validation limits and remaining work

Node syntax check passes. Browser script NOT executed by importer; author16/46 claim is unverified older-candidate evidence. Contrast computation approximates backgrounds/opacity and focus rings; axe/manual visual and actual keyboard/screenreader checks remain necessary. The script covers viewer/owner UI navigation, not backend role enforcement, editor authorization or full browser acceptance. Information-architecture checks only inspect sidebar text despite their broader label. Known failures remain failures; importing this script is not fixing accessibility.

#59 latest already implements approved separate display aliases Marine Alga→Marine alga and Alkaloids→Alkaloid in options/filtering/aggregation, preserving raw values, plus native Account Recovery dialog and unset contact config. Its independent review concerned earlier f38055e. Recheck supported CI and independent browser focus/contrast before acceptance; do not duplicate already corrected source.

NMR Open Record loss on rerun remains a high-priority reproduction target for a separate narrowly scoped fix. Dark/light theme, visible focus, scientific-caption contrast,320px overflow, semantic headings/alt text require a separate coordinated UI PR and measured before/after browser evidence. Citation/license/contact content requires owner approval; never invent destinations or licensing claims.

Rollback: close unmerged draft, or revert import commit on a candidate. No data/config rollback needed. Independent review required. Restore #24 and release BLOCKED; no production/main/paid services/deployment changes.
