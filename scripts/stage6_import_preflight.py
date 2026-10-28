"""Read-only preflight for NEW Stage5 evidence. This DOES NOT approve index import.

Only inspect existing files. In particular, never open ChromaDB/BM25, call a crawler,
modify content-review records, promote a generation, or change any active pointer.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import re
from pathlib import Path
from urllib.parse import urlsplit


def canonical(obj):
    return json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode('utf-8')


def sha(blob: bytes):
    return hashlib.sha256(blob).hexdigest()


def load(path):
    path = Path(path)
    if path.is_symlink() or not path.is_file():
        raise ValueError('File missing or symlinked: ' + str(path))
    result = json.loads(path.read_text(encoding='utf-8'))
    if not isinstance(result, dict):
        raise ValueError('Expected JSON object: ' + str(path))
    return result


def looks_generic_note(note):
    note = ' '.join(str(note).lower().strip().rstrip('.!').split())
    return note in {'everything is fine', 'ok', 'okay', 'checked', 'verified',
                    'looks good', 'all good', 'fine', 'ভালো', 'ঠিক আছে', 'যাচাই করা হয়েছে'}


def review(review_dir, decisions_path, workspace=None):
    root = Path(review_dir).resolve(strict=True)
    decisions_path = Path(decisions_path).resolve(strict=True)
    manifest = load(root / 'review_manifest.json')
    manifest_hash = (root / 'review_manifest.sha256').read_text(encoding='ascii').strip()
    issues, warnings, inventory = [], [], []
    if manifest_hash != sha(canonical(manifest)):
        issues.append('Stage5 manifest digest mismatch')
    if manifest.get('schema_version') != 1 or manifest.get('status') != 'awaiting_human_review':
        issues.append('Stage5 manifest state invalid')
    if manifest.get('index_import_authorized') is not False:
        issues.append('Unexpected index authorization in Stage5 manifest')
    if manifest.get('source_snapshot_sha256') is None:
        issues.append('Missing source snapshot hash')
    files = manifest.get('source_file_hashes')
    if not isinstance(files, dict) or not files:
        issues.append('Missing Stage4 file hashes')
    else:
        for filename, expected in files.items():
            path = Path(filename)
            if path.is_symlink() or not path.is_file():
                issues.append('Stage4 source missing/symlinked: ' + filename)
            elif sha(path.read_bytes()) != expected:
                issues.append('Stage4 source changed: ' + filename)
    items = []
    p = root / 'review_items.jsonl'
    if p.is_symlink() or not p.is_file():
        issues.append('Missing review_items.jsonl')
    else:
        for n, line in enumerate(p.read_text(encoding='utf-8').splitlines(), 1):
            if not line.strip():
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                issues.append(f'Malformed JSONL line {n}')
                continue
            if not isinstance(obj, dict) or not isinstance(obj.get('text'), str):
                issues.append(f'Invalid review text line {n}')
                continue
            if sha(obj['text'].encode('utf-8')) != obj.get('text_sha256'):
                issues.append(f'Review item text hash mismatch line {n}')
            items.append(obj)
    itemmap = {item.get('id'): item for item in items}
    if len(itemmap) != len(items):
        issues.append('Duplicate Stage5 item IDs')
    if [{k:v for k,v in item.items() if k != 'text'} for item in items] != manifest.get('items'):
        issues.append('Review item metadata differs from manifest')
    d = load(decisions_path)
    if d.get('schema_version') != 1 or d.get('manifest_sha256') != manifest_hash or d.get('request_id') != manifest.get('request_id'):
        issues.append('Decision/manifest identity mismatch')
    decisions = d.get('decisions')
    if not isinstance(decisions, list):
        decisions = []
        issues.append('Missing decisions list')
    choice_map = {}
    for entry in decisions:
        if not isinstance(entry, dict) or not isinstance(entry.get('id'), str):
            issues.append('Invalid decision entry')
            continue
        key = entry['id']
        if key in choice_map or key not in itemmap:
            issues.append('Duplicate or unknown decision item: ' + key)
            continue
        choice_map[key] = entry
    if set(choice_map) != set(itemmap):
        issues.append('Decision set does not match review items')
    receipt_path = root / 'content_review_record.json'
    if not receipt_path.is_file():
        issues.append('No finalized content review receipt')
        receipt = {}
    else:
        receipt = load(receipt_path)
        if receipt.get('status') != 'content_review_recorded_not_import_approved':
            issues.append('Unexpected review receipt status')
        if receipt.get('request_id') != manifest.get('request_id') or receipt.get('manifest_sha256') != manifest_hash:
            issues.append('Content review receipt does not match batch')
        if receipt.get('decisions_sha256') != sha(canonical(d)):
            issues.append('Finalized receipt was not issued for this decisions file')
        if receipt.get('index_import_authorized') is not False or receipt.get('index_writes') != 0:
            issues.append('Stage5 receipt contains unexpected index permissions/writes')
        if receipt.get('generation_at_consent') != manifest.get('generation_at_consent'):
            issues.append('Stage5 generation at consent mismatch')
        approved_receipt = receipt.get('content_reviewed_items', [])
        if not isinstance(approved_receipt, list):
            issues.append('Invalid receipt item records')
            approved_receipt = []
        approved_ids = {e.get('id') for e in approved_receipt if isinstance(e, dict)}
        decision_approved = {key for key, e in choice_map.items() if e.get('decision') == 'approved'}
        if approved_ids != decision_approved or receipt.get('approved_content_count') != len(decision_approved):
            issues.append('Receipt approved IDs/count do not match decisions')
        for entry in approved_receipt:
            if not isinstance(entry, dict):
                continue
            item = itemmap.get(entry.get('id'))
            if item and any(entry.get(key) != item.get(key) for key in ('text_sha256', 'raw_sha256', 'source_url', 'page')):
                issues.append('Receipt source hash/page mismatch: ' + str(entry.get('id')))
    counts = {s: 0 for s in ('approved','needs_correction','rejected','pending')}
    for key, item in itemmap.items():
        entry = choice_map.get(key, {})
        choice = entry.get('decision')
        if choice not in counts:
            issues.append('Unknown decision: ' + str(choice))
            continue
        counts[choice] += 1
        source_url = item.get('source_url')
        date = item.get('date')
        page = item.get('page')
        note = entry.get('notes', '')
        flags = []
        if choice == 'approved':
            if entry.get('source_checked') is not True or entry.get('context_checked') is not True:
                issues.append('Approval without explicit human source/context check: ' + key)
            if item.get('extraction_status') != 'processed_unverified':
                issues.append('Approved item has extraction problem: ' + key)
            if looks_generic_note(note):
                flags.append('generic_review_note')
                warnings.append('Approval note lacks specific source/page explanation: ' + key)
            if not date:
                flags.append('document_date_not_reviewed')
            if not (isinstance(source_url,str) and urlsplit(source_url).scheme == 'https' and urlsplit(source_url).hostname):
                flags.append('official_source_url_missing_or_invalid')
            if isinstance(page, int) and page < 1:
                issues.append('Invalid PDF page number: ' + key)
        if choice == 'needs_correction':
            flags.append('exclude_until_corrected_and_rereviewed')
        inventory.append({'id': key, 'kind': item.get('kind'), 'decision':choice,
                          'page':page,'date':date,'source_url':source_url,
                          'text_sha256': item.get('text_sha256'),
                          'flags':flags})
    active_generation = None
    if workspace is not None:
        wspath = Path(workspace).resolve(strict=True)
        active_path = wspath / 'active.json'
        pointer = load(active_path)
        active_generation = pointer.get('generation')
        if active_generation != manifest.get('generation_at_consent'):
            issues.append('Active generation differs from generation at consent; rebase planning needed')
    return {'schema_version':1,'status':'BLOCKED' if issues else 'STAGE5_CONSISTENT_IMPORT_NOT_AUTHORIZED',
            'request_id':manifest.get('request_id'), 'generation_at_consent':manifest.get('generation_at_consent'),
            'active_generation_read_only':active_generation, 'counts':counts,
            'receipt_digest':sha(receipt_path.read_bytes()) if receipt_path.is_file() else None,
            'blocking_integrity_issues':issues,'manual_review_warnings':warnings,
            'items':inventory,'index_import_authorized':False,'current_policy_verified':False,
            'index_writes':0,'network_calls':0,
            'next_gate':'Separate source version/applicability review, explicit import authorization, isolated pair build, consistency and held-out-safe regression checks'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--review-dir', required=True)
    parser.add_argument('--decisions', required=True)
    parser.add_argument('--workspace', help='Optional read-only Stage6 workspace check')
    a = parser.parse_args()
    try:
        result = review(a.review_dir, a.decisions, a.workspace)
    except Exception as exc:
        print(json.dumps({'status':'BLOCKED','reason':str(exc),'index_writes':0},ensure_ascii=False,indent=2))
        return 1
    print(json.dumps(result,ensure_ascii=False,indent=2))
    return 1 if result['status'] == 'BLOCKED' else 0

if __name__ == '__main__':
    raise SystemExit(main())
