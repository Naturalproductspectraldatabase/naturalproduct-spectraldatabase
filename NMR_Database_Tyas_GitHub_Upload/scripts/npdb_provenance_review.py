"""Private offline owner-review packets; no DB/network/config writes.

prepare never approves. approve consumes individually enumerated decisions after
human source/content inspection. Result is a proposed server manifest for owner
review, not a production installation. Never put real packets in public Git/CI.
"""
import argparse
from dataclasses import asdict
from datetime import datetime
import hashlib
import json
import os
from pathlib import Path
from npdb_field_access import is_protected, record_revision
from npdb_location_policy import Evidence, CLASSIFICATIONS, PUBLISHED_VERIFIED, UNKNOWN_UNVERIFIED, value_digest


def prepare(table, records):
    entries=[]
    for record in records:
        for field,value in record.items():
            if not is_protected(field,value):
                continue
            item=dict(table=table,record_id=str(record['id']),field=field,
                      record_revision=record_revision(record,table),value_sha256=value_digest(value),
                      classification=UNKNOWN_UNVERIFIED,value=value)
            item['candidate_id']=hashlib.sha256(json.dumps(item,sort_keys=True).encode()).hexdigest()
            entries.append(item)
    return dict(version=1, entries=entries, status='PROPOSED_NOT_APPROVED')


def approve(packet, decisions):
    candidates={x['candidate_id']:x for x in packet['entries']}
    if len(candidates)!=len(packet['entries']):
        raise ValueError('Duplicate candidate identifiers')
    facts=[];seen=set()
    for decision in decisions:
        candidate_id=decision['candidate_id']
        if candidate_id in seen or candidate_id not in candidates:
            raise ValueError('Unknown or duplicate enumerated decision')
        seen.add(candidate_id);candidate=candidates[candidate_id]
        if not candidate['record_revision'] or candidate['value_sha256']!=value_digest(candidate['value']):
            raise ValueError('Missing revision or changed candidate value')
        classification=decision['classification']
        if classification not in CLASSIFICATIONS:
            raise ValueError('Invalid classification')
        if classification==PUBLISHED_VERIFIED and (decision.get('verification_status')!='VERIFIED'
            or not all(str(decision.get(x,'')).strip() for x in ('verified_by','verified_at','source_reference','source_locator'))
            or decision.get('disclosure_restrictions') or decision.get('content_reviewed') is not True):
            raise ValueError('Each published field requires explicit source/content verification')
        if classification==PUBLISHED_VERIFIED:
            datetime.fromisoformat(decision['verified_at'].replace('Z','+00:00'))
        if candidate['field'] in {'file_path','image_path','structure_image_path'} and classification==PUBLISHED_VERIFIED:
            digest=decision.get('asset_sha256','')
            if len(digest)!=64 or any(c not in '0123456789abcdef' for c in digest):
                raise ValueError('Reviewed attachment bytes and metadata require a SHA256 digest')
        facts.append(asdict(Evidence(**{k:candidate[k] for k in ('table','record_id','field','record_revision','value_sha256')},
            classification=classification, verification_status=decision.get('verification_status',''),
            source_reference=decision.get('source_reference',''),source_locator=decision.get('source_locator',''),
            verified_by=decision.get('verified_by',''),verified_at=decision.get('verified_at',''),verifier_role='owner',
            disclosure_restrictions=tuple(decision.get('disclosure_restrictions',())),asset_sha256=decision.get('asset_sha256',''))))
    return dict(version=1,entries=facts)


def private_write(path,value):
    fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
    with os.fdopen(fd,'w') as stream:json.dump(value,stream,indent=2,ensure_ascii=False)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('operation',choices=('prepare','approve'))
    parser.add_argument('--input',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--table')
    parser.add_argument('--decisions',type=Path)
    args=parser.parse_args()
    data=json.loads(args.input.read_text())
    if args.operation=='prepare':
        if not args.table:parser.error('--table required')
        result=prepare(args.table,data)
    else:
        if not args.decisions:parser.error('--decisions required')
        result=approve(data,json.loads(args.decisions.read_text()))
    private_write(args.output,result)
    print(json.dumps({'status':'PRIVATE_PROPOSAL_WRITTEN','entries':len(result['entries']), 'production_applied':False}))


if __name__=='__main__':main()
