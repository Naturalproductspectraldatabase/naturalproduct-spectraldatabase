"""Reproduce frozen #63 read-boundary failures using REAL Streamlit cache + SQLite.

Success means vulnerabilities reproduced, NOT authorization acceptance. No app
startup/network/research data. Frozen source and actual auth functions are used.
"""
import ast
import os
from contextlib import closing
import hashlib
import json
from pathlib import Path
import sqlite3
import sys
import tempfile
from unittest.mock import patch

import pandas as pd
import streamlit as real_st

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tests'))
from authorization_fixture import bind_authorization
APP = Path(os.environ.get('NPDB_AUDIT_APP',str(ROOT/'scripts/app.py')))
EXPECT = os.environ.get('NPDB_AUDIT_EXPECT','baseline')
assert EXPECT in ('baseline','denial')
if EXPECT=='baseline':
    assert hashlib.sha256(APP.read_bytes()).hexdigest() == '7ab220ecbd8588e6ad08691003a59892a8eb0416cd108d50ea6b766d0c83aa33'
TREE=ast.parse(APP.read_text())


def live(name,ns):
    node=[n for n in TREE.body if isinstance(n,ast.FunctionDef) and n.name==name][-1]
    # Preserve real cache decorators; do not replace memoization or underlying SQLite.
    exec(compile(ast.Module(body=[node],type_ignores=[]),str(APP),'exec'),ns)


LOADERS=(('load_all_compounds',()),('load_compound_row',(1,)),('load_all_proton_data',()),
         ('load_all_carbon_data',()),('load_all_spectra_files',()),('_sqlite_dataframe',('SELECT * FROM compounds',)))
STATES=('anonymous_cold','logout_warm','revocation_warm','rotation_warm')


def run_case(name,args,state):
    with tempfile.TemporaryDirectory(prefix='npdb-synthetic-auth-') as temp:
        db=Path(temp)/'only-synthetic.sqlite'
        with closing(sqlite3.connect(db)) as conn:
            conn.executescript('''
              CREATE TABLE compounds(id INTEGER,trivial_name TEXT,gps_coordinates TEXT,collection_location TEXT);
              INSERT INTO compounds VALUES(1,'SYNTHETIC','SYNTHETIC-NO-COORDINATES','SYNTHETIC-NOT-A-REAL-LOCATION');
              CREATE TABLE proton_nmr(id INTEGER,compound_id INTEGER,delta_ppm REAL,multiplicity TEXT,j_value TEXT,proton_count TEXT,assignment TEXT,solvent TEXT,instrument_mhz REAL,note TEXT);
              INSERT INTO proton_nmr VALUES(1,1,1,NULL,NULL,NULL,NULL,NULL,NULL,NULL);
              CREATE TABLE carbon_nmr(id INTEGER,compound_id INTEGER,delta_ppm REAL,carbon_type TEXT,assignment TEXT,solvent TEXT,instrument_mhz REAL,note TEXT);
              INSERT INTO carbon_nmr VALUES(1,1,10,NULL,NULL,NULL,NULL,NULL);
              CREATE TABLE spectra_files(id INTEGER,compound_id INTEGER,spectrum_type TEXT,file_path TEXT,note TEXT);
              INSERT INTO spectra_files VALUES(1,1,'SYNTHETIC','SYNTHETIC-NO-FILE',NULL);
            ''')
            conn.commit()
        io_calls=[]
        def connection():
            io_calls.append(True)
            return sqlite3.connect(db)
        ns=bind_authorization(role='owner')
        ns['st'].cache_data=real_st.cache_data
        ns.update(__name__='npdb_synthetic_baseline',pd=pd,DB_PATH=db,
                  get_connection=connection,get_npdb_read_backend=lambda:'local',
                  get_db_signature=lambda:('synthetic',str(db)),
                  compound_select_columns=lambda:'id,trivial_name,gps_coordinates,collection_location',
                  enrich_compounds_dataframe=lambda x:x.copy(),
                  DATA_CACHE_TTL_SECONDS=60,SOURCE_NORMALIZATION_CACHE_VERSION='synthetic')
        for func in ('redact_private_gps_for_current_user','_sqlite_dataframe','_load_all_compounds_cached',
                     'load_all_compounds','_load_compound_row_cached','load_compound_row',
                     'load_all_proton_data','load_all_carbon_data','load_all_spectra_files'):
            live(func,ns)
        for func in ('_load_all_compounds_cached','_load_compound_row_cached','load_all_proton_data','load_all_carbon_data','load_all_spectra_files'):
            ns[func].clear()
        cache_verified=False
        if state!='anonymous_cold':
            assert len(ns[name](*args))==1
            if name!='_sqlite_dataframe':
                before=len(io_calls)
                assert len(ns[name](*args))==1
                assert len(io_calls)==before, 'Expected real cache hit before invalidation'
                target={'load_all_compounds':'_load_all_compounds_cached','load_compound_row':'_load_compound_row_cached'}.get(name,name)
                ns[target].clear()
                assert len(ns[name](*args))==1
                assert len(io_calls)>before, 'Cache clear must invalidate underlying data'
                cache_verified=True
        if state in ('anonymous_cold','logout_warm'):
            ns['st'].session_state['npdb_authenticated']=False
        elif state=='revocation_warm':
            ns['load_approved_users']=lambda:[]
        else:
            ns['load_approved_users']()[0]['password_hash']='synthetic-rotated-revision'
        assert not ns['current_backend_role']()
        try:
            result=ns[name](*args)
        except PermissionError:
            return {'function':name,'state':state,'desired':'DENY','actual':'DENIED','security_status':'PASS','cache_hit_and_clear_verified':cache_verified}
        return {'function':name,'state':state,'desired':'DENY','actual':'RETURNED_ROWS',
                'row_count':len(result),'security_status':'FAIL','cache_hit_and_clear_verified':cache_verified}


if __name__=='__main__':
    rows=[]
    with patch('urllib.request.urlopen',side_effect=AssertionError('Network forbidden')),\
         patch('socket.create_connection',side_effect=AssertionError('Network forbidden')):
        for name,args in LOADERS:
            for state in STATES:
                row=run_case(name,args,state)
                rows.append(row)
                print('NPDB_AUTH_BASELINE '+json.dumps(row),flush=True)
    reproduced=sum(row['actual']=='RETURNED_ROWS' and row.get('row_count')==1 for row in rows)
    print('NPDB_AUTH_BASELINE_SUMMARY '+json.dumps(dict(frozen_reference='9d81a72e397897fe1614ca98adfec254cb4f1c4f',tested_revision='9d81a72e397897fe1614ca98adfec254cb4f1c4f' if EXPECT=='baseline' else os.environ.get('GITHUB_SHA','WORKTREE'),
          trials=len(rows),unauthorized_returns=reproduced,expected=EXPECT,app_sha256=hashlib.sha256(APP.read_bytes()).hexdigest(),
          meaning='REPRODUCTION_ONLY_NOT_SECURITY_PASS' if EXPECT=='baseline' else 'CANDIDATE_BOUNDARY_CHECK',release='BLOCKED')))
    if EXPECT=='denial':
        mid_read_denials=0
        for state in ('logout','revocation','rotation','valid_role_swap'):
            ns=bind_authorization(role='owner')
            def reader():
                if state=='logout':ns['st'].session_state['npdb_authenticated']=False
                elif state=='revocation':ns['load_approved_users']=lambda:[]
                elif state=='rotation':ns['load_approved_users']()[0]['password_hash']='synthetic-rotated'
                else:
                    ns['load_approved_users']()[0]['role']='editor'
                    ns['st'].session_state['npdb_role']='editor'
                    ns['st'].session_state['npdb_credential_revision']=ns['configured_session_identity']()[1]
                return 'SYNTHETIC-MUST-NOT-RETURN'
            trial_denied=False
            try:
                ns['authorized_read'](reader)()
            except PermissionError:
                mid_read_denials+=1
                trial_denied=True
            print('NPDB_AUTH_MID_READ '+json.dumps(dict(state=state,security_status='PASS' if trial_denied else 'FAIL')))
        print('NPDB_AUTH_MID_READ_SUMMARY '+json.dumps(dict(trials=4,denied=mid_read_denials)))
        assert mid_read_denials==4
    denied=sum(row['actual']=='DENIED' for row in rows)
    sys.exit(0 if len(rows)==24 and ((EXPECT=='baseline' and reproduced==24) or (EXPECT=='denial' and denied==24)) else 1)
