"""Build a human-only Stage5 review bundle from consented Dynamic Stage4 output.

No crawler, index, KG or model operations are performed.  Stage4's original
consent/provenance validator is reused; results are never auto-approved.
"""
from __future__ import annotations
import argparse
from dataclasses import dataclass
from hashlib import sha256
from html import escape
import json
from pathlib import Path
import sys


def canonical(obj):
    return json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode('utf-8')


def digest(data):
    return sha256(data).hexdigest()


def fail(msg):
    raise ValueError(msg)


def read_json(path):
    path = Path(path)
    if path.is_symlink() or not path.is_file():
        fail(f'Missing/symlinked input: {path}')
    result = json.loads(path.read_text(encoding='utf-8'))
    if not isinstance(result, dict):
        fail(f'Expected JSON object: {path}')
    return result


def record_source(path, files):
    path = Path(path).resolve(strict=True)
    if path.is_symlink():
        fail('Symlink source')
    files[str(path)] = digest(path.read_bytes())
    return read_json(path)


def guard_output(output, stage4, snapshot, package):
    output = Path(output).absolute()
    for root in (stage4, snapshot, package):
        if output == root or output.is_relative_to(root) or root.is_relative_to(output):
            fail('Review output must not overlap input directories')
    if output.exists() and (not output.is_dir() or any(output.iterdir())):
        fail('Output directory must be new or empty')
    for ancestor in (output, *output.parents):
        if ancestor.is_symlink() or any((ancestor / x).exists() for x in ('active.json', 'chroma.sqlite3', 'bm25_index.pkl')):
            fail('Refusing to write into an index workspace or symlinked directory')
    return output


def build(stage4, snapshot, package, output, validator=None):
    stage4 = Path(stage4).resolve(strict=True)
    snapshot = Path(snapshot).resolve(strict=True)
    package = Path(package).resolve(strict=True)
    output = guard_output(output, stage4, snapshot, package)
    if validator is None:
        if str(package) not in sys.path:
            sys.path.insert(0, str(package))
        # Import exact previously installed adapter from the unified application.
        from unmochon_live.stage4_dynamic import validate_app_snapshot
        validator = validate_app_snapshot
    verified = validator(snapshot)
    if verified['root'].resolve() != snapshot or not verified.get('hash'):
        fail('Stage3 provenance validator disagrees with source snapshot')
    files = {}
    summary = record_source(stage4 / 'stage4_dynamic_summary.json', files)
    fields = ('request_id', 'generation_at_consent', 'source_snapshot_sha256')
    expected = (verified['request_id'], verified['generation'], verified['hash'])
    if tuple(summary.get(k) for k in fields) != expected:
        fail('Stage4 summary is not bound to this approved crawl')
    if not (summary.get('source_snapshot_unchanged') is True
            and summary.get('status') in ('review_required', 'processing_review_needed')
            and summary.get('human_content_review_required') is True
            and summary.get('index_import_authorized') is False
            and summary.get('current_policy_verified') is False
            and summary.get('network_calls') == 0
            and summary.get('index_writes') == 0
            and type(summary.get('artifacts_verified')) is int
            and summary['artifacts_verified'] == len(verified['result'].artifacts)):
        fail('Stage4 safety or source integrity gates missing')
    for kind in ('html', 'pdf'):
        if Path(summary.get(kind + '_output', '')).resolve() != (stage4 / kind).resolve():
            fail(f'Stage4 {kind} output path mismatch')
    sources = {a.raw_sha256: a for a in verified['result'].artifacts}
    html_sources = {k: a for k,a in sources.items() if a.relative_path.endswith('.html')}
    pdf_sources = {k: a for k,a in sources.items() if a.relative_path.endswith('.pdf')}
    if len(sources) != len(verified['result'].artifacts):
        fail('Duplicate raw digests not supported in this review batch')
    if summary.get('html_artifacts_processed') != len(html_sources) or summary.get('pdf_artifacts_processed') != len(pdf_sources):
        fail('Stage4 artifact counters disagree with crawl')
    items = []
    for raw_sha, a in sorted(html_sources.items()):
        data = record_source(stage4 / 'html' / 'documents' / (raw_sha + '.json'), files)
        body = data.get('text')
        if (not isinstance(body, str) or len(body) > 1_000_000 or
                digest(body.encode('utf-8')) != data.get('text_sha256') or
                data.get('source', {}).get('raw_sha256') != raw_sha or
                data.get('source', {}).get('url') != a.url or
                data.get('human_approval') is not False or
                data.get('requires_human_import_approval') is not True or
                data.get('evidence_status') != 'processed_unverified'):
            fail('HTML evidence/source hash or human-review gates disagree')
        items.append({'id': f'html:{raw_sha}', 'kind':'HTML', 'raw_sha256':raw_sha,
            'page': None, 'source_url':a.url, 'source_referrer':getattr(a, 'government_referrer_url', None),
            'title':data.get('title') or '', 'text':body, 'text_sha256':data['text_sha256'],
            'date':data.get('document_date'), 'extraction_status': 'processed_unverified',
            'current_policy_verified': False})
    count_pages = 0
    for raw_sha, a in sorted(pdf_sources.items()):
        doc = record_source(stage4 / 'pdf' / 'documents' / (raw_sha + '.json'), files)
        if (doc.get('source', {}).get('raw_sha256') != raw_sha or
                doc.get('source', {}).get('url') != a.url or
                doc.get('requires_human_import_approval') is not True or
                doc.get('current_policy_verified') is not False):
            fail('PDF document source/approval metadata mismatched')
        pages = doc.get('pages')
        if not isinstance(pages,list) or not pages:
            fail('PDF has no processed pages')
        if [p.get('page') for p in pages] != list(range(1,len(pages)+1)):
            fail('PDF page sequence invalid')
        for p in pages:
            page = p['page']
            data = record_source(stage4 / 'pdf' / 'pages' / (raw_sha + '_p' + str(page) + '.json'), files)
            body = data.get('text')
            quality = data.get('final_quality')
            if (not isinstance(body,str) or len(body)>1_000_000 or
                    digest(body.encode('utf-8')) != data.get('text_sha256') or
                    data.get('raw_sha256') != raw_sha or data.get('source_url') != a.url or
                    data.get('page') != page or data.get('human_approval') is not False or
                    data.get('requires_human_import_approval') is not True or
                    data.get('evidence_status') not in ('processed_unverified','needs_extraction_review') or
                    not isinstance(quality,dict) or
                    p.get('accepted_for_staging') is not quality.get('accepted_for_staging')):
                fail('PDF page content/quality/source mismatch')
            items.append({'id': f'pdf:{raw_sha}:p{page}', 'kind':'PDF', 'raw_sha256':raw_sha,
                'page':page, 'source_url':a.url,
                'source_referrer':getattr(a, 'government_referrer_url', None),
                'title':'', 'text':body, 'text_sha256':data['text_sha256'],
                'date':data.get('document_date'), 'route':data.get('route'),
                'extraction_status':data.get('evidence_status'), 'extraction_issue':data.get('extraction_issue'),
                'current_policy_verified': False})
            count_pages += 1
    if (summary.get('pdf_pages') != count_pages or
            summary.get('pages_needing_extraction_review') != sum(x.get('extraction_status') == 'needs_extraction_review' for x in items)):
        fail('Stage4 PDF page counters mismatch')
    if not items:
        fail('Nothing available for human review')
    # Source snapshot gets revalidated after reading the Stage4 output.
    if validator(snapshot)['hash'] != verified['hash']:
        fail('Stage3 snapshot modified while preparing review')
    item_meta = [{k:v for k,v in item.items() if k != 'text'} for item in items]
    manifest = {'schema_version':1, 'status':'awaiting_human_review',
        'request_id':verified['request_id'],'generation_at_consent':verified['generation'],
        'source_snapshot_sha256':verified['hash'], 'raw_snapshot':str(snapshot),
        'stage4_output':str(stage4), 'source_file_hashes':files, 'items':item_meta,
        'content_approved': False, 'index_import_authorized':False, 'current_policy_verified':False,
        'kg_module_applied':False, 'network_calls':0, 'index_writes':0}
    manifest_sha = digest(canonical(manifest))
    # Output files written last after all checks, no overwrite allowed.
    output.mkdir(parents=True, exist_ok=True)
    (output/'review_manifest.json').write_text(json.dumps(manifest, ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    (output/'review_manifest.sha256').write_text(manifest_sha+'\n',encoding='ascii')
    (output/'review_items.jsonl').write_text(''.join(json.dumps(x,ensure_ascii=False)+'\n' for x in items),encoding='utf-8')
    (output/'review.html').write_text(make_review_html(items, manifest_sha, verified['request_id']),encoding='utf-8')
    return {'status':'awaiting_human_review', 'items':len(items), 'html_items':len(html_sources),
        'pdf_page_items':count_pages, 'manifest_sha256':manifest_sha, 'review_page':str(output/'review.html'),
        'index_writes':0, 'network_calls':0}


def make_review_html(items, manifest_sha, request_id):
    # Escape untrusted extracted text; no remote JS, fonts or CSS.
    cards=[]
    for i,item in enumerate(items):
        url=escape(item['source_url'],quote=True)
        text=escape(item['text'])
        title=escape(item['title'])
        status=escape(item['extraction_status'])
        pag=f" — page {item['page']}" if item['page'] is not None else ''
        cards.append(f'''<section class="card" data-n="{i}"><h2>{i+1}. {escape(item['kind'])}{pag}</h2>
        <p><a href="{url}" target="_blank" rel="noopener noreferrer">Original source (verify manually)</a> · {title}</p>
        <p class="muted">{status} · {escape(str(item.get('date') or 'Document date unverified'))}</p>
        <details><summary>Extracted text / quote</summary><pre>{text}</pre></details>
        <p><label>Decision <select class="decision"><option value="pending">Pending</option><option value="approved">Content reviewed — approve</option><option value="rejected">Reject</option><option value="needs_correction">Needs correction</option></select></label></p>
        <p><label><input type="checkbox" class="sourcechecked"> I opened and checked the original source</label></p>
        <p><label><input type="checkbox" class="contextchecked"> I verified quote, date applicability and page context</label></p>
        <p><label>Review notes <textarea class="notes" rows="2" placeholder="Why approved/rejected; source version ambiguity..." ></textarea></label></p></section>''')
    ids=json.dumps([x['id'] for x in items],ensure_ascii=True)
    head='''<!doctype html><html lang="en"><meta charset="utf-8"><title>Unmochon Stage 5 Human Review</title>
    <style>body{max-width:1000px;margin:30px auto;padding:0 18px;font:16px system-ui;line-height:1.6;background:#f7f7f7;color:#202020}.card{background:white;border:1px solid #ddd;border-radius:12px;padding:18px;margin:20px 0}pre{white-space:pre-wrap;overflow-wrap:anywhere;border:1px solid #ddd;border-radius:8px;padding:14px;max-height:470px;overflow:auto}textarea{display:block;width:95%;padding:8px}select{padding:6px}.muted{color:#666}button{padding:11px 19px;font-weight:bold}</style>
    <h1>Unmochon — Stage 5 Human Review</h1><p>Review the original source before approving. These items are <b>NOT verified current policy</b>. This interface does not crawl, approve an index import or update ChromaDB/BM25.</p>
    <p><label>Reviewer name/identifier: <input id="reviewer" autocomplete="off"></label></p>'''
    tail='''<button type="button" id="export">Export decisions JSON</button><p id="message"></p>
    <script>const ids=__IDS__;const manifest="__MANIFEST__";const requestId="__REQUEST__";
    document.getElementById('export').addEventListener('click',()=>{
       const reviewer=document.getElementById('reviewer').value.trim();
       if(!reviewer){alert('Reviewer name is required');return;}
       const cards=[...document.querySelectorAll('.card')];
       const decisions=cards.map((card,i)=>({id:ids[i],decision:card.querySelector('.decision').value,
          source_checked:card.querySelector('.sourcechecked').checked,
          context_checked:card.querySelector('.contextchecked').checked,
          notes:card.querySelector('.notes').value.trim()}));
       const content=JSON.stringify({schema_version:1,manifest_sha256:manifest,request_id:requestId,reviewer,decisions},null,2);
       const blob=new Blob([content],{type:'application/json'});const a=document.createElement('a');
       const url=URL.createObjectURL(blob);a.href=url;a.download='stage5_review_decisions.json';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);
       document.getElementById('message').textContent='Decisions downloaded. Run the verification CLI to record them; no index imported.';
    });</script></html>'''
    tail=tail.replace('__IDS__', ids).replace('__MANIFEST__',manifest_sha).replace('__REQUEST__',request_id)
    return head+'\n'.join(cards)+tail


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--stage4',required=True,type=Path)
    p.add_argument('--snapshot',required=True,type=Path)
    p.add_argument('--package',required=True,type=Path)
    p.add_argument('--output',required=True,type=Path)
    a=p.parse_args()
    try:
        print(json.dumps(build(a.stage4,a.snapshot,a.package,a.output),ensure_ascii=False,indent=2))
    except Exception as exc:
        print(f'BLOCKED: {type(exc).__name__}: {exc}',file=sys.stderr)
        return 1
    return 0

if __name__=='__main__':
    raise SystemExit(main())
