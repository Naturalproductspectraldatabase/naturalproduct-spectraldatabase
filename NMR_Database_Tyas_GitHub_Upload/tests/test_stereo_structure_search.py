"""Stereo-aware structure-search regression tests using synthetic molecules only.

No research records, production database, network, credentials or external files.
Use real RDKit chemistry and exact application search functions extracted by AST.
"""
import ast
import math
from pathlib import Path
import unittest

import pandas as pd
from rdkit import Chem, DataStructs
from rdkit.Chem import AllChem


APP = Path(__file__).resolve().parents[1] / "scripts" / "app.py"
SOURCE = APP.read_text(encoding="utf-8")
TREE = ast.parse(SOURCE)

ALANINE_R = "N[C@@H](C)C(=O)O"
ALANINE_S = "N[C@H](C)C(=O)O"
ALKENE_E = "F/C=C/F"
ALKENE_Z = "F/C=C\\F"


def test_namespace():
    """Keep test surface small: extract actual production chemistry functions."""
    ns = dict(
        pd=pd, math=math, Chem=Chem, DataStructs=DataStructs, AllChem=AllChem,
        maybe_blank=lambda v: str(v or "").strip(),
        is_structure_backend_available=lambda: True,
        smiles_to_mol=lambda text: Chem.MolFromSmiles(text) if text else None,
        structure_text_to_mol=lambda text: Chem.MolFromSmiles(text) if text else None,
    )
    names = (
        "canonicalize_smiles",
        "molecule_similarity_score",
        "molecule_fingerprint",
        "build_structure_candidate_index",
        "search_by_structure",
    )
    funcs = []
    for name in names:
        matches = [n for n in TREE.body if isinstance(n, ast.FunctionDef) and n.name == name]
        if len(matches) != 1:
            raise AssertionError(f"Expected one {name} function")
        node = matches[0]
        node.decorator_list = []
        funcs.append(node)
    exec(compile(ast.Module(body=funcs, type_ignores=[]), str(APP), "exec"), ns)
    return ns


class StereochemicalSearchTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.ns = test_namespace()
        cls.df = pd.DataFrame([
            {"id": 1, "trivial_name": "Synthetic alanine enantiomer A", "smiles": ALANINE_R},
            {"id": 2, "trivial_name": "Synthetic alanine enantiomer B", "smiles": ALANINE_S},
            {"id": 3, "trivial_name": "Synthetic alkene isomer E", "smiles": ALKENE_E},
            {"id": 4, "trivial_name": "Synthetic alkene isomer Z", "smiles": ALKENE_Z},
        ])

    def search(self, smiles, mode, threshold=0.35):
        return self.ns["search_by_structure"](self.df, smiles, mode, threshold)

    def test_morgan_fingerprint_distinguishes_enantiomers(self):
        m1, m2 = Chem.MolFromSmiles(ALANINE_R), Chem.MolFromSmiles(ALANINE_S)
        fp1 = self.ns["molecule_fingerprint"](m1)
        fp2 = self.ns["molecule_fingerprint"](m2)
        self.assertLess(DataStructs.TanimotoSimilarity(fp1, fp2), 1.0)
        self.assertEqual(DataStructs.TanimotoSimilarity(fp1, fp1), 1.0)
        self.assertLess(self.ns["molecule_similarity_score"](m1, m2), 1.0)

    def test_morgan_fingerprint_distinguishes_E_Z_double_bond(self):
        e, z = Chem.MolFromSmiles(ALKENE_E), Chem.MolFromSmiles(ALKENE_Z)
        fp_e = self.ns["molecule_fingerprint"](e)
        fp_z = self.ns["molecule_fingerprint"](z)
        self.assertLess(DataStructs.TanimotoSimilarity(fp_e, fp_z), 1.0)

    def test_exact_identity_preserves_enantiomer_configuration(self):
        results, err = self.search(ALANINE_R, "Identity Search")
        self.assertFalse(err)
        self.assertEqual([x["id"] for x in results], [1])

    def test_exact_identity_preserves_E_Z_configuration(self):
        results, err = self.search(ALKENE_E, "Identity Search")
        self.assertFalse(err)
        self.assertEqual([x["id"] for x in results], [3])

    def test_chiral_substructure_excludes_opposite_enantiomer(self):
        results, err = self.search(ALANINE_R, "Substructure Search")
        self.assertFalse(err)
        self.assertEqual([x["id"] for x in results], [1])

    def test_E_Z_substructure_excludes_opposite_configuration(self):
        results, err = self.search(ALKENE_E, "Substructure Search")
        self.assertFalse(err)
        self.assertEqual([x["id"] for x in results], [3])

    def test_unspecified_stereochemistry_still_allows_broad_substructure(self):
        results, err = self.search("NC(C)C(=O)O", "Substructure Search")
        self.assertFalse(err)
        self.assertEqual({x["id"] for x in results}, {1, 2})

    def test_high_similarity_threshold_excludes_opposite_stereoisomers(self):
        results, err = self.search(ALANINE_R, "Similarity Search", threshold=0.99)
        self.assertFalse(err)
        self.assertEqual([x["id"] for x in results], [1])

    def test_stereo_aware_fp_used_consistently_in_similarity_and_index(self):
        self.assertIn("useChirality=True", SOURCE)
        self.assertIn("HasSubstructMatch(query_mol, useChirality=True)", SOURCE)


if __name__ == "__main__":
    unittest.main()
