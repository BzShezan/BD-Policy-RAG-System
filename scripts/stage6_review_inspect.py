#!/usr/bin/env python3
"""Read-only diagnostic of a Stage 6 source review against Stage 5 extracted text.

Does NOT change decisions, authorize an import, call network, or touch any index.
"""
from __future__ import annotations
import argparse
import difflib
import hashlib
import json
from pathlib import Path


def sha256_text(s: str) -> str:
    return hashlib.sha256(s.encode('utf-8')).hexdigest()


def load_extractions(path: Path) -> dict:
    result = {}
    with path.open(encoding='utf-8') as fh:
        for n, line in enumerate(fh, 1):
            if not line.strip():
                continue
            row = json.loads(line)
            rid, value = row['id'], row['text']
            if rid in result or not isinstance(value, str):
                raise ValueError(f'Duplicate/bad extraction on line {n}')
            if sha256_text(value) != row['text_sha256']:
                raise ValueError(f'Extraction hash mismatch on line {n}: {rid}')
            result[rid] = row
    return result


def summarize(review: dict, extraction: dict) -> dict:
    output = []
    for row in review.get('items', []):
        rid = row['id']
        src = extraction.get(rid)
        concerns = []
        if src is None:
            concerns.append('Stage5 extracted text missing for this item')
        else:
            for field in ('source_url', 'page', 'text_sha256'):
                # Stage5 item shape may use original page field, same as the review draft.
                if row.get(field) != src.get(field):
                    concerns.append(f'Provenance differs: {field}')
        if row.get('disposition') != 'candidate':
            output.append({'id': rid, 'disposition': row.get('disposition'), 'concerns': concerns})
            continue
        if not row.get('program'):
            concerns.append('Program missing')
        if not isinstance(row.get('reviewer'), str) or len(row['reviewer'].strip()) < 2:
            concerns.append('Reviewer must be a reviewer name, not true/false')
        if len(str(row.get('source_version_notes') or '').strip()) < 25:
            concerns.append('Source version explanation too short')
        quote = row.get('verified_quote')
        literal_match = isinstance(quote, str) and bool(quote.strip()) and src is not None and quote in src['text']
        if not literal_match:
            concerns.append('Quote is not a literal substring of the Stage5 extraction')
        # For reviewing, show a short nearest *unverified* extraction excerpt, never auto-approve it.
        nearest = ''
        if src is not None and not literal_match:
            text = src['text']
            chunks = [s.strip() for s in text.splitlines() if len(s.strip()) >= 12]
            if not chunks:
                chunks = [text[:400]] if text else []
            if chunks:
                nearest = max(chunks, key=lambda s: difflib.SequenceMatcher(None, str(quote or '')[:160], s[:160]).ratio())[:450]
        output.append({'id': rid, 'disposition': row['disposition'], 'page': row.get('page'),
                       'source_url': row.get('source_url'), 'concerns': concerns,
                       'literal_quote_matches_extraction': bool(literal_match),
                       'extraction_excerpt_for_manual_review_NOT_VERIFIED': nearest})
    return {'status': 'READ_ONLY_REVIEW_DIAGNOSTIC', 'index_import_authorized': False,
            'index_writes': 0, 'network_calls': 0, 'items': output,
            'items_with_concerns': sum(bool(i['concerns']) for i in output)}


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--reviewed', required=True, type=Path)
    p.add_argument('--review-items', required=True, type=Path,
                   help='Your existing stage5_review_20261017/review_items.jsonl')
    p.add_argument('--out', type=Path, help='New output JSON filename; existing file will never be overwritten')
    args = p.parse_args()
    doc = json.loads(args.reviewed.read_text(encoding='utf-8'))
    source = load_extractions(args.review_items)
    result = summarize(doc, source)
    encoded = json.dumps(result, ensure_ascii=False, indent=2) + '\n'
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        with args.out.open('x', encoding='utf-8') as out:
            out.write(encoded)
        print(json.dumps({'status': result['status'], 'items_with_concerns': result['items_with_concerns'],
                          'output': str(args.out), 'index_writes': 0}, ensure_ascii=False))
    else:
        print(encoded)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
