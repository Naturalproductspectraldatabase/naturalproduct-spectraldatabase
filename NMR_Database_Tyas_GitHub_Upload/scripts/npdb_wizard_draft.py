"""Safe multi-step New Submission drafts for NPDB (no network or database access).

Streamlit removes widget keys when widgets stop rendering. Persist ONLY the
currently visible step's keys to separate _draft_ session keys before
navigating, then restore widget keys from drafts as the step is rendered.
Never copy stale keys from inactive steps: those may already be blank.
"""

from __future__ import annotations

from collections.abc import MutableMapping
from typing import Any

WIZARD_STEP_FIELDS: dict[int, tuple[str, ...]] = {
    1: (
        "wizard_trivial_name", "wizard_iupac_name", "wizard_formula",
        "wizard_molecular_weight", "wizard_smiles", "wizard_inchi",
        "wizard_inchikey", "wizard_compound_class_select",
        "wizard_compound_class_custom", "wizard_compound_subclass_select",
        "wizard_compound_subclass_custom", "wizard_data_source_select",
        "wizard_data_source_custom",
    ),
    2: (
        "wizard_source_category_select", "wizard_source_category_custom",
        "wizard_source_organism", "wizard_sample_code",
        "wizard_collection_location", "wizard_gps_coordinates",
        "wizard_depth_m", "wizard_note",
    ),
    3: (
        "wizard_uv_data", "wizard_ftir_data", "wizard_cd_data",
        "wizard_optical_rotation", "wizard_melting_point",
        "wizard_crystallization_method", "wizard_ccdc_number",
        "wizard_hrms_data", "wizard_structure_path",
        "wizard_structure_upload", "wizard_submission_spectrum_type_select",
        "wizard_submission_spectrum_type_custom",
        "wizard_submission_spectra_note", "wizard_submission_spectra_uploads",
    ),
    4: (
        "wizard_journal_name", "wizard_article_title",
        "wizard_publication_year", "wizard_volume", "wizard_issue",
        "wizard_pages", "wizard_doi", "wizard_curation_status",
    ),
}

UPLOAD_KEYS = frozenset({
    "wizard_structure_upload",
    "wizard_submission_spectra_uploads",
})


def persist_visible_wizard_step(state: MutableMapping[str, Any], step: int) -> None:
    """Capture only widgets actually mounted in the current wizard step.

    No-op for absent widget keys. UploadedFile(s) are held only within this
    Streamlit session and must never be serialized to public files/logs.
    Do not erase a previously captured upload when an unmounted widget has
    subsequently been removed by Streamlit.
    """
    if step not in WIZARD_STEP_FIELDS:
        raise ValueError(f"Unsupported wizard step: {step!r}")
    for key in WIZARD_STEP_FIELDS[step]:
        if key not in state:
            continue
        value = state[key]
        if key in UPLOAD_KEYS and not value and state.get(f"_draft_{key}"):
            continue
        state[f"_draft_{key}"] = value


def draft_value(state: MutableMapping[str, Any], key: str, default: Any = "") -> Any:
    """Draft has precedence over transient Streamlit widget state."""
    draft_key = f"_draft_{key}"
    if draft_key in state:
        return state[draft_key]
    return state.get(key, default)


def reset_wizard_drafts(state: MutableMapping[str, Any]) -> None:
    """Forget the complete draft only on explicit reset / verified save."""
    for group in WIZARD_STEP_FIELDS.values():
        for key in group:
            state.pop(key, None)
            state.pop(f"_draft_{key}", None)
    state["compound_wizard_step"] = 1
