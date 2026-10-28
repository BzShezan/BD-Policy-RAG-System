"""Read-only source overlap preview between new Stage5 items and sealed active Stage6 corpus.

Does not claim semantic/quote equivalence. Does not open ChromaDB, BM25 or change pointers.
"""
import argparse
import hashlib
import json
import re
from pathlib import Path

from stage6_import_preflight import review as inspect_stage5


def sha(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024*1024),b''):
            h.update(block)
    return h.hexdigest()


def read(path):
    path=Path(path)
    if path.is_symlink() or not path.is_file():
        raise ValueError('Missing/symlinked file: '+str(path))
    return json.loads(path.read_text(encoding='utf-8'))


def active_selected(workspace):
    workspace=Path(workspace).resolve(strict=True)
    p=read(workspace/'active.json')
    name=p.get('generation','')
    if not re.fullmatch(r'[A-Za-z0-9_-]{1,80}',name):
        raise ValueError('Unsafe generation name')
    root=workspace/'generations'/name
    manifestfile=root/'generation_manifest.json'
    manifest=read(manifestfile)
    ready=read(root/'READY.json')
    wanted=sha(manifestfile)
    if (p.get('manifest_sha256')!=wanted or ready.get('manifest_sha256')!=wanted or
         manifest.get('generation')!=name or ready.get('generation')!=name or
         manifest.get('metadata',{}).get('validation_passed') is not True):
        raise ValueError('Pointer, readiness and sealed manifest do not agree')
    key='index/selected_corpus.jsonl'
    corpus=root/key
    if sha(corpus)!=manifest.get('files',{}).get(key):
        raise ValueError('Sealed selected corpus hash changed')
    rows=[json.loads(s) for s in corpus.read_text(encoding='utf-8').splitlines() if s.strip()]
    return name,rows


def scan(preflight, generation, corpus):
    by_raw={}
    for row in corpus:
        meta=row.get('metadata') or {}
        raw=meta.get('source_raw_sha256')
        if raw:
            by_raw.setdefault(raw,[]).append({'id':row.get('id'),
             'page':meta.get('page_number'),'date':meta.get('date_value'),
             'validation_status':meta.get('validation_status')})
    found=[]
    for item in preflight['items']:
        if item['decision']!='approved':
            continue
        m=re.fullmatch(r'(?:pdf|html):([a-f0-9]{64})(?::p\d+)?',item['id'])
        if not m:
            raise ValueError('Unexpected Stage5 artifact ID: '+item['id'])
        overlaps=by_raw.get(m.group(1),[])
        exact_page=[x for x in overlaps if item.get('page') is not None and x['page']==item['page']]
        found.append({'item_id':item['id'],'same_raw_source_index_rows':len(overlaps),
           'same_pdf_page_index_rows':len(exact_page),
           'example_existing_ids':[x['id'] for x in exact_page[:5]],
           'note':'Source/page overlap is NOT proof of identical claim or text'})
    return {'schema_version':1,'status':'READ_ONLY_SOURCE_OVERLAP_PREVIEW',
       'active_generation':generation,'approved_stage5_items':len(found),
       'items_with_source_overlap':sum(v['same_raw_source_index_rows']>0 for v in found),
       'items_with_same_page_overlap':sum(v['same_pdf_page_index_rows']>0 for v in found),
       'items':found,'corpus_file_hash_verified':True,
       'full_generation_audit':False,'index_import_authorized':False,
       'index_writes':0,'network_calls':0}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--review-dir',required=True)
    parser.add_argument('--decisions',required=True)
    parser.add_argument('--workspace',required=True)
    a=parser.parse_args()
    preflight=inspect_stage5(a.review_dir,a.decisions,a.workspace)
    if preflight.get('status')!='STAGE5_CONSISTENT_IMPORT_NOT_AUTHORIZED':
        raise SystemExit('BLOCKED: Stage5 preflight failed')
    generation,corpus=active_selected(a.workspace)
    if generation!=preflight['generation_at_consent']:
        raise SystemExit('BLOCKED: generation drift')
    print(json.dumps(scan(preflight,generation,corpus),ensure_ascii=False,indent=2))


if __name__=='__main__':
    main()
