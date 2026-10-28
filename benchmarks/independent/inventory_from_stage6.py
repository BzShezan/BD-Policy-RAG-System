"""Read-only source/document inventory from sealed active Stage6 generation.

Does not open Chroma or BM25, validate Excel, write index, or score retrieval.
"""
import argparse
from collections import defaultdict
import csv
import hashlib
import json
from pathlib import Path


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--workspace',type=Path,required=True)
    ap.add_argument('--output',type=Path,required=True)
    a=ap.parse_args()
    if a.output.exists():raise ValueError('Output exists: choose a fresh filename')
    workspace=a.workspace.resolve()
    pointer=json.loads((workspace/'active.json').read_text(encoding='utf-8'))
    generation=pointer['generation']
    if not generation or '/' in generation or '\\' in generation or generation.startswith('.'):
        raise ValueError('Invalid generation name')
    gen=workspace/'generations'/generation
    manifest_file=gen/'generation_manifest.json'
    digest=hashlib.sha256(manifest_file.read_bytes()).hexdigest()
    if digest != pointer['manifest_sha256']:
        raise ValueError('Active pointer manifest SHA mismatch')
    ready=json.loads((gen/'READY.json').read_text(encoding='utf-8'))
    if ready['manifest_sha256'] != digest:
        raise ValueError('Not a ready generation')
    manifest=json.loads(manifest_file.read_text(encoding='utf-8'))
    corpus=gen/'index/selected_corpus.jsonl'
    expected=manifest['files']['index/selected_corpus.jsonl']
    if hashlib.sha256(corpus.read_bytes()).hexdigest() != expected:
        raise ValueError('Selected corpus seal mismatch')
    groups=defaultdict(lambda:{'indexed_items':0,'indexed_pages':set()})
    with corpus.open(encoding='utf-8') as f:
        for line in f:
            if not line.strip():continue
            r=json.loads(line)
            m=r.get('metadata') or {}
            key=(m.get('ministry') or 'Unknown', m.get('doc_id') or 'Unknown',
                 m.get('date_value') or '', m.get('source_url') or '')
            item=groups[key];item['indexed_items']+=1
            if m.get('page_number') is not None:item['indexed_pages'].add(str(m['page_number']))
    a.output.parent.mkdir(parents=True,exist_ok=True)
    with a.output.open('x',newline='',encoding='utf-8-sig') as f:
        w=csv.writer(f)
        w.writerow(['ministry','doc_id','date_value','source_url','indexed_items','indexed_page_count',
                    'indexed_pages_not_proof_of_pdf_page_count','pdf_local_path_for_reviewer',
                    'document_family_for_independent_split'])
        for key,item in sorted(groups.items()):
            w.writerow([*key,item['indexed_items'],len(item['indexed_pages']),
                        ' '.join(sorted(item['indexed_pages'],key=lambda x:int(x) if x.isdigit() else x)), '', ''])
    print('Sealed active generation:',generation,'| Indexed document editions:',len(groups))
    print('No database, PDF, model or network accessed; no metadata reconciliation performed.')

if __name__=='__main__':main()
