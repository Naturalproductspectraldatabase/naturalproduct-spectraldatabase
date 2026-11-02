"""Real structure-save CAS with synthetic cloud transport and disposable SQLite."""
from datetime import UTC, datetime
from pathlib import Path
import sqlite3
import tempfile
import unittest
from test_c1_c2_regressions import isolated_function


class StructureSaveConcurrencyTests(unittest.TestCase):
    def fixture(self, cloud=True):
        patches=[];events=[];invalidations=[]
        ns=dict(ensure_write_target_ready=lambda:None,use_supabase_write_backend=lambda:cloud,
                use_local_read_backend=lambda:not cloud, datetime=datetime,UTC=UTC,
                maybe_blank=lambda v:str(v or '').strip(),
                verify_compound_editor_revision=lambda *a:None,
                derive_structure_identifiers=lambda text:dict(smiles='CCO',inchi='synthetic-inchi',inchikey='synthetic-key'),
                _save_generated_structure_image=lambda *a:self.fail('curated image was replaced'),
                supabase_update_row=lambda *a,**kw:patches.append((a,kw)),
                invalidate_cached_views=lambda:invalidations.append(True),
                record_audit_event=lambda *a:events.append(a))
        save=isolated_function('save_structure_query_to_compound',ns)
        original=dict(id=1,updated_at='2026-11-03T00:00:00+00:00',smiles='',inchi='',inchikey='',
                      structure_image_path='data/structures/curated-synthetic.png')
        return ns,save,original,patches,events,invalidations

    def test_cloud_patch_uses_displayed_revision_and_preserves_image(self):
        ns,save,original,patches,_,_=self.fixture()
        self.assertTrue(save(1,'CCO',original_row=original)[0])
        args,kw=patches[0]
        self.assertEqual(kw,{'expected_updated_at':original['updated_at']})
        self.assertNotIn('structure_image_path',args[2])

    def test_missing_revision_or_wrong_record_does_no_write(self):
        ns,save,original,patches,_,_=self.fixture()
        for row in (None,dict(original,updated_at=''),dict(original,id=2)):
            self.assertFalse(save(1,'CCO',original_row=row)[0])
        self.assertEqual(patches,[])

    def test_cloud_preflight_conflict_stops_before_derivation_and_patch(self):
        ns,save,original,patches,_,_=self.fixture()
        ns['verify_compound_editor_revision']=lambda *a:(_ for _ in ()).throw(RuntimeError('synthetic conflict'))
        ns['derive_structure_identifiers']=lambda *a:self.fail('derived after preflight conflict')
        self.assertFalse(save(1,'CCO',original_row=original)[0])
        self.assertEqual(patches,[])

    def test_race_after_preflight_returns_conflict_without_cache_invalidation(self):
        ns,save,original,_,_,invalidations=self.fixture()
        ns['supabase_update_row']=lambda *a,**kw:(_ for _ in ()).throw(RuntimeError('CAS rejected'))
        self.assertFalse(save(1,'CCO',original_row=original)[0])
        self.assertEqual(invalidations,[])

    def test_unchanged_identifiers_do_not_patch_or_regenerate_assets(self):
        ns,save,original,patches,_,_=self.fixture()
        original.update(smiles='CCO',inchi='synthetic-inchi',inchikey='synthetic-key')
        self.assertTrue(save(1,'CCO',original_row=original)[0])
        self.assertEqual(patches,[])

    def test_sqlite_atomic_cas_rejects_stale_and_accepts_current_revision(self):
        ns,save,original,_,events,invalidations=self.fixture(False)
        with tempfile.TemporaryDirectory() as directory:
            db=Path(directory)/'synthetic.db'
            ns['get_connection']=lambda:sqlite3.connect(db)
            with sqlite3.connect(db) as conn:
                conn.execute('CREATE TABLE compounds (id INTEGER PRIMARY KEY, smiles TEXT, inchi TEXT, inchikey TEXT, structure_image_path TEXT, updated_at TEXT)')
                conn.execute('INSERT INTO compounds VALUES (1,?,?,?,?,?)',('newer-smiles','','',original['structure_image_path'],'newer-revision'))
            self.assertFalse(save(1,'CCO',original_row=original)[0])
            with sqlite3.connect(db) as conn:
                self.assertEqual(conn.execute('SELECT smiles FROM compounds').fetchone()[0],'newer-smiles')
            self.assertEqual(events,[]);self.assertEqual(invalidations,[])
            original['updated_at']='newer-revision'
            self.assertTrue(save(1,'CCO',original_row=original)[0])
            with sqlite3.connect(db) as conn:
                row=conn.execute('SELECT smiles, structure_image_path, updated_at FROM compounds').fetchone()
            self.assertEqual(row[0],'CCO');self.assertEqual(row[1],original['structure_image_path'])
            self.assertNotEqual(row[2],'newer-revision');self.assertEqual(len(events),1)
