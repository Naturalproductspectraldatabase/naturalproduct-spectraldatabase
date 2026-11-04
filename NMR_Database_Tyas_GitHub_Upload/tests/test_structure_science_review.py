"""Synthetic RDKit characterization for Claude's C13/C14 review; no normalization."""
import importlib.util
import math
from pathlib import Path
import unittest
import pandas as pd
from test_structure_index_freshness import load

HAS_RDKIT = importlib.util.find_spec('rdkit') is not None


@unittest.skipUnless(HAS_RDKIT, 'RDKit required; dedicated science CI installs pinned version')
class StructureScienceReviewTests(unittest.TestCase):
    def fixture(self, smiles):
        from rdkit import Chem, DataStructs, RDLogger
        from rdkit.Chem import AllChem
        RDLogger.DisableLog('rdApp.*')
        ns=dict(Chem=Chem,DataStructs=DataStructs,AllChem=AllChem,pd=pd,math=math,
                maybe_blank=lambda v:str(v or '').strip(),
                ensure_rdkit_loaded=lambda:True,is_structure_backend_available=lambda:True,
                is_inchikey_like=lambda v:False,
                resolve_inchikey_to_smiles=lambda v:self.fail('network resolver forbidden'))
        load(ns,'smiles_to_mol','structure_text_to_mol','canonicalize_smiles',
             'molecule_similarity_score','molecule_fingerprint','build_structure_candidate_index',
             'search_by_structure','derive_structure_identifiers')
        rows=[dict(id=i+1,smiles=s,trivial_name=f'synthetic-{i}') for i,s in enumerate(smiles)]
        return ns,pd.DataFrame(rows)

    def test_stereo_exact_distinguishes_enantiomer_and_unspecified_stereo(self):
        ns,df=self.fixture(['C[C@H](O)C(=O)O','C[C@@H](O)C(=O)O','CC(O)C(=O)O'])
        matches,_=ns['search_by_structure'](df,df.iloc[0]['smiles'],'Identity Search')
        self.assertEqual([m['id'] for m in matches],[1])

    def test_fingerprint_similarity_distinguishes_stereo_but_is_not_identity(self):
        ns,df=self.fixture(['C[C@H](O)C(=O)O','C[C@@H](O)C(=O)O'])
        a,b=[ns['smiles_to_mol'](s) for s in df['smiles']]
        stereo_score=ns['molecule_similarity_score'](a,b)
        self.assertGreater(stereo_score,0.0)
        self.assertLess(stereo_score,1.0)
        self.assertEqual(ns['molecule_similarity_score'](a,a),1.0)
        self.assertNotEqual(ns['canonicalize_smiles'](df.iloc[0]['smiles']),
                            ns['canonicalize_smiles'](df.iloc[1]['smiles']))

    def test_salts_charges_and_tautomers_are_not_silently_merged(self):
        for pair in [('CC(=O)O','CC(=O)[O-].[Na+]'),('CC(=O)C','C=C(O)C')]:
            ns,df=self.fixture(pair)
            matches,_=ns['search_by_structure'](df,pair[0],'Identity Search')
            self.assertEqual([m['id'] for m in matches],[1])

    def test_derived_full_keys_preserve_stereo_and_original_input(self):
        ns,df=self.fixture(['C[C@H](O)C(=O)O','C[C@@H](O)C(=O)O','CC(=O)[O-].[Na+]'])
        original=df.copy(deep=True)
        identifiers=[ns['derive_structure_identifiers'](s) for s in df['smiles']]
        self.assertEqual(len({v['inchikey'] for v in identifiers}),3)
        for value in identifiers:
            self.assertEqual(value['inchikey'],ns['Chem'].InchiToInchiKey(value['inchi']))
        pd.testing.assert_frame_equal(df,original)

    def test_invalid_structure_is_not_turned_into_identity(self):
        ns,df=self.fixture(['CCO','invalid-synthetic-structure'])
        self.assertIsNone(ns['derive_structure_identifiers']('invalid-synthetic-structure'))
        matches,_=ns['search_by_structure'](df,'CCO','Identity Search')
        self.assertEqual([m['id'] for m in matches],[1])
