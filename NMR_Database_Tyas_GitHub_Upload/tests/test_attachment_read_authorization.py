"""Actual attachment readers with isolated accounts/files and fake HTTPS only."""
import io
from pathlib import Path
import tempfile
import unittest
from urllib.parse import urlparse
from PIL import Image
from authorization_fixture import bind_authorization
from test_asset_reader_integration import reader_namespace, load


class AttachmentReadAuthorizationTests(unittest.TestCase):
    def fixture(self, role='viewer', authenticated=True):
        temp=tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        project=Path(temp.name).resolve()
        root=project/'data/structures';root.mkdir(parents=True)
        output=io.BytesIO();Image.new('RGB',(8,8),'white').save(output,format='PNG')
        path=root/'synthetic.png';path.write_bytes(output.getvalue())
        ns=reader_namespace(project)
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
