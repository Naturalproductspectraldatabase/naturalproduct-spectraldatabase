"""Non-production tests for NPDB Quality & Operations Center mock-only workflows.

Run on a full checkout:
  python -m unittest discover -s NMR_Database_Tyas_GitHub_Upload/tests -p 'test_quality_center.py' -v

No Streamlit app startup, no Supabase connection and no real data.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path
import unittest


MODULE_PATH = Path(__file__).resolve().parents[1] / "scripts" / "npdb_quality_center.py"
spec = importlib.util.spec_from_file_location("npdb_quality_center_test_only", MODULE_PATH)
center = importlib.util.module_from_spec(spec)
spec.loader.exec_module(center)


class FakeStreamlit:
    """Only the UI methods needed by the dummy owner/curator experience."""

    def __init__(self, click: str = ""):
        self.session_state = {}
        self.click = click
        self.errors = []
        self.warnings = []
        self.frames = []
        self.messages = []

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def title(self, value):
        self.messages.append(value)

    def subheader(self, value):
        self.messages.append(value)

    def markdown(self, value):
        self.messages.append(value)

    def warning(self, value):
        self.warnings.append(value)

    def error(self, value):
        self.errors.append(value)

    def info(self, value):
        self.messages.append(value)

    def caption(self, value):
        self.messages.append(value)

    def write(self, value):
        self.messages.append(value)

    def dataframe(self, values, **kwargs):
        self.frames.append(values)

    def metric(self, label, value):
        self.messages.append((label, value))

    def columns(self, number):
        return [self] * number

    def tabs(self, names):
        return [self] * len(names)

    def selectbox(self, label, options, **kwargs):
        return options[0]

    def button(self, label, key=None):
        return key == self.click

    def json(self, value):
        self.messages.append(value)


class QualityCenterPermissionTests(unittest.TestCase):
    def test_owner_requires_both_exact_identity_and_owner_role(self):
        self.assertTrue(center.owner_allowed(" NPDB_TYAS ", "OWNER"))
        for username, role in [
            ("npdb_tjomori", "owner"), ("npdb_tyas", "viewer"),
            ("npdb_tyas", "editor"), ("guest", "admin"), ("", "owner"),
        ]:
            self.assertFalse(center.owner_allowed(username, role), (username, role))

    def test_curator_requires_designated_editor_account(self):
        self.assertTrue(center.curator_allowed("npdb_tjomori", "editor"))
        for username, role in [
            ("npdb_tjomori", "viewer"), ("npdb_tjomori", "owner"),
            ("npdb_tyas", "editor"), ("guest", "editor"),
        ]:
            self.assertFalse(center.curator_allowed(username, role))

    def test_viewer_cannot_see_curator_tasks(self):
        self.assertEqual(center.curator_tasks("guest", "viewer"), [])
        self.assertFalse(center.authorized_for_tasks("guest", "viewer"))

    def test_curator_sees_only_explicitly_assigned_dummy_tasks(self):
        result = center.curator_tasks("npdb_tjomori", "editor")
        self.assertGreater(len(result), 0)
        self.assertTrue(all(item["assignee"] == "npdb_tjomori" for item in result))
        self.assertTrue(all(item["record"].startswith("DEMO-") for item in result))

    def test_owner_preview_requires_explicit_option(self):
        self.assertEqual(center.curator_tasks("npdb_tyas", "owner"), [])
        self.assertGreater(len(center.curator_tasks("npdb_tyas", "owner", owner_preview=True)), 0)

    def test_quality_center_url_bypass_returns_only_access_denied(self):
        fake = FakeStreamlit()
        center.render_owner_quality_center(fake, "guest", "viewer")
        self.assertEqual(len(fake.errors), 1)
        self.assertEqual(fake.frames, [])
        self.assertEqual(fake.messages, [])

    def test_editor_cannot_open_owner_quality_center(self):
        fake = FakeStreamlit()
        center.render_owner_quality_center(fake, "npdb_tjomori", "editor")
        self.assertEqual(len(fake.errors), 1)
        self.assertEqual(fake.frames, [])

    def test_owner_and_curator_demo_pages_show_explicit_demo_warnings(self):
        owner = FakeStreamlit()
        center.render_owner_quality_center(owner, "npdb_tyas", "owner")
        curator = FakeStreamlit()
        center.render_curator_tasks(curator, "npdb_tjomori", "editor")
        self.assertTrue(any("DEMO DATA ONLY" in w for w in owner.warnings))
        self.assertTrue(any("DEMO DATA ONLY" in w for w in curator.warnings))
        self.assertGreater(len(owner.frames), 0)
        self.assertGreater(len(curator.frames), 0)


class QualityCenterDataTests(unittest.TestCase):
    def test_issue_counts_and_priorities(self):
        result = center.summarize_issues(center.DEMO_ISSUES)
        self.assertEqual(result, {"open_active": 6, "P0": 2, "P1": 2, "P2": 1, "P3": 1})

    def test_sorting_preserves_priority_and_stable_issue_id(self):
        issues = center.filter_issues(center.DEMO_ISSUES)
        self.assertEqual([issue["severity"] for issue in issues], ["P0", "P0", "P1", "P1", "P2", "P3"])
        self.assertEqual(issues[0]["issue_id"], "DEMO-001")

    def test_filter_severity_category_and_status(self):
        a = center.filter_issues(center.DEMO_ISSUES, severity="P1")
        self.assertEqual(len(a), 2)
        b = center.filter_issues(center.DEMO_ISSUES, category="Images & files", status="in_review")
        self.assertEqual([item["issue_id"] for item in b], ["DEMO-003"])

    def test_source_is_not_mutated_by_filtering(self):
        before = center.DEMO_ISSUES[0]["title"]
        matches = center.filter_issues(center.DEMO_ISSUES)
        matches[0]["title"] = "changed by test only"
        self.assertEqual(center.DEMO_ISSUES[0]["title"], before)

    def test_resolved_and_false_positive_issues_excluded_from_open_counts(self):
        demo = list(center.DEMO_ISSUES)
        demo.append({"severity": "P0", "status": "resolved"})
        demo.append({"severity": "P1", "status": "false_positive"})
        self.assertEqual(center.summarize_issues(demo), center.summarize_issues(center.DEMO_ISSUES))

    def test_all_fixture_resource_ids_are_explicitly_synthetic(self):
        self.assertTrue(all(i["record"].startswith("DEMO-") for i in center.DEMO_ISSUES))
        self.assertTrue(all(i["issue_id"].startswith("DEMO-") for i in center.DEMO_ISSUES))


class QualityCenterApprovalTests(unittest.TestCase):
    def test_owner_simulation_returns_no_real_permission(self):
        result = center.make_demo_decision(
            username="npdb_tyas", role="owner",
            request_id="DEMO-A001", decision="approve_preview",
        )
        self.assertEqual(result["decision"], "DEMO_APPROVAL_ONLY")
        self.assertEqual(result["effective_permission"], "NONE")
        self.assertEqual(result["persistence"], "session_state_only")

    def test_reject_simulation_does_not_execute_anything(self):
        result = center.make_demo_decision(
            username="npdb_tyas", role="owner",
            request_id="DEMO-A001", decision="reject_preview",
        )
        self.assertEqual(result["decision"], "DEMO_REJECTION_ONLY")
        self.assertEqual(result["effective_permission"], "NONE")

    def test_unauthorized_editor_cannot_simulate_owner_approval(self):
        with self.assertRaises(PermissionError):
            center.make_demo_decision(
                username="npdb_tjomori", role="editor",
                request_id="DEMO-A001", decision="approve_preview",
            )

    def test_invalid_request_or_decision_is_rejected(self):
        with self.assertRaises(ValueError):
            center.make_demo_decision(
                username="npdb_tyas", role="owner",
                request_id="DEMO-DOES-NOT-EXIST", decision="approve_preview",
            )
        with self.assertRaises(ValueError):
            center.make_demo_decision(
                username="npdb_tyas", role="owner",
                request_id="DEMO-A001", decision="execute",
            )

    def test_owner_approve_button_only_modifies_ephemeral_demo_session(self):
        fake = FakeStreamlit(click="qoc_demo_approve")
        center.render_owner_quality_center(fake, "npdb_tyas", "owner")
        result = fake.session_state["qoc_demo_last_decision"]
        self.assertEqual(result["effective_permission"], "NONE")
        self.assertEqual(result["persistence"], "session_state_only")

    def test_curator_preview_does_not_submit_a_request(self):
        fake = FakeStreamlit(click="qoc_demo_request_preview")
        center.render_curator_tasks(fake, "npdb_tjomori", "editor")
        self.assertTrue(any("No request has been submitted" in str(x) for x in fake.messages))
        self.assertEqual(fake.session_state, {})


class QualityCenterRoutingTests(unittest.TestCase):
    """Code-level guards; staging UI tests are still required."""

    def app_source(self):
        return (MODULE_PATH.parent / "app.py").read_text(encoding="utf-8")

    def test_navigation_is_separately_restricted_for_owner_and_curator(self):
        source = self.app_source()
        self.assertIn('group_title == "Owner Workspace" and not is_owner_editor()', source)
        self.assertIn('group_title == "Curator Workspace"', source)
        self.assertIn('from npdb_quality_center import authorized_for_tasks', source)

    def test_direct_link_routing_has_its_own_owner_guard(self):
        source = self.app_source()
        route_start = source.rfind('if main_section == "Quality & Operations Center":')
        self.assertGreater(route_start, 0)
        block = source[route_start:route_start + 550]
        self.assertIn("if not is_owner_editor():", block)
        self.assertIn("render_owner_quality_center(", block)

    def test_direct_link_routing_has_its_own_curator_guard(self):
        source = self.app_source()
        route_start = source.rfind('elif main_section == "My Curation Tasks":')
        self.assertGreater(route_start, 0)
        block = source[route_start:route_start + 750]
        self.assertIn("if not authorized_for_tasks(", block)
        self.assertIn("render_curator_tasks(", block)

    def test_demo_sections_skip_bulk_compound_load_and_live_scan_retry(self):
        source = self.app_source()
        self.assertIn('if section in QUALITY_DEMO_SECTIONS:', source)
        self.assertIn('return pd.DataFrame()', source)
        self.assertIn('if not quality_demo_page:\n    render_cloud_sync_notice()', source)

    def test_prototype_module_exposes_no_sql_or_real_email_transport(self):
        source = MODULE_PATH.read_text(encoding="utf-8")
        for unsafe in (
            "supabase_insert_row(", "supabase_update_row(", "supabase_delete_row(",
            "smtplib.SMTP(", "requests.post(", "httpx.post(",
            "execute_sql(", "send_email(", "storage.objects",
        ):
            self.assertNotIn(unsafe, source)



if __name__ == "__main__":
    unittest.main()
