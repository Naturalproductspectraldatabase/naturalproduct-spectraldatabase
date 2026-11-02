"""NON-PRODUCTION SQLite in-memory prototype of owner approvals and audit.

THIS MODULE CANNOT CONNECT TO SUPABASE OR SEND EMAIL. It always opens
':memory:' and permits only DEMO- prefixed record IDs. Caller-supplied
usernames/roles are test fixtures, NOT real authentication claims. Never
deploy this as a production authorization service.
"""
from __future__ import annotations

import hashlib
import json
import sqlite3
import time
from typing import Any
from uuid import uuid4

OWNER = "npdb_tyas"
CURATOR = "npdb_tjomori"


def _require_owner(actor: str, role: str) -> None:
    if actor != OWNER or role not in ("owner", "owner_editor", "admin"):
        raise PermissionError("Owner approval required.")


def _require_curator(actor: str, role: str) -> None:
    if actor != CURATOR or role != "editor":
        raise PermissionError("Curator role required.")


def _demo_id(value: str) -> str:
    if not isinstance(value, str) or not value.startswith("DEMO-"):
        raise ValueError("Only synthetic DEMO- identifiers are supported.")
    return value


def _digest(value: dict[str, Any]) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
    ).hexdigest()


def create_demo_store() -> sqlite3.Connection:
    """A new private, disposable SQLite RAM database: never a filesystem path."""
    db = sqlite3.connect(":memory:", isolation_level=None)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA foreign_keys=ON")
    db.executescript("""
    CREATE TABLE demo_records (
        record_id TEXT PRIMARY KEY CHECK(record_id LIKE 'DEMO-%'),
        value TEXT NOT NULL,
        version INTEGER NOT NULL DEFAULT 1
    );
    CREATE TABLE demo_issues (
        issue_id TEXT PRIMARY KEY CHECK(issue_id LIKE 'DEMO-%'),
        record_id TEXT NOT NULL REFERENCES demo_records(record_id),
        assignee TEXT NOT NULL, severity TEXT NOT NULL, status TEXT NOT NULL
    );
    CREATE TABLE approval_requests (
        request_id TEXT PRIMARY KEY CHECK(request_id LIKE 'DEMO-%'),
        issue_id TEXT NOT NULL REFERENCES demo_issues(issue_id),
        record_id TEXT NOT NULL REFERENCES demo_records(record_id),
        proposed_value TEXT NOT NULL,
        proposed_hash TEXT NOT NULL,
        expected_version INTEGER NOT NULL,
        requester TEXT NOT NULL,
        status TEXT NOT NULL,
        expires_at INTEGER NOT NULL,
        reviewed_by TEXT,
        reviewed_at INTEGER,
        executed_at INTEGER
    );
    CREATE TABLE audit_events (
        event_id TEXT PRIMARY KEY,
        event_time INTEGER NOT NULL,
        actor TEXT NOT NULL,
        action TEXT NOT NULL,
        record_id TEXT,
        request_id TEXT,
        outcome TEXT NOT NULL
    );
    CREATE TRIGGER demo_audit_immutable_update
        BEFORE UPDATE ON audit_events BEGIN SELECT RAISE(ABORT,'audit update prohibited'); END;
    CREATE TRIGGER demo_audit_immutable_delete
        BEFORE DELETE ON audit_events BEGIN SELECT RAISE(ABORT,'audit delete prohibited'); END;
    CREATE TABLE owner_notifications (
        notification_id TEXT PRIMARY KEY,
        event_id TEXT NOT NULL UNIQUE REFERENCES audit_events(event_id),
        recipient TEXT NOT NULL,
        message TEXT NOT NULL,
        read_at INTEGER
    );
    CREATE TABLE notification_outbox (
        event_id TEXT PRIMARY KEY REFERENCES audit_events(event_id),
        channel TEXT NOT NULL,
        delivery_status TEXT NOT NULL DEFAULT 'pending',
        attempts INTEGER NOT NULL DEFAULT 0
    );
    """)
    return db


def seed_demo_record(
    db: sqlite3.Connection, record_id: str, *, value: str = "TEST-OLD",
    assignee: str = CURATOR, severity: str = "P1"
) -> str:
    """Only synthetic records and issue IDs are admitted."""
    _demo_id(record_id)
    issue_id = f"DEMO-ISSUE-{record_id[5:]}"
    db.execute("BEGIN IMMEDIATE")
    try:
        db.execute(
            "INSERT INTO demo_records(record_id,value) VALUES (?,?)",
            (record_id, value),
        )
        db.execute(
            "INSERT INTO demo_issues(issue_id,record_id,assignee,severity,status) "
            "VALUES (?,?,?,?,?)",
            (issue_id, record_id, assignee, severity, "open"),
        )
        db.commit()
    except BaseException:
        db.rollback()
        raise
    return issue_id


def _event(
    db: sqlite3.Connection, *, actor: str, action: str,
    record_id: str, request_id: str, outcome: str,
    message: str | None = None,
    owner_email_intent: bool = False,
    now: int,
) -> str:
    eid = f"DEMO-EVENT-{uuid4().hex}"
    db.execute(
        "INSERT INTO audit_events VALUES (?,?,?,?,?,?,?)",
        (eid, now, actor, action, record_id, request_id, outcome),
    )
    if message is not None:
        db.execute(
            "INSERT INTO owner_notifications VALUES (?,?,?,?,NULL)",
            (f"DEMO-NOTICE-{uuid4().hex}", eid, OWNER, message),
        )
    if owner_email_intent:
        # No dispatcher is implemented. This cannot send real email.
        db.execute(
            "INSERT INTO notification_outbox(event_id,channel,delivery_status,attempts) "
            "VALUES (?,?,?,0)",
            (eid, "demo-email-NOT-SENT", "pending"),
        )
    return eid


def my_demo_tasks(db: sqlite3.Connection, actor: str, role: str) -> list[dict[str, Any]]:
    _require_curator(actor, role)
    return [
        dict(x) for x in db.execute(
            "SELECT issue_id,record_id,severity,status FROM demo_issues "
            "WHERE assignee=? ORDER BY severity,issue_id", (actor,)
        ).fetchall()
    ]


def owner_demo_notifications(db: sqlite3.Connection, actor: str, role: str) -> list[dict[str, Any]]:
    _require_owner(actor, role)
    return [
        dict(x) for x in db.execute(
            "SELECT notification_id,message,read_at FROM owner_notifications "
            "WHERE recipient=? ORDER BY rowid DESC", (OWNER,)
        ).fetchall()
    ]


def propose_demo_edit(
    db: sqlite3.Connection, actor: str, role: str, issue_id: str,
    proposed_value: str, *, now: int | None = None, expiry_seconds: int = 600
) -> str:
    """Request owner approval; proposal NEVER alters the record."""
    _require_curator(actor, role)
    _demo_id(issue_id)
    if expiry_seconds <= 0 or expiry_seconds > 86400:
        raise ValueError("Invalid approval expiry interval.")
    ts = int(now if now is not None else time.time())
    row = db.execute(
        "SELECT i.record_id,r.version,i.status FROM demo_issues i "
        "JOIN demo_records r ON r.record_id=i.record_id "
        "WHERE i.issue_id=? AND i.assignee=?", (issue_id, actor)
    ).fetchone()
    if row is None or row["status"] not in ("open", "in_review"):
        raise PermissionError("Issue not assigned or unavailable.")
    request_id = f"DEMO-REQUEST-{uuid4().hex}"
    payload = {
        "record_id": row["record_id"], "proposed_value": proposed_value,
        "expected_version": row["version"], "requester": actor,
    }
    db.execute("BEGIN IMMEDIATE")
    try:
        db.execute(
            "INSERT INTO approval_requests "
            "(request_id,issue_id,record_id,proposed_value,proposed_hash,"
            "expected_version,requester,status,expires_at) VALUES (?,?,?,?,?,?,?,?,?)",
            (
                request_id, issue_id, row["record_id"], proposed_value,
                _digest(payload), row["version"], actor, "pending", ts + expiry_seconds,
            ),
        )
        _event(
            db, actor=actor, action="propose", record_id=row["record_id"],
            request_id=request_id, outcome="pending_owner_approval",
            message="A dummy curation proposal needs owner review.", now=ts,
        )
        db.commit()
    except BaseException:
        db.rollback()
        raise
    return request_id


def owner_decide_demo(
    db: sqlite3.Connection, actor: str, role: str, request_id: str,
    approve: bool, *, now: int | None = None,
) -> str:
    """Owner approves/rejects only the exact pending proposal, NO execution."""
    _require_owner(actor, role)
    _demo_id(request_id)
    ts = int(now if now is not None else time.time())
    db.execute("BEGIN IMMEDIATE")
    try:
        row = db.execute(
            "SELECT * FROM approval_requests WHERE request_id=?", (request_id,)
        ).fetchone()
        if row is None or row["status"] != "pending":
            raise ValueError("Request is missing or no longer pending.")
        if ts >= row["expires_at"]:
            raise ValueError("Approval request expired.")
        target = "approved" if approve else "rejected"
        db.execute(
            "UPDATE approval_requests SET status=?,reviewed_by=?,reviewed_at=? "
            "WHERE request_id=? AND status='pending'",
            (target, actor, ts, request_id),
        )
        _event(
            db, actor=actor, action="review", record_id=row["record_id"],
            request_id=request_id, outcome=target, now=ts,
        )
        db.commit()
        return target
    except BaseException:
        db.rollback()
        raise


def execute_approved_demo(
    db: sqlite3.Connection, actor: str, role: str, request_id: str,
    *, now: int | None = None,
) -> str:
    """A second, explicit operation: mutates ONLY synthetic RAM data.

    All approval, payload hash, expiry and optimistic-version checks happen
    inside one SQLite transaction. Successful commit queues a dummy owner
    notification and a dummy *unsent* email outbox entry.
    """
    _require_curator(actor, role)
    _demo_id(request_id)
    ts = int(now if now is not None else time.time())
    db.execute("BEGIN IMMEDIATE")
    try:
        row = db.execute(
            "SELECT * FROM approval_requests WHERE request_id=?", (request_id,)
        ).fetchone()
        if row is None or row["status"] != "approved" or row["requester"] != actor:
            raise PermissionError("No valid, unconsumed owner approval.")
        if ts >= row["expires_at"]:
            raise PermissionError("Owner approval expired.")
        payload = {
            "record_id": row["record_id"], "proposed_value": row["proposed_value"],
            "expected_version": row["expected_version"], "requester": row["requester"],
        }
        if _digest(payload) != row["proposed_hash"]:
            raise PermissionError("Proposal content has changed.")
        updated = db.execute(
            "UPDATE demo_records SET value=?,version=version+1 "
            "WHERE record_id=? AND version=?",
            (row["proposed_value"], row["record_id"], row["expected_version"]),
        )
        if updated.rowcount != 1:
            raise RuntimeError("Record was changed by a competing editor.")
        db.execute(
            "UPDATE approval_requests SET status='executed',executed_at=? "
            "WHERE request_id=? AND status='approved'",
            (ts, request_id),
        )
        _event(
            db, actor=actor, action="execute_demo_edit",
            record_id=row["record_id"], request_id=request_id,
            outcome="committed_demo", now=ts,
            message="A dummy editor change was committed after approval.",
            owner_email_intent=True,
        )
        db.commit()
        return "committed_demo"
    except BaseException:
        db.rollback()
        raise
