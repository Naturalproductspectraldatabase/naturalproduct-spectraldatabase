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
        'field_provenance_export','build_compound_record_bundle','export_name_results','export_bioactivity_results',
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
                provenance=json.loads(archive.read('field_provenance.json'))
                gps=next(e for e in provenance['entries'] if e['field']=='gps_coordinates')
                self.assertEqual(gps['classification'],'PUBLISHED_VERIFIED')
                self.assertEqual(gps['source_locator'],'Synthetic table row 1')
                self.assertEqual(bool(gps['verified_by']),role=='owner')
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
            if alteration=='forged':
                with self.assertRaises(PermissionError):ns['dataframe_to_csv_bytes'](frame)
                continue
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

    def test_owner_produced_frame_is_reprojected_before_successful_viewer_registration(self):
        owner,record,_=fixture('owner');viewer,_,_=fixture('viewer')
        held=owner['export_name_results'](pd.DataFrame([record]));captured=[]
        viewer['st'].download_button=lambda **kw:captured.append(kw)
        viewer['download_dataframe_button']('Export',held,PRIVATE+'.xlsx','viewer-export')
        self.assertEqual(len(captured),1)
        self.assertNotIn(PRIVATE,captured[0]['file_name'])
        text=text_in_workbook(captured[0]['data']) if captured[0]['mime']!='text/csv' else captured[0]['data'].decode()
        self.assertIn(PUBLIC,text);self.assertNotIn(PRIVATE,text)

    def test_similarity_structure_and_bioactivity_export_families(self):
        ns,record,_=fixture('viewer')
        item={**record,'compound_id':501,'structure_score':100,'structure_match_type':'Synthetic',
              'matched_smiles':'CCO','score':95,'match_count':1,'total_query':1,'db_peak_count':1,
              'query_coverage':1,'db_coverage':1,'avg_difference':0,
              'proton_match_count':1,'proton_total_query':1,'proton_query_coverage':1,'proton_score':95,
              'carbon_match_count':1,'carbon_total_query':1,'carbon_query_coverage':1,'carbon_score':95,'total_score':95}
        for name in ('export_structure_search_results','export_similarity_results_1h','export_similarity_results_13c','export_similarity_results_combined'):
            output=ns[name]([item]);text=ns['dataframe_to_csv_bytes'](output).decode()
            self.assertNotIn(PRIVATE,text);self.assertIn('SYNTHETIC-ETHANOL',text)
        bio=pd.DataFrame([dict(id=81,compound_id=501,trivial_name='SYNTHETIC-ETHANOL',activity_label='Synthetic',potency_value=2.1,potency_unit='uM',note=PRIVATE)])
        text=ns['dataframe_to_csv_bytes'](ns['export_bioactivity_results'](bio)).decode()
        self.assertNotIn(PRIVATE,text);self.assertIn('uM',text)

    def test_each_location_field_has_independent_classification_all_roles(self):
        fields=('gps_coordinates','collection_location','depth_m','sample_code','sampling_date','collection_date','collector')
        for role in ('owner','viewer','editor'):
            for classification in ('PUBLISHED_VERIFIED','INTERNAL_UNPUBLISHED','SENSITIVE_RESTRICTED','UNKNOWN_UNVERIFIED'):
                ns,record,config=fixture(role);config['entries']=[]
                for field in fields:
                    record[field]=PUBLIC+'-'+field
                    config['entries'].append(asdict(Evidence(table='compounds',record_id='501',field=field,
                        record_revision=record['updated_at'],value_sha256=value_digest(record[field]),classification=classification,
                        verification_status='VERIFIED',source_reference='Synthetic source',source_locator='Synthetic table',verified_by='Synthetic owner',verifier_role='owner')))
                projected=ns['policy_frame'](pd.DataFrame([record]))
                for field in fields:
                    with self.subTest(role=role,classification=classification,field=field):
                        self.assertEqual(projected.iloc[0][field],record[field] if role=='owner' or classification=='PUBLISHED_VERIFIED' else None)

    @unittest.skipUnless(__import__('importlib').util.find_spec('streamlit'),'Streamlit not installed')
    def test_actual_sqlite_shared_streamlit_cache_owner_then_viewer_and_alias_read(self):
        import streamlit
        ns,record,config=fixture('owner')
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'synthetic.sqlite';calls=[]
            with sqlite3.connect(path) as connection:pd.DataFrame([record]).to_sql('compounds',connection,index=False)
            def connection():calls.append(1);return sqlite3.connect(path)
            ns.update(DB_PATH=path,get_connection=connection,get_npdb_read_backend=lambda:'local',
                compound_select_columns=lambda:'*',get_db_signature=lambda:'synthetic-'+directory,
                enrich_compounds_dataframe=lambda frame:frame.copy(),SOURCE_NORMALIZATION_CACHE_VERSION='synthetic',DATA_CACHE_TTL_SECONDS=60)
            ns['st'].cache_data=streamlit.cache_data
            load(ns,'_sqlite_dataframe','_load_all_compounds_cached','load_all_compounds')
            ns['_load_all_compounds_cached'].clear();held=ns['load_all_compounds']()
            self.assertIn(PRIVATE,str(held.to_dict()))
            before=len(calls)
            ns['load_approved_users']()[0]['role']='viewer';ns['st'].session_state['npdb_role']='viewer'
            ns['st'].session_state['npdb_credential_revision']=ns['configured_session_identity']()[1]
            public=ns['load_all_compounds']();self.assertEqual(len(calls),before)
            self.assertIn(PUBLIC,str(public.to_dict()));self.assertNotIn(PRIVATE,str(public.to_dict())+str(public.attrs))
            with self.assertRaises(PermissionError):ns['_sqlite_dataframe']('SELECT id,updated_at,sample_code AS smiles,gps_coordinates FROM compounds')
            # Cross-session projection never mutates owner-held objects or raw cache.
            self.assertIn(PRIVATE,str(held.to_dict()))

    def test_actual_asset_review_digest_metadata_replacement_and_private_raw_helper(self):
        from PIL import Image
        from PIL.PngImagePlugin import PngInfo
        from npdb_asset_paths import AssetAccessError,read_local_asset,validate_asset_content
        ns,record,config=fixture('viewer')
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);assets=root/'data/structures';assets.mkdir(parents=True)
            path=assets/'synthetic.png';Image.new('RGB',(8,8),'white').save(path)
            record['structure_image_path']='data/structures/synthetic.png'
            db=root/'synthetic.sqlite'
            with sqlite3.connect(db) as connection:pd.DataFrame([record]).to_sql('compounds',connection,index=False)
            ns.update(get_connection=lambda:sqlite3.connect(db),get_npdb_read_backend=lambda:'local',
                PROJECT_DIR=root,STRUCTURES_DIR=assets,SPECTRA_DIR=root/'data/spectra',SPECIMENS_DIR=root/'data/specimens',
                LOCAL_IMAGE_SUFFIXES={'.png'},LOCAL_SPECTRUM_SUFFIXES={'.png'},LOCAL_ASSET_MAX_BYTES=1024*1024,
                read_local_asset=read_local_asset,validate_asset_content=validate_asset_content,AssetAccessError=AssetAccessError)
            load(ns,'read_scientific_asset')
            with self.assertRaises(AssetAccessError):ns['read_scientific_asset'](record['structure_image_path'],'structure')
            with self.assertRaises(PermissionError):ns['field_policy_raw_record']('compounds',501)
            config['entries'].append(asdict(Evidence(table='compounds',record_id='501',field='structure_image_path',record_revision=record['updated_at'],
                value_sha256=value_digest(record['structure_image_path']),classification=PUBLISHED_VERIFIED,verification_status='VERIFIED',
                source_reference='Synthetic source',source_locator='Synthetic figure',verified_by='Synthetic owner',verifier_role='owner',asset_sha256=hashlib.sha256(path.read_bytes()).hexdigest())))
            self.assertEqual(ns['read_scientific_asset'](record['structure_image_path'],'structure'),path.read_bytes())
            metadata=PngInfo();metadata.add_text('Description',PRIVATE)
            Image.new('RGB',(8,8),'white').save(path,pnginfo=metadata)
            with self.assertRaises(AssetAccessError):ns['read_scientific_asset'](record['structure_image_path'],'structure')

    def test_owner_receipt_cannot_relabel_private_cell_as_scientific_column(self):
        owner,record,_=fixture('owner');viewer,_,_=fixture('viewer')
        held=owner['policy_frame'](pd.DataFrame([record]))
        forged=held[['sample_code']].rename(columns={'sample_code':'smiles'})
        with self.assertRaises(PermissionError):viewer['dataframe_to_csv_bytes'](forged)
        filtered=held[held['id']==501].copy()
        self.assertNotIn(PRIVATE,viewer['dataframe_to_csv_bytes'](filtered).decode())
        nested=viewer['current_disclosure']().payload({PRIVATE:PRIVATE,'nested':{PRIVATE:PRIVATE,'smiles':'CCO'}})
        self.assertNotIn(PRIVATE,str(nested));self.assertIn('CCO',str(nested))

    def test_editor_update_preserves_hidden_stored_values(self):
        ns,record,_=fixture('editor')
        with tempfile.TemporaryDirectory() as directory:
            db=Path(directory)/'only-synthetic.sqlite'
            with sqlite3.connect(db) as connection:pd.DataFrame([record]).to_sql('compounds',connection,index=False)
            ns.update(get_connection=lambda:sqlite3.connect(db),get_npdb_read_backend=lambda:'local',
                _sqlite_columns=lambda table:list(record),use_supabase_write_backend=lambda:False,record_audit_event=lambda *a,**k:None)
            load(ns,'_sqlite_upsert_row')
            ns['_sqlite_upsert_row']('compounds',dict(id=501,trivial_name='Synthetic edited name',note='',sample_code='',collection_location='',structure_image_path=''))
            with sqlite3.connect(db) as connection:stored=pd.read_sql_query('SELECT * FROM compounds',connection).iloc[0]
            self.assertEqual(stored['trivial_name'],'Synthetic edited name')
            for field in ('note','sample_code','collection_location'):
                self.assertEqual(stored[field],PRIVATE)

    def test_linked_specimen_tables_follow_same_compound_and_field_decisions(self):
        ns,record,_=fixture('viewer')
        ns.update(load_specimen_compound_links=lambda:pd.DataFrame([dict(id=1,compound_id=501,specimen_id=7,evidence_note=PRIVATE,reference_note=PRIVATE,created_at='synthetic')]),
            load_all_specimens=lambda *a:pd.DataFrame([dict(id=7,scientific_name='Synthetic taxon',specimen_name=PRIVATE,collection_location=PRIVATE,gps_coordinates=PRIVATE,updated_at='synthetic')]),
            load_specimen_extracts=lambda **kw:pd.DataFrame([dict(id=9,specimen_id=7,file_path=PRIVATE,note=PRIVATE,solvent='Synthetic',updated_at='synthetic')]),
            get_db_signature=lambda:'synthetic')
        load(ns,'record_related_specimen_tables')
        blob,_=ns['build_compound_record_bundle'](pd.DataFrame([record]),pd.DataFrame(),pd.DataFrame(),pd.DataFrame(),pd.DataFrame())
        with zipfile.ZipFile(io.BytesIO(blob)) as archive:
            links=pd.read_csv(io.BytesIO(archive.read('tables/specimen_compounds.csv')))
            specimens=pd.read_csv(io.BytesIO(archive.read('tables/specimens.csv')))
            self.assertEqual(int(links.iloc[0]['compound_id']),501)
            self.assertEqual(int(links.iloc[0]['specimen_id']),int(specimens.iloc[0]['id']))
            self.assertNotIn(PRIVATE,archive.read('tables/specimens.csv').decode())
            self.assertIn('Synthetic taxon',archive.read('tables/specimens.csv').decode())

    def test_reprojection_is_idempotent_on_partial_child_frames(self):
        ns,_,_=fixture('viewer')
        frame=pd.DataFrame([dict(id=51,compound_id=501,delta_ppm=1.23,multiplicity='t',assignment='H1',note=PRIVATE)])
        first=ns['policy_frame'](frame,'proton_nmr')
        second=ns['policy_frame'](first,'proton_nmr')
        self.assertEqual(first.to_dict(),second.to_dict())
        self.assertEqual(second.iloc[0]['delta_ppm'],1.23)
        columns=list(second.columns)
        ns['_select_existing_columns'](second,['delta_ppm','note','new_optional_column'])
        self.assertEqual(list(second.columns),columns)
        self.assertEqual(ns['policy_frame'](second,'proton_nmr').to_dict(),second.to_dict())

    def test_raw_sql_read_cannot_mutate_or_open_unrelated_tables(self):
        ns,record,_=fixture('owner')
        with tempfile.TemporaryDirectory() as directory:
            db=Path(directory)/'synthetic.sqlite'
            with sqlite3.connect(db) as connection:
                pd.DataFrame([record]).to_sql('compounds',connection,index=False)
                connection.execute('CREATE TABLE private_config(smiles TEXT)')
                connection.execute('INSERT INTO private_config VALUES(?)',(PRIVATE,))
            ns.update(DB_PATH=db,get_connection=lambda:sqlite3.connect(db),get_npdb_read_backend=lambda:'local')
            load(ns,'_sqlite_dataframe','_snapshot_dataframe')
            for query in ('DELETE FROM compounds','UPDATE compounds SET note=1','SELECT smiles FROM private_config',"ATTACH DATABASE ':memory:' AS elsewhere"):
                with self.subTest(query=query),self.assertRaises((pd.errors.DatabaseError,sqlite3.DatabaseError)):
                    ns['_sqlite_dataframe'](query)
            with sqlite3.connect(db) as connection:self.assertEqual(connection.execute('SELECT count(*) FROM compounds').fetchone()[0],1)
            with self.assertRaises(PermissionError):ns['_snapshot_dataframe']('../private_config')

    @unittest.skipUnless(__import__('importlib').util.find_spec('openpyxl'),'openpyxl not installed')
    def test_workbook_sheet_and_dataframe_index_metadata_cannot_leak(self):
        ns,record,_=fixture('viewer');frame=pd.DataFrame([record],index=[PRIVATE])
        projected=ns['policy_frame'](frame)
        self.assertNotIn(PRIVATE,str(projected.index))
        data=ns['dataframe_to_excel_bytes'](frame,sheet_name=PRIVATE)
        book=__import__('openpyxl').load_workbook(io.BytesIO(data),data_only=True)
        self.assertNotIn(PRIVATE,str(book.sheetnames));self.assertIn(PUBLIC,text_in_workbook(data))
        data=ns['_dataframes_to_record_workbook']({PRIVATE:frame})
        book=__import__('openpyxl').load_workbook(io.BytesIO(data),data_only=True)
        self.assertNotIn(PRIVATE,str(book.sheetnames));self.assertNotIn(PRIVATE,text_in_workbook(data))

    def test_combined_nmr_match_pairs_survive_projection_without_notes(self):
        ns,record,_=fixture('viewer')
        item={**record,'compound_id':501,'proton_matches':[(1.23,1.23,0)],'carbon_matches':[(18.7,18.7,0)]}
        result=ns['current_disclosure']().payload([item])[0]
        self.assertEqual(result['proton_matches'],[(1.23,1.23,0)])
        self.assertEqual(result['carbon_matches'],[(18.7,18.7,0)])
        self.assertNotIn(PRIVATE,str(result))

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
        import copy
        changed=copy.deepcopy(packet)
        next(e for e in changed['entries'] if e['candidate_id']==gps['candidate_id'])['record_id']='999'
        with self.assertRaises(ValueError):approve(changed,[decision])
