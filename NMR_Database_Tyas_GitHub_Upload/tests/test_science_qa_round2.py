"""Independent scientific QA, round 2 (stacked on draft #56). Synthetic data only; no network, credentials, Storage, database or research records.

Three kinds of test, all against the LIVE functions/source of scripts/app.py (last definition wins):
* FIX-VERIFICATION tests pass: they confirm the corrections in #52/#53/#56 behave as intended.
* CHARACTERIZATION tests pass: they pin a verified scientific limitation that remains.
* `desired` tests state the scientifically correct property; they are expected failures now. NPDB_STRICT_DESIRED=1 runs them as ordinary tests
  (each must fail by AssertionError, never by a harness error).  Fixtures are textbook/synthetic; no real compound identity is claimed.
Report: docs/science/SCIENTIFIC_QA_ROUND2_20261105.md
"""
import ast
import datetime
import hashlib
import importlib.util
import io
import json
import os
import re
import sys
import unittest
import zipfile
from pathlib import Path
from urllib.parse import unquote, urlparse

import pandas as pd

APP = Path(__file__).resolve().parents[1] / "scripts" / "app.py"
sys.path.insert(0, str(APP.parent))
SOURCE = APP.read_text(encoding="utf-8")
TREE = ast.parse(SOURCE)
HAVE_RDKIT = importlib.util.find_spec("rdkit") is not None
needs_rdkit = unittest.skipUnless(HAVE_RDKIT, "RDKit is not installed")
desired = (lambda f: f) if os.environ.get("NPDB_STRICT_DESIRED") else unittest.expectedFailure
clean_text = lambda v: "" if v is None or (isinstance(v, float) and v != v) else str(v)
maybe_blank = lambda v: "" if v is None or (isinstance(v, float) and v != v) else str(v).strip()


def source_has(text):
    return text in SOURCE


def live(name, deps):
    nodes = [n for n in TREE.body if isinstance(n, ast.FunctionDef) and n.name == name]
    assert nodes, name
    node = nodes[-1]
    node.decorator_list = []
    from authorization_fixture import bind_authorization
    namespace = bind_authorization(dict(deps), role="owner")
    exec(compile(ast.Module(body=[node], type_ignores=[]), str(APP), "exec"), namespace)
    return namespace[name]


def constant(name):
    for node in TREE.body:
        if isinstance(node, ast.Assign) and getattr(node.targets[0], "id", "") == name:
            return ast.literal_eval(node.value)
    raise KeyError(name)


if HAVE_RDKIT:
    from rdkit import Chem, DataStructs, RDLogger
    from rdkit.Chem import AllChem
    RDLogger.DisableLog("rdApp.*")
    CW, CCW = Chem.ChiralType.CHI_TETRAHEDRAL_CW, Chem.ChiralType.CHI_TETRAHEDRAL_CCW


def M(smiles):
    mol = Chem.MolFromSmiles(smiles)
    assert mol is not None, smiles
    return mol


def flip(mol, indices):
    new = Chem.Mol(mol)
    for i in indices:
        atom = new.GetAtomWithIdx(i)
        atom.SetChiralTag(CCW if atom.GetChiralTag() == CW else CW)
    Chem.AssignStereochemistry(new, cleanIt=True, force=True)
    return Chem.MolFromSmiles(Chem.MolToSmiles(new))


def centres(mol):
    return [i for i, _ in Chem.FindMolChiralCenters(mol, includeUnassigned=False, useLegacyImplementation=True)]


CHOL = "C[C@H](CCCC(C)C)[C@H]1CC[C@@H]2[C@@]1(CC[C@H]3[C@H]2CC=C4[C@@]3(CC[C@@H](C4)O)C)C"
DISACCHARIDE_LIKE = "OC[C@H]1O[C@@](CO)(O[C@H]2O[C@H](CO)[C@@H](O)[C@H](O)[C@H]2O)[C@@H](O)[C@@H]1O"
GENERATED = "storage://structures/generated/synthetic_101.png"
CURATED_STORAGE = "storage://structures/synthetic_curated_101.png"


def parse_ref():
    is_external_url = live("is_external_url", {"maybe_blank": maybe_blank, "urlparse": urlparse})
    return live("parse_supabase_storage_reference", {"maybe_blank": maybe_blank, "urlparse": urlparse, "unquote": unquote, "re": re, "is_external_url": is_external_url, "get_supabase_url": lambda: "https://synthetic.invalid"})


@needs_rdkit
class FixVerification(unittest.TestCase):
    """The corrections in #52 / #53 / #56 do what they claim (independent re-check)."""

    def test_curation_status_fails_closed_to_the_least_trusted_label(self):
        normalize = live("normalize_curation_status", {"maybe_blank": maybe_blank, "CURATION_STATUS_OPTIONS": constant("CURATION_STATUS_OPTIONS")})
        for value in (None, "", "  ", "verified", "CURATED?", float("nan")):
            self.assertEqual(normalize(value), "imported", repr(value))
        self.assertEqual([normalize(v) for v in ("curated", "Reviewed", " imported ")], ["curated", "reviewed", "imported"])

    def test_explicit_positive_outcome_never_counts_negated_or_ambiguous_text(self):
        positive = live("is_explicit_positive_outcome", {"re": re})
        for label in ("active", "Potent", "highly active", "very active"):
            self.assertTrue(positive(label), label)
        for label in ("inactive", "Inactive (IC50 > 100 uM)", "not active", "not potent", "moderately active", "weak", "", None, "selective"):
            self.assertFalse(positive(label), repr(label))

    def test_sidebar_label_describes_metadata_coverage_and_never_says_verified(self):
        self.assertTrue(source_has("{quality_pct}% with name, class &amp; source"))
        self.assertFalse(source_has("% Verified"))

    def test_entry_forms_no_longer_prefill_experimental_claims(self):
        self.assertFalse(source_has('value="CDCl3"'))
        self.assertFalse(source_has('st.text_input("Instrument (MHz)", value="500")'))
        self.assertFalse(source_has('"wizard_data_source", value="Experimental"'))

    def test_zip_manifest_origin_classification(self):
        cases = [(GENERATED, b"PNG", "embedded_generated_unverified", "generated_storage_unverified"), (GENERATED, b"", "generated_unavailable", "generated_storage_unverified"),
                 (CURATED_STORAGE, b"PNG", "embedded_registered", "registered_storage_unverified"), ("https://example.invalid/x.png", b"PNG", "embedded_registered", "registered_external_https_unverified"),
                 ("", b"", "not_registered", "not_registered")]
        for path, payload, status, origin in cases:
            with self.subTest(path=path, payload=bool(payload)):
                manifest = build_manifest(path, payload)
                self.assertEqual((manifest["structure_asset_status"], manifest["structure_asset_origin_class"]), (status, origin))

    def test_blank_potency_unit_is_disclosed_and_the_raw_unit_is_untouched(self):
        disclose = live("disclose_potency_unit_status", {"pd": pd})
        frame = pd.DataFrame([{"Value": 5.0, "Unit": ""}, {"Value": 5.0, "Unit": "uM"}, {"Value": None, "Unit": ""}])
        out = disclose(frame)
        self.assertEqual(list(out["Unit Status"]), ["Not recorded (check endpoint; may be dimensionless)", "Recorded", "No potency value"])
        self.assertEqual(list(out["Unit"]), ["", "uM", ""])

    def test_enantiomers_and_double_bond_isomers_are_no_longer_identical_in_the_live_fingerprint(self):
        fingerprint = live("molecule_fingerprint", {"AllChem": AllChem, "is_structure_backend_available": lambda: True})
        for a, b in (("N[C@@H](C)C(=O)O", "N[C@H](C)C(=O)O"), ("C/C=C/C", "C/C=C\\C")):
            self.assertLess(DataStructs.TanimotoSimilarity(fingerprint(M(a)), fingerprint(M(b))), 1.0)

    def test_nmr_labels_are_heuristic_and_coverage_is_disclosed(self):
        self.assertTrue(source_has("Heuristic NMR Rank (0–100)"))
        self.assertTrue(source_has("Registered NMR peak-list coverage"))
        for name in ("export_similarity_results_13c", "export_similarity_results_1h", "export_similarity_results_combined"):
            node = [n for n in TREE.body if isinstance(n, ast.FunctionDef) and n.name == name][-1]
            self.assertNotIn("Score (%)", ast.unparse(node), name)

    def test_structure_similarity_export_still_labels_a_tanimoto_value_as_a_percentage_score(self):
        """#53 left structural labels unchanged: a chirality-aware Tanimoto x 100 is shown as 'Score (%)' / 'Top Similarity / Match'."""
        self.assertTrue(source_has('"Score (%)": round(float(item.get("structure_score", 0.0)), 2)'))
        self.assertTrue(source_has("Top Similarity / Match") and source_has("{top_score:.1f}%"))


def build_manifest(path, payload):
    env = {"pd": pd, "io": io, "zipfile": zipfile, "json": json, "hashlib": hashlib, "datetime": datetime.datetime, "UTC": datetime.timezone.utc,
           "_archive_safe_name": lambda *a, **k: "synthetic", "clean_text": clean_text, "maybe_blank": maybe_blank,
           "_important_metadata_dataframe": lambda row: pd.DataFrame([{"Field": "Compound", "Value": "synthetic"}]),
           "_important_bioactivity_dataframe": lambda frame: frame.copy(), "_select_existing_columns": lambda frame, cols: frame.reindex(columns=cols).copy(),
           "build_compound_summary_text": lambda *a: b"SYNTHETIC", "_dataframes_to_record_workbook": lambda _: b"SYNTHETIC WORKBOOK",
           "_compound_structure_asset": lambda row: (payload, ".png" if payload else ""),
           "is_generated_structure_reference": live("is_generated_structure_reference", {"parse_supabase_storage_reference": parse_ref()})}
    bundle = live("build_compound_record_bundle", env)
    compound = pd.DataFrame([{"id": 101, "trivial_name": "synthetic", "structure_image_path": path}])
    data, _ = bundle(compound, pd.DataFrame(), pd.DataFrame(), pd.DataFrame(), pd.DataFrame())
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        return json.loads(z.read("manifest.json"))


@needs_rdkit
class StereoSearchLimitations(unittest.TestCase):
    """What chirality-aware Morgan fingerprints (the app's live configuration) can and cannot do."""

    def setUp(self):
        self.fingerprint = live("molecule_fingerprint", {"AllChem": AllChem, "is_structure_backend_available": lambda: True})
        self.sim = lambda a, b: DataStructs.TanimotoSimilarity(self.fingerprint(a), self.fingerprint(b))

    def test_some_single_centre_epimers_are_indistinguishable_even_with_chirality_aware_fingerprints(self):
        for smiles in (CHOL, DISACCHARIDE_LIKE):
            mol, blind = M(smiles), []
            for i in centres(mol):
                epimer = flip(mol, [i])
                self.assertNotEqual(Chem.MolToSmiles(epimer), Chem.MolToSmiles(mol), "the epimer is a genuinely different isomer")
                if self.sim(mol, epimer) == 1.0:
                    blind.append(i)
            self.assertTrue(blind, f"expected at least one blind centre; got none for {smiles[:20]}")

    @desired
    def test_desired_every_single_centre_epimer_is_distinguishable_by_the_fingerprint(self):
        mol = M(CHOL)
        self.assertTrue(all(self.sim(mol, flip(mol, [i])) < 1.0 for i in centres(mol)))

    def test_exact_isomeric_identity_does_distinguish_what_the_fingerprint_cannot(self):
        mol = M(CHOL)
        for i in centres(mol):
            self.assertNotEqual(Chem.MolToSmiles(flip(mol, [i])), Chem.MolToSmiles(mol))
            self.assertNotEqual(Chem.MolToInchiKey(flip(mol, [i])).split("-")[1], Chem.MolToInchiKey(mol).split("-")[1])

    def test_enantiomers_remain_well_above_zero_and_pass_the_default_threshold(self):
        mol = M(CHOL)
        enantiomer = flip(mol, centres(mol))
        value = self.sim(mol, enantiomer)
        self.assertGreater(value, 0.35, "the default minimum similarity (35) would still return the enantiomer")
        self.assertLess(value, 1.0)

    def test_a_stereo_free_query_scores_the_correct_record_no_higher_than_its_enantiomer(self):
        for smiles in (CHOL, DISACCHARIDE_LIKE):
            mol = M(smiles)
            flat = Chem.Mol(mol)
            Chem.RemoveStereochemistry(flat)
            flat = Chem.MolFromSmiles(Chem.MolToSmiles(flat, isomericSmiles=False))
            to_correct, to_enantiomer = self.sim(flat, mol), self.sim(mol, flip(mol, centres(mol)))
            self.assertLess(to_correct, 0.6, "recall regression: the correct record is far from a stereo-free query")
            self.assertAlmostEqual(to_correct, to_enantiomer, delta=0.06)
        flat_disaccharide = Chem.MolFromSmiles(Chem.MolToSmiles(M(DISACCHARIDE_LIKE), isomericSmiles=False))
        self.assertLess(self.sim(flat_disaccharide, M(DISACCHARIDE_LIKE)), 0.35, "below the default threshold: the correct compound is not returned")

    @desired
    def test_desired_search_offers_connectivity_level_similarity_for_stereo_free_queries(self):
        self.assertTrue(re.search(r"ignore stereo|connectivity similarity|stereo-free|without stereo", SOURCE, re.I))

    @desired
    def test_desired_hits_state_their_stereo_relationship_to_the_query(self):
        self.assertTrue(re.search(r"enantiomer|diastereomer|epimer", SOURCE, re.I))

    def test_regioisomers_are_distinct_but_highly_similar_and_share_a_formula(self):
        a, b = M("Brc1ccc2[nH]ccc2c1"), M("Brc1ccc2cc[nH]c2c1")
        self.assertNotEqual(Chem.MolToSmiles(a), Chem.MolToSmiles(b))
        self.assertEqual(AllChem.CalcMolFormula(a), AllChem.CalcMolFormula(b))
        self.assertGreater(self.sim(a, b), 0.6)

    @desired
    def test_desired_search_results_flag_constitutional_isomers_of_the_query(self):
        self.assertTrue(re.search(r"constitutional isomer|regioisomer|same formula", SOURCE, re.I))

    def test_specified_stereo_substructure_query_excludes_candidates_with_unspecified_stereo(self):
        specified, unspecified = M("C[C@H](O)CCC"), M("CC(O)CCC")
        same, opposite, flat = M("C[C@H](O)CC"), M("C[C@@H](O)CC"), M("CC(O)CC")
        self.assertTrue(source_has("HasSubstructMatch(query_mol, useChirality=True)"))
        self.assertEqual([specified.HasSubstructMatch(q, useChirality=True) for q in (same, opposite, flat)], [True, False, True])
        self.assertEqual([unspecified.HasSubstructMatch(q, useChirality=True) for q in (same, opposite, flat)], [False, False, True],
                         "a stereo-specified query finds no incompletely-specified record (policy decision for curators)")

    def test_chirality_aware_fingerprint_is_invariant_to_atom_order_spelling_molblock_and_inchi(self):
        import random
        from rdkit.Chem import rdDepictor
        mol, rng = M(CHOL), random.Random(7)
        base = self.fingerprint(mol)
        for _ in range(10):
            order = list(range(mol.GetNumAtoms()))
            rng.shuffle(order)
            self.assertEqual(self.fingerprint(Chem.RenumberAtoms(mol, order)), base)
            self.assertEqual(self.fingerprint(M(Chem.MolToSmiles(mol, doRandom=True))), base)
        rdDepictor.Compute2DCoords(mol)
        self.assertEqual(self.fingerprint(Chem.MolFromMolBlock(Chem.MolToMolBlock(mol))), base)
        self.assertEqual(self.fingerprint(Chem.MolFromInchi(Chem.MolToInchi(M(CHOL)))), base)


class NmrInputAndQuality(unittest.TestCase):
    """Uploaded peak files, unassigned peaks and NMR-vs-formula plausibility."""

    @staticmethod
    def upload(name, text):
        ns = {"re": re, "Path": Path, "maybe_blank": maybe_blank, "math": __import__("math"), "decode_uploaded_text": lambda f: f.text}
        ns["parse_peak_input"] = live("parse_peak_input", ns)
        parse = live("parse_peak_upload", ns)

        class Upload:
            pass
        item = Upload()
        item.name, item.text = name, text
        return parse(item)[0]

    XYDATA = "##TITLE=S\n##JCAMP-DX=5.01\n##DATA TYPE=NMR SPECTRUM\n##XUNITS=HZ\n##XYDATA=(X++(Y..Y))\n3000 10 20 30 40\n2000 50 60 70 80\n##END=\n"
    HZ_TABLE = "##TITLE=S\n##DATA TYPE=NMR PEAK TABLE\n##XUNITS=HZ\n##.OBSERVE FREQUENCY=500.0\n##PEAK TABLE=(XY..XY)\n3630, 100\n3425, 50\n##END=\n"
    XYW_TABLE = "##TITLE=S\n##PEAK TABLE=(XYW..XYW)\n7.26, 100, 0.01\n6.85, 50, 0.02\n##END=\n"

    def test_jcamp_processed_spectrum_returns_intensities_as_peak_positions(self):
        self.assertEqual(self.upload("s.jdx", self.XYDATA), [3000.0, 20.0, 40.0, 2000.0, 60.0, 80.0])

    def test_jcamp_hertz_values_are_returned_as_if_they_were_ppm(self):
        self.assertEqual(self.upload("p.jdx", self.HZ_TABLE), [3630.0, 3425.0], "true shifts are 7.26 and 6.85 ppm")

    def test_jcamp_peak_widths_are_returned_as_peaks(self):
        self.assertEqual(self.upload("w.jdx", self.XYW_TABLE), [7.26, 0.01, 6.85, 0.02])

    @desired
    def test_desired_processed_spectra_are_rejected_not_converted_into_peaks(self):
        self.assertNotEqual(len(self.upload("s.jdx", self.XYDATA)), 6)

    @desired
    def test_desired_hertz_peak_tables_are_converted_with_the_observe_frequency_or_rejected(self):
        self.assertTrue(all(abs(x - y) < 0.01 for x, y in zip(self.upload("p.jdx", self.HZ_TABLE), [7.26, 6.85])))

    @desired
    def test_desired_peak_widths_are_never_returned_as_peaks(self):
        self.assertEqual(self.upload("w.jdx", self.XYW_TABLE), [7.26, 6.85])

    def test_unassigned_peak_lists_cannot_be_stored(self):
        self.assertGreaterEqual(SOURCE.count('st.error("Assignment is required.")'), 4)
        self.assertTrue(source_has("delta_ppm and assignment are required."))

    @desired
    def test_desired_peaks_can_be_stored_as_explicitly_unassigned(self):
        self.assertLess(SOURCE.count('st.error("Assignment is required.")'), 4)

    def test_no_nmr_plausibility_or_formula_consistency_validator_exists(self):
        names = [n.name for n in TREE.body if isinstance(n, ast.FunctionDef) and re.search(r"formula|consisten|plausib|qc_", n.name, re.I) and re.search(r"nmr|peak|shift|proton|carbon", n.name, re.I)]
        self.assertEqual(names, [])

    @desired
    def test_desired_nmr_entries_are_checked_against_the_molecular_formula(self):
        names = [n.name for n in TREE.body if isinstance(n, ast.FunctionDef) and re.search(r"formula|consisten|plausib|qc_", n.name, re.I) and re.search(r"nmr|peak|shift|proton|carbon", n.name, re.I)]
        self.assertTrue(names)

    def test_exact_zero_tolerance_still_matches_values_that_are_not_equal(self):
        from npdb_peak_matching import optimal_nmr_peak_matches
        self.assertEqual(len(optimal_nmr_peak_matches([0.0], [5e-13], 0.0)), 1)

    @desired
    def test_desired_zero_tolerance_means_equality_at_reporting_precision(self):
        from npdb_peak_matching import optimal_nmr_peak_matches
        self.assertEqual(len(optimal_nmr_peak_matches([0.0], [5e-13], 0.0)), 0)


class BioactivityAndLabels(unittest.TestCase):
    def test_recorded_unit_is_not_validated_against_the_endpoint(self):
        disclose = live("disclose_potency_unit_status", {"pd": pd})
        out = disclose(pd.DataFrame([{"Metric": "IC50", "Value": 5.0, "Unit": "%"}, {"Metric": "Zone of Inhibition", "Value": 14.0, "Unit": "uM"}]))
        self.assertEqual(list(out["Unit Status"]), ["Recorded", "Recorded"], "a percent unit on an IC50 and a molar unit on a zone size are both 'Recorded'")

    @desired
    def test_desired_unit_status_does_not_call_an_incompatible_unit_recorded_without_qualification(self):
        disclose = live("disclose_potency_unit_status", {"pd": pd})
        out = disclose(pd.DataFrame([{"Metric": "IC50", "Value": 5.0, "Unit": "%"}]))
        self.assertNotEqual(out["Unit Status"].iloc[0], "Recorded")

    def test_unit_dropdown_offers_millimetre_but_not_millimolar(self):
        units = constant("DEFAULT_POTENCY_UNITS")
        self.assertIn("mm", units)
        self.assertNotIn("mM", units)
        self.assertNotIn("M", units)

    @desired
    def test_desired_unit_vocabulary_contains_millimolar(self):
        self.assertIn("mM", constant("DEFAULT_POTENCY_UNITS"))

    def test_relation_defaults_to_equals_and_outcome_is_free_text_without_an_untested_state(self):
        self.assertTrue(source_has('potency_relation = st.selectbox("Relation", ["=", "<", "<=", ">", ">=", "~"], index=0)'))
        self.assertTrue(source_has('outcome = st.text_input("Outcome", placeholder="e.g. active, inactive, moderate, selective")'))
        self.assertFalse(re.search(r"not tested|untested|not assayed", SOURCE, re.I))

    @desired
    def test_desired_outcome_vocabulary_distinguishes_inactive_from_not_tested(self):
        self.assertTrue(re.search(r"not tested|untested|not assayed", SOURCE, re.I))

    def test_completeness_percentage_is_presence_only_and_counts_generated_images(self):
        score = live("calculate_completeness_score", {"pd": pd, "maybe_blank": maybe_blank})
        junk = {"trivial_name": "x", "molecular_formula": "?", "smiles": "not a smiles", "compound_class": "x", "source_category": "x", "data_source": "x",
                "hrms_data": "n/a", "doi": "x", "structure_image_path": GENERATED}
        peaks = pd.DataFrame([{"delta_ppm": 1.0}])
        self.assertEqual(score(pd.Series(junk), peaks, peaks, peaks), 100, "unparseable SMILES, placeholder formula/HRMS and a generated image still give 100 %")

    @desired
    def test_desired_completeness_never_reaches_100_for_unvalidated_content(self):
        score = live("calculate_completeness_score", {"pd": pd, "maybe_blank": maybe_blank})
        junk = {"trivial_name": "x", "molecular_formula": "?", "smiles": "not a smiles", "compound_class": "x", "source_category": "x", "data_source": "x",
                "hrms_data": "n/a", "doi": "x", "structure_image_path": GENERATED}
        peaks = pd.DataFrame([{"delta_ppm": 1.0}])
        self.assertLess(score(pd.Series(junk), peaks, peaks, peaks), 100)

    def test_formula_mass_and_inchikey_format_of_stored_records_are_never_validated(self):
        for needle in ("CalcMolFormula", "ExactMolWt", "MolWt(", "rdMolDescriptors"):
            self.assertFalse(source_has(needle), needle)

    def test_viewer_text_describes_the_whole_database_as_curated(self):
        self.assertTrue(source_has("Open curated compound dossiers and linked spectra."))
        self.assertTrue(source_has("A read-only workspace for curated records."))

    @desired
    def test_desired_viewer_text_does_not_claim_curation_for_all_records(self):
        self.assertFalse(source_has("A read-only workspace for curated records."))

    def test_exports_carry_no_licence_citation_or_version_information(self):
        manifest = build_manifest("", b"")
        self.assertFalse([k for k in manifest if re.search(r"licen|citation|cite|doi|version|release|attribution", k, re.I)])
        self.assertTrue(source_has('OWNER_CREDIT = "©'), "the only attribution in exports is an owner credit line")

    @desired
    def test_desired_manifest_states_licence_citation_and_export_version(self):
        manifest = build_manifest("", b"")
        self.assertTrue([k for k in manifest if re.search(r"licen|citation|cite|version|attribution", k, re.I)])


if __name__ == "__main__":
    unittest.main()
