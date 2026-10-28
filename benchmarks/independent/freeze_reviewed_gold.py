"""Freeze independently reviewed gold labels BEFORE held-out testing.

This does not create/approve labels. An incomplete review is rejected.
"""
import argparse
from collections import defaultdict,Counter
import hashlib
import json
from pathlib import Path


def load(path):
    return [json.loads(t) for t in path.read_text(encoding='utf-8-sig').splitlines() if t.strip()]


def digest(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def validate(retrieval,ocr):
    if len(retrieval)!=240 or len(ocr)!=45: raise ValueError('Wrong expected set sizes (240 / 45)')
    identities=set()
    family_split=defaultdict(set)
    for r in retrieval:
        if r['query_id'] in identities: raise ValueError('Duplicate query ID')
        identities.add(r['query_id'])
        if r['split'] not in ('dev','heldout') or not r['question'].strip() or not r['source_reviewed'] or not r['reviewer_id']:
            raise ValueError('Unreviewed retrieval row '+r['query_id'])
        if r['case_type']=='answerable':
            if not r['document_family'] or not r['gold_evidence_ids'] or not r['required_evidence_groups']:
                raise ValueError('Incomplete answerable evidence: '+r['query_id'])
        if r['case_type']=='verified_missing' and not r['absence_scope_verified']:
            raise ValueError('Missing case not verified for defined corpus scope '+r['query_id'])
        if r['document_family']:
            family_split[r['document_family']].add(r['split'])
    for r in ocr:
        if (not r['source_pdf_sha256'] or not r['document_family'] or r['page_number'] is None
                or not r['raw_engine_text_path'] or not r['reference_text_path']
                or not r['reference_reviewed'] or not r['reviewer_id']
                or r['scope']!='full_page'):
            raise ValueError('OCR full-page review missing: '+r['sample_id'])
        family_split[r['document_family']].add(r['split'])
    leaks=[key for key,splits in family_split.items() if len(splits)>1]
    if leaks:raise ValueError('Document family spans dev and heldout: '+', '.join(leaks[:10]))
    count=Counter((r['case_type'],r['split']) for r in retrieval)
    if count != Counter({('answerable','dev'):126,('answerable','heldout'):54,
                        ('unrelated','dev'):21,('unrelated','heldout'):9,
                        ('verified_missing','dev'):21,('verified_missing','heldout'):9}):
        raise ValueError('Invalid retrieval partition counts')
    counts=Counter(r['split'] for r in ocr)
    if counts != {'dev':30,'heldout':15}:raise ValueError('Invalid OCR partition counts')


def main():
    a=argparse.ArgumentParser()
    a.add_argument('--retrieval',type=Path,required=True)
    a.add_argument('--ocr',type=Path,required=True)
    a.add_argument('--output',type=Path,required=True)
    args=a.parse_args()
    if args.output.exists():raise ValueError('Output exists, choose new frozen manifest')
    retrieval=load(args.retrieval);ocr=load(args.ocr)
    validate(retrieval,ocr)
    manifest={'schema_version':1,'type':'independent_reviewed_gold_freeze',
              'retrieval_gold_sha256':digest(args.retrieval),
              'ocr_gold_sha256':digest(args.ocr),
              'retrieval_count':len(retrieval),'ocr_page_count':len(ocr),
              'heldout_labels_for_tuning_allowed':False,
              'source_family_leak_check':'PASS',
              'warning':'Frozen gold is reviewed separately; scoring must follow predictions.'}
    args.output.write_text(json.dumps(manifest,indent=2)+'\n',encoding='utf-8')
    print('Reviewed labels frozen:',args.output)

if __name__=='__main__':main()
