"""Synthetic-first #43 policy primitive, used by the application field adapter.

Identity provider and evidence manifest are trusted server inputs, never request
role/classification claims. This module does not implement Storage/RLS or project
grants, does not infer publication from a DOI, and never writes scientific data.
"""
from copy import deepcopy
from dataclasses import dataclass
from functools import wraps
import hashlib
import hmac
import json
from typing import Callable, Mapping

PUBLISHED_VERIFIED = 'PUBLISHED_VERIFIED'
INTERNAL_UNPUBLISHED = 'INTERNAL_UNPUBLISHED'
SENSITIVE_RESTRICTED = 'SENSITIVE_RESTRICTED'
UNKNOWN_UNVERIFIED = 'UNKNOWN_UNVERIFIED'
CLASSIFICATIONS = frozenset((PUBLISHED_VERIFIED, INTERNAL_UNPUBLISHED, SENSITIVE_RESTRICTED, UNKNOWN_UNVERIFIED))
LOCATION_FIELDS = frozenset(('gps_coordinates','collection_location','depth_m','sample_code',
                             'collection_date','sampling_date','collector','approved_broad_region'))
# Integration must inventory mixed text/attachment fields separately; do not silently
# classify scientific names, publication_year or NMR acquisition dates as locations.
REVIEWABLE_OPAQUE_FIELDS = frozenset(('note','description','habitat','specimen_name','file_path',
                                     'image_path','structure_image_path','evidence_note','reference_note'))


def value_digest(value):
    encoded = json.dumps(value, ensure_ascii=False, sort_keys=True, allow_nan=False,
                         separators=(',',':')).encode('utf-8')
    return hashlib.sha256(encoded).hexdigest()


@dataclass(frozen=True)
class Identity:
    role: str
    credential_revision: str


@dataclass(frozen=True)
class Evidence:
    table: str
    record_id: str
    field: str
    record_revision: str
    value_sha256: str
    classification: str
    verification_status: str = ''
    source_reference: str = ''
    source_locator: str = ''
    verified_by: str = ''
    verifier_role: str = ''
    disclosure_restrictions: tuple = ()
    asset_sha256: str = ''
    verified_at: str = ''


class FieldPolicy:
    def __init__(self, identity_provider: Callable[[], Identity], evidence=()):
        self.identity_provider = identity_provider
        index = {}
        for item in evidence:
            if not isinstance(item, Evidence):
                raise TypeError('Evidence must be trusted typed server configuration')
            key = (item.table, item.record_id, item.field)
            index.setdefault(key, []).append(item)
        # Duplicate/conflicting approvals fail closed, including duplicate published facts.
        self._evidence = {key: tuple(items) for key, items in index.items()}

    def identity(self):
        identity = self.identity_provider()
        if (not isinstance(identity, Identity) or identity.role not in ('viewer','editor','owner')
                or not identity.credential_revision):
            raise PermissionError('Current approved authentication required')
        return identity

    def _unchanged_identity(self, original):
        current = self.identity()
        if current.role != original.role or not hmac.compare_digest(current.credential_revision, original.credential_revision):
            raise PermissionError('Current approved authentication required')

    def evidence_for(self, table, record_id, field, value, revision):
        items = self._evidence.get((table, str(record_id), field), ())
        if len(items) != 1:
            return None
        fact = items[0]
        try:
            digest = value_digest(value)
        except (TypeError, ValueError):
            return None
        if (not revision or fact.record_revision != str(revision) or
                not hmac.compare_digest(fact.value_sha256, digest) or
                fact.classification not in CLASSIFICATIONS):
            return None
        return fact

    @staticmethod
    def _published(fact):
        return bool(fact and fact.classification == PUBLISHED_VERIFIED and
                    fact.verification_status == 'VERIFIED' and fact.source_reference.strip() and
                    fact.source_locator.strip() and fact.verified_by.strip() and
                    fact.verifier_role == 'owner' and not fact.disclosure_restrictions)

    def project_record(self, table, record, *, protected_fields=LOCATION_FIELDS):
        identity = self.identity()
        result = deepcopy(dict(record))
        decisions = {}
        for field in protected_fields:
            if field not in result:
                continue
            fact = self.evidence_for(table, record.get('id'), field, record[field], record.get('updated_at'))
            classification = fact.classification if fact else UNKNOWN_UNVERIFIED
            visible = identity.role == 'owner' or self._published(fact)
            if not visible:
                result[field] = None
            decisions[field] = dict(visible=visible, classification=classification,
                                    reason='OWNER' if identity.role == 'owner' else ('PUBLISHED_VERIFIED' if visible else 'WITHHELD'))
        self._unchanged_identity(identity)
        return result, decisions

    def read_asset(self, table, record, field, reader):
        identity = self.identity()
        fact = self.evidence_for(table, record.get('id'), field, record.get(field), record.get('updated_at'))
        if identity.role != 'owner' and not (self._published(fact) and fact.asset_sha256):
            raise PermissionError('Attachment requires authorized provenance review')
        payload = reader()  # Reader must separately enforce path/HTTPS/file safety.
        if identity.role != 'owner' and not hmac.compare_digest(hashlib.sha256(payload).hexdigest(), fact.asset_sha256):
            raise PermissionError('Attachment requires authorized provenance review')
        self._unchanged_identity(identity)
        return payload

    def guard_cached_read(self, cached_reader, projector):
        """Wrap OUTSIDE cache, authorize before invocation and after projection.

        The projector must cover the complete returned DTO. This is not automatic
        SQL/alias/ZIP/EXIF protection; callers must not expose raw cached helpers.
        """
        @wraps(cached_reader)
        def read(*args, **kwargs):
            identity = self.identity()
            raw = cached_reader(*args, **kwargs)
            projected = projector(deepcopy(raw))
            self._unchanged_identity(identity)
            return projected
        return read
