"""Offline tests for in-memory-only NPDB owner approval/outbox prototype.

No real accounts, database, email, network, file writes or secrets used.
Run from checkout:
python -m unittest discover -s NMR_Database_Tyas_GitHub_Upload/tests -p 'test_approval_demo_store.py' -v
"""
import importlib.util
from pathlib import Path
import sqlite3
import unittest

MODULE_PATH = Path(__file__).resolve().parents[1] / "scripts" / "npdb_approval_demo_store.py"
spec = importlib.util.spec_from_file_location("npdb_approval_demo_store", MODULE_PATH)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


class ApprovalDemoStoreTests(unittest.TestCase):
    def setUp(self):
        self.db = mod.create_demo_store()
        self.issue = mod.seed_demo_record(self.db, "DEMO-RECORD-01")

    def tearDown(self):
        self.db.close()

    def propose(self, now=100):
        return mod.propose_demo_edit(
            self.db, mod.CURATOR, "editor", self.issue,
            "NEW-DUMMY-VALUE", now=now,
        )

    def test_store_is_disposable_memory_only(self):
        dbs = self.db.execute("PRAGMA database_list").fetchall()
        self.assertEqual(len(dbs), 1)
        self.assertEqual(dbs[0]["file"], "")

    def test_rejects_non_demo_record_ids(self):
        with self.assertRaises(ValueError):
            mod.seed_demo_record(self.db, "1")
        with self.assertRaises(ValueError):
            mod.seed_demo_record(self.db, "compound_1")

    def test_curator_sees_only_own_issues(self):
        own = mod.my_demo_tasks(self.db, mod.CURATOR, "editor")
        self.assertEqual(len(own), 1)
        self.assertEqual(own[0]["record_id"], "DEMO-RECORD-01")

    def test_viewer_cannot_access_editor_queue(self):
        with self.assertRaises(PermissionError):
            mod.my_demo_tasks(self.db, "public", "viewer")

    def test_curator_cannot_read_owner_notifications(self):
        with self.assertRaises(PermissionError):
            mod.owner_demo_notifications(self.db, mod.CURATOR, "editor")

    def test_proposal_not_a_data_change_and_creates_owner_notice(self):
        req = self.propose()
        row = self.db.execute(
            "SELECT value,version FROM demo_records WHERE record_id='DEMO-RECORD-01'"
        ).fetchone()
        self.assertEqual((row["value"], row["version"]), ("TEST-OLD", 1))
        self.assertEqual(len(mod.owner_demo_notifications(self.db, mod.OWNER, "owner")), 1)
        self.assertTrue(req.startswith("DEMO-REQUEST-"))

    def test_editor_cannot_approve_own_request(self):
        req = self.propose()
        with self.assertRaises(PermissionError):
            mod.owner_decide_demo(self.db, mod.CURATOR, "editor", req, True, now=120)

    def test_owner_approval_does_not_automatically_edit_any_record(self):
        req = self.propose()
        self.assertEqual(
            mod.owner_decide_demo(self.db, mod.OWNER, "owner", req, True, now=120),
            "approved",
        )
        row = self.db.execute("SELECT value FROM demo_records").fetchone()
        self.assertEqual(row["value"], "TEST-OLD")
        self.assertEqual(self.db.execute("SELECT count(*) FROM notification_outbox").fetchone()[0], 0)

    def test_rejected_request_never_executes(self):
        req = self.propose()
        mod.owner_decide_demo(self.db, mod.OWNER, "owner", req, False, now=120)
        with self.assertRaises(PermissionError):
            mod.execute_approved_demo(self.db, mod.CURATOR, "editor", req, now=130)

    def test_expiry_blocks_approval_and_execution(self):
        req = self.propose()
        with self.assertRaises(ValueError):
            mod.owner_decide_demo(self.db, mod.OWNER, "owner", req, True, now=1000)
        self.assertEqual(
            self.db.execute("SELECT status FROM approval_requests").fetchone()["status"],
            "pending",
        )
        self.assertEqual(self.db.execute("SELECT value FROM demo_records").fetchone()["value"], "TEST-OLD")

    def test_successful_owner_approval_then_explicit_demo_execution(self):
        req = self.propose()
        mod.owner_decide_demo(self.db, mod.OWNER, "owner", req, True, now=120)
        self.assertEqual(
            mod.execute_approved_demo(self.db, mod.CURATOR, "editor", req, now=130),
            "committed_demo",
        )
        row = self.db.execute("SELECT value,version FROM demo_records").fetchone()
        self.assertEqual((row["value"], row["version"]), ("NEW-DUMMY-VALUE", 2))
        outbox = self.db.execute("SELECT * FROM notification_outbox").fetchall()
        self.assertEqual(len(outbox), 1)
        self.assertEqual(outbox[0]["channel"], "demo-email-NOT-SENT")
        self.assertEqual(outbox[0]["delivery_status"], "pending")

    def test_replay_cannot_execute_approved_demo_twice(self):
        req = self.propose()
        mod.owner_decide_demo(self.db, mod.OWNER, "owner", req, True, now=120)
        mod.execute_approved_demo(self.db, mod.CURATOR, "editor", req, now=130)
        with self.assertRaises(PermissionError):
            mod.execute_approved_demo(self.db, mod.CURATOR, "editor", req, now=140)
        self.assertEqual(self.db.execute("SELECT count(*) FROM notification_outbox").fetchone()[0], 1)

    def test_conflicting_revision_rolls_back_audit_and_does_not_alert_success(self):
        req = self.propose()
        mod.owner_decide_demo(self.db, mod.OWNER, "owner", req, True, now=120)
        self.db.execute(
            "UPDATE demo_records SET value='OTHER-EDITOR',version=version+1 "
            "WHERE record_id='DEMO-RECORD-01'"
        )
        before = self.db.execute("SELECT count(*) FROM audit_events").fetchone()[0]
        with self.assertRaisesRegex(RuntimeError, "competing editor"):
            mod.execute_approved_demo(self.db, mod.CURATOR, "editor", req, now=130)
        after = self.db.execute("SELECT count(*) FROM audit_events").fetchone()[0]
        self.assertEqual(before, after)
        self.assertEqual(self.db.execute("SELECT count(*) FROM notification_outbox").fetchone()[0], 0)

    def test_tampered_proposal_is_rejected_without_write(self):
        req = self.propose()
        mod.owner_decide_demo(self.db, mod.OWNER, "owner", req, True, now=120)
        self.db.execute(
            "UPDATE approval_requests SET proposed_value='TAMPERED' WHERE request_id=?", (req,)
        )
        with self.assertRaisesRegex(PermissionError, "content has changed"):
            mod.execute_approved_demo(self.db, mod.CURATOR, "editor", req, now=130)
        self.assertEqual(self.db.execute("SELECT value FROM demo_records").fetchone()["value"], "TEST-OLD")

    def test_append_only_audit_rows_reject_updates_and_deletes(self):
        self.propose()
        with self.assertRaises(sqlite3.IntegrityError):
            self.db.execute("DELETE FROM audit_events")
        with self.assertRaises(sqlite3.IntegrityError):
            self.db.execute("UPDATE audit_events SET outcome='tampered'")

    def test_owner_notification_isolation(self):
        self.propose()
        owner = mod.owner_demo_notifications(self.db, mod.OWNER, "owner")
        self.assertEqual(len(owner), 1)
        self.assertIn("owner review", owner[0]["message"])
        with self.assertRaises(PermissionError):
            mod.owner_demo_notifications(self.db, "guest", "admin")


if __name__ == "__main__":
    unittest.main()
