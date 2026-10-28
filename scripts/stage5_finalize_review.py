"""Record manually reviewed Stage5 content decisions; NEVER import to an index.

The record is NOT a Stage6 approval receipt. Any new Stage6 builder must independently
verify official source, content review, version applicability and a fresh paired index.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import sys
try:
    from .stage5_prepare_review import canonical,digest,read_json,fail
except ImportError:  # Direct legacy CLI invocation.
    from stage5_prepare_review import canonical,digest,read_json,fail

ALLOWED={'pending','approved','rejected','needs_correction'}

def finalize(review_dir, decisions_path, package, validator=None):
    review_dir=Path(review_dir).resolve(strict=True)
    decisions_path=Path(decisions_path).resolve(strict=True)
    package=Path(package).resolve(strict=True)
    if decisions_path.is_relative_to(review_dir) and decisions_path.name == 'content_review_record.json':
        fail('Do not submit the output receipt as decisions')
    for ancestor in (review_dir,*review_dir.parents):
        if ancestor.is_symlink() or any((ancestor/x).exists() for x in ('active.json','chroma.sqlite3','bm25_index.pkl')):
            fail('Review directory cannot be in index workspace')
    manifest=read_json(review_dir/'review_manifest.json')
    expected_hash=(review_dir/'review_manifest.sha256').read_text(encoding='ascii').strip()
    if expected_hash != digest(canonical(manifest)):
        fail('Review manifest hash mismatch')
    if manifest.get('status') != 'awaiting_human_review' or manifest.get('index_import_authorized') is not False:
        fail('Review manifest cannot be treated as import approval')
    source_files=manifest.get('source_file_hashes')
    if not isinstance(source_files,dict) or not source_files:
        fail('Missing Stage4 input evidence hashes')
    for filename,h in source_files.items():
        path=Path(filename)
        if not path.is_file() or path.is_symlink() or digest(path.read_bytes()) != h:
            fail('Stage4 file changed since review preparation: '+filename)
    if validator is None:
        if str(package) not in sys.path:
            sys.path.insert(0,str(package))
        from unmochon_live.stage4_dynamic import validate_app_snapshot
        validator=validate_app_snapshot
    val=validator(Path(manifest['raw_snapshot']))
    if (val['hash'] != manifest['source_snapshot_sha256'] or
        val['request_id'] != manifest['request_id'] or
        val['generation'] != manifest['generation_at_consent']):
        fail('Raw evidence/consent changed or different generation')
    items=[]
    path=review_dir/'review_items.jsonl'
    if path.is_symlink():fail('Symlinked review items')
    for line in path.read_text(encoding='utf-8').splitlines():
        item=json.loads(line)
        if digest(item['text'].encode('utf-8')) != item.get('text_sha256'):
            fail('Review text changed')
        items.append(item)
    metadata=[{k:v for k,v in item.items() if k!='text'} for item in items]
    if metadata != manifest['items']:
        fail('Review items differ from manifest')
    decisions=read_json(decisions_path)
    if (decisions.get('schema_version')!=1 or decisions.get('manifest_sha256')!=expected_hash
        or decisions.get('request_id')!=manifest['request_id']):
        fail('Decision file is not tied to this review batch')
    reviewer=decisions.get('reviewer')
    if not isinstance(reviewer,str) or not reviewer.strip() or len(reviewer)>160:
        fail('Human reviewer name or identifier required')
    records=decisions.get('decisions')
    if not isinstance(records,list) or len(records)!=len(items):
        fail('One decision per exact review item required')
    indexed={item['id']:item for item in items}
    if len(indexed)!=len(items):fail('Duplicate item IDs')
    seen=set();selected=[];audit=[]
    for decision in records:
        if not isinstance(decision,dict):fail('Non-object decision')
        rid=decision.get('id')
        if rid in seen or rid not in indexed:
            fail('Duplicate/unknown item ID')
        seen.add(rid)
        choice=decision.get('decision')
        if choice not in ALLOWED:fail('Invalid review decision')
        notes=decision.get('notes')
        if not isinstance(notes,str) or len(notes)>4000:
            fail('Invalid review notes')
        src=decision.get('source_checked')
        context=decision.get('context_checked')
        if type(src) is not bool or type(context) is not bool:
            fail('Source/context confirmation must be explicit boolean')
        item=indexed[rid]
        if choice=='approved':
            if (not src or not context or len(notes.strip())<10 or
                item['extraction_status'] != 'processed_unverified' or not item['text'].strip()):
                fail('Cannot approve without verified source/context, notes and clean extracted text')
            selected.append({'id':rid,'raw_sha256':item['raw_sha256'], 'page':item['page'],
                             'source_url':item['source_url'],'text_sha256':item['text_sha256'],
                             'date_review_note':notes.strip(),'content_reviewed':True,
                             'current_policy_verified':False})
        if choice in ('rejected','needs_correction') and len(notes.strip())<5:
            fail('Review note is required for reject/correction')
        audit.append({'id':rid,'decision':choice,'notes':notes,'source_checked':src,'context_checked':context})
    if len(seen)!=len(items):fail('Review list incomplete')
    receipt={'schema_version':1,'status':'content_review_recorded_not_import_approved',
             'request_id':manifest['request_id'],'generation_at_consent':manifest['generation_at_consent'],
             'manifest_sha256':expected_hash,'reviewer':reviewer.strip(),
             'decisions_sha256':digest(canonical(decisions)),
             'approved_content_count':len(selected),'decision_counts':{k:sum(r['decision']==k for r in audit) for k in sorted(ALLOWED)},
             'content_reviewed_items':selected, 'decisions':audit,
             'index_import_authorized':False,'current_policy_verified':False,
             'automatic_policy_winner_selected':False,'kg_module_applied':False,
             'network_calls':0,'index_writes':0}
    out=review_dir/'content_review_record.json'
    if out.exists() or out.is_symlink():fail('A content review record already exists; never overwrite')
    # Do not alter candidate manifest, HTML or source bytes.
    with out.open('x',encoding='utf-8') as f:
        json.dump(receipt,f,ensure_ascii=False,indent=2)
        f.write('\n')
    return {'status':receipt['status'],'approved_content_count':len(selected),
            'receipt':str(out),'index_import_authorized':False,'index_writes':0}


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--review-dir',required=True)
    p.add_argument('--decisions',required=True)
    p.add_argument('--package',required=True)
    a=p.parse_args()
    try:
        print(json.dumps(finalize(a.review_dir,a.decisions,a.package),ensure_ascii=False,indent=2))
        return 0
    except Exception as exc:
        print(f'BLOCKED: {type(exc).__name__}: {exc}',file=sys.stderr)
        return 1

if __name__=='__main__':raise SystemExit(main())
