"""Actual boundary functions with synthetic secrets/HTTP; no production I/O."""
import io
from pathlib import Path
import types
import unittest
import zipfile
import pandas as pd
import test_backend_security_boundaries as boundaries
load = boundaries.load


class PreflightBypassTests(unittest.TestCase):
    def fixture(self,role='viewer'):
        ns=boundaries.BackendSecurityBoundaryTests().fixture(role)
        from openpyxl.styles import Font
        ns.update(io=io,pd=pd,Alignment=None,Font=Font,PatternFill=None,OWNER_CREDIT='synthetic')
        load(ns,'display_precise_gps','redact_private_gps_for_current_user',
             'dataframe_to_csv_bytes','dataframe_to_excel_bytes','_dataframes_to_record_workbook')
        return ns

    def test_owner_then_viewer_csv_and_workbook_do_not_reuse_sensitive_bytes(self):
        frame=pd.DataFrame([{'GPS Coordinates':'SYNTHETIC_PRIVATE_MARKER','name':'synthetic'}])
        owner=self.fixture('owner');viewer=self.fixture()
        self.assertIn(b'SYNTHETIC_PRIVATE_MARKER',owner['dataframe_to_csv_bytes'](frame))
        self.assertNotIn(b'SYNTHETIC_PRIVATE_MARKER',viewer['dataframe_to_csv_bytes'](frame))
        for function,args in [('dataframe_to_excel_bytes',(frame,)),
                              ('_dataframes_to_record_workbook',({'Metadata':pd.DataFrame([{'Field':'GPS Coordinates','Value':'SYNTHETIC_PRIVATE_MARKER'}])},))]:
            data=viewer[function](*args)
            with zipfile.ZipFile(io.BytesIO(data)) as archive:
                self.assertFalse(any(b'SYNTHETIC_PRIVATE_MARKER' in archive.read(n) for n in archive.namelist()))
        self.assertEqual(frame.iloc[0]['GPS Coordinates'],'SYNTHETIC_PRIVATE_MARKER')

    def test_revoked_owner_serialization_fails_closed(self):
        ns=self.fixture('owner');frame=pd.DataFrame([{'gps_coordinates':'SYNTHETIC_PRIVATE_MARKER'}])
        ns['load_approved_users']=lambda:[]
        self.assertNotIn(b'SYNTHETIC_PRIVATE_MARKER',ns['dataframe_to_csv_bytes'](frame))

    def test_raw_private_storage_and_admin_reads_stop_before_credentials(self):
        for role,method,path in [('viewer','GET','/storage/v1/object/authenticated/backups/private.zip'),
             ('editor','HEAD','/storage/v1/object/backups/private.zip'),
             ('viewer','GET','/rest/v1/audit_events'),
             ('viewer','DELETE','/storage/v1/object/sign/structures/x.png')]:
            ns=self.fixture(role)
            ns['_supabase_headers']=lambda **kw:self.fail('privileged headers created')
            ns['urllib']=types.SimpleNamespace(request=types.SimpleNamespace(Request=lambda *a,**kw:self.fail('request construction reached')))
            load(ns,'_supabase_request')
            with self.subTest(role=role,method=method,path=path),self.assertRaises(PermissionError):
                ns['_supabase_request'](method,path,write=True)

    def test_unauthenticated_raw_science_read_stops_before_transport(self):
        ns=self.fixture();ns['st'].session_state['npdb_authenticated']=False
        load(ns,'_supabase_request')
        with self.assertRaises(PermissionError):ns['_supabase_request']('GET','/rest/v1/compounds')

    def test_raw_json_nested_gps_alias_is_redacted_without_mutating_payload(self):
        import json
        import re
        import urllib.request
        payload=[{'id':1,'position':'SYNTHETIC_PRIVATE_MARKER','nested':{'gps_coordinates':'SYNTHETIC_PRIVATE_MARKER'}}]
        ns=self.fixture()
        ns.update(re=re,_supabase_headers=lambda **kw:{},_supabase_ssl_context=lambda:None)
        ns['urllib']=types.SimpleNamespace(request=types.SimpleNamespace(
            Request=urllib.request.Request,urlopen=lambda *a,**kw:io.BytesIO(json.dumps(payload).encode())),error=__import__('urllib.error',fromlist=['HTTPError']))
        load(ns,'redact_gps_payload','_supabase_request')
        result=ns['_supabase_request']('GET','/rest/v1/compounds',query={'select':'id,position:gps_coordinates,nested(*)'})
        self.assertNotIn('SYNTHETIC_PRIVATE_MARKER',str(result))
        self.assertIn('SYNTHETIC_PRIVATE_MARKER',str(payload))
