"""Synthetic structure index membership, metadata, signature and cache tests."""
import ast
import hashlib
import math
import os
from pathlib import Path
import sqlite3
import tempfile
import types
import unittest
import pandas as pd

APP = Path(__file__).resolve().parents[1] / 'scripts/app.py'


def load(ns, *names, keep_decorators=False):
    tree = ast.parse(APP.read_text())
    for name in names:
        node = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == name][-1]
        if not keep_decorators:
            node.decorator_list = []
        exec(compile(ast.Module(body=[node], type_ignores=[]), str(APP), 'exec'), ns)


class TimedCache:
    def __init__(self):
        self.now = 0
        self.calls = 0
    def cache_resource(self, *, ttl, max_entries, **kw):
        self.ttl, self.max_entries = ttl, max_entries
        def decorate(fn):
            cache = {}
            def wrapped(key):
                if key not in cache or self.now - cache[key][0] >= ttl:
                    self.calls += 1
                    cache[key] = self.now, fn(key)
                return cache[key][1]
            return wrapped
        return decorate


class StructureIndexFreshnessTests(unittest.TestCase):
    def fixture(self):
        cache = TimedCache()
        ns = dict(pd=pd, math=math, st=cache, DATA_CACHE_TTL_SECONDS=60,
                  maybe_blank=lambda v: str(v or '').strip(),
                  is_structure_backend_available=lambda: True,
                  structure_text_to_mol=lambda v: v, smiles_to_mol=lambda v: v,
                  molecule_fingerprint=lambda v: v, canonicalize_smiles=lambda v: v,
                  load_all_compounds=lambda: self.fail('index queried unfiltered database'))
        load(ns, 'build_structure_candidate_index', keep_decorators=True)
        load(ns, 'search_by_structure')
        return ns, cache

    def search(self, ns, rows, query='CCO'):
        return ns['search_by_structure'](pd.DataFrame(rows), query, 'Identity Search')

    def test_empty_filters_or_missing_ids_never_query_global_index(self):
        ns, cache = self.fixture()
        for df in (pd.DataFrame(columns=['id','smiles']),pd.DataFrame([dict(smiles='CCO')])):
            self.assertEqual(ns['search_by_structure'](df,'CCO','Identity Search')[0], [])
        self.assertEqual(cache.calls,0)

    def test_second_session_add_update_delete_visible_without_restart(self):
        ns, cache = self.fixture()
        rows=[dict(id=1,smiles='CCO',trivial_name='synthetic ethanol')]
        self.assertEqual(len(self.search(ns,rows)[0]),1)
        rows.append(dict(id=2,smiles='CCC',trivial_name='synthetic propane'))
        self.assertEqual(self.search(ns,rows,'CCC')[0][0]['id'],2)
        rows[1]['smiles']='CCN'
        self.assertEqual(self.search(ns,rows,'CCC')[0],[])
        self.assertEqual(self.search(ns,rows,'CCN')[0][0]['id'],2)
        rows.pop(1)
        self.assertEqual(self.search(ns,rows,'CCN')[0],[])

    def test_metadata_refresh_does_not_rebuild_chemistry_or_reuse_old_row(self):
        ns, cache = self.fixture()
        rows=[dict(id=1,smiles='CCO',trivial_name='old metadata')]
        self.search(ns,rows)
        rows[0]['trivial_name']='updated metadata'
        self.assertEqual(self.search(ns,rows)[0][0]['trivial_name'],'updated metadata')
        self.assertEqual(cache.calls,1)
        cache.now=60
        self.search(ns,rows)
        self.assertEqual(cache.calls,2)
        self.assertEqual(cache.max_entries,16)

    def test_invalid_modes_thresholds_and_record_ids_fail_closed(self):
        ns, cache=self.fixture()
        df=pd.DataFrame([dict(id=1,smiles='CCO')])
        for threshold in (math.nan,math.inf,-1,1.1,'invalid'):
            self.assertEqual(ns['search_by_structure'](df,'CCO','Similarity Search',threshold)[0],[])
        self.assertEqual(ns['search_by_structure'](df,'CCO','typo')[0],[])
        for value in (1.5,math.nan,math.inf,-1,'invalid'):
            self.assertEqual(self.search(ns,[dict(id=value,smiles='CCO')])[0],[])
        self.assertEqual(self.search(ns,[dict(id=1,smiles='CCO'),dict(id='1',smiles='CCC')])[0],[])


class LocalDatabaseSignatureTests(unittest.TestCase):
    def test_sqlite_wal_commit_changes_signature_without_main_mtime_change(self):
        with tempfile.TemporaryDirectory() as directory:
            db=Path(directory)/'synthetic.db'
            ns=dict(Path=Path,hashlib=hashlib,DB_PATH=db,get_npdb_read_backend=lambda:'local')
            load(ns,'get_db_signature')
            conn=sqlite3.connect(db)
            self.addCleanup(conn.close)
            conn.execute('PRAGMA journal_mode=WAL')
            conn.execute('CREATE TABLE example (id INTEGER PRIMARY KEY, note TEXT)')
            conn.commit()
            before=ns['get_db_signature']()
            stamp=db.stat().st_mtime_ns
            conn.execute("INSERT INTO example (note) VALUES ('synthetic')")
            conn.commit()
            self.assertEqual(db.stat().st_mtime_ns,stamp)
            self.assertNotEqual(before,ns['get_db_signature']())

    def test_snapshot_deletion_and_nonmax_mtime_replacement_change_signature(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            a,b=root/'a.csv',root/'b.csv'
            a.write_text('synthetic A')
            b.write_text('synthetic B')
            os.utime(a,(100,100));os.utime(b,(200,200))
            ns=dict(Path=Path,hashlib=hashlib,CSV_SNAPSHOT_DIR=root,get_npdb_read_backend=lambda:'snapshot')
            load(ns,'get_db_signature')
            before=ns['get_db_signature']()
            a.write_text('changed A');os.utime(a,(100,100))
            self.assertNotEqual(before,ns['get_db_signature']())
            before=ns['get_db_signature']()
            a.unlink()
            self.assertNotEqual(before,ns['get_db_signature']())
