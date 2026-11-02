# Local scientific asset integration

QA base: 606ba8f7decdd3767a93b64ac8a3a2896d6e8bd9. Reuses #35's reader.
This PR changes local attachment boundaries only. No data/schema migration,
production connection, private dataset inspection, deployment or paid service.

Every record-controlled local image, spectrum, specimen preview and structure in
record ZIPs is read through `read_scientific_asset`. Streamlit and Pillow receive
validated bytes, never paths for a later open. Roots are `data/structures`,
`data/spectra`, `data/specimens`; context-specific consumers restrict further.
No project/database/backups/configuration directory is an attachment root.
`get_full_file_path` remains a compatibility locator for validation only.
Trusted branding, templates and privileged backup functions are separate and
are not attachment readers. Their authorization is a separate change.

Reads pin directories with descriptor-relative O_NOFOLLOW; all symlinks and
hardlinks are rejected, including contained symlinks. Reads are bounded to
64 MiB, media signatures/decoding are checked, and images are limited to 40 million
pixels. Opaque .fid/.mnova are download-only; ZIP files are never extracted.
Uploads use the same types/limits and exclusive, symlink-free file creation;
curated files are never overwritten. No asset bytes are cached. Remote fetches use the separately validated HTTPS/redirect policy below.
Current-account URL authorization is implemented in companion #39.

Existing records and citations are unchanged. Legitimate out-of-root paths,
symlinked files, unrecognized formats, or files over the limit need private
curator review and deliberate relocation/approval; they are not silently rewritten.
A blocked registered structure is omitted from ZIP, never replaced by SMILES.
Errors do not expose filesystem paths. The existing record-link metadata is
preserved; this change prevents disclosure of unrelated file bytes, not removal
of curator-authored metadata.

Tests use synthetic files and real final app functions extracted without app
initialization. Include direct preview/download, full ZIP inspection, absolute
and relative legitimate files, traversal, symlink/hardlink/prefix escape, race
swap, configuration/database suffixes, forged media, exact/over byte limits,
changed asset freshness, and exclusive upload writes. No production secrets
or network is used. Run with Python 3.11/3.12 and pinned Streamlit dependencies.
On macOS use canonical TMPDIR=/private/tmp because /var and /tmp are symlinks;
this deliberately strict reader rejects symlink ancestors.

Rollback: close this unmerged PR. After QA integration revert the integration
commit and its helper dependency only if no consumers remain. Restoring unsafe
readers is not a safe production rollback: disable affected attachment previews
and downloads until a corrected implementation passes tests. No stored data is
changed, so no data restoration is required. Keep #22 open for independent review
and remote authorization checks; keep #14 draft for #24 and browser acceptance.

HTTPS follow-up: server fetches now require HTTPS, port 443, no userinfo and an
exact trusted hostname (configured Supabase host or fixed NIH/Google Drive hosts).
Redirects revalidate that policy before following; local/private IP literals,
file/HTTP/FTP schemes, arbitrary hosts and environment proxies are blocked.
Remote bodies are bounded and media validated. Other legitimate HTTPS references
remain browser links; no metadata or remote bytes are relocated. Public legacy
Storage URLs are signed privately or remain unavailable, with no unsigned fallback.
This narrows compatibility: unlisted external providers need deliberate review
before server-side preview/export. Signature authorization remains in companion #39.
