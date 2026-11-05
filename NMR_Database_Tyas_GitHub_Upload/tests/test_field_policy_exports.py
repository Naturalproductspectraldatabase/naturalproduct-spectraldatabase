"""Actual successful app serializers/readers against isolated synthetic records.

No app import/startup, bundled data, network or real coordinates. AST extraction
keeps actual decorators and policies; only backend transport and formatting
helpers irrelevant to policy are synthetic. Full-script/browser jobs are separate.
"""
import ast
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict
from datetime import UTC, datetime
import hashlib
import io
import json
from pathlib import Path
import sqlite3
import sys
import tempfile
from threading import Barrier
from types import SimpleNamespace
import unittest
import zipfile
import pandas as pd
from authorization_fixture import bind_authorization
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from npdb_location_policy import Evidence, PUBLISHED_VERIFIED, value_digest
from npdb_field_access import Disclosure, context, verify_payload, READ_DEPTH
from npdb_provenance_review import prepare, approve

APP=Path(__file__).resolve().parents[1]/'scripts/app.py'
PRIVATE='SYNTHETIC-RESTRICTED-SENTINEL'
PUBLIC='SYNTHETIC-PUBLISHED-ORIGINAL-PRECISION'


def load(ns,*names):
    tree=ast.parse(APP.read_text())
    for name in names:
        node=[n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name==name][-1]
        exec(compile(ast.Module(body=[node],type_ignores=[]),str(APP),'exec'),ns)


def fixture(role='viewer'):
    ns=bind_authorization(role=role)
    record=dict(id=501,updated_at='synthetic-revision-1',trivial_name='SYNTHETIC-ETHANOL',
        iupac_name='ethanol',smiles='CCO',inchi='InChI=1S/C2H6O/c1-2-3/h3H,2H2,1H3',inchikey='LFQSCWFLJHTTHZ-UHFFFAOYSA-N',molecular_formula='C2H6O',molecular_weight=46.07,
        compound_class='Synthetic',compound_subclass='',source_category='Synthetic',source_organism='Synthetic taxon',source_material=PRIVATE,
        sample_code=PRIVATE,gps_coordinates=PUBLIC,collection_location=PRIVATE,depth_m=PRIVATE,
        collector=PRIVATE,sampling_date=PRIVATE,note=PRIVATE,structure_image_path='',
        uv_data='',ftir_data='',cd_data='',optical_rotation='',melting_point='',crystallization_method='',hrms_data='',
        journal_name='Synthetic journal',article_title='Synthetic reference',publication_year=2026,volume='',issue='',pages='',doi='10.0000/synthetic-not-a-real-doi',ccdc_number='',data_source='Synthetic',curation_status='imported')
    fact=Evidence(table='compounds',record_id='501',field='gps_coordinates',record_revision=record['updated_at'],value_sha256=value_digest(PUBLIC),classification=PUBLISHED_VERIFIED,verification_status='VERIFIED',source_reference='Synthetic fixture source, not a real publication',source_locator='Synthetic table row 1',verified_by='Synthetic owner',verifier_role='owner')
    config=dict(version=1,entries=[asdict(fact)])
    ns['get_secret_object']=lambda *keys:config
    ns.update(pd=pd,io=io,Path=Path,datetime=datetime,UTC=UTC,zipfile=zipfile,
        OWNER_CREDIT='Synthetic QA credit',clean_text=lambda v:'-' if v is None else str(v),
        maybe_blank=lambda v:'' if v is None else str(v).strip(),source_summary_from_record=lambda row:row.get('source_material',''),
        normalize_curation_status=lambda value,default='imported':value or default,
        slugify_value=lambda v,fallback='file':str(v or fallback).replace(' ','_'),
        is_generated_structure_reference=lambda v:str(v).startswith('storage://structures/generated/'),
        is_external_url=lambda v:str(v).startswith('https://'),
        is_supabase_storage_reference=lambda v:str(v).startswith('storage://'),
        load_bioactivity_data=lambda cid:pd.DataFrame(),
        _asset_bytes_from_source=lambda *a,**kw:(b'',''))
    try:
        from openpyxl.styles import Alignment,Font,PatternFill
    except ImportError:
        Alignment=Font=PatternFill=None
    ns.update(Alignment=Alignment,Font=Font,PatternFill=PatternFill)
    load(ns,'redact_private_gps_for_current_user','display_precise_gps','redact_gps_payload',
        'add_credit_to_text_bytes','dataframe_to_csv_bytes','dataframe_to_excel_bytes',
        'download_dataframe_button','_archive_safe_name','_select_existing_columns',
        '_important_metadata_dataframe','disclose_potency_unit_status','_important_bioactivity_dataframe',
        '_dataframes_to_record_workbook','_compound_structure_asset','build_compound_summary_text',
        'build_compound_record_bundle','export_name_results','export_bioactivity_results',
        'export_structure_search_results','export_similarity_results_13c','export_similarity_results_1h','export_similarity_results_combined')
    return ns,record,config


def text_in_workbook(data):
    from openpyxl import load_workbook
    book=load_workbook(io.BytesIO(data),data_only=True)
    return '\n'.join(str(cell.value) for sheet in book for row in sheet for cell in row if cell.value is not None)


class SuccessfulFieldExports(unittest.TestCase):
    def test_actual_name_csv_and_owner_held_frames_all_roles(self):
        for role in ('owner','editor','viewer'):
            ns,record,config=fixture(role)
            raw=pd.DataFrame([record]);before=raw.copy(deep=True)
            output=ns['export_name_results'](raw)
            payload=ns['dataframe_to_csv_bytes'](output)
            self.assertIn(PUBLIC,payload.decode())
            self.assertEqual(PRIVATE in payload.decode(),role=='owner')
            self.assertEqual(raw.to_dict(),before.to_dict())
            self.assertNotIn(PRIVATE,str(output.attrs))
            self.assertIn('C2H6O',payload.decode())

    @unittest.skipUnless(__import__('importlib').util.find_spec('openpyxl'),'openpyxl not installed')
    def test_real_xlsx_bytes_preserve_published_and_chemistry(self):
        for role in ('viewer','editor','owner'):
            ns,record,_=fixture(role)
            data=ns['dataframe_to_excel_bytes'](ns['export_name_results'](pd.DataFrame([record])))
            text=text_in_workbook(data)
            self.assertIn(PUBLIC,text)
            self.assertEqual(PRIVATE in text,role=='owner')
            self.assertIn('SYNTHETIC-ETHANOL',text)

    def test_real_zip_text_csv_json_and_workbook_members(self):
        for role in ('owner','editor','viewer'):
            ns,record,_=fixture(role)
            h=pd.DataFrame([dict(id=51,compound_id=501,delta_ppm=1.23,multiplicity='t',assignment='H1',note=PRIVATE)])
            c=pd.DataFrame([dict(id=61,compound_id=501,delta_ppm=18.7,carbon_type='CH3',assignment='C1',note=PRIVATE)])
            spectra=pd.DataFrame([dict(id=71,compound_id=501,spectrum_type='1H',file_path=PRIVATE,note=PRIVATE)])
            bio=pd.DataFrame([dict(id=81,compound_id=501,activity_label='Synthetic assay',potency_value=2.1,potency_unit='uM',note=PRIVATE)])
            blob,name=ns['build_compound_record_bundle'](pd.DataFrame([record]),h,c,spectra,bio)
            with zipfile.ZipFile(io.BytesIO(blob)) as archive:
                text='\n'.join(archive.read(n).decode() for n in archive.namelist() if not n.endswith('.xlsx'))
                self.assertIn(PUBLIC,text)
                self.assertEqual(PRIVATE in text,role=='owner')
                self.assertIn('1.23',text);self.assertIn('18.7',text);self.assertIn('501',text)
                if 'NPDB_full_record.xlsx' in archive.namelist():
                    workbook=text_in_workbook(archive.read('NPDB_full_record.xlsx'))
                    self.assertEqual(PRIVATE in workbook,role=='owner')
                    self.assertIn(PUBLIC,workbook)

    def test_metadata_vertical_and_nested_alias_unknown_columns(self):
        ns,record,_=fixture()
        d=ns['current_disclosure']()
        raw=pd.DataFrame([{**record,'payload':{'GPS':PRIVATE,'nested':{'note':PRIVATE,'smiles':'CCO'}},'mystery_location':PRIVATE}])
        result=d.frame(raw)
        self.assertNotIn(PRIVATE,str(result.to_dict('records'))+str(result.attrs))
        self.assertEqual(result.iloc[0]['payload']['nested']['smiles'],'CCO')
        direct=d.payload([dict(record,chemical_alias=PRIVATE)],'compounds',{'chemical_alias':'gps_coordinates'})
        self.assertNotIn(PRIVATE,str(direct))
        vertical=ns['_important_metadata_dataframe'](record)
        self.assertIn(PUBLIC,ns['dataframe_to_csv_bytes'](vertical).decode())

    def test_conflicting_stale_forged_receipts_and_doi_only_fail_closed(self):
        for alteration in ('missing','stale','changed_value','conflict','restricted','forged'):
            ns,record,config=fixture()
            if alteration=='missing':config['entries']=[]
            elif alteration=='stale':record['updated_at']='new-revision'
            elif alteration=='changed_value':record['gps_coordinates']=PRIVATE
            elif alteration=='conflict':config['entries']*=2
            elif alteration=='restricted':config['entries'][0]['disclosure_restrictions']=['sensitive']
            frame=pd.DataFrame([record])
            if alteration=='forged':
                frame.attrs['_npdb_field_context_v1']={'signature':'fake','contexts':[context(record,'compounds')]}
                config['entries']=[]
            text=ns['dataframe_to_csv_bytes'](frame).decode()
            self.assertNotIn(PUBLIC,text);self.assertNotIn(PRIVATE,text)

    def test_generated_owner_payload_cannot_register_in_viewer_or_after_policy_change(self):
        ns,record,config=fixture('owner')
        payload=ns['dataframe_to_csv_bytes'](pd.DataFrame([record]))
        captured=[];ns['st'].download_button=lambda **kw:captured.append(kw)
        ns['guarded_download_button'](data=payload,file_name='owner.csv',label='Export',key='ok')
        self.assertEqual(len(captured),1)
        for change in ('logout','remove','rotate','role','policy'):
            current,record,current_config=fixture('owner')
            data=current['dataframe_to_csv_bytes'](pd.DataFrame([record]))
            current['st'].download_button=lambda **kw:self.fail('stale payload registered')
            if change=='logout':current['st'].session_state['npdb_authenticated']=False
            elif change=='remove':current['load_approved_users']().clear()
            elif change=='rotate':current['load_approved_users']()[0]['password_hash']='rotated'
            elif change=='role':
                current['load_approved_users']()[0]['role']='viewer';current['st'].session_state['npdb_role']='viewer'
                current['st'].session_state['npdb_credential_revision']=current['configured_session_identity']()[1]
            else:current_config['entries']=[]
            with self.subTest(change=change),self.assertRaises(PermissionError):
                current['guarded_download_button'](data=data,file_name='private.csv',label='Export',key='blocked')

    def test_mid_generation_revocation_before_any_widget_registration(self):
        ns,record,_=fixture('owner');ns['st'].download_button=lambda **kw:self.fail('revoked download registered')
        original=ns['dataframe_to_excel_bytes']
        def generate(*args,**kwargs):
            payload=ns['dataframe_to_csv_bytes'](args[0])
            ns['st'].session_state['npdb_authenticated']=False
            return payload
        ns['dataframe_to_excel_bytes']=generate
        with self.assertRaises(PermissionError):
            ns['download_dataframe_button']('Export',pd.DataFrame([record]),'private.xlsx','export')

    def test_concurrent_role_swap_during_generation_is_denied(self):
        ns,record,_=fixture('owner');barrier=Barrier(2);captured=[]
        ns['st'].download_button=lambda **kw:captured.append(kw)
        def generate(frame,**kwargs):
            result=ns['dataframe_to_csv_bytes'](frame);barrier.wait(timeout=10);barrier.wait(timeout=10);return result
        ns['dataframe_to_excel_bytes']=generate
        with ThreadPoolExecutor(max_workers=1) as pool:
            future=pool.submit(ns['download_dataframe_button'],'Export',pd.DataFrame([record]),'x.xlsx','concurrent')
            barrier.wait(timeout=10)
            ns['load_approved_users']()[0]['role']='viewer';ns['st'].session_state['npdb_role']='viewer'
            ns['st'].session_state['npdb_credential_revision']=ns['configured_session_identity']()[1]
            barrier.wait(timeout=10)
            with self.assertRaises(PermissionError):future.result(timeout=10)
        self.assertFalse(captured);self.assertEqual(READ_DEPTH.get(),0)

    def test_owner_review_requires_individually_enumerated_verified_evidence(self):
        _,record,_=fixture()
        packet=prepare('compounds',[record]);self.assertTrue(all(e['classification']=='UNKNOWN_UNVERIFIED' for e in packet['entries']))
        gps=next(e for e in packet['entries'] if e['field']=='gps_coordinates')
        decision=dict(candidate_id=gps['candidate_id'],classification=PUBLISHED_VERIFIED,
            verification_status='VERIFIED',verified_by='Synthetic owner',verified_at='2026-11-05T00:00:00Z',source_reference='Synthetic source',source_locator='Synthetic table',content_reviewed=True)
        self.assertEqual(len(approve(packet,[decision])['entries']),1)
        for field in ('source_locator','verified_by','verified_at','content_reviewed'):
            bad=dict(decision);bad.pop(field)
            with self.subTest(field=field),self.assertRaises((ValueError,KeyError)):approve(packet,[bad])
        with self.assertRaises(ValueError):approve(packet,[decision,decision])
