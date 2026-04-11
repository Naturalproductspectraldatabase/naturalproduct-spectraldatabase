import hmac
import json
import os
import re
import sqlite3
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse

import pandas as pd
import streamlit as st

# =========================
# Basic configuration
# =========================
def resolve_project_dir(script_dir: Path) -> Path:
    candidates = [script_dir, script_dir.parent]
    for candidate in candidates:
        if (candidate / "data").exists() and (candidate / "database").exists():
            return candidate
    return script_dir


SCRIPT_DIR = Path(__file__).resolve().parent
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
    "Tunicate",
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

NAV_OPTIONS = [
    "Dashboard",
    "Search & Match",
    "Compound Workspace",
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
    "source_material",
    "sample_code",
    "collection_location",
    "gps_coordinates",
    "depth_m",
    "uv_data",
    "ftir_data",
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
        iterable = [
            {"username": username, "password": password}
            for username, password in raw_users.items()
        ]
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
            users.append(
                {"username": username, "password": password, "role": role}
            )
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

    expected_username = get_secret_setting(
        "NPDB_ACCESS_USERNAME", "access_username"
    )
    expected_password = get_secret_setting(
        "NPDB_ACCESS_PASSWORD", "access_password"
    )
    approved_password = get_secret_setting(
        "NPDB_APPROVED_PASSWORD", "approved_password"
    )
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
        submitted = st.form_submit_button(
            "Open Database", use_container_width=True
        )

    if submitted:
        authenticated = False
        matched_role = "viewer"

        if approved_users:
            for user in approved_users:
                username_ok = hmac.compare_digest(
                    username.strip(), user["username"]
                )
                password_ok = hmac.compare_digest(
                    password, user["password"]
                )
                if username_ok and password_ok:
                    authenticated = True
                    matched_role = user.get("role", "viewer")
                    break

        elif approved_names and approved_password:
            submitted_username = str(username).strip() if username is not None else ""
            if submitted_username.lower().startswith("npdb_"):
                submitted_name = submitted_username[5:]
                submitted_slug = normalize_login_slug(submitted_name)
                allowed_slugs = {
                    normalize_login_slug(name) for name in approved_names
                }
                if (
                    submitted_slug in allowed_slugs
                    and hmac.compare_digest(password, approved_password)
                ):
                    authenticated = True
                    matched_role = "approved-viewer"

        else:
            username_ok = True if not expected_username else hmac.compare_digest(
                username.strip(), expected_username
            )
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
    --bg-soft: rgba(255,255,255,0.026);
    --bg-soft-2: rgba(255,255,255,0.038);
    --border-soft: rgba(255,255,255,0.09);
    --text-soft: #AEB8C6;
    --text-main: #F5F8FD;
    --accent-cyan: #61D8ED;
    --accent-blue: #4C8EFF;
    --accent-purple: #9C63F1;
    --accent-green: #7EF0C2;
    --accent-coral: #FF7F6D;
    --shadow-soft: 0 18px 44px rgba(0,0,0,0.22);
    --shadow-strong: 0 24px 54px rgba(0,0,0,0.28);
}

[data-testid="stAppViewContainer"] {
    background:
        radial-gradient(circle at 16% 16%, rgba(97, 216, 237, 0.08), transparent 28%),
        radial-gradient(circle at 84% 12%, rgba(156, 99, 241, 0.10), transparent 30%),
        linear-gradient(180deg, #07111d 0%, #091321 42%, #07111b 100%);
}

.block-container {
    padding-top: 1.05rem;
    padding-bottom: 2.2rem;
    max-width: 1480px;
}

header[data-testid="stHeader"] {
    background: rgba(7, 17, 29, 0.30);
}

[data-testid="stSidebar"] {
    border-right: 1px solid rgba(255,255,255,0.06);
    background: linear-gradient(180deg, rgba(8,17,30,0.97), rgba(8,14,24,0.99)) !important;
}

[data-testid="stSidebar"] .block-container {
    padding-top: 1.2rem;
}

hr {
    border-color: rgba(255,255,255,0.07);
}

.section-title {
    margin-top: 0.05rem;
    margin-bottom: 0.3rem;
    font-size: 2rem;
    line-height: 1.1;
    font-weight: 800;
    letter-spacing: -0.03em;
    color: var(--text-main);
}

.section-subtitle {
    color: var(--text-soft);
    margin-bottom: 1.15rem;
    line-height: 1.62;
    max-width: 60rem;
    font-size: 0.98rem;
}

.sidebar-brand {
    border-radius: 24px;
    padding: 1.05rem 1rem;
    margin-bottom: 1rem;
    background: linear-gradient(180deg, rgba(255,255,255,0.035), rgba(255,255,255,0.018));
    border: 1px solid rgba(255,255,255,0.08);
    box-shadow: 0 12px 28px rgba(0,0,0,0.18);
}

.sidebar-brand-title {
    color: var(--text-main);
    font-size: 1.05rem;
    font-weight: 780;
    letter-spacing: -0.02em;
    margin-top: 0.15rem;
}

.sidebar-brand-subtitle {
    color: var(--text-soft);
    font-size: 0.92rem;
    line-height: 1.58;
    margin-top: 0.3rem;
}

.sidebar-stats {
    display: grid;
    grid-template-columns: 1fr;
    gap: 0.75rem;
    margin-bottom: 1rem;
}

.sidebar-stat {
    border-radius: 18px;
    padding: 0.95rem 1rem;
    background: linear-gradient(180deg, rgba(255,255,255,0.028), rgba(255,255,255,0.018));
    border: 1px solid rgba(255,255,255,0.08);
    box-shadow: 0 10px 24px rgba(0,0,0,0.14);
}

.sidebar-stat-value {
    color: var(--text-main);
    font-size: 1.18rem;
    font-weight: 780;
    line-height: 1.05;
}

.sidebar-stat-label {
    color: var(--text-soft);
    font-size: 0.84rem;
    margin-top: 0.22rem;
}

.sidebar-note {
    border-radius: 18px;
    padding: 0.95rem 1rem;
    background: linear-gradient(180deg, rgba(255,255,255,0.03), rgba(255,255,255,0.02));
    border: 1px solid rgba(255,255,255,0.08);
    color: var(--text-soft);
    font-size: 0.9rem;
    line-height: 1.55;
}

.selector-card {
    border-radius: 22px;
    padding: 1rem 1.05rem;
    margin-bottom: 1rem;
    background: linear-gradient(180deg, rgba(255,255,255,0.03), rgba(255,255,255,0.018));
    border: 1px solid rgba(255,255,255,0.08);
}

.selector-title {
    color: var(--text-main);
    font-size: 1rem;
    font-weight: 740;
    margin-bottom: 0.22rem;
}

.selector-subtitle {
    color: var(--text-soft);
    font-size: 0.9rem;
    line-height: 1.52;
    margin-bottom: 0.7rem;
}

.hero-shell {
    margin-top: 0.1rem;
    margin-bottom: 1.2rem;
}

.hero-banner-wrap {
    border-radius: 28px;
    overflow: hidden;
    border: 1px solid rgba(255,255,255,0.06);
    box-shadow: var(--shadow-strong);
}

.hero-actions-wrap {
    margin-top: 0.95rem;
    padding: 1rem 1.05rem;
    border-radius: 24px;
    border: 1px solid rgba(255,255,255,0.08);
    background: linear-gradient(180deg, rgba(255,255,255,0.032), rgba(255,255,255,0.018));
    box-shadow: var(--shadow-soft);
}

.hero-actions-note {
    color: var(--text-soft);
    font-size: 0.96rem;
    line-height: 1.55;
    margin-bottom: 0.9rem;
}

.metric-strip {
    display: grid;
    grid-template-columns: repeat(4, minmax(0, 1fr));
    gap: 0;
    border-radius: 24px;
    overflow: hidden;
    border: 1px solid rgba(255,255,255,0.08);
    background: linear-gradient(180deg, rgba(255,255,255,0.035), rgba(255,255,255,0.02));
    box-shadow: var(--shadow-soft);
    margin-bottom: 1rem;
}

.metric-cell {
    padding: 1.15rem 1.2rem;
    border-right: 1px solid rgba(255,255,255,0.06);
}

.metric-cell:last-child {
    border-right: none;
}

.metric-strip-value {
    font-size: 2.15rem;
    font-weight: 800;
    letter-spacing: -0.03em;
    line-height: 1;
    color: var(--text-main);
}

.metric-strip-label {
    margin-top: 0.45rem;
    color: var(--text-soft);
    font-size: 0.92rem;
}

.insight-grid {
    display: grid;
    grid-template-columns: repeat(2, minmax(0, 1fr));
    gap: 1rem;
    margin-bottom: 1rem;
}

.insight-card {
    padding: 1.1rem 1.15rem;
    border-radius: 24px;
    background: linear-gradient(180deg, rgba(255,255,255,0.03), rgba(255,255,255,0.018));
    border: 1px solid rgba(255,255,255,0.08);
    box-shadow: var(--shadow-soft);
}

.insight-title {
    color: var(--text-main);
    font-size: 1rem;
    font-weight: 760;
    margin-bottom: 0.45rem;
}

.insight-text {
    color: var(--text-soft);
    font-size: 0.96rem;
    line-height: 1.7;
}

.quick-actions-card {
    padding: 1rem 1.05rem 1.15rem 1.05rem;
    border-radius: 24px;
    background: linear-gradient(180deg, rgba(255,255,255,0.032), rgba(255,255,255,0.018));
    border: 1px solid rgba(255,255,255,0.08);
    box-shadow: var(--shadow-soft);
    margin-bottom: 1rem;
}

.chart-card {
    padding: 1rem 1.05rem;
    border-radius: 24px;
    background: linear-gradient(180deg, rgba(255,255,255,0.025), rgba(255,255,255,0.015));
    border: 1px solid rgba(255,255,255,0.08);
    box-shadow: var(--shadow-soft);
    margin-bottom: 1rem;
}

.quick-browse-card {
    padding: 1rem 1.05rem;
    border-radius: 24px;
    background: linear-gradient(180deg, rgba(255,255,255,0.025), rgba(255,255,255,0.015));
    border: 1px solid rgba(255,255,255,0.08);
    box-shadow: var(--shadow-soft);
    margin-bottom: 1rem;
}

.compound-card {
    padding: 1rem 1.05rem;
    border-radius: 22px;
    border: 1px solid rgba(255,255,255,0.08);
    background: linear-gradient(180deg, rgba(255,255,255,0.028), rgba(255,255,255,0.016));
    margin-bottom: 0.9rem;
    box-shadow: var(--shadow-soft);
}

.compound-card:hover {
    border-color: rgba(115,231,255,0.22);
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
    padding: 0.34rem 0.65rem;
    font-size: 0.83rem;
    color: #E8EEF8;
    background: rgba(255,255,255,0.045);
    border: 1px solid rgba(255,255,255,0.07);
}

.helper-card {
    border-radius: 22px;
    padding: 1rem 1.05rem;
    border: 1px solid rgba(255,255,255,0.08);
    background: rgba(255,255,255,0.024);
    margin-bottom: 0.95rem;
}

.helper-title {
    color: var(--text-main);
    font-size: 1rem;
    font-weight: 740;
    margin-bottom: 0.28rem;
}

.helper-text {
    color: var(--text-soft);
    font-size: 0.93rem;
    line-height: 1.58;
}

div[data-baseweb="select"] > div {
    border-radius: 14px !important;
}

div[data-testid="stTextInput"] input,
div[data-testid="stTextArea"] textarea,
div[data-testid="stNumberInput"] input {
    border-radius: 14px !important;
}

div[data-testid="stButton"] button,
div[data-testid="stDownloadButton"] button {
    border-radius: 16px !important;
    min-height: 46px !important;
    font-weight: 680 !important;
    transition: all 0.18s ease !important;
}

div[data-testid="stButton"] button:hover,
div[data-testid="stDownloadButton"] button:hover {
    border-color: rgba(97, 216, 237, 0.34) !important;
    box-shadow: 0 0 0 1px rgba(97,216,237,0.05) !important;
}

.quick-action-primary button {
    background: linear-gradient(90deg, rgba(66,183,255,0.22), rgba(123,66,255,0.22)) !important;
    border: 1px solid rgba(97,216,237,0.35) !important;
    color: #F7FAFF !important;
}

.quick-action-secondary button {
    background: rgba(255,255,255,0.02) !important;
    border: 1px solid rgba(255,255,255,0.10) !important;
    color: #F5F8FD !important;
}

div[data-testid="stRadio"] > div {
    gap: 0.55rem;
}

div[data-testid="stRadio"] label {
    background: rgba(255,255,255,0.022);
    border: 1px solid rgba(255,255,255,0.08);
    border-radius: 999px;
    padding: 0.42rem 0.95rem;
    transition: all 0.18s ease;
}

div[data-testid="stRadio"] label p {
    font-size: 0.95rem !important;
    font-weight: 600 !important;
}

div[data-testid="stRadio"] label:has(input:checked) {
    background: linear-gradient(90deg, rgba(97,216,237,0.24), rgba(156,99,241,0.24));
    border-color: rgba(97,216,237,0.42);
    box-shadow: 0 0 0 1px rgba(97,216,237,0.06);
}

[data-testid="stDataFrame"] {
    border-radius: 16px;
    overflow: hidden;
    border: 1px solid rgba(255,255,255,0.06);
}

@media (max-width: 1100px) {
    .metric-strip {
        grid-template-columns: repeat(2, minmax(0, 1fr));
    }
    .metric-cell:nth-child(2) {
        border-right: none;
    }
    .insight-grid {
        grid-template-columns: 1fr;
    }
}

@media (max-width: 900px) {
    .section-title {
        font-size: 1.55rem;
    }
    .section-subtitle {
        font-size: 0.95rem;
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
                compound_class TEXT,
                compound_subclass TEXT,
                source_material TEXT,
                sample_code TEXT,
                collection_location TEXT,
                gps_coordinates TEXT,
                depth_m REAL,
                uv_data TEXT,
                ftir_data TEXT,
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
        conn.commit()
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
    finally:
        conn.close()


ensure_database_schema()
ensure_compounds_schema()

# =========================
# Generic helpers
# =========================
def render_dashboard_bar_chart(dataframe, x_col, y_col, color_hex):
    fig = px.bar(
        dataframe,
        x=x_col,
        y=y_col,
        text=y_col,
    )

    fig.update_traces(
        marker=dict(
            color=color_hex,
            line=dict(color="rgba(255,255,255,0.15)", width=1)
        ),
        textposition="outside",
        hovertemplate=f"<b>%{{x}}</b><br>{y_col}: %{{y}}<extra></extra>",
    )

    fig.update_layout(
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(color="#C9D4E0", size=13),
        margin=dict(l=10, r=10, t=10, b=10),
        showlegend=False,
        height=320,
        bargap=0.4,
    )

    fig.update_xaxes(
        showgrid=False,
        color="#9FB0C3",
    )

    fig.update_yaxes(
        gridcolor="rgba(255,255,255,0.08)",
        zeroline=False,
        color="#9FB0C3",
    )

    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})
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
    if normalized_value and normalized_value not in clean_options:
        clean_options.append(normalized_value)

    select_options = [""] + sorted(set(clean_options)) + ["Custom..."]
    default_value = normalized_value if normalized_value in select_options else ("Custom..." if normalized_value else "")
    selected = st.selectbox(
        label,
        select_options,
        index=select_options.index(default_value),
        key=f"{key}_select",
        help=help_text,
    )

    if selected == "Custom...":
        custom_default = normalized_value if normalized_value not in select_options else ""
        return st.text_input(
            f"{label} (Custom)",
            value=custom_default,
            key=f"{key}_custom",
        )

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
        "wizard_source_material_select",
        "wizard_source_material_custom",
        "wizard_sample_code",
        "wizard_collection_location",
        "wizard_gps_coordinates",
        "wizard_depth_m",
        "wizard_uv_data",
        "wizard_ftir_data",
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
    st.session_state["compound_wizard_step"] = 1

def keyword_search_mask(df: pd.DataFrame, keyword: str) -> pd.Series:
    searchable_columns = [
        "trivial_name",
        "iupac_name",
        "smiles",
        "inchi",
        "inchikey",
        "sample_code",
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

def calculate_completeness_score(compound_row, proton_df, carbon_df, spectra_df):
    row = compound_row.iloc[0] if isinstance(compound_row, pd.DataFrame) else compound_row
    checks = [
        bool(maybe_blank(row.get("trivial_name"))),
        bool(maybe_blank(row.get("molecular_formula"))),
        bool(maybe_blank(row.get("smiles")) or maybe_blank(row.get("inchi")) or maybe_blank(row.get("inchikey"))),
        bool(maybe_blank(row.get("compound_class"))),
        bool(maybe_blank(row.get("source_material"))),
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
        result = result[result["source_material"].fillna("").astype(str).str.strip() == source_filter]

    if data_source_filter != "All":
        result = result[result["data_source"].fillna("").astype(str).str.strip() == data_source_filter]

    return result

def filter_similarity_results(results, class_filter="All", source_filter="All", data_source_filter="All"):
    filtered = []

    for item in results:
        ok = True

        if class_filter != "All" and clean_text(item.get("compound_class")) != class_filter:
            ok = False

        if source_filter != "All" and clean_text(item.get("source_material")) != source_filter:
            ok = False

        if data_source_filter != "All" and clean_text(item.get("data_source")) != data_source_filter:
            ok = False

        if ok:
            filtered.append(item)

    return filtered

def dataframe_to_csv_bytes(df: pd.DataFrame) -> bytes:
    return df.to_csv(index=False).encode("utf-8")

def get_backup_bytes():
    with open(DB_PATH, "rb") as f:
        return f.read()

def count_related_records(filtered_ids):
    conn = get_connection()

    if filtered_ids:
        placeholders = ",".join("?" * len(filtered_ids))
        proton_query = f"SELECT COUNT(*) AS n FROM proton_nmr WHERE compound_id IN ({placeholders})"
        carbon_query = f"SELECT COUNT(*) AS n FROM carbon_nmr WHERE compound_id IN ({placeholders})"
        spectra_query = f"SELECT COUNT(*) AS n FROM spectra_files WHERE compound_id IN ({placeholders})"

        proton_count = pd.read_sql_query(proton_query, conn, params=filtered_ids)["n"][0]
        carbon_count = pd.read_sql_query(carbon_query, conn, params=filtered_ids)["n"][0]
        spectra_count = pd.read_sql_query(spectra_query, conn, params=filtered_ids)["n"][0]
    else:
        proton_count = 0
        carbon_count = 0
        spectra_count = 0

    conn.close()
    return proton_count, carbon_count, spectra_count


def calculate_workspace_health(compounds_df: pd.DataFrame):
    if compounds_df.empty:
        return {
            "structure_ready": 0,
            "reference_ready": 0,
            "external_ready": 0,
            "submission_ready": 0,
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
    submission_ready = compounds_df[
        compounds_df["trivial_name"].fillna("").astype(str).str.strip().ne("")
        & compounds_df["compound_class"].fillna("").astype(str).str.strip().ne("")
        & compounds_df["source_material"].fillna("").astype(str).str.strip().ne("")
    ]

    return {
        "structure_ready": int(len(structure_ready)),
        "reference_ready": int(len(reference_ready)),
        "external_ready": int(len(external_ready_ids)),
        "submission_ready": int(len(submission_ready)),
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
        st.markdown('<div class="metric-card">', unsafe_allow_html=True)
        st.metric(label, value)
        st.markdown('</div>', unsafe_allow_html=True)


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


def render_sidebar_workspace_summary(active_section: str, all_compounds_df: pd.DataFrame):
    total_compounds = len(all_compounds_df)
    proton_count, carbon_count, spectra_count = count_related_records(all_compounds_df["id"].tolist())
    health = calculate_workspace_health(all_compounds_df)
    active_copy = NAV_SECTION_COPY.get(active_section, {"title": active_section, "summary": ""})

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
    st.caption(
        f"Structure-ready: {health['structure_ready']} | Reference-ready: {health['reference_ready']} | "
        f"Drive-linked: {health['external_ready']}"
    )


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
    source_material = clean_text(row["source_material"])
    sample_code = clean_text(row["sample_code"])

    st.markdown(
        f"""
        <div class="compound-card">
            <div class="result-title">{title}</div>
            <div class="result-subtitle">{formula}</div>
            <div class="info-chip-row">
                <span class="info-chip">Class: {compound_class}</span>
                <span class="info-chip">Subclass: {subclass}</span>
                <span class="info-chip">Source: {source_material}</span>
                <span class="info-chip">Sample: {sample_code}</span>
            </div>
        </div>
        """,
        unsafe_allow_html=True
    )

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

    st.markdown('<div class="hero-actions-wrap">', unsafe_allow_html=True)

    c1, c2, c3 = st.columns([1.25, 1, 1])
    with c1:
        st.markdown('<div class="hero-btn-primary">', unsafe_allow_html=True)
        if st.button("Browse Dashboard", use_container_width=True, key="hero_overview_btn"):
            set_main_nav("Dashboard")
            st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)

    with c2:
        st.markdown('<div class="hero-btn-secondary">', unsafe_allow_html=True)
        if st.button("Search Spectra", use_container_width=True, key="hero_search_btn"):
            set_main_nav("Search & Match")
            st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)

    with c3:
        st.markdown('<div class="hero-btn-secondary">', unsafe_allow_html=True)
        if st.button("Start Submission", use_container_width=True, key="hero_add_btn"):
            set_main_nav("Compound Workspace")
            set_compound_page("New Submission")
            st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)

    st.markdown('</div>', unsafe_allow_html=True)

# =========================
# Data loading
# =========================
def load_all_compounds():
    conn = get_connection()
    query = """
        SELECT id, trivial_name, iupac_name, molecular_formula,
               smiles, inchi, inchikey,
               compound_class, compound_subclass,
               source_material, sample_code, collection_location,
               gps_coordinates, depth_m, uv_data, ftir_data,
               optical_rotation, melting_point, crystallization_method,
               structure_image_path, journal_name, article_title, publication_year,
               volume, issue, pages, doi, ccdc_number,
               molecular_weight, hrms_data, data_source, note
        FROM compounds
        ORDER BY id ASC
    """
    df = pd.read_sql_query(query, conn)
    conn.close()
    return df

def load_compound_row(compound_id):
    conn = get_connection()
    query = """
        SELECT id, trivial_name, iupac_name, molecular_formula,
               smiles, inchi, inchikey,
               compound_class, compound_subclass,
               source_material, sample_code, collection_location,
               gps_coordinates, depth_m, uv_data, ftir_data,
               optical_rotation, melting_point, crystallization_method,
               structure_image_path, journal_name, article_title, publication_year,
               volume, issue, pages, doi, ccdc_number,
               molecular_weight, hrms_data, data_source, note
        FROM compounds
        WHERE id = ?
    """
    df = pd.read_sql_query(query, conn, params=(compound_id,))
    conn.close()
    return df

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
    source_material,
    sample_code,
    collection_location,
    gps_coordinates,
    depth_m,
    uv_data,
    ftir_data,
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
            source_material,
            sample_code,
            collection_location,
            gps_coordinates,
            depth_m,
            uv_data,
            ftir_data,
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
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        trivial_name,
        iupac_name,
        molecular_formula,
        compound_class,
        compound_subclass,
        smiles,
        inchi,
        inchikey,
        source_material,
        sample_code,
        collection_location,
        gps_coordinates,
        depth_m,
        uv_data,
        ftir_data,
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
    source_material,
    sample_code,
    collection_location,
    gps_coordinates,
    depth_m,
    uv_data,
    ftir_data,
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
            source_material = ?,
            sample_code = ?,
            collection_location = ?,
            gps_coordinates = ?,
            depth_m = ?,
            uv_data = ?,
            ftir_data = ?,
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
        source_material,
        sample_code,
        collection_location,
        gps_coordinates,
        depth_m,
        uv_data,
        ftir_data,
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
    conn.close()

def delete_compound_record(compound_id):
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("DELETE FROM proton_nmr WHERE compound_id = ?", (compound_id,))
        cursor.execute("DELETE FROM carbon_nmr WHERE compound_id = ?", (compound_id,))
        cursor.execute("DELETE FROM spectra_files WHERE compound_id = ?", (compound_id,))
        cursor.execute("DELETE FROM compounds WHERE id = ?", (compound_id,))
        conn.commit()
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
    conn.close()

def delete_proton_record_by_id(proton_id):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM proton_nmr WHERE id = ?", (proton_id,))
    conn.commit()
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
    conn.close()

def delete_carbon_record_by_id(carbon_id):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM carbon_nmr WHERE id = ?", (carbon_id,))
    conn.commit()
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
    conn.close()

def delete_spectrum_file_record_by_id(file_id):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM spectra_files WHERE id = ?", (file_id,))
    conn.commit()
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

        insert_compound_record(
            trivial_name=trivial_name,
            iupac_name=maybe_blank(row.get("iupac_name")),
            molecular_formula=maybe_blank(row.get("molecular_formula")),
            compound_class=maybe_blank(row.get("compound_class")),
            compound_subclass=maybe_blank(row.get("compound_subclass")),
            smiles=maybe_blank(row.get("smiles")),
            inchi=maybe_blank(row.get("inchi")),
            inchikey=maybe_blank(row.get("inchikey")),
            source_material=maybe_blank(row.get("source_material")),
            sample_code=maybe_blank(row.get("sample_code")),
            collection_location=maybe_blank(row.get("collection_location")),
            gps_coordinates=maybe_blank(row.get("gps_coordinates")),
            depth_m=depth_value,
            uv_data=maybe_blank(row.get("uv_data")),
            ftir_data=maybe_blank(row.get("ftir_data")),
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
            SELECT id, trivial_name, sample_code, molecular_formula, smiles, inchi, inchikey, source_material,
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
    return result_df.rename(columns={
        "id": "ID",
        "trivial_name": "Trivial Name",
        "iupac_name": "IUPAC Name",
        "molecular_formula": "Molecular Formula",
        "compound_class": "Compound Class",
        "compound_subclass": "Compound Subclass",
        "source_material": "Source Material",
        "sample_code": "Sample Code",
        "collection_location": "Collection Location",
        "gps_coordinates": "GPS Coordinates",
        "depth_m": "Depth (m)",
        "uv_data": "UV Data",
        "ftir_data": "FTIR Data",
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
            "Source Material": clean_text(item["source_material"]),
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
            "Source Material": clean_text(item["source_material"]),
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
            "Source Material": clean_text(item["source_material"]),
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

Source Material: {clean_text(row['source_material'])}
Sample Code: {clean_text(row['sample_code'])}
Collection Location: {clean_text(row['collection_location'])}
GPS Coordinates: {clean_text(row['gps_coordinates'])}
Depth (m): {clean_text(row['depth_m'])}

UV Data: {clean_text(row['uv_data'])}
FTIR Data: {clean_text(row['ftir_data'])}
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
"""
    return summary.encode("utf-8")

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
    row_data = row.iloc[0]

    section_header(
        clean_text(row_data["trivial_name"]),
        f"Record ID {row_data['id']} · full metadata, structure, peak tables, and linked spectra arranged in one review page"
    )

    st.markdown('<div class="action-strip">', unsafe_allow_html=True)
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
        if st.button("Edit This Record", key=f"edit_compound_from_detail_{row_data['id']}", use_container_width=True):
            open_compound_editor(int(row_data["id"]))
            st.rerun()
    with action_col3:
        if st.button("Open 1H Workspace", key=f"open_1h_from_detail_{row_data['id']}", use_container_width=True):
            st.session_state["selected_compound_id"] = int(row_data["id"])
            set_main_nav("1H Peaks")
            st.rerun()
    with action_col4:
        if st.button("Open 13C Workspace", key=f"open_13c_from_detail_{row_data['id']}", use_container_width=True):
            st.session_state["selected_compound_id"] = int(row_data["id"])
            set_main_nav("13C Peaks")
            st.rerun()
    with action_col5:
        if st.button("Open Spectra Files", key=f"open_spectra_from_detail_{row_data['id']}", use_container_width=True):
            st.session_state["selected_compound_id"] = int(row_data["id"])
            set_main_nav("Spectra Library")
            st.rerun()
    st.markdown('</div>', unsafe_allow_html=True)

    completeness_score = calculate_completeness_score(row, proton_df_raw, carbon_df_raw, spectra_df_raw)

    m1, m2, m3, m4 = st.columns(4)
    render_metric_card("1H NMR Peaks", len(proton_df_raw), m1)
    render_metric_card("13C NMR Peaks", len(carbon_df_raw), m2)
    render_metric_card("Spectra Files", len(spectra_df_raw), m3)
    render_metric_card("Completeness", f"{completeness_score}%", m4)

    top_left, top_right = st.columns([1.7, 1])

    with top_left:
        section_header("Core Information")
        c1, c2 = st.columns(2)

        with c1:
            render_kv("IUPAC Name", row_data["iupac_name"])
            render_kv("Molecular Formula", row_data["molecular_formula"])
            render_kv("Mr", row_data["molecular_weight"])
            render_kv("SMILES", row_data.get("smiles"))
            render_kv("InChI", row_data.get("inchi"))
            render_kv("InChIKey", row_data.get("inchikey"))
            render_kv("Compound Class", row_data["compound_class"])
            render_kv("Compound Subclass", row_data["compound_subclass"])
            render_kv("Source Material", row_data["source_material"])
            render_kv("Sample Code", row_data["sample_code"])

        with c2:
            render_kv("Collection Location", row_data["collection_location"])
            render_kv("GPS Coordinates", row_data["gps_coordinates"])
            render_kv("Depth (m)", row_data["depth_m"])
            render_kv("Data Source", row_data["data_source"])
            render_kv("Journal Name", row_data["journal_name"])
            render_kv("Article Title", row_data["article_title"])
            render_kv("DOI", row_data["doi"])
            render_kv("CCDC", row_data["ccdc_number"])

        section_header("Physical and Spectral Summary")
        p1, p2 = st.columns(2)
        with p1:
            render_kv("UV Data", row_data["uv_data"])
            render_kv("FTIR Data", row_data["ftir_data"])
            render_kv("Optical Rotation", row_data["optical_rotation"])
            render_kv("HRMS", row_data["hrms_data"])
        with p2:
            render_kv("Melting Point", row_data["melting_point"])
            render_kv("Crystallization Method", row_data["crystallization_method"])
            render_kv(
                "Publication Year / Volume / Issue / Pages",
                f"{clean_text(row_data['publication_year'])} / {clean_text(row_data['volume'])} / {clean_text(row_data['issue'])} / {clean_text(row_data['pages'])}"
            )

        section_header("Notes")
        st.markdown('<div class="panel-card">', unsafe_allow_html=True)
        st.write(clean_text(row_data["note"]))
        st.markdown('</div>', unsafe_allow_html=True)

    with top_right:
        section_header("Structure")
        st.markdown('<div class="structure-card">', unsafe_allow_html=True)
        structure_path = row_data["structure_image_path"]
        if pd.notna(structure_path) and str(structure_path).strip():
            full_path = get_full_file_path(structure_path)
            if full_path and full_path.exists():
                st.image(str(full_path), width="stretch")
                st.caption(full_path.name)
            else:
                st.warning("Structure image file not found.")
                if full_path:
                    st.code(str(full_path))
        else:
            st.info("No structure image path available.")
        st.markdown("---")
        st.write(f"**SMILES:** {clean_text(row_data.get('smiles'))}")
        st.write(f"**InChI:** {clean_text(row_data.get('inchi'))}")
        st.write(f"**InChIKey:** {clean_text(row_data.get('inchikey'))}")
        st.markdown('</div>', unsafe_allow_html=True)

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

def render_best_match_summary(item, mode_label):
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
            <div class="badge-row"><strong>Source Material:</strong> {clean_text(item.get('source_material'))}</div>
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
        source_material = clean_text(item.get("source_material"))
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
                    <div class="badge-row"><strong>Source Material:</strong> {source_material}</div>
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
        ["Keyword Search", "13C Match", "1H Match", "Combined Match"],
        horizontal=True
    )

    with st.sidebar.expander("Search Filters", expanded=True):
        search_class_filter = st.selectbox(
            "Compound Class",
            build_filter_options(all_compounds_df, "compound_class"),
            key="search_class_filter"
        )
        search_source_filter = st.selectbox(
            "Source Material",
            build_filter_options(all_compounds_df, "source_material"),
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

    if search_mode == "Keyword Search":
        filtered_df = apply_dataframe_filters(
            all_compounds_df,
            class_filter=search_class_filter,
            source_filter=search_source_filter,
            data_source_filter=search_data_source_filter
        )

        with st.form("search_by_name_form"):
            st.markdown('<div class="panel-card">', unsafe_allow_html=True)
            keyword = st.text_input(
                "Enter compound name, keyword, sample code, source material, journal, or DOI",
                key="search_name_keyword",
            )
            run_name_search = st.form_submit_button("Run Keyword Search", use_container_width=True)
            st.markdown('</div>', unsafe_allow_html=True)

        if keyword.strip():
            result = filtered_df[keyword_search_mask(filtered_df, keyword)].copy()
            st.write(f"Found {len(result)} compound(s).")

            if not result.empty:
                export_df = export_name_results(result)
                st.download_button(
                    label="Download Search Results as CSV",
                    data=dataframe_to_csv_bytes(export_df),
                    file_name="search_by_name_results.csv",
                    mime="text/csv",
                    key="download_name_csv"
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
                    st.download_button(
                        label="Download 13C Similarity Results as CSV",
                        data=dataframe_to_csv_bytes(export_df),
                        file_name="search_by_13c_results.csv",
                        mime="text/csv",
                        key="download_13c_csv"
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
                    st.download_button(
                        label="Download 1H Similarity Results as CSV",
                        data=dataframe_to_csv_bytes(export_df),
                        file_name="search_by_1h_results.csv",
                        mime="text/csv",
                        key="download_1h_csv"
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
                    st.download_button(
                        label="Download Combined Similarity Results as CSV",
                        data=dataframe_to_csv_bytes(export_df),
                        file_name="search_combined_results.csv",
                        mime="text/csv",
                        key="download_combined_csv"
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
            "Source Material",
            build_filter_options(all_compounds_df, "source_material"),
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
    health = calculate_workspace_health(filtered_df)

    st.markdown(
        f"""
        <div class="metric-strip">
            <div class="metric-cell">
                <div class="metric-strip-value">{len(filtered_df)}</div>
                <div class="metric-strip-label">Compounds</div>
            </div>
            <div class="metric-cell">
                <div class="metric-strip-value">{proton_count}</div>
                <div class="metric-strip-label">1H Peaks</div>
            </div>
            <div class="metric-cell">
                <div class="metric-strip-value">{carbon_count}</div>
                <div class="metric-strip-label">13C Peaks</div>
            </div>
            <div class="metric-cell">
                <div class="metric-strip-value">{spectra_count}</div>
                <div class="metric-strip-label">Spectra Files</div>
            </div>
        </div>
        """,
        unsafe_allow_html=True
    )

    st.markdown(
        f"""
        <div class="metric-strip" style="margin-top:-0.1rem;">
            <div class="metric-cell">
                <div class="metric-strip-value">{health["structure_ready"]}</div>
                <div class="metric-strip-label">Structure IDs Ready</div>
            </div>
            <div class="metric-cell">
                <div class="metric-strip-value">{health["reference_ready"]}</div>
                <div class="metric-strip-label">Reference Ready</div>
            </div>
            <div class="metric-cell">
                <div class="metric-strip-value">{health["external_ready"]}</div>
                <div class="metric-strip-label">Drive-linked Records</div>
            </div>
            <div class="metric-cell">
                <div class="metric-strip-value">{health["submission_ready"]}</div>
                <div class="metric-strip-label">Submission-ready Metadata</div>
            </div>
        </div>
        """,
        unsafe_allow_html=True
    )

    st.markdown(
        """
        <div class="insight-grid">
            <div class="insight-card">
                <div class="insight-title">Curation priorities</div>
                <div class="insight-text">
                    Prioritize records that still miss SMILES, InChI, InChIKey, citation metadata,
                    and external raw-data links. These areas will have the biggest effect on future
                    search, reproducibility, and public usability.
                </div>
            </div>
            <div class="insight-card">
                <div class="insight-title">Public access readiness</div>
                <div class="insight-text">
                    For public small-scale access, keep preview images lightweight, keep raw data in
                    Google Drive, and make sure each shared file has viewer permission for approved users.
                </div>
            </div>
        </div>
        """,
        unsafe_allow_html=True
    )

    st.markdown('<div class="quick-actions-card">', unsafe_allow_html=True)
    st.markdown('<div class="section-title" style="font-size:1.55rem;">Quick Actions</div>', unsafe_allow_html=True)

    qa1, qa2, qa3, qa4 = st.columns(4)

    with qa1:
        st.markdown('<div class="quick-action-primary">', unsafe_allow_html=True)
        if st.button("Keyword Search", use_container_width=True, key="overview_keyword_search"):
            set_main_nav("Search & Match")
        st.markdown('</div>', unsafe_allow_html=True)

    with qa2:
        st.markdown('<div class="quick-action-secondary">', unsafe_allow_html=True)
        if st.button("Run Spectral Match", use_container_width=True, key="overview_spectral_match"):
            set_main_nav("Search & Match")
        st.markdown('</div>', unsafe_allow_html=True)

    with qa3:
        st.markdown('<div class="quick-action-secondary">', unsafe_allow_html=True)
        if st.button("Start Submission", use_container_width=True, key="overview_start_submission"):
            set_main_nav("Compound Workspace")
            set_compound_page("New Submission")
        st.markdown('</div>', unsafe_allow_html=True)

    with qa4:
        st.markdown('<div class="quick-action-secondary">', unsafe_allow_html=True)
        if st.button("Browse Records", use_container_width=True, key="overview_browse_records"):
            set_main_nav("Compound Workspace")
            set_compound_page("Browse Record")
        st.markdown('</div>', unsafe_allow_html=True)

    st.markdown('</div>', unsafe_allow_html=True)

    left, right = st.columns(2)

    with left:
        st.markdown('<div class="chart-card">', unsafe_allow_html=True)
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

        st.markdown('</div>', unsafe_allow_html=True)

    with right:
        st.markdown('<div class="chart-card">', unsafe_allow_html=True)
        section_header("Source Material Distribution")

        if filtered_df.empty:
            st.info("No compounds available for the selected filters.")
        else:
            source_counts = (
                filtered_df["source_material"]
                .fillna("Uncategorized")
                .replace("", "Uncategorized")
                .value_counts()
                .reset_index()
            )
            source_counts.columns = ["Source Material", "Count"]

            render_dashboard_bar_chart(
                source_counts,
                x_col="Source Material",
                y_col="Count",
                color_hex="#9C63F1",
            )

        st.markdown('</div>', unsafe_allow_html=True)

    st.markdown('<div class="quick-browse-card">', unsafe_allow_html=True)
    section_header("Quick Browse", "Card-based browsing for faster scanning than a dense table.")
    preview_count = st.slider(
        "Number of compounds to preview",
        min_value=1,
        max_value=max(1, min(12, len(filtered_df) if not filtered_df.empty else 1)),
        value=min(8, max(1, len(filtered_df) if not filtered_df.empty else 1)),
        key="overview_preview_count"
    )

    if filtered_df.empty:
        st.info("No compounds match the current dashboard filters.")
    else:
        preview_df = filtered_df.head(preview_count)
        for _, row in preview_df.iterrows():
            st.markdown('<div class="compound-card">', unsafe_allow_html=True)
            st.markdown(f"### {clean_text(row.get('trivial_name'))}")
            st.caption(clean_text(row.get("molecular_formula")))
            st.markdown(
                f"""
                <div class="info-chip-row">
                    <span class="info-chip">Class: {clean_text(row.get('compound_class'))}</span>
                    <span class="info-chip">Subclass: {clean_text(row.get('compound_subclass'))}</span>
                    <span class="info-chip">Source: {clean_text(row.get('source_material'))}</span>
                    <span class="info-chip">Sample: {clean_text(row.get('sample_code'))}</span>
                </div>
                """,
                unsafe_allow_html=True
            )
            if st.button("Open", key=f"overview_open_{int(row['id'])}"):
                open_compound_detail(int(row["id"]))
            st.markdown('</div>', unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)

    section_header("Compound Table", "Full filtered table view for exact inspection and export.")
    if filtered_df.empty:
        st.info("No compounds to display.")
    else:
        export_columns = [
            "id",
            "trivial_name",
            "molecular_formula",
            "compound_class",
            "compound_subclass",
            "source_material",
            "sample_code",
        ]
        export_df = filtered_df[[col for col in export_columns if col in filtered_df.columns]].copy()
        st.download_button(
            "Download Current Overview as CSV",
            data=dataframe_to_csv_bytes(export_df),
            file_name="dashboard_overview.csv",
            mime="text/csv",
            key="dashboard_export_csv"
        )
        st.dataframe(export_df, use_container_width=True)

    section_header("Backup")
    if DB_PATH.exists():
        st.download_button(
            "Download SQLite Backup",
            data=DB_PATH.read_bytes(),
            file_name="nmr_backup.db",
            mime="application/octet-stream",
            key="dashboard_backup_db"
        )
    else:
        st.warning("Database file not found.")
        
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
            3. Open `Compound Workspace` to inspect full records, references, and linked files.
            4. Use `1H Peaks`, `13C Peaks`, and `Spectra Library` when you want to manage sub-records directly.
            """
        )

    with use_tabs[1]:
        st.markdown(
            """
            1. Start in `Compound Workspace` > `New Submission`.
            2. Fill the core identity fields first: trivial name, formula, SMILES/InChI/InChIKey, class, subclass, source material, and structure.
            3. Add publication information, notes, and reference fields.
            4. Save the compound record.
            5. Add 1H peaks, 13C peaks, preview images, PDFs, and raw-data links from the dedicated sections if needed.
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
    compound_options = COMPOUND_PAGE_OPTIONS

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
    set_compound_page(compound_page)

    render_helper_card(
        "Compound workspace",
        "Browse full records, create new submissions, import batches, update metadata, and remove outdated entries from one consistent workflow. The editor now lives in a single clear place instead of appearing as a duplicated menu.",
    )

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
                select_or_custom("Compound Class", class_options, "wizard_compound_class")
                select_or_custom("Compound Subclass", subclass_options, "wizard_compound_subclass")
                select_or_custom("Data Source", data_source_options, "wizard_data_source", value="Experimental")

        elif wizard_step == 2:
            c1, c2 = st.columns(2)
            with c1:
                source_options = build_existing_options(compounds_df, "source_material", DEFAULT_SOURCE_OPTIONS)
                select_or_custom("Source Material", source_options, "wizard_source_material")
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
                    "trivial_name": st.session_state.get("wizard_trivial_name", ""),
                    "molecular_formula": st.session_state.get("wizard_formula", ""),
                    "smiles": st.session_state.get("wizard_smiles", ""),
                    "inchi": st.session_state.get("wizard_inchi", ""),
                    "inchikey": st.session_state.get("wizard_inchikey", ""),
                    "compound_class": st.session_state.get("wizard_compound_class_custom") or st.session_state.get("wizard_compound_class_select", ""),
                    "source_material": st.session_state.get("wizard_source_material_custom") or st.session_state.get("wizard_source_material_select", ""),
                    "data_source": st.session_state.get("wizard_data_source_custom") or st.session_state.get("wizard_data_source_select", ""),
                    "hrms_data": st.session_state.get("wizard_hrms_data", ""),
                    "doi": st.session_state.get("wizard_doi", ""),
                    "journal_name": st.session_state.get("wizard_journal_name", ""),
                    "article_title": st.session_state.get("wizard_article_title", ""),
                    "structure_image_path": st.session_state.get("wizard_structure_path", "") or ("uploaded" if st.session_state.get("wizard_structure_upload") else ""),
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
                st.write(f"**Source:** {clean_text(draft_row['source_material'])}")
                st.write(f"**Data Source:** {clean_text(draft_row['data_source'])}")
                st.write(f"**Journal:** {clean_text(st.session_state.get('wizard_journal_name'))}")
                st.write(f"**Article:** {clean_text(st.session_state.get('wizard_article_title'))}")
                st.markdown('</div>', unsafe_allow_html=True)

        nav_left, nav_right = st.columns([1, 1])
        with nav_left:
            if wizard_step > 1 and st.button("Back", use_container_width=True, key=f"wizard_back_{wizard_step}"):
                st.session_state["compound_wizard_step"] = wizard_step - 1
                st.rerun()

        with nav_right:
            if wizard_step < 4:
                if st.button("Continue", use_container_width=True, key=f"wizard_next_{wizard_step}"):
                    if wizard_step == 1 and not maybe_blank(st.session_state.get("wizard_trivial_name")):
                        st.error("Trivial Name is required before moving to the next step.")
                    else:
                        st.session_state["compound_wizard_step"] = wizard_step + 1
                        st.rerun()
            else:
                if st.button("Save New Record", use_container_width=True, key="wizard_submit_compound"):
                    trivial_name = maybe_blank(st.session_state.get("wizard_trivial_name"))
                    iupac_name = maybe_blank(st.session_state.get("wizard_iupac_name"))
                    molecular_formula = maybe_blank(st.session_state.get("wizard_formula"))
                    smiles = maybe_blank(st.session_state.get("wizard_smiles"))
                    inchi = maybe_blank(st.session_state.get("wizard_inchi"))
                    inchikey = maybe_blank(st.session_state.get("wizard_inchikey"))
                    compound_class = maybe_blank(st.session_state.get("wizard_compound_class_custom")) or maybe_blank(st.session_state.get("wizard_compound_class_select"))
                    compound_subclass = maybe_blank(st.session_state.get("wizard_compound_subclass_custom")) or maybe_blank(st.session_state.get("wizard_compound_subclass_select"))
                    source_material = maybe_blank(st.session_state.get("wizard_source_material_custom")) or maybe_blank(st.session_state.get("wizard_source_material_select"))
                    sample_code = maybe_blank(st.session_state.get("wizard_sample_code"))
                    collection_location = maybe_blank(st.session_state.get("wizard_collection_location"))
                    gps_coordinates = maybe_blank(st.session_state.get("wizard_gps_coordinates"))
                    depth_m_text = maybe_blank(st.session_state.get("wizard_depth_m"))
                    uv_data = maybe_blank(st.session_state.get("wizard_uv_data"))
                    ftir_data = maybe_blank(st.session_state.get("wizard_ftir_data"))
                    optical_rotation = maybe_blank(st.session_state.get("wizard_optical_rotation"))
                    melting_point = maybe_blank(st.session_state.get("wizard_melting_point"))
                    crystallization_method = maybe_blank(st.session_state.get("wizard_crystallization_method"))
                    structure_image_path = maybe_blank(st.session_state.get("wizard_structure_path"))
                    structure_upload = st.session_state.get("wizard_structure_upload")
                    journal_name = maybe_blank(st.session_state.get("wizard_journal_name"))
                    article_title = maybe_blank(st.session_state.get("wizard_article_title"))
                    publication_year = maybe_blank(st.session_state.get("wizard_publication_year"))
                    volume = maybe_blank(st.session_state.get("wizard_volume"))
                    issue = maybe_blank(st.session_state.get("wizard_issue"))
                    pages = maybe_blank(st.session_state.get("wizard_pages"))
                    doi = maybe_blank(st.session_state.get("wizard_doi"))
                    ccdc_number = maybe_blank(st.session_state.get("wizard_ccdc_number"))
                    molecular_weight_text = maybe_blank(st.session_state.get("wizard_molecular_weight"))
                    hrms_data = maybe_blank(st.session_state.get("wizard_hrms_data"))
                    data_source = maybe_blank(st.session_state.get("wizard_data_source_custom")) or maybe_blank(st.session_state.get("wizard_data_source_select"))
                    note = maybe_blank(st.session_state.get("wizard_note"))
                    uploaded_spectra = st.session_state.get("wizard_submission_spectra_uploads") or []
                    uploaded_spectrum_type = maybe_blank(st.session_state.get("wizard_submission_spectrum_type_custom")) or maybe_blank(st.session_state.get("wizard_submission_spectrum_type_select")) or "Supporting Data"
                    uploaded_spectrum_note = maybe_blank(st.session_state.get("wizard_submission_spectra_note"))

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
                        source_material=source_material,
                        sample_code=sample_code,
                        collection_location=collection_location,
                        gps_coordinates=gps_coordinates,
                        depth_m=depth_value,
                        uv_data=uv_data,
                        ftir_data=ftir_data,
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

                with st.form("edit_compound_form", clear_on_submit=False):
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
                        )
                        compound_subclass = select_or_custom(
                            "Compound Subclass",
                            build_existing_options(compounds_df, "compound_subclass"),
                            f"edit_compound_subclass_{edit_compound_id}",
                            value=maybe_blank(row["compound_subclass"]),
                        )
                        source_material = select_or_custom(
                            "Source Material",
                            build_existing_options(compounds_df, "source_material", DEFAULT_SOURCE_OPTIONS),
                            f"edit_source_material_{edit_compound_id}",
                            value=maybe_blank(row["source_material"]),
                        )
                        sample_code = st.text_input("Sample Code", value=maybe_blank(row["sample_code"]))
                        collection_location = st.text_input("Collection Location", value=maybe_blank(row["collection_location"]))
                        gps_coordinates = st.text_input("GPS Coordinates", value=maybe_blank(row["gps_coordinates"]))
                        depth_m_text = st.text_input("Depth (m)", value=maybe_blank(row["depth_m"]))

                    with col2:
                        uv_data = st.text_input("UV Data", value=maybe_blank(row["uv_data"]))
                        ftir_data = st.text_input("FTIR Data", value=maybe_blank(row["ftir_data"]))
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
                    submitted_edit = st.form_submit_button("Save Changes")

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
                            source_material=source_material.strip(),
                            sample_code=sample_code.strip(),
                            collection_location=collection_location.strip(),
                            gps_coordinates=gps_coordinates.strip(),
                            depth_m=depth_value,
                            uv_data=uv_data.strip(),
                            ftir_data=ftir_data.strip(),
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
# Spectra pages
# =========================
def show_spectra_pages():
    spectra_page = st.radio(
        "Spectra Tools",
        ["Add Files", "Edit Files", "Delete Files"],
        horizontal=True
    )

    if spectra_page == "Add Files":
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

            with st.form("add_spectra_form", clear_on_submit=False):
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

                submitted_spectra = st.form_submit_button("Save Spectra File")

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

                with st.form("edit_spectra_form", clear_on_submit=False):
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

                    submitted_edit_spectra = st.form_submit_button("Save Changes")

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
# App boot
# =========================
show_app_header()
all_compounds_df = load_all_compounds()
write_batch_import_templates()


# =========================
# Sidebar navigation
# =========================
with st.sidebar:
    active_section = st.session_state.get("main_section_radio", st.session_state.get("nav_section", "Dashboard"))
    render_sidebar_workspace_summary(active_section, all_compounds_df)

    st.markdown("### Workspace")

    nav_options = NAV_OPTIONS
    current_index = 0
    if st.session_state.get("nav_section") in nav_options:
        current_index = nav_options.index(st.session_state["nav_section"])

    main_radio_kwargs = {
        "label": "Open workspace",
        "options": nav_options,
        "key": "main_section_radio",
    }
    if "main_section_radio" not in st.session_state:
        main_radio_kwargs["index"] = current_index
    main_section = st.radio(**main_radio_kwargs)
    st.session_state["nav_section"] = main_section

    st.markdown("---")
    if st.button("Open Guide", use_container_width=True, key="sidebar_open_guide"):
        set_main_nav("Guide")
        st.rerun()
# =========================
# Main routing
# =========================
if main_section == "Dashboard":
    show_overview_page(all_compounds_df)

elif main_section == "Search & Match":
    show_search_page(all_compounds_df)

elif main_section == "Compound Workspace":
    show_compound_pages()

elif main_section == "1H Peaks":
    show_proton_pages()

elif main_section == "13C Peaks":
    show_carbon_pages()

elif main_section == "Spectra Library":
    show_spectra_pages()

elif main_section == "Guide":
    show_guide_page()
