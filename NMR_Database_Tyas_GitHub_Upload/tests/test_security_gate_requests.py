"""Adversarial raw dispatcher tests: synthetic accounts and transport spies."""
import io
import json
import re
import types
import unittest
import urllib.request
import urllib.error
import test_backend_security_boundaries as boundary


class RequestGateTests(unittest.TestCase):
    def fixture(self, role='viewer'):
        ns=boundary.BackendSecurityBoundaryTests().fixture(role)
        ns.update(re=re,_supabase_headers=lambda **kw:{},_supabase_ssl_context=lambda:None)
        boundary.load(ns,'redact_gps_payload','_supabase_request')
        return ns

    def test_raw_signing_cannot_override_lifetime(self):
        for role in ('owner','editor','viewer'):
            for expiry in (None,True,0,301,86400,'300'):
                ns=self.fixture(role)
                with self.subTest(role=role,expiry=expiry),self.assertRaises(PermissionError):
                    ns['_supabase_request']('POST','/storage/v1/object/sign/structures/x.png',body={'expiresIn':expiry},write=True)

    def test_raw_headers_cannot_override_identity_method_or_object(self):
        for header,value in [('Authorization','synthetic'),('apikey','synthetic'),('Host','outside.invalid'),
                             ('X-HTTP-Method-Override','DELETE'),('x-upsert','true')]:
            ns=self.fixture('editor')
            with self.subTest(header=header),self.assertRaises(PermissionError):
                ns['_supabase_request']('POST','/storage/v1/object/structures/x.png',body=b'test',extra_headers={header:value})

    def test_quoted_and_whitespace_gps_aliases_fail_closed(self):
        for select,key in [('"precise location":gps_coordinates','precise location'),('position : gps_coordinates','position')]:
            ns=self.fixture()
            ns['urllib']=types.SimpleNamespace(request=types.SimpleNamespace(Request=urllib.request.Request,
                urlopen=lambda *a,**kw:io.BytesIO(json.dumps([{key:'SYNTHETIC_PRIVATE'}]).encode())),error=urllib.error)
            result=ns['_supabase_request']('GET','/rest/v1/compounds',query={'select':select})
            self.assertNotIn('SYNTHETIC_PRIVATE',str(result))

    def test_http_error_does_not_echo_private_response_body(self):
        ns=self.fixture()
        error=urllib.error.HTTPError('https://synthetic.invalid',400,'synthetic',{},io.BytesIO(b'SYNTHETIC_PRIVATE'))
        def fail(*a,**kw):raise error
        ns['urllib']=types.SimpleNamespace(request=types.SimpleNamespace(Request=urllib.request.Request,urlopen=fail),error=urllib.error)
        with self.assertRaises(RuntimeError) as result:ns['_supabase_request']('GET','/rest/v1/compounds')
        self.assertNotIn('SYNTHETIC_PRIVATE',str(result.exception))
