"""Owner/curator Quality & Operations Center: DEMO-ONLY foundation.

No database calls, storage access, email, provider actions, or live writes.
All issue/approval/notification rows below are synthetic examples. The
production feature requires separately approved role enforcement, schema,
RLS, event ingestion, signed actions, and durable notification delivery.
"""

from __future__ import annotations

from collections import Counter
from copy import deepcopy
from typing import Any, Mapping, Sequence

OWNER_USERNAME = "npdb_tyas"
CURATOR_USERNAME = "npdb_tjomori"
SEVERITY_ORDER = {"P0": 0, "P1": 1, "P2": 2, "P3": 3}
VALID_STATUSES = {"open", "in_review", "blocked", "resolved", "false_positive"}

# Never use real compound identifiers in these fixtures. A DEMO label must
# never be mistaken for a real record requiring remediation.
DEMO_ISSUES: tuple[dict[str, str], ...] = (
    {
        "issue_id": "DEMO-001", "severity": "P0",
        "category": "Data integrity", "status": "open",
        "title": "Prevent a stale snapshot from overwriting new data",
        "record": "DEMO-REC-101", "assignee": "owner",
        "recommended_action": "Review cache/concurrency tests before enabling editing.",
        "evidence": "Synthetic C1 regression illustration.",
    },
    {
        "issue_id": "DEMO-002", "severity": "P0",
        "category": "Scientific identity", "status": "open",
        "title": "Molecular formula disagrees with structure representation",
        "record": "DEMO-REC-102", "assignee": CURATOR_USERNAME,
        "recommended_action": "Check curated PNG and primary literature; do not change SMILES automatically.",
        "evidence": "Synthetic formula/InChI screening illustration.",
    },
    {
        "issue_id": "DEMO-003", "severity": "P1",
        "category": "Images & files", "status": "in_review",
        "title": "Curated PNG cannot be rendered",
        "record": "DEMO-REC-103", "assignee": CURATOR_USERNAME,
        "recommended_action": "Check the private Storage reference; preserve the curated PNG.",
        "evidence": "Synthetic missing signed-URL illustration.",
    },
    {
        "issue_id": "DEMO-004", "severity": "P1",
        "category": "Security & access", "status": "blocked",
        "title": "Unattributed change requires administrator review",
        "record": "DEMO-REC-104", "assignee": "owner",
        "recommended_action": "Inspect approved actor and provider activity; do not infer identity from a shared key.",
        "evidence": "Synthetic audit-gap illustration.",
    },
    {
        "issue_id": "DEMO-005", "severity": "P2",
        "category": "Metadata", "status": "open",
        "title": "Compound has no approved structure image",
        "record": "DEMO-REC-105", "assignee": CURATOR_USERNAME,
        "recommended_action": "Find a licensed, scientifically verified depiction before uploading.",
        "evidence": "Synthetic missing-image illustration.",
    },
    {
        "issue_id": "DEMO-006", "severity": "P3",
        "category": "Storage & performance", "status": "open",
        "title": "Candidate duplicate object needs retention review",
        "record": "DEMO-REC-106", "assignee": "owner",
        "recommended_action": "Verify original references, file hashes and backups. Do not delete automatically.",
        "evidence": "Synthetic Storage optimization illustration.",
    },
)

DEMO_NOTIFICATIONS: tuple[dict[str, str], ...] = (
    {"event_id": "DEMO-N001", "kind": "Security", "message": "Example: unusual administrator operation", "state": "unread"},
    {"event_id": "DEMO-N002", "kind": "Curation", "message": "Example: editor submitted a proposed metadata review", "state": "unread"},
)

DEMO_APPROVAL_REQUESTS: tuple[dict[str, str], ...] = (
    {
        "request_id": "DEMO-A001", "actor": CURATOR_USERNAME,
        "operation": "Edit metadata for DEMO-REC-102", "risk": "Scientific data change",
        "status": "pending_owner_approval",
        "owner_action": "Review evidence and proposed before/after values.",
    },
    {
        "request_id": "DEMO-A002", "actor": "Codex",
        "operation": "Review isolated regression tests", "risk": "Read-only / local dummy data",
        "status": "pending_owner_approval",
        "owner_action": "Review exact tool, branch and approved scope.",
    },
)


def normalize_identity(value: Any) -> str:
    return str(value or "").strip().casefold()


def owner_allowed(username: str, role: str) -> bool:
    """Double-check both username and authenticated app role."""
    return (
        normalize_identity(username) == OWNER_USERNAME
        and normalize_identity(role) in {"owner", "owner_editor", "admin"}
    )


def curator_allowed(username: str, role: str) -> bool:
    """This does not confer editing privileges; it only gates demo navigation."""
    return (
        normalize_identity(username) == CURATOR_USERNAME
        and normalize_identity(role) == "editor"
    )


def authorized_for_tasks(username: str, role: str) -> bool:
    return owner_allowed(username, role) or curator_allowed(username, role)


def priority_sort_key(issue: Mapping[str, str]) -> tuple[int, str]:
    return (
        SEVERITY_ORDER.get(str(issue.get("severity", "")), 99),
        str(issue.get("issue_id", "")),
    )


def filter_issues(
    issues: Sequence[Mapping[str, str]],
    *,
    severity: str = "All",
    category: str = "All",
    status: str = "All",
    assignee: str = "All",
) -> list[dict[str, str]]:
    """Pure, stable, deterministic filtering for tiny demo records.

    Production will use paginated server-side queries, not in-memory scans.
    """
    result = []
    for item in issues:
        if severity != "All" and item.get("severity") != severity:
            continue
        if category != "All" and item.get("category") != category:
            continue
        if status != "All" and item.get("status") != status:
            continue
        if assignee != "All" and item.get("assignee") != assignee:
            continue
        result.append(dict(item))
    return sorted(result, key=priority_sort_key)


def summarize_issues(issues: Sequence[Mapping[str, str]]) -> dict[str, int]:
    active = [i for i in issues if i.get("status") not in {"resolved", "false_positive"}]
    severity_counts = Counter(i.get("severity") for i in active)
    return {
        "open_active": len(active),
        "P0": severity_counts["P0"],
        "P1": severity_counts["P1"],
        "P2": severity_counts["P2"],
        "P3": severity_counts["P3"],
    }


def make_demo_decision(
    *,
    username: str,
    role: str,
    request_id: str,
    decision: str,
    available_requests: Sequence[Mapping[str, str]] = DEMO_APPROVAL_REQUESTS,
) -> dict[str, str]:
    """Generate a SESSION-ONLY simulation. NEVER authorizes real actions."""
    if not owner_allowed(username, role):
        raise PermissionError("Only the owner can simulate an approval decision.")
    if decision not in {"approve_preview", "reject_preview"}:
        raise ValueError("Unsupported simulation decision.")
    request = next((r for r in available_requests if r.get("request_id") == request_id), None)
    if request is None or request.get("status") != "pending_owner_approval":
        raise ValueError("Unknown or nonpending demo request.")
    return {
        "request_id": request_id,
        "decision": "DEMO_APPROVAL_ONLY" if decision == "approve_preview" else "DEMO_REJECTION_ONLY",
        "effective_permission": "NONE",
        "persistence": "session_state_only",
        "message": "This simulated decision did not grant permission, change records, or send notifications.",
    }


def curator_tasks(username: str, role: str, *, owner_preview: bool = False) -> list[dict[str, str]]:
    if curator_allowed(username, role):
        return filter_issues(DEMO_ISSUES, assignee=CURATOR_USERNAME)
    if owner_preview and owner_allowed(username, role):
        return filter_issues(DEMO_ISSUES, assignee=CURATOR_USERNAME)
    return []


def _issue_rows(issues: Sequence[Mapping[str, str]]) -> list[dict[str, str]]:
    fields = ("issue_id", "severity", "status", "category", "record", "title", "assignee")
    return [{field: str(issue.get(field, "")) for field in fields} for issue in issues]


def render_owner_quality_center(st: Any, username: str, role: str) -> None:
    """Owner-only Streamlit demonstration; does not query live NPDB."""
    if not owner_allowed(username, role):
        st.error("Access denied: this workspace is reserved for the NPDB owner.")
        return

    st.title("Quality & Operations Center")
    st.warning(
        "PROTOTYPE / DEMO DATA ONLY — These are synthetic issues, not live audit findings. "
        "No production queries, writes, email, automated checks, or real approvals are active."
    )
    counts = summarize_issues(DEMO_ISSUES)
    cols = st.columns(4)
    for col, (name, value) in zip(
        cols,
        (("Open issues", counts["open_active"]), ("Critical (P0)", counts["P0"]),
         ("High (P1)", counts["P1"]), ("Unread notices (demo)", len(DEMO_NOTIFICATIONS))),
    ):
        col.metric(name, value)

    issues_tab, scientific_tab, health_tab, activity_tab = st.tabs(
        ["Issues & Action Queue", "Scientific Curation", "System Health", "Activity & Approvals"]
    )
    with issues_tab:
        severities = ["All", "P0", "P1", "P2", "P3"]
        categories = ["All"] + sorted({i["category"] for i in DEMO_ISSUES})
        c1, c2, c3 = st.columns(3)
        severity = c1.selectbox("Priority", severities, key="qoc_demo_severity")
        category = c2.selectbox("Category", categories, key="qoc_demo_category")
        status = c3.selectbox(
            "Status", ["All", "open", "in_review", "blocked", "resolved", "false_positive"],
            key="qoc_demo_status",
        )
        matching = filter_issues(DEMO_ISSUES, severity=severity, category=category, status=status)
        st.dataframe(_issue_rows(matching), use_container_width=True, hide_index=True)
        if matching:
            selected = st.selectbox(
                "Review example issue", [i["issue_id"] for i in matching], key="qoc_demo_issue"
            )
            detail = next(i for i in matching if i["issue_id"] == selected)
            st.markdown("**Recommended next action (review required)**")
            st.write(detail["recommended_action"])
            st.caption("Evidence: " + detail["evidence"])
        st.info(
            "Real issue detection, status transitions and curator assignments will require a "
            "separately approved, access-controlled database design."
        )
    with scientific_tab:
        st.subheader("Scientific integrity")
        st.write(
            "Planned checks: formula vs InChI (with salt/ion exceptions), SMILES identity, "
            "curated PNG provenance, NMR assignment/source, references and missing metadata."
        )
        st.dataframe(
            _issue_rows(filter_issues(DEMO_ISSUES, category="Scientific identity")),
            use_container_width=True, hide_index=True,
        )
        st.caption("Human chemical-structure verification is mandatory; no automatic corrections.")
    with health_tab:
        st.subheader("System health — not connected")
        st.info(
            "Database size, Storage usage, Streamlit memory, availability, backup age, "
            "and alert-delivery monitoring are PLANNED; no live status is asserted here."
        )
        st.caption("No monitoring schedule, background job or email provider is enabled.")
    with activity_tab:
        st.subheader("Owner notifications — demo")
        st.dataframe(list(DEMO_NOTIFICATIONS), use_container_width=True, hide_index=True)
        st.subheader("Approval requests — demo")
        st.dataframe(list(DEMO_APPROVAL_REQUESTS), use_container_width=True, hide_index=True)
        selected_request = st.selectbox(
            "Select dummy request",
            [r["request_id"] for r in DEMO_APPROVAL_REQUESTS],
            key="qoc_demo_request_id",
        )
        approve, reject = st.columns(2)
        choice = None
        if approve.button("Simulate Approve — no real permission", key="qoc_demo_approve"):
            choice = "approve_preview"
        if reject.button("Simulate Reject — no real changes", key="qoc_demo_reject"):
            choice = "reject_preview"
        if choice:
            outcome = make_demo_decision(
                username=username, role=role,
                request_id=selected_request, decision=choice,
            )
            st.session_state["qoc_demo_last_decision"] = deepcopy(outcome)
        if "qoc_demo_last_decision" in st.session_state:
            st.json(st.session_state["qoc_demo_last_decision"])
        st.warning(
            "These buttons only preview a decision within this browser session. "
            "They do NOT grant AI/editor access or execute changes, and no email is sent."
        )


def render_curator_tasks(st: Any, username: str, role: str) -> None:
    """Future curator experience: read-only demo and no active permissions."""
    if not authorized_for_tasks(username, role):
        st.error("Access denied: curation tasks require a permitted curator identity.")
        return
    st.title("My Curation Tasks")
    st.warning(
        "PROTOTYPE / DEMO DATA ONLY. The editor account has NOT been activated or "
        "granted write access. Task requests and notifications are not connected."
    )
    owner_preview = owner_allowed(username, role)
    assigned = curator_tasks(username, role, owner_preview=owner_preview)
    st.dataframe(_issue_rows(assigned), use_container_width=True, hide_index=True)
    if assigned:
        selected = st.selectbox(
            "Inspect assigned demo task",
            [issue["issue_id"] for issue in assigned],
            key="qoc_demo_curator_task",
        )
        detail = next(item for item in assigned if item["issue_id"] == selected)
        st.write(detail["recommended_action"])
        if st.button("Preview owner approval request (not sent)", key="qoc_demo_request_preview"):
            st.info(
                "Draft only: request permission to review " + selected +
                ". No request has been submitted, and no scientific record was changed."
            )
    st.caption(
        "After separately approved staging tests, this page can show real assignments; "
        "every write must have attribution, audit, owner notification and a reversible history."
    )
