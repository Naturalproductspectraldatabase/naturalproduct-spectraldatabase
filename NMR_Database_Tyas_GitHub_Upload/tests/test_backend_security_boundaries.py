"""Synthetic permissions at actual REST, SQLite, upload, signing and admin sinks."""
import ast
import io
from pathlib import Path
import sqlite3
import tempfile
import types
import unittest
from urllib.parse import quote, unquote, urlencode, urlparse
from authorization_fixture import bind_authorization, APP


def load(ns, *names):
    tree = ast.parse(APP.read_text())
    for name in names:
        node = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == name][-1]
        node.decorator_list = []
        exec(compile(ast.Module(body=[node], type_ignores=[]), str(APP), 'exec'), ns)


class BackendSecurityBoundaryTests(unittest.TestCase):
    def fixture(self, role='editor'):
        ns = bind_authorization(role=role)
        ns.update(quote=quote, unquote=unquote, urlencode=urlencode, urlparse=urlparse,
                  AUDIT_EVENTS_TABLE='audit_events', Path=Path,
                  maybe_blank=lambda v: str(v or '').strip(),
                  use_supabase_write_backend=lambda: True,
                  get_supabase_url=lambda: 'https://synthetic.invalid',
                  _json_ready=lambda v:v, is_duplicate_primary_key_error=lambda e: False,
                  record_audit_event=lambda *a, **k: None,
                  cloud_backend_is_configured=lambda: False,
                  use_supabase_backend=lambda: True)
        load(ns, 'validate_storage_asset_reference')
        return ns

    def test_revocation_role_change_password_rotation_and_missing_proof(self):
        for alteration in ('revoke', 'role', 'password', 'proof', 'username'):
            ns = self.fixture()
            if alteration == 'revoke': ns['load_approved_users'] = lambda: []
            elif alteration == 'proof': ns['st'].session_state.pop('npdb_credential_revision')
            elif alteration == 'username': ns['st'].session_state['npdb_username'] = 'SYNTHETIC_EDITOR'
            else:
                users = ns['load_approved_users']()
                users[0]['role' if alteration == 'role' else 'password_hash'] = 'changed'
            with self.subTest(alteration=alteration), self.assertRaises(PermissionError):
                ns['require_backend_permission']('curate')

    def test_editor_cannot_approve_manage_accounts_or_write_unknown_tables(self):
        ns = self.fixture()
        for action, table, row in [('approve', None, None), ('admin', None, None),
                                  ('curate', 'accounts', {}), ('curate', 'compounds; DROP TABLE x', {}),
                                  ('curate', 'compounds', {'curation_status': 'curated'}),
                                  ('curate', 'compounds', {'curation_status': 'reviewed'})]:
            with self.subTest(action=action, table=table), self.assertRaises(PermissionError):
                ns['require_backend_permission'](action, table, row)
        ns['require_backend_permission']('curate', 'compounds', {'curation_status': 'imported'})

    def test_sqlite_guards_run_before_connection_for_viewer_and_editor_delete(self):
        for role, name, args in [('viewer', '_sqlite_upsert_row', ('compounds', {'note':'test'})),
                                 ('viewer', '_write_child_row', ('proton_nmr', {})),
                                 ('editor', '_sqlite_delete_row', ('compounds', 1))]:
            ns = self.fixture(role)
            ns['get_connection'] = lambda: self.fail('unauthorized SQLite connection')
            load(ns, name)
            with self.subTest(role=role, name=name), self.assertRaises(PermissionError):
                ns[name](*args)

    def test_owner_and_editor_synthetic_sqlite_curate_owner_only_delete(self):
        with tempfile.TemporaryDirectory() as directory:
            db = Path(directory)/'synthetic.db'
            with sqlite3.connect(db) as conn:
                conn.execute('CREATE TABLE compounds (id INTEGER PRIMARY KEY, note TEXT)')
            for role in ('editor', 'owner'):
                ns = self.fixture(role)
                ns['get_connection'] = lambda: sqlite3.connect(db)
                ns['_sqlite_columns'] = lambda table: ['id', 'note']
                ns['use_supabase_write_backend'] = lambda: False
                load(ns, '_sqlite_upsert_row', '_sqlite_delete_row')
                row_id = ns['_sqlite_upsert_row']('compounds', {'note':'synthetic'})
                ns['_sqlite_upsert_row']('compounds', {'id':row_id, 'note':'changed'})
                if role == 'editor':
                    with self.assertRaises(PermissionError): ns['_sqlite_delete_row']('compounds',row_id)
                else: ns['_sqlite_delete_row']('compounds',row_id)

    def test_upload_and_backup_and_link_replacement_block_before_work(self):
        for role in ('viewer', 'editor'):
            ns = self.fixture(role)
            load(ns, 'save_uploaded_asset', '_save_generated_structure_image', 'get_backup_bytes',
                 'build_backup_bundle_bytes', 'replace_specimen_compound_links')
            cases = [('get_backup_bytes', ()), ('build_backup_bundle_bytes', ()),
                     ('replace_specimen_compound_links', (1, []))]
            if role == 'viewer': cases += [('save_uploaded_asset', (None, None, 'test')),
                                           ('_save_generated_structure_image', (1, None))]
            for name, args in cases:
                with self.subTest(role=role, name=name), self.assertRaises(PermissionError): ns[name](*args)

    def test_signing_requires_current_identity_and_private_bucket_scope(self):
        ns = self.fixture('viewer')
        calls = []
        ns['_supabase_request'] = lambda *a, **k: calls.append((a,k)) or {'signedURL':'/object/sign/structures/test.png?token=synthetic'}
        load(ns, 'signed_supabase_storage_url')
        url = ns['signed_supabase_storage_url']('structures', 'test.png')
        self.assertIn('/object/sign/', url)
        self.assertEqual(calls[0][1]['body']['expiresIn'], 300)
        with self.assertRaises(PermissionError): ns['signed_supabase_storage_url']('backups', 'private.zip')
        ns['load_approved_users'] = lambda: []
        with self.assertRaises(PermissionError): ns['signed_supabase_storage_url']('structures', 'test.png')
        self.assertEqual(len(calls),1)

    def test_storage_traversal_and_public_upload_rejected_before_transport(self):
        ns = self.fixture()
        ns['_supabase_request'] = lambda *a, **k: self.fail('invalid storage transport')
        load(ns, 'supabase_upload_bytes', 'signed_supabase_storage_url')
        for value in ('../backups/private.zip', '%2e%2e/private.zip', '/absolute', 'x\\private', 'x//private'):
            with self.subTest(value=value), self.assertRaises(PermissionError):
                ns['supabase_upload_bytes']('structures', value, b'synthetic')
        with self.assertRaises(PermissionError):
            ns['supabase_upload_bytes']('structures', 'test.png', b'synthetic', public_bucket=True)

    def test_raw_rest_dispatcher_cannot_bypass_roles_or_approval(self):
        for role, method, path, body in [('viewer','POST','/rest/v1/compounds',{'note':'test'}),
                 ('editor','DELETE','/rest/v1/compounds',None),
                 ('editor','PATCH','/rest/v1/compounds',{'curation_status':'curated'}),
                 ('editor','POST','/rest/v1/accounts',{}),
                 ('editor','POST','/rest/v1/compounds',[{'curation_status':'curated'}]),
                 ('editor','POST','/storage/v1/object/structures/../backups/x',b'x')]:
            ns=self.fixture(role)
            ns['urllib']=types.SimpleNamespace(request=types.SimpleNamespace(Request=lambda *a, **k:self.fail('transport reached')))
            load(ns, '_supabase_request')
            with self.subTest(role=role, path=path), self.assertRaises(PermissionError):
                ns['_supabase_request'](method,path,body=body,write=True)
