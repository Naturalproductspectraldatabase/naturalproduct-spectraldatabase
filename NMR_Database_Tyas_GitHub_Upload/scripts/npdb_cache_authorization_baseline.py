"""Reproduce frozen #63 read-boundary failures using REAL Streamlit cache + SQLite.

Success means vulnerabilities reproduced, NOT authorization acceptance. No app
startup/network/research data. Frozen source and actual auth functions are used.
"""
import ast
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
APP = ROOT/'scripts/app.py'
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
        ns=bind_authorization(role='owner')
        ns['st'].cache_data=real_st.cache_data
        ns.update(__name__='npdb_synthetic_baseline',pd=pd,DB_PATH=db,
                  get_connection=lambda:sqlite3.connect(db),get_npdb_read_backend=lambda:'local',
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
        if state!='anonymous_cold':
            assert len(ns[name](*args))==1
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
            return {'function':name,'state':state,'desired':'DENY','actual':'DENIED','security_status':'PASS'}
        return {'function':name,'state':state,'desired':'DENY','actual':'RETURNED_ROWS',
                'row_count':len(result),'security_status':'FAIL'}


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
    print('NPDB_AUTH_BASELINE_SUMMARY '+json.dumps(dict(candidate='9d81a72e397897fe1614ca98adfec254cb4f1c4f',
          trials=len(rows),unauthorized_returns=reproduced,meaning='REPRODUCTION_ONLY_NOT_SECURITY_PASS',release='BLOCKED')))
    sys.exit(0 if len(rows)==24 and reproduced==24 else 1)
