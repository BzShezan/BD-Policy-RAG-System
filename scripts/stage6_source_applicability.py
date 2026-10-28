"""Stage 6 source-edition/applicability gate. NO index writes or authorization.

It reads the existing Stage5 receipt through stage6_import_preflight.review,
then produces a separate human source review template. Re-validation requires
exact batch binding, checked original evidence and literal extract quotes.
"""
from __future__ import annotations
import argparse
import datetime
import hashlib
import json
import re
import sys
from pathlib import Path
from urllib.parse import urlsplit

from stage6_import_preflight import review as inspect_stage5


def canonical(v):
    return json.dumps(v, sort_keys=True, ensure_ascii=False, separators=(',', ':'), allow_nan=False).encode('utf-8')


def digest(v):
    return hashlib.sha256(canonical(v)).hexdigest()


def load(path):
    path = Path(path)
    if path.is_symlink() or not path.is_file():
        raise ValueError('Missing or symlinked file: ' + str(path))
    return json.loads(path.read_text(encoding='utf-8'))


def load_stage5_texts(review_dir):
    path = Path(review_dir) / 'review_items.jsonl'
    if path.is_symlink():
        raise ValueError('Symlinked review items')
    result = {}
    for line in path.read_text(encoding='utf-8').splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        rid, value = row['id'], row['text']
        if rid in result or not isinstance(value, str):
            raise ValueError('Duplicate/bad review item')
        if hashlib.sha256(value.encode('utf-8')).hexdigest() != row['text_sha256']:
            raise ValueError('Stage5 text changed: ' + rid)
        result[rid] = value
    return result


def binding(preflight):
    return {
        'request_id': preflight['request_id'],
        'generation_at_consent': preflight['generation_at_consent'],
        'active_generation_at_prepare': preflight['active_generation_read_only'],
        'receipt_digest': preflight['receipt_digest'],
        'content_items_sha256': digest(preflight['items']),
        'approved_ids': [i['id'] for i in preflight['items'] if i['decision'] == 'approved'],
    }


def prepare(preflight):
    if preflight['status'] != 'STAGE5_CONSISTENT_IMPORT_NOT_AUTHORIZED' or preflight['blocking_integrity_issues']:
        raise ValueError('Stage5 preflight must be consistent before source review')
    items=[]
    for it in preflight['items']:
        if it['decision'] != 'approved':
            continue
        items.append({
            'id': it['id'], 'kind': it['kind'], 'source_url': it['source_url'],
            'page': it['page'], 'text_sha256': it['text_sha256'],
            'disposition': 'pending',  # pending | exclude | candidate
            'document_kind': 'unknown',  # official_policy_document | official_notice | navigation_page | other
            'program': '', 'document_date': '', 'date_evidence': '',
            'source_version_notes': '', 'applicability_notes': '',
            'verified_quote': '', 'reviewer': '',
            'original_source_opened': False, 'page_and_quote_checked': False,
            'current_policy_verified': False,
        })
    return {'schema_version':1,'purpose':'source_applicability_review_only',
            'index_import_authorized':False, 'index_writes':0,
            'stage5_binding':binding(preflight), 'items':items}


def check_date(s):
    if not isinstance(s, str) or not re.fullmatch(r'\d{4}-\d{2}-\d{2}', s):
        return False
    try:
        datetime.date.fromisoformat(s)
        return True
    except ValueError:
        return False


def validate(preflight, review_document, source_texts):
    blockers=[]; candidates=[]; excluded=[]
    if preflight.get('status') != 'STAGE5_CONSISTENT_IMPORT_NOT_AUTHORIZED':
        blockers.append('Stage5 preflight no longer consistent')
    if preflight.get('active_generation_read_only') is None:
        blockers.append('Active generation pointer must be checked')
    if not isinstance(review_document,dict) or review_document.get('schema_version') != 1 or review_document.get('purpose') != 'source_applicability_review_only':
        blockers.append('Invalid review document')
        review_document={}
    if review_document.get('index_import_authorized') is not False or review_document.get('index_writes') != 0:
        blockers.append('Unexpected index approval/write in review document')
    if review_document.get('stage5_binding') != binding(preflight):
        blockers.append('Stage5 receipt/generation/items binding mismatch')
    base={it['id']:it for it in preflight.get('items',[]) if it['decision']=='approved'}
    rows=review_document.get('items')
    if not isinstance(rows,list):
        rows=[]; blockers.append('Review items missing')
    if len({it.get('id') for it in rows if isinstance(it,dict)}) != len(rows):
        blockers.append('Duplicate or invalid reviewed ID')
    if {it.get('id') for it in rows if isinstance(it,dict)} != set(base):
        blockers.append('Every approved Stage5 item must be reviewed or explicitly excluded')
    for it in rows:
        if not isinstance(it,dict) or it.get('id') not in base:
            blockers.append('Unknown item in review');continue
        uid=it['id']; baseitem=base[uid]
        for immutable in ('kind','source_url','page','text_sha256'):
            if it.get(immutable)!=baseitem.get(immutable):
                blockers.append('Item provenance mismatch: '+uid+' / '+immutable)
        if it.get('current_policy_verified') is not False:
            blockers.append('Current-policy verification cannot be declared by this gate: '+uid)
        disposition=it.get('disposition')
        if disposition == 'exclude':
            excluded.append(uid)
            continue
        if disposition == 'pending':
            blockers.append('Unresolved source applicability item: '+uid);continue
        if disposition != 'candidate':
            blockers.append('Invalid disposition: '+uid);continue
        failures=[]
        if it.get('document_kind') not in ('official_policy_document','official_notice'):
            failures.append('not a source policy/order document')
        if not check_date(it.get('document_date')) or len(str(it.get('date_evidence') or '').strip()) < 12:
            failures.append('date or printed-date evidence is missing')
        if len(str(it.get('source_version_notes') or '').strip()) < 25:
            failures.append('source version explanation is missing')
        if len(str(it.get('applicability_notes') or '').strip()) < 25:
            failures.append('applicability/temporal-scope explanation is missing')
        if len(str(it.get('reviewer') or '').strip()) < 2 or not it.get('original_source_opened') or not it.get('page_and_quote_checked'):
            failures.append('manual original-source/page checks missing')
        if not isinstance(it.get('program'),str) or len(it['program'].strip()) < 2:
            failures.append('program not identified')
        quote=it.get('verified_quote')
        if not isinstance(quote,str) or len(quote.strip())<12 or quote not in source_texts.get(uid,''):
            failures.append('quote not a literal substring of the reviewed extraction; correction requires re-review')
        source=urlsplit(str(it.get('source_url') or ''))
        if source.scheme!='https' or not source.hostname:
            failures.append('source URL not HTTPS')
        if failures:
            blockers.extend(uid+': '+msg for msg in failures)
        else:
            candidates.append({'id':uid,'date':it['document_date'],'page':it['page'],
                              'quote_sha256':hashlib.sha256(quote.encode('utf-8')).hexdigest(),
                              'source_url':it['source_url']})
    status='BLOCKED' if blockers else ('SOURCE_REVIEW_COMPLETE_NOT_IMPORT_AUTHORIZED' if candidates else 'NO_ELIGIBLE_ITEMS')
    return {'schema_version':1,'status':status,
            'source_review_digest':digest(review_document),
            'request_id':preflight.get('request_id'),
            'active_generation_read_only':preflight.get('active_generation_read_only'),
            'candidate_proposals_count':len(candidates), 'excluded_count':len(excluded),
            'candidate_proposals':candidates, 'excluded_ids':excluded,
            'blocking_issues':blockers,
            'index_import_authorized':False,'index_writes':0,'network_calls':0,
            'current_policy_verified':False,
            'next_gate':'Independent import authorization; generation/duplicate scan; isolated paired build; consistency+benchmark; separate activation'}


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--review-dir',required=True)
    parser.add_argument('--decisions',required=True)
    parser.add_argument('--workspace',required=True)
    mode=parser.add_mutually_exclusive_group(required=True)
    mode.add_argument('--prepare',help='NEW location for manual review draft JSON')
    mode.add_argument('--validate',help='Previously filled source review JSON')
    args=parser.parse_args(argv)
    try:
        preflight=inspect_stage5(args.review_dir,args.decisions,args.workspace)
        if args.prepare:
            draft=prepare(preflight)
            target=Path(args.prepare)
            target.parent.mkdir(parents=True,exist_ok=True)
            if target.is_symlink() or target.exists():
                raise ValueError('Refusing overwrite/symlink for review draft')
            # Exclusive creation: only the user edits the draft after generation
            with target.open('x',encoding='utf-8') as h:
                json.dump(draft,h,ensure_ascii=False,indent=2)
                h.write('\n')
            print(json.dumps({'status':'DRAFT_CREATED_NOT_AUTHORIZED','draft':str(target),
                'approved_items_awaiting_review':len(draft['items']),
                'index_import_authorized':False,'index_writes':0},ensure_ascii=False,indent=2))
            return 0
        report=validate(preflight,load(args.validate),load_stage5_texts(args.review_dir))
        print(json.dumps(report,ensure_ascii=False,indent=2))
        return 0 if not report['blocking_issues'] else 2
    except Exception as exc:
        print(json.dumps({'status':'BLOCKED','error':str(exc),'index_import_authorized':False,'index_writes':0},ensure_ascii=False),file=sys.stderr)
        return 2


if __name__=='__main__':
    raise SystemExit(main())
