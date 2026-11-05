"""Synthetic #43 policy contract; no application, credentials, network or datasets."""
from dataclasses import replace
from pathlib import Path
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from npdb_location_policy import *


class LocationPolicyContract(unittest.TestCase):
    def setUp(self):
        self.state = Identity('owner','synthetic-revision-1')
        self.row = dict(id=1,updated_at='synthetic-record-revision',gps_coordinates='SYNTHETIC-PRECISION-00.000',
                        collection_location='SYNTHETIC-LOCALITY',depth_m=12.50,sample_code='SYNTHETIC-CODE',
                        sampling_date='SYNTHETIC-DATE',collector='SYNTHETIC-PERSON',
                        approved_broad_region='SYNTHETIC-APPROVED-REGION',note='SYNTHETIC-MIXED-TEXT',
                        publication_year='2020',delta_ppm=1.25)
        self.fact = Evidence('compounds','1','gps_coordinates',self.row['updated_at'],
            value_digest(self.row['gps_coordinates']),PUBLISHED_VERIFIED,'VERIFIED',
            'https://example.invalid/synthetic-source','synthetic table 1','synthetic-owner-review','owner')

    def policy(self, facts=()):
        return FieldPolicy(lambda:self.state,facts)

    def test_published_positive_each_role_preserves_original_precision_and_inputs(self):
        for role in ('viewer','editor','owner'):
            with self.subTest(role=role):
                self.state=Identity(role,'synthetic-revision-1')
                projected,status=self.policy([self.fact]).project_record('compounds',self.row)
                self.assertEqual(projected['gps_coordinates'],self.row['gps_coordinates'])
                self.assertTrue(status['gps_coordinates']['visible'])
                self.assertEqual(self.row['collection_location'],'SYNTHETIC-LOCALITY')

    def test_all_restricted_states_withheld_from_viewer_and_editor_owner_retains(self):
        for role in ('viewer','editor','owner'):
            for state in (INTERNAL_UNPUBLISHED,SENSITIVE_RESTRICTED,UNKNOWN_UNVERIFIED):
                with self.subTest(role=role,classification=state):
                    self.state=Identity(role,'synthetic-revision-1')
                    result,_=self.policy([replace(self.fact,classification=state)]).project_record('compounds',self.row)
                    self.assertEqual(result['gps_coordinates'],self.row['gps_coordinates'] if role=='owner' else None)

    def test_missing_metadata_never_inferred_from_doi_and_non_location_science_unchanged(self):
        self.state=Identity('viewer','synthetic-revision-1')
        self.row['doi']='10.synthetic/not-real'
        result,status=self.policy().project_record('compounds',self.row)
        self.assertIsNone(result['gps_coordinates'])
        self.assertEqual(status['gps_coordinates']['classification'],UNKNOWN_UNVERIFIED)
        self.assertEqual(result['publication_year'],'2020')
        self.assertEqual(result['delta_ppm'],1.25)

    def test_missing_stale_conflicting_incomplete_or_restricted_evidence_fails_closed(self):
        self.state=Identity('editor','synthetic-revision-1')
        invalid = [replace(self.fact,record_revision='stale'),replace(self.fact,value_sha256=value_digest('other')),
                   replace(self.fact,source_locator=''),replace(self.fact,source_reference=''),
                   replace(self.fact,verification_status=''),replace(self.fact,verified_by=''),
                   replace(self.fact,verifier_role='editor'),replace(self.fact,disclosure_restrictions=('restricted',)),
                   replace(self.fact,classification='FORGED')]
        for fact in invalid:
            with self.subTest(fact=fact):
                result,_=self.policy([fact]).project_record('compounds',self.row)
                self.assertIsNone(result['gps_coordinates'])
        for facts in ([self.fact,self.fact],[self.fact,replace(self.fact,classification=INTERNAL_UNPUBLISHED)]):
            result,_=self.policy(facts).project_record('compounds',self.row)
            self.assertIsNone(result['gps_coordinates'])

    def test_broad_region_separate_no_rounding_or_replacement(self):
        self.state=Identity('viewer','synthetic-revision-1')
        fact=replace(self.fact,field='approved_broad_region',value_sha256=value_digest(self.row['approved_broad_region']))
        result,_=self.policy([fact]).project_record('compounds',self.row)
        self.assertIsNone(result['gps_coordinates'])
        self.assertEqual(result['approved_broad_region'],self.row['approved_broad_region'])

    def test_opaque_text_requires_explicit_review_without_mutating_original(self):
        self.state=Identity('editor','synthetic-revision-1')
        result,_=self.policy().project_record('compounds',self.row,protected_fields=LOCATION_FIELDS|{'note'})
        self.assertIsNone(result['note'])
        self.assertEqual(self.row['note'],'SYNTHETIC-MIXED-TEXT')

    def test_outer_cache_guard_rechecks_auth_and_projects_copies_after_owner_warm(self):
        raw=[self.row]
        calls=[]
        def cache():
            calls.append(True)
            return raw
        policy=self.policy()
        read=policy.guard_cached_read(cache,lambda rows:[policy.project_record('compounds',r)[0] for r in rows])
        self.assertEqual(read()[0]['gps_coordinates'],self.row['gps_coordinates'])
        self.state=Identity('viewer','synthetic-revision-1')
        self.assertIsNone(read()[0]['gps_coordinates'])
        self.assertEqual(raw[0]['gps_coordinates'],self.row['gps_coordinates'])
        before=len(calls)
        for identity in (None,Identity('viewer',''),Identity('forged','revision')):
            self.state=identity
            with self.assertRaises(PermissionError):read()
        self.assertEqual(len(calls),before)

    def test_revocation_rotation_or_role_change_during_read_denies_return(self):
        for changed in (None,Identity('owner','rotated'),Identity('viewer','synthetic-revision-1')):
            self.state=Identity('owner','synthetic-revision-1')
            def cache():
                self.state=changed
                return self.row
            with self.assertRaises(PermissionError):self.policy().guard_cached_read(cache,lambda x:x)()

    def test_attachment_unknown_denied_before_io_and_reviewed_digest_checked(self):
        self.row['file_path']='SYNTHETIC-REFERENCE'
        payload=b'SYNTHETIC-ATTACHMENT'
        calls=[]
        def reader():calls.append(True);return payload
        self.state=Identity('editor','synthetic-revision-1')
        with self.assertRaises(PermissionError):self.policy().read_asset('compounds',self.row,'file_path',reader)
        self.assertFalse(calls)
        fact=replace(self.fact,field='file_path',value_sha256=value_digest(self.row['file_path']),
                     asset_sha256=__import__('hashlib').sha256(payload).hexdigest())
        for role in ('viewer','editor','owner'):
            self.state=Identity(role,'synthetic-revision-1')
            self.assertEqual(self.policy([fact]).read_asset('compounds',self.row,'file_path',reader),payload)
        self.state=Identity('viewer','synthetic-revision-1')
        with self.assertRaises(PermissionError):self.policy([fact]).read_asset('compounds',self.row,'file_path',lambda:b'CHANGED')

    def test_client_dict_evidence_rejected(self):
        with self.assertRaises(TypeError):self.policy([{'classification':PUBLISHED_VERIFIED}])


if __name__=='__main__':unittest.main()
