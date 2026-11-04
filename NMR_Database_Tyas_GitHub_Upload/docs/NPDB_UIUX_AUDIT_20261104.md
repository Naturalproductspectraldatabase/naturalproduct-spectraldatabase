# NPDB UI/UX and frontend design audit

**Date:** 4 November 2026. **Lane:** #23 (Claude Code, UI and accessibility), coordinated through #17.
**Candidate reviewed:** draft PR #56 head `02484b64`, the top of the stack #47 → #48 → … → #55 → #56 (includes the gallery work of #7, the Home spacing work of #9 and the branding fixes of #49/#50).
**Scope of this document:** review and proposals only. It changes no application code, theme, CI, data or deployment.

**UI verdict: BLOCK** for a professional public release. Six P0 defects make core text unreadable, break the search-to-record path, or hide the scientific disclosures that other lanes just added. **The overall release gate stays BLOCKED** in any case until the real production restore (#24), browser role acceptance (#19), the location policy (#43) and the scientific validation (#44) are satisfied.

Each finding is labelled **Measured** (browser run or computed style), **Code** (read in `scripts/app.py` at `02484b64`), **Recommendation**, or **Opinion** (aesthetic judgment, open to the owner).

## 1. How the evidence was produced

| Item | Detail |
| --- | --- |
| Build | `git archive` of `02484b64`, run locally with `streamlit run scripts/app.py` |
| Runtime | Python 3.11, Streamlit 1.66.1, pandas 2.3.3, RDKit 2026.09.1: installed from the candidate's own `requirements.txt` (`runtime.txt` = 3.11) |
| Data | The repository's 5-compound CSV snapshot (`database/backups/latest_csv`). No production data, Supabase or Storage |
| Accounts | Dummy viewer and owner accounts in `NPDB_APPROVED_USERS`; no real credentials |
| Browser | Chromium (Playwright), axe-core 4.10.2 with WCAG 2.0/2.1/2.2 A and AA rules |
| Widths | 320, 768, 1280 and 1920 px |
| Live app | **Not reachable from this environment**: the network policy denies `npdb-spectraldatabase.streamlit.app`. Nothing in this audit is claimed about the deployed app |
| Local-only artefacts | The yellow "Local-only mode is active" banner and the "Deploy" toolbar button appear because the app ran without Supabase secrets; ignore them in the screenshots |

Contrast was measured two ways that agree: computed text colour composited over the page background token, and pixel sampling of the screenshots (approximate, JPEG). Raw numbers are in [`uiux-audit-20261104/measurements.json`](uiux-audit-20261104/measurements.json). The acceptance gate in section 7 reproduces every P0 and P1 check.

## 2. What already works

- The visual identity is distinctive: deep navy with a cyan-to-violet accent, a recognisable coral/spectrum logo, and spectrum and structure line art in the hero. It suits a marine natural-products database. (Opinion)
- Structures and spectra are shown on opaque white canvases, never recoloured for the dark theme (Measured; `record-1280-part4.jpg`).
- The sidebar quality line now reads "Core metadata coverage: 100% with name, class & source" instead of "% Verified" (#52).
- NMR search now explains coverage and heuristic ranking (#53), shows "Heuristic rank 87.6/100 | Matched 8/8 | Query coverage | DB coverage" per hit, and labels status "Imported".
- The ¹³C/¹H galleries have top and bottom pagination with a page jump (#7).
- At 768, 1280 and 1920 px no page overflows horizontally (Measured).

## 3. Findings by priority

### P0: must be fixed before a public release

| ID | Finding | Evidence | Location | Fix |
| --- | --- | --- | --- | --- |
| U1 | **Most interface text is unreadable.** Root cause: the app paints a dark design in CSS, but Streamlit still runs its default **light** theme. Every element the CSS does not override keeps light-theme colours: text `#31333F` on a dark page, near-white typed text on `#F0F2F6` fields | Measured: widget labels 1.49:1; captions 1.24:1; selected radio label 1.10:1; typed text in the ¹³C peak box, tolerance, page-jump and 13 Update Metadata fields **1.05:1**; axe `color-contrast` serious on Search (1), Gallery (2), New Submission (4), Update Metadata (7). Computed style `rgb(49,51,63)`, `data-stale="false"`, so this is not a rerun fade | `.streamlit/config.toml` has no `[theme]`; CSS L1157–3920 | Add a dark `[theme]` (section 4.6) to `.streamlit/config.toml`; then delete the CSS that fights it. One file change fixes most of U1, U4 and U13 |
| U2 | **"Open Record" on NMR search results does nothing.** The click reruns the script, the results disappear and the empty form returns | Measured: after clicking "Open Record #1", no record and no "Download Full Record" control. Code: `render_candidate_cards()` runs only inside `if run_13c:` (L10115, L10150), true only in the submit run; the same pattern at L10206 (¹H) and L10274 (combined) | L9727–9734, L10115–10274 | Store results in `st.session_state` on submit and render from there on every run; use `on_click=open_compound_detail, args=(id,)` |
| U3 | **No visible keyboard focus** on most controls | Measured: 39 tab stops on Home, 0 with an outline; 25 of 39 with no visible indicator (sidebar navigation, text fields, selects, Log out). The text-field ring is a 1 px shadow at 18% opacity (L2665–2670) | `focus-sidebar-nav-1280.jpg` | One global `:focus-visible` ring: 3 px solid focus token, 2 px offset, on buttons, fields (on their wrapper), radios (on their label) and the sidebar scroller |
| U4 | **The new scientific disclosures are invisible.** The #53 coverage note, the heuristic-ranking caption, spectrum captions and the generated-depiction warning are all `st.caption` text | Measured: coverage note 1.22:1, heuristic caption 1.20:1, spectrum file captions 1.17–1.24:1. The structure-provenance captions (L7049, L9405, L9556) use the same component | `search-13c-settled-1280.jpg` | Render disclosures as a notice component (`role="status"`, icon plus text, ≥ 4.5:1), not as captions. 99.8% of registered structure images are app-generated (#17, 3 Nov), so this warning must be legible on almost every record |
| U5 | **No About, Data & methods, How to cite, License or terms, Privacy, or Contact page** | Code: 0 occurrences of About, Citation, License, Privacy, Terms; "Contact" appears only as "Contact the database owner" on the login card | whole app | Add one "About & Help" page with these sections, linked from the sidebar footer and the login page. The owner decides the licence, citation, privacy and location-disclosure texts (#43) |
| U6 | **The copy still claims curation** | Code: "This access gate protects the curated NPDB workspace" (L1564), "Open curated compound dossiers" (L6816), "A unified workspace to manage curated data… high-quality spectral records" (L6862), "A read-only workspace for curated records" (L6864). Only 79 of 4,063 records carry a "curated" label, and none has curation evidence (#17) | Home, login | Neutral wording, for example "Literature-compiled natural-product records with NMR, structures and bioactivity" |

### P1: needed for a professional, usable release

| ID | Finding | Evidence | Fix |
| --- | --- | --- | --- |
| U7 | Home overflows sideways at 320 px | Measured: 29 px; the Research Workflow cards keep two columns (`home-viewer-320.jpg`) | Grid `repeat(auto-fit, minmax(min(100%, 16rem), 1fr))`; acceptance 0 px at 320/360/768 |
| U8 | Page structure is invisible to assistive technology | Measured: only Home has an `<h1>`; Search, record, gallery and curation pages have none; the 11 record section titles are `<div>`s | One `<h1>` per page named after the page; `<h2>` for record sections |
| U9 | Images lack text alternatives | Measured: axe `image-alt` critical, 3 on Home, 7 on the record page, 6 in the gallery; structure and spectrum `<img>` have empty `alt` | Structure: "Structure of <name> (computed depiction)" or "(curated drawing)"; spectrum: "<nucleus> NMR spectrum of <name>, <solvent>, <MHz>"; decorative art `alt=""` with `aria-hidden` |
| U10 | Navigation duplicates and hides pages | Measured: "Start Submission" and "New Submission" open the same page and are **both highlighted** at once (`owner-new-submission-1280.jpg`); a second "Compound Workflow" radio row repeats the sidebar; the Data Library (Bioactivity, peaks, galleries, Spectra Library, Specimens, Guide) sits in a collapsed "Additional Views" group whose label measures 1.54:1 and looks disabled; ¹H and ¹³C items are interleaved | Proposed menu in 4.5; one active state; remove the in-page workflow radio |
| U11 | Home is not search-first | Measured: Home shows a "Search Spectra" card and a separate "Start Searching →" button; there is no search field | Put the search field and mode (name or formula · structure · ¹H · ¹³C) on Home; Enter runs the search |
| U12 | The record page buries the science | Measured at 1280 px: page 8,067 px tall (7,822 at 320). The full brand hero repeats on every page; the record is chosen from one drop-down listing every compound (4,063 in production); empty fields render as cards showing "-" (Mr, SMILES, InChI, InChIKey, journal, DOI, CCDC on the sample); the citation sits at the bottom; formula shows as "C21H32ON" with no subscripts; NMR tables start with internal row IDs; δC 44.0 displays as "44"; spectrum captions are file names | Record template in 4.4 |
| U13 | Primary button label fails contrast | Measured: white "Start Searching" on the cyan-to-violet gradient ≈ 3.8:1 (normal-size text needs 4.5:1) | Darker gradient stops or a dark label (`on_accent` #06121C on #5CC8E0 = 9.7:1) |
| U14 | "Forgot password?" promises a reset that does not exist | Code: the link jumps to `#login-access-help`, above a **collapsed** "Access Guide" expander (L1558, L1568–1569) | Rename to "Need access? Contact the owner" and open that help, or remove it |

### P2: quality, performance and consistency

| ID | Finding | Evidence | Fix |
| --- | --- | --- | --- |
| U15 | No design system in the CSS | Code: 2,453 lines of inline CSS in three blocks; 47 font sizes; 42 hex colours plus 306 `rgba()` values; 186 `!important`; 21 border radii; 85 gradients; 59 shadows; 8 breakpoints (640–1340 px); 3 focus rules; no `prefers-reduced-motion`; no print styles | Tokens (4.1–4.3) in one stylesheet; retire overrides page by page |
| U16 | Heavy payload, no loading feedback | Measured locally: login → Home ≈ 947 KiB over the websocket; an idle rerun ≈ 47 KiB; rerun ≈ 1.3 s. Code: images are re-encoded to base64 and inlined on every render (hero source `background.png` 605 KB at 1,600 px); 0 `st.spinner` calls | Serve branding as static files (`server.enableStaticServing`) or cached bytes via `st.image`; `st.spinner` around search, record load and export; budgets in section 7 |
| U17 | Error messages are inconsistent | Code: raw exception text shown to users (L6969 `Could not read the import file: {exc}`); one Indonesian message in an English interface (L4472) | One message catalogue: what happened, what was kept, what to do next; technical detail only in the owner's log |
| U18 | Curation workflows are hard to use safely | Measured: Update Metadata is one long two-column form with every value unreadable (U1); required fields are not marked; "Delete Record" sits in the main sidebar next to everyday actions | Edit from the record page; sectioned forms with required markers and an unsaved-changes notice; deletion in a record "danger zone" with typed confirmation |
| U19 | Streamlit's default red accent leaks through | Measured: slider, selected radio dot and expander focus ring are `#FF4B4B` | `primaryColor` in the theme (4.6) |
| U20 | Cross-lane note (security, Codex): the read-only banner names the owner's login, and the Access Guide reveals the login pattern | Measured (redacted in screenshots) | Generic wording: "Editing is limited to the database owner" |

### P3: polish and brand

| ID | Finding | Recommendation |
| --- | --- | --- |
| U21 | The header phrase **"Explore. Analyze. Discover."** is legible (11.4:1) but generic: it says nothing about what NPDB contains and could title any data product | Keep it as a short brand line on the login screen if the owner likes it. On Home, use a descriptive subtitle such as "¹H and ¹³C NMR, structures and bioactivity of marine natural products" plus the data version. (Opinion; owner decides) |
| U22 | The brand appears three times on one screen: sidebar logo and name, the hero title, and the eyebrow | Brand once (sidebar); pages start with their own title (4.4) |
| U23 | Login inputs are two-tone (white icon cell beside a dark field) | One field surface (the theme fixes most of it) |
| U24 | Print and reduced-motion support are absent | Print stylesheet for record pages (white background, sidebar hidden, figures unsplit); honour `prefers-reduced-motion` |

## 4. Proposed design system

A tested implementation of this system already exists on branch `feat/npdb-design-system-20261103` (head `615bfcf`): tokens with a WCAG contrast test, display-only scientific notation, components and a browser audit. It is delivered as a bundle because this lane cannot push. The values below are taken from it.

### 4.1 Colour tokens (dark theme)

| Token | Value | Contrast | Use |
| --- | --- | --- | --- |
| `bg` | #0B1220 | — | page |
| `surface` / `surface_raised` | #111A2B / #172338 | — | cards, sidebar, tables |
| `input_bg` | #0E1726 | — | fields |
| `text` | #F2F5FA | 17.1:1 on bg; 16.4:1 on input_bg | body text, typed text |
| `text_muted` | #B4BFCE | 10.1:1 on bg | labels, captions, units |
| `border` | #5B6A82 | ≥ 3:1 | field and card outlines |
| `accent` / `on_accent` | #5CC8E0 / #06121C | 9.7:1 | primary actions |
| `focus` | #FFD166 | ≥ 3:1 on all surfaces | keyboard focus ring |
| `success`, `warning`, `danger`, `info` | #6FD69C, #F2C66D, #FF8A7A, #8AB4FF | ≥ 4.5:1 on surface | notices and badges, always with an icon and text |
| `structure_canvas` | #FFFFFF | — | structures and spectra, never filtered |

A light theme with the same token names is defined for projection and print.

### 4.2 Type and spacing

- Type scale (rem): 0.8125 caption · 0.9375 body · 1.0625 lead · 1.1875 h3 · 1.4375 h2 · 1.8125 h1. Six sizes replace the current 47.
- Spacing scale: 4, 8, 12, 16, 24, 32, 48, 64 px. Radii: 4, 8, 12 px. Breakpoints: 640 and 1024 px.
- Tabular figures for all numbers; units in column headers (δ<sub>H</sub> (ppm), *J* (Hz)); reported precision kept.

### 4.3 Components

Page header (one h1) · notice (status, warning, error, with roles) · status and evidence badges ("Not curated" by default) · key–value list that hides empty fields · structure figure (curated / computed / failed / missing states) · NMR table · NMR dataset card ("Not reported" for missing conditions) · gallery card with top and bottom pagination · search result card · data-coverage panel.

### 4.4 Record page template

1. **Header:** name; formula with subscripts and Hill order hint; status badge; evidence level; the citation (authors, year, journal, DOI link) directly under the name.
2. **Structure and identifiers:** the structure with a visible provenance label ("Computed depiction from SMILES — not curator-verified" or "Curated drawing"); SMILES, InChI and InChIKey with copy buttons; only filled fields shown.
3. **NMR datasets:** one card per nucleus + solvent + frequency, then its table (position, δ, multiplicity, *J*, integral), with reported precision and without internal IDs.
4. **Spectra:** thumbnails with descriptive captions (nucleus, experiment, solvent, MHz) that open full size; raw-file downloads labelled by format.
5. **Bioactivity:** with unit status ("unit not recorded" where missing).
6. **Source and specimen:** organism, collection site at the precision the owner approves (#43).
7. **References and provenance, record history.**

Replace the all-records drop-down with search-as-you-type and links from search results, so each record has its own address.

### 4.5 Navigation

Home (search-first) · Search · Compounds · Spectra (¹H and ¹³C gallery, one view with a nucleus switch) · Bioactivity · Specimens · Curation (editors and owner: new submission, batch import, review queue) · About & Help. One active state. "Delete" moves to the record page.

### 4.6 Streamlit theme (shared file: reserve on #17 first)

```toml
[theme]
base = "dark"
primaryColor = "#5CC8E0"
backgroundColor = "#0B1220"
secondaryBackgroundColor = "#111A2B"
textColor = "#F2F5FA"
font = "sans serif"

[client]
toolbarMode = "viewer"
```

## 5. Ordered improvement plan

| Phase | Work | Fixes | Needs | Rollback |
| --- | --- | --- | --- | --- |
| 0 | Theme block in `.streamlit/config.toml` | most of U1, U4, U13, U19 | reserve the file on #17; no `app.py` edit | revert one file |
| 1 | P0 code fixes: search results in session state; global focus ring; disclosures as notices; neutral copy; About & Help page | U2, U3, U4, U5, U6 | `app.py` slot after the current Codex claim (#17, 5 Nov); owner texts for licence, citation, privacy | revert the PR; no data change |
| 2 | Structure and navigation: one h1 per page, alt text, menu, search-first Home, 320 px reflow | U7–U11, U14 | `app.py` | revert the PR |
| 3 | Record template and gallery cards; design-system stylesheet behind the `NPDB_DESIGN_SYSTEM` flag | U12, U15, U22 | `app.py`; design-system bundle (`615bfcf`) | set the flag off |
| 4 | Performance and curation UX: static branding, spinners, message catalogue, sectioned edit forms, delete confirmation | U16–U18, U23, U24 | `app.py` | revert per PR |

## 6. Implementation list for Codex (after ownership coordination on #17)

Line numbers refer to `scripts/app.py` at `02484b64`.

1. **Search results persist (U2):** on submit, store `filtered_results` and the query in `st.session_state["nmr_results_<mode>"]`; render the cards from session state outside `if run_13c:` (L10115–10150), and likewise for ¹H (L10206) and combined (L10274). Give the "Open Record" buttons (L9728) `on_click=open_compound_detail, args=(item["compound_id"],)`. Add a "Clear results" button. Test: click "Open Record #1" → record opens; "Back to results" restores the list.
2. **Theme (U1, U13, U19):** add the section 4.6 block to `.streamlit/config.toml`; then remove overrides that set light field backgrounds and dark label colours, and re-run the acceptance gate.
3. **Focus ring (U3):** replace L2665–2670 with a `:focus-visible` rule (3 px solid #FFD166, 2 px offset) on `button`, `[role="radio"]` labels, `summary`, `a`, and `div:has(> input:focus-visible)` / `div:has(> textarea:focus-visible)`.
4. **Disclosures (U4):** replace the `st.caption` calls at L7049, L9405, L9556 and the #53 coverage and heuristic captions with a notice component (icon plus text, ≥ 4.5:1, `role="status"`).
5. **Copy (U6):** change the strings at L1564, L6816, L6862 and L6864 to neutral wording.
6. **About & Help (U5):** one page with About, Data & methods (sources, what "imported" means, NMR origin not recorded), How to cite, License or terms, Privacy and location policy, Contact, and data version; links in the sidebar footer and on the login card. Texts come from the owner.
7. **Headings (U8):** one `<h1>` per page from the page name; record section titles as `<h2>` (the section header helper).
8. **Alt text (U9):** add `alt` to the hero, sidebar art and gallery images; descriptive `alt` for structures and spectra (see U9).
9. **Navigation (U10):** remove the duplicate "Start Submission" (L371); make the Data Library a visible group; drop the in-page "Compound Workflow" radio; group ¹H and ¹³C items.
10. **Home (U7, U11):** replace the search card and button with a search field and a mode selector; make the workflow cards a responsive grid.
11. **Login (U14):** rename "Forgot password?" (L1558) and open the Access Guide when it is followed.
12. **Messages (U17):** replace L6969's raw exception with a fixed message and log the detail; translate L4472 to English.

## 7. Acceptance criteria and screenshot checks

`tests/ui/npdb_uiux_acceptance.js` runs these checks against a local build with dummy accounts. **On `02484b64` it passes 16 of 46**; the target is 46 of 46.

| Check | Threshold | Pages and widths | Baseline on `02484b64` |
| --- | --- | --- | --- |
| Widget labels, captions, radio labels, h3 | ≥ 4.5:1 | Home, Search ¹³C, record, gallery, New Submission, Update Metadata at 1280 | fail: 1.24–1.49:1 (Update Metadata passes) |
| Typed text in fields | ≥ 4.5:1 | same | fail on Search, gallery, Update Metadata: 1.05:1 |
| axe-core serious or critical | 0 | same | fail on all six |
| Exactly one `<h1>` | 1 | same | Home only |
| Visible focus on every tab stop | 100% | Home, 40 stops | 25 of 39 without |
| NMR "Open Record" opens the record | record visible | Search ¹³C | fail |
| Trust pages reachable | About, How to cite, License, Privacy, Contact visible from sidebar or footer | all | fail (none) |
| One active navigation item | 1 | owner, New Submission | fail: 2 |
| No unsupported claims ("curated records", "% Verified", "high-quality spectral records") | 0 | all | fail on Home |
| Horizontal overflow | ≤ 1 px | Home at 320, 768; all pages at 1280 | fail at 320 (29 px) |

Screenshot set for the integration PR (before and after, same data and accounts): login 320/1280; Home 320/768/1280/1920; Search ¹³C with results; a record page (header, structure, NMR tables, spectra); ¹³C gallery; New Submission step 1; Update Metadata; keyboard focus on a sidebar item, a text field and the primary button; print preview of a record.

Additional budgets (Recommendation, to be measured in the integration PR): login → Home websocket payload ≤ 300 KiB; idle rerun ≤ 15 KiB; Home interactive ≤ 2.5 s locally; every search shows a spinner within 300 ms.

## 8. Evidence in this folder

`uiux-audit-20261104/`: `home-viewer-1280.jpg`, `home-viewer-320.jpg`, `search-13c-settled-1280.jpg`, `search-13c-candidates-1280.jpg`, `focus-sidebar-nav-1280.jpg`, `record-1280-part1.jpg`, `record-1280-part2.jpg`, `record-1280-part4.jpg`, `record-320-part1.jpg`, `gallery-13c-1280.jpg`, `owner-new-submission-1280.jpg`, `owner-update-metadata-1280.jpg`, `login-1280.jpg`, and `measurements.json`. The read-only banner is redacted in two record screenshots because it names the owner's account. All other content comes from the repository's sample snapshot.

## 9. Not verified here

- The deployed app (network policy), Supabase mode, signed Storage previews and real-scale pagination with 4,063 records.
- Screen-reader output (NVDA, VoiceOver) and real mobile devices; checks used Chromium emulation only.
- The visual result of any proposed change: no change was implemented in `app.py`, so no "after" screenshots of the real app exist for this audit. The design-system preview on `615bfcf` has its own audited screenshots.
