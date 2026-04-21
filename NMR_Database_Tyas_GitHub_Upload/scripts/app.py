import hmac
import io
import json
import mimetypes
import os
import re
import sqlite3
import ssl
import sys
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path
from urllib.parse import quote, urlencode, urlparse

import pandas as pd
import streamlit as st

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

try:
    from PIL import Image, ImageOps
except Exception:
    Image = None
    ImageOps = None

streamlit_ketchersa = None
st_ketcher = None
KETCHER_STATUS = "local Ketcher unavailable"

try:
    from streamlit_ketchersa import streamlit_ketchersa as _local_streamlit_ketchersa

    streamlit_ketchersa = _local_streamlit_ketchersa
    KETCHER_STATUS = "local streamlit_ketchersa loaded"
except Exception:
    streamlit_ketchersa = None

try:
    from streamlit_ketcher import st_ketcher as _local_st_ketcher

    st_ketcher = _local_st_ketcher
    if streamlit_ketchersa is None:
        KETCHER_STATUS = "local streamlit_ketcher fallback loaded"
except Exception:
    st_ketcher = None

try:
    from rdkit import Chem, DataStructs
    from rdkit.Chem import AllChem
except Exception:
    Chem = None
    DataStructs = None
    AllChem = None

try:
    from rdkit.Chem import Draw
except Exception:
    Draw = None

try:
    from openpyxl.styles import Alignment, Font, PatternFill
except Exception:
    Alignment = None
    Font = None
    PatternFill = None

# =========================
# Basic configuration
# =========================
def resolve_project_dir(script_dir: Path) -> Path:
    candidates = [script_dir, script_dir.parent]
    for candidate in candidates:
        if (candidate / "data").exists() and (candidate / "database").exists():
            return candidate
    return script_dir


PROJECT_DIR = resolve_project_dir(SCRIPT_DIR)
DATABASE_DIR = PROJECT_DIR / "database"
DATA_DIR = PROJECT_DIR / "data"
BRANDING_DIR = DATA_DIR / "branding"
STRUCTURES_DIR = DATA_DIR / "structures"
SPECTRA_DIR = DATA_DIR / "spectra"
TEMPLATES_DIR = DATA_DIR / "templates"
SUBMISSIONS_DIR = DATA_DIR / "submissions"
SUBMISSIONS_INBOX_DIR = SUBMISSIONS_DIR / "inbox"
SUBMISSIONS_REVIEWED_DIR = SUBMISSIONS_DIR / "reviewed"
SUBMISSIONS_APPROVED_DIR = SUBMISSIONS_DIR / "approved"
EXPORTS_DIR = DATA_DIR / "exports"
DOCS_DIR = DATA_DIR / "docs"
BACKUPS_DIR = DATABASE_DIR / "backups"
DB_PATH = PROJECT_DIR / "database" / "nmr.db"

MAX_PAGE_ICON_BYTES = 5 * 1024 * 1024
OWNER_CREDIT = "© Trianda Ayuning Tyas_project"
OWNER_EDITOR_USERNAME = "npdb_tyas"


def pick_branding_asset(*filenames: str) -> Path:
    for filename in filenames:
        candidate = BRANDING_DIR / filename
        if candidate.exists():
            return candidate
    return BRANDING_DIR / filenames[0]


FAVICON_PATH = pick_branding_asset(
    "coral_favicon1.png",
    "Coral_favicon.png",
    "NP_favicon_tab.png",
    "favicon_tab.png",
    "NP_favicon2.png",
    "favicon_circle.png",
    "favicon2.png",
    "favicon.png",
)
SIDEBAR_LOGO_PATH = pick_branding_asset(
    "coral_favicon1.png",
    "favicon_circle.png",
    "favicon2.png",
    "favicon.png",
    "logo_header_web.png",
)
HEADER_LOGO_PATH = pick_branding_asset("logo_header_web.png", "header1_web.png", "logo_header.png", "header1.png", "header.png")

DEFAULT_CLASS_OPTIONS = [
    "Alkaloid",
    "Peptide",
    "Polyketide",
    "Steroid",
    "Terpenoid",
    "Phenolic",
    "Flavonoid",
    "Marine Natural Product",
]
DEFAULT_SOURCE_OPTIONS = [
    "Sponge",
    "Soft Coral",
    "Hard Coral",
    "Tunicate",
    "Cyanobacteria",
    "Bacteria",
    "Coral",
    "Seaweed",
    "Microorganism",
    "Plant",
    "Fungus",
]
DEFAULT_DATA_SOURCE_OPTIONS = ["Experimental", "Literature", "In-house Archive"]
DEFAULT_SOLVENT_OPTIONS = ["CDCl3", "DMSO-d6", "CD3OD", "Acetone-d6", "Pyridine-d5"]
DEFAULT_SPECTRUM_TYPES = [
    "1H",
    "13C",
    "1H Raw Data",
    "13C Raw Data",
    "JCAMP-DX",
    "MNova",
    "COSY",
    "HSQC",
    "HMBC",
    "NOESY",
    "FTIR",
    "UV",
    "HRMS",
    "Supporting Data",
]
DEFAULT_BIOACTIVITY_CATEGORIES = [
    "Cytotoxicity",
    "Antibacterial",
    "Antifungal",
    "Antiviral",
    "Anti-inflammatory",
    "Antiparasitic",
    "Enzyme Inhibition",
    "Receptor Binding",
    "Antioxidant",
    "Ecological Activity",
]
DEFAULT_TARGET_CATEGORIES = [
    "Cell Line",
    "Bacterium",
    "Fungus",
    "Virus",
    "Parasite",
    "Enzyme",
    "Receptor",
    "In Vivo",
    "General",
]
DEFAULT_POTENCY_TYPES = [
    "IC50",
    "EC50",
    "MIC",
    "GI50",
    "LC50",
    "ED50",
    "% Inhibition",
    "Zone of Inhibition",
]
DEFAULT_POTENCY_UNITS = [
    "uM",
    "nM",
    "ug/mL",
    "mg/mL",
    "%",
    "mm",
]

NAV_OPTIONS = [
    "Dashboard",
    "Search & Match",
    "Compound Workspace",
    "Bioactivity",
    "1H Peaks",
    "13C Peaks",
    "Spectra Library",
    "Guide",
]

LEGACY_NAV_MAP = {
    "Overview": "Dashboard",
    "Search": "Search & Match",
    "Compound": "Compound Workspace",
    "1H NMR": "1H Peaks",
    "13C NMR": "13C Peaks",
    "Spectra": "Spectra Library",
}

COMPOUND_PAGE_OPTIONS = [
    "Browse Record",
    "New Submission",
    "Batch Import",
    "Update Metadata",
    "Delete Record",
]

LEGACY_COMPOUND_PAGE_MAP = {
    "Compound Detail": "Browse Record",
    "Record Detail": "Browse Record",
    "Add Compound": "New Submission",
    "Add Record": "New Submission",
    "Edit Compound": "Update Metadata",
    "Metadata Editor": "Update Metadata",
    "Delete Compound": "Delete Record",
}

NAV_SECTION_COPY = {
    "Dashboard": {
        "title": "Dashboard",
        "summary": "Overview and backup.",
    },
    "Search & Match": {
        "title": "Search & Match",
        "summary": "Keyword lookup and NMR matching.",
    },
    "Compound Workspace": {
        "title": "Compound Workspace",
        "summary": "Browse, submit, import, and revise records.",
    },
    "Bioactivity": {
        "title": "Bioactivity",
        "summary": "Track assay outcomes, targets, potency values, and literature-reported activity profiles.",
    },
    "1H Peaks": {
        "title": "1H Peaks",
        "summary": "Manage proton peak assignments.",
    },
    "13C Peaks": {
        "title": "13C Peaks",
        "summary": "Manage carbon shift assignments.",
    },
    "Spectra Library": {
        "title": "Spectra Library",
        "summary": "Manage spectra previews, files, and raw-data links.",
    },
    "Guide": {
        "title": "Guide",
        "summary": "Usage guide, submission rules, storage, and access notes.",
    },
}

COMPOUND_IMPORT_COLUMNS = [
    "trivial_name",
    "iupac_name",
    "molecular_formula",
    "molecular_weight",
    "smiles",
    "inchi",
    "inchikey",
    "compound_class",
    "compound_subclass",
    "source_category",
    "source_organism",
    "source_material",
    "sample_code",
    "collection_location",
    "gps_coordinates",
    "depth_m",
    "uv_data",
    "ftir_data",
    "cd_data",
    "optical_rotation",
    "melting_point",
    "crystallization_method",
    "structure_image_path",
    "journal_name",
    "article_title",
    "publication_year",
    "volume",
    "issue",
    "pages",
    "doi",
    "ccdc_number",
    "hrms_data",
    "data_source",
    "note",
]

PROTON_IMPORT_COLUMNS = [
    "compound_id",
    "compound_name",
    "delta_ppm",
    "multiplicity",
    "j_value",
    "proton_count",
    "assignment",
    "solvent",
    "instrument_mhz",
    "note",
]

CARBON_IMPORT_COLUMNS = [
    "compound_id",
    "compound_name",
    "delta_ppm",
    "carbon_type",
    "assignment",
    "solvent",
    "instrument_mhz",
    "note",
]

SPECTRA_IMPORT_COLUMNS = [
    "compound_id",
    "compound_name",
    "spectrum_type",
    "file_path",
    "note",
]

if FAVICON_PATH.exists() and FAVICON_PATH.stat().st_size <= MAX_PAGE_ICON_BYTES:
    st.set_page_config(
        page_title="Natural Products Spectral Database",
        page_icon=str(FAVICON_PATH),
        layout="wide"
    )
else:
    st.set_page_config(
        page_title="Natural Products Spectral Database",
        page_icon="🧬",
        layout="wide"
    )


def get_secret_setting(*keys: str) -> str:
    for key in keys:
        value = os.environ.get(key)
        if value is not None and str(value).strip():
            return str(value).strip()
        try:
            secret_value = st.secrets.get(key)
        except Exception:
            secret_value = None
        if secret_value is not None and str(secret_value).strip():
            return str(secret_value).strip()
    return ""


def get_secret_object(*keys: str):
    for key in keys:
        value = os.environ.get(key)
        if value is not None and str(value).strip():
            try:
                return json.loads(str(value))
            except json.JSONDecodeError:
                continue
        try:
            secret_value = st.secrets.get(key)
        except Exception:
            secret_value = None
        if secret_value:
            return secret_value
    return None


def load_approved_users() -> list[dict[str, str]]:
    raw_users = get_secret_object("NPDB_APPROVED_USERS", "approved_users")
    if isinstance(raw_users, dict):
        iterable = [{"username": username, "password": password} for username, password in raw_users.items()]
    elif isinstance(raw_users, list):
        iterable = raw_users
    else:
        iterable = []

    users = []
    for item in iterable:
        if not isinstance(item, dict):
            continue
        username = str(item.get("username", "")).strip()
        password = str(item.get("password", "")).strip()
        role = str(item.get("role", "viewer")).strip() or "viewer"
        if username and password:
            users.append({"username": username, "password": password, "role": role})
    return users


def load_approved_names() -> list[str]:
    raw_names = get_secret_object("NPDB_APPROVED_NAMES", "approved_names")
    if not isinstance(raw_names, list):
        return []
    names = []
    for item in raw_names:
        text = str(item).strip() if item is not None else ""
        if text:
            names.append(text)
    return names


def normalize_login_slug(value: str) -> str:
    text = str(value).strip().lower() if value is not None else ""
    return re.sub(r"[^a-z0-9]+", "", text)


def is_access_gate_enabled() -> bool:
    return bool(
        get_secret_setting("NPDB_ACCESS_PASSWORD", "access_password")
        or get_secret_setting("NPDB_APPROVED_PASSWORD", "approved_password")
        or load_approved_users()
        or load_approved_names()
    )


def verify_access_gate():
    if not is_access_gate_enabled():
        return

    if st.session_state.get("npdb_authenticated"):
        return

    expected_username = get_secret_setting("NPDB_ACCESS_USERNAME", "access_username")
    expected_password = get_secret_setting("NPDB_ACCESS_PASSWORD", "access_password")
    approved_password = get_secret_setting("NPDB_APPROVED_PASSWORD", "approved_password")
    approved_users = load_approved_users()
    approved_names = load_approved_names()

    st.markdown(
        """
        <style>
        .auth-wrap {
            max-width: 560px;
            margin: 5rem auto 0 auto;
            padding: 1.35rem;
            border-radius: 28px;
            background: linear-gradient(180deg, rgba(255,255,255,0.04), rgba(255,255,255,0.02));
            border: 1px solid rgba(255,255,255,0.08);
            box-shadow: 0 18px 44px rgba(0,0,0,0.24);
        }
        .auth-title {
            color: #F5F8FD;
            font-size: 1.7rem;
            font-weight: 780;
            letter-spacing: -0.02em;
            margin-bottom: 0.25rem;
        }
        .auth-subtitle {
            color: #AEB8C6;
            line-height: 1.6;
            margin-bottom: 1rem;
        }
        </style>
        <div class="auth-wrap">
            <div class="auth-title">Protected Database</div>
            <div class="auth-subtitle">
                This workspace is configured with an access gate. Enter an approved username and password to continue.
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    with st.form("npdb_access_gate"):
        username = st.text_input("Username", value="")
        password = st.text_input("Password", value="", type="password")
        submitted = st.form_submit_button("Open Database", use_container_width=True)

    if submitted:
        authenticated = False
        matched_role = "viewer"

        if approved_users:
            for user in approved_users:
                username_ok = hmac.compare_digest(username.strip(), user["username"])
                password_ok = hmac.compare_digest(password, user["password"])
                if username_ok and password_ok:
                    authenticated = True
                    matched_role = user.get("role", "viewer")
                    break
        elif approved_names and approved_password:
            submitted_username = str(username).strip() if username is not None else ""
            if submitted_username.lower().startswith("npdb_"):
                submitted_name = submitted_username[5:]
                submitted_slug = normalize_login_slug(submitted_name)
                allowed_slugs = {normalize_login_slug(name) for name in approved_names}
                if submitted_slug in allowed_slugs and hmac.compare_digest(password, approved_password):
                    authenticated = True
                    matched_role = "approved-viewer"
        else:
            username_ok = True if not expected_username else hmac.compare_digest(username.strip(), expected_username)
            password_ok = hmac.compare_digest(password, expected_password)
            authenticated = username_ok and password_ok

        if authenticated:
            st.session_state["npdb_authenticated"] = True
            st.session_state["npdb_username"] = username.strip()
            st.session_state["npdb_role"] = matched_role
            st.rerun()
        st.error("Access denied. Please check the approved credentials.")

    st.stop()


verify_access_gate()


def is_owner_editor() -> bool:
    current_username = normalize_login_slug(st.session_state.get("npdb_username", ""))
    return current_username == normalize_login_slug(OWNER_EDITOR_USERNAME)


def can_edit_database() -> bool:
    return is_owner_editor()


def render_read_only_notice(feature_label: str):
    st.info(
        f"Read-only access. Only `{OWNER_EDITOR_USERNAME}` can {feature_label}. "
        "Other approved users can still browse records, search structures, and review spectra."
    )


def clear_structure_search_state():
    st.session_state["structure_search_results"] = []
    st.session_state["structure_search_error"] = ""
    st.session_state["structure_search_mode_label"] = ""
    st.session_state["structure_search_attempted"] = False

# =========================
# Session state defaults
# =========================
if "nav_section" not in st.session_state:
    st.session_state["nav_section"] = "Dashboard"
elif st.session_state["nav_section"] in LEGACY_NAV_MAP:
    st.session_state["nav_section"] = LEGACY_NAV_MAP[st.session_state["nav_section"]]

if "selected_compound_id" not in st.session_state:
    st.session_state["selected_compound_id"] = None

if "compound_page" not in st.session_state:
    st.session_state["compound_page"] = "Browse Record"
elif st.session_state["compound_page"] in LEGACY_COMPOUND_PAGE_MAP:
    st.session_state["compound_page"] = LEGACY_COMPOUND_PAGE_MAP[st.session_state["compound_page"]]

if "compound_wizard_step" not in st.session_state:
    st.session_state["compound_wizard_step"] = 1

# Pending widget-state sync helpers.
# These avoid Streamlit errors when navigation is changed from buttons
# after a radio widget has already been instantiated in the same run.
if "_pending_main_section_radio" in st.session_state:
    st.session_state["main_section_radio"] = st.session_state.pop("_pending_main_section_radio")
elif "main_section_radio" not in st.session_state:
    st.session_state["main_section_radio"] = st.session_state["nav_section"]

if "_pending_compound_page_radio" in st.session_state:
    st.session_state["compound_page_radio"] = st.session_state.pop("_pending_compound_page_radio")
elif "compound_page_radio" not in st.session_state:
    st.session_state["compound_page_radio"] = st.session_state["compound_page"]

# =========================
# Navigation helpers
# =========================
def set_main_nav(section: str):
    st.session_state["nav_section"] = section
    st.session_state["_pending_main_section_radio"] = section

def set_compound_page(page_name: str):
    st.session_state["compound_page"] = page_name
    st.session_state["_pending_compound_page_radio"] = page_name

def open_compound_detail(compound_id: int):
    st.session_state["selected_compound_id"] = int(compound_id)
    set_main_nav("Compound Workspace")
    set_compound_page("Browse Record")

def open_compound_editor(compound_id: int):
    st.session_state["selected_compound_id"] = int(compound_id)
    set_main_nav("Compound Workspace")
    set_compound_page("Update Metadata")

# =========================
# Custom styling
# =========================
st.markdown("""
<style>
:root {
    --bg-soft: rgba(255,255,255,0.028);
    --bg-soft-2: rgba(255,255,255,0.05);
    --bg-panel: rgba(12, 24, 40, 0.74);
    --bg-panel-strong: rgba(14, 27, 45, 0.9);
    --border-soft: rgba(255,255,255,0.10);
    --text-soft: #AEB8C6;
    --text-main: #F5F8FD;
    --text-strong: #FFFFFF;
    --accent-cyan: #61D8ED;
    --accent-blue: #4C8EFF;
    --accent-purple: #9C63F1;
    --accent-green: #7EF0C2;
    --accent-coral: #FF7F6D;
    --accent-gold: #F2C66D;
    --shadow-soft: 0 18px 44px rgba(0,0,0,0.22);
    --shadow-deep: 0 24px 60px rgba(0,0,0,0.34);
    --glow-soft: 0 0 0 1px rgba(255,255,255,0.04), 0 10px 30px rgba(97,216,237,0.05);
    --radius-card: 22px;
    --radius-pill: 999px;
}

[data-testid="stAppViewContainer"] {
    background:
        radial-gradient(circle at 14% 16%, rgba(97, 216, 237, 0.11), transparent 28%),
        radial-gradient(circle at 84% 12%, rgba(156, 99, 241, 0.14), transparent 30%),
        radial-gradient(circle at 62% 82%, rgba(255, 127, 109, 0.07), transparent 24%),
        linear-gradient(180deg, #06101c 0%, #081321 40%, #07111b 100%);
}

.block-container {
    padding-top: 1.2rem;
    padding-bottom: 6.75rem;
    max-width: 1520px;
}

[data-testid="stSidebar"] {
    border-right: 1px solid rgba(255,255,255,0.06);
    background:
        linear-gradient(180deg, rgba(8, 17, 30, 0.96), rgba(8, 14, 24, 0.98)) !important;
}

[data-testid="stSidebar"] .block-container {
    padding-top: 1.35rem;
}

.sidebar-note {
    border-radius: 20px;
    padding: 0.95rem 1rem;
    background: linear-gradient(180deg, rgba(255,255,255,0.04), rgba(255,255,255,0.018));
    border: 1px solid rgba(255,255,255,0.09);
    color: var(--text-soft);
    font-size: 0.93rem;
    line-height: 1.5;
    box-shadow: var(--glow-soft);
}

.sidebar-logo-shell {
    border-radius: 24px;
    padding: 0.7rem;
    margin-bottom: 0.9rem;
    background: linear-gradient(180deg, rgba(255,255,255,0.05), rgba(255,255,255,0.018));
    border: 1px solid rgba(255,255,255,0.08);
    box-shadow: var(--shadow-soft);
}

.sidebar-brand {
    border-radius: 22px;
    padding: 1rem 1rem 1rem 1rem;
    margin-bottom: 1rem;
    background: linear-gradient(180deg, rgba(255,255,255,0.045), rgba(255,255,255,0.02));
    border: 1px solid rgba(255,255,255,0.08);
    box-shadow: var(--shadow-soft);
}

.sidebar-brand-title {
    color: var(--text-main);
    font-size: 1.05rem;
    font-weight: 760;
    letter-spacing: -0.02em;
    margin-top: 0.15rem;
}

.sidebar-brand-subtitle {
    color: var(--text-soft);
    font-size: 0.89rem;
    line-height: 1.5;
    margin-top: 0.25rem;
}

.sidebar-stats {
    display: grid;
    grid-template-columns: repeat(2, minmax(0, 1fr));
    gap: 0.6rem;
    margin-bottom: 1rem;
}

.sidebar-stat {
    border-radius: 16px;
    padding: 0.75rem 0.8rem;
    background: linear-gradient(180deg, rgba(255,255,255,0.036), rgba(255,255,255,0.018));
    border: 1px solid rgba(255,255,255,0.08);
    box-shadow: inset 0 1px 0 rgba(255,255,255,0.04);
}

.sidebar-stat-value {
    color: var(--text-main);
    font-size: 1.15rem;
    font-weight: 760;
    line-height: 1.1;
}

.sidebar-stat-label {
    color: var(--text-soft);
    font-size: 0.8rem;
    margin-top: 0.18rem;
}

.selector-card {
    border-radius: 20px;
    padding: 1rem 1.05rem;
    margin-bottom: 1rem;
    background: linear-gradient(180deg, rgba(255,255,255,0.04), rgba(255,255,255,0.018));
    border: 1px solid rgba(255,255,255,0.08);
    box-shadow: var(--glow-soft);
}

.selector-title {
    color: var(--text-main);
    font-size: 0.98rem;
    font-weight: 720;
    margin-bottom: 0.18rem;
}

.selector-subtitle {
    color: var(--text-soft);
    font-size: 0.9rem;
    line-height: 1.5;
    margin-bottom: 0.75rem;
}

.inline-note {
    color: var(--text-soft);
    font-size: 0.92rem;
    line-height: 1.5;
}

.hero-shell {
    margin-top: 0.1rem;
    margin-bottom: 1.2rem;
}

.hero-banner-wrap {
    border-radius: 28px;
    overflow: hidden;
    border: 1px solid rgba(255,255,255,0.06);
    box-shadow: var(--shadow-deep);
}

.hero-image-fallback {
    border-radius: 20px;
    padding: 1.2rem;
    background: linear-gradient(180deg, rgba(255,255,255,0.03), rgba(255,255,255,0.014));
    border: 1px solid rgba(255,255,255,0.08);
}

@media (max-width: 1100px) {
    .hero-shell {
        margin-bottom: 1rem;
    }
}
.section-title {
    margin-top: 0.2rem;
    margin-bottom: 0.34rem;
    font-size: 1.88rem;
    line-height: 1.15;
    font-weight: 800;
    letter-spacing: -0.03em;
    color: var(--text-strong);
    text-wrap: balance;
}

.app-credit-footer {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    margin: 2rem auto 0.35rem auto;
    padding: 0.42rem 0.95rem;
    border-radius: 999px;
    background: linear-gradient(180deg, rgba(11, 21, 34, 0.9), rgba(7, 15, 27, 0.88));
    border: 1px solid rgba(255,255,255,0.08);
    box-shadow: 0 10px 28px rgba(0,0,0,0.22);
    color: rgba(245, 248, 253, 0.92);
    font-size: 0.76rem;
    letter-spacing: 0.01em;
    backdrop-filter: blur(8px);
    white-space: nowrap;
}

.section-subtitle {
    color: var(--text-soft);
    margin-bottom: 1.1rem;
    line-height: 1.65;
    max-width: 62rem;
    font-size: 1rem;
}

.metric-card {
    border-radius: var(--radius-card);
    padding: 1.08rem 1.12rem;
    background: linear-gradient(180deg, rgba(255,255,255,0.042), rgba(255,255,255,0.02));
    border: 1px solid rgba(255,255,255,0.08);
    margin-bottom: 0.9rem;
    box-shadow: var(--glow-soft), var(--shadow-soft);
    min-height: 118px;
    transition: transform 0.18s ease, border-color 0.18s ease, box-shadow 0.18s ease;
}

.metric-card:hover,
.panel-card:hover,
.compound-card:hover,
.result-card:hover,
.helper-card:hover,
.kv-card:hover,
.structure-card:hover {
    transform: translateY(-1px);
    border-color: rgba(97,216,237,0.2);
    box-shadow: 0 18px 42px rgba(0,0,0,0.26), 0 0 0 1px rgba(97,216,237,0.05);
}

.metric-card-label {
    color: var(--text-soft);
    font-size: 0.9rem;
    font-weight: 580;
    margin-bottom: 0.5rem;
    line-height: 1.35;
}

.metric-card-value {
    font-size: 2.18rem;
    font-weight: 780;
    line-height: 1;
    letter-spacing: -0.03em;
    color: var(--text-strong);
}

.dashboard-section {
    margin-top: 0.5rem;
    margin-bottom: 1.2rem;
}

.dashboard-dataframe-note {
    margin-top: -0.25rem;
    margin-bottom: 0.9rem;
    color: var(--text-soft);
    font-size: 0.9rem;
}

.clean-stat {
    padding: 0.95rem 1rem;
    border-radius: 18px;
    background: linear-gradient(180deg, rgba(255,255,255,0.03), rgba(255,255,255,0.016));
    border: 1px solid rgba(255,255,255,0.07);
    box-shadow: inset 0 1px 0 rgba(255,255,255,0.035);
    min-height: 116px;
}

.clean-stat-label {
    color: var(--text-soft);
    font-size: 1rem;
    font-weight: 560;
    margin-bottom: 0.3rem;
    line-height: 1.5;
}

.clean-stat-value {
    color: var(--text-main);
    font-size: 2.08rem;
    font-weight: 780;
    letter-spacing: -0.03em;
    line-height: 1;
}

.panel-card {
    padding: 1.1rem 1.12rem;
    border-radius: 24px;
    background: linear-gradient(180deg, rgba(255,255,255,0.04), rgba(255,255,255,0.018));
    border: 1px solid rgba(255,255,255,0.08);
    box-shadow: var(--glow-soft), var(--shadow-soft);
    margin-bottom: 1rem;
    backdrop-filter: blur(10px);
}

.quick-card {
    padding: 1rem 1.05rem;
    border-radius: 18px;
    border: 1px solid rgba(255,255,255,0.08);
    background: rgba(255,255,255,0.022);
    margin-bottom: 0.8rem;
}

.compound-card {
    padding: 1.02rem 1.08rem;
    border-radius: 22px;
    border: 1px solid rgba(255,255,255,0.08);
    background: linear-gradient(180deg, rgba(255,255,255,0.034), rgba(255,255,255,0.016));
    margin-bottom: 0.85rem;
    box-shadow: var(--glow-soft), var(--shadow-soft);
}

.compound-thumb-shell {
    width: 100%;
    height: 184px;
    display: flex;
    align-items: center;
    justify-content: center;
    overflow: hidden;
    border-radius: 18px;
    background: linear-gradient(180deg, rgba(255,255,255,0.065), rgba(255,255,255,0.018));
    border: 1px solid rgba(255,255,255,0.08);
}

.compound-thumb-shell img {
    width: 100%;
    height: 184px;
    object-fit: contain;
    display: block;
    background: rgba(255,255,255,0.96);
}

.compound-card:hover {
    border-color: rgba(115,231,255,0.22);
}

.result-card {
    padding: 1.05rem 1.1rem;
    border-radius: 22px;
    border: 1px solid rgba(255,255,255,0.08);
    background: linear-gradient(180deg, rgba(255,255,255,0.034), rgba(255,255,255,0.018));
    margin-bottom: 0.8rem;
    box-shadow: var(--glow-soft), var(--shadow-soft);
}

.best-match-card {
    padding: 1.15rem 1.2rem;
    border-radius: 20px;
    border: 1px solid rgba(126, 240, 194, 0.30);
    background: linear-gradient(135deg, rgba(11, 103, 83, 0.18), rgba(53, 81, 152, 0.14));
    margin-bottom: 1rem;
}

.result-title {
    font-size: 1.16rem;
    font-weight: 780;
    margin-bottom: 0.22rem;
    color: var(--text-strong);
}

.result-subtitle {
    color: var(--text-soft);
    font-size: 0.95rem;
    margin-bottom: 0.55rem;
}

.badge-row {
    margin-top: 0.28rem;
    margin-bottom: 0.28rem;
    color: #D9DDE5;
    font-size: 0.95rem;
}

.info-chip-row {
    display: flex;
    flex-wrap: wrap;
    gap: 0.45rem;
    margin-top: 0.55rem;
}

.info-chip {
    display: inline-block;
    border-radius: 999px;
    padding: 0.38rem 0.72rem;
    font-size: 0.82rem;
    color: #E8EEF8;
    background: linear-gradient(180deg, rgba(255,255,255,0.06), rgba(255,255,255,0.025));
    border: 1px solid rgba(255,255,255,0.07);
    box-shadow: inset 0 1px 0 rgba(255,255,255,0.03);
}

.kv-card {
    height: 100%;
    border-radius: 18px;
    padding: 1rem 1.05rem;
    background: linear-gradient(180deg, rgba(255,255,255,0.028), rgba(255,255,255,0.014));
    border: 1px solid rgba(255,255,255,0.08);
    margin-bottom: 0.75rem;
    box-shadow: inset 0 1px 0 rgba(255,255,255,0.03);
}

.kv-title {
    color: var(--text-soft);
    font-size: 0.87rem;
    margin-bottom: 0.18rem;
}

.kv-value {
    font-size: 1rem;
    font-weight: 660;
    color: var(--text-main);
    word-break: break-word;
    line-height: 1.55;
}

.structure-card {
    border-radius: 24px;
    padding: 1.05rem;
    background: linear-gradient(180deg, rgba(255,255,255,0.03), rgba(255,255,255,0.015));
    border: 1px solid rgba(255,255,255,0.08);
    box-shadow: var(--glow-soft), var(--shadow-soft);
}

.record-shell {
    margin-top: 0.55rem;
}

.record-section-note {
    color: var(--text-soft);
    font-size: 0.94rem;
    line-height: 1.6;
    margin-top: -0.25rem;
    margin-bottom: 0.85rem;
}

.record-badge-strip {
    display: flex;
    flex-wrap: wrap;
    gap: 0.55rem;
    margin-bottom: 1rem;
}

.record-badge {
    display: inline-flex;
    align-items: center;
    padding: 0.48rem 0.82rem;
    border-radius: 999px;
    background: linear-gradient(180deg, rgba(255,255,255,0.06), rgba(255,255,255,0.026));
    border: 1px solid rgba(255,255,255,0.08);
    color: #E8EEF8;
    font-size: 0.88rem;
    box-shadow: inset 0 1px 0 rgba(255,255,255,0.04);
}

.structure-result-grid {
    display: grid;
    grid-template-columns: minmax(220px, 280px) 1fr;
    gap: 1rem;
    align-items: start;
}

.structure-result-meta {
    display: grid;
    gap: 0.45rem;
}

.structure-result-stat {
    color: var(--text-soft);
    font-size: 0.92rem;
    line-height: 1.5;
}

.query-summary-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
    gap: 0.7rem;
}

.query-summary-card {
    border-radius: 18px;
    padding: 0.95rem 1rem;
    background: linear-gradient(180deg, rgba(255,255,255,0.036), rgba(255,255,255,0.018));
    border: 1px solid rgba(255,255,255,0.08);
}

.query-summary-label {
    color: var(--text-soft);
    font-size: 0.84rem;
    margin-bottom: 0.18rem;
}

.query-summary-value {
    color: var(--text-strong);
    font-size: 1.15rem;
    font-weight: 740;
    line-height: 1.2;
}

.detail-table-wrap {
    padding: 0.2rem 0 0.9rem 0;
}

@media (max-width: 900px) {
    .structure-result-grid {
        grid-template-columns: 1fr;
    }
}

.small-note {
    color: var(--text-soft);
    font-size: 0.92rem;
}

div[data-baseweb="select"] > div {
    border-radius: 16px !important;
    background: rgba(255,255,255,0.028) !important;
    border-color: rgba(255,255,255,0.09) !important;
    min-height: 50px !important;
}

div[data-testid="stTextInput"] input,
div[data-testid="stTextArea"] textarea,
div[data-testid="stNumberInput"] input {
    border-radius: 16px !important;
    background: rgba(255,255,255,0.026) !important;
    border: 1px solid rgba(255,255,255,0.08) !important;
    color: var(--text-main) !important;
    box-shadow: inset 0 1px 0 rgba(255,255,255,0.025);
}

div[data-testid="stTextInput"] input:focus,
div[data-testid="stTextArea"] textarea:focus,
div[data-testid="stNumberInput"] input:focus {
    border-color: rgba(97,216,237,0.34) !important;
    box-shadow: 0 0 0 1px rgba(97,216,237,0.18), 0 0 0 6px rgba(97,216,237,0.05) !important;
}

button[kind="primary"] {
    border-radius: 16px !important;
    min-height: 46px !important;
}

div[data-testid="stButton"] button,
div[data-testid="stDownloadButton"] button {
    border-radius: 16px !important;
    min-height: 46px !important;
    font-weight: 660 !important;
    background: linear-gradient(180deg, rgba(255,255,255,0.055), rgba(255,255,255,0.028)) !important;
    border: 1px solid rgba(255,255,255,0.10) !important;
    color: #F5F8FD !important;
    box-shadow: inset 0 1px 0 rgba(255,255,255,0.04), 0 8px 22px rgba(0,0,0,0.16);
    transition: transform 0.16s ease, box-shadow 0.16s ease, border-color 0.16s ease !important;
}

div[data-testid="stButton"] button:hover,
div[data-testid="stDownloadButton"] button:hover {
    border-color: rgba(97, 216, 237, 0.36) !important;
    transform: translateY(-1px);
    box-shadow: inset 0 1px 0 rgba(255,255,255,0.05), 0 14px 26px rgba(0,0,0,0.2);
}

div[data-testid="stRadio"] > div {
    gap: 0.6rem;
}

div[data-testid="stRadio"] label {
    background: linear-gradient(180deg, rgba(255,255,255,0.03), rgba(255,255,255,0.018));
    border: 1px solid rgba(255,255,255,0.08);
    border-radius: 999px;
    padding: 0.48rem 1rem;
    transition: all 0.18s ease;
    box-shadow: inset 0 1px 0 rgba(255,255,255,0.03);
}

div[data-testid="stRadio"] label p {
    font-size: 0.95rem !important;
    font-weight: 600 !important;
}

div[data-testid="stRadio"] label:has(input:checked) {
    background: linear-gradient(90deg, rgba(97,216,237,0.26), rgba(156,99,241,0.28));
    border-color: rgba(97,216,237,0.42);
    box-shadow: 0 0 0 1px rgba(97,216,237,0.06), 0 10px 24px rgba(76,142,255,0.12);
}

.action-strip {
    border-radius: 20px;
    padding: 1rem 1.05rem;
    border: 1px solid rgba(255,255,255,0.08);
    background: linear-gradient(180deg, rgba(255,255,255,0.04), rgba(255,255,255,0.018));
    margin-bottom: 1rem;
    box-shadow: var(--glow-soft);
}

.helper-card {
    border-radius: 20px;
    padding: 1.05rem 1.08rem;
    border: 1px solid rgba(255,255,255,0.08);
    background: linear-gradient(180deg, rgba(255,255,255,0.03), rgba(255,255,255,0.016));
    margin-bottom: 0.9rem;
    box-shadow: var(--glow-soft);
}

.helper-title {
    color: var(--text-main);
    font-size: 1rem;
    font-weight: 720;
    margin-bottom: 0.24rem;
}

.helper-text {
    color: var(--text-soft);
    font-size: 0.93rem;
    line-height: 1.5;
}

.section-banner {
    margin-bottom: 1rem;
    border-radius: 22px;
    overflow: hidden;
    border: 1px solid rgba(255,255,255,0.08);
    background: rgba(255,255,255,0.02);
    box-shadow: var(--shadow-soft);
}

.accent-logo-wrap {
    margin-top: 1rem;
    padding-top: 0.2rem;
    text-align: center;
}

[data-testid="stDataFrame"] {
    border-radius: 18px;
    overflow: hidden;
    border: 1px solid rgba(255,255,255,0.08);
    box-shadow: var(--glow-soft);
}

[data-testid="stDataFrame"] [role="grid"] {
    background: rgba(8, 17, 30, 0.45) !important;
}

[data-testid="stTabs"] [data-baseweb="tab-list"] {
    gap: 0.55rem;
    padding: 0.18rem;
    background: linear-gradient(180deg, rgba(255,255,255,0.026), rgba(255,255,255,0.014));
    border: 1px solid rgba(255,255,255,0.08);
    border-radius: 18px;
    margin-bottom: 1rem;
}

[data-testid="stTabs"] button[role="tab"] {
    min-height: 42px;
    border-radius: 14px !important;
    color: var(--text-soft) !important;
    font-weight: 650 !important;
    transition: all 0.18s ease;
}

[data-testid="stTabs"] button[role="tab"][aria-selected="true"] {
    background: linear-gradient(90deg, rgba(97,216,237,0.22), rgba(156,99,241,0.24)) !important;
    color: var(--text-strong) !important;
    box-shadow: 0 8px 18px rgba(76,142,255,0.12);
}

[data-testid="stExpander"] {
    border-radius: 18px !important;
    border: 1px solid rgba(255,255,255,0.08) !important;
    background: linear-gradient(180deg, rgba(255,255,255,0.03), rgba(255,255,255,0.014)) !important;
    box-shadow: var(--glow-soft);
    overflow: hidden;
}

[data-testid="stExpander"] details summary {
    padding-top: 0.25rem;
    padding-bottom: 0.25rem;
}

[data-testid="stFileUploader"] section {
    border-radius: 18px !important;
    border: 1px dashed rgba(97,216,237,0.24) !important;
    background: linear-gradient(180deg, rgba(255,255,255,0.028), rgba(255,255,255,0.012)) !important;
}

[data-testid="stAlert"] {
    border-radius: 18px !important;
    border: 1px solid rgba(255,255,255,0.07) !important;
    box-shadow: var(--glow-soft);
}

hr {
    border-color: rgba(255,255,255,0.07);
}

header[data-testid="stHeader"] {
    background: rgba(7, 17, 29, 0.32);
}

@media (max-width: 900px) {
    .section-title {
        font-size: 1.45rem;
    }

    .section-subtitle {
        font-size: 0.95rem;
    }

    .sidebar-stats {
        grid-template-columns: 1fr;
    }

    .app-credit-footer {
        display: flex;
        text-align: center;
        white-space: normal;
    }
}

</style>
""", unsafe_allow_html=True)

# =========================
# Database connection
# =========================
def ensure_project_dirs():
    for directory in [
        DATABASE_DIR,
        BRANDING_DIR,
        STRUCTURES_DIR,
        SPECTRA_DIR,
        TEMPLATES_DIR,
        SUBMISSIONS_DIR,
        SUBMISSIONS_INBOX_DIR,
        SUBMISSIONS_REVIEWED_DIR,
        SUBMISSIONS_APPROVED_DIR,
        EXPORTS_DIR,
        DOCS_DIR,
        BACKUPS_DIR,
    ]:
        directory.mkdir(parents=True, exist_ok=True)


def get_connection():
    ensure_project_dirs()
    connection = sqlite3.connect(DB_PATH)
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def invalidate_cached_views():
    try:
        st.cache_data.clear()
    except Exception:
        pass


def table_exists(table_name: str) -> bool:
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table' AND name = ?",
            (table_name,),
        )
        return cursor.fetchone() is not None
    finally:
        conn.close()


def get_table_columns(table_name: str):
    if not table_exists(table_name):
        return set()

    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(f"PRAGMA table_info({table_name})")
        rows = cursor.fetchall()
        return {row[1] for row in rows}
    finally:
        conn.close()


def ensure_database_schema():
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS compounds (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                trivial_name TEXT NOT NULL,
                iupac_name TEXT,
                molecular_formula TEXT,
                smiles TEXT,
                inchi TEXT,
                inchikey TEXT,
                compound_class TEXT,
                compound_subclass TEXT,
                source_category TEXT,
                source_organism TEXT,
                source_material TEXT,
                sample_code TEXT,
                collection_location TEXT,
                gps_coordinates TEXT,
                depth_m REAL,
                uv_data TEXT,
                ftir_data TEXT,
                cd_data TEXT,
                optical_rotation TEXT,
                melting_point TEXT,
                crystallization_method TEXT,
                structure_image_path TEXT,
                journal_name TEXT,
                article_title TEXT,
                publication_year TEXT,
                volume TEXT,
                issue TEXT,
                pages TEXT,
                doi TEXT,
                ccdc_number TEXT,
                molecular_weight REAL,
                hrms_data TEXT,
                data_source TEXT,
                note TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS proton_nmr (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                compound_id INTEGER NOT NULL,
                delta_ppm REAL NOT NULL,
                multiplicity TEXT,
                j_value TEXT,
                proton_count TEXT,
                assignment TEXT,
                solvent TEXT,
                instrument_mhz REAL,
                note TEXT,
                FOREIGN KEY (compound_id) REFERENCES compounds(id) ON DELETE CASCADE
            )
            """
        )
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS carbon_nmr (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                compound_id INTEGER NOT NULL,
                delta_ppm REAL NOT NULL,
                carbon_type TEXT,
                assignment TEXT,
                solvent TEXT,
                instrument_mhz REAL,
                note TEXT,
                FOREIGN KEY (compound_id) REFERENCES compounds(id) ON DELETE CASCADE
            )
            """
        )
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS spectra_files (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                compound_id INTEGER NOT NULL,
                spectrum_type TEXT NOT NULL,
                file_path TEXT NOT NULL,
                note TEXT,
                FOREIGN KEY (compound_id) REFERENCES compounds(id) ON DELETE CASCADE
            )
            """
        )
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS bioactivity_records (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                compound_id INTEGER NOT NULL,
                activity_label TEXT NOT NULL,
                target_name TEXT,
                target_category TEXT,
                assay_type TEXT,
                potency_type TEXT,
                potency_relation TEXT,
                potency_value REAL,
                potency_unit TEXT,
                outcome TEXT,
                assay_medium TEXT,
                selectivity TEXT,
                assay_source TEXT,
                note TEXT,
                FOREIGN KEY (compound_id) REFERENCES compounds(id) ON DELETE CASCADE
            )
            """
        )
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_compounds_trivial_name ON compounds(trivial_name)"
        )
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_compounds_sample_code ON compounds(sample_code)"
        )
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_compounds_doi ON compounds(doi)"
        )
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_compounds_inchikey ON compounds(inchikey)"
        )
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_compounds_smiles ON compounds(smiles)"
        )
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_proton_compound ON proton_nmr(compound_id)"
        )
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_carbon_compound ON carbon_nmr(compound_id)"
        )
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_spectra_compound ON spectra_files(compound_id)"
        )
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_bioactivity_compound ON bioactivity_records(compound_id)"
        )
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_bioactivity_target_category ON bioactivity_records(target_category)"
        )
        conn.commit()
        invalidate_cached_views()
    finally:
        conn.close()


def ensure_compounds_schema():
    required_columns = {
        "issue": "TEXT",
        "ccdc_number": "TEXT",
        "molecular_weight": "REAL",
        "smiles": "TEXT",
        "inchi": "TEXT",
        "inchikey": "TEXT",
        "hrms_data": "TEXT",
        "source_category": "TEXT",
        "source_organism": "TEXT",
        "cd_data": "TEXT",
        "article_title": "TEXT",
        "created_at": "TEXT",
        "updated_at": "TEXT",
    }

    existing = get_table_columns("compounds")
    missing = {name: dtype for name, dtype in required_columns.items() if name not in existing}
    if not missing:
        return

    conn = get_connection()
    try:
        cursor = conn.cursor()
        for column_name, data_type in missing.items():
            cursor.execute(f"ALTER TABLE compounds ADD COLUMN {column_name} {data_type}")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_compounds_inchikey ON compounds(inchikey)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_compounds_smiles ON compounds(smiles)")
        conn.commit()
        invalidate_cached_views()
    finally:
        conn.close()


def ensure_bioactivity_schema():
    required_columns = {
        "activity_label": "TEXT",
        "target_name": "TEXT",
        "target_category": "TEXT",
        "assay_type": "TEXT",
        "potency_type": "TEXT",
        "potency_relation": "TEXT",
        "potency_value": "REAL",
        "potency_unit": "TEXT",
        "outcome": "TEXT",
        "assay_medium": "TEXT",
        "selectivity": "TEXT",
        "assay_source": "TEXT",
        "note": "TEXT",
    }

    if not table_exists("bioactivity_records"):
        ensure_database_schema()
        return

    existing = get_table_columns("bioactivity_records")
    missing = {name: dtype for name, dtype in required_columns.items() if name not in existing}
    if not missing:
        return

    conn = get_connection()
    try:
        cursor = conn.cursor()
        for column_name, data_type in missing.items():
            cursor.execute(f"ALTER TABLE bioactivity_records ADD COLUMN {column_name} {data_type}")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_bioactivity_compound ON bioactivity_records(compound_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_bioactivity_target_category ON bioactivity_records(target_category)")
        conn.commit()
        invalidate_cached_views()
    finally:
        conn.close()


ensure_database_schema()
ensure_compounds_schema()
ensure_bioactivity_schema()

# =========================
# Generic helpers
# =========================
def clean_text(value):
    if pd.isna(value) or value is None:
        return "-"
    text = str(value).strip()
    return text if text else "-"

def maybe_blank(value):
    if value is None:
        return ""
    if pd.isna(value):
        return ""
    return str(value).strip()

def safe_float_or_none(value):
    text = maybe_blank(value)
    if not text:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def normalize_source_category(value: str) -> str:
    text = maybe_blank(value)
    if not text:
        return ""
    for option in DEFAULT_SOURCE_OPTIONS:
        if text.casefold() == option.casefold():
            return option
    return text


def infer_source_fields(source_category="", source_organism="", source_material="") -> tuple[str, str, str]:
    category = normalize_source_category(source_category)
    organism = maybe_blank(source_organism)
    legacy = maybe_blank(source_material)

    if not category and legacy:
        category = normalize_source_category(legacy)
        if category and category.casefold() != legacy.casefold():
            category = normalize_source_category(category)

    if not organism and legacy:
        normalized_legacy_category = normalize_source_category(legacy)
        if not normalized_legacy_category or normalized_legacy_category.casefold() != legacy.casefold():
            organism = legacy

    summary = legacy
    if category and organism:
        summary = f"{category} | {organism}"
    elif category:
        summary = category
    elif organism:
        summary = organism

    return category, organism, summary


def source_summary_from_record(record) -> str:
    category, organism, summary = infer_source_fields(
        record.get("source_category"),
        record.get("source_organism"),
        record.get("source_material"),
    )
    return summary


COMPOUND_REQUIRED_COLUMNS = [
    "id",
    "trivial_name",
    "iupac_name",
    "molecular_formula",
    "smiles",
    "inchi",
    "inchikey",
    "compound_class",
    "compound_subclass",
    "source_category",
    "source_organism",
    "source_material",
    "sample_code",
    "collection_location",
    "gps_coordinates",
    "depth_m",
    "uv_data",
    "ftir_data",
    "cd_data",
    "optical_rotation",
    "melting_point",
    "crystallization_method",
    "structure_image_path",
    "journal_name",
    "article_title",
    "publication_year",
    "volume",
    "issue",
    "pages",
    "doi",
    "ccdc_number",
    "molecular_weight",
    "hrms_data",
    "data_source",
    "note",
    "created_at",
    "updated_at",
]


def enrich_compounds_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    enriched = df.copy()
    for column_name in COMPOUND_REQUIRED_COLUMNS:
        if column_name not in enriched.columns:
            enriched[column_name] = ""

    if enriched.empty:
        return enriched[COMPOUND_REQUIRED_COLUMNS]

    source_fields = enriched.apply(
        lambda row: infer_source_fields(
            row.get("source_category"),
            row.get("source_organism"),
            row.get("source_material"),
        ),
        axis=1,
        result_type="expand",
    )
    source_fields.columns = ["source_category", "source_organism", "source_material"]
    enriched["source_category"] = source_fields["source_category"]
    enriched["source_organism"] = source_fields["source_organism"]
    enriched["source_material"] = source_fields["source_material"]
    return enriched


def is_raw_spectrum_type(spectrum_type_value: str) -> bool:
    text = maybe_blank(spectrum_type_value).lower()
    raw_tokens = ["raw", "jcamp", "mnova", "fid"]
    return any(token in text for token in raw_tokens)


def classify_storage_type(file_path_value: str) -> str:
    text = maybe_blank(file_path_value)
    if not text:
        return "Unknown"
    if is_google_drive_url(text):
        return "Google Drive"
    if is_external_url(text):
        return "External URL"
    return "Local file"


def validate_spectrum_entry(file_path_value: str, spectrum_type_value: str) -> tuple[list[str], list[str]]:
    errors = []
    warnings = []
    path_text = maybe_blank(file_path_value)
    spectrum_text = maybe_blank(spectrum_type_value)

    if not path_text:
        errors.append("File path or URL is required.")
        return errors, warnings

    if is_external_url(path_text):
        if is_google_drive_url(path_text):
            file_id = extract_google_drive_file_id(path_text)
            if not file_id:
                warnings.append("Google Drive link was detected, but the file ID could not be extracted. Preview/download may fail.")
            if is_raw_spectrum_type(spectrum_text):
                warnings.append("Raw-data link saved in Google Drive mode. Make sure sharing permission is set to viewer/download for approved users.")
        elif is_raw_spectrum_type(spectrum_text):
            warnings.append("Raw-data link uses a non-Google external URL. Confirm that users can access it from outside your laptop.")
        return errors, warnings

    full_path = get_full_file_path(path_text)
    if full_path is None or not full_path.exists():
        warnings.append("Local file path was saved, but the file does not currently exist at that location.")
    elif is_raw_spectrum_type(spectrum_text):
        warnings.append("Raw-data file is stored locally. Google Drive is safer for public deployment and laptop storage.")
    return errors, warnings

def slugify_value(value: str, fallback: str = "file") -> str:
    text = re.sub(r"[^A-Za-z0-9._-]+", "_", maybe_blank(value))
    text = text.strip("._")
    return text or fallback

def relative_project_path(path: Path) -> str:
    return str(path.relative_to(PROJECT_DIR))

def save_uploaded_asset(uploaded_file, target_dir: Path, base_name: str) -> str:
    safe_name = slugify_value(base_name, fallback="asset")
    suffix = Path(uploaded_file.name).suffix.lower() or ".bin"
    candidate = target_dir / f"{safe_name}{suffix}"
    counter = 2

    while candidate.exists():
        candidate = target_dir / f"{safe_name}_{counter}{suffix}"
        counter += 1

    with open(candidate, "wb") as output_file:
        output_file.write(uploaded_file.getbuffer())

    return relative_project_path(candidate)

def build_existing_options(df: pd.DataFrame, column_name: str, defaults=None):
    values = set(defaults or [])
    if column_name in df.columns:
        for value in df[column_name].dropna().astype(str):
            cleaned = value.strip()
            if cleaned:
                values.add(cleaned)
    return sorted(values)

def select_or_custom(label: str, options: list[str], key: str, value: str = "", help_text: str | None = None):
    normalized_value = maybe_blank(value)
    clean_options = [item for item in options if maybe_blank(item)]
    known_values = sorted(set(clean_options))

    custom_default = normalized_value if normalized_value and normalized_value not in known_values else ""
    select_options = [""] + known_values + ["Custom..."]
    default_value = normalized_value if normalized_value in known_values else ("Custom..." if custom_default else "")
    select_key = f"{key}_select"
    selectbox_kwargs = {
        "label": label,
        "options": select_options,
        "key": select_key,
        "help": help_text,
    }
    if select_key not in st.session_state:
        selectbox_kwargs["index"] = select_options.index(default_value)
    selected = st.selectbox(**selectbox_kwargs)
    show_custom_input = selected == "Custom..." or bool(custom_default)
    if show_custom_input:
        custom_key = f"{key}_custom"
        custom_kwargs = {
            "label": f"{label} (Custom, optional)",
            "key": custom_key,
            "placeholder": f"Type a new {label.lower()} here if it is not in the list.",
        }
        if custom_key not in st.session_state:
            custom_kwargs["value"] = custom_default
        custom_value = st.text_input(**custom_kwargs)
        custom_text = maybe_blank(custom_value)
        if custom_text:
            return custom_text
        return ""
    return selected

def reset_compound_wizard():
    wizard_keys = [
        "compound_wizard_step",
        "wizard_trivial_name",
        "wizard_iupac_name",
        "wizard_formula",
        "wizard_molecular_weight",
        "wizard_smiles",
        "wizard_inchi",
        "wizard_inchikey",
        "wizard_compound_class_select",
        "wizard_compound_class_custom",
        "wizard_compound_subclass_select",
        "wizard_compound_subclass_custom",
        "wizard_data_source_select",
        "wizard_data_source_custom",
        "wizard_source_category_select",
        "wizard_source_category_custom",
        "wizard_source_organism",
        "wizard_sample_code",
        "wizard_collection_location",
        "wizard_gps_coordinates",
        "wizard_depth_m",
        "wizard_uv_data",
        "wizard_ftir_data",
        "wizard_cd_data",
        "wizard_optical_rotation",
        "wizard_melting_point",
        "wizard_crystallization_method",
        "wizard_ccdc_number",
        "wizard_hrms_data",
        "wizard_structure_path",
        "wizard_structure_upload",
        "wizard_submission_spectrum_type_select",
        "wizard_submission_spectrum_type_custom",
        "wizard_submission_spectra_note",
        "wizard_submission_spectra_uploads",
        "wizard_journal_name",
        "wizard_article_title",
        "wizard_publication_year",
        "wizard_volume",
        "wizard_issue",
        "wizard_pages",
        "wizard_doi",
        "wizard_note",
    ]
    for key in wizard_keys:
        if key in st.session_state:
            del st.session_state[key]
        draft_key = f"_draft_{key}"
        if draft_key in st.session_state:
            del st.session_state[draft_key]
    st.session_state["compound_wizard_step"] = 1


def persist_wizard_inputs():
    wizard_keys = [
        "wizard_trivial_name",
        "wizard_iupac_name",
        "wizard_formula",
        "wizard_molecular_weight",
        "wizard_smiles",
        "wizard_inchi",
        "wizard_inchikey",
        "wizard_compound_class_select",
        "wizard_compound_class_custom",
        "wizard_compound_subclass_select",
        "wizard_compound_subclass_custom",
        "wizard_data_source_select",
        "wizard_data_source_custom",
        "wizard_source_category_select",
        "wizard_source_category_custom",
        "wizard_source_organism",
        "wizard_sample_code",
        "wizard_collection_location",
        "wizard_gps_coordinates",
        "wizard_depth_m",
        "wizard_uv_data",
        "wizard_ftir_data",
        "wizard_cd_data",
        "wizard_optical_rotation",
        "wizard_melting_point",
        "wizard_crystallization_method",
        "wizard_ccdc_number",
        "wizard_hrms_data",
        "wizard_structure_path",
        "wizard_structure_upload",
        "wizard_submission_spectrum_type_select",
        "wizard_submission_spectrum_type_custom",
        "wizard_submission_spectra_note",
        "wizard_submission_spectra_uploads",
        "wizard_journal_name",
        "wizard_article_title",
        "wizard_publication_year",
        "wizard_volume",
        "wizard_issue",
        "wizard_pages",
        "wizard_doi",
        "wizard_note",
    ]
    for key in wizard_keys:
        if key in st.session_state:
            st.session_state[f"_draft_{key}"] = st.session_state[key]


def get_wizard_value(key: str, default=""):
    draft_key = f"_draft_{key}"
    if draft_key in st.session_state:
        return st.session_state[draft_key]
    return st.session_state.get(key, default)


def hydrate_wizard_widget(key: str, default=""):
    draft_key = f"_draft_{key}"
    if key not in st.session_state:
        if draft_key in st.session_state:
            st.session_state[key] = st.session_state[draft_key]
        else:
            st.session_state[key] = default

def keyword_search_mask(df: pd.DataFrame, keyword: str) -> pd.Series:
    searchable_columns = [
        "trivial_name",
        "iupac_name",
        "smiles",
        "inchi",
        "inchikey",
        "sample_code",
        "source_category",
        "source_organism",
        "source_material",
        "collection_location",
        "compound_class",
        "compound_subclass",
        "journal_name",
        "doi",
        "note",
    ]
    combined = df[searchable_columns].fillna("").astype(str).agg(" ".join, axis=1).str.lower()
    tokens = [token.lower() for token in re.split(r"\s+", keyword.strip()) if token]

    if not tokens:
        return pd.Series([True] * len(df), index=df.index)

    mask = pd.Series([True] * len(df), index=df.index)
    for token in tokens:
        mask &= combined.str.contains(re.escape(token), regex=True)
    return mask


def is_structure_backend_available() -> bool:
    return Chem is not None and DataStructs is not None and AllChem is not None


def smiles_to_mol(smiles_value: str):
    if not is_structure_backend_available():
        return None
    smiles_text = maybe_blank(smiles_value)
    if not smiles_text:
        return None
    try:
        return Chem.MolFromSmiles(smiles_text)
    except Exception:
        return None


def structure_text_to_mol(structure_value: str):
    if not is_structure_backend_available():
        return None
    structure_text = maybe_blank(structure_value)
    if not structure_text:
        return None

    mol = smiles_to_mol(structure_text)
    if mol is not None:
        return mol

    try:
        return Chem.MolFromMolBlock(structure_text, sanitize=True, removeHs=True)
    except Exception:
        return None


def canonicalize_smiles(smiles_value: str) -> str:
    mol = structure_text_to_mol(smiles_value)
    if mol is None:
        return ""
    try:
        return Chem.MolToSmiles(mol, canonical=True)
    except Exception:
        return ""


def molecule_similarity_score(query_mol, candidate_mol) -> float:
    if not is_structure_backend_available() or query_mol is None or candidate_mol is None:
        return 0.0
    query_fp = AllChem.GetMorganFingerprintAsBitVect(query_mol, radius=2, nBits=2048)
    candidate_fp = AllChem.GetMorganFingerprintAsBitVect(candidate_mol, radius=2, nBits=2048)
    return float(DataStructs.TanimotoSimilarity(query_fp, candidate_fp))


def search_by_structure(
    compounds_df: pd.DataFrame,
    query_smiles: str,
    search_type: str,
    similarity_threshold: float = 0.35,
):
    query_text = maybe_blank(query_smiles)
    if not query_text:
        return [], "Please draw a structure and click Apply in the editor first, or paste a valid SMILES / Molfile query."

    if not is_structure_backend_available():
        return [], "Structure search requires RDKit. Install `rdkit>=2026.3` in both requirements.txt files before using this feature."

    query_mol = structure_text_to_mol(query_text)
    if query_mol is None:
        return [], "The structure could not be parsed. Please redraw the query or paste a valid SMILES / Molfile structure."

    query_canonical = canonicalize_smiles(query_text)
    results = []
    searchable_candidates = 0

    for _, row in compounds_df.iterrows():
        candidate_smiles = maybe_blank(row.get("smiles"))
        if not candidate_smiles:
            continue

        candidate_mol = smiles_to_mol(candidate_smiles)
        if candidate_mol is None:
            continue
        searchable_candidates += 1

        matched = False
        score = 0.0
        match_label = ""

        if search_type == "Identity Search":
            candidate_canonical = canonicalize_smiles(candidate_smiles)
            matched = bool(query_canonical and candidate_canonical and query_canonical == candidate_canonical)
            score = 1.0 if matched else 0.0
            match_label = "Identity"
        elif search_type == "Substructure Search":
            try:
                matched = candidate_mol.HasSubstructMatch(query_mol)
            except Exception:
                matched = False
            score = 1.0 if matched else 0.0
            match_label = "Substructure"
        else:
            score = molecule_similarity_score(query_mol, candidate_mol)
            matched = score >= similarity_threshold
            match_label = "Similarity"

        if matched:
            item = row.to_dict()
            item["structure_score"] = score * 100
            item["structure_match_type"] = match_label
            item["query_smiles"] = query_text
            item["matched_smiles"] = candidate_smiles
            results.append(item)

    if search_type == "Similarity Search":
        results.sort(
            key=lambda item: (
                item.get("structure_score", 0.0),
                maybe_blank(item.get("trivial_name")).lower(),
            ),
            reverse=True,
        )
    else:
        results.sort(
            key=lambda item: (
                maybe_blank(item.get("trivial_name")).lower(),
                int(item.get("id", 0)),
            )
        )

    if searchable_candidates == 0:
        return [], (
            f"No searchable structures are available yet in the current filtered dataset. Searchable compounds right now: {searchable_candidates}. "
            "Structure search compares your drawn query against compounds that already have SMILES filled in, "
            "so please add SMILES to your records first or use the admin shortcut to save the current drawn structure into a compound record."
        )

    if not results:
        return [], (
            f"No compounds matched this {search_type.lower()} query in the current filtered dataset. Searchable compounds checked: {searchable_candidates}. "
            "Try lowering the similarity threshold, changing filters, or saving structure identifiers for more compounds first."
        )

    return results, ""


def export_structure_search_results(results: list[dict]) -> pd.DataFrame:
    rows = []
    for i, item in enumerate(results, start=1):
        rows.append(
            {
                "Rank": i,
                "Compound ID": item.get("id"),
                "Trivial Name": clean_text(item.get("trivial_name")),
                "Molecular Formula": clean_text(item.get("molecular_formula")),
                "Compound Class": clean_text(item.get("compound_class")),
                "Source Category": clean_text(item.get("source_category")),
                "Source Organism": clean_text(item.get("source_organism")),
                "Source Summary": clean_text(source_summary_from_record(item)),
                "Match Type": clean_text(item.get("structure_match_type")),
                "Score (%)": round(float(item.get("structure_score", 0.0)), 2),
                "SMILES": clean_text(item.get("matched_smiles")),
            }
        )
    return pd.DataFrame(rows)


def render_structure_search_results(results: list[dict], search_type: str, limit: int = 10):
    if not results:
        st.info("No compounds matched the current structure query.")
        return

    section_header("Structure Search Results", f"Showing the top {min(limit, len(results))} candidate(s) for {search_type.lower()}.")
    st.caption(f"Results: {len(results)}")

    summary_rows = []
    for i, item in enumerate(results, start=1):
        summary_rows.append(
            {
                "Rank": i,
                "Compound ID": item.get("id"),
                "Trivial Name": clean_text(item.get("trivial_name")),
                "Match Type": clean_text(item.get("structure_match_type")),
                "Score (%)": round(float(item.get("structure_score", 0.0)), 2),
            }
        )
    st.markdown('<div class="detail-table-wrap">', unsafe_allow_html=True)
    st.dataframe(pd.DataFrame(summary_rows[:limit]), width="stretch", hide_index=True)
    st.markdown('</div>', unsafe_allow_html=True)

    for i, item in enumerate(results[:limit], start=1):
        title = clean_text(item.get("trivial_name"))
        formula = clean_text(item.get("molecular_formula"))
        compound_class = clean_text(item.get("compound_class"))
        source_summary = clean_text(source_summary_from_record(item))
        score = float(item.get("structure_score", 0.0))
        subtitle = f"{item.get('structure_match_type', search_type)} match | Score: {score:.1f}%"

        with st.expander(f"#{i} · {title}", expanded=(i == 1)):
            st.markdown('<div class="result-card">', unsafe_allow_html=True)
            st.markdown(
                f"""
                <div class="result-title">{title}</div>
                <div class="result-subtitle">{subtitle}</div>
                """,
                unsafe_allow_html=True,
            )
            preview_col, meta_col = st.columns([1, 1.3])
            with preview_col:
                render_structure_preview(item.get("matched_smiles"), caption=f"Query candidate #{i}", size=(380, 260))
            with meta_col:
                st.markdown('<div class="structure-result-meta">', unsafe_allow_html=True)
                st.markdown(f'<div class="structure-result-stat"><strong>Compound ID:</strong> {item.get("id")}</div>', unsafe_allow_html=True)
                st.markdown(f'<div class="structure-result-stat"><strong>Molecular Formula:</strong> {formula}</div>', unsafe_allow_html=True)
                st.markdown(f'<div class="structure-result-stat"><strong>Compound Class:</strong> {compound_class}</div>', unsafe_allow_html=True)
                st.markdown(f'<div class="structure-result-stat"><strong>Source:</strong> {source_summary}</div>', unsafe_allow_html=True)
                st.markdown(f'<div class="structure-result-stat"><strong>SMILES:</strong> {clean_text(item.get("matched_smiles"))}</div>', unsafe_allow_html=True)
                st.progress(min(max(score / 100.0, 0.0), 1.0))
                st.markdown('</div>', unsafe_allow_html=True)

            action_left, action_right = st.columns([1, 1])
            with action_left:
                if st.button(f"Open Record #{i}", key=f"open_structure_result_{item.get('id')}_{i}"):
                    open_compound_detail(int(item["id"]))
                    st.rerun()
            with action_right:
                if can_edit_database():
                    if st.button(f"Update Metadata #{i}", key=f"edit_structure_result_{item.get('id')}_{i}"):
                        open_compound_editor(int(item["id"]))
                        st.rerun()
            st.markdown('</div>', unsafe_allow_html=True)

def calculate_completeness_score(compound_row, proton_df, carbon_df, spectra_df):
    row = compound_row.iloc[0] if isinstance(compound_row, pd.DataFrame) else compound_row
    checks = [
        bool(maybe_blank(row.get("trivial_name"))),
        bool(maybe_blank(row.get("molecular_formula"))),
        bool(maybe_blank(row.get("smiles")) or maybe_blank(row.get("inchi")) or maybe_blank(row.get("inchikey"))),
        bool(maybe_blank(row.get("compound_class"))),
        bool(
            maybe_blank(row.get("source_category"))
            or maybe_blank(row.get("source_organism"))
            or maybe_blank(row.get("source_material"))
        ),
        bool(maybe_blank(row.get("data_source"))),
        bool(maybe_blank(row.get("hrms_data"))),
        bool(maybe_blank(row.get("doi")) or maybe_blank(row.get("journal_name"))),
        bool(maybe_blank(row.get("structure_image_path"))),
        not proton_df.empty,
        not carbon_df.empty,
        not spectra_df.empty,
    ]
    completed = sum(1 for item in checks if item)
    return round((completed / len(checks)) * 100)

def parse_peak_input(text: str):
    peaks = []
    for item in re.split(r"[\s,;]+", maybe_blank(text)):
        if not item:
            continue
        try:
            peaks.append(float(item))
        except ValueError:
            pass
    return peaks

def find_best_matches(query_peaks, db_peaks, tolerance):
    matched_query_peaks = []
    matched_db_indexes = set()

    for q in query_peaks:
        best_match = None
        best_diff = None
        best_index = None

        for i, db_peak in enumerate(db_peaks):
            if i in matched_db_indexes:
                continue

            diff = abs(q - db_peak)
            if diff <= tolerance:
                if best_diff is None or diff < best_diff:
                    best_diff = diff
                    best_match = db_peak
                    best_index = i

        if best_match is not None:
            matched_query_peaks.append((q, best_match, best_diff))
            matched_db_indexes.add(best_index)

    return matched_query_peaks

def is_external_url(value) -> bool:
    text = maybe_blank(value)
    if not text:
        return False
    parsed = urlparse(text)
    return parsed.scheme in {"http", "https"}


def is_google_drive_url(value) -> bool:
    text = maybe_blank(value).lower()
    return "drive.google.com" in text or "docs.google.com" in text


def extract_google_drive_file_id(value) -> str:
    text = maybe_blank(value)
    if not text:
        return ""

    patterns = [
        r"/file/d/([a-zA-Z0-9_-]+)",
        r"[?&]id=([a-zA-Z0-9_-]+)",
        r"/d/([a-zA-Z0-9_-]+)",
    ]
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            return match.group(1)
    return ""


def google_drive_preview_url(value) -> str:
    file_id = extract_google_drive_file_id(value)
    if not file_id:
        return ""
    return f"https://drive.google.com/thumbnail?id={file_id}&sz=w2000"


def google_drive_download_url(value) -> str:
    file_id = extract_google_drive_file_id(value)
    if not file_id:
        return value
    return f"https://drive.google.com/uc?export=download&id={file_id}"


def can_preview_external_image(file_path_value, spectrum_type_value="") -> bool:
    path_text = maybe_blank(file_path_value).lower()
    spectrum_text = maybe_blank(spectrum_type_value).lower()

    if any(raw_token in spectrum_text for raw_token in ["raw", "jcamp", "mnova", "fid"]):
        return False

    if is_google_drive_url(path_text):
        return True

    return path_text.endswith((".png", ".jpg", ".jpeg", ".webp", ".gif"))


def get_full_file_path(relative_path):
    if relative_path is None:
        return None
    relative_path = str(relative_path).strip()
    if not relative_path:
        return None
    if is_external_url(relative_path):
        return None
    candidate = Path(relative_path)
    if candidate.is_absolute():
        return candidate
    return PROJECT_DIR / candidate

def is_image_file(path: Path):
    return path.suffix.lower() in [".png", ".jpg", ".jpeg", ".webp"]

def is_pdf_file(path: Path):
    return path.suffix.lower() == ".pdf"

def normalize_filter_value(value):
    text = clean_text(value)
    return text if text != "-" else None

def build_filter_options(df, column_name):
    values = []
    for value in df[column_name].tolist():
        normalized = normalize_filter_value(value)
        if normalized is not None:
            values.append(normalized)
    return ["All"] + sorted(set(values))

def apply_dataframe_filters(
    df,
    class_filter="All",
    subclass_filter="All",
    source_filter="All",
    data_source_filter="All"
):
    result = df.copy()

    if class_filter != "All":
        result = result[result["compound_class"].fillna("").astype(str).str.strip() == class_filter]

    if subclass_filter != "All":
        result = result[result["compound_subclass"].fillna("").astype(str).str.strip() == subclass_filter]

    if source_filter != "All":
        result = result[result["source_category"].fillna("").astype(str).str.strip() == source_filter]

    if data_source_filter != "All":
        result = result[result["data_source"].fillna("").astype(str).str.strip() == data_source_filter]

    return result

def filter_similarity_results(results, class_filter="All", source_filter="All", data_source_filter="All"):
    filtered = []

    for item in results:
        ok = True

        if class_filter != "All" and clean_text(item.get("compound_class")) != class_filter:
            ok = False

        item_source_category = normalize_source_category(item.get("source_category"))
        if not item_source_category:
            item_source_category = normalize_source_category(item.get("source_material"))
        if source_filter != "All" and clean_text(item_source_category) != source_filter:
            ok = False

        if data_source_filter != "All" and clean_text(item.get("data_source")) != data_source_filter:
            ok = False

        if ok:
            filtered.append(item)

    return filtered

def dataframe_to_csv_bytes(df: pd.DataFrame) -> bytes:
    return df.to_csv(index=False).encode("utf-8")


def dataframe_to_excel_bytes(df: pd.DataFrame, sheet_name: str = "Data") -> bytes:
    if Alignment is None and Font is None and PatternFill is None:
        raise ModuleNotFoundError("openpyxl is not available")

    output = io.BytesIO()
    export_df = df.copy()

    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        export_df.to_excel(writer, sheet_name=sheet_name, index=False)
        worksheet = writer.book[sheet_name]

        worksheet.freeze_panes = "A2"
        worksheet.auto_filter.ref = worksheet.dimensions

        for column_cells in worksheet.columns:
            max_length = 0
            column_letter = column_cells[0].column_letter
            for cell in column_cells:
                cell_value = "" if cell.value is None else str(cell.value)
                max_length = max(max_length, len(cell_value))
            worksheet.column_dimensions[column_letter].width = min(max(max_length + 2, 14), 42)

        footer_row = worksheet.max_row + 2
        footer_col_end = max(1, worksheet.max_column)
        worksheet.cell(row=footer_row, column=1, value=OWNER_CREDIT)
        if footer_col_end > 1:
            worksheet.merge_cells(start_row=footer_row, start_column=1, end_row=footer_row, end_column=footer_col_end)

        footer_cell = worksheet.cell(row=footer_row, column=1)
        if Font is not None:
            footer_cell.font = Font(italic=True, size=10, color="4F5B6B")
        if Alignment is not None:
            footer_cell.alignment = Alignment(horizontal="right")
        if PatternFill is not None:
            footer_cell.fill = PatternFill(fill_type="solid", fgColor="F5F8FD")

        try:
            worksheet.oddFooter.right.text = OWNER_CREDIT
        except Exception:
            pass

    output.seek(0)
    return output.getvalue()


def download_dataframe_button(label: str, df: pd.DataFrame, file_name: str, key: str, sheet_name: str = "Data"):
    try:
        payload = dataframe_to_excel_bytes(df, sheet_name=sheet_name)
        resolved_name = file_name if file_name.lower().endswith(".xlsx") else f"{Path(file_name).stem}.xlsx"
        mime = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    except Exception:
        payload = add_credit_to_text_bytes(dataframe_to_csv_bytes(df))
        resolved_name = f"{Path(file_name).stem}.csv"
        mime = "text/csv"

    st.download_button(
        label=label,
        data=payload,
        file_name=resolved_name,
        mime=mime,
        key=key,
    )


def add_credit_to_text_bytes(payload: bytes) -> bytes:
    text = payload.decode("utf-8")
    text = text.rstrip() + f"\n\n{OWNER_CREDIT}\n"
    return text.encode("utf-8")


def render_app_credit_footer():
    st.markdown(
        f'<div style="text-align:center;"><div class="app-credit-footer">{OWNER_CREDIT}</div></div>',
        unsafe_allow_html=True,
    )


def normalize_structure_image(image_obj, size=(520, 360)):
    if Image is None or ImageOps is None or image_obj is None:
        return image_obj
    try:
        image = image_obj.convert("RGBA")
        contained = ImageOps.contain(image, size, method=Image.Resampling.LANCZOS)
        canvas = Image.new("RGBA", size, (255, 255, 255, 255))
        x = (size[0] - contained.width) // 2
        y = (size[1] - contained.height) // 2
        canvas.paste(contained, (x, y), contained)
        return canvas.convert("RGB")
    except Exception:
        return image_obj


def load_standardized_structure_image(image_path: Path, size=(520, 360)):
    if Image is None or image_path is None or not image_path.exists():
        return None
    try:
        with Image.open(image_path) as image:
            return normalize_structure_image(image, size=size)
    except Exception:
        return None


def load_standardized_structure_source(source_value, size=(520, 360)):
    if Image is None or source_value is None:
        return None
    source_text = str(source_value).strip()
    if not source_text:
        return None

    if is_external_url(source_text):
        try:
            with urllib.request.urlopen(source_text, timeout=30, context=_supabase_ssl_context()) as response:
                raw = response.read()
            with Image.open(io.BytesIO(raw)) as image:
                return normalize_structure_image(image, size=size)
        except Exception:
            return None

    full_path = get_full_file_path(source_text)
    if full_path is None or not full_path.exists():
        return None
    return load_standardized_structure_image(full_path, size=size)


def render_structure_preview(smiles_text: str, caption: str | None = None, empty_message: bool = True, size=(520, 360)):
    if Chem is None or Draw is None:
        if empty_message:
            st.info("Structure preview becomes available when RDKit drawing support is active.")
        return
    smiles_value = maybe_blank(smiles_text)
    if not smiles_value:
        if empty_message:
            st.info("No structure preview available for this record.")
        return
    try:
        mol = structure_text_to_mol(smiles_value)
        if mol is None:
            if empty_message:
                st.info("Stored structure could not be rendered from the available structure string.")
            return
        image = normalize_structure_image(Draw.MolToImage(mol, size=size), size=size)
        st.image(image, caption=caption, width="stretch")
    except Exception:
        if empty_message:
            st.info("Structure preview could not be rendered for this record.")

def get_backup_bytes():
    with open(DB_PATH, "rb") as f:
        return f.read()

def count_related_records(filtered_ids):
    filtered_ids = [int(item) for item in filtered_ids if str(item).strip()]
    if not filtered_ids:
        return 0, 0, 0
    conn = get_connection()

    try:
        placeholders = ",".join("?" * len(filtered_ids))
        proton_query = f"SELECT COUNT(*) AS n FROM proton_nmr WHERE compound_id IN ({placeholders})"
        carbon_query = f"SELECT COUNT(*) AS n FROM carbon_nmr WHERE compound_id IN ({placeholders})"
        spectra_query = f"SELECT COUNT(*) AS n FROM spectra_files WHERE compound_id IN ({placeholders})"

        proton_count = int(pd.read_sql_query(proton_query, conn, params=filtered_ids)["n"][0])
        carbon_count = int(pd.read_sql_query(carbon_query, conn, params=filtered_ids)["n"][0])
        spectra_count = int(pd.read_sql_query(spectra_query, conn, params=filtered_ids)["n"][0])
        return proton_count, carbon_count, spectra_count
    finally:
        conn.close()


def count_bioactivity_records(filtered_ids):
    filtered_ids = [int(item) for item in filtered_ids if str(item).strip()]
    if not filtered_ids:
        return 0
    conn = get_connection()
    try:
        placeholders = ",".join("?" * len(filtered_ids))
        query = f"SELECT COUNT(*) AS n FROM bioactivity_records WHERE compound_id IN ({placeholders})"
        return int(pd.read_sql_query(query, conn, params=filtered_ids)["n"][0])
    finally:
        conn.close()


def calculate_workspace_health(compounds_df: pd.DataFrame):
    compounds_df = enrich_compounds_dataframe(compounds_df)
    if compounds_df.empty:
        return {
            "structure_ready": 0,
            "reference_ready": 0,
            "external_ready": 0,
            "submission_ready": 0,
            "bioactivity_ready": 0,
        }

    structure_ready = compounds_df[
        compounds_df["smiles"].fillna("").astype(str).str.strip().ne("")
        | compounds_df["inchi"].fillna("").astype(str).str.strip().ne("")
        | compounds_df["inchikey"].fillna("").astype(str).str.strip().ne("")
    ]
    reference_ready = compounds_df[
        compounds_df["doi"].fillna("").astype(str).str.strip().ne("")
        | compounds_df["journal_name"].fillna("").astype(str).str.strip().ne("")
    ]

    spectra_df = load_all_spectra_files()
    external_ready_ids = set(
        spectra_df[spectra_df["file_path"].fillna("").astype(str).apply(is_external_url)]["compound_id"].tolist()
    )
    bioactivity_df = load_all_bioactivity_data()
    bioactivity_ready_ids = set(bioactivity_df["compound_id"].tolist()) if not bioactivity_df.empty else set()
    submission_ready = compounds_df[
        compounds_df["trivial_name"].fillna("").astype(str).str.strip().ne("")
        & compounds_df["compound_class"].fillna("").astype(str).str.strip().ne("")
        & (
            compounds_df["source_category"].fillna("").astype(str).str.strip().ne("")
            | compounds_df["source_organism"].fillna("").astype(str).str.strip().ne("")
            | compounds_df["source_material"].fillna("").astype(str).str.strip().ne("")
        )
    ]

    return {
        "structure_ready": int(len(structure_ready)),
        "reference_ready": int(len(reference_ready)),
        "external_ready": int(len(external_ready_ids)),
        "submission_ready": int(len(submission_ready)),
        "bioactivity_ready": int(len(bioactivity_ready_ids)),
    }

# =========================
# UI helpers
# =========================
def section_header(title, subtitle=""):
    st.markdown(f'<div class="section-title">{title}</div>', unsafe_allow_html=True)
    if subtitle:
        st.markdown(f'<div class="section-subtitle">{subtitle}</div>', unsafe_allow_html=True)

def render_metric_card(label, value, col):
    with col:
        st.markdown(
            f"""
            <div class="metric-card">
                <div class="metric-card-label">{label}</div>
                <div class="metric-card-value">{value}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )


def render_clean_stat(label, value, col):
    with col:
        st.markdown(
            f"""
            <div class="clean-stat">
                <div class="clean-stat-label">{label}</div>
                <div class="clean-stat-value">{value}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )


def render_helper_card(title, text):
    st.markdown(
        f"""
        <div class="helper-card">
            <div class="helper-title">{title}</div>
            <div class="helper-text">{text}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_selector_card(title, subtitle):
    st.markdown(
        f"""
        <div class="selector-card">
            <div class="selector-title">{title}</div>
            <div class="selector-subtitle">{subtitle}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_external_link_card(label: str, url: str, note: str | None = None):
    st.markdown('<div class="panel-card">', unsafe_allow_html=True)
    st.markdown(f"**{label}**")
    if is_google_drive_url(url):
        st.markdown(f"[Open file]({url})")
        st.markdown(f"[Download file]({google_drive_download_url(url)})")
    else:
        st.markdown(f"[Open external file]({url})")
    if note:
        st.caption(note)
    st.markdown('</div>', unsafe_allow_html=True)


def render_dashboard_bar_chart(df: pd.DataFrame, x_col: str, y_col: str, color_hex: str = "#61D8ED"):
    if df.empty:
        st.info("No data available.")
        return

    chart_df = df[[x_col, y_col]].copy()
    chart_df[x_col] = chart_df[x_col].fillna("Uncategorized").astype(str).str.strip()
    chart_df[x_col] = chart_df[x_col].replace("", "Uncategorized")
    chart_df[y_col] = pd.to_numeric(chart_df[y_col], errors="coerce").fillna(0)
    chart_df = chart_df.sort_values(by=y_col, ascending=False).set_index(x_col)

    st.bar_chart(chart_df[[y_col]], color=color_hex)


def render_sidebar_workspace_summary(active_section: str, all_compounds_df: pd.DataFrame):
    all_compounds_df = enrich_compounds_dataframe(all_compounds_df)
    total_compounds = len(all_compounds_df)
    available_ids = all_compounds_df["id"].tolist() if "id" in all_compounds_df.columns else []
    proton_count, carbon_count, spectra_count = count_related_records(available_ids)
    bioactivity_count = count_bioactivity_records(available_ids)
    health = calculate_workspace_health(all_compounds_df)
    active_copy = NAV_SECTION_COPY.get(active_section, {"title": active_section, "summary": ""})

    if SIDEBAR_LOGO_PATH.exists():
        st.markdown('<div class="sidebar-logo-shell">', unsafe_allow_html=True)
        st.image(str(SIDEBAR_LOGO_PATH), width="stretch")
        st.markdown('</div>', unsafe_allow_html=True)

    st.markdown('<div class="sidebar-brand">', unsafe_allow_html=True)
    st.markdown(
        """
        <div class="sidebar-brand-title">Natural Products Spectral Database</div>
        <div class="sidebar-brand-subtitle">
            From raw spectra to verified structures — organized, connected, and accessible.
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.markdown("</div>", unsafe_allow_html=True)

    st.markdown(
        f"""
        <div class="sidebar-stats">
            <div class="sidebar-stat">
                <div class="sidebar-stat-value">{total_compounds}</div>
                <div class="sidebar-stat-label">Compounds</div>
            </div>
            <div class="sidebar-stat">
                <div class="sidebar-stat-value">{proton_count}</div>
                <div class="sidebar-stat-label">1H Peaks</div>
            </div>
            <div class="sidebar-stat">
                <div class="sidebar-stat-value">{carbon_count}</div>
                <div class="sidebar-stat-label">13C Peaks</div>
            </div>
            <div class="sidebar-stat">
                <div class="sidebar-stat-value">{spectra_count}</div>
                <div class="sidebar-stat-label">Spectra Files</div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.markdown(
        f"""
        <div class="sidebar-note">
            <strong>{active_copy['title']}</strong><br><br>
            {active_copy['summary']}
        </div>
        """,
        unsafe_allow_html=True,
    )

    current_user = maybe_blank(st.session_state.get("npdb_username")) or "Approved user"
    current_role = maybe_blank(st.session_state.get("npdb_role")) or "viewer"
    st.caption(f"Signed in as {current_user} ({current_role})")
    st.caption(f"Data backend: {'Supabase cloud' if use_supabase_backend() else 'Local SQLite'}")
    st.caption(
        f"Structure-ready: {health['structure_ready']} | Reference-ready: {health['reference_ready']} | "
        f"Drive-linked: {health['external_ready']} | Submission-ready: {health['submission_ready']}"
    )
    st.caption(f"Bioactivity records: {bioactivity_count} | Bioactivity-linked compounds: {health.get('bioactivity_ready', 0)}")


def show_section_banner(image_path: Path, caption: str | None = None):
    if not image_path.exists():
        return
    st.markdown('<div class="section-banner">', unsafe_allow_html=True)
    st.image(str(image_path), width="stretch")
    st.markdown('</div>', unsafe_allow_html=True)
    if caption:
        st.caption(caption)


def render_batch_import_workspace():
    section_header(
        "Batch Import",
        "Use these ready-to-fill CSV templates to add compounds, 1H peaks, 13C peaks, and spectra records without guessing column names.",
    )

    write_batch_import_templates()
    template_map = build_batch_import_template_map()

    render_helper_card(
        "Why this import page matters",
        "The sample rows already follow your current database structure. Replace the values in rows marked TEMPLATE_, keep the column headers unchanged, then upload the CSV back into this workspace.",
    )

    existing_names = load_all_compounds()["trivial_name"].fillna("").astype(str).tolist()
    if existing_names:
        st.caption(
            "Exact compound names currently available for peak/file imports: "
            + ", ".join(existing_names[:5])
        )

    tabs = st.tabs(["Compounds", "1H Peaks", "13C Peaks", "Spectra Files"])
    import_specs = [
        (
            "compounds_batch_import_template.csv",
            COMPOUND_IMPORT_COLUMNS,
            ["trivial_name"],
            "Create new compound records in one pass. This is the best place to add metadata-heavy submissions from papers or lab notebooks.",
            import_compounds_from_dataframe,
        ),
        (
            "proton_nmr_batch_import_template.csv",
            PROTON_IMPORT_COLUMNS,
            ["delta_ppm", "assignment"],
            "Add many 1H NMR peaks at once. Use either compound_id or an exact compound_name already present in the database.",
            import_proton_from_dataframe,
        ),
        (
            "carbon_nmr_batch_import_template.csv",
            CARBON_IMPORT_COLUMNS,
            ["delta_ppm", "assignment"],
            "Add many 13C NMR peaks at once. Use either compound_id or an exact compound_name already present in the database.",
            import_carbon_from_dataframe,
        ),
        (
            "spectra_files_batch_import_template.csv",
            SPECTRA_IMPORT_COLUMNS,
            ["spectrum_type", "file_path"],
            "Register many spectra file links quickly. The file_path can point to an existing relative path inside data/spectra or to an external URL such as a Google Drive sharing link.",
            import_spectra_from_dataframe,
        ),
    ]

    for tab, (filename, expected_columns, required_columns, helper_text, import_function) in zip(tabs, import_specs):
        with tab:
            template_df = template_map[filename]
            template_path = TEMPLATES_DIR / filename

            render_helper_card("Template guide", helper_text)
            st.download_button(
                label=f"Download {filename}",
                data=dataframe_to_csv_bytes(template_df),
                file_name=filename,
                mime="text/csv",
                key=f"download_{filename}",
            )
            st.caption(f"Local template file: {template_path}")
            st.dataframe(template_df, width="stretch", hide_index=True)

            uploaded_file = st.file_uploader(
                f"Upload completed {filename}",
                type=["csv"],
                key=f"upload_{filename}",
            )

            if uploaded_file is None:
                continue

            try:
                uploaded_df = pd.read_csv(uploaded_file).fillna("")
            except Exception as exc:
                st.error(f"Could not read the CSV file: {exc}")
                continue

            missing_required_columns = validate_import_columns(uploaded_df, required_columns)
            if missing_required_columns:
                st.error(
                    "Missing required column(s): "
                    + ", ".join(missing_required_columns)
                    + ". Keep the original template headers unchanged."
                )
                continue

            preview_df = align_import_columns(uploaded_df, expected_columns)
            st.markdown("**Preview before import**")
            st.dataframe(preview_df, width="stretch", hide_index=True)

            if st.button(f"Import {filename}", key=f"import_{filename}", use_container_width=True):
                inserted, skipped, errors = import_function(uploaded_df)
                status, headline = summarize_import_result(inserted, skipped, errors)
                getattr(st, status)(headline)

                if errors:
                    note_df = pd.DataFrame({"Import notes": errors[:30]})
                    st.dataframe(note_df, width="stretch", hide_index=True)

def render_kv(title, value):
    st.markdown(
        f"""
        <div class="kv-card">
            <div class="kv-title">{title}</div>
            <div class="kv-value">{clean_text(value)}</div>
        </div>
        """,
        unsafe_allow_html=True
    )

def render_compound_card(row):
    title = clean_text(row["trivial_name"])
    formula = clean_text(row["molecular_formula"])
    compound_class = clean_text(row["compound_class"])
    subclass = clean_text(row["compound_subclass"])
    source_summary = clean_text(source_summary_from_record(row))
    sample_code = clean_text(row["sample_code"])
    st.markdown('<div class="compound-card">', unsafe_allow_html=True)
    preview_col, info_col = st.columns([1, 3.7])
    with preview_col:
        source_value = row.get("structure_image_path")
        standardized_image = load_standardized_structure_source(source_value, size=(360, 260))
        if standardized_image is not None:
            st.image(standardized_image, width="stretch")
        elif source_value and is_external_url(str(source_value).strip()):
            safe_url = str(source_value).strip().replace('"', "&quot;")
            st.markdown(
                f'<div class="compound-thumb-shell"><img src="{safe_url}" alt="{title} structure"/></div>',
                unsafe_allow_html=True,
            )
        else:
            render_structure_preview(row.get("smiles"), caption=None, empty_message=False, size=(360, 260))
    with info_col:
        st.markdown(
            f"""
            <div class="result-title">{title}</div>
            <div class="result-subtitle">{formula}</div>
            <div class="info-chip-row">
                <span class="info-chip">Class: {compound_class}</span>
                <span class="info-chip">Subclass: {subclass}</span>
                <span class="info-chip">Source: {source_summary}</span>
                <span class="info-chip">Sample: {sample_code}</span>
            </div>
            """,
            unsafe_allow_html=True,
        )
    st.markdown('</div>', unsafe_allow_html=True)

def show_app_header():
    st.markdown('<div class="hero-shell">', unsafe_allow_html=True)
    st.markdown('<div class="hero-banner-wrap">', unsafe_allow_html=True)
    if HEADER_LOGO_PATH.exists():
        st.image(str(HEADER_LOGO_PATH), width="stretch")
    else:
        st.markdown(
            """
            <div class="hero-image-fallback">
                <div class="result-title">Header image not found</div>
                <div class="result-subtitle">Place the file at data/branding/logo_header_web.png</div>
            </div>
            """,
            unsafe_allow_html=True
        )
    st.markdown('</div>', unsafe_allow_html=True)

    hero_col1, hero_col2, hero_col3 = st.columns([1.1, 0.9, 0.9])
    with hero_col1:
        if st.button("Browse Dashboard", use_container_width=True, key="hero_overview_btn"):
            set_main_nav("Dashboard")
            st.rerun()
    with hero_col2:
        if st.button("Search Spectra", use_container_width=True, key="hero_search_btn"):
            set_main_nav("Search & Match")
            st.rerun()
    with hero_col3:
        if st.button("Start Submission", use_container_width=True, key="hero_add_btn"):
            set_main_nav("Compound Workspace")
            set_compound_page("New Submission" if can_edit_database() else "Browse Record")
            st.rerun()

# =========================
# Data loading
# =========================
@st.cache_data(show_spinner=False)
def load_all_compounds():
    conn = get_connection()
    query = """
        SELECT id, trivial_name, iupac_name, molecular_formula,
               smiles, inchi, inchikey,
               compound_class, compound_subclass,
               source_category, source_organism, source_material,
               sample_code, collection_location,
               gps_coordinates, depth_m, uv_data, ftir_data, cd_data,
               optical_rotation, melting_point, crystallization_method,
               structure_image_path, journal_name, article_title, publication_year,
               volume, issue, pages, doi, ccdc_number,
               molecular_weight, hrms_data, data_source, note,
               created_at, updated_at
        FROM compounds
        ORDER BY id ASC
    """
    df = pd.read_sql_query(query, conn)
    conn.close()
    return enrich_compounds_dataframe(df)

@st.cache_data(show_spinner=False)
def load_compound_row(compound_id):
    conn = get_connection()
    query = """
        SELECT id, trivial_name, iupac_name, molecular_formula,
               smiles, inchi, inchikey,
               compound_class, compound_subclass,
               source_category, source_organism, source_material,
               sample_code, collection_location,
               gps_coordinates, depth_m, uv_data, ftir_data, cd_data,
               optical_rotation, melting_point, crystallization_method,
               structure_image_path, journal_name, article_title, publication_year,
               volume, issue, pages, doi, ccdc_number,
               molecular_weight, hrms_data, data_source, note,
               created_at, updated_at
        FROM compounds
        WHERE id = ?
    """
    df = pd.read_sql_query(query, conn, params=(compound_id,))
    conn.close()
    return enrich_compounds_dataframe(df)

@st.cache_data(show_spinner=False)
def load_proton_data(compound_id):
    conn = get_connection()
    query = """
        SELECT id, compound_id, delta_ppm, multiplicity, j_value, proton_count,
               assignment, solvent, instrument_mhz, note
        FROM proton_nmr
        WHERE compound_id = ?
        ORDER BY delta_ppm DESC
    """
    df = pd.read_sql_query(query, conn, params=(compound_id,))
    conn.close()
    return df

@st.cache_data(show_spinner=False)
def load_all_proton_data():
    conn = get_connection()
    query = """
        SELECT p.id, p.compound_id, c.trivial_name,
               p.delta_ppm, p.multiplicity, p.j_value, p.proton_count,
               p.assignment, p.solvent, p.instrument_mhz, p.note
        FROM proton_nmr p
        LEFT JOIN compounds c ON p.compound_id = c.id
        ORDER BY p.id ASC
    """
    df = pd.read_sql_query(query, conn)
    conn.close()
    return df

@st.cache_data(show_spinner=False)
def load_proton_row(proton_id):
    conn = get_connection()
    query = """
        SELECT id, compound_id, delta_ppm, multiplicity, j_value, proton_count,
               assignment, solvent, instrument_mhz, note
        FROM proton_nmr
        WHERE id = ?
    """
    df = pd.read_sql_query(query, conn, params=(proton_id,))
    conn.close()
    return df

@st.cache_data(show_spinner=False)
def load_carbon_data(compound_id):
    conn = get_connection()
    query = """
        SELECT id, compound_id, delta_ppm, carbon_type, assignment, solvent,
               instrument_mhz, note
        FROM carbon_nmr
        WHERE compound_id = ?
        ORDER BY delta_ppm DESC
    """
    df = pd.read_sql_query(query, conn, params=(compound_id,))
    conn.close()
    return df

@st.cache_data(show_spinner=False)
def load_all_carbon_data():
    conn = get_connection()
    query = """
        SELECT n.id, n.compound_id, c.trivial_name,
               n.delta_ppm, n.carbon_type, n.assignment, n.solvent,
               n.instrument_mhz, n.note
        FROM carbon_nmr n
        LEFT JOIN compounds c ON n.compound_id = c.id
        ORDER BY n.id ASC
    """
    df = pd.read_sql_query(query, conn)
    conn.close()
    return df

@st.cache_data(show_spinner=False)
def load_carbon_row(carbon_id):
    conn = get_connection()
    query = """
        SELECT id, compound_id, delta_ppm, carbon_type, assignment, solvent,
               instrument_mhz, note
        FROM carbon_nmr
        WHERE id = ?
    """
    df = pd.read_sql_query(query, conn, params=(carbon_id,))
    conn.close()
    return df

@st.cache_data(show_spinner=False)
def load_spectra_files(compound_id):
    conn = get_connection()
    query = """
        SELECT id, compound_id, spectrum_type, file_path, note
        FROM spectra_files
        WHERE compound_id = ?
        ORDER BY id ASC
    """
    df = pd.read_sql_query(query, conn, params=(compound_id,))
    conn.close()
    return df

@st.cache_data(show_spinner=False)
def load_all_spectra_files():
    conn = get_connection()
    query = """
        SELECT s.id, s.compound_id, c.trivial_name,
               s.spectrum_type, s.file_path, s.note
        FROM spectra_files s
        LEFT JOIN compounds c ON s.compound_id = c.id
        ORDER BY s.id ASC
    """
    df = pd.read_sql_query(query, conn)
    conn.close()
    return df

@st.cache_data(show_spinner=False)
def load_spectrum_file_row(file_id):
    conn = get_connection()
    query = """
        SELECT id, compound_id, spectrum_type, file_path, note
        FROM spectra_files
        WHERE id = ?
    """
    df = pd.read_sql_query(query, conn, params=(file_id,))
    conn.close()
    return df


@st.cache_data(show_spinner=False)
def load_bioactivity_data(compound_id):
    conn = get_connection()
    query = """
        SELECT id, compound_id, activity_label, target_name, target_category, assay_type,
               potency_type, potency_relation, potency_value, potency_unit, outcome,
               assay_medium, selectivity, assay_source, note
        FROM bioactivity_records
        WHERE compound_id = ?
        ORDER BY id ASC
    """
    df = pd.read_sql_query(query, conn, params=(compound_id,))
    conn.close()
    return df


@st.cache_data(show_spinner=False)
def load_all_bioactivity_data():
    conn = get_connection()
    query = """
        SELECT b.id, b.compound_id, c.trivial_name,
               b.activity_label, b.target_name, b.target_category, b.assay_type,
               b.potency_type, b.potency_relation, b.potency_value, b.potency_unit, b.outcome,
               b.assay_medium, b.selectivity, b.assay_source, b.note
        FROM bioactivity_records b
        LEFT JOIN compounds c ON b.compound_id = c.id
        ORDER BY b.id ASC
    """
    df = pd.read_sql_query(query, conn)
    conn.close()
    return df


@st.cache_data(show_spinner=False)
def load_bioactivity_row(bioactivity_id):
    conn = get_connection()
    query = """
        SELECT id, compound_id, activity_label, target_name, target_category, assay_type,
               potency_type, potency_relation, potency_value, potency_unit, outcome,
               assay_medium, selectivity, assay_source, note
        FROM bioactivity_records
        WHERE id = ?
    """
    df = pd.read_sql_query(query, conn, params=(bioactivity_id,))
    conn.close()
    return df

# =========================
# Insert / update / delete functions
# =========================
def insert_compound_record(
    trivial_name,
    iupac_name,
    molecular_formula,
    compound_class,
    compound_subclass,
    smiles,
    inchi,
    inchikey,
    source_category,
    source_organism,
    source_material,
    sample_code,
    collection_location,
    gps_coordinates,
    depth_m,
    uv_data,
    ftir_data,
    cd_data,
    optical_rotation,
    melting_point,
    crystallization_method,
    structure_image_path,
    journal_name,
    article_title,
    publication_year,
    volume,
    issue,
    pages,
    doi,
    ccdc_number,
    molecular_weight,
    hrms_data,
    data_source,
    note
):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        INSERT INTO compounds (
            trivial_name,
            iupac_name,
            molecular_formula,
            compound_class,
            compound_subclass,
            smiles,
            inchi,
            inchikey,
            source_category,
            source_organism,
            source_material,
            sample_code,
            collection_location,
            gps_coordinates,
            depth_m,
            uv_data,
            ftir_data,
            cd_data,
            optical_rotation,
            melting_point,
            crystallization_method,
            structure_image_path,
            journal_name,
            article_title,
            publication_year,
            volume,
            issue,
            pages,
            doi,
            ccdc_number,
            molecular_weight,
            hrms_data,
            data_source,
            note
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        trivial_name,
        iupac_name,
        molecular_formula,
        compound_class,
        compound_subclass,
        smiles,
        inchi,
        inchikey,
        source_category,
        source_organism,
        source_material,
        sample_code,
        collection_location,
        gps_coordinates,
        depth_m,
        uv_data,
        ftir_data,
        cd_data,
        optical_rotation,
        melting_point,
        crystallization_method,
        structure_image_path,
        journal_name,
        article_title,
        publication_year,
        volume,
        issue,
        pages,
        doi,
        ccdc_number,
        molecular_weight,
        hrms_data,
        data_source,
        note
    ))

    new_id = cursor.lastrowid
    conn.commit()
    invalidate_cached_views()
    conn.close()
    return new_id

def update_compound_record(
    compound_id,
    trivial_name,
    iupac_name,
    molecular_formula,
    compound_class,
    compound_subclass,
    smiles,
    inchi,
    inchikey,
    source_category,
    source_organism,
    source_material,
    sample_code,
    collection_location,
    gps_coordinates,
    depth_m,
    uv_data,
    ftir_data,
    cd_data,
    optical_rotation,
    melting_point,
    crystallization_method,
    structure_image_path,
    journal_name,
    article_title,
    publication_year,
    volume,
    issue,
    pages,
    doi,
    ccdc_number,
    molecular_weight,
    hrms_data,
    data_source,
    note
):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        UPDATE compounds
        SET trivial_name = ?,
            iupac_name = ?,
            molecular_formula = ?,
            compound_class = ?,
            compound_subclass = ?,
            smiles = ?,
            inchi = ?,
            inchikey = ?,
            source_category = ?,
            source_organism = ?,
            source_material = ?,
            sample_code = ?,
            collection_location = ?,
            gps_coordinates = ?,
            depth_m = ?,
            uv_data = ?,
            ftir_data = ?,
            cd_data = ?,
            optical_rotation = ?,
            melting_point = ?,
            crystallization_method = ?,
            structure_image_path = ?,
            journal_name = ?,
            article_title = ?,
            publication_year = ?,
            volume = ?,
            issue = ?,
            pages = ?,
            doi = ?,
            ccdc_number = ?,
            molecular_weight = ?,
            hrms_data = ?,
            data_source = ?,
            note = ?,
            updated_at = CURRENT_TIMESTAMP
        WHERE id = ?
    """, (
        trivial_name,
        iupac_name,
        molecular_formula,
        compound_class,
        compound_subclass,
        smiles,
        inchi,
        inchikey,
        source_category,
        source_organism,
        source_material,
        sample_code,
        collection_location,
        gps_coordinates,
        depth_m,
        uv_data,
        ftir_data,
        cd_data,
        optical_rotation,
        melting_point,
        crystallization_method,
        structure_image_path,
        journal_name,
        article_title,
        publication_year,
        volume,
        issue,
        pages,
        doi,
        ccdc_number,
        molecular_weight,
        hrms_data,
        data_source,
        note,
        compound_id
    ))

    conn.commit()

    invalidate_cached_views()
    conn.close()

def delete_compound_record(compound_id):
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("DELETE FROM bioactivity_records WHERE compound_id = ?", (compound_id,))
        cursor.execute("DELETE FROM proton_nmr WHERE compound_id = ?", (compound_id,))
        cursor.execute("DELETE FROM carbon_nmr WHERE compound_id = ?", (compound_id,))
        cursor.execute("DELETE FROM spectra_files WHERE compound_id = ?", (compound_id,))
        cursor.execute("DELETE FROM compounds WHERE id = ?", (compound_id,))
        conn.commit()
        invalidate_cached_views()
    finally:
        conn.close()

def insert_proton_record(
    compound_id,
    delta_ppm,
    multiplicity,
    j_value,
    proton_count,
    assignment,
    solvent,
    instrument_mhz,
    note
):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        INSERT INTO proton_nmr (
            compound_id,
            delta_ppm,
            multiplicity,
            j_value,
            proton_count,
            assignment,
            solvent,
            instrument_mhz,
            note
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        compound_id,
        delta_ppm,
        multiplicity,
        j_value,
        proton_count,
        assignment,
        solvent,
        instrument_mhz,
        note
    ))

    new_id = cursor.lastrowid
    conn.commit()
    invalidate_cached_views()
    conn.close()
    return new_id

def update_proton_record(
    proton_id,
    compound_id,
    delta_ppm,
    multiplicity,
    j_value,
    proton_count,
    assignment,
    solvent,
    instrument_mhz,
    note
):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        UPDATE proton_nmr
        SET compound_id = ?,
            delta_ppm = ?,
            multiplicity = ?,
            j_value = ?,
            proton_count = ?,
            assignment = ?,
            solvent = ?,
            instrument_mhz = ?,
            note = ?
        WHERE id = ?
    """, (
        compound_id,
        delta_ppm,
        multiplicity,
        j_value,
        proton_count,
        assignment,
        solvent,
        instrument_mhz,
        note,
        proton_id
    ))

    conn.commit()

    invalidate_cached_views()
    conn.close()

def delete_proton_record_by_id(proton_id):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM proton_nmr WHERE id = ?", (proton_id,))
    conn.commit()
    invalidate_cached_views()
    conn.close()

def insert_carbon_record(
    compound_id,
    delta_ppm,
    carbon_type,
    assignment,
    solvent,
    instrument_mhz,
    note
):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        INSERT INTO carbon_nmr (
            compound_id,
            delta_ppm,
            carbon_type,
            assignment,
            solvent,
            instrument_mhz,
            note
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (
        compound_id,
        delta_ppm,
        carbon_type,
        assignment,
        solvent,
        instrument_mhz,
        note
    ))

    new_id = cursor.lastrowid
    conn.commit()
    invalidate_cached_views()
    conn.close()
    return new_id

def update_carbon_record(
    carbon_id,
    compound_id,
    delta_ppm,
    carbon_type,
    assignment,
    solvent,
    instrument_mhz,
    note
):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        UPDATE carbon_nmr
        SET compound_id = ?,
            delta_ppm = ?,
            carbon_type = ?,
            assignment = ?,
            solvent = ?,
            instrument_mhz = ?,
            note = ?
        WHERE id = ?
    """, (
        compound_id,
        delta_ppm,
        carbon_type,
        assignment,
        solvent,
        instrument_mhz,
        note,
        carbon_id
    ))

    conn.commit()

    invalidate_cached_views()
    conn.close()

def delete_carbon_record_by_id(carbon_id):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM carbon_nmr WHERE id = ?", (carbon_id,))
    conn.commit()
    invalidate_cached_views()
    conn.close()

def insert_spectrum_file_record(
    compound_id,
    spectrum_type,
    file_path,
    note
):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        INSERT INTO spectra_files (
            compound_id,
            spectrum_type,
            file_path,
            note
        ) VALUES (?, ?, ?, ?)
    """, (
        compound_id,
        spectrum_type,
        file_path,
        note
    ))

    new_id = cursor.lastrowid
    conn.commit()
    invalidate_cached_views()
    conn.close()
    return new_id

def update_spectrum_file_record(
    file_id,
    compound_id,
    spectrum_type,
    file_path,
    note
):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        UPDATE spectra_files
        SET compound_id = ?,
            spectrum_type = ?,
            file_path = ?,
            note = ?
        WHERE id = ?
    """, (
        compound_id,
        spectrum_type,
        file_path,
        note,
        file_id
    ))

    conn.commit()

    invalidate_cached_views()
    conn.close()

def delete_spectrum_file_record_by_id(file_id):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM spectra_files WHERE id = ?", (file_id,))
    conn.commit()
    invalidate_cached_views()
    conn.close()


def insert_bioactivity_record(
    compound_id,
    activity_label,
    target_name,
    target_category,
    assay_type,
    potency_type,
    potency_relation,
    potency_value,
    potency_unit,
    outcome,
    assay_medium,
    selectivity,
    assay_source,
    note,
):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        INSERT INTO bioactivity_records (
            compound_id, activity_label, target_name, target_category, assay_type,
            potency_type, potency_relation, potency_value, potency_unit, outcome,
            assay_medium, selectivity, assay_source, note
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            compound_id,
            activity_label,
            target_name,
            target_category,
            assay_type,
            potency_type,
            potency_relation,
            potency_value,
            potency_unit,
            outcome,
            assay_medium,
            selectivity,
            assay_source,
            note,
        ),
    )
    new_id = cursor.lastrowid
    conn.commit()
    invalidate_cached_views()
    conn.close()
    return new_id


def update_bioactivity_record(
    bioactivity_id,
    compound_id,
    activity_label,
    target_name,
    target_category,
    assay_type,
    potency_type,
    potency_relation,
    potency_value,
    potency_unit,
    outcome,
    assay_medium,
    selectivity,
    assay_source,
    note,
):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        UPDATE bioactivity_records
        SET compound_id = ?,
            activity_label = ?,
            target_name = ?,
            target_category = ?,
            assay_type = ?,
            potency_type = ?,
            potency_relation = ?,
            potency_value = ?,
            potency_unit = ?,
            outcome = ?,
            assay_medium = ?,
            selectivity = ?,
            assay_source = ?,
            note = ?
        WHERE id = ?
        """,
        (
            compound_id,
            activity_label,
            target_name,
            target_category,
            assay_type,
            potency_type,
            potency_relation,
            potency_value,
            potency_unit,
            outcome,
            assay_medium,
            selectivity,
            assay_source,
            note,
            bioactivity_id,
        ),
    )
    conn.commit()
    invalidate_cached_views()
    conn.close()


def delete_bioactivity_record_by_id(bioactivity_id):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM bioactivity_records WHERE id = ?", (bioactivity_id,))
    conn.commit()
    invalidate_cached_views()
    conn.close()


def is_template_marker(value) -> bool:
    return maybe_blank(value).upper().startswith("TEMPLATE_")


def normalize_import_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    normalized = df.copy()
    normalized.columns = [str(column).strip() for column in normalized.columns]
    return normalized


def align_import_columns(df: pd.DataFrame, expected_columns: list[str]) -> pd.DataFrame:
    aligned = normalize_import_dataframe(df)
    for column in expected_columns:
        if column not in aligned.columns:
            aligned[column] = ""
    return aligned[expected_columns]


def validate_import_columns(df: pd.DataFrame, required_columns: list[str]) -> list[str]:
    normalized_columns = {str(column).strip() for column in df.columns}
    return [column for column in required_columns if column not in normalized_columns]


def resolve_import_compound_id(row, compounds_df: pd.DataFrame) -> int:
    compound_id_text = maybe_blank(row.get("compound_id"))
    if compound_id_text:
        try:
            compound_id = int(float(compound_id_text))
        except ValueError as exc:
            raise ValueError(f"Invalid compound_id: {compound_id_text}") from exc

        matches = compounds_df[compounds_df["id"] == compound_id]
        if matches.empty:
            raise ValueError(f"compound_id {compound_id} was not found in the current database.")
        return compound_id

    compound_name = maybe_blank(row.get("compound_name")) or maybe_blank(row.get("trivial_name"))
    if not compound_name:
        raise ValueError("Provide either compound_id or compound_name.")
    if is_template_marker(compound_name):
        raise LookupError("Template row skipped.")

    matches = compounds_df[
        compounds_df["trivial_name"].fillna("").astype(str).str.casefold() == compound_name.casefold()
    ]
    if matches.empty:
        raise ValueError(f'Compound "{compound_name}" was not found. Use an exact trivial name or compound_id.')
    if len(matches) > 1:
        raise ValueError(f'Multiple compounds matched "{compound_name}". Use compound_id instead.')
    return int(matches.iloc[0]["id"])


def summarize_import_result(inserted: int, skipped: int, errors: list[str]) -> tuple[str, str]:
    if errors:
        status = "warning"
        headline = f"Imported {inserted} row(s), skipped {skipped}, and found {len(errors)} issue(s)."
    elif inserted:
        status = "success"
        headline = f"Imported {inserted} row(s) successfully."
    else:
        status = "info"
        headline = f"No rows were imported. Skipped {skipped} row(s)."
    return status, headline


def build_batch_import_template_map() -> dict[str, pd.DataFrame]:
    compounds_df = load_all_compounds()
    proton_df = load_all_proton_data()
    carbon_df = load_all_carbon_data()
    spectra_df = load_all_spectra_files()

    compound_example = compounds_df.iloc[0].to_dict() if not compounds_df.empty else {}
    proton_example = proton_df.iloc[0].to_dict() if not proton_df.empty else {}
    carbon_example = carbon_df.iloc[0].to_dict() if not carbon_df.empty else {}
    spectra_example = spectra_df.iloc[0].to_dict() if not spectra_df.empty else {}

    compound_row = {column: "" for column in COMPOUND_IMPORT_COLUMNS}
    for column in COMPOUND_IMPORT_COLUMNS:
        compound_row[column] = maybe_blank(compound_example.get(column))
    compound_row["trivial_name"] = "TEMPLATE_Replace_With_Compound_Name"
    compound_row["source_category"] = compound_row["source_category"] or "Sponge"
    compound_row["source_organism"] = compound_row["source_organism"] or "Stylissa sp."
    compound_row["sample_code"] = compound_row["sample_code"] or "NP-001"
    compound_row["data_source"] = compound_row["data_source"] or "Experimental"
    compound_row["note"] = "Delete or replace this template row before import."

    proton_row = {column: "" for column in PROTON_IMPORT_COLUMNS}
    for column in PROTON_IMPORT_COLUMNS:
        proton_row[column] = maybe_blank(proton_example.get(column))
    proton_row["compound_id"] = ""
    proton_row["compound_name"] = "TEMPLATE_Existing_Compound_Name"
    proton_row["note"] = "Delete or replace this template row before import."

    carbon_row = {column: "" for column in CARBON_IMPORT_COLUMNS}
    for column in CARBON_IMPORT_COLUMNS:
        carbon_row[column] = maybe_blank(carbon_example.get(column))
    carbon_row["compound_id"] = ""
    carbon_row["compound_name"] = "TEMPLATE_Existing_Compound_Name"
    carbon_row["note"] = "Delete or replace this template row before import."

    spectra_row = {column: "" for column in SPECTRA_IMPORT_COLUMNS}
    for column in SPECTRA_IMPORT_COLUMNS:
        spectra_row[column] = maybe_blank(spectra_example.get(column))
    spectra_row["compound_id"] = ""
    spectra_row["compound_name"] = "TEMPLATE_Existing_Compound_Name"
    spectra_row["file_path"] = spectra_row["file_path"] or "data/spectra/example_1H.png"
    spectra_row["spectrum_type"] = spectra_row["spectrum_type"] or "1H"
    spectra_row["note"] = "Delete or replace this template row before import."

    return {
        "compounds_batch_import_template.csv": align_import_columns(pd.DataFrame([compound_row]), COMPOUND_IMPORT_COLUMNS),
        "proton_nmr_batch_import_template.csv": align_import_columns(pd.DataFrame([proton_row]), PROTON_IMPORT_COLUMNS),
        "carbon_nmr_batch_import_template.csv": align_import_columns(pd.DataFrame([carbon_row]), CARBON_IMPORT_COLUMNS),
        "spectra_files_batch_import_template.csv": align_import_columns(pd.DataFrame([spectra_row]), SPECTRA_IMPORT_COLUMNS),
    }


def write_batch_import_templates():
    for filename, template_df in build_batch_import_template_map().items():
        template_df.to_csv(TEMPLATES_DIR / filename, index=False)


def import_compounds_from_dataframe(df: pd.DataFrame):
    aligned = align_import_columns(df, COMPOUND_IMPORT_COLUMNS)
    existing_df = load_all_compounds()
    existing_keys = {
        (
            maybe_blank(row["trivial_name"]).casefold(),
            maybe_blank(row["sample_code"]).casefold(),
            maybe_blank(row["doi"]).casefold(),
        )
        for _, row in existing_df.iterrows()
    }

    inserted = 0
    skipped = 0
    errors = []

    for row_number, row in aligned.iterrows():
        display_row = row_number + 2
        trivial_name = maybe_blank(row.get("trivial_name"))
        if not trivial_name:
            skipped += 1
            continue
        if is_template_marker(trivial_name):
            skipped += 1
            continue

        dedupe_key = (
            trivial_name.casefold(),
            maybe_blank(row.get("sample_code")).casefold(),
            maybe_blank(row.get("doi")).casefold(),
        )
        if dedupe_key in existing_keys:
            skipped += 1
            errors.append(f"Row {display_row}: skipped because the compound already exists with the same name/sample/DOI.")
            continue

        depth_value = safe_float_or_none(row.get("depth_m"))
        if maybe_blank(row.get("depth_m")) and depth_value is None:
            errors.append(f"Row {display_row}: depth_m must be a valid number.")
            continue

        molecular_weight_value = safe_float_or_none(row.get("molecular_weight"))
        if maybe_blank(row.get("molecular_weight")) and molecular_weight_value is None:
            errors.append(f"Row {display_row}: molecular_weight must be a valid number.")
            continue

        source_category, source_organism, source_material = infer_source_fields(
            row.get("source_category"),
            row.get("source_organism"),
            row.get("source_material"),
        )

        insert_compound_record(
            trivial_name=trivial_name,
            iupac_name=maybe_blank(row.get("iupac_name")),
            molecular_formula=maybe_blank(row.get("molecular_formula")),
            compound_class=maybe_blank(row.get("compound_class")),
            compound_subclass=maybe_blank(row.get("compound_subclass")),
            smiles=maybe_blank(row.get("smiles")),
            inchi=maybe_blank(row.get("inchi")),
            inchikey=maybe_blank(row.get("inchikey")),
            source_category=source_category,
            source_organism=source_organism,
            source_material=source_material,
            sample_code=maybe_blank(row.get("sample_code")),
            collection_location=maybe_blank(row.get("collection_location")),
            gps_coordinates=maybe_blank(row.get("gps_coordinates")),
            depth_m=depth_value,
            uv_data=maybe_blank(row.get("uv_data")),
            ftir_data=maybe_blank(row.get("ftir_data")),
            cd_data=maybe_blank(row.get("cd_data")),
            optical_rotation=maybe_blank(row.get("optical_rotation")),
            melting_point=maybe_blank(row.get("melting_point")),
            crystallization_method=maybe_blank(row.get("crystallization_method")),
            structure_image_path=maybe_blank(row.get("structure_image_path")),
            journal_name=maybe_blank(row.get("journal_name")),
            article_title=maybe_blank(row.get("article_title")),
            publication_year=maybe_blank(row.get("publication_year")),
            volume=maybe_blank(row.get("volume")),
            issue=maybe_blank(row.get("issue")),
            pages=maybe_blank(row.get("pages")),
            doi=maybe_blank(row.get("doi")),
            ccdc_number=maybe_blank(row.get("ccdc_number")),
            molecular_weight=molecular_weight_value,
            hrms_data=maybe_blank(row.get("hrms_data")),
            data_source=maybe_blank(row.get("data_source")),
            note=maybe_blank(row.get("note")),
        )
        existing_keys.add(dedupe_key)
        inserted += 1

    return inserted, skipped, errors


def import_proton_from_dataframe(df: pd.DataFrame):
    aligned = align_import_columns(df, PROTON_IMPORT_COLUMNS)
    compounds_df = load_all_compounds()
    existing_df = load_all_proton_data()
    existing_keys = {
        (
            int(row["compound_id"]),
            round(float(row["delta_ppm"]), 4),
            maybe_blank(row["assignment"]).casefold(),
        )
        for _, row in existing_df.iterrows()
    }

    inserted = 0
    skipped = 0
    errors = []

    for row_number, row in aligned.iterrows():
        display_row = row_number + 2
        if is_template_marker(row.get("compound_name")):
            skipped += 1
            continue

        try:
            compound_id = resolve_import_compound_id(row, compounds_df)
        except LookupError:
            skipped += 1
            continue
        except ValueError as exc:
            errors.append(f"Row {display_row}: {exc}")
            continue

        assignment = maybe_blank(row.get("assignment"))
        delta_text = maybe_blank(row.get("delta_ppm"))
        if not delta_text or not assignment:
            errors.append(f"Row {display_row}: delta_ppm and assignment are required.")
            continue

        delta_value = safe_float_or_none(delta_text)
        if delta_value is None:
            errors.append(f"Row {display_row}: delta_ppm must be a valid number.")
            continue

        instrument_value = safe_float_or_none(row.get("instrument_mhz"))
        if maybe_blank(row.get("instrument_mhz")) and instrument_value is None:
            errors.append(f"Row {display_row}: instrument_mhz must be a valid number.")
            continue

        dedupe_key = (compound_id, round(delta_value, 4), assignment.casefold())
        if dedupe_key in existing_keys:
            skipped += 1
            errors.append(f"Row {display_row}: skipped duplicate 1H peak for the same compound, shift, and assignment.")
            continue

        insert_proton_record(
            compound_id=compound_id,
            delta_ppm=delta_value,
            multiplicity=maybe_blank(row.get("multiplicity")),
            j_value=maybe_blank(row.get("j_value")),
            proton_count=maybe_blank(row.get("proton_count")),
            assignment=assignment,
            solvent=maybe_blank(row.get("solvent")),
            instrument_mhz=instrument_value,
            note=maybe_blank(row.get("note")),
        )
        existing_keys.add(dedupe_key)
        inserted += 1

    return inserted, skipped, errors


def import_carbon_from_dataframe(df: pd.DataFrame):
    aligned = align_import_columns(df, CARBON_IMPORT_COLUMNS)
    compounds_df = load_all_compounds()
    existing_df = load_all_carbon_data()
    existing_keys = {
        (
            int(row["compound_id"]),
            round(float(row["delta_ppm"]), 4),
            maybe_blank(row["assignment"]).casefold(),
        )
        for _, row in existing_df.iterrows()
    }

    inserted = 0
    skipped = 0
    errors = []

    for row_number, row in aligned.iterrows():
        display_row = row_number + 2
        if is_template_marker(row.get("compound_name")):
            skipped += 1
            continue

        try:
            compound_id = resolve_import_compound_id(row, compounds_df)
        except LookupError:
            skipped += 1
            continue
        except ValueError as exc:
            errors.append(f"Row {display_row}: {exc}")
            continue

        assignment = maybe_blank(row.get("assignment"))
        delta_text = maybe_blank(row.get("delta_ppm"))
        if not delta_text or not assignment:
            errors.append(f"Row {display_row}: delta_ppm and assignment are required.")
            continue

        delta_value = safe_float_or_none(delta_text)
        if delta_value is None:
            errors.append(f"Row {display_row}: delta_ppm must be a valid number.")
            continue

        instrument_value = safe_float_or_none(row.get("instrument_mhz"))
        if maybe_blank(row.get("instrument_mhz")) and instrument_value is None:
            errors.append(f"Row {display_row}: instrument_mhz must be a valid number.")
            continue

        dedupe_key = (compound_id, round(delta_value, 4), assignment.casefold())
        if dedupe_key in existing_keys:
            skipped += 1
            errors.append(f"Row {display_row}: skipped duplicate 13C peak for the same compound, shift, and assignment.")
            continue

        insert_carbon_record(
            compound_id=compound_id,
            delta_ppm=delta_value,
            carbon_type=maybe_blank(row.get("carbon_type")),
            assignment=assignment,
            solvent=maybe_blank(row.get("solvent")),
            instrument_mhz=instrument_value,
            note=maybe_blank(row.get("note")),
        )
        existing_keys.add(dedupe_key)
        inserted += 1

    return inserted, skipped, errors


def import_spectra_from_dataframe(df: pd.DataFrame):
    aligned = align_import_columns(df, SPECTRA_IMPORT_COLUMNS)
    compounds_df = load_all_compounds()
    existing_df = load_all_spectra_files()
    existing_keys = {
        (
            int(row["compound_id"]),
            maybe_blank(row["spectrum_type"]).casefold(),
            maybe_blank(row["file_path"]).casefold(),
        )
        for _, row in existing_df.iterrows()
    }

    inserted = 0
    skipped = 0
    errors = []

    for row_number, row in aligned.iterrows():
        display_row = row_number + 2
        if is_template_marker(row.get("compound_name")):
            skipped += 1
            continue

        try:
            compound_id = resolve_import_compound_id(row, compounds_df)
        except LookupError:
            skipped += 1
            continue
        except ValueError as exc:
            errors.append(f"Row {display_row}: {exc}")
            continue

        spectrum_type = maybe_blank(row.get("spectrum_type"))
        file_path = maybe_blank(row.get("file_path"))
        if not spectrum_type or not file_path:
            errors.append(f"Row {display_row}: spectrum_type and file_path are required.")
            continue

        validation_errors, validation_warnings = validate_spectrum_entry(file_path, spectrum_type)
        if validation_errors:
            errors.extend([f"Row {display_row}: {message}" for message in validation_errors])
            continue
        errors.extend([f"Row {display_row}: note - {message}" for message in validation_warnings])

        dedupe_key = (compound_id, spectrum_type.casefold(), file_path.casefold())
        if dedupe_key in existing_keys:
            skipped += 1
            errors.append(f"Row {display_row}: skipped duplicate spectra file entry.")
            continue

        insert_spectrum_file_record(
            compound_id=compound_id,
            spectrum_type=spectrum_type,
            file_path=file_path,
            note=maybe_blank(row.get("note")),
        )
        existing_keys.add(dedupe_key)
        inserted += 1

    return inserted, skipped, errors

# =========================
# Similarity search helpers
# =========================
def get_db_signature():
    if not DB_PATH.exists():
        return 0.0
    return DB_PATH.stat().st_mtime


@st.cache_data(show_spinner=False)
def load_search_index(_db_signature: float):
    conn = get_connection()
    try:
        compounds_df = pd.read_sql_query(
            """
            SELECT id, trivial_name, sample_code, molecular_formula, smiles, inchi, inchikey,
                   source_category, source_organism, source_material,
                   compound_class, compound_subclass, data_source
            FROM compounds
            ORDER BY id ASC
            """,
            conn,
        )
        proton_df = pd.read_sql_query(
            """
            SELECT compound_id, delta_ppm
            FROM proton_nmr
            ORDER BY compound_id ASC, delta_ppm DESC
            """,
            conn,
        )
        carbon_df = pd.read_sql_query(
            """
            SELECT compound_id, delta_ppm
            FROM carbon_nmr
            ORDER BY compound_id ASC, delta_ppm DESC
            """,
            conn,
        )
    finally:
        conn.close()

    compounds_df = enrich_compounds_dataframe(compounds_df)

    proton_groups = {}
    carbon_groups = {}

    if not proton_df.empty:
        proton_groups = proton_df.groupby("compound_id")["delta_ppm"].apply(list).to_dict()
    if not carbon_df.empty:
        carbon_groups = carbon_df.groupby("compound_id")["delta_ppm"].apply(list).to_dict()

    search_index = []
    for _, row in compounds_df.iterrows():
        compound_id = int(row["id"])
        search_index.append(
            {
                "compound_id": compound_id,
                "trivial_name": row["trivial_name"],
                "sample_code": row["sample_code"],
                "molecular_formula": row["molecular_formula"],
                "source_category": row.get("source_category"),
                "source_organism": row.get("source_organism"),
                "source_material": row["source_material"],
                "compound_class": row["compound_class"],
                "compound_subclass": row["compound_subclass"],
                "data_source": row["data_source"],
                "proton_peaks": proton_groups.get(compound_id, []),
                "carbon_peaks": carbon_groups.get(compound_id, []),
            }
        )

    return search_index


def score_peak_matches(query_peaks, db_peaks, tolerance):
    matches = find_best_matches(query_peaks, db_peaks, tolerance)
    match_count = len(matches)
    total_query = len(query_peaks)
    db_peak_count = len(db_peaks)
    query_coverage = (match_count / total_query) if total_query else 0.0
    db_coverage = (match_count / db_peak_count) if db_peak_count else 0.0
    avg_difference = None
    closeness = 0.0

    if matches:
        avg_difference = sum(diff for _, _, diff in matches) / match_count
        if tolerance > 0:
            closeness = max(0.0, 1 - (avg_difference / tolerance))
        elif avg_difference == 0:
            closeness = 1.0

    score = ((query_coverage * 0.65) + (db_coverage * 0.20) + (closeness * 0.15)) * 100

    return {
        "matches": matches,
        "match_count": match_count,
        "total_query": total_query,
        "db_peak_count": db_peak_count,
        "query_coverage": query_coverage,
        "db_coverage": db_coverage,
        "avg_difference": avg_difference,
        "score": score,
    }


def sort_similarity_results(results, score_key="score"):
    return sorted(
        results,
        key=lambda item: (
            item.get(score_key, 0.0),
            item.get("match_count", 0),
            item.get("query_coverage", 0.0),
            -(item.get("avg_difference") if item.get("avg_difference") is not None else 9999),
        ),
        reverse=True,
    )


def search_similarity_13c(query_peaks, tolerance):
    results = []
    search_index = load_search_index(get_db_signature())

    for item in search_index:
        metrics = score_peak_matches(query_peaks, item["carbon_peaks"], tolerance)
        results.append(
            {
                **item,
                "db_peak_count": metrics["db_peak_count"],
                "match_count": metrics["match_count"],
                "total_query": metrics["total_query"],
                "query_coverage": metrics["query_coverage"],
                "db_coverage": metrics["db_coverage"],
                "avg_difference": metrics["avg_difference"],
                "score": metrics["score"],
                "matches": metrics["matches"],
            }
        )

    return sort_similarity_results(results)


def search_similarity_1h(query_peaks, tolerance):
    results = []
    search_index = load_search_index(get_db_signature())

    for item in search_index:
        metrics = score_peak_matches(query_peaks, item["proton_peaks"], tolerance)
        results.append(
            {
                **item,
                "db_peak_count": metrics["db_peak_count"],
                "match_count": metrics["match_count"],
                "total_query": metrics["total_query"],
                "query_coverage": metrics["query_coverage"],
                "db_coverage": metrics["db_coverage"],
                "avg_difference": metrics["avg_difference"],
                "score": metrics["score"],
                "matches": metrics["matches"],
            }
        )

    return sort_similarity_results(results)


def search_similarity_combined(query_protons, proton_tol, query_carbons, carbon_tol):
    results = []
    search_index = load_search_index(get_db_signature())

    for item in search_index:
        proton_metrics = score_peak_matches(query_protons, item["proton_peaks"], proton_tol) if query_protons else None
        carbon_metrics = score_peak_matches(query_carbons, item["carbon_peaks"], carbon_tol) if query_carbons else None

        if proton_metrics and carbon_metrics:
            total_score = (proton_metrics["score"] * 0.5) + (carbon_metrics["score"] * 0.5)
        elif proton_metrics:
            total_score = proton_metrics["score"]
        elif carbon_metrics:
            total_score = carbon_metrics["score"]
        else:
            total_score = 0.0

        avg_differences = [
            metric["avg_difference"]
            for metric in [proton_metrics, carbon_metrics]
            if metric and metric["avg_difference"] is not None
        ]

        results.append(
            {
                **item,
                "db_proton_count": len(item["proton_peaks"]),
                "db_carbon_count": len(item["carbon_peaks"]),
                "proton_match_count": proton_metrics["match_count"] if proton_metrics else 0,
                "carbon_match_count": carbon_metrics["match_count"] if carbon_metrics else 0,
                "proton_total_query": proton_metrics["total_query"] if proton_metrics else len(query_protons),
                "carbon_total_query": carbon_metrics["total_query"] if carbon_metrics else len(query_carbons),
                "proton_score": proton_metrics["score"] if proton_metrics else 0.0,
                "carbon_score": carbon_metrics["score"] if carbon_metrics else 0.0,
                "proton_query_coverage": proton_metrics["query_coverage"] if proton_metrics else 0.0,
                "carbon_query_coverage": carbon_metrics["query_coverage"] if carbon_metrics else 0.0,
                "proton_db_coverage": proton_metrics["db_coverage"] if proton_metrics else 0.0,
                "carbon_db_coverage": carbon_metrics["db_coverage"] if carbon_metrics else 0.0,
                "total_score": total_score,
                "avg_difference": (
                    sum(avg_differences) / len(avg_differences) if avg_differences else None
                ),
                "proton_matches": proton_metrics["matches"] if proton_metrics else [],
                "carbon_matches": carbon_metrics["matches"] if carbon_metrics else [],
            }
        )

    return sorted(
        results,
        key=lambda item: (
            item["total_score"],
            item["proton_match_count"] + item["carbon_match_count"],
            -(item["avg_difference"] if item["avg_difference"] is not None else 9999),
        ),
        reverse=True,
    )

# =========================
# Export helpers
# =========================
def export_name_results(result_df: pd.DataFrame) -> pd.DataFrame:
    export_df = result_df.copy()
    if "source_material" in export_df.columns:
        export_df["source_material"] = export_df.apply(source_summary_from_record, axis=1)
    return export_df.rename(columns={
        "id": "ID",
        "trivial_name": "Trivial Name",
        "iupac_name": "IUPAC Name",
        "molecular_formula": "Molecular Formula",
        "compound_class": "Compound Class",
        "compound_subclass": "Compound Subclass",
        "source_category": "Source Category",
        "source_organism": "Source Organism",
        "source_material": "Source Summary",
        "sample_code": "Sample Code",
        "collection_location": "Collection Location",
        "gps_coordinates": "GPS Coordinates",
        "depth_m": "Depth (m)",
        "uv_data": "UV Data",
        "ftir_data": "FTIR Data",
        "cd_data": "CD / ECD Data",
        "optical_rotation": "Optical Rotation",
        "melting_point": "Melting Point",
        "crystallization_method": "Crystallization Method",
        "structure_image_path": "Structure Image Path",
        "journal_name": "Journal Name",
        "article_title": "Article Title",
        "publication_year": "Publication Year",
        "volume": "Volume",
        "issue": "Issue",
        "pages": "Pages",
        "doi": "DOI",
        "ccdc_number": "CCDC",
        "molecular_weight": "Mr",
        "hrms_data": "HRMS Data",
        "data_source": "Data Source",
        "note": "Note"
    })

def export_similarity_results_13c(results: list) -> pd.DataFrame:
    rows = []
    for i, item in enumerate(results[:10], start=1):
        rows.append({
            "Rank": i,
            "Compound ID": item["compound_id"],
            "Trivial Name": clean_text(item["trivial_name"]),
            "Molecular Formula": clean_text(item["molecular_formula"]),
            "Compound Class": clean_text(item["compound_class"]),
            "Compound Subclass": clean_text(item["compound_subclass"]),
            "Source Category": clean_text(item.get("source_category")),
            "Source Organism": clean_text(item.get("source_organism")),
            "Source Summary": clean_text(source_summary_from_record(item)),
            "Sample Code": clean_text(item["sample_code"]),
            "Matched Peaks": item["match_count"],
            "Query Peaks": item["total_query"],
            "DB Peaks": item["db_peak_count"],
            "Query Coverage (%)": round(item["query_coverage"] * 100, 2),
            "DB Coverage (%)": round(item["db_coverage"] * 100, 2),
            "Average Difference": round(item["avg_difference"], 4) if item["avg_difference"] is not None else "-",
            "Score (%)": round(item["score"], 2),
        })
    return pd.DataFrame(rows)

def export_similarity_results_1h(results: list) -> pd.DataFrame:
    rows = []
    for i, item in enumerate(results[:10], start=1):
        rows.append({
            "Rank": i,
            "Compound ID": item["compound_id"],
            "Trivial Name": clean_text(item["trivial_name"]),
            "Molecular Formula": clean_text(item["molecular_formula"]),
            "Compound Class": clean_text(item["compound_class"]),
            "Compound Subclass": clean_text(item["compound_subclass"]),
            "Source Category": clean_text(item.get("source_category")),
            "Source Organism": clean_text(item.get("source_organism")),
            "Source Summary": clean_text(source_summary_from_record(item)),
            "Sample Code": clean_text(item["sample_code"]),
            "Matched Peaks": item["match_count"],
            "Query Peaks": item["total_query"],
            "DB Peaks": item["db_peak_count"],
            "Query Coverage (%)": round(item["query_coverage"] * 100, 2),
            "DB Coverage (%)": round(item["db_coverage"] * 100, 2),
            "Average Difference": round(item["avg_difference"], 4) if item["avg_difference"] is not None else "-",
            "Score (%)": round(item["score"], 2),
        })
    return pd.DataFrame(rows)

def export_similarity_results_combined(results: list) -> pd.DataFrame:
    rows = []
    for i, item in enumerate(results[:10], start=1):
        rows.append({
            "Rank": i,
            "Compound ID": item["compound_id"],
            "Trivial Name": clean_text(item["trivial_name"]),
            "Molecular Formula": clean_text(item["molecular_formula"]),
            "Compound Class": clean_text(item["compound_class"]),
            "Compound Subclass": clean_text(item["compound_subclass"]),
            "Source Category": clean_text(item.get("source_category")),
            "Source Organism": clean_text(item.get("source_organism")),
            "Source Summary": clean_text(source_summary_from_record(item)),
            "Sample Code": clean_text(item["sample_code"]),
            "1H Matched Peaks": item["proton_match_count"],
            "1H Query Peaks": item["proton_total_query"],
            "1H Query Coverage (%)": round(item["proton_query_coverage"] * 100, 2),
            "1H Score (%)": round(item["proton_score"], 2),
            "13C Matched Peaks": item["carbon_match_count"],
            "13C Query Peaks": item["carbon_total_query"],
            "13C Query Coverage (%)": round(item["carbon_query_coverage"] * 100, 2),
            "13C Score (%)": round(item["carbon_score"], 2),
            "Average Difference": round(item["avg_difference"], 4) if item["avg_difference"] is not None else "-",
            "Total Score (%)": round(item["total_score"], 2),
        })
    return pd.DataFrame(rows)

def build_compound_summary_text(compound_row, proton_df, carbon_df, spectra_df):
    row = compound_row.iloc[0]
    bioactivity_df = load_bioactivity_data(int(row["id"]))

    summary = f"""Natural Products Spectral Database
Compound Summary

Compound ID: {row['id']}
Trivial Name: {clean_text(row['trivial_name'])}
IUPAC Name: {clean_text(row['iupac_name'])}
Molecular Formula: {clean_text(row['molecular_formula'])}
SMILES: {clean_text(row.get('smiles'))}
InChI: {clean_text(row.get('inchi'))}
InChIKey: {clean_text(row.get('inchikey'))}
Compound Class: {clean_text(row['compound_class'])}
Compound Subclass: {clean_text(row['compound_subclass'])}

Source Category: {clean_text(row.get('source_category'))}
Source Organism: {clean_text(row.get('source_organism'))}
Source Summary: {clean_text(source_summary_from_record(row))}
Sample Code: {clean_text(row['sample_code'])}
Collection Location: {clean_text(row['collection_location'])}
GPS Coordinates: {clean_text(row['gps_coordinates'])}
Depth (m): {clean_text(row['depth_m'])}

UV Data: {clean_text(row['uv_data'])}
FTIR Data: {clean_text(row['ftir_data'])}
CD / ECD Data: {clean_text(row.get('cd_data'))}
Optical Rotation: {clean_text(row['optical_rotation'])}
Melting Point: {clean_text(row['melting_point'])}
Crystallization Method: {clean_text(row['crystallization_method'])}

Journal Name: {clean_text(row['journal_name'])}
Article Title: {clean_text(row['article_title'])}
Publication Year: {clean_text(row['publication_year'])}
Volume: {clean_text(row['volume'])}
Issue: {clean_text(row['issue'])}
Pages: {clean_text(row['pages'])}
DOI: {clean_text(row['doi'])}
CCDC: {clean_text(row['ccdc_number'])}
Mr: {clean_text(row['molecular_weight'])}
HRMS Data: {clean_text(row['hrms_data'])}
Data Source: {clean_text(row['data_source'])}

Note:
{clean_text(row['note'])}

Data Coverage
-------------
1H NMR Peaks: {len(proton_df)}
13C NMR Peaks: {len(carbon_df)}
Spectra Files: {len(spectra_df)}
Bioactivity Records: {len(bioactivity_df)}
"""
    return add_credit_to_text_bytes(summary.encode("utf-8"))

# =========================
# Bioactivity helpers
# =========================
def export_bioactivity_results(bioactivity_df: pd.DataFrame) -> pd.DataFrame:
    if bioactivity_df.empty:
        return pd.DataFrame(
            columns=[
                "ID",
                "Compound ID",
                "Trivial Name",
                "Activity",
                "Target",
                "Target Category",
                "Assay Type",
                "Metric",
                "Relation",
                "Value",
                "Unit",
                "Outcome",
                "Assay Medium",
                "Selectivity",
                "Assay Source",
                "Note",
            ]
        )
    export_df = bioactivity_df.copy()
    return export_df.rename(
        columns={
            "id": "ID",
            "compound_id": "Compound ID",
            "trivial_name": "Trivial Name",
            "activity_label": "Activity",
            "target_name": "Target",
            "target_category": "Target Category",
            "assay_type": "Assay Type",
            "potency_type": "Metric",
            "potency_relation": "Relation",
            "potency_value": "Value",
            "potency_unit": "Unit",
            "outcome": "Outcome",
            "assay_medium": "Assay Medium",
            "selectivity": "Selectivity",
            "assay_source": "Assay Source",
            "note": "Note",
        }
    )


def render_bioactivity_table(compound_id: int):
    bioactivity_df = load_bioactivity_data(compound_id)
    section_header(
        "Bioactivity",
        "Reported assay outcomes, targets, potency values, and screening notes linked to this compound.",
    )
    if bioactivity_df.empty:
        st.info("No bioactivity records available for this compound yet.")
        return

    display_df = bioactivity_df.rename(
        columns={
            "id": "ID",
            "activity_label": "Activity",
            "target_name": "Target",
            "target_category": "Target Category",
            "assay_type": "Assay Type",
            "potency_type": "Metric",
            "potency_relation": "Relation",
            "potency_value": "Value",
            "potency_unit": "Unit",
            "outcome": "Outcome",
            "assay_medium": "Assay Medium",
            "selectivity": "Selectivity",
            "assay_source": "Assay Source",
            "note": "Note",
        }
    )
    st.dataframe(display_df, width="stretch", hide_index=True)

    export_df = export_bioactivity_results(load_all_bioactivity_data().query("compound_id == @compound_id"))
    download_dataframe_button(
        label="Download Bioactivity Table as Excel",
        df=export_df,
        file_name=f"compound_{compound_id}_bioactivity.xlsx",
        key=f"download_bioactivity_{compound_id}",
        sheet_name="Bioactivity",
    )

# =========================
# Spectra preview
# =========================
def render_spectra_section(compound_id):
    spectra_df = load_spectra_files(compound_id)

    section_header("Spectra Files", "Registered previews, PDFs, raw-data links, and downloadable files.")

    if spectra_df.empty:
        st.info("No spectra files available.")
        return

    grouped_types = spectra_df["spectrum_type"].fillna("Uncategorized").unique().tolist()

    for spectrum_type in grouped_types:
        sub_df = spectra_df[spectra_df["spectrum_type"].fillna("Uncategorized") == spectrum_type]

        with st.expander(f"{spectrum_type} ({len(sub_df)})", expanded=True):
            for _, row in sub_df.iterrows():
                file_id = row["id"]
                file_path_value = row["file_path"]
                note_value = clean_text(row["note"])
                full_path = get_full_file_path(file_path_value)
                _, file_warnings = validate_spectrum_entry(file_path_value, spectrum_type)

                st.markdown(
                    f"""
                    <div class="panel-card">
                        <div class="result-title">File ID {file_id}</div>
                        <div class="badge-row"><strong>Storage:</strong> {classify_storage_type(file_path_value)}</div>
                        <div class="badge-row"><strong>Path:</strong> {clean_text(file_path_value)}</div>
                        <div class="badge-row"><strong>Note:</strong> {note_value}</div>
                    </div>
                    """,
                    unsafe_allow_html=True
                )
                for warning_message in file_warnings:
                    st.caption(warning_message)

                if is_external_url(file_path_value):
                    if can_preview_external_image(file_path_value, spectrum_type):
                        preview_url = google_drive_preview_url(file_path_value) if is_google_drive_url(file_path_value) else file_path_value
                        if preview_url:
                            st.image(preview_url, caption=f"{spectrum_type} preview", width="stretch")
                    if is_google_drive_url(file_path_value):
                        external_note = "Google Drive link detected. Preview works when the file is shared with viewer access."
                    else:
                        external_note = "External repository link detected."
                    render_external_link_card("Remote file", file_path_value, external_note)
                    continue

                if full_path is None or not full_path.exists():
                    st.warning("File not found.")
                    if full_path is not None:
                        st.code(str(full_path))
                    continue

                if is_image_file(full_path):
                    st.image(str(full_path), caption=full_path.name, width="stretch")

                elif is_pdf_file(full_path):
                    with open(full_path, "rb") as f:
                        pdf_bytes = f.read()
                    st.download_button(
                        label=f"Download {full_path.name}",
                        data=pdf_bytes,
                        file_name=full_path.name,
                        mime="application/pdf",
                        key=f"pdf_download_{file_id}"
                    )

                else:
                    with open(full_path, "rb") as f:
                        file_bytes = f.read()
                    st.download_button(
                        label=f"Download {full_path.name}",
                        data=file_bytes,
                        file_name=full_path.name,
                        mime="application/octet-stream",
                        key=f"file_download_{file_id}"
                    )

# =========================
# Compound detail
# =========================
def show_compound_detail(compound_id):
    compounds = load_all_compounds()
    row = compounds[compounds["id"] == compound_id]

    if row.empty:
        st.error("Compound not found.")
        return

    proton_df_raw = load_proton_data(compound_id)
    carbon_df_raw = load_carbon_data(compound_id)
    spectra_df_raw = load_spectra_files(compound_id)
    bioactivity_df_raw = load_bioactivity_data(compound_id)
    row_data = row.iloc[0]

    section_header(
        clean_text(row_data["trivial_name"]),
        f"Record ID {row_data['id']} · full metadata, structure, peak tables, and linked spectra arranged in one review page"
    )
    st.markdown('<div class="record-shell">', unsafe_allow_html=True)
    st.markdown(
        '<div class="record-section-note">All submitted metadata, structure information, NMR tables, spectra files, and bioactivity records are displayed together here so the compound can be reviewed as one complete dossier.</div>',
        unsafe_allow_html=True,
    )

    st.markdown('<div class="action-strip">', unsafe_allow_html=True)
    is_editor = can_edit_database()
    action_col1, action_col2, action_col3, action_col4, action_col5 = st.columns(5)
    with action_col1:
        summary_bytes = build_compound_summary_text(row, proton_df_raw, carbon_df_raw, spectra_df_raw)
        st.download_button(
            label="Download Summary",
            data=summary_bytes,
            file_name=f"compound_{row_data['id']}_summary.txt",
            mime="text/plain",
            key=f"download_summary_{row_data['id']}"
        )
    with action_col2:
        if is_editor:
            if st.button("Edit This Record", key=f"edit_compound_from_detail_{row_data['id']}", use_container_width=True):
                open_compound_editor(int(row_data["id"]))
                st.rerun()
        else:
            if st.button("Open Search", key=f"search_from_detail_{row_data['id']}", use_container_width=True):
                set_main_nav("Search & Match")
                st.rerun()
    with action_col3:
        if is_editor:
            if st.button("Open 1H Workspace", key=f"open_1h_from_detail_{row_data['id']}", use_container_width=True):
                st.session_state["selected_compound_id"] = int(row_data["id"])
                set_main_nav("1H Peaks")
                st.rerun()
        else:
            if st.button("Open Bioactivity", key=f"bioactivity_from_detail_{row_data['id']}", use_container_width=True):
                set_main_nav("Bioactivity")
                st.rerun()
    with action_col4:
        if is_editor:
            if st.button("Open 13C Workspace", key=f"open_13c_from_detail_{row_data['id']}", use_container_width=True):
                st.session_state["selected_compound_id"] = int(row_data["id"])
                set_main_nav("13C Peaks")
                st.rerun()
        else:
            if st.button("Open Spectra Browser", key=f"spectra_from_detail_{row_data['id']}", use_container_width=True):
                st.session_state["selected_compound_id"] = int(row_data["id"])
                set_main_nav("Spectra Library")
                st.rerun()
    with action_col5:
        if is_editor:
            if st.button("Open Spectra Files", key=f"open_spectra_from_detail_{row_data['id']}", use_container_width=True):
                st.session_state["selected_compound_id"] = int(row_data["id"])
                set_main_nav("Spectra Library")
                st.rerun()
        else:
            st.button("Read-only Access", key=f"readonly_detail_{row_data['id']}", disabled=True, use_container_width=True)
    st.markdown('</div>', unsafe_allow_html=True)

    completeness_score = calculate_completeness_score(row, proton_df_raw, carbon_df_raw, spectra_df_raw)

    m1, m2, m3, m4, m5 = st.columns(5)
    render_metric_card("1H NMR Peaks", len(proton_df_raw), m1)
    render_metric_card("13C NMR Peaks", len(carbon_df_raw), m2)
    render_metric_card("Spectra Files", len(spectra_df_raw), m3)
    render_metric_card("Bioactivity Records", len(bioactivity_df_raw), m4)
    render_metric_card("Completeness", f"{completeness_score}%", m5)
    st.markdown(
        f"""
        <div class="record-badge-strip">
            <span class="record-badge">Class: {clean_text(row_data['compound_class'])}</span>
            <span class="record-badge">Source: {clean_text(source_summary_from_record(row_data))}</span>
            <span class="record-badge">Data Source: {clean_text(row_data['data_source'])}</span>
            <span class="record-badge">Completeness: {completeness_score}%</span>
        </div>
        """,
        unsafe_allow_html=True,
    )

    info_left, info_mid, info_right = st.columns([1.12, 1.12, 0.96])

    with info_left:
        section_header("Structure & Identity")
        render_kv("IUPAC Name", row_data["iupac_name"])
        render_kv("Molecular Formula", row_data["molecular_formula"])
        render_kv("Mr", row_data["molecular_weight"])
        render_kv("SMILES", row_data.get("smiles"))
        render_kv("InChI", row_data.get("inchi"))
        render_kv("InChIKey", row_data.get("inchikey"))
        render_kv("Compound Class", row_data["compound_class"])
        render_kv("Compound Subclass", row_data["compound_subclass"])

    with info_mid:
        section_header("Origin & Reference")
        render_kv("Source Category", row_data.get("source_category"))
        render_kv("Source Organism / Species", row_data.get("source_organism"))
        render_kv("Source Summary", source_summary_from_record(row_data))
        render_kv("Sample Code", row_data["sample_code"])
        render_kv("Collection Location", row_data["collection_location"])
        render_kv("GPS Coordinates", row_data["gps_coordinates"])
        render_kv("Depth (m)", row_data["depth_m"])
        render_kv("Data Source", row_data["data_source"])
        render_kv("Journal Name", row_data["journal_name"])
        render_kv("Article Title", row_data["article_title"])
        render_kv(
            "Publication Year / Volume / Issue / Pages",
            f"{clean_text(row_data['publication_year'])} / {clean_text(row_data['volume'])} / {clean_text(row_data['issue'])} / {clean_text(row_data['pages'])}"
        )
        render_kv("DOI", row_data["doi"])
        render_kv("CCDC", row_data["ccdc_number"])

    with info_right:
        section_header("Structure")
        st.markdown('<div class="structure-card">', unsafe_allow_html=True)
        structure_path = row_data["structure_image_path"]
        if pd.notna(structure_path) and str(structure_path).strip():
            standardized_image = load_standardized_structure_source(structure_path, size=(520, 360))
            if standardized_image is not None:
                st.image(standardized_image, width="stretch")
                if is_external_url(str(structure_path).strip()):
                    st.caption("Stored in cloud structure library")
                else:
                    full_path = get_full_file_path(structure_path)
                    if full_path:
                        st.caption(full_path.name)
            else:
                st.warning("Structure image file not found.")
                if is_external_url(str(structure_path).strip()):
                    st.code(str(structure_path).strip())
                else:
                    full_path = get_full_file_path(structure_path)
                    if full_path:
                        st.code(str(full_path))
        else:
            render_structure_preview(row_data.get("smiles"), caption="Rendered from SMILES", size=(520, 360))
        st.markdown('</div>', unsafe_allow_html=True)
        st.markdown('<div class="panel-card">', unsafe_allow_html=True)
        st.markdown("**Record Snapshot**")
        st.caption(f"Created: {clean_text(row_data.get('created_at'))}")
        st.caption(f"Updated: {clean_text(row_data.get('updated_at'))}")
        st.caption(f"Source summary: {clean_text(source_summary_from_record(row_data))}")
        st.caption(f"Bioactivity records linked: {len(bioactivity_df_raw)}")
        st.markdown('</div>', unsafe_allow_html=True)

    section_header("Physical, Spectral & Supporting Data")
    spectral_col1, spectral_col2, spectral_col3 = st.columns(3)
    with spectral_col1:
        render_kv("UV Data", row_data["uv_data"])
        render_kv("FTIR Data", row_data["ftir_data"])
        render_kv("CD / ECD Data", row_data.get("cd_data"))
    with spectral_col2:
        render_kv("Optical Rotation", row_data["optical_rotation"])
        render_kv("HRMS", row_data["hrms_data"])
        render_kv("Melting Point", row_data["melting_point"])
    with spectral_col3:
        render_kv("Crystallization Method", row_data["crystallization_method"])
        render_kv("Structure Image Path", row_data["structure_image_path"])
        render_kv("Reference DOI / Journal", f"{clean_text(row_data['doi'])} / {clean_text(row_data['journal_name'])}")

    section_header("1H NMR Table")
    if proton_df_raw.empty:
        st.info("No 1H NMR data available.")
    else:
        proton_df = proton_df_raw.rename(columns={
            "id": "ID",
            "delta_ppm": "δH (ppm)",
            "multiplicity": "Multiplicity",
            "j_value": "J Value",
            "proton_count": "Proton Count",
            "assignment": "Assignment",
            "solvent": "Solvent",
            "instrument_mhz": "Instrument (MHz)",
            "note": "Note"
        })
        st.dataframe(proton_df, width="stretch", hide_index=True)

    section_header("13C NMR Table")
    if carbon_df_raw.empty:
        st.info("No 13C NMR data available.")
    else:
        carbon_df = carbon_df_raw.rename(columns={
            "id": "ID",
            "delta_ppm": "δC (ppm)",
            "carbon_type": "Carbon Type",
            "assignment": "Assignment",
            "solvent": "Solvent",
            "instrument_mhz": "Instrument (MHz)",
            "note": "Note"
        })
        st.dataframe(carbon_df, width="stretch", hide_index=True)

    render_spectra_section(compound_id)
    render_bioactivity_table(compound_id)

    section_header("Notes")
    st.markdown('<div class="panel-card">', unsafe_allow_html=True)
    st.write(clean_text(row_data["note"]))
    st.markdown('</div>', unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)

def render_best_match_summary(item, mode_label):
    source_summary = clean_text(source_summary_from_record(item))
    st.markdown("### Best Match Summary")
    st.markdown(
        f"""
        <div class="best-match-card">
            <div class="result-title">{clean_text(item['trivial_name'])}</div>
            <div class="result-subtitle">Compound ID: {item['compound_id']}</div>
            <div class="badge-row"><strong>Mode:</strong> {mode_label}</div>
            <div class="badge-row"><strong>Molecular Formula:</strong> {clean_text(item.get('molecular_formula'))}</div>
            <div class="badge-row"><strong>Compound Class:</strong> {clean_text(item.get('compound_class'))}</div>
            <div class="badge-row"><strong>Compound Subclass:</strong> {clean_text(item.get('compound_subclass'))}</div>
            <div class="badge-row"><strong>Source:</strong> {source_summary}</div>
            <div class="badge-row"><strong>Sample Code:</strong> {clean_text(item.get('sample_code'))}</div>
            <div class="badge-row"><strong>Data Source:</strong> {clean_text(item.get('data_source'))}</div>
        </div>
        """,
        unsafe_allow_html=True
    )

def render_candidate_cards(results, mode="13C", limit=10):
    if not results:
        st.info("No matching candidates found.")
        return

    top = results[0]

    if mode == "13C":
        render_best_match_summary(top, "13C similarity search")
    elif mode == "1H":
        render_best_match_summary(top, "1H similarity search")
    else:
        render_best_match_summary(top, "Combined 1H + 13C similarity search")

    section_header(
        "Candidate Ranking",
        "Ranking blends query coverage, database coverage, and how closely the matched peaks align."
    )

    for i, item in enumerate(results[:limit], start=1):
        title = clean_text(item["trivial_name"])
        formula = clean_text(item.get("molecular_formula"))
        compound_class = clean_text(item.get("compound_class"))
        subclass = clean_text(item.get("compound_subclass"))
        source_summary = clean_text(source_summary_from_record(item))
        sample_code = clean_text(item.get("sample_code"))
        data_source = clean_text(item.get("data_source"))

        if mode == "13C":
            subtitle = (
                f"Score: {item['score']:.1f}% | Matched: {item['match_count']}/{item['total_query']} | "
                f"Query Coverage: {item['query_coverage'] * 100:.1f}% | DB Coverage: {item['db_coverage'] * 100:.1f}%"
            )
            progress_value = item["score"] / 100
        elif mode == "1H":
            subtitle = (
                f"Score: {item['score']:.1f}% | Matched: {item['match_count']}/{item['total_query']} | "
                f"Query Coverage: {item['query_coverage'] * 100:.1f}% | DB Coverage: {item['db_coverage'] * 100:.1f}%"
            )
            progress_value = item["score"] / 100
        else:
            subtitle = (
                f"Total Score: {item['total_score']:.1f}% | "
                f"1H: {item['proton_match_count']}/{item['proton_total_query']} ({item['proton_score']:.1f}%) | "
                f"13C: {item['carbon_match_count']}/{item['carbon_total_query']} ({item['carbon_score']:.1f}%)"
            )
            progress_value = item["total_score"] / 100

        with st.expander(f"#{i} · {title}", expanded=(i == 1)):
            st.markdown(
                f"""
                <div class="result-card">
                    <div class="result-title">{title}</div>
                    <div class="result-subtitle">{subtitle}</div>
                    <div class="badge-row"><strong>Compound ID:</strong> {item['compound_id']}</div>
                    <div class="badge-row"><strong>Molecular Formula:</strong> {formula}</div>
                    <div class="badge-row"><strong>Compound Class:</strong> {compound_class}</div>
                    <div class="badge-row"><strong>Compound Subclass:</strong> {subclass}</div>
                    <div class="badge-row"><strong>Source:</strong> {source_summary}</div>
                    <div class="badge-row"><strong>Sample Code:</strong> {sample_code}</div>
                    <div class="badge-row"><strong>Data Source:</strong> {data_source}</div>
                </div>
                """,
                unsafe_allow_html=True
            )

            st.progress(progress_value)

            if mode in ["13C", "1H"]:
                diff_text = (
                    f"{item['avg_difference']:.4f} ppm"
                    if item["avg_difference"] is not None else "-"
                )
                st.caption(
                    f"Average difference: {diff_text} | DB peaks: {item['db_peak_count']}"
                )
            else:
                diff_text = (
                    f"{item['avg_difference']:.4f} ppm"
                    if item["avg_difference"] is not None else "-"
                )
                st.caption(f"Average difference across matched peaks: {diff_text}")

            action_left, action_right = st.columns([1, 1])
            with action_left:
                if st.button(
                    f"Open Record #{i}",
                    key=f"open_detail_{mode}_{item['compound_id']}_{i}"
                ):
                    open_compound_detail(item["compound_id"])
                    st.rerun()

            with action_right:
                if st.button(
                    f"Update Metadata #{i}",
                    key=f"edit_compound_{mode}_{item['compound_id']}_{i}"
                ):
                    open_compound_editor(item["compound_id"])
                    st.rerun()

            if mode == "13C" and item["matches"]:
                st.markdown("**Matched 13C Peaks**")
                match_df = pd.DataFrame(item["matches"], columns=["Query Peak", "DB Peak", "Difference"])
                st.dataframe(match_df, width="stretch", hide_index=True)

            elif mode == "1H" and item["matches"]:
                st.markdown("**Matched 1H Peaks**")
                match_df = pd.DataFrame(item["matches"], columns=["Query Peak", "DB Peak", "Difference"])
                st.dataframe(match_df, width="stretch", hide_index=True)

            elif mode == "combined":
                if item["proton_matches"]:
                    st.markdown("**Matched 1H Peaks**")
                    proton_df = pd.DataFrame(item["proton_matches"], columns=["Query Peak", "DB Peak", "Difference"])
                    st.dataframe(proton_df, width="stretch", hide_index=True)

                if item["carbon_matches"]:
                    st.markdown("**Matched 13C Peaks**")
                    carbon_df = pd.DataFrame(item["carbon_matches"], columns=["Query Peak", "DB Peak", "Difference"])
                    st.dataframe(carbon_df, width="stretch", hide_index=True)

                    # =========================
# Search page
# =========================
def show_search_page(all_compounds_df):
    section_header("Search & Match", "Switch between keyword lookup and spectral similarity ranking without leaving the same workspace.")

    search_mode = st.radio(
        "Search Mode",
        ["Keyword Search", "Structure Search", "13C Match", "1H Match", "Combined Match"],
        horizontal=True
    )

    with st.sidebar.expander("Search Filters", expanded=True):
        search_class_filter = st.selectbox(
            "Compound Class",
            build_filter_options(all_compounds_df, "compound_class"),
            key="search_class_filter"
        )
        search_source_filter = st.selectbox(
            "Source Category",
            build_filter_options(all_compounds_df, "source_category"),
            key="search_source_filter"
        )
        search_data_source_filter = st.selectbox(
            "Data Source",
            build_filter_options(all_compounds_df, "data_source"),
            key="search_data_source_filter"
        )
        min_similarity_score = st.slider(
            "Minimum similarity score (%)",
            min_value=0,
            max_value=100,
            value=35,
            step=5,
            key="search_min_similarity_score",
        )
        candidate_limit = st.slider(
            "Candidates to display",
            min_value=3,
            max_value=20,
            value=10,
            key="search_candidate_limit",
        )

    if search_mode == "Structure Search":
        filtered_df = apply_dataframe_filters(
            all_compounds_df,
            class_filter=search_class_filter,
            source_filter=search_source_filter,
            data_source_filter=search_data_source_filter
        )

        query_smiles = maybe_blank(st.session_state.get("structure_query_smiles"))
        editor_left, editor_right = st.columns([1.95, 1])

        with editor_left:
            st.markdown('<div class="panel-card">', unsafe_allow_html=True)
            st.markdown("**Search by Structure**")
            previous_query_smiles = maybe_blank(st.session_state.get("structure_query_smiles"))
            editor_mode_message = ""
            if st_ketcher is not None:
                drawn_smiles = st_ketcher(
                    value=previous_query_smiles,
                    height=720,
                    molecule_format="SMILES",
                    key="structure_search_editor_primary",
                )
                drawn_smiles_text = "" if drawn_smiles in {None, 0, "0"} else maybe_blank(drawn_smiles)
                if drawn_smiles_text != previous_query_smiles:
                    st.session_state["structure_query_smiles"] = drawn_smiles_text
                    clear_structure_search_state()
                query_smiles = drawn_smiles_text
                editor_mode_message = "Direct drawing editor is active. Draw the structure in the canvas, then run identity, substructure, or similarity search."
            elif streamlit_ketchersa is not None:
                drawn_structure = streamlit_ketchersa(height="720px", key="structure_search_editor_full")
                drawn_structure_text = "" if drawn_structure in {None, 0, "0"} else maybe_blank(drawn_structure)
                if drawn_structure_text != previous_query_smiles:
                    st.session_state["structure_query_smiles"] = drawn_structure_text
                    clear_structure_search_state()
                query_smiles = drawn_structure_text
                editor_mode_message = "Embedded Ketcher build is active. Draw directly in the canvas, then run identity, substructure, or similarity search."
            else:
                st.warning("The direct drawing editor is not active in this deployment yet.")
                st.caption(f"Editor status: {KETCHER_STATUS}")
                query_smiles = st.text_area(
                    "Query Structure (SMILES or Molfile)",
                    key="structure_query_smiles",
                    height=220,
                    placeholder="Example: C1=CC=CC=C1",
                )
                st.text_input(
                    "Starting SMILES (optional)",
                    key="structure_seed_smiles",
                    placeholder="Paste a known scaffold here if you want to seed the editor in a future run.",
                )
                editor_mode_message = "Fallback mode is active. You can still search by pasting a valid SMILES or Molfile query."
                if maybe_blank(query_smiles) != previous_query_smiles:
                    clear_structure_search_state()
            st.caption(editor_mode_message)
            st.markdown('</div>', unsafe_allow_html=True)

        with editor_right:
            st.markdown('<div class="panel-card">', unsafe_allow_html=True)
            structure_search_type = st.radio(
                "Structure Search Type",
                ["Identity Search", "Substructure Search", "Similarity Search"],
                horizontal=False,
                key="structure_search_type",
            )
            if query_smiles:
                render_structure_preview(query_smiles, caption="Current query", empty_message=False, size=(420, 300))
            else:
                st.caption("Draw a structure in the editor area to prepare the current query.")
            if structure_search_type == "Similarity Search":
                st.caption(f"Minimum similarity score: {min_similarity_score}%")
                st.caption("Similarity mode compares molecular fingerprints and ranks the closest structures first.")
            elif structure_search_type == "Substructure Search":
                st.caption("Substructure mode checks whether your query fragment is present inside stored candidate structures.")
            else:
                st.caption("Identity mode compares the canonicalized query structure against stored compounds.")
            run_structure_search = st.button("Search by Structure", use_container_width=True, key="run_structure_search")
            if query_smiles:
                with st.expander("Technical query preview", expanded=False):
                    st.code(query_smiles)
                if can_edit_database():
                    target_df = all_compounds_df.copy()
                    missing_df = target_df[
                        target_df["smiles"].fillna("").astype(str).str.strip().eq("")
                        & target_df["inchi"].fillna("").astype(str).str.strip().eq("")
                        & target_df["inchikey"].fillna("").astype(str).str.strip().eq("")
                    ]
                    preferred_df = missing_df if not missing_df.empty else target_df
                    preferred_df = preferred_df[["id", "trivial_name"]].copy()
                    preferred_df["label"] = preferred_df["id"].astype(str) + " - " + preferred_df["trivial_name"].fillna("Unnamed record").astype(str)
                    st.markdown("---")
                    st.caption("Admin shortcut: save the current drawn structure into a compound record so structure search becomes searchable in your own database.")
                    selected_structure_label = st.selectbox(
                        "Save current structure to compound",
                        preferred_df["label"].tolist(),
                        key="structure_link_target_select",
                    )
                    if st.button("Save Structure IDs to Selected Compound", use_container_width=True, key="save_structure_ids_from_query"):
                        target_compound_id = int(selected_structure_label.split(" - ")[0])
                        saved, save_message = save_structure_query_to_compound(target_compound_id, query_smiles)
                        if saved:
                            st.success(save_message)
                            st.rerun()
                        else:
                            st.error(save_message)
            st.markdown('</div>', unsafe_allow_html=True)

        if run_structure_search:
            results, error_message = search_by_structure(
                filtered_df,
                query_smiles=query_smiles,
                search_type=structure_search_type,
                similarity_threshold=float(min_similarity_score) / 100.0,
            )
            st.session_state["structure_search_results"] = results
            st.session_state["structure_search_error"] = error_message
            st.session_state["structure_search_mode_label"] = structure_search_type
            st.session_state["structure_search_attempted"] = True

        structure_error = maybe_blank(st.session_state.get("structure_search_error"))
        structure_results = st.session_state.get("structure_search_results", [])
        structure_mode_label = maybe_blank(st.session_state.get("structure_search_mode_label")) or structure_search_type
        structure_attempted = bool(st.session_state.get("structure_search_attempted"))

        if structure_error:
            if structure_error.lower().startswith("no compounds matched") or structure_error.lower().startswith("no searchable structures"):
                st.info(structure_error)
            else:
                st.error(structure_error)
        elif structure_results:
            st.write(f"Found {len(structure_results)} compound(s) for the current structure query.")
            query_col, summary_col = st.columns([1.05, 1.35])
            with query_col:
                st.markdown('<div class="panel-card">', unsafe_allow_html=True)
                st.markdown("**Query Structure**")
                render_structure_preview(query_smiles, caption="Current query", empty_message=False, size=(420, 300))
                st.markdown('</div>', unsafe_allow_html=True)
            with summary_col:
                st.markdown('<div class="panel-card">', unsafe_allow_html=True)
                top_score = float(structure_results[0].get("structure_score", 0.0)) if structure_results else 0.0
                st.markdown(
                    f'''
                    <div class="query-summary-grid">
                        <div class="query-summary-card">
                            <div class="query-summary-label">Search Mode</div>
                            <div class="query-summary-value">{structure_mode_label}</div>
                        </div>
                        <div class="query-summary-card">
                            <div class="query-summary-label">Top Similarity / Match</div>
                            <div class="query-summary-value">{top_score:.1f}%</div>
                        </div>
                        <div class="query-summary-card">
                            <div class="query-summary-label">Candidates Returned</div>
                            <div class="query-summary-value">{len(structure_results)}</div>
                        </div>
                    </div>
                    ''',
                    unsafe_allow_html=True,
                )
                st.caption("Results are ranked against the structures currently available in your database, so the percentages always reflect your own curated dataset.")
                st.markdown('</div>', unsafe_allow_html=True)
            export_df = export_structure_search_results(structure_results)
            download_dataframe_button(
                label="Download Structure Search Results as Excel",
                df=export_df,
                file_name="search_by_structure_results.xlsx",
                key="download_structure_search_xlsx",
                sheet_name="Structure Search",
            )
            render_structure_search_results(structure_results, structure_mode_label, limit=candidate_limit)
        elif structure_attempted:
            st.info("The structure query was submitted, but no result rows were returned.")
        else:
            render_helper_card(
                "Structure search workflow",
                "Draw a structure directly in the embedded editor, choose identity, substructure, or similarity mode, then run the search against the currently filtered dataset.",
            )

    elif search_mode == "Keyword Search":
        filtered_df = apply_dataframe_filters(
            all_compounds_df,
            class_filter=search_class_filter,
            source_filter=search_source_filter,
            data_source_filter=search_data_source_filter
        )

        with st.form("search_by_name_form"):
            st.markdown('<div class="panel-card">', unsafe_allow_html=True)
            keyword = st.text_input(
                "Enter compound name, keyword, sample code, source category/organism, journal, or DOI",
                key="search_name_keyword",
            )
            run_name_search = st.form_submit_button("Run Keyword Search", use_container_width=True)
            st.markdown('</div>', unsafe_allow_html=True)

        if keyword.strip():
            result = filtered_df[keyword_search_mask(filtered_df, keyword)].copy()
            st.write(f"Found {len(result)} compound(s).")

            if not result.empty:
                export_df = export_name_results(result)
                download_dataframe_button(
                    label="Download Search Results as Excel",
                    df=export_df,
                    file_name="search_by_name_results.xlsx",
                    key="download_name_xlsx",
                    sheet_name="Keyword Search",
                )
                st.dataframe(export_df, width="stretch", hide_index=True)

                section_header("Quick Browse")
                for _, row in result.head(candidate_limit).iterrows():
                    c1, c2 = st.columns([5, 1])
                    with c1:
                        render_compound_card(row)
                    with c2:
                        st.write("")
                        if st.button("Open", key=f"name_open_{row['id']}"):
                            open_compound_detail(int(row["id"]))
                            st.rerun()
            else:
                st.info("No compounds matched all keywords in your query.")
        elif run_name_search:
            st.warning("Please enter at least one keyword.")
        elif not filtered_df.empty:
            st.info("Type one or more keywords to search. The filtered dataset preview is shown below.")
            preview_df = export_name_results(filtered_df.head(candidate_limit))
            st.dataframe(preview_df, width="stretch", hide_index=True)
        else:
            st.info("No compounds available for the selected filters.")

    elif search_mode == "13C Match":
        with st.form("search_13c_form"):
            left, right = st.columns([1.35, 1])
            with left:
                st.markdown('<div class="panel-card">', unsafe_allow_html=True)
                carbon_text = st.text_area("Enter 13C peaks (comma, space, or newline separated)", height=140)
                st.markdown('</div>', unsafe_allow_html=True)
            with right:
                st.markdown('<div class="panel-card">', unsafe_allow_html=True)
                carbon_tol = st.number_input("13C tolerance", min_value=0.0, value=0.5, step=0.1)
                run_13c = st.form_submit_button("Run 13C Match", use_container_width=True)
                st.markdown('<div class="small-note">Example: 145.2, 122.8, 77.1, 38.5</div>', unsafe_allow_html=True)
                st.markdown('</div>', unsafe_allow_html=True)

        if run_13c:
            query_carbons = parse_peak_input(carbon_text)
            if not query_carbons:
                st.warning("Please enter at least one valid 13C peak.")
            else:
                results = search_similarity_13c(query_carbons, carbon_tol)
                filtered_results = filter_similarity_results(
                    results,
                    class_filter=search_class_filter,
                    source_filter=search_source_filter,
                    data_source_filter=search_data_source_filter
                )
                filtered_results = [
                    item for item in filtered_results
                    if item["score"] >= float(min_similarity_score)
                ]

                st.caption(
                    "Similarity score uses query coverage, database coverage, and average peak closeness."
                )
                st.write(f"Found {len(filtered_results)} candidate(s) above the current score threshold.")

                if filtered_results:
                    export_df = export_similarity_results_13c(filtered_results)
                    download_dataframe_button(
                        label="Download 13C Similarity Results as Excel",
                        df=export_df,
                        file_name="search_by_13c_results.xlsx",
                        key="download_13c_xlsx",
                        sheet_name="13C Match",
                    )

                render_candidate_cards(filtered_results, mode="13C", limit=candidate_limit)

    elif search_mode == "1H Match":
        with st.form("search_1h_form"):
            left, right = st.columns([1.35, 1])
            with left:
                st.markdown('<div class="panel-card">', unsafe_allow_html=True)
                proton_text = st.text_area("Enter 1H peaks (comma, space, or newline separated)", height=140)
                st.markdown('</div>', unsafe_allow_html=True)
            with right:
                st.markdown('<div class="panel-card">', unsafe_allow_html=True)
                proton_tol = st.number_input("1H tolerance", min_value=0.0, value=0.05, step=0.01, format="%.2f")
                run_1h = st.form_submit_button("Run 1H Match", use_container_width=True)
                st.markdown('<div class="small-note">Example: 5.82, 5.35, 3.21, 1.22</div>', unsafe_allow_html=True)
                st.markdown('</div>', unsafe_allow_html=True)

        if run_1h:
            query_protons = parse_peak_input(proton_text)
            if not query_protons:
                st.warning("Please enter at least one valid 1H peak.")
            else:
                results = search_similarity_1h(query_protons, proton_tol)
                filtered_results = filter_similarity_results(
                    results,
                    class_filter=search_class_filter,
                    source_filter=search_source_filter,
                    data_source_filter=search_data_source_filter
                )
                filtered_results = [
                    item for item in filtered_results
                    if item["score"] >= float(min_similarity_score)
                ]

                st.caption(
                    "Similarity score uses query coverage, database coverage, and average peak closeness."
                )
                st.write(f"Found {len(filtered_results)} candidate(s) above the current score threshold.")

                if filtered_results:
                    export_df = export_similarity_results_1h(filtered_results)
                    download_dataframe_button(
                        label="Download 1H Similarity Results as Excel",
                        df=export_df,
                        file_name="search_by_1h_results.xlsx",
                        key="download_1h_xlsx",
                        sheet_name="1H Match",
                    )

                render_candidate_cards(filtered_results, mode="1H", limit=candidate_limit)

    else:
        with st.form("search_combined_form"):
            left, right = st.columns([1.4, 1])
            with left:
                st.markdown('<div class="panel-card">', unsafe_allow_html=True)
                proton_text = st.text_area("Enter 1H peaks (comma, space, or newline separated)", height=120, key="combined_proton_text")
                carbon_text = st.text_area("Enter 13C peaks (comma, space, or newline separated)", height=120, key="combined_carbon_text")
                st.markdown('</div>', unsafe_allow_html=True)
            with right:
                st.markdown('<div class="panel-card">', unsafe_allow_html=True)
                proton_tol = st.number_input("1H tolerance", min_value=0.0, value=0.05, step=0.01, format="%.2f", key="combined_1h")
                carbon_tol = st.number_input("13C tolerance", min_value=0.0, value=0.5, step=0.1, key="combined_13c")
                run_combined = st.form_submit_button("Run Combined Match", use_container_width=True)
                st.markdown('<div class="small-note">Use both peak lists for more selective candidate ranking.</div>', unsafe_allow_html=True)
                st.markdown('</div>', unsafe_allow_html=True)

        if run_combined:
            query_protons = parse_peak_input(proton_text)
            query_carbons = parse_peak_input(carbon_text)

            if not query_protons and not query_carbons:
                st.warning("Please enter at least one valid 1H or 13C peak.")
            else:
                results = search_similarity_combined(query_protons, proton_tol, query_carbons, carbon_tol)
                filtered_results = filter_similarity_results(
                    results,
                    class_filter=search_class_filter,
                    source_filter=search_source_filter,
                    data_source_filter=search_data_source_filter
                )
                filtered_results = [
                    item for item in filtered_results
                    if item["total_score"] >= float(min_similarity_score)
                ]

                st.caption(
                    "Combined ranking averages the improved 1H and 13C similarity scores."
                )
                st.write(f"Found {len(filtered_results)} candidate(s) above the current score threshold.")

                if filtered_results:
                    export_df = export_similarity_results_combined(filtered_results)
                    download_dataframe_button(
                        label="Download Combined Similarity Results as Excel",
                        df=export_df,
                        file_name="search_combined_results.xlsx",
                        key="download_combined_xlsx",
                        sheet_name="Combined Match",
                    )

                render_candidate_cards(filtered_results, mode="combined", limit=candidate_limit)


# =========================
# Overview page
# =========================
def show_overview_page(all_compounds_df):
    section_header("Dashboard")

    with st.sidebar.expander("Dashboard Filters", expanded=True):
        dashboard_class_filter = st.selectbox(
            "Compound Class",
            build_filter_options(all_compounds_df, "compound_class"),
            key="dashboard_class"
        )
        dashboard_subclass_filter = st.selectbox(
            "Compound Subclass",
            build_filter_options(all_compounds_df, "compound_subclass"),
            key="dashboard_subclass"
        )
        dashboard_source_filter = st.selectbox(
            "Source Category",
            build_filter_options(all_compounds_df, "source_category"),
            key="dashboard_source"
        )
        dashboard_data_source_filter = st.selectbox(
            "Data Source",
            build_filter_options(all_compounds_df, "data_source"),
            key="dashboard_data_source"
        )

    filtered_df = apply_dataframe_filters(
        all_compounds_df,
        class_filter=dashboard_class_filter,
        subclass_filter=dashboard_subclass_filter,
        source_filter=dashboard_source_filter,
        data_source_filter=dashboard_data_source_filter
    )

    filtered_ids = filtered_df["id"].tolist()
    proton_count, carbon_count, spectra_count = count_related_records(filtered_ids)
    bioactivity_count = count_bioactivity_records(filtered_ids)
    health = calculate_workspace_health(filtered_df)
    spectra_df = load_all_spectra_files()
    linked_spectra_ids = set(spectra_df["compound_id"].tolist()) if not spectra_df.empty else set()

    missing_structure_df = filtered_df[
        filtered_df["smiles"].fillna("").astype(str).str.strip().eq("")
        & filtered_df["inchi"].fillna("").astype(str).str.strip().eq("")
        & filtered_df["inchikey"].fillna("").astype(str).str.strip().eq("")
    ]
    missing_reference_df = filtered_df[
        filtered_df["doi"].fillna("").astype(str).str.strip().eq("")
        & filtered_df["journal_name"].fillna("").astype(str).str.strip().eq("")
    ]
    missing_source_df = filtered_df[
        filtered_df["source_category"].fillna("").astype(str).str.strip().eq("")
        & filtered_df["source_organism"].fillna("").astype(str).str.strip().eq("")
        & filtered_df["source_material"].fillna("").astype(str).str.strip().eq("")
    ]
    missing_spectra_df = filtered_df[~filtered_df["id"].isin(linked_spectra_ids)]

    c1, c2, c3, c4, c5 = st.columns(5)
    render_metric_card("Compounds", len(filtered_df), c1)
    render_metric_card("1H Peaks", proton_count, c2)
    render_metric_card("13C Peaks", carbon_count, c3)
    render_metric_card("Spectra Files", spectra_count, c4)
    render_metric_card("Bioactivity Records", bioactivity_count, c5)

    h1, h2, h3, h4, h5 = st.columns(5)
    render_metric_card("Structure IDs Ready", health["structure_ready"], h1)
    render_metric_card("Reference Ready", health["reference_ready"], h2)
    render_metric_card("Drive-linked Records", health["external_ready"], h3)
    render_metric_card("Submission-ready Metadata", health["submission_ready"], h4)
    render_metric_card("Bioactivity-linked Compounds", health.get("bioactivity_ready", 0), h5)

    section_header("Metadata Gaps", "This section helps you see which records should be curated next.")
    g1, g2, g3, g4 = st.columns(4)
    render_clean_stat("Missing Structure IDs", len(missing_structure_df), g1)
    render_clean_stat("Missing Reference Info", len(missing_reference_df), g2)
    render_clean_stat("Missing Source Info", len(missing_source_df), g3)
    render_clean_stat("Without Spectra Links", len(missing_spectra_df), g4)

    priority_df = filtered_df.copy()
    if not priority_df.empty:
        priority_df["missing_structure"] = (
            priority_df["smiles"].fillna("").astype(str).str.strip().eq("")
            & priority_df["inchi"].fillna("").astype(str).str.strip().eq("")
            & priority_df["inchikey"].fillna("").astype(str).str.strip().eq("")
        )
        priority_df["missing_reference"] = (
            priority_df["doi"].fillna("").astype(str).str.strip().eq("")
            & priority_df["journal_name"].fillna("").astype(str).str.strip().eq("")
        )
        priority_df["missing_source"] = (
            priority_df["source_category"].fillna("").astype(str).str.strip().eq("")
            & priority_df["source_organism"].fillna("").astype(str).str.strip().eq("")
            & priority_df["source_material"].fillna("").astype(str).str.strip().eq("")
        )
        priority_df["source_material"] = priority_df.apply(source_summary_from_record, axis=1)
        priority_df["missing_spectra"] = ~priority_df["id"].isin(linked_spectra_ids)
        priority_df["curation_priority"] = (
            priority_df["missing_structure"].astype(int)
            + priority_df["missing_reference"].astype(int)
            + priority_df["missing_source"].astype(int)
            + priority_df["missing_spectra"].astype(int)
        )

        priority_view = priority_df[priority_df["curation_priority"] > 0].copy()
        if not priority_view.empty:
            section_header("Priority Records", "Records at the top of this list are the best candidates for metadata improvement.")
            priority_view = priority_view.sort_values(
                by=["curation_priority", "id"],
                ascending=[False, True],
            )
            priority_view["Missing Fields"] = priority_view.apply(
                lambda row: ", ".join(
                    [
                        label
                        for label, missing in [
                            ("structure IDs", row["missing_structure"]),
                            ("reference", row["missing_reference"]),
                            ("source", row["missing_source"]),
                            ("spectra link", row["missing_spectra"]),
                        ]
                        if missing
                    ]
                ),
                axis=1,
            )
            st.dataframe(
                priority_view[
                    [
                        "id",
                        "trivial_name",
                        "compound_class",
                        "source_material",
                        "curation_priority",
                        "Missing Fields",
                    ]
                ].rename(
                    columns={
                        "id": "ID",
                        "trivial_name": "Trivial Name",
                        "compound_class": "Compound Class",
                        "source_material": "Source Summary",
                        "curation_priority": "Priority Score",
                    }
                ),
                width="stretch",
                hide_index=True,
            )
        else:
            render_helper_card(
                "Priority status",
                "The filtered records already look well curated. Use the sidebar to move into record editing, spectra review, or submission work when needed.",
            )

    st.markdown('<div class="dashboard-section"></div>', unsafe_allow_html=True)
    section_header("Distribution Overview", "These charts help you see how the current filtered dataset is distributed across class and source category.")
    left, right = st.columns([1.25, 1])

    with left:
        section_header("Compound Distribution")
        if filtered_df.empty:
            st.info("No compounds available for the selected filters.")
        else:
            class_counts = (
                filtered_df["compound_class"]
                .fillna("Uncategorized")
                .replace("", "Uncategorized")
                .value_counts()
                .reset_index()
            )
            class_counts.columns = ["Compound Class", "Count"]
            render_dashboard_bar_chart(
                class_counts,
                x_col="Compound Class",
                y_col="Count",
                color_hex="#61D8ED",
            )

    with right:
        section_header("Source Category Distribution")
        if filtered_df.empty:
            st.info("No compounds available for the selected filters.")
        else:
            source_counts = (
                filtered_df["source_category"]
                .fillna("Uncategorized")
                .replace("", "Uncategorized")
                .value_counts()
                .reset_index()
            )
            source_counts.columns = ["Source Category", "Count"]
            render_dashboard_bar_chart(
                source_counts,
                x_col="Source Category",
                y_col="Count",
                color_hex="#9C63F1",
            )

    st.markdown('<div class="dashboard-section"></div>', unsafe_allow_html=True)
    section_header("Quick Browse")
    if filtered_df.empty:
        st.info("No compounds available for the selected filters.")
    else:
        browse_limit = st.slider("Number of compounds to preview", min_value=3, max_value=20, value=8)
        for _, row in filtered_df.head(browse_limit).iterrows():
            c1, c2 = st.columns([5, 1])
            with c1:
                render_compound_card(row)
            with c2:
                st.write("")
                if st.button("Open", key=f"overview_open_{row['id']}"):
                    open_compound_detail(int(row["id"]))
                    st.rerun()

    st.markdown('<div class="dashboard-section"></div>', unsafe_allow_html=True)
    table_col, utility_col = st.columns([4.2, 1.3])

    with table_col:
        section_header("Compound Table")
        st.markdown(
            '<div class="dashboard-dataframe-note">Use this table for broad scanning, then open individual records from Quick Browse when you need detailed review.</div>',
            unsafe_allow_html=True,
        )
        if filtered_df.empty:
            st.info("No rows available.")
        else:
            display_df = filtered_df[
                [
                    "id",
                    "trivial_name",
                    "molecular_formula",
                    "compound_class",
                    "compound_subclass",
                    "source_category",
                    "source_organism",
                    "source_material",
                    "sample_code"
                ]
            ].rename(columns={
                "id": "ID",
                "trivial_name": "Trivial Name",
                "molecular_formula": "Molecular Formula",
                "compound_class": "Compound Class",
                "compound_subclass": "Compound Subclass",
                "source_category": "Source Category",
                "source_organism": "Source Organism",
                "source_material": "Source Summary",
                "sample_code": "Sample Code"
            })

            download_dataframe_button(
                label="Download Current Overview as Excel",
                df=display_df,
                file_name="overview_filtered_compounds.xlsx",
                key="download_overview_xlsx",
                sheet_name="Dashboard Overview",
            )

            st.dataframe(display_df, width="stretch", hide_index=True)

    with utility_col:
        section_header("Backup")
        render_helper_card(
            "Keep a safe copy",
            "Download a fresh SQLite backup before major imports, metadata revision, or record deletion.",
        )
        backup_filename = f"nmr_database_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.db"
        st.download_button(
            label="Download SQLite Backup",
            data=get_backup_bytes(),
            file_name=backup_filename,
            mime="application/octet-stream",
            key="download_db_backup"
        )


def show_guide_page():
    section_header("Guide", "Complete usage, submission, storage, and access guidance for this database.")

    intro_left, intro_right = st.columns([1.2, 1])
    with intro_left:
        render_helper_card(
            "What this web app is for",
            "This database is designed to connect compounds, structural metadata, spectra previews, raw-data references, and publication details in one searchable workspace.",
        )
    with intro_right:
        render_helper_card(
            "Who can use it",
            "Researchers can search and compare records. Curators can submit, revise, import, and maintain compounds, peaks, and spectra links.",
        )

    section_header("How To Use")
    use_tabs = st.tabs(["Browse", "Submit", "Spectra & Raw Data", "Storage Layout", "Access & Deployment"])

    with use_tabs[0]:
            st.markdown(
                """
                1. Open `Dashboard` to see coverage, quick browsing, and backup.
                2. Use `Search & Match` for keyword lookup or 1H/13C spectral matching.
                3. Open `Compound Workspace` to inspect full records, references, linked files, and bioactivity tabs.
                4. Use `Bioactivity` to curate assay outcomes, potency values, and target annotations separately from the core compound metadata.
                5. Use `1H Peaks`, `13C Peaks`, and `Spectra Library` when you want to manage sub-records directly.
            """
        )

    with use_tabs[1]:
        st.markdown(
            """
            1. Start in `Compound Workspace` > `New Submission`.
            2. Fill the core identity fields first: trivial name, formula, SMILES/InChI/InChIKey, class, subclass, source category/organism, and structure.
            3. Add publication information, notes, and reference fields.
            4. Save the compound record.
            5. Add 1H peaks, 13C peaks, preview images, PDFs, raw-data links, and bioactivity records from their dedicated sections if needed.
            """
        )

    with use_tabs[2]:
        st.markdown(
            """
            1. Keep lightweight preview images locally or in Google Drive if you want them visible directly in the app.
            2. Store large raw 1H/13C data files in Google Drive to avoid filling the laptop.
            3. Paste the Google Drive sharing link into `Spectra Library` so the database stays metadata-first and device-friendly.
            4. Use spectrum types such as `1H`, `13C`, `COSY`, `HSQC`, or `HMBC` for preview images.
            5. Use `1H Raw Data`, `13C Raw Data`, `JCAMP-DX`, or `MNova` for raw downloadable files.
            6. If a Google Drive link points to an image and sharing is allowed, the spectra image can preview directly inside the web app without opening Google Drive first.
            7. For future structure search, keep `SMILES`, `InChI`, and `InChIKey` filled as consistently as possible.
            """
        )
        st.caption("Preview depends on the Google Drive link being shared with the right viewing permission.")

    with use_tabs[3]:
        st.markdown(
            """
            Recommended local folder layout in `Desktop/NMR_Database_Tyas`:

            1. `database/nmr.db` for the main SQLite metadata database.
            2. `database/backups/` for timestamped backup copies before major edits.
            3. `data/structures/` for lightweight structure images only.
            4. `data/spectra/` for lightweight preview images or PDFs only.
            5. `data/templates/` for batch import CSV templates generated by the app.
            6. `data/submissions/inbox/` for newly received material not yet curated.
            7. `data/submissions/reviewed/` for material already checked but not yet approved.
            8. `data/submissions/approved/` for curated source files that match the published record.
            9. `data/exports/` for CSV exports or reports shared with collaborators.
            """
        )
        st.markdown(
            """
            Recommended Google Drive layout:

            1. `NPDB_Public_Previews/` for shareable image previews.
            2. `NPDB_Raw_Data/Compound_Name_or_ID/1H/`
            3. `NPDB_Raw_Data/Compound_Name_or_ID/13C/`
            4. `NPDB_Raw_Data/Compound_Name_or_ID/JCAMP_DX/`
            5. `NPDB_Raw_Data/Compound_Name_or_ID/MNova/`
            6. `NPDB_Submission_Source/Year/LabMember_or_Paper/`
            """
        )
        st.markdown(
            """
            Recommended naming convention:

            1. Structure preview: `NPDB_<compound_id>_<trivial_name>_structure.png`
            2. Spectra preview: `NPDB_<compound_id>_<trivial_name>_<spectrum_type>_preview.png`
            3. Raw file: `NPDB_<compound_id>_<trivial_name>_<nucleus>_raw.<ext>`
            4. JCAMP-DX: `NPDB_<compound_id>_<trivial_name>_jcamp.dx`
            5. MNova: `NPDB_<compound_id>_<trivial_name>_mnova.mnova`
            """
        )
        st.caption("Keep one canonical file per dataset. If a better version appears later, replace the old file and update the database link instead of making silent duplicates.")

    with use_tabs[4]:
        st.markdown(
            """
            1. `http://localhost:8501` is still your local development address. It only works on your own machine while Streamlit is running there.
            2. A local app can sometimes be opened from another device on the same network using your computer IP, but that is temporary and depends on your network and firewall.
            3. If people need stable access from phone, laptop, Windows, macOS, or Linux, deploy the app to a server or cloud platform and share the public HTTPS URL from there.
            4. The current access gate supports either one shared login with `NPDB_ACCESS_USERNAME` and `NPDB_ACCESS_PASSWORD`, or multiple approved users with `NPDB_APPROVED_USERS`.
            5. After deployment, users should open the public URL, not `localhost`.
            6. Mobile access is possible after deployment, but the best experience still needs responsive visual QA.
            """
        )

    section_header("Important Notes")
    note_left, note_right = st.columns(2)
    with note_left:
        render_helper_card(
            "Storage limits",
            "This app does not enforce its own storage quota. The real limits come from your laptop disk, Google Drive quota, and whichever server or hosting platform you use.",
        )
    with note_right:
        render_helper_card(
            "Stable public access",
            "If you want the same address that people can open anytime from anywhere, you will need deployment. A local `localhost` address will not stay public forever and cannot be your permanent access URL.",
        )


# =========================
# Compound pages
# =========================
def show_compound_pages():
    compound_options = COMPOUND_PAGE_OPTIONS if can_edit_database() else ["Browse Record"]

    current_page = st.session_state.get("compound_page", "Browse Record")
    if current_page not in compound_options:
        current_page = "Browse Record"
        st.session_state["compound_page"] = current_page
        st.session_state["_pending_compound_page_radio"] = current_page

    compound_radio_kwargs = {
        "label": "Compound Workflow",
        "options": compound_options,
        "horizontal": True,
        "key": "compound_page_radio",
    }
    if "compound_page_radio" not in st.session_state:
        compound_radio_kwargs["index"] = compound_options.index(current_page)
    compound_page = st.radio(**compound_radio_kwargs)
    st.session_state["compound_page"] = compound_page

    render_helper_card(
        "Compound workspace",
        "Browse full records, create new submissions, import batches, update metadata, and remove outdated entries from one consistent workflow. The editor now lives in a single clear place instead of appearing as a duplicated menu.",
    )
    if not can_edit_database():
        render_read_only_notice("submit, edit, import, or delete compound records")

    if compound_page == "Browse Record":
        section_header("Compound Browser", "Inspect the full record, structure, spectral tables, and attached spectra from one focused review page.")
        compounds_df = load_all_compounds()

        if compounds_df.empty:
            st.info("No compounds available.")
        else:
            options = compounds_df[["id", "trivial_name"]].copy()
            options["label"] = options["id"].astype(str) + " - " + options["trivial_name"].fillna("")
            label_list = options["label"].tolist()

            default_index = 0
            selected_id = st.session_state.get("selected_compound_id")
            if selected_id is not None and selected_id in options["id"].tolist():
                default_index = options.index[options["id"] == selected_id][0]

            render_selector_card(
                "Record selector",
                "Choose a compound to inspect. The selected record is also reused in the edit and peak-management workspaces.",
            )
            selected = st.selectbox("Choose compound record", label_list, index=default_index)
            current_selected_id = int(selected.split(" - ")[0])
            st.session_state["selected_compound_id"] = current_selected_id
            show_compound_detail(current_selected_id)

    elif compound_page == "New Submission":
        section_header("New Submission", "Submit a new compound with a guided workflow, automatic file upload, and a review step before saving.")

        compounds_df = load_all_compounds()
        spectra_df = load_all_spectra_files()
        persist_wizard_inputs()
        for key in [
            "wizard_trivial_name",
            "wizard_iupac_name",
            "wizard_formula",
            "wizard_molecular_weight",
            "wizard_smiles",
            "wizard_inchi",
            "wizard_inchikey",
            "wizard_compound_class_select",
            "wizard_compound_class_custom",
            "wizard_compound_subclass_select",
            "wizard_compound_subclass_custom",
            "wizard_data_source_select",
            "wizard_data_source_custom",
            "wizard_source_category_select",
            "wizard_source_category_custom",
            "wizard_source_organism",
            "wizard_sample_code",
            "wizard_collection_location",
            "wizard_gps_coordinates",
            "wizard_depth_m",
            "wizard_uv_data",
            "wizard_ftir_data",
            "wizard_cd_data",
            "wizard_optical_rotation",
            "wizard_melting_point",
            "wizard_crystallization_method",
            "wizard_ccdc_number",
            "wizard_hrms_data",
            "wizard_structure_path",
            "wizard_submission_spectrum_type_select",
            "wizard_submission_spectrum_type_custom",
            "wizard_submission_spectra_note",
            "wizard_journal_name",
            "wizard_article_title",
            "wizard_publication_year",
            "wizard_volume",
            "wizard_issue",
            "wizard_pages",
            "wizard_doi",
            "wizard_note",
        ]:
            hydrate_wizard_widget(key)
        wizard_step = st.session_state.get("compound_wizard_step", 1)
        step_labels = {
            1: "Identity",
            2: "Origin",
            3: "Spectral Data & Files",
            4: "Reference & Review",
        }

        st.progress(wizard_step / 4)
        st.caption(
            f"Step {wizard_step} of 4: {step_labels[wizard_step]}. "
            "Your inputs stay in place while you move between steps."
        )

        if wizard_step == 1:
            c1, c2 = st.columns(2)
            with c1:
                st.text_input("Trivial Name", key="wizard_trivial_name")
                st.text_area("IUPAC Name", key="wizard_iupac_name")
                st.text_input("Molecular Formula", key="wizard_formula")
                st.text_input("Mr", key="wizard_molecular_weight")
                st.text_area("SMILES", key="wizard_smiles", placeholder="e.g. C1=CC=CC=C1")
            with c2:
                st.text_area("InChI", key="wizard_inchi", placeholder="e.g. InChI=1S/...")
                st.text_input("InChIKey", key="wizard_inchikey", placeholder="e.g. BSYNRYMUTXBXSQ-UHFFFAOYSA-N")
                class_options = build_existing_options(compounds_df, "compound_class", DEFAULT_CLASS_OPTIONS)
                subclass_options = build_existing_options(compounds_df, "compound_subclass")
                data_source_options = build_existing_options(compounds_df, "data_source", DEFAULT_DATA_SOURCE_OPTIONS)
                select_or_custom(
                    "Compound Class",
                    class_options,
                    "wizard_compound_class",
                    help_text="Choose an existing class or use Custom... to add a new compound class.",
                )
                select_or_custom("Compound Subclass", subclass_options, "wizard_compound_subclass")
                select_or_custom("Data Source", data_source_options, "wizard_data_source", value="Experimental")

        elif wizard_step == 2:
            c1, c2 = st.columns(2)
            with c1:
                source_options = build_existing_options(compounds_df, "source_category", DEFAULT_SOURCE_OPTIONS)
                select_or_custom(
                    "Source Category",
                    source_options,
                    "wizard_source_category",
                    help_text="Choose an existing source category or use Custom... to add a new one.",
                )
                st.text_input(
                    "Source Organism / Species (optional)",
                    key="wizard_source_organism",
                    placeholder="e.g. Halicondria sp. or Unknown sponge",
                )
                st.text_input("Sample Code", key="wizard_sample_code")
                st.text_input("Collection Location", key="wizard_collection_location")
            with c2:
                st.text_input("GPS Coordinates", key="wizard_gps_coordinates")
                st.text_input("Depth (m)", key="wizard_depth_m")
                st.text_area("Notes", key="wizard_note")

        elif wizard_step == 3:
            c1, c2 = st.columns(2)
            with c1:
                st.text_input("UV Data", key="wizard_uv_data")
                st.text_input("FTIR Data", key="wizard_ftir_data")
                st.text_area("Circular Dichroism (CD / ECD)", key="wizard_cd_data")
                st.text_input("Optical Rotation", key="wizard_optical_rotation")
                st.text_input("Melting Point", key="wizard_melting_point")
                st.text_input("Crystallization Method", key="wizard_crystallization_method")
                st.text_area(
                    "HRMS Data",
                    key="wizard_hrms_data",
                    placeholder="e.g. HRMS (ESI) m/z: [M + Na]+ calcd..., found...",
                )
                st.text_input("CCDC", key="wizard_ccdc_number")
            with c2:
                st.text_input(
                    "Structure Image Path (optional)",
                    key="wizard_structure_path",
                    placeholder="e.g. data/structures/example.png",
                )
                st.file_uploader(
                    "Upload Structure Image",
                    type=["png", "jpg", "jpeg", "webp"],
                    key="wizard_structure_upload",
                )
                wizard_spectrum_options = build_existing_options(
                    spectra_df,
                    "spectrum_type",
                    DEFAULT_SPECTRUM_TYPES,
                )
                select_or_custom(
                    "Uploaded Spectra Type",
                    wizard_spectrum_options,
                    "wizard_submission_spectrum_type",
                    value="Supporting Data",
                    help_text="All files uploaded in this step will use the same type label. You can fine-tune them later in the Spectra section.",
                )
                st.file_uploader(
                    "Upload Supporting Spectra Files",
                    accept_multiple_files=True,
                    key="wizard_submission_spectra_uploads",
                )
                st.text_area("Uploaded Spectra Note", key="wizard_submission_spectra_note")
                st.caption("Tip: for large raw 1H/13C datasets, store the raw files in Google Drive and register the share link later from Spectra Library. Keep only lightweight preview files locally when necessary.")

        else:
            c1, c2 = st.columns(2)
            with c1:
                st.text_input("Journal Name", key="wizard_journal_name")
                st.text_input("Article Title", key="wizard_article_title")
                st.text_input("Publication Year", key="wizard_publication_year")
                st.text_input("Volume", key="wizard_volume")
                st.text_input("Issue", key="wizard_issue")
                st.text_input("Pages", key="wizard_pages")
                st.text_input("DOI", key="wizard_doi")
            with c2:
                draft_row = {
                    "trivial_name": get_wizard_value("wizard_trivial_name", ""),
                    "molecular_formula": get_wizard_value("wizard_formula", ""),
                    "smiles": get_wizard_value("wizard_smiles", ""),
                    "inchi": get_wizard_value("wizard_inchi", ""),
                    "inchikey": get_wizard_value("wizard_inchikey", ""),
                    "compound_class": get_wizard_value("wizard_compound_class_custom", "") or get_wizard_value("wizard_compound_class_select", ""),
                    "source_category": get_wizard_value("wizard_source_category_custom", "") or get_wizard_value("wizard_source_category_select", ""),
                    "source_organism": get_wizard_value("wizard_source_organism", ""),
                    "source_material": source_summary_from_record(
                        {
                            "source_category": get_wizard_value("wizard_source_category_custom", "") or get_wizard_value("wizard_source_category_select", ""),
                            "source_organism": get_wizard_value("wizard_source_organism", ""),
                            "source_material": "",
                        }
                    ),
                    "data_source": get_wizard_value("wizard_data_source_custom", "") or get_wizard_value("wizard_data_source_select", ""),
                    "hrms_data": get_wizard_value("wizard_hrms_data", ""),
                    "doi": get_wizard_value("wizard_doi", ""),
                    "journal_name": get_wizard_value("wizard_journal_name", ""),
                    "article_title": get_wizard_value("wizard_article_title", ""),
                    "structure_image_path": get_wizard_value("wizard_structure_path", "") or ("uploaded" if get_wizard_value("wizard_structure_upload") else ""),
                }
                completeness_preview = calculate_completeness_score(
                    draft_row,
                    pd.DataFrame(),
                    pd.DataFrame(),
                    pd.DataFrame(),
                )
                st.markdown('<div class="panel-card">', unsafe_allow_html=True)
                st.write(f"**Draft completeness estimate:** {completeness_preview}%")
                st.write(f"**Trivial Name:** {clean_text(draft_row['trivial_name'])}")
                st.write(f"**Formula:** {clean_text(draft_row['molecular_formula'])}")
                st.write(f"**SMILES:** {clean_text(draft_row['smiles'])}")
                st.write(f"**InChIKey:** {clean_text(draft_row['inchikey'])}")
                st.write(f"**Class:** {clean_text(draft_row['compound_class'])}")
                st.write(f"**Source Category:** {clean_text(draft_row['source_category'])}")
                st.write(f"**Source Organism:** {clean_text(draft_row['source_organism'])}")
                st.write(f"**Source Summary:** {clean_text(draft_row['source_material'])}")
                st.write(f"**Data Source:** {clean_text(draft_row['data_source'])}")
                st.write(f"**Journal:** {clean_text(get_wizard_value('wizard_journal_name'))}")
                st.write(f"**Article:** {clean_text(get_wizard_value('wizard_article_title'))}")
                st.markdown('</div>', unsafe_allow_html=True)

        nav_left, nav_right = st.columns([1, 1])
        with nav_left:
            if wizard_step > 1 and st.button("Back", use_container_width=True, key=f"wizard_back_{wizard_step}"):
                persist_wizard_inputs()
                st.session_state["compound_wizard_step"] = wizard_step - 1
                st.rerun()

        with nav_right:
            if wizard_step < 4:
                if st.button("Continue", use_container_width=True, key=f"wizard_next_{wizard_step}"):
                    persist_wizard_inputs()
                    if wizard_step == 1 and not maybe_blank(get_wizard_value("wizard_trivial_name")):
                        st.error("Trivial Name is required before moving to the next step.")
                    else:
                        st.session_state["compound_wizard_step"] = wizard_step + 1
                        st.rerun()
            else:
                if st.button("Save New Record", use_container_width=True, key="wizard_submit_compound"):
                    persist_wizard_inputs()
                    trivial_name = maybe_blank(get_wizard_value("wizard_trivial_name"))
                    iupac_name = maybe_blank(get_wizard_value("wizard_iupac_name"))
                    molecular_formula = maybe_blank(get_wizard_value("wizard_formula"))
                    smiles = maybe_blank(get_wizard_value("wizard_smiles"))
                    inchi = maybe_blank(get_wizard_value("wizard_inchi"))
                    inchikey = maybe_blank(get_wizard_value("wizard_inchikey"))
                    compound_class = maybe_blank(get_wizard_value("wizard_compound_class_custom")) or maybe_blank(get_wizard_value("wizard_compound_class_select"))
                    compound_subclass = maybe_blank(get_wizard_value("wizard_compound_subclass_custom")) or maybe_blank(get_wizard_value("wizard_compound_subclass_select"))
                    source_category = maybe_blank(get_wizard_value("wizard_source_category_custom")) or maybe_blank(get_wizard_value("wizard_source_category_select"))
                    source_organism = maybe_blank(get_wizard_value("wizard_source_organism"))
                    _, _, source_material = infer_source_fields(source_category, source_organism, "")
                    sample_code = maybe_blank(get_wizard_value("wizard_sample_code"))
                    collection_location = maybe_blank(get_wizard_value("wizard_collection_location"))
                    gps_coordinates = maybe_blank(get_wizard_value("wizard_gps_coordinates"))
                    depth_m_text = maybe_blank(get_wizard_value("wizard_depth_m"))
                    uv_data = maybe_blank(get_wizard_value("wizard_uv_data"))
                    ftir_data = maybe_blank(get_wizard_value("wizard_ftir_data"))
                    cd_data = maybe_blank(get_wizard_value("wizard_cd_data"))
                    optical_rotation = maybe_blank(get_wizard_value("wizard_optical_rotation"))
                    melting_point = maybe_blank(get_wizard_value("wizard_melting_point"))
                    crystallization_method = maybe_blank(get_wizard_value("wizard_crystallization_method"))
                    structure_image_path = maybe_blank(get_wizard_value("wizard_structure_path"))
                    structure_upload = get_wizard_value("wizard_structure_upload")
                    journal_name = maybe_blank(get_wizard_value("wizard_journal_name"))
                    article_title = maybe_blank(get_wizard_value("wizard_article_title"))
                    publication_year = maybe_blank(get_wizard_value("wizard_publication_year"))
                    volume = maybe_blank(get_wizard_value("wizard_volume"))
                    issue = maybe_blank(get_wizard_value("wizard_issue"))
                    pages = maybe_blank(get_wizard_value("wizard_pages"))
                    doi = maybe_blank(get_wizard_value("wizard_doi"))
                    ccdc_number = maybe_blank(get_wizard_value("wizard_ccdc_number"))
                    molecular_weight_text = maybe_blank(get_wizard_value("wizard_molecular_weight"))
                    hrms_data = maybe_blank(get_wizard_value("wizard_hrms_data"))
                    data_source = maybe_blank(get_wizard_value("wizard_data_source_custom")) or maybe_blank(get_wizard_value("wizard_data_source_select"))
                    note = maybe_blank(get_wizard_value("wizard_note"))
                    uploaded_spectra = get_wizard_value("wizard_submission_spectra_uploads") or []
                    uploaded_spectrum_type = maybe_blank(get_wizard_value("wizard_submission_spectrum_type_custom")) or maybe_blank(get_wizard_value("wizard_submission_spectrum_type_select")) or "Supporting Data"
                    uploaded_spectrum_note = maybe_blank(get_wizard_value("wizard_submission_spectra_note"))

                    if not trivial_name:
                        st.error("Trivial Name is required.")
                        st.stop()

                    depth_value = safe_float_or_none(depth_m_text)
                    if depth_m_text and depth_value is None:
                        st.error("Depth (m) must be a valid number.")
                        st.stop()

                    molecular_weight_value = safe_float_or_none(molecular_weight_text)
                    if molecular_weight_text and molecular_weight_value is None:
                        st.error("Mr must be a valid number.")
                        st.stop()

                    if structure_upload is not None:
                        structure_image_path = save_uploaded_asset(
                            structure_upload,
                            STRUCTURES_DIR,
                            f"{trivial_name}_{sample_code or 'structure'}",
                        )

                    new_id = insert_compound_record(
                        trivial_name=trivial_name,
                        iupac_name=iupac_name,
                        molecular_formula=molecular_formula,
                        compound_class=compound_class,
                        compound_subclass=compound_subclass,
                        smiles=smiles,
                        inchi=inchi,
                        inchikey=inchikey,
                        source_category=source_category,
                        source_organism=source_organism,
                        source_material=source_material,
                        sample_code=sample_code,
                        collection_location=collection_location,
                        gps_coordinates=gps_coordinates,
                        depth_m=depth_value,
                        uv_data=uv_data,
                        ftir_data=ftir_data,
                        cd_data=cd_data,
                        optical_rotation=optical_rotation,
                        melting_point=melting_point,
                        crystallization_method=crystallization_method,
                        structure_image_path=structure_image_path,
                        journal_name=journal_name,
                        article_title=article_title,
                        publication_year=publication_year,
                        volume=volume,
                        issue=issue,
                        pages=pages,
                        doi=doi,
                        ccdc_number=ccdc_number,
                        molecular_weight=molecular_weight_value,
                        hrms_data=hrms_data,
                        data_source=data_source,
                        note=note,
                    )

                    for uploaded_file in uploaded_spectra:
                        saved_path = save_uploaded_asset(
                            uploaded_file,
                            SPECTRA_DIR,
                            f"compound_{new_id}_{uploaded_spectrum_type}_{uploaded_file.name}",
                        )
                        insert_spectrum_file_record(
                            compound_id=new_id,
                            spectrum_type=uploaded_spectrum_type,
                            file_path=saved_path,
                            note=uploaded_spectrum_note,
                        )

                    st.success(f"Record saved successfully. New Compound ID: {new_id}")
                    reset_compound_wizard()
                    open_compound_detail(new_id)
                    st.rerun()

    elif compound_page == "Batch Import":
        render_batch_import_workspace()

    elif compound_page == "Update Metadata":
        section_header("Update Metadata", "Revise compound metadata, references, and structure links without leaving the database workspace.")
        compounds_df = load_all_compounds()

        if compounds_df.empty:
            st.info("No compounds available.")
        else:
            options = compounds_df[["id", "trivial_name"]].copy()
            options["label"] = options["id"].astype(str) + " - " + options["trivial_name"].fillna("")
            label_list = options["label"].tolist()

            default_index = 0
            selected_id = st.session_state.get("selected_compound_id")
            if selected_id is not None and selected_id in options["id"].tolist():
                default_index = options.index[options["id"] == selected_id][0]

            render_selector_card(
                "Editing target",
                "Choose the record you want to revise. This is the only main editing entry point in the compound workspace.",
            )
            selected_label = st.selectbox(
                "Select record to edit",
                label_list,
                index=default_index,
                key="edit_compound_select"
            )

            edit_compound_id = int(selected_label.split(" - ")[0])
            st.session_state["selected_compound_id"] = edit_compound_id

            row_df = load_compound_row(edit_compound_id)
            if row_df.empty:
                st.error("Record not found.")
            else:
                row = row_df.iloc[0]


                col1, col2 = st.columns(2)

                with col1:
                    trivial_name = st.text_input("Trivial Name", value=maybe_blank(row["trivial_name"]))
                    iupac_name = st.text_area("IUPAC Name", value=maybe_blank(row["iupac_name"]))
                    molecular_formula = st.text_input("Molecular Formula", value=maybe_blank(row["molecular_formula"]))
                    smiles = st.text_area("SMILES", value=maybe_blank(row.get("smiles")))
                    inchi = st.text_area("InChI", value=maybe_blank(row.get("inchi")))
                    inchikey = st.text_input("InChIKey", value=maybe_blank(row.get("inchikey")))
                    compound_class = select_or_custom(
                        "Compound Class",
                        build_existing_options(compounds_df, "compound_class", DEFAULT_CLASS_OPTIONS),
                        f"edit_compound_class_{edit_compound_id}",
                        value=maybe_blank(row["compound_class"]),
                        help_text="Choose an existing class or use Custom... to add a new compound class.",
                    )
                    compound_subclass = select_or_custom(
                        "Compound Subclass",
                        build_existing_options(compounds_df, "compound_subclass"),
                        f"edit_compound_subclass_{edit_compound_id}",
                        value=maybe_blank(row["compound_subclass"]),
                    )
                    source_category = select_or_custom(
                        "Source Category",
                        build_existing_options(compounds_df, "source_category", DEFAULT_SOURCE_OPTIONS),
                        f"edit_source_category_{edit_compound_id}",
                        value=maybe_blank(row.get("source_category")),
                        help_text="Choose an existing source category or use Custom... to add a new one.",
                    )
                    source_organism = st.text_input(
                        "Source Organism / Species (optional)",
                        value=maybe_blank(row.get("source_organism")),
                    )
                    sample_code = st.text_input("Sample Code", value=maybe_blank(row["sample_code"]))
                    collection_location = st.text_input("Collection Location", value=maybe_blank(row["collection_location"]))
                    gps_coordinates = st.text_input("GPS Coordinates", value=maybe_blank(row["gps_coordinates"]))
                    depth_m_text = st.text_input("Depth (m)", value=maybe_blank(row["depth_m"]))

                with col2:
                    uv_data = st.text_input("UV Data", value=maybe_blank(row["uv_data"]))
                    ftir_data = st.text_input("FTIR Data", value=maybe_blank(row["ftir_data"]))
                    cd_data = st.text_area("Circular Dichroism (CD / ECD)", value=maybe_blank(row.get("cd_data")))
                    optical_rotation = st.text_input("Optical Rotation", value=maybe_blank(row["optical_rotation"]))
                    melting_point = st.text_input("Melting Point", value=maybe_blank(row["melting_point"]))
                    crystallization_method = st.text_input("Crystallization Method", value=maybe_blank(row["crystallization_method"]))
                    structure_image_path = st.text_input("Structure Image Path", value=maybe_blank(row["structure_image_path"]))
                    structure_upload = st.file_uploader(
                        "Replace Structure Image",
                        type=["png", "jpg", "jpeg", "webp"],
                        key=f"edit_structure_upload_{edit_compound_id}",
                    )
                    journal_name = st.text_input("Journal Name", value=maybe_blank(row["journal_name"]))
                    article_title = st.text_area("Article Title", value=maybe_blank(row["article_title"]))
                    publication_year = st.text_input("Publication Year", value=maybe_blank(row["publication_year"]))
                    volume = st.text_input("Volume", value=maybe_blank(row["volume"]))
                    issue = st.text_input("Issue / Journal Number", value=maybe_blank(row["issue"]))
                    pages = st.text_input("Pages", value=maybe_blank(row["pages"]))
                    doi = st.text_input("DOI", value=maybe_blank(row["doi"]))
                    ccdc_number = st.text_input("CCDC", value=maybe_blank(row["ccdc_number"]))
                    molecular_weight_text = st.text_input("Mr", value=maybe_blank(row["molecular_weight"]))
                    hrms_data = st.text_area("HRMS Data", value=maybe_blank(row["hrms_data"]))
                    data_source = select_or_custom(
                        "Data Source",
                        build_existing_options(compounds_df, "data_source", DEFAULT_DATA_SOURCE_OPTIONS),
                        f"edit_data_source_{edit_compound_id}",
                        value=maybe_blank(row["data_source"]),
                    )

                note = st.text_area("Note", value=maybe_blank(row["note"]))
                submitted_edit = st.button("Save Changes", key="edit_compound_submit")

                if submitted_edit:
                    if not trivial_name.strip():
                        st.error("Trivial Name is required.")
                    else:
                        depth_value = None
                        if depth_m_text.strip():
                            try:
                                depth_value = float(depth_m_text.strip())
                            except ValueError:
                                st.error("Depth (m) must be a valid number.")
                                st.stop()

                        molecular_weight_value = None
                        if molecular_weight_text.strip():
                            try:
                                molecular_weight_value = float(molecular_weight_text.strip())
                            except ValueError:
                                st.error("Mr must be a valid number.")
                                st.stop()

                        if structure_upload is not None:
                            structure_image_path = save_uploaded_asset(
                                structure_upload,
                                STRUCTURES_DIR,
                                f"{trivial_name}_{sample_code or edit_compound_id}_structure",
                            )

                        source_category, source_organism, source_material = infer_source_fields(
                            source_category.strip(),
                            source_organism.strip(),
                            row.get("source_material"),
                        )

                        update_compound_record(
                            compound_id=edit_compound_id,
                            trivial_name=trivial_name.strip(),
                            iupac_name=iupac_name.strip(),
                            molecular_formula=molecular_formula.strip(),
                            compound_class=compound_class.strip(),
                            compound_subclass=compound_subclass.strip(),
                            smiles=smiles.strip(),
                            inchi=inchi.strip(),
                            inchikey=inchikey.strip(),
                            source_category=source_category.strip(),
                            source_organism=source_organism.strip(),
                            source_material=source_material.strip(),
                            sample_code=sample_code.strip(),
                            collection_location=collection_location.strip(),
                            gps_coordinates=gps_coordinates.strip(),
                            depth_m=depth_value,
                            uv_data=uv_data.strip(),
                            ftir_data=ftir_data.strip(),
                            cd_data=cd_data.strip(),
                            optical_rotation=optical_rotation.strip(),
                            melting_point=melting_point.strip(),
                            crystallization_method=crystallization_method.strip(),
                            structure_image_path=structure_image_path.strip(),
                            journal_name=journal_name.strip(),
                            article_title=article_title.strip(),
                            publication_year=publication_year.strip(),
                            volume=volume.strip(),
                            issue=issue.strip(),
                            pages=pages.strip(),
                            doi=doi.strip(),
                            ccdc_number=ccdc_number.strip(),
                            molecular_weight=molecular_weight_value,
                            hrms_data=hrms_data.strip(),
                            data_source=data_source.strip(),
                            note=note.strip()
                        )

                        st.success(f"Record ID {edit_compound_id} updated successfully.")

                        left_btn, right_btn = st.columns([1, 1])
                        with left_btn:
                            if st.button("Open Updated Record", key=f"open_updated_compound_{edit_compound_id}"):
                                open_compound_detail(edit_compound_id)
                                st.rerun()
                        with right_btn:
                            if st.button("Refresh Form", key=f"stay_editor_{edit_compound_id}"):
                                st.rerun()

    else:
        section_header("Delete Record", "Delete a compound together with all related spectral records.")
        compounds_df = load_all_compounds()

        if compounds_df.empty:
            st.info("No compounds available.")
        else:
            options = compounds_df[["id", "trivial_name"]].copy()
            options["label"] = options["id"].astype(str) + " - " + options["trivial_name"].fillna("")
            selected_label = st.selectbox("Select record to delete", options["label"].tolist(), key="delete_compound_select")
            compound_id = int(selected_label.split(" - ")[0])

            row_df = load_compound_row(compound_id)
            if not row_df.empty:
                row = row_df.iloc[0]
                proton_count = len(load_proton_data(compound_id))
                carbon_count = len(load_carbon_data(compound_id))
                spectra_count = len(load_spectra_files(compound_id))

                st.warning("This action cannot be undone.")
                c1, c2, c3 = st.columns(3)
                render_metric_card("1H records", proton_count, c1)
                render_metric_card("13C records", carbon_count, c2)
                render_metric_card("Spectra records", spectra_count, c3)

                st.markdown('<div class="panel-card">', unsafe_allow_html=True)
                st.write(f"**Compound:** {clean_text(row['trivial_name'])}")
                st.write(f"**Compound ID:** {compound_id}")
                st.markdown('</div>', unsafe_allow_html=True)

                with st.form("delete_compound_form"):
                    confirm = st.checkbox("I understand that this will permanently delete the compound record and all related database records.")
                    submitted_delete = st.form_submit_button("Delete Record")

                if submitted_delete:
                    if not confirm:
                        st.error("Please confirm deletion first.")
                    else:
                        delete_compound_record(compound_id)
                        st.success(f"Compound ID {compound_id} and its related records were deleted.")
                        st.session_state["selected_compound_id"] = None


# =========================
# 1H pages
# =========================
def show_proton_pages():
    if not can_edit_database():
        section_header("1H Peak Browser", "Read-only access to proton assignments. Full edit access remains reserved for the database owner.")
        render_read_only_notice("add, edit, or delete 1H peak records")
        compounds_df = load_all_compounds()
        if compounds_df.empty:
            st.info("No compounds available.")
            return
        options = compounds_df[["id", "trivial_name"]].copy()
        options["label"] = options["id"].astype(str) + " - " + options["trivial_name"].fillna("")
        default_index = 0
        selected_id = st.session_state.get("selected_compound_id")
        if selected_id is not None and selected_id in options["id"].tolist():
            default_index = options.index[options["id"] == selected_id][0]
        selected_compound_label = st.selectbox("Select Compound", options["label"].tolist(), index=default_index, key="readonly_proton_compound")
        compound_id = int(selected_compound_label.split(" - ")[0])
        proton_df = load_proton_data(compound_id)
        if proton_df.empty:
            st.info("No 1H NMR data available for this compound.")
        else:
            proton_df = proton_df.rename(columns={
                "id": "ID",
                "delta_ppm": "δH (ppm)",
                "multiplicity": "Multiplicity",
                "j_value": "J Value",
                "proton_count": "Proton Count",
                "assignment": "Assignment",
                "solvent": "Solvent",
                "instrument_mhz": "Instrument (MHz)",
                "note": "Note",
            })
            st.dataframe(proton_df, width="stretch", hide_index=True)
        return

    proton_page = st.radio(
        "1H Peak Tools",
        ["Add Peak", "Edit Peak", "Delete Peak"],
        horizontal=True
    )

    if proton_page == "Add Peak":
        section_header("Add 1H Peak", "Register a single 1H NMR peak for a selected compound.")
        compounds_df = load_all_compounds()

        if compounds_df.empty:
            st.info("No compounds available. Please add a compound first.")
        else:
            options = compounds_df[["id", "trivial_name"]].copy()
            options["label"] = options["id"].astype(str) + " - " + options["trivial_name"].fillna("")
            label_list = options["label"].tolist()

            default_index = 0
            selected_id = st.session_state.get("selected_compound_id")
            if selected_id is not None and selected_id in options["id"].tolist():
                default_index = options.index[options["id"] == selected_id][0]

            selected_compound_label = st.selectbox(
                "Select Compound",
                label_list,
                index=default_index,
                key="add1h_compound"
            )

            selected_compound_id = int(selected_compound_label.split(" - ")[0])

            with st.form("add_1h_form", clear_on_submit=False):
                c1, c2 = st.columns(2)

                with c1:
                    delta_ppm_text = st.text_input("δH (ppm)")
                    multiplicity = st.text_input("Multiplicity")
                    j_value = st.text_input("J Value")
                    proton_count = st.text_input("Proton Count", placeholder="e.g. 1H or 3H")
                    assignment = st.text_input("Assignment")

                with c2:
                    solvent = st.text_input("Solvent", value="CDCl3")
                    instrument_mhz_text = st.text_input("Instrument (MHz)", value="500")
                    note = st.text_area("Note")

                submitted_1h = st.form_submit_button("Save 1H Peak")

            if submitted_1h:
                if not delta_ppm_text.strip():
                    st.error("δH (ppm) is required.")
                elif not assignment.strip():
                    st.error("Assignment is required.")
                else:
                    try:
                        delta_ppm_value = float(delta_ppm_text.strip())
                    except ValueError:
                        st.error("δH (ppm) must be a valid number.")
                        st.stop()

                    instrument_mhz_value = None
                    if instrument_mhz_text.strip():
                        try:
                            instrument_mhz_value = float(instrument_mhz_text.strip())
                        except ValueError:
                            st.error("Instrument (MHz) must be a valid number.")
                            st.stop()

                    new_peak_id = insert_proton_record(
                        compound_id=selected_compound_id,
                        delta_ppm=delta_ppm_value,
                        multiplicity=multiplicity.strip(),
                        j_value=j_value.strip(),
                        proton_count=proton_count.strip(),
                        assignment=assignment.strip(),
                        solvent=solvent.strip(),
                        instrument_mhz=instrument_mhz_value,
                        note=note.strip()
                    )

                    st.success(f"1H NMR peak saved successfully. New Peak ID: {new_peak_id}")

                    if st.button("Open Record", key=f"open_detail_after_1h_{new_peak_id}"):
                        open_compound_detail(selected_compound_id)
                        st.rerun()

    elif proton_page == "Edit Peak":
        section_header("Edit 1H Peak", "Update a single 1H record directly from the web interface.")
        proton_df = load_all_proton_data()

        if proton_df.empty:
            st.info("No 1H NMR records available.")
        else:
            proton_df["label"] = (
                proton_df["id"].astype(str)
                + " | "
                + proton_df["trivial_name"].fillna("-").astype(str)
                + " | δH "
                + proton_df["delta_ppm"].astype(str)
                + " | "
                + proton_df["assignment"].fillna("-").astype(str)
            )

            selected_label = st.selectbox(
                "Select 1H NMR Record",
                proton_df["label"].tolist(),
                key="edit_1h_select"
            )

            proton_id = int(selected_label.split(" | ")[0])
            row_df = load_proton_row(proton_id)

            if row_df.empty:
                st.error("1H NMR record not found.")
            else:
                row = row_df.iloc[0]
                compounds_df = load_all_compounds()
                options = compounds_df[["id", "trivial_name"]].copy()
                options["label"] = options["id"].astype(str) + " - " + options["trivial_name"].fillna("")
                label_list = options["label"].tolist()

                default_index = 0
                if row["compound_id"] in options["id"].tolist():
                    default_index = options.index[options["id"] == row["compound_id"]][0]

                with st.form("edit_1h_form", clear_on_submit=False):
                    selected_compound_label = st.selectbox(
                        "Select Compound",
                        label_list,
                        index=default_index,
                        key="edit1h_compound"
                    )

                    c1, c2 = st.columns(2)

                    with c1:
                        delta_ppm_text = st.text_input("δH (ppm)", value=maybe_blank(row["delta_ppm"]))
                        multiplicity = st.text_input("Multiplicity", value=maybe_blank(row["multiplicity"]))
                        j_value = st.text_input("J Value", value=maybe_blank(row["j_value"]))
                        proton_count = st.text_input("Proton Count", value=maybe_blank(row["proton_count"]))
                        assignment = st.text_input("Assignment", value=maybe_blank(row["assignment"]))

                    with c2:
                        solvent = st.text_input("Solvent", value=maybe_blank(row["solvent"]))
                        instrument_mhz_text = st.text_input("Instrument (MHz)", value=maybe_blank(row["instrument_mhz"]))
                        note = st.text_area("Note", value=maybe_blank(row["note"]))

                    submitted_edit_1h = st.form_submit_button("Save Changes")

                if submitted_edit_1h:
                    if not delta_ppm_text.strip():
                        st.error("δH (ppm) is required.")
                    elif not assignment.strip():
                        st.error("Assignment is required.")
                    else:
                        try:
                            delta_ppm_value = float(delta_ppm_text.strip())
                        except ValueError:
                            st.error("δH (ppm) must be a valid number.")
                            st.stop()

                        instrument_mhz_value = None
                        if instrument_mhz_text.strip():
                            try:
                                instrument_mhz_value = float(instrument_mhz_text.strip())
                            except ValueError:
                                st.error("Instrument (MHz) must be a valid number.")
                                st.stop()

                        selected_compound_id = int(selected_compound_label.split(" - ")[0])

                        update_proton_record(
                            proton_id=proton_id,
                            compound_id=selected_compound_id,
                            delta_ppm=delta_ppm_value,
                            multiplicity=multiplicity.strip(),
                            j_value=j_value.strip(),
                            proton_count=proton_count.strip(),
                            assignment=assignment.strip(),
                            solvent=solvent.strip(),
                            instrument_mhz=instrument_mhz_value,
                            note=note.strip()
                        )

                        st.success(f"1H NMR record ID {proton_id} updated successfully.")

                        left_btn, right_btn = st.columns([1, 1])
                        with left_btn:
                            if st.button("Open Record", key=f"open_detail_after_edit_1h_{proton_id}"):
                                open_compound_detail(selected_compound_id)
                                st.rerun()
                        with right_btn:
                            if st.button("Refresh Form", key=f"reload_edit_1h_{proton_id}"):
                                st.rerun()

    else:
        section_header("Delete 1H Peak", "Remove a single 1H NMR record.")
        proton_df = load_all_proton_data()

        if proton_df.empty:
            st.info("No 1H NMR records available.")
        else:
            proton_df["label"] = (
                proton_df["id"].astype(str)
                + " | "
                + proton_df["trivial_name"].fillna("-").astype(str)
                + " | δH "
                + proton_df["delta_ppm"].astype(str)
                + " | "
                + proton_df["assignment"].fillna("-").astype(str)
            )

            selected_label = st.selectbox("Select 1H NMR Record to Delete", proton_df["label"].tolist(), key="delete_1h_select")
            proton_id = int(selected_label.split(" | ")[0])
            row_df = load_proton_row(proton_id)

            if not row_df.empty:
                row = row_df.iloc[0]
                st.warning("This action cannot be undone.")
                st.markdown('<div class="panel-card">', unsafe_allow_html=True)
                st.write(f"**Record ID:** {proton_id}")
                st.write(f"**Compound ID:** {row['compound_id']}")
                st.write(f"**δH (ppm):** {clean_text(row['delta_ppm'])}")
                st.write(f"**Assignment:** {clean_text(row['assignment'])}")
                st.markdown('</div>', unsafe_allow_html=True)

                with st.form("delete_1h_form"):
                    confirm = st.checkbox("I understand that this will permanently delete this 1H NMR record.")
                    submitted_delete = st.form_submit_button("Delete 1H Record")

                if submitted_delete:
                    if not confirm:
                        st.error("Please confirm deletion first.")
                    else:
                        compound_id = int(row["compound_id"])
                        delete_proton_record_by_id(proton_id)
                        st.success(f"1H NMR record ID {proton_id} was deleted.")
                        if st.button("Open Record", key=f"open_detail_after_delete_1h_{proton_id}"):
                            open_compound_detail(compound_id)
                            st.rerun()


# =========================
# 13C pages
# =========================
def show_carbon_pages():
    if not can_edit_database():
        section_header("13C Peak Browser", "Read-only access to carbon assignments. Full edit access remains reserved for the database owner.")
        render_read_only_notice("add, edit, or delete 13C peak records")
        compounds_df = load_all_compounds()
        if compounds_df.empty:
            st.info("No compounds available.")
            return
        options = compounds_df[["id", "trivial_name"]].copy()
        options["label"] = options["id"].astype(str) + " - " + options["trivial_name"].fillna("")
        default_index = 0
        selected_id = st.session_state.get("selected_compound_id")
        if selected_id is not None and selected_id in options["id"].tolist():
            default_index = options.index[options["id"] == selected_id][0]
        selected_compound_label = st.selectbox("Select Compound", options["label"].tolist(), index=default_index, key="readonly_carbon_compound")
        compound_id = int(selected_compound_label.split(" - ")[0])
        carbon_df = load_carbon_data(compound_id)
        if carbon_df.empty:
            st.info("No 13C NMR data available for this compound.")
        else:
            carbon_df = carbon_df.rename(columns={
                "id": "ID",
                "delta_ppm": "δC (ppm)",
                "carbon_type": "Carbon Type",
                "assignment": "Assignment",
                "solvent": "Solvent",
                "instrument_mhz": "Instrument (MHz)",
                "note": "Note",
            })
            st.dataframe(carbon_df, width="stretch", hide_index=True)
        return

    carbon_page = st.radio(
        "13C Peak Tools",
        ["Add Peak", "Edit Peak", "Delete Peak"],
        horizontal=True
    )

    if carbon_page == "Add Peak":
        section_header("Add 13C Peak", "Register a single 13C NMR peak for a selected compound.")
        compounds_df = load_all_compounds()

        if compounds_df.empty:
            st.info("No compounds available. Please add a compound first.")
        else:
            options = compounds_df[["id", "trivial_name"]].copy()
            options["label"] = options["id"].astype(str) + " - " + options["trivial_name"].fillna("")
            label_list = options["label"].tolist()

            default_index = 0
            selected_id = st.session_state.get("selected_compound_id")
            if selected_id is not None and selected_id in options["id"].tolist():
                default_index = options.index[options["id"] == selected_id][0]

            selected_compound_label = st.selectbox(
                "Select Compound",
                label_list,
                index=default_index,
                key="add13c_compound"
            )

            selected_compound_id = int(selected_compound_label.split(" - ")[0])

            with st.form("add_13c_form", clear_on_submit=False):
                c1, c2 = st.columns(2)

                with c1:
                    delta_ppm_text = st.text_input("δC (ppm)")
                    carbon_type = st.text_input("Carbon Type", placeholder="e.g. CH3, CH2, CH, C")
                    assignment = st.text_input("Assignment")

                with c2:
                    solvent = st.text_input("Solvent", value="CDCl3", key="add13c_solvent")
                    instrument_mhz_text = st.text_input("Instrument (MHz)", value="125")
                    note = st.text_area("Note", key="add13c_note")

                submitted_13c = st.form_submit_button("Save 13C Peak")

            if submitted_13c:
                if not delta_ppm_text.strip():
                    st.error("δC (ppm) is required.")
                elif not assignment.strip():
                    st.error("Assignment is required.")
                else:
                    try:
                        delta_ppm_value = float(delta_ppm_text.strip())
                    except ValueError:
                        st.error("δC (ppm) must be a valid number.")
                        st.stop()

                    instrument_mhz_value = None
                    if instrument_mhz_text.strip():
                        try:
                            instrument_mhz_value = float(instrument_mhz_text.strip())
                        except ValueError:
                            st.error("Instrument (MHz) must be a valid number.")
                            st.stop()

                    new_peak_id = insert_carbon_record(
                        compound_id=selected_compound_id,
                        delta_ppm=delta_ppm_value,
                        carbon_type=carbon_type.strip(),
                        assignment=assignment.strip(),
                        solvent=solvent.strip(),
                        instrument_mhz=instrument_mhz_value,
                        note=note.strip()
                    )

                    st.success(f"13C NMR peak saved successfully. New Peak ID: {new_peak_id}")

                    if st.button("Open Record", key=f"open_detail_after_13c_{new_peak_id}"):
                        open_compound_detail(selected_compound_id)
                        st.rerun()

    elif carbon_page == "Edit Peak":
        section_header("Edit 13C Peak", "Update a single 13C record directly from the web interface.")
        carbon_df = load_all_carbon_data()

        if carbon_df.empty:
            st.info("No 13C NMR records available.")
        else:
            carbon_df["label"] = (
                carbon_df["id"].astype(str)
                + " | "
                + carbon_df["trivial_name"].fillna("-").astype(str)
                + " | δC "
                + carbon_df["delta_ppm"].astype(str)
                + " | "
                + carbon_df["assignment"].fillna("-").astype(str)
            )

            selected_label = st.selectbox(
                "Select 13C NMR Record",
                carbon_df["label"].tolist(),
                key="edit_13c_select"
            )

            carbon_id = int(selected_label.split(" | ")[0])
            row_df = load_carbon_row(carbon_id)

            if row_df.empty:
                st.error("13C NMR record not found.")
            else:
                row = row_df.iloc[0]
                compounds_df = load_all_compounds()
                options = compounds_df[["id", "trivial_name"]].copy()
                options["label"] = options["id"].astype(str) + " - " + options["trivial_name"].fillna("")
                label_list = options["label"].tolist()

                default_index = 0
                if row["compound_id"] in options["id"].tolist():
                    default_index = options.index[options["id"] == row["compound_id"]][0]

                with st.form("edit_13c_form", clear_on_submit=False):
                    selected_compound_label = st.selectbox(
                        "Select Compound",
                        label_list,
                        index=default_index,
                        key="edit13c_compound"
                    )

                    c1, c2 = st.columns(2)

                    with c1:
                        delta_ppm_text = st.text_input("δC (ppm)", value=maybe_blank(row["delta_ppm"]))
                        carbon_type = st.text_input("Carbon Type", value=maybe_blank(row["carbon_type"]))
                        assignment = st.text_input("Assignment", value=maybe_blank(row["assignment"]))

                    with c2:
                        solvent = st.text_input("Solvent", value=maybe_blank(row["solvent"]))
                        instrument_mhz_text = st.text_input("Instrument (MHz)", value=maybe_blank(row["instrument_mhz"]))
                        note = st.text_area("Note", value=maybe_blank(row["note"]))

                    submitted_edit_13c = st.form_submit_button("Save Changes")

                if submitted_edit_13c:
                    if not delta_ppm_text.strip():
                        st.error("δC (ppm) is required.")
                    elif not assignment.strip():
                        st.error("Assignment is required.")
                    else:
                        try:
                            delta_ppm_value = float(delta_ppm_text.strip())
                        except ValueError:
                            st.error("δC (ppm) must be a valid number.")
                            st.stop()

                        instrument_mhz_value = None
                        if instrument_mhz_text.strip():
                            try:
                                instrument_mhz_value = float(instrument_mhz_text.strip())
                            except ValueError:
                                st.error("Instrument (MHz) must be a valid number.")
                                st.stop()

                        selected_compound_id = int(selected_compound_label.split(" - ")[0])

                        update_carbon_record(
                            carbon_id=carbon_id,
                            compound_id=selected_compound_id,
                            delta_ppm=delta_ppm_value,
                            carbon_type=carbon_type.strip(),
                            assignment=assignment.strip(),
                            solvent=solvent.strip(),
                            instrument_mhz=instrument_mhz_value,
                            note=note.strip()
                        )

                        st.success(f"13C NMR record ID {carbon_id} updated successfully.")

                        left_btn, right_btn = st.columns([1, 1])
                        with left_btn:
                            if st.button("Open Record", key=f"open_detail_after_edit_13c_{carbon_id}"):
                                open_compound_detail(selected_compound_id)
                                st.rerun()
                        with right_btn:
                            if st.button("Refresh Form", key=f"reload_edit_13c_{carbon_id}"):
                                st.rerun()

    else:
        section_header("Delete 13C Peak", "Remove a single 13C NMR record.")
        carbon_df = load_all_carbon_data()

        if carbon_df.empty:
            st.info("No 13C NMR records available.")
        else:
            carbon_df["label"] = (
                carbon_df["id"].astype(str)
                + " | "
                + carbon_df["trivial_name"].fillna("-").astype(str)
                + " | δC "
                + carbon_df["delta_ppm"].astype(str)
                + " | "
                + carbon_df["assignment"].fillna("-").astype(str)
            )

            selected_label = st.selectbox("Select 13C NMR Record to Delete", carbon_df["label"].tolist(), key="delete_13c_select")
            carbon_id = int(selected_label.split(" | ")[0])
            row_df = load_carbon_row(carbon_id)

            if not row_df.empty:
                row = row_df.iloc[0]
                st.warning("This action cannot be undone.")
                st.markdown('<div class="panel-card">', unsafe_allow_html=True)
                st.write(f"**Record ID:** {carbon_id}")
                st.write(f"**Compound ID:** {row['compound_id']}")
                st.write(f"**δC (ppm):** {clean_text(row['delta_ppm'])}")
                st.write(f"**Assignment:** {clean_text(row['assignment'])}")
                st.markdown('</div>', unsafe_allow_html=True)

                with st.form("delete_13c_form"):
                    confirm = st.checkbox("I understand that this will permanently delete this 13C NMR record.")
                    submitted_delete = st.form_submit_button("Delete 13C Record")

                if submitted_delete:
                    if not confirm:
                        st.error("Please confirm deletion first.")
                    else:
                        compound_id = int(row["compound_id"])
                        delete_carbon_record_by_id(carbon_id)
                        st.success(f"13C NMR record ID {carbon_id} was deleted.")
                        if st.button("Open Record", key=f"open_detail_after_delete_13c_{carbon_id}"):
                            open_compound_detail(compound_id)
                            st.rerun()


# =========================
# Bioactivity pages
# =========================
def show_bioactivity_pages():
    bioactivity_options = ["Browse Assays", "Add Assay", "Edit Assay", "Delete Assay"] if can_edit_database() else ["Browse Assays"]
    bioactivity_page = st.radio(
        "Bioactivity Tools",
        bioactivity_options,
        horizontal=True,
    )

    bioactivity_df = load_all_bioactivity_data()
    compounds_df = load_all_compounds()
    if not can_edit_database():
        render_read_only_notice("add, edit, or delete bioactivity records")

    if bioactivity_page == "Browse Assays":
        section_header(
            "Bioactivity Browser",
            "Review assay records by activity class, target, potency metric, and linked compound.",
        )
        if bioactivity_df.empty:
            st.info("No bioactivity records available yet.")
            return

        with st.expander("Bioactivity Filters", expanded=True):
            activity_filter = st.selectbox(
                "Activity",
                ["All"] + sorted(set(bioactivity_df["activity_label"].fillna("").astype(str).str.strip()) - {""}),
                key="bioactivity_activity_filter",
            )
            target_category_filter = st.selectbox(
                "Target Category",
                ["All"] + sorted(set(bioactivity_df["target_category"].fillna("").astype(str).str.strip()) - {""}),
                key="bioactivity_target_filter",
            )
            potency_filter = st.selectbox(
                "Potency Metric",
                ["All"] + sorted(set(bioactivity_df["potency_type"].fillna("").astype(str).str.strip()) - {""}),
                key="bioactivity_metric_filter",
            )
            keyword_filter = st.text_input(
                "Keyword",
                key="bioactivity_keyword_filter",
                placeholder="target, organism, compound, assay source...",
            )

        filtered_df = bioactivity_df.copy()
        if activity_filter != "All":
            filtered_df = filtered_df[filtered_df["activity_label"].fillna("").astype(str).str.strip() == activity_filter]
        if target_category_filter != "All":
            filtered_df = filtered_df[filtered_df["target_category"].fillna("").astype(str).str.strip() == target_category_filter]
        if potency_filter != "All":
            filtered_df = filtered_df[filtered_df["potency_type"].fillna("").astype(str).str.strip() == potency_filter]
        if keyword_filter.strip():
            keyword = keyword_filter.strip().lower()
            searchable = filtered_df[
                [
                    "trivial_name",
                    "activity_label",
                    "target_name",
                    "target_category",
                    "assay_type",
                    "assay_source",
                    "note",
                ]
            ].fillna("").astype(str).agg(" ".join, axis=1).str.lower()
            filtered_df = filtered_df[searchable.str.contains(re.escape(keyword), regex=True)]

        top1, top2, top3 = st.columns(3)
        render_metric_card("Assay Records", len(filtered_df), top1)
        render_metric_card("Linked Compounds", filtered_df["compound_id"].nunique(), top2)
        active_hits = filtered_df[filtered_df["outcome"].fillna("").astype(str).str.lower().str.contains("active|potent|strong")]
        render_metric_card("Marked Active/Potent", len(active_hits), top3)

        export_df = export_bioactivity_results(filtered_df)
        download_dataframe_button(
            label="Download Bioactivity Browser as Excel",
            df=export_df,
            file_name="bioactivity_browser.xlsx",
            key="download_bioactivity_browser",
            sheet_name="Bioactivity Browser",
        )
        st.dataframe(export_df, width="stretch", hide_index=True)

        section_header("Highlighted Assays")
        for _, row in filtered_df.head(8).iterrows():
            st.markdown('<div class="panel-card">', unsafe_allow_html=True)
            left, right = st.columns([4.5, 1])
            with left:
                st.markdown(f"**{clean_text(row['trivial_name'])}**")
                st.caption(
                    f"{clean_text(row['activity_label'])} | {clean_text(row['target_name'])} | "
                    f"{clean_text(row['potency_type'])} {clean_text(row['potency_relation'])} "
                    f"{clean_text(row['potency_value'])} {clean_text(row['potency_unit'])}"
                )
                st.write(clean_text(row["note"]))
            with right:
                if st.button("Open Record", key=f"bioactivity_open_{row['id']}"):
                    open_compound_detail(int(row["compound_id"]))
                    st.rerun()
            st.markdown('</div>', unsafe_allow_html=True)

    elif bioactivity_page == "Add Assay":
        section_header(
            "Add Bioactivity Record",
            "Capture reported assay outcomes from marine natural product papers in a flexible but structured format.",
        )
        render_helper_card(
            "Suggested data model",
            "Use Activity for the broad phenotype, Target for the exact cell line / microbe / enzyme, Metric for IC50 or MIC, and Outcome/Note for context such as selectivity or partial inhibition.",
        )

        if compounds_df.empty:
            st.info("No compounds available. Please add a compound first.")
            return

        options = compounds_df[["id", "trivial_name"]].copy()
        options["label"] = options["id"].astype(str) + " - " + options["trivial_name"].fillna("")
        label_list = options["label"].tolist()
        default_index = 0
        selected_id = st.session_state.get("selected_compound_id")
        if selected_id is not None and selected_id in options["id"].tolist():
            default_index = options.index[options["id"] == selected_id][0]


        selected_compound_label = st.selectbox("Select Compound", label_list, index=default_index, key="add_bioactivity_compound")
        c1, c2 = st.columns(2)
        with c1:
            activity_label = select_or_custom(
                "Activity",
                build_existing_options(bioactivity_df, "activity_label", DEFAULT_BIOACTIVITY_CATEGORIES),
                "add_bioactivity_activity",
                help_text="Choose an existing broad activity label or use Custom... for a new one.",
            )
            target_name = st.text_input("Target Name", placeholder="e.g. HCT-116, MRSA, PTP1B")
            target_category = select_or_custom(
                "Target Category",
                build_existing_options(bioactivity_df, "target_category", DEFAULT_TARGET_CATEGORIES),
                "add_bioactivity_target_category",
            )
            assay_type = st.text_input("Assay Type", placeholder="e.g. cytotoxicity assay, antimicrobial assay")
            potency_type = select_or_custom(
                "Potency Metric",
                build_existing_options(bioactivity_df, "potency_type", DEFAULT_POTENCY_TYPES),
                "add_bioactivity_metric",
            )
            potency_relation = st.selectbox("Relation", ["=", "<", "<=", ">", ">=", "~"], index=0)
            potency_value_text = st.text_input("Potency Value", placeholder="e.g. 1.2")
        with c2:
            potency_unit = select_or_custom(
                "Potency Unit",
                build_existing_options(bioactivity_df, "potency_unit", DEFAULT_POTENCY_UNITS),
                "add_bioactivity_unit",
            )
            outcome = st.text_input("Outcome", placeholder="e.g. active, inactive, moderate, selective")
            assay_medium = st.text_input("Assay Medium / Test System", placeholder="e.g. in vitro, broth microdilution")
            selectivity = st.text_input("Selectivity", placeholder="e.g. selective vs normal Vero cells")
            assay_source = st.text_input("Assay Source", placeholder="e.g. J. Am. Chem. Soc. 2006")
            note = st.text_area("Note", placeholder="Any caveat, mechanism note, replicate information, or assay context")
        submitted = st.button("Save Bioactivity Record", key="add_bioactivity_submit")

        if submitted:
            if not activity_label.strip():
                st.error("Activity is required.")
            else:
                potency_value = safe_float_or_none(potency_value_text)
                if potency_value_text.strip() and potency_value is None:
                    st.error("Potency Value must be a valid number.")
                else:
                    selected_compound_id = int(selected_compound_label.split(" - ")[0])
                    new_id = insert_bioactivity_record(
                        compound_id=selected_compound_id,
                        activity_label=activity_label.strip(),
                        target_name=target_name.strip(),
                        target_category=target_category.strip(),
                        assay_type=assay_type.strip(),
                        potency_type=potency_type.strip(),
                        potency_relation=potency_relation.strip(),
                        potency_value=potency_value,
                        potency_unit=potency_unit.strip(),
                        outcome=outcome.strip(),
                        assay_medium=assay_medium.strip(),
                        selectivity=selectivity.strip(),
                        assay_source=assay_source.strip(),
                        note=note.strip(),
                    )
                    st.success(f"Bioactivity record saved successfully. New Assay ID: {new_id}")

    elif bioactivity_page == "Edit Assay":
        section_header("Edit Bioactivity Record", "Update an existing assay entry without touching the parent compound metadata.")
        if bioactivity_df.empty:
            st.info("No bioactivity records available.")
            return

        bioactivity_df["label"] = (
            bioactivity_df["id"].astype(str)
            + " | "
            + bioactivity_df["trivial_name"].fillna("-").astype(str)
            + " | "
            + bioactivity_df["activity_label"].fillna("-").astype(str)
            + " | "
            + bioactivity_df["target_name"].fillna("-").astype(str)
        )
        selected_label = st.selectbox("Select Bioactivity Record", bioactivity_df["label"].tolist(), key="edit_bioactivity_select")
        bioactivity_id = int(selected_label.split(" | ")[0])
        row_df = load_bioactivity_row(bioactivity_id)

        if row_df.empty:
            st.error("Bioactivity record not found.")
            return

        row = row_df.iloc[0]
        options = compounds_df[["id", "trivial_name"]].copy()
        options["label"] = options["id"].astype(str) + " - " + options["trivial_name"].fillna("")
        label_list = options["label"].tolist()
        default_index = 0
        if row["compound_id"] in options["id"].tolist():
            default_index = options.index[options["id"] == row["compound_id"]][0]


        selected_compound_label = st.selectbox("Select Compound", label_list, index=default_index, key="edit_bioactivity_compound")
        c1, c2 = st.columns(2)
        with c1:
            activity_label = select_or_custom(
                "Activity",
                build_existing_options(bioactivity_df, "activity_label", DEFAULT_BIOACTIVITY_CATEGORIES),
                f"edit_bioactivity_activity_{bioactivity_id}",
                value=maybe_blank(row["activity_label"]),
            )
            target_name = st.text_input("Target Name", value=maybe_blank(row["target_name"]))
            target_category = select_or_custom(
                "Target Category",
                build_existing_options(bioactivity_df, "target_category", DEFAULT_TARGET_CATEGORIES),
                f"edit_bioactivity_target_category_{bioactivity_id}",
                value=maybe_blank(row["target_category"]),
            )
            assay_type = st.text_input("Assay Type", value=maybe_blank(row["assay_type"]))
            potency_type = select_or_custom(
                "Potency Metric",
                build_existing_options(bioactivity_df, "potency_type", DEFAULT_POTENCY_TYPES),
                f"edit_bioactivity_metric_{bioactivity_id}",
                value=maybe_blank(row["potency_type"]),
            )
            relation_options = ["=", "<", "<=", ">", ">=", "~"]
            relation_value = maybe_blank(row["potency_relation"]) or "="
            potency_relation = st.selectbox("Relation", relation_options, index=relation_options.index(relation_value) if relation_value in relation_options else 0)
            potency_value_text = st.text_input("Potency Value", value=maybe_blank(row["potency_value"]))
        with c2:
            potency_unit = select_or_custom(
                "Potency Unit",
                build_existing_options(bioactivity_df, "potency_unit", DEFAULT_POTENCY_UNITS),
                f"edit_bioactivity_unit_{bioactivity_id}",
                value=maybe_blank(row["potency_unit"]),
            )
            outcome = st.text_input("Outcome", value=maybe_blank(row["outcome"]))
            assay_medium = st.text_input("Assay Medium / Test System", value=maybe_blank(row["assay_medium"]))
            selectivity = st.text_input("Selectivity", value=maybe_blank(row["selectivity"]))
            assay_source = st.text_input("Assay Source", value=maybe_blank(row["assay_source"]))
            note = st.text_area("Note", value=maybe_blank(row["note"]))
        submitted = st.button("Save Changes", key="edit_bioactivity_submit")

        if submitted:
            if not activity_label.strip():
                st.error("Activity is required.")
            else:
                potency_value = safe_float_or_none(potency_value_text)
                if potency_value_text.strip() and potency_value is None:
                    st.error("Potency Value must be a valid number.")
                else:
                    selected_compound_id = int(selected_compound_label.split(" - ")[0])
                    update_bioactivity_record(
                        bioactivity_id=bioactivity_id,
                        compound_id=selected_compound_id,
                        activity_label=activity_label.strip(),
                        target_name=target_name.strip(),
                        target_category=target_category.strip(),
                        assay_type=assay_type.strip(),
                        potency_type=potency_type.strip(),
                        potency_relation=potency_relation.strip(),
                        potency_value=potency_value,
                        potency_unit=potency_unit.strip(),
                        outcome=outcome.strip(),
                        assay_medium=assay_medium.strip(),
                        selectivity=selectivity.strip(),
                        assay_source=assay_source.strip(),
                        note=note.strip(),
                    )
                    st.success(f"Bioactivity record ID {bioactivity_id} updated successfully.")

    else:
        section_header("Delete Bioactivity Record", "Remove one assay record without deleting the parent compound.")
        if bioactivity_df.empty:
            st.info("No bioactivity records available.")
            return
        bioactivity_df["label"] = (
            bioactivity_df["id"].astype(str)
            + " | "
            + bioactivity_df["trivial_name"].fillna("-").astype(str)
            + " | "
            + bioactivity_df["activity_label"].fillna("-").astype(str)
            + " | "
            + bioactivity_df["target_name"].fillna("-").astype(str)
        )
        selected_label = st.selectbox("Select Bioactivity Record to Delete", bioactivity_df["label"].tolist(), key="delete_bioactivity_select")
        bioactivity_id = int(selected_label.split(" | ")[0])
        row_df = load_bioactivity_row(bioactivity_id)
        if not row_df.empty:
            row = row_df.iloc[0]
            st.warning("This action cannot be undone.")
            st.markdown('<div class="panel-card">', unsafe_allow_html=True)
            st.write(f"**Assay ID:** {bioactivity_id}")
            st.write(f"**Activity:** {clean_text(row['activity_label'])}")
            st.write(f"**Target:** {clean_text(row['target_name'])}")
            st.write(f"**Metric:** {clean_text(row['potency_type'])} {clean_text(row['potency_relation'])} {clean_text(row['potency_value'])} {clean_text(row['potency_unit'])}")
            st.markdown('</div>', unsafe_allow_html=True)

            with st.form("delete_bioactivity_form"):
                confirm = st.checkbox("I understand that this will permanently delete this bioactivity record.")
                submitted_delete = st.form_submit_button("Delete Bioactivity Record")

            if submitted_delete:
                if not confirm:
                    st.error("Please confirm deletion first.")
                else:
                    delete_bioactivity_record_by_id(bioactivity_id)
                    st.success(f"Bioactivity record ID {bioactivity_id} was deleted.")


# =========================
# Spectra pages
# =========================
def show_spectra_library_overview():
    spectra_df = load_all_spectra_files()
    section_header(
        "Spectra Library Overview",
        "Review coverage, storage quality, and quick-access previews before editing individual file records.",
    )
    if spectra_df.empty:
        st.info("No spectra file records available.")
        return

    spectra_df = spectra_df.copy()
    spectra_df["storage_type"] = spectra_df["file_path"].fillna("").astype(str).apply(classify_storage_type)
    spectra_df["is_remote"] = spectra_df["file_path"].fillna("").astype(str).apply(is_external_url)
    spectra_df["exists_locally"] = spectra_df["file_path"].fillna("").astype(str).apply(
        lambda value: True if is_external_url(value) else bool(get_full_file_path(value) and get_full_file_path(value).exists())
    )

    m1, m2, m3, m4 = st.columns(4)
    render_metric_card("Library Records", len(spectra_df), m1)
    render_metric_card("Remote Links", int(spectra_df["is_remote"].sum()), m2)
    render_metric_card("Local Existing Files", int((~spectra_df["is_remote"] & spectra_df["exists_locally"]).sum()), m3)
    render_metric_card("Missing Local Files", int((~spectra_df["is_remote"] & ~spectra_df["exists_locally"]).sum()), m4)

    spectrum_counts = (
        spectra_df["spectrum_type"]
        .fillna("Uncategorized")
        .replace("", "Uncategorized")
        .value_counts()
        .reset_index()
    )
    spectrum_counts.columns = ["Spectrum Type", "Count"]
    render_dashboard_bar_chart(spectrum_counts, x_col="Spectrum Type", y_col="Count", color_hex="#FF7F6D")

    st.markdown("**Recent Library Entries**")
    preview_df = spectra_df[
        ["id", "trivial_name", "spectrum_type", "storage_type", "file_path", "note"]
    ].rename(
        columns={
            "id": "ID",
            "trivial_name": "Compound",
            "spectrum_type": "Spectrum Type",
            "storage_type": "Storage",
            "file_path": "Path",
            "note": "Note",
        }
    )
    st.dataframe(preview_df.head(20), width="stretch", hide_index=True)


def show_spectra_pages():
    if not can_edit_database():
        render_read_only_notice("add, edit, or delete spectra file records")
        show_spectra_library_overview()
        return

    spectra_page = st.radio(
        "Spectra Tools",
        ["Library Overview", "Add Files", "Edit Files", "Delete Files"],
        horizontal=True
    )

    if spectra_page == "Library Overview":
        show_spectra_library_overview()

    elif spectra_page == "Add Files":
        section_header("Add Spectra Files", "Upload files directly or register an existing file path for a selected compound.")
        render_helper_card(
            "Tip",
            "Use Google Drive for large raw-data files and keep local uploads for lighter preview images only.",
        )
        compounds_df = load_all_compounds()
        spectra_df = load_all_spectra_files()

        if compounds_df.empty:
            st.info("No compounds available. Please add a compound first.")
        else:
            options = compounds_df[["id", "trivial_name"]].copy()
            options["label"] = options["id"].astype(str) + " - " + options["trivial_name"].fillna("")
            label_list = options["label"].tolist()

            default_index = 0
            selected_id = st.session_state.get("selected_compound_id")
            if selected_id is not None and selected_id in options["id"].tolist():
                default_index = options.index[options["id"] == selected_id][0]

            selected_compound_label = st.selectbox(
                "Select Compound",
                label_list,
                index=default_index,
                key="add_spectra_compound"
            )

            selected_compound_id = int(selected_compound_label.split(" - ")[0])


            spectrum_type = select_or_custom(
                "Spectrum Type",
                build_existing_options(spectra_df, "spectrum_type", DEFAULT_SPECTRUM_TYPES),
                "add_spectrum_type",
                value="Supporting Data",
            )
            file_path = st.text_input("File Path or External URL (optional if uploading)", placeholder="e.g. data/spectra/RU207-C1_1H.png or https://drive.google.com/...")
            uploaded_files = st.file_uploader(
                "Upload Spectra Files",
                accept_multiple_files=True,
                key="add_spectra_uploads",
            )
            note = st.text_area("Note", key="add_spectra_note")
            st.caption("Recommended: raw data types such as 1H Raw Data, 13C Raw Data, JCAMP-DX, and MNova should use Google Drive links.")

            submitted_spectra = st.button("Save Spectra File", key="add_spectra_submit")

            if submitted_spectra:
                if not spectrum_type.strip():
                    st.error("Spectrum Type is required.")
                elif not file_path.strip() and not uploaded_files:
                    st.error("Provide at least one uploaded file or a file path.")
                else:
                    created_records = []

                    if file_path.strip():
                        validation_errors, validation_warnings = validate_spectrum_entry(file_path.strip(), spectrum_type.strip())
                        for warning_message in validation_warnings:
                            st.warning(warning_message)
                        if validation_errors:
                            for error_message in validation_errors:
                                st.error(error_message)
                            st.stop()

                        created_records.append(
                            insert_spectrum_file_record(
                                compound_id=selected_compound_id,
                                spectrum_type=spectrum_type.strip(),
                                file_path=file_path.strip(),
                                note=note.strip()
                            )
                        )

                    for uploaded_file in uploaded_files or []:
                        saved_path = save_uploaded_asset(
                            uploaded_file,
                            SPECTRA_DIR,
                            f"compound_{selected_compound_id}_{spectrum_type}_{uploaded_file.name}",
                        )
                        created_records.append(
                            insert_spectrum_file_record(
                                compound_id=selected_compound_id,
                                spectrum_type=spectrum_type.strip(),
                                file_path=saved_path,
                                note=note.strip()
                            )
                        )

                    st.success(f"Saved {len(created_records)} spectra file record(s).")

                    if st.button("Open Record", key=f"open_detail_after_spectra_{selected_compound_id}"):
                        open_compound_detail(selected_compound_id)
                        st.rerun()

    elif spectra_page == "Edit Files":
        section_header("Edit Spectra Files", "Update a spectra file record and verify its path.")
        render_helper_card(
            "Tip",
            "You can switch a local path to a Google Drive link at any time, especially for large raw files before public deployment.",
        )
        spectra_df = load_all_spectra_files()

        if spectra_df.empty:
            st.info("No spectra file records available.")
        else:
            spectra_df["label"] = (
                spectra_df["id"].astype(str)
                + " | "
                + spectra_df["trivial_name"].fillna("-").astype(str)
                + " | "
                + spectra_df["spectrum_type"].fillna("-").astype(str)
                + " | "
                + spectra_df["file_path"].fillna("-").astype(str)
            )

            selected_label = st.selectbox(
                "Select Spectra File Record",
                spectra_df["label"].tolist(),
                key="edit_spectra_select"
            )

            file_id = int(selected_label.split(" | ")[0])
            row_df = load_spectrum_file_row(file_id)

            if row_df.empty:
                st.error("Spectra file record not found.")
            else:
                row = row_df.iloc[0]
                compounds_df = load_all_compounds()
                options = compounds_df[["id", "trivial_name"]].copy()
                options["label"] = options["id"].astype(str) + " - " + options["trivial_name"].fillna("")
                label_list = options["label"].tolist()

                default_index = 0
                if row["compound_id"] in options["id"].tolist():
                    default_index = options.index[options["id"] == row["compound_id"]][0]


                selected_compound_label = st.selectbox(
                    "Select Compound",
                    label_list,
                    index=default_index,
                    key="edit_spectra_compound"
                )

                spectrum_type = select_or_custom(
                    "Spectrum Type",
                    build_existing_options(spectra_df, "spectrum_type", DEFAULT_SPECTRUM_TYPES),
                    f"edit_spectrum_type_{file_id}",
                    value=maybe_blank(row["spectrum_type"]),
                )
                file_path = st.text_input("File Path or External URL", value=maybe_blank(row["file_path"]))
                replacement_upload = st.file_uploader(
                    "Replace File by Upload",
                    key=f"edit_spectrum_upload_{file_id}",
                )
                note = st.text_area("Note", value=maybe_blank(row["note"]))

                submitted_edit_spectra = st.button("Save Changes", key="edit_spectra_submit")

                if submitted_edit_spectra:
                    if not spectrum_type.strip():
                        st.error("Spectrum Type is required.")
                    elif not file_path.strip() and replacement_upload is None:
                        st.error("File Path is required.")
                    else:
                        selected_compound_id = int(selected_compound_label.split(" - ")[0])

                        if replacement_upload is not None:
                            file_path = save_uploaded_asset(
                                replacement_upload,
                                SPECTRA_DIR,
                                f"compound_{selected_compound_id}_{spectrum_type}_{replacement_upload.name}",
                            )

                        validation_errors, validation_warnings = validate_spectrum_entry(file_path.strip(), spectrum_type.strip())
                        for warning_message in validation_warnings:
                            st.warning(warning_message)
                        if validation_errors:
                            for error_message in validation_errors:
                                st.error(error_message)
                            st.stop()

                        update_spectrum_file_record(
                            file_id=file_id,
                            compound_id=selected_compound_id,
                            spectrum_type=spectrum_type.strip(),
                            file_path=file_path.strip(),
                            note=note.strip()
                        )

                        st.success(f"Spectra file record ID {file_id} updated successfully.")

                        left_btn, right_btn = st.columns([1, 1])
                        with left_btn:
                            if st.button("Open Record", key=f"open_detail_after_edit_spectra_{file_id}"):
                                open_compound_detail(selected_compound_id)
                                st.rerun()
                        with right_btn:
                            if st.button("Refresh Form", key=f"reload_edit_spectra_{file_id}"):
                                st.rerun()

    else:
        section_header("Delete Spectra Files", "Remove a spectra file record from the database.")
        spectra_df = load_all_spectra_files()

        if spectra_df.empty:
            st.info("No spectra file records available.")
        else:
            spectra_df["label"] = (
                spectra_df["id"].astype(str)
                + " | "
                + spectra_df["trivial_name"].fillna("-").astype(str)
                + " | "
                + spectra_df["spectrum_type"].fillna("-").astype(str)
                + " | "
                + spectra_df["file_path"].fillna("-").astype(str)
            )

            selected_label = st.selectbox("Select Spectra File Record to Delete", spectra_df["label"].tolist(), key="delete_spectra_select")
            file_id = int(selected_label.split(" | ")[0])
            row_df = load_spectrum_file_row(file_id)

            if not row_df.empty:
                row = row_df.iloc[0]
                st.warning("This action cannot be undone.")
                st.markdown('<div class="panel-card">', unsafe_allow_html=True)
                st.write(f"**Record ID:** {file_id}")
                st.write(f"**Compound ID:** {row['compound_id']}")
                st.write(f"**Spectrum Type:** {clean_text(row['spectrum_type'])}")
                st.write(f"**File Path:** {clean_text(row['file_path'])}")
                st.markdown('</div>', unsafe_allow_html=True)

                with st.form("delete_spectra_form"):
                    confirm = st.checkbox("I understand that this will permanently delete this spectra file record.")
                    submitted_delete = st.form_submit_button("Delete Spectra File Record")

                if submitted_delete:
                    if not confirm:
                        st.error("Please confirm deletion first.")
                    else:
                        compound_id = int(row["compound_id"])
                        delete_spectrum_file_record_by_id(file_id)
                        st.success(f"Spectra file record ID {file_id} was deleted.")
                        if st.button("Open Record", key=f"open_detail_after_delete_spectra_{file_id}"):
                            open_compound_detail(compound_id)
                            st.rerun()


# =========================
# Supabase-first cloud adapters
# =========================
def get_supabase_url() -> str:
    return get_secret_setting("SUPABASE_URL")


def get_supabase_anon_key() -> str:
    return get_secret_setting("SUPABASE_ANON_KEY")


def get_supabase_service_role_key() -> str:
    return get_secret_setting("SUPABASE_SERVICE_ROLE_KEY")


def use_supabase_backend() -> bool:
    return bool(get_supabase_url() and (get_supabase_service_role_key() or get_supabase_anon_key()))


def _supabase_ssl_context():
    if get_secret_setting("NPDB_SKIP_SSL_VERIFY") == "1":
        return ssl._create_unverified_context()
    return None


def _json_ready(value):
    try:
        if pd.isna(value):
            return None
    except Exception:
        pass
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, datetime):
        return value.isoformat()
    return value


def _supabase_headers(write: bool = False, json_body: bool = True, extra: dict | None = None):
    api_key = get_supabase_service_role_key() or get_supabase_anon_key()
    headers = {
        "apikey": api_key,
        "Authorization": f"Bearer {api_key}",
    }
    if json_body:
        headers["Content-Type"] = "application/json"
    if extra:
        headers.update(extra)
    return headers


def _supabase_request(method: str, path: str, query: dict | None = None, body=None, write: bool = False, json_body: bool = True, extra_headers: dict | None = None, return_json: bool = True):
    base = get_supabase_url().rstrip("/")
    url = f"{base}{path}"
    if query:
        query_text = urlencode(query, doseq=True, safe=",().:*+-")
        url = f"{url}?{query_text}"
    payload = None
    if body is not None:
        payload = json.dumps(body).encode("utf-8") if json_body else body
    request = urllib.request.Request(
        url,
        data=payload,
        method=method.upper(),
        headers=_supabase_headers(write=write, json_body=json_body, extra=extra_headers),
    )
    try:
        with urllib.request.urlopen(request, timeout=60, context=_supabase_ssl_context()) as response:
            raw = response.read()
            if not return_json:
                return raw
            if not raw:
                return None
            return json.loads(raw.decode("utf-8"))
    except urllib.error.HTTPError as exc:
        details = exc.read().decode("utf-8", errors="ignore")
        raise RuntimeError(f"Supabase request failed ({exc.code} {exc.reason}): {details}") from exc


def _supabase_filter_query(filters: dict | None) -> dict:
    query = {}
    for key, value in (filters or {}).items():
        if isinstance(value, tuple) and len(value) == 2:
            operator, operand = value
            if operator == "in":
                joined = ",".join(str(item) for item in operand)
                query[key] = f"in.({joined})"
            else:
                query[key] = f"{operator}.{operand}"
        else:
            query[key] = f"eq.{value}"
    return query


def supabase_select_df(table: str, columns: str = "*", filters: dict | None = None, order: str | None = None) -> pd.DataFrame:
    if not use_supabase_backend():
        return pd.DataFrame()
    query = {"select": columns}
    query.update(_supabase_filter_query(filters))
    if order:
        query["order"] = order
    rows = _supabase_request("GET", f"/rest/v1/{table}", query=query, write=False) or []
    return pd.DataFrame(rows)


def supabase_insert_row(table: str, row: dict):
    payload = {k: _json_ready(v) for k, v in row.items() if k and v is not None}
    response = _supabase_request(
        "POST",
        f"/rest/v1/{table}",
        query={"select": "id"},
        body=payload,
        write=True,
        extra_headers={"Prefer": "return=representation"},
    ) or []
    if response:
        return response[0]
    return {}


def supabase_update_row(table: str, row_id: int, row: dict):
    payload = {k: _json_ready(v) for k, v in row.items() if k and k != "id"}
    response = _supabase_request(
        "PATCH",
        f"/rest/v1/{table}",
        query={"id": f"eq.{row_id}", "select": "id"},
        body=payload,
        write=True,
        extra_headers={"Prefer": "return=representation"},
    ) or []
    if response:
        return response[0]
    return {}


def supabase_delete_row(table: str, row_id: int):
    _supabase_request(
        "DELETE",
        f"/rest/v1/{table}",
        query={"id": f"eq.{row_id}"},
        body=None,
        write=True,
        extra_headers={"Prefer": "return=minimal"},
    )


def supabase_upload_bytes(bucket: str, object_path: str, data: bytes, content_type: str = "application/octet-stream") -> str:
    _supabase_request(
        "POST",
        f"/storage/v1/object/{bucket}/{quote(object_path, safe='/')}"
        ,body=data,
        write=True,
        json_body=False,
        extra_headers={"Content-Type": content_type, "x-upsert": "true"},
        return_json=False,
    )
    return f"{get_supabase_url().rstrip('/')}" + f"/storage/v1/object/public/{bucket}/{quote(object_path, safe='/')}"


def _sqlite_dataframe(query: str, params: tuple | list | None = None) -> pd.DataFrame:
    conn = get_connection()
    try:
        return pd.read_sql_query(query, conn, params=params)
    finally:
        conn.close()


def _sqlite_columns(table: str) -> list[str]:
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(f"PRAGMA table_info({table})")
        return [row[1] for row in cursor.fetchall()]
    finally:
        conn.close()


def _sqlite_upsert_row(table: str, row: dict) -> int | None:
    columns = [column for column in row.keys() if column in _sqlite_columns(table)]
    if not columns:
        return None
    conn = get_connection()
    try:
        cursor = conn.cursor()
        row_id = row.get("id")
        if row_id is not None:
            cursor.execute(f"SELECT 1 FROM {table} WHERE id = ?", (row_id,))
            exists = cursor.fetchone() is not None
        else:
            exists = False
        if exists:
            set_columns = [column for column in columns if column != "id"]
            assignments = ", ".join(f"{column} = ?" for column in set_columns)
            values = [row.get(column) for column in set_columns] + [row_id]
            cursor.execute(f"UPDATE {table} SET {assignments} WHERE id = ?", values)
        else:
            placeholders = ", ".join("?" for _ in columns)
            values = [row.get(column) for column in columns]
            cursor.execute(
                f"INSERT INTO {table} ({', '.join(columns)}) VALUES ({placeholders})",
                values,
            )
            row_id = row_id if row_id is not None else cursor.lastrowid
        conn.commit()
        return int(row_id) if row_id is not None else None
    finally:
        conn.close()


def _sqlite_delete_row(table: str, row_id: int):
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(f"DELETE FROM {table} WHERE id = ?", (row_id,))
        conn.commit()
    finally:
        conn.close()


def _local_binary_path(target_dir: Path, base_name: str, suffix: str) -> Path:
    safe_name = slugify_value(base_name, fallback="asset")
    candidate = target_dir / f"{safe_name}{suffix}"
    counter = 2
    while candidate.exists():
        candidate = target_dir / f"{safe_name}_{counter}{suffix}"
        counter += 1
    return candidate


def save_uploaded_asset(uploaded_file, target_dir: Path, base_name: str) -> str:
    suffix = Path(uploaded_file.name).suffix.lower() or ".bin"
    data = uploaded_file.getbuffer().tobytes()
    candidate = _local_binary_path(target_dir, base_name, suffix)
    candidate.parent.mkdir(parents=True, exist_ok=True)
    try:
        with open(candidate, "wb") as output_file:
            output_file.write(data)
    except Exception:
        pass
    if use_supabase_backend():
        bucket = "exports"
        if target_dir == STRUCTURES_DIR:
            bucket = "structures"
        elif target_dir == SPECTRA_DIR:
            bucket = "spectra"
        object_path = f"{datetime.utcnow().strftime('%Y/%m/%d')}/{candidate.name}"
        try:
            content_type = getattr(uploaded_file, "type", None) or mimetypes.guess_type(candidate.name)[0] or "application/octet-stream"
            return supabase_upload_bytes(bucket, object_path, data, content_type=content_type)
        except Exception:
            pass
    return relative_project_path(candidate) if candidate.exists() else str(candidate)


def _merge_compound_names(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df
    compounds_df = load_all_compounds()[["id", "trivial_name"]].copy()
    compounds_df = compounds_df.rename(columns={"id": "compound_id"})
    return df.merge(compounds_df, on="compound_id", how="left")


def get_db_signature():
    if use_supabase_backend():
        return 1.0
    if not DB_PATH.exists():
        return 0.0
    return DB_PATH.stat().st_mtime


@st.cache_data(show_spinner=False)
def load_all_compounds():
    columns = "id,trivial_name,iupac_name,molecular_formula,smiles,inchi,inchikey,compound_class,compound_subclass,source_category,source_organism,source_material,sample_code,collection_location,gps_coordinates,depth_m,uv_data,ftir_data,cd_data,optical_rotation,melting_point,crystallization_method,structure_image_path,journal_name,article_title,publication_year,volume,issue,pages,doi,ccdc_number,molecular_weight,hrms_data,data_source,note,created_at,updated_at"
    if use_supabase_backend():
        df = supabase_select_df("compounds", columns=columns, order="id.asc")
        return enrich_compounds_dataframe(df)
    return enrich_compounds_dataframe(_sqlite_dataframe(f"SELECT {columns} FROM compounds ORDER BY id ASC"))


@st.cache_data(show_spinner=False)
def load_compound_row(compound_id):
    columns = "id,trivial_name,iupac_name,molecular_formula,smiles,inchi,inchikey,compound_class,compound_subclass,source_category,source_organism,source_material,sample_code,collection_location,gps_coordinates,depth_m,uv_data,ftir_data,cd_data,optical_rotation,melting_point,crystallization_method,structure_image_path,journal_name,article_title,publication_year,volume,issue,pages,doi,ccdc_number,molecular_weight,hrms_data,data_source,note,created_at,updated_at"
    if use_supabase_backend():
        df = supabase_select_df("compounds", columns=columns, filters={"id": ("eq", compound_id)})
        return enrich_compounds_dataframe(df)
    return enrich_compounds_dataframe(_sqlite_dataframe(f"SELECT {columns} FROM compounds WHERE id = ?", (compound_id,)))


@st.cache_data(show_spinner=False)
def load_proton_data(compound_id):
    columns = "id,compound_id,delta_ppm,multiplicity,j_value,proton_count,assignment,solvent,instrument_mhz,note"
    if use_supabase_backend():
        return supabase_select_df("proton_nmr", columns=columns, filters={"compound_id": ("eq", compound_id)}, order="delta_ppm.desc")
    return _sqlite_dataframe(f"SELECT {columns} FROM proton_nmr WHERE compound_id = ? ORDER BY delta_ppm DESC", (compound_id,))


@st.cache_data(show_spinner=False)
def load_all_proton_data():
    columns = "id,compound_id,delta_ppm,multiplicity,j_value,proton_count,assignment,solvent,instrument_mhz,note"
    if use_supabase_backend():
        df = supabase_select_df("proton_nmr", columns=columns, order="id.asc")
        return _merge_compound_names(df)
    return _sqlite_dataframe("SELECT p.id, p.compound_id, c.trivial_name, p.delta_ppm, p.multiplicity, p.j_value, p.proton_count, p.assignment, p.solvent, p.instrument_mhz, p.note FROM proton_nmr p LEFT JOIN compounds c ON p.compound_id = c.id ORDER BY p.id ASC")


@st.cache_data(show_spinner=False)
def load_proton_row(proton_id):
    columns = "id,compound_id,delta_ppm,multiplicity,j_value,proton_count,assignment,solvent,instrument_mhz,note"
    if use_supabase_backend():
        return supabase_select_df("proton_nmr", columns=columns, filters={"id": ("eq", proton_id)})
    return _sqlite_dataframe(f"SELECT {columns} FROM proton_nmr WHERE id = ?", (proton_id,))


@st.cache_data(show_spinner=False)
def load_carbon_data(compound_id):
    columns = "id,compound_id,delta_ppm,carbon_type,assignment,solvent,instrument_mhz,note"
    if use_supabase_backend():
        return supabase_select_df("carbon_nmr", columns=columns, filters={"compound_id": ("eq", compound_id)}, order="delta_ppm.desc")
    return _sqlite_dataframe(f"SELECT {columns} FROM carbon_nmr WHERE compound_id = ? ORDER BY delta_ppm DESC", (compound_id,))


@st.cache_data(show_spinner=False)
def load_all_carbon_data():
    columns = "id,compound_id,delta_ppm,carbon_type,assignment,solvent,instrument_mhz,note"
    if use_supabase_backend():
        df = supabase_select_df("carbon_nmr", columns=columns, order="id.asc")
        return _merge_compound_names(df)
    return _sqlite_dataframe("SELECT c.id, c.compound_id, cp.trivial_name, c.delta_ppm, c.carbon_type, c.assignment, c.solvent, c.instrument_mhz, c.note FROM carbon_nmr c LEFT JOIN compounds cp ON c.compound_id = cp.id ORDER BY c.id ASC")


@st.cache_data(show_spinner=False)
def load_carbon_row(carbon_id):
    columns = "id,compound_id,delta_ppm,carbon_type,assignment,solvent,instrument_mhz,note"
    if use_supabase_backend():
        return supabase_select_df("carbon_nmr", columns=columns, filters={"id": ("eq", carbon_id)})
    return _sqlite_dataframe(f"SELECT {columns} FROM carbon_nmr WHERE id = ?", (carbon_id,))


@st.cache_data(show_spinner=False)
def load_spectra_files(compound_id):
    columns = "id,compound_id,spectrum_type,file_path,note"
    if use_supabase_backend():
        return supabase_select_df("spectra_files", columns=columns, filters={"compound_id": ("eq", compound_id)}, order="id.asc")
    return _sqlite_dataframe(f"SELECT {columns} FROM spectra_files WHERE compound_id = ? ORDER BY id ASC", (compound_id,))


@st.cache_data(show_spinner=False)
def load_all_spectra_files():
    columns = "id,compound_id,spectrum_type,file_path,note"
    if use_supabase_backend():
        df = supabase_select_df("spectra_files", columns=columns, order="id.asc")
        return _merge_compound_names(df)
    return _sqlite_dataframe("SELECT s.id, s.compound_id, c.trivial_name, s.spectrum_type, s.file_path, s.note FROM spectra_files s LEFT JOIN compounds c ON s.compound_id = c.id ORDER BY s.id ASC")


@st.cache_data(show_spinner=False)
def load_spectrum_file_row(file_id):
    columns = "id,compound_id,spectrum_type,file_path,note"
    if use_supabase_backend():
        return supabase_select_df("spectra_files", columns=columns, filters={"id": ("eq", file_id)})
    return _sqlite_dataframe(f"SELECT {columns} FROM spectra_files WHERE id = ?", (file_id,))


@st.cache_data(show_spinner=False)
def load_bioactivity_data(compound_id):
    columns = "id,compound_id,activity_label,target_name,target_category,assay_type,potency_type,potency_relation,potency_value,potency_unit,outcome,assay_medium,selectivity,assay_source,note"
    if use_supabase_backend():
        return supabase_select_df("bioactivity_records", columns=columns, filters={"compound_id": ("eq", compound_id)}, order="id.asc")
    return _sqlite_dataframe(f"SELECT {columns} FROM bioactivity_records WHERE compound_id = ? ORDER BY id ASC", (compound_id,))


@st.cache_data(show_spinner=False)
def load_all_bioactivity_data():
    columns = "id,compound_id,activity_label,target_name,target_category,assay_type,potency_type,potency_relation,potency_value,potency_unit,outcome,assay_medium,selectivity,assay_source,note"
    if use_supabase_backend():
        df = supabase_select_df("bioactivity_records", columns=columns, order="id.asc")
        return _merge_compound_names(df)
    return _sqlite_dataframe("SELECT b.id, b.compound_id, c.trivial_name, b.activity_label, b.target_name, b.target_category, b.assay_type, b.potency_type, b.potency_relation, b.potency_value, b.potency_unit, b.outcome, b.assay_medium, b.selectivity, b.assay_source, b.note FROM bioactivity_records b LEFT JOIN compounds c ON b.compound_id = c.id ORDER BY b.id ASC")


@st.cache_data(show_spinner=False)
def load_bioactivity_row(bioactivity_id):
    columns = "id,compound_id,activity_label,target_name,target_category,assay_type,potency_type,potency_relation,potency_value,potency_unit,outcome,assay_medium,selectivity,assay_source,note"
    if use_supabase_backend():
        return supabase_select_df("bioactivity_records", columns=columns, filters={"id": ("eq", bioactivity_id)})
    return _sqlite_dataframe(f"SELECT {columns} FROM bioactivity_records WHERE id = ?", (bioactivity_id,))


def count_related_records(filtered_ids):
    if not filtered_ids:
        return 0, 0, 0
    proton_df = load_all_proton_data()
    carbon_df = load_all_carbon_data()
    spectra_df = load_all_spectra_files()
    if "compound_id" not in proton_df.columns:
        proton_df = pd.DataFrame(columns=["compound_id"])
    if "compound_id" not in carbon_df.columns:
        carbon_df = pd.DataFrame(columns=["compound_id"])
    if "compound_id" not in spectra_df.columns:
        spectra_df = pd.DataFrame(columns=["compound_id"])
    return (
        int(proton_df[proton_df["compound_id"].isin(filtered_ids)].shape[0]) if not proton_df.empty else 0,
        int(carbon_df[carbon_df["compound_id"].isin(filtered_ids)].shape[0]) if not carbon_df.empty else 0,
        int(spectra_df[spectra_df["compound_id"].isin(filtered_ids)].shape[0]) if not spectra_df.empty else 0,
    )


def count_bioactivity_records(filtered_ids):
    if not filtered_ids:
        return 0
    bio_df = load_all_bioactivity_data()
    if bio_df.empty or "compound_id" not in bio_df.columns:
        return 0
    return int(bio_df[bio_df["compound_id"].isin(filtered_ids)].shape[0])


@st.cache_data(show_spinner=False)
def load_search_index(_db_signature: float):
    compounds_df = load_all_compounds()
    all_proton_df = load_all_proton_data()
    all_carbon_df = load_all_carbon_data()
    proton_df = all_proton_df[["compound_id", "delta_ppm"]] if not all_proton_df.empty else pd.DataFrame(columns=["compound_id", "delta_ppm"])
    carbon_df = all_carbon_df[["compound_id", "delta_ppm"]] if not all_carbon_df.empty else pd.DataFrame(columns=["compound_id", "delta_ppm"])
    proton_groups = proton_df.groupby("compound_id")["delta_ppm"].apply(list).to_dict() if not proton_df.empty else {}
    carbon_groups = carbon_df.groupby("compound_id")["delta_ppm"].apply(list).to_dict() if not carbon_df.empty else {}
    search_index = []
    for _, row in compounds_df.iterrows():
        compound_id = int(row["id"])
        search_index.append(
            {
                "compound_id": compound_id,
                "trivial_name": row.get("trivial_name"),
                "sample_code": row.get("sample_code"),
                "molecular_formula": row.get("molecular_formula"),
                "source_category": row.get("source_category"),
                "source_organism": row.get("source_organism"),
                "source_material": row.get("source_material"),
                "compound_class": row.get("compound_class"),
                "compound_subclass": row.get("compound_subclass"),
                "data_source": row.get("data_source"),
                "proton_peaks": proton_groups.get(compound_id, []),
                "carbon_peaks": carbon_groups.get(compound_id, []),
            }
        )
    return search_index


def _upsert_compound_local(row: dict):
    return _sqlite_upsert_row("compounds", row)


def insert_compound_record(trivial_name, iupac_name, molecular_formula, compound_class, compound_subclass, smiles, inchi, inchikey, source_category, source_organism, source_material, sample_code, collection_location, gps_coordinates, depth_m, uv_data, ftir_data, cd_data, optical_rotation, melting_point, crystallization_method, structure_image_path, journal_name, article_title, publication_year, volume, issue, pages, doi, ccdc_number, molecular_weight, hrms_data, data_source, note):
    row = {
        "trivial_name": trivial_name,
        "iupac_name": iupac_name,
        "molecular_formula": molecular_formula,
        "compound_class": compound_class,
        "compound_subclass": compound_subclass,
        "smiles": smiles,
        "inchi": inchi,
        "inchikey": inchikey,
        "source_category": source_category,
        "source_organism": source_organism,
        "source_material": source_material,
        "sample_code": sample_code,
        "collection_location": collection_location,
        "gps_coordinates": gps_coordinates,
        "depth_m": depth_m,
        "uv_data": uv_data,
        "ftir_data": ftir_data,
        "cd_data": cd_data,
        "optical_rotation": optical_rotation,
        "melting_point": melting_point,
        "crystallization_method": crystallization_method,
        "structure_image_path": structure_image_path,
        "journal_name": journal_name,
        "article_title": article_title,
        "publication_year": publication_year,
        "volume": volume,
        "issue": issue,
        "pages": pages,
        "doi": doi,
        "ccdc_number": ccdc_number,
        "molecular_weight": molecular_weight,
        "hrms_data": hrms_data,
        "data_source": data_source,
        "note": note,
        "updated_at": datetime.utcnow().isoformat(),
    }
    if use_supabase_backend():
        inserted = supabase_insert_row("compounds", row)
        row_id = int(inserted.get("id")) if inserted and inserted.get("id") is not None else None
        if row_id is not None:
            row["id"] = row_id
            _upsert_compound_local(row)
            invalidate_cached_views()
            return row_id
    row_id = _sqlite_upsert_row("compounds", row)
    invalidate_cached_views()
    return row_id


def update_compound_record(compound_id, trivial_name, iupac_name, molecular_formula, compound_class, compound_subclass, smiles, inchi, inchikey, source_category, source_organism, source_material, sample_code, collection_location, gps_coordinates, depth_m, uv_data, ftir_data, cd_data, optical_rotation, melting_point, crystallization_method, structure_image_path, journal_name, article_title, publication_year, volume, issue, pages, doi, ccdc_number, molecular_weight, hrms_data, data_source, note):
    row = {
        "id": compound_id,
        "trivial_name": trivial_name,
        "iupac_name": iupac_name,
        "molecular_formula": molecular_formula,
        "compound_class": compound_class,
        "compound_subclass": compound_subclass,
        "smiles": smiles,
        "inchi": inchi,
        "inchikey": inchikey,
        "source_category": source_category,
        "source_organism": source_organism,
        "source_material": source_material,
        "sample_code": sample_code,
        "collection_location": collection_location,
        "gps_coordinates": gps_coordinates,
        "depth_m": depth_m,
        "uv_data": uv_data,
        "ftir_data": ftir_data,
        "cd_data": cd_data,
        "optical_rotation": optical_rotation,
        "melting_point": melting_point,
        "crystallization_method": crystallization_method,
        "structure_image_path": structure_image_path,
        "journal_name": journal_name,
        "article_title": article_title,
        "publication_year": publication_year,
        "volume": volume,
        "issue": issue,
        "pages": pages,
        "doi": doi,
        "ccdc_number": ccdc_number,
        "molecular_weight": molecular_weight,
        "hrms_data": hrms_data,
        "data_source": data_source,
        "note": note,
        "updated_at": datetime.utcnow().isoformat(),
    }
    if use_supabase_backend():
        supabase_update_row("compounds", compound_id, row)
    _upsert_compound_local(row)
    invalidate_cached_views()


def delete_compound_record(compound_id):
    if use_supabase_backend():
        supabase_delete_row("compounds", compound_id)
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM bioactivity_records WHERE compound_id = ?", (compound_id,))
        cursor.execute("DELETE FROM proton_nmr WHERE compound_id = ?", (compound_id,))
        cursor.execute("DELETE FROM carbon_nmr WHERE compound_id = ?", (compound_id,))
        cursor.execute("DELETE FROM spectra_files WHERE compound_id = ?", (compound_id,))
        cursor.execute("DELETE FROM compounds WHERE id = ?", (compound_id,))
        conn.commit()
    finally:
        conn.close()
    invalidate_cached_views()


def _write_child_row(table: str, row: dict, row_id: int | None = None):
    if use_supabase_backend():
        if row_id is None:
            inserted = supabase_insert_row(table, row)
            if inserted and inserted.get("id") is not None:
                row["id"] = int(inserted.get("id"))
        else:
            supabase_update_row(table, row_id, row)
            row["id"] = row_id
    return _sqlite_upsert_row(table, row)


def insert_proton_record(compound_id, delta_ppm, multiplicity, j_value, proton_count, assignment, solvent, instrument_mhz, note):
    row = {"compound_id": compound_id, "delta_ppm": delta_ppm, "multiplicity": multiplicity, "j_value": j_value, "proton_count": proton_count, "assignment": assignment, "solvent": solvent, "instrument_mhz": instrument_mhz, "note": note}
    row_id = _write_child_row("proton_nmr", row)
    invalidate_cached_views()
    return row_id


def update_proton_record(proton_id, compound_id, delta_ppm, multiplicity, j_value, proton_count, assignment, solvent, instrument_mhz, note):
    row = {"compound_id": compound_id, "delta_ppm": delta_ppm, "multiplicity": multiplicity, "j_value": j_value, "proton_count": proton_count, "assignment": assignment, "solvent": solvent, "instrument_mhz": instrument_mhz, "note": note}
    _write_child_row("proton_nmr", row, row_id=proton_id)
    invalidate_cached_views()


def delete_proton_record_by_id(proton_id):
    if use_supabase_backend():
        supabase_delete_row("proton_nmr", proton_id)
    _sqlite_delete_row("proton_nmr", proton_id)
    invalidate_cached_views()


def insert_carbon_record(compound_id, delta_ppm, carbon_type, assignment, solvent, instrument_mhz, note):
    row = {"compound_id": compound_id, "delta_ppm": delta_ppm, "carbon_type": carbon_type, "assignment": assignment, "solvent": solvent, "instrument_mhz": instrument_mhz, "note": note}
    row_id = _write_child_row("carbon_nmr", row)
    invalidate_cached_views()
    return row_id


def update_carbon_record(carbon_id, compound_id, delta_ppm, carbon_type, assignment, solvent, instrument_mhz, note):
    row = {"compound_id": compound_id, "delta_ppm": delta_ppm, "carbon_type": carbon_type, "assignment": assignment, "solvent": solvent, "instrument_mhz": instrument_mhz, "note": note}
    _write_child_row("carbon_nmr", row, row_id=carbon_id)
    invalidate_cached_views()


def delete_carbon_record_by_id(carbon_id):
    if use_supabase_backend():
        supabase_delete_row("carbon_nmr", carbon_id)
    _sqlite_delete_row("carbon_nmr", carbon_id)
    invalidate_cached_views()


def insert_spectrum_file_record(compound_id, spectrum_type, file_path, note):
    row = {"compound_id": compound_id, "spectrum_type": spectrum_type, "file_path": file_path, "note": note}
    row_id = _write_child_row("spectra_files", row)
    invalidate_cached_views()
    return row_id


def update_spectrum_file_record(file_id, compound_id, spectrum_type, file_path, note):
    row = {"compound_id": compound_id, "spectrum_type": spectrum_type, "file_path": file_path, "note": note}
    _write_child_row("spectra_files", row, row_id=file_id)
    invalidate_cached_views()


def delete_spectrum_file_record_by_id(file_id):
    if use_supabase_backend():
        supabase_delete_row("spectra_files", file_id)
    _sqlite_delete_row("spectra_files", file_id)
    invalidate_cached_views()


def insert_bioactivity_record(compound_id, activity_label, target_name, target_category, assay_type, potency_type, potency_relation, potency_value, potency_unit, outcome, assay_medium, selectivity, assay_source, note):
    row = {"compound_id": compound_id, "activity_label": activity_label, "target_name": target_name, "target_category": target_category, "assay_type": assay_type, "potency_type": potency_type, "potency_relation": potency_relation, "potency_value": potency_value, "potency_unit": potency_unit, "outcome": outcome, "assay_medium": assay_medium, "selectivity": selectivity, "assay_source": assay_source, "note": note}
    row_id = _write_child_row("bioactivity_records", row)
    invalidate_cached_views()
    return row_id


def update_bioactivity_record(bioactivity_id, compound_id, activity_label, target_name, target_category, assay_type, potency_type, potency_relation, potency_value, potency_unit, outcome, assay_medium, selectivity, assay_source, note):
    row = {"compound_id": compound_id, "activity_label": activity_label, "target_name": target_name, "target_category": target_category, "assay_type": assay_type, "potency_type": potency_type, "potency_relation": potency_relation, "potency_value": potency_value, "potency_unit": potency_unit, "outcome": outcome, "assay_medium": assay_medium, "selectivity": selectivity, "assay_source": assay_source, "note": note}
    _write_child_row("bioactivity_records", row, row_id=bioactivity_id)
    invalidate_cached_views()


def delete_bioactivity_record_by_id(bioactivity_id):
    if use_supabase_backend():
        supabase_delete_row("bioactivity_records", bioactivity_id)
    _sqlite_delete_row("bioactivity_records", bioactivity_id)
    invalidate_cached_views()


def derive_structure_identifiers(structure_text: str) -> dict | None:
    if not is_structure_backend_available():
        return None
    mol = structure_text_to_mol(structure_text)
    if mol is None:
        return None
    smiles_value = maybe_blank(Chem.MolToSmiles(mol, canonical=True)) if Chem is not None else ""
    inchi_value = ""
    inchikey_value = ""
    if Chem is not None:
        try:
            inchi_value = maybe_blank(Chem.MolToInchi(mol))
        except Exception:
            inchi_value = ""
        try:
            inchikey_value = maybe_blank(Chem.InchiToInchiKey(inchi_value)) if inchi_value else ""
        except Exception:
            inchikey_value = ""
    return {"mol": mol, "smiles": smiles_value, "inchi": inchi_value, "inchikey": inchikey_value}


def _save_generated_structure_image(compound_id: int, mol) -> str:
    if Draw is None or Image is None or mol is None:
        return ""
    image = normalize_structure_image(Draw.MolToImage(mol, size=(720, 540)), size=(720, 540))
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    data = buffer.getvalue()
    candidate = _local_binary_path(STRUCTURES_DIR, f"compound_{compound_id}_structure", ".png")
    candidate.parent.mkdir(parents=True, exist_ok=True)
    try:
        with open(candidate, "wb") as output_file:
            output_file.write(data)
    except Exception:
        pass
    if use_supabase_backend():
        try:
            return supabase_upload_bytes("structures", f"generated/{candidate.name}", data, content_type="image/png")
        except Exception:
            pass
    return relative_project_path(candidate) if candidate.exists() else ""


def save_structure_query_to_compound(compound_id: int, query_text: str) -> tuple[bool, str]:
    identifiers = derive_structure_identifiers(query_text)
    if not identifiers:
        return False, "The current query could not be converted into searchable structure identifiers."
    structure_image_path = _save_generated_structure_image(compound_id, identifiers.get("mol"))
    payload = {
        "smiles": identifiers.get("smiles"),
        "inchi": identifiers.get("inchi"),
        "inchikey": identifiers.get("inchikey"),
        "updated_at": datetime.utcnow().isoformat(),
    }
    if structure_image_path:
        payload["structure_image_path"] = structure_image_path
    if use_supabase_backend():
        supabase_update_row("compounds", compound_id, payload)
    conn = get_connection()
    try:
        cursor = conn.cursor()
        assignments = ", ".join(f"{key} = ?" for key in payload.keys())
        values = list(payload.values()) + [compound_id]
        cursor.execute(f"UPDATE compounds SET {assignments} WHERE id = ?", values)
        conn.commit()
    finally:
        conn.close()
    invalidate_cached_views()
    return True, f"Structure identifiers were saved to compound ID {compound_id}."


# =========================
# App boot
# =========================
show_app_header()
all_compounds_df = load_all_compounds()
if use_supabase_backend() and all_compounds_df.empty:
    try:
        load_all_compounds.clear()
    except Exception:
        pass
    all_compounds_df = load_all_compounds()
write_batch_import_templates()


# =========================
# Sidebar navigation
# =========================
with st.sidebar:
    active_section = st.session_state.get("main_section_radio", st.session_state.get("nav_section", "Dashboard"))
    render_sidebar_workspace_summary(active_section, all_compounds_df)

    st.markdown("### Workspace")
    st.caption("Choose the area you want to open next.")

    nav_options = NAV_OPTIONS
    current_index = 0
    if st.session_state.get("nav_section") in nav_options:
        current_index = nav_options.index(st.session_state["nav_section"])

    main_radio_kwargs = {
        "label": "Open workspace",
        "options": nav_options,
        "key": "main_section_radio",
        "label_visibility": "collapsed",
    }
    if "main_section_radio" not in st.session_state:
        main_radio_kwargs["index"] = current_index
    main_section = st.radio(**main_radio_kwargs)
    st.session_state["nav_section"] = main_section
# =========================
# Main routing
# =========================
if main_section == "Dashboard":
    show_overview_page(all_compounds_df)

elif main_section == "Search & Match":
    show_search_page(all_compounds_df)

elif main_section == "Compound Workspace":
    show_compound_pages()

elif main_section == "Bioactivity":
    show_bioactivity_pages()

elif main_section == "1H Peaks":
    show_proton_pages()

elif main_section == "13C Peaks":
    show_carbon_pages()

elif main_section == "Spectra Library":
    show_spectra_pages()

elif main_section == "Guide":
    show_guide_page()

render_app_credit_footer()
