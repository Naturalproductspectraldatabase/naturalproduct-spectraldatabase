"""CI-only deterministic resolver for the known #39/#41 CAS guard overlap.

Never invoked on production files; only ephemeral GitHub runner checkout.
Rejects unexpected conflicts instead of selecting a whole file from one branch.
"""
from pathlib import Path
import re

path = Path("NMR_Database_Tyas_GitHub_Upload/scripts/app.py")
raw = path.read_text(encoding="utf-8")
pattern = re.compile(r"(?ms)^<<<<<<< [^\n]*\n(?P<ours>.*?)^=======\n(?P<theirs>.*?)^>>>>>>> [^\n]*\n")
matches = list(pattern.finditer(raw))
if len(matches) != 1:
    raise SystemExit("Refusing unknown merge conflict count; review required.")
block = matches[0]
left = block.group("ours")
right = block.group("theirs")
if "save_structure_query_to_compound" not in (left + right):
    raise SystemExit("Conflict is not the approved structure-save overlap.")
if "original_row=None" not in right:
    raise SystemExit("Expected #41 compare-and-swap implementation is missing.")
new = raw[:block.start()] + right + raw[block.end():]
signature = "def save_structure_query_to_compound(compound_id: int, query_text: str, *, original_row=None) -> tuple[bool, str]:\n"
if new.count(signature) != 1:
    raise SystemExit("Expected exact CAS function not present exactly once.")
permission = '    require_backend_permission("curate")\n'
start = new.index(signature) + len(signature)
if not new[start:start+250].lstrip().startswith('ensure_write_target_ready()'):
    raise SystemExit("Unexpected structure-save function start; no automatic resolution.")
new = new[:start] + permission + new[start:]
if any(marker in new for marker in ("<<<<<<< ", "\n=======\n", ">>>>>>> ")):
    raise SystemExit("Unresolved markers remain.")
if "expected_updated_at=expected" not in new:
    raise SystemExit("CAS protection missing; abort.")
if "def redact_private_gps_for_current_user(" not in new:
    raise SystemExit("GPS privacy guard missing; abort.")
if "def read_scientific_asset(" not in new:
    raise SystemExit("Asset containment from #38 missing; abort.")
path.write_text(new, encoding="utf-8")
print("Resolved one known #39/#41 conflict while retaining permission, CAS, GPS, assets.")
