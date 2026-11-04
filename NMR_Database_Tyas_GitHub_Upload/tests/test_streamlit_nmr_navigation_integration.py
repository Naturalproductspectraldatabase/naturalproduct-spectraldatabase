"""Actual full-script NMR result navigation on disposable synthetic SQLite data.

AppTest covers Streamlit rerun/callback behavior; it is not browser acceptance.
All network calls are forbidden by the existing isolated login fixture.
"""
import importlib.util
from pathlib import Path
import sqlite3
from contextlib import closing
import unittest
import test_streamlit_login_integration as login_fixture


@unittest.skipUnless(importlib.util.find_spec('streamlit'), 'Streamlit not installed')
class NmrResultNavigationIntegration(unittest.TestCase):
    def create_app(self, editor=False):
        fixture = login_fixture.StreamlitLoginIntegrationTests()
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        if editor:
            fixture.configure_multi_role_login()
            username, password = 'npdb_tjomori', 'test-mentor-only'
        else:
            fixture.configure_login()
            username, password = 'synthetic_viewer', 'synthetic-test-password'
        app = fixture.app
        app.run()
        app.text_input[0].input(username)
        app.text_input[1].input(password)
        app.button[0].click().run()
        self.assertEqual(len(app.exception), 0)
        database = Path(fixture.temp.name) / 'database/nmr.db'
        with closing(sqlite3.connect(database)) as conn:
            conn.execute("INSERT INTO compounds (id,trivial_name,curation_status,compound_class,source_category) VALUES (99001,'SYNTHETIC-NMR-NAV','imported','Synthetic','Synthetic')")
            conn.execute("INSERT INTO carbon_nmr (compound_id,delta_ppm,assignment) VALUES (99001,10,'C-test')")
            conn.execute("INSERT INTO proton_nmr (compound_id,delta_ppm,assignment) VALUES (99001,1,'H-test')")
            conn.commit()
        app.session_state['nav_section'] = 'Search & Match'
        app.session_state['_pending_main_section_radio'] = 'Search & Match'
        app.run()
        return app

    def submit(self, app, mode):
        next(w for w in app.radio if w.label == 'Search Mode').set_value(mode).run()
        for w in app.text_area:
            if 'Enter 13C peaks' in w.label:
                w.input('10')
            elif 'Enter 1H peaks' in w.label:
                w.input('1')
        label = {'13C Match':'Run 13C Match','1H Match':'Run 1H Match','Combined Match':'Run Combined Match'}[mode]
        next(b for b in app.button if b.label == label).click().run()
        self.assertEqual(len(app.exception), 0)
        self.assertTrue(any(b.label == 'Open Record #1' for b in app.button))

    def test_all_nmr_modes_open_synthetic_record_after_submit_rerun(self):
        for mode in ('13C Match','1H Match','Combined Match'):
            with self.subTest(mode=mode):
                app = self.create_app()
                self.submit(app, mode)
                next(b for b in app.button if b.label == 'Open Record #1').click().run()
                self.assertEqual(len(app.exception), 0)
                self.assertEqual(app.session_state['selected_compound_id'], 99001)
                self.assertEqual(app.session_state['nav_section'], 'Compound Workspace')
                self.assertTrue(any('SYNTHETIC-NMR-NAV' in t.value for t in app.markdown))

    def test_editor_update_metadata_action_survives_submit_rerun(self):
        app = self.create_app(editor=True)
        self.submit(app, '13C Match')
        next(b for b in app.button if b.label == 'Update Metadata #1').click().run()
        self.assertEqual(len(app.exception), 0)
        self.assertEqual(app.session_state['selected_compound_id'], 99001)
        self.assertEqual(app.session_state['compound_page'], 'Update Metadata')

    def test_viewer_has_no_edit_action_and_new_session_has_no_selection(self):
        app = self.create_app()
        self.submit(app, '13C Match')
        self.assertFalse(any(b.label == 'Update Metadata #1' for b in app.button))
        self.assertTrue(next(b for b in app.button if b.label == 'View Only #1').disabled)
        next(b for b in app.button if b.label == 'Open Record #1').click().run()
        other = self.create_app()
        self.assertIsNone(other.session_state['selected_compound_id'])
        self.assertEqual(other.session_state['nav_section'], 'Search & Match')

    def test_revoked_session_cannot_open_record_through_saved_result_action(self):
        app = self.create_app()
        self.submit(app, '13C Match')
        button = next(b for b in app.button if b.label == 'Open Record #1')
        app.secrets['NPDB_ACCESS_PASSWORD_HASH'] = 'pbkdf2_sha256$10000$rotated$synthetic'
        button.click().run()
        self.assertEqual(len(app.exception), 0)
        self.assertFalse(app.session_state['npdb_authenticated'])
        self.assertEqual([w.label for w in app.text_input], ['Username','Password'])
        self.assertFalse(any('SYNTHETIC-NMR-NAV' in t.value for t in app.markdown))
