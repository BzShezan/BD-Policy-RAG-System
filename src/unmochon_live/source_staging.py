"""Source-integrity staging for automatic ingestion, with content deduplication."""
import hashlib
import json
from pathlib import Path


def prepare_sources(processed, snapshot, package, output):
    from .stage4_dynamic import validate_app_snapshot
    from .evidence_verification import read, write
    from scripts.stage5_prepare_review import guard_output, canonical, digest
    processed, snapshot, package = (Path(p).resolve(strict=True) for p in (processed,snapshot,package))
    output = guard_output(output, processed, snapshot, package)
    valid = validate_app_snapshot(snapshot)
    files = {}

    def load(path):
        path = Path(path).resolve(strict=True)
        if not path.is_relative_to(processed) or path.is_symlink():
            raise ValueError('Extracted source escaped its processing directory')
        files[str(path)] = hashlib.sha256(path.read_bytes()).hexdigest()
        return read(path)

    summary = load(processed/'stage4_dynamic_summary.json')
    if (summary.get('request_id') != valid['request_id'] or
            summary.get('generation_at_consent') != valid['generation'] or
            summary.get('source_snapshot_sha256') != valid['hash'] or
            summary.get('source_snapshot_unchanged') is not True or
            summary.get('artifacts_verified') != len(valid['result'].artifacts)):
        raise ValueError('Extracted evidence is not bound to the consented snapshot')
    grouped = {}
    for a in valid['result'].artifacts:
        grouped.setdefault(a.raw_sha256, []).append(a)
    items = []
    for sha, artifacts in sorted(grouped.items()):
        urls = list(dict.fromkeys(a.url for a in artifacts))
        a = artifacts[0]
        kind = 'PDF' if a.relative_path.endswith('.pdf') else 'HTML'
        folder = processed/('pdf' if kind == 'PDF' else 'html')
        doc = load(folder/'documents'/(sha+'.json'))
        if doc.get('source',{}).get('raw_sha256') != sha or doc['source'].get('url') not in urls:
            raise ValueError('Extracted document source mismatch')
        pages = doc.get('pages', []) if kind == 'PDF' else [None]
        if kind == 'PDF' and [p.get('page') for p in pages] != list(range(1,len(pages)+1)):
            raise ValueError('Extracted PDF page sequence mismatch')
        for page in pages:
            number = page['page'] if page else None
            body = load(folder/'pages'/(sha+'_p'+str(number)+'.json')) if page else doc
            text = body.get('text')
            if (not isinstance(text,str) or len(text)>1_000_000 or
                    hashlib.sha256(text.encode('utf-8')).hexdigest() != body.get('text_sha256')):
                raise ValueError('Extracted source text hash mismatch')
            if page and (body.get('raw_sha256') != sha or body.get('page') != number or body.get('source_url') not in urls):
                raise ValueError('Extracted PDF page provenance mismatch')
            items.append({'id':('pdf:' if page else 'html:')+sha+(':p'+str(number) if page else ''),
                'kind':kind,'raw_sha256':sha,'page':number,'source_url':a.url,'source_urls':urls,
                'source_referrer':a.government_referrer_url,'title':doc.get('title') or a.title or '',
                'text':text,'text_sha256':body['text_sha256'],'date':None,'route':body.get('route'),
                'extraction_status':body.get('evidence_status','processed_unverified'),
                'extraction_issue':body.get('extraction_issue'),'current_policy_verified':False})
    if validate_app_snapshot(snapshot)['hash'] != valid['hash']:
        raise ValueError('Source snapshot changed while staging')
    manifest = {'schema_version':1,'status':'automatic_source_staging','request_id':valid['request_id'],
        'generation_at_consent':valid['generation'],'raw_snapshot':str(snapshot),
        'source_snapshot_sha256':valid['hash'],'stage4_output':str(processed),
        'source_file_hashes':files,'items':[{k:v for k,v in x.items() if k!='text'} for x in items],
        'human_review_required':False,'current_policy_verified':False,'index_writes':0}
    output.mkdir(parents=True, exist_ok=False)
    write(output/'review_manifest.json',manifest)
    (output/'review_manifest.sha256').write_text(digest(canonical(manifest))+'\n',encoding='ascii')
    (output/'review_items.jsonl').write_text(''.join(json.dumps(x,ensure_ascii=False)+'\n' for x in items),encoding='utf-8')
    return {'status':'automatic_source_staging','items':len(items)}
