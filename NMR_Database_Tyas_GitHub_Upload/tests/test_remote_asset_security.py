"""Synthetic HTTPS/redirect/size policy, without DNS or network calls."""
import ast
import io
from pathlib import Path
import sys
import types
import unittest
from unittest.mock import patch
from urllib.parse import urlparse
import urllib.request
from PIL import Image
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from npdb_asset_paths import AssetAccessError, read_https_asset, validate_https_asset_url, validate_asset_content
from test_asset_reader_integration import load


class RemoteAssetSecurityTests(unittest.TestCase):
    def test_unsafe_urls_denied_before_opener_creation(self):
        for url in ('file:///private/secrets.toml','http://trusted.invalid/file.png',
                    'https://localhost/file.png','https://127.0.0.1/file.png',
                    'https://169.254.169.254/credentials','https://[::1]/file.png',
                    'https://trusted.invalid@attacker.invalid/file.png',
                    'https://trusted.invalid:444/file.png','https://attacker.invalid/file.png',
                    'https://trusted.invalid/\nfile.png'):
            with self.subTest(url=url), patch('urllib.request.build_opener') as opener:
                with self.assertRaises(AssetAccessError):
                    read_https_asset(url,allowed_hosts={'trusted.invalid'},max_bytes=50)
                opener.assert_not_called()

    def test_redirect_policy_rechecks_scheme_host_and_local_address(self):
        captured=[]
        class Response(io.BytesIO):
            def geturl(self): return 'https://trusted.invalid/image.png'
        def make_opener(*handlers):
            captured.extend(handlers)
            return types.SimpleNamespace(open=lambda *a,**k:Response(b'synthetic'))
        with patch('urllib.request.build_opener', side_effect=make_opener):
            self.assertEqual(read_https_asset('https://trusted.invalid/image.png',
                             allowed_hosts={'trusted.invalid'},max_bytes=9),b'synthetic')
        redirect=next(h for h in captured if isinstance(h,urllib.request.HTTPRedirectHandler))
        for newurl in ('file:///private/config','http://trusted.invalid/x',
                       'https://127.0.0.1/x','https://attacker.invalid/x'):
            with self.subTest(newurl=newurl),self.assertRaises(AssetAccessError):
                redirect.redirect_request(urllib.request.Request('https://trusted.invalid/x'),None,302,'Found',{},newurl)
        request=redirect.redirect_request(urllib.request.Request('https://trusted.invalid/x'),None,302,'Found',{},'https://trusted.invalid/y')
        self.assertEqual(request.full_url,'https://trusted.invalid/y')

    def test_oversized_remote_body_is_bounded_and_error_does_not_echo_url(self):
        sizes=[]
        class Response(io.BytesIO):
            def geturl(self): return 'https://trusted.invalid/private-token'
            def read(self,n=-1): sizes.append(n);return super().read(n)
        with patch('urllib.request.build_opener',return_value=types.SimpleNamespace(
                open=lambda *a,**k:Response(b'x'*100))):
            with self.assertRaises(AssetAccessError) as error:
                read_https_asset('https://trusted.invalid/private-token',allowed_hosts={'trusted.invalid'},max_bytes=8)
        self.assertEqual(sizes,[9])
        self.assertNotIn('private-token',str(error.exception))

    def test_app_remote_reader_validates_media_and_uses_server_hosts(self):
        output=io.BytesIO();Image.new('RGB',(8,8),'white').save(output,format='PNG')
        calls=[]
        def reader(url,**kw):calls.append((url,kw));return output.getvalue()
        ns=dict(Path=Path,Image=Image,io=io,urlparse=urlparse,AssetAccessError=AssetAccessError,
                display_asset_url=lambda s:'https://synthetic.supabase.co/object/sign/image.png?token=synthetic',
                get_supabase_url=lambda:'https://synthetic.supabase.co',read_https_asset=reader,
                validate_asset_content=validate_asset_content,LOCAL_ASSET_MAX_BYTES=1024,
                LOCAL_IMAGE_SUFFIXES={'.png'},LOCAL_SPECTRUM_SUFFIXES={'.png'})
        load(ns,'read_remote_scientific_asset')
        data,suffix=ns['read_remote_scientific_asset']('storage://structures/test.png',image_only=True)
        self.assertEqual(data,output.getvalue());self.assertEqual(suffix,'.png')
        self.assertIn('synthetic.supabase.co',calls[0][1]['allowed_hosts'])
        ns['read_https_asset']=lambda *a,**k:b'forged image'
        with self.assertRaises(Exception):ns['read_remote_scientific_asset']('https://trusted.invalid/file.png',image_only=True)
