"""Issue 43 disclosure adapter. No database writes, publication inference or URL revocation.

Only server configuration supplies Evidence. Receipts are ephemeral, process-local,
value-bound context, never an authorization decision: every use rechecks identity
and the current manifest. No supplied DataFrame.attrs or request role is trusted.
"""
from contextvars import ContextVar
from copy import deepcopy
import hashlib
import hmac
import json
import math
import re
import secrets
from urllib.parse import urlparse

from npdb_location_policy import Evidence, FieldPolicy, UNKNOWN_UNVERIFIED, value_digest

READ_DEPTH = ContextVar('npdb_private_read_depth', default=0)
ASSET_IO = ContextVar('npdb_reviewed_asset_io', default=False)
_RECEIPT_KEY = secrets.token_bytes(32)
_RECEIPT = '_npdb_field_context_v1'


def key(value):
    return re.sub('[^a-z0-9]', '', str(value).casefold())

# Explicit aliases describe field names, not scientific/taxonomic synonyms.
ALIASES = {}
for canonical, labels in {
    'gps_coordinates': ('GPS', 'GPS Coordinates', 'latitude', 'longitude', 'coordinates', 'lat', 'lon', 'lng'),
    'collection_location': ('Collection Location', 'collection_locality', 'locality', 'location', 'site', 'sampling_location'),
    'depth_m': ('Depth', 'Depth (m)', 'collection_depth', 'sampling_depth'),
    'sample_code': ('Sample Code', 'specimen_code', 'internal_sample_code'),
    'sampling_date': ('Sampling Date',),
    'collection_date': ('Collection Date',),
    'collector': ('Collector', 'collector_identity', 'collected_by'),
    'note': ('Note', 'Notes', 'Residue / Note', 'residue_note'),
    'source_material': ('Source Material', 'Source Summary', 'source_summary'),
    'structure_image_path': ('Structure Image Link', 'structure_path'),
    'file_path': ('Cloud Link', 'file_name', 'filename', 'file_path', 'attachment_path'),
    'image_path': ('image_path',),
    'specimen_name': ('specimen_name',),
    'approved_broad_region': ('approved_broad_region',),
}.items():
    for label in (canonical, *labels):
        ALIASES[key(label)] = canonical

# Explicit scientific/schema outputs allowed without treating every string as
# location provenance. Opaque metadata and unknown columns are withheld below.
SCIENTIFIC = {key(v) for v in """id compound_id specimen_id proton_id carbon_id
trivial_name iupac_name molecular_formula molecular_weight smiles inchi inchikey
compound_class compound_subclass source_category source_organism scientific_name
specimen_type curation_status created_at updated_at journal_name article_title
publication_year volume issue pages doi ccdc_number data_source
uv_data ftir_data cd_data optical_rotation melting_point crystallization_method hrms_data
spectrum_type delta_ppm multiplicity j_value proton_count carbon_type assignment
solvent instrument_mhz acquisition_date activity_label target_name target_category
assay_type potency_type potency_relation potency_value potency_unit outcome assay_medium
selectivity assay_source extract_type
rank score total_score match_count total_query db_peak_count query_coverage db_coverage avg_difference
proton_match_count proton_total_query proton_query_coverage proton_score
carbon_match_count carbon_total_query carbon_query_coverage carbon_score
atom_number atom_label carbon_number proton_number query_peaks matched_peaks db_peaks missing_peaks
proton_matches carbon_matches proton_db_peak_count carbon_db_peak_count proton_db_coverage carbon_db_coverage proton_avg_difference carbon_avg_difference
matched_pairs query_coverage_percent db_coverage_percent difference delta formula name count n total Field Mr Category Percentage
proton carbon structures spectra bioactivity compounds proton_nmr carbon_nmr spectra_files bioactivity_records specimens
specimen_compounds specimen_1h_extracts proton_peaks carbon_peaks mol fp fingerprint matches
structure_score structure_match_type matched_smiles identity_relationship stereochemical_relationship stereo_relationship
""".split()}
SCIENTIFIC |= {key(v) for v in (
    'Compound ID','Specimen ID','Trivial Name','IUPAC Name','Molecular Formula','Molecular Weight',
    'Compound Class','Compound Subclass','Source Category','Source Organism','Scientific Name','Specimen Type',
    'Curation Status','Journal Name','Article Title','Publication Year','Data Source','CCDC',
    'Bioactivity ID','Spectra File ID','Spectrum Type','Activity','Target','Target Category','Assay Type','Metric','Relation','Value','Unit',
    'Outcome','Selectivity','Unit Status','Assay Medium','Assay Source','Matched Peaks','Query Peaks','DB Peaks',
    'Query Coverage (%)','DB Coverage (%)','Average Difference','Heuristic NMR Rank (0–100)',
    '1H Matched Peaks','1H Query Peaks','1H Query Coverage (%)','1H Heuristic Rank (0–100)',
    '13C Matched Peaks','13C Query Peaks','13C Query Coverage (%)','13C Heuristic Rank (0–100)',
    'Combined Heuristic Rank (0–100)','Similarity (%)','Score (%)','Structure Relationship',
    'UV Data','FTIR Data','CD / ECD Data','Optical Rotation','Melting Point','HRMS Data',
    'δH (ppm)','δC (ppm)','J (Hz)','J Value','Proton Count','Carbon Type','Instrument (MHz)',
)}

CONTAINERS = {'payload','nested','metadata','records','attachments','compound','specimen','provenance'}

OPAQUE = {key(v) for v in ('note','description','habitat','traits','color','texture','evidence_note','reference_note','observed_features','source_material','source_summary','specimen_name','file_path','image_path','structure_image_path','extract_label','assay_source','assay_medium','selectivity')}


def canonical(label, aliases=None):
    return (aliases or {}).get(str(label), ALIASES.get(key(label), str(label)))


def is_protected(label, value=None, aliases=None):
    name = canonical(label, aliases)
    normalized = key(name)
    return normalized in OPAQUE or normalized in {key(v) for v in ALIASES.values()} or normalized not in SCIENTIFIC


def plain(value):
    if isinstance(value, dict):
        return {str(k): plain(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [plain(v) for v in value]
    if value is None or (isinstance(value, float) and not math.isfinite(value)):
        return None
    if hasattr(value, 'item'):
        return plain(value.item())
    if isinstance(value, (str, int, float, bool)):
        return value
    return str(value)


def infer_table(record):
    fields = {key(k) for k in record}
    if 'scientificname' in fields or 'specimenname' in fields:
        return 'specimens'
    if 'deltappm' in fields:
        return 'proton_nmr' if 'multiplicity' in fields or 'protoncount' in fields else 'carbon_nmr'
    if 'spectrumtype' in fields:
        return 'spectra_files'
    if 'potencyvalue' in fields or 'activitylabel' in fields:
        return 'bioactivity_records'
    if 'evidencenote' in fields:
        return 'specimen_compounds'
    if 'observedfeatures' in fields:
        return 'specimen_1h_extracts'
    return 'compounds' if fields & {'smiles','molecularformula','compoundclass','compoundid','trivialname'} else ''


# Legacy child tables have no updated_at. Bind approvals to the complete base
# row, excluding joined display columns. Partial rows cannot claim this revision.
REVISION_FIELDS = {
    'spectra_files': 'id compound_id spectrum_type file_path note'.split(),
    'proton_nmr': 'id compound_id delta_ppm multiplicity j_value proton_count assignment solvent instrument_mhz note'.split(),
    'carbon_nmr': 'id compound_id delta_ppm carbon_type assignment solvent instrument_mhz note'.split(),
    'bioactivity_records': 'id compound_id activity_label target_name target_category assay_type potency_type potency_relation potency_value potency_unit outcome assay_medium selectivity assay_source note'.split(),
    'specimen_compounds': 'id specimen_id compound_id evidence_note reference_note created_at'.split(),
}


def record_revision(record, table):
    revision = record.get('updated_at')
    if revision is not None and str(revision).strip():
        return str(revision)
    fields = REVISION_FIELDS.get(table,())
    if fields and all(field in record for field in fields):
        return 'row-sha256:' + value_digest({f:plain(record[f]) for f in fields})
    return ''


def context(record, table=''):
    normalized = {key(k): v for k, v in record.items()}
    return {'table': table or infer_table(record),
            'id': str(normalized.get('id', normalized.get('compoundid', ''))),
            'revision': record_revision(record, table or infer_table(record)),
            'values': {canonical(k): plain(v) for k, v in record.items()}}


def _signature(records, contexts):
    return hmac.new(_RECEIPT_KEY, json.dumps(plain([records, contexts]), sort_keys=True, allow_nan=False, separators=(',',':')).encode(), hashlib.sha256).hexdigest()


ASSET_FIELDS = frozenset({'file_path','image_path','structure_image_path'})


def parse_asset_token(value):
    if not isinstance(value,str) or not value.startswith('npdbasset://'):
        return None
    parsed=urlparse(value)
    parts=parsed.path.strip('/').split('/')
    if (parsed.netloc not in {'compounds','specimens','spectra_files','specimen_1h_extracts'} or
            parsed.query or parsed.fragment or len(parts)!=3 or not parts[0].isdigit() or
            parts[1] not in ASSET_FIELDS or not re.fullmatch('[0-9a-f]{64}',parts[2])):
        return None
    return parsed.netloc,*parts


class Disclosure:
    def __init__(self, policy):
        self.policy = policy

    def fact(self, field, value, ctx):
        token=parse_asset_token(value)
        if token:
            table,record_id,token_field,digest=token
            items=self.policy._evidence.get((table,record_id,field),())
            if (table!=ctx.get('table') or record_id!=ctx.get('id') or token_field!=field or len(items)!=1):
                return None
            fact=items[0]
            return fact if fact.record_revision==ctx.get('revision') and fact.asset_sha256==digest else None
        return self.policy.evidence_for(ctx.get('table',''),ctx.get('id',''),field,value,ctx.get('revision',''))

    def visible(self, field, value, ctx):
        fact = self.fact(field,value,ctx)
        if field in ASSET_FIELDS and (not fact or not re.fullmatch(r"[0-9a-f]{64}",fact.asset_sha256)):
            return False
        return self.policy._published(fact)

    def asset_reference(self, field, value, ctx):
        fact=self.fact(field,value,ctx)
        return f"npdbasset://{fact.table}/{fact.record_id}/{field}/{fact.asset_sha256}"

    def record(self, record, ctx=None, aliases=None):
        identity = self.policy.identity()
        if identity.role == 'owner':
            result = deepcopy(record)
            self.policy._unchanged_identity(identity)
            return result
        ctx = ctx or context(record)
        result = {}
        vertical = 'Field' in record and 'Value' in record
        for label, value in record.items():
            field = canonical(record['Field'] if vertical and label == 'Value' else label, aliases)
            known = key(field) in SCIENTIFIC or key(field) in OPAQUE or key(field) in {key(v) for v in ALIASES.values()} or key(field) in CONTAINERS
            if not known:
                if vertical and label == 'Value':result[label]=None
                continue
            explicit = (ctx.get('table',''),ctx.get('id',''),field) in self.policy._evidence
            original = ctx.get('values',{}).get(field,value)
            if explicit and not self.visible(field,original,ctx):
                result[label] = 'withheld://provenance-review' if field=='structure_image_path' and value else None
                continue
            if vertical and label == 'Field':
                # A user-supplied metadata label can itself contain private text.
                result[label] = record[label] if key(record[label]) in SCIENTIFIC or key(record[label]) in {key(x) for x in ALIASES.values()} or key(record[label]) in OPAQUE else 'Withheld field'
            elif isinstance(value, (dict,list,tuple)):
                if is_protected(field,value,aliases) and key(field) not in CONTAINERS:
                    result[label] = deepcopy(value) if self.visible(field,value,ctx) else None
                else:
                    def nested(item):
                        if isinstance(item,dict):return self.record(item,aliases=aliases)
                        if isinstance(item,list):return [nested(v) for v in item]
                        if isinstance(item,tuple):return tuple(nested(v) for v in item)
                        return deepcopy(item)
                    result[label] = nested(value)
            elif is_protected(field, value, aliases):
                original = ctx.get('values',{}).get(field, value)
                same = plain(original) == plain(value) or str(original).strip() == str(value).strip()
                if same and self.visible(field,original,ctx):
                    result[label] = self.asset_reference(field,original,ctx) if field in ASSET_FIELDS else deepcopy(original)
                else:
                    result[label] = 'withheld://provenance-review' if field == 'structure_image_path' and value else None
            else:
                result[label] = deepcopy(value)
        self.policy._unchanged_identity(identity)
        return result

    def frame(self, frame, table='', *, source=None, contexts=None, aliases=None):
        # Import only here: the pure policy/owner manifest workflow is stdlib-only.
        records = frame.to_dict('records')
        receipt = frame.attrs.get(_RECEIPT)
        if contexts is None and isinstance(receipt,dict):
            proposed = receipt.get('contexts',[])
            if hmac.compare_digest(str(receipt.get('signature','')), _signature(records, proposed)):
                contexts = proposed
            else:
                signed_rows = receipt.get('rows',[])
                valid=[]
                for record in records:
                    matches=[r for r in signed_rows if isinstance(r,dict) and
                             hmac.compare_digest(str(r.get('signature','')), _signature(record,r.get('context',{})))]
                    if not matches:break
                    valid.append(matches[0]['context'])
                if len(valid)==len(records):
                    contexts=valid
                elif source is None and self.policy.identity().role!='owner':
                    raise PermissionError('Transformed disclosure context must be regenerated at a trusted export boundary.')
        if contexts is None and source is not None:
            contexts = self.contexts(source, table)
            by_id = {c['id']: c for c in contexts if c['id']}
            contexts = [by_id.get(context(r,table)['id'], {}) for r in records]
        if contexts is None or len(contexts) != len(records):
            contexts = [context(r, table) for r in records]
        safe = [self.record(r,c,aliases) for r,c in zip(records,contexts)]
        output = frame.copy(deep=True)
        # Assignment preserves original dtypes for scientific numeric columns.
        for index, row in enumerate(safe):
            for column, value in row.items():
                if plain(records[index].get(column)) != plain(value):
                    output[column] = output[column].astype(object)
                    output.iat[index, output.columns.get_loc(column)] = value
        contexts = [{**c, 'values': {f:v for f,v in c.get('values',{}).items() if f not in ASSET_FIELDS and self.visible(f,v,c)}} for c in contexts]
        if self.policy.identity().role!='owner':
            # Keep only named schema/approved policy/container columns. Arbitrary
            # unreviewed column labels must not become filenames or CSV headers.
            keep=[c for c in output.columns if key(canonical(c,aliases)) in SCIENTIFIC or key(canonical(c,aliases)) in OPAQUE or key(canonical(c,aliases)) in {key(v) for v in ALIASES.values()} or key(c) in CONTAINERS or c in {'Field','Value'}]
            output=output[keep].copy().reset_index(drop=True)
            output.columns.name=None
        output.attrs = {_RECEIPT: {'contexts': deepcopy(contexts), 'signature': _signature(output.to_dict('records'),contexts), 'rows':[{'context':c,'signature':_signature(r,c)} for r,c in zip(output.to_dict('records'),contexts)]}}
        return output

    def contexts(self, frame, table=''):
        receipt = frame.attrs.get(_RECEIPT)
        records = frame.to_dict('records')
        if isinstance(receipt,dict) and hmac.compare_digest(str(receipt.get('signature','')), _signature(records, receipt.get('contexts',[]))):
            return deepcopy(receipt['contexts'])
        if isinstance(receipt,dict):
            valid=[]
            for record in records:
                matches=[r for r in receipt.get('rows',[]) if isinstance(r,dict) and hmac.compare_digest(str(r.get('signature','')), _signature(record,r.get('context',{})))]
                if not matches:break
                valid.append(deepcopy(matches[0]['context']))
            if len(valid)==len(records):return valid
        return [context(r,table) for r in records]

    def payload(self, value, table='', aliases=None):
        if hasattr(value, 'to_dict') and hasattr(value, 'columns'):
            return self.frame(value,table,aliases=aliases)
        if isinstance(value, dict):
            return self.record(value,context(value,table),aliases)
        if isinstance(value,list):
            return [self.payload(v,table,aliases) for v in value]
        if isinstance(value,tuple):
            return tuple(self.payload(v,table,aliases) for v in value)
        return value


def evidence_from_config(config):
    if config is None or config == '':
        return ()
    if not isinstance(config,dict) or set(config) != {'version','entries'} or config['version'] != 1 or not isinstance(config['entries'],list) or len(config['entries']) > 10000:
        raise PermissionError('Invalid field-provenance configuration; owner review required.')
    try:
        facts=[]
        for entry in config['entries']:
            if not isinstance(entry,dict):
                raise ValueError()
            fact=Evidence(**{**entry,'disclosure_restrictions':tuple(entry.get('disclosure_restrictions',()))})
            if any(not isinstance(getattr(fact,f),str) for f in ('table','record_id','field','record_revision','value_sha256','classification','verification_status','source_reference','source_locator','verified_by','verifier_role','asset_sha256')):
                raise ValueError()
            facts.append(fact)
        return tuple(facts)
    except (TypeError,ValueError):
        raise PermissionError('Invalid field-provenance configuration; owner review required.') from None


class SealedPayload(bytes):
    """Process-local attestation; not a downloadable URL or persisted credential."""
    def __new__(cls, data, identity, policy_revision):
        value = super().__new__(cls, data)
        value.identity = tuple(identity)
        value.policy_revision = policy_revision
        value.signature = _signature(bytes(data).hex(), [list(identity), policy_revision])
        return value


def verify_payload(data, identity, revision):
    return (isinstance(data,SealedPayload) and data.identity == tuple(identity) and data.policy_revision == revision
            and hmac.compare_digest(data.signature, _signature(bytes(data).hex(), [list(identity),revision])))
