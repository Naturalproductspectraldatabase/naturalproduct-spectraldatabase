"""Actual attachment readers with isolated accounts/files and fake HTTPS only."""
import io
import hashlib
from dataclasses import asdict

from pathlib import Path
import tempfile
import unittest
from urllib.parse import urlparse
from PIL import Image
from authorization_fixture import bind_authorization
from test_asset_reader_integration import reader_namespace, load
from npdb_location_policy import Evidence, value_digest, PUBLISHED_VERIFIED


class AttachmentReadAuthorizationTests(unittest.TestCase):
    def fixture(self, role='viewer', authenticated=True):
        temp=tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        project=Path(temp.name).resolve()
        root=project/'data/structures';root.mkdir(parents=True)
        output=io.BytesIO();Image.new('RGB',(8,8),'white').save(output,format='PNG')
        path=root/'synthetic.png';path.write_bytes(output.getvalue())
        ns=reader_namespace(project)
        # Explicit synthetic owner review, not publication inferred from the path.
        raw={1:dict(id=1,updated_at='synthetic-r1',structure_image_path=str(path)),
             2:dict(id=2,updated_at='synthetic-r1',structure_image_path='https://synthetic.invalid/x.png')}
        facts=[asdict(Evidence(table='compounds',record_id=str(rid),field='structure_image_path',
            record_revision='synthetic-r1',value_sha256=value_digest(row['structure_image_path']),
            classification=PUBLISHED_VERIFIED,verification_status='VERIFIED',source_reference='Synthetic fixture source',
            source_locator='Synthetic figure',verified_by='Synthetic owner',verifier_role='owner',asset_sha256=hashlib.sha256(output.getvalue()).hexdigest())) for rid,row in raw.items()]
        ns['get_secret_object']=lambda *a:dict(version=1,entries=facts)
        ns['field_policy_raw_record']=lambda table,rid,**kw:raw[int(rid)]

        auth=bind_authorization(role=role,authenticated=authenticated)
        ns['require_backend_permission']=auth['require_backend_permission']
        calls=[]
        def display(source):calls.append('display');return 'https://synthetic.invalid/x.png'
        def remote(*args,**kw):calls.append('fetch');return output.getvalue()
        ns.update(urlparse=urlparse,display_asset_url=display,read_https_asset=remote,
                  get_supabase_url=lambda:'https://synthetic.invalid')
        load(ns,'read_remote_scientific_asset')
        return ns,auth,path,output.getvalue(),calls

    def test_authorized_owner_editor_viewer_can_read_original_bytes(self):
        for role in ('owner','editor','viewer'):
            ns,auth,path,data,calls=self.fixture(role)
            self.assertEqual(ns['read_scientific_asset'](path,'structure'),data)
            self.assertEqual(ns['_asset_bytes_from_source'](str(path),'structure')[0],data)
            self.assertEqual(ns['read_remote_scientific_asset']('https://synthetic.invalid/x.png')[0],data)

    def test_unreviewed_attachment_denied_for_editor_and_viewer_before_io(self):
        from npdb_asset_paths import AssetAccessError
        for role in ('editor','viewer'):
            ns,auth,path,data,calls=self.fixture(role)
            ns['get_secret_object']=lambda *a:None
            ns['read_local_asset']=lambda *a,**k:self.fail('unreviewed bytes opened')
            with self.assertRaises(AssetAccessError):ns['read_scientific_asset'](path,'structure')

    def test_anonymous_read_refused_before_local_open_or_remote_resolution(self):
        ns,auth,path,data,calls=self.fixture(authenticated=False)
        ns['read_local_asset']=lambda *a,**kw:self.fail('local reader reached')
        for name,args in [('read_scientific_asset',(path,'structure')),
                          ('read_remote_scientific_asset',('https://synthetic.invalid/x.png',)),
                          ('_asset_bytes_from_source',(str(path),'structure'))]:
            with self.subTest(name=name),self.assertRaises(PermissionError):ns[name](*args)
        self.assertEqual(calls,[])

    def test_revoked_or_rotated_account_cannot_read_registered_attachment(self):
        for change in ('revoke','rotate','promote'):
            ns,auth,path,data,calls=self.fixture('editor')
            if change=='revoke':auth['load_approved_users']=lambda:[]
            elif change=='rotate':auth['load_approved_users']()[0]['password_hash']='changed-synthetic'
            else:auth['st'].session_state['npdb_role']='owner'
            with self.subTest(change=change),self.assertRaises(PermissionError):
                ns['_asset_bytes_from_source'](str(path),'structure')
            self.assertEqual(calls,[])

    def test_compatibility_locator_is_not_a_reusable_read_capability(self):
        ns,auth,path,data,calls=self.fixture('owner')
        locator=ns['get_full_file_path'](str(path))
        self.assertEqual(locator,path)
        auth['load_approved_users']=lambda:[]
        self.assertFalse(ns['local_asset_available'](str(path)))
        self.assertIsNone(ns['get_full_file_path'](str(path)))
        with self.assertRaises(PermissionError):ns['read_scientific_asset'](locator,'structure')
        with self.assertRaises(PermissionError):ns['_asset_bytes_from_source'](str(locator),'structure')

    def test_cross_session_revalidation_and_preview_denial(self):
        import types
        owner,auth,path,data,calls=self.fixture('owner')
        outputs=[]
        owner['st']=types.SimpleNamespace(image=lambda image,**kw:outputs.append(image),
             warning=lambda text:None,info=lambda text:None)
        owner['render_registered_file_preview'](str(path),kind='structure')
        self.assertEqual(outputs,[data])
        auth['st'].session_state['npdb_authenticated']=False
        owner['render_registered_file_preview'](str(path),kind='structure')
        self.assertEqual(outputs,[data])
        # Fresh authorized viewer can read the same public-within-workspace asset;
        # the revoked owner's namespace must not inherit that identity.
        viewer=bind_authorization(role='viewer')
        read_context=dict(owner,require_backend_permission=viewer['require_backend_permission'])
        load(read_context,'read_scientific_asset')
        self.assertEqual(read_context['read_scientific_asset'](path,'structure'),data)
        with self.assertRaises(PermissionError):owner['read_scientific_asset'](path,'structure')

    def test_raw_locator_callers_are_presence_checks_only(self):
        import ast
        from test_asset_reader_integration import APP
        tree=ast.parse(APP.read_text())
        callers=[]
        for node in tree.body:
            if isinstance(node,ast.FunctionDef):
                for call in ast.walk(node):
                    if isinstance(call,ast.Call) and isinstance(call.func,ast.Name) and call.func.id=='get_full_file_path':
                        callers.append(node.name)
        self.assertEqual(callers,['validate_spectrum_entry'])
        for name in ('load_standardized_structure_image','render_registered_file_preview','_render_specimen_image','_asset_bytes_from_source'):
            node=[n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name==name][-1]
            source=ast.get_source_segment(APP.read_text(),node)
            self.assertNotIn('.read_bytes()',source)
            self.assertNotIn('open(full_path',source)
            self.assertNotIn('st.image(str(full_path)',source)
