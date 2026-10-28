"""Offline child processes for original hybrid query, candidate append and restart.

The embedding model is resolved from the existing, hash-pinned LOCAL cache.
The same Stage 6 append_candidate/verify_pair/vector_hash implementations are
used; the Stage 1 builder and sealed source generation are never opened/written.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile

from .runtime import load_stage4, load_stage6

REGRESSION_QUESTIONS = (
    '২০১৩ সালের বয়স্ক ভাতা নীতিমালায় পুরুষ ও মহিলার বয়স কত?',
    '২০১৩ সালের চা শ্রমিকদের আর্থিক সহায়তা নীতিমালায় বয়স কত?',
    '২০১৮ সালের কৃষি বিপণন নীতিমালায় পর্যালোচনার সময় কত বছর?',
)


def bootstrap(spec):
    load_stage6(Path(spec['package']))
    from stage6.common import offline
    offline()
    from stage6.legacy import install
    install()
    # Stage 3/4 and Stage 6 bundle the same public Stage 2 evaluator contract.
    # Extend its module search path for the original live adapter, without
    # replacing the loaded evaluator or permission classes.
    import stage2
    compat = str(Path(spec['package'])/'compat/stage2')
    if compat not in stage2.__path__:
        stage2.__path__.append(compat)
    load_stage4(spec['stage4_package'])
    os.environ['RESEARCH_SOURCE_REGISTRY'] = spec['registry']
    from index_checks import index_common
    from .research_registry import make_registry
    registry = make_registry(spec['registry'])
    # The original verifier hardcodes three pilot buckets. Register only the
    # explicitly verified new authorities in this isolated child process.
    index_common.MINISTRIES.update({k:k for k in registry.entries})
    return registry


def resolve_local_model(spec):
    from stage6.common import read
    from run_stage2_live import resolve_model
    plan = read(Path(spec['workspace'])/'workspace.json')
    explicit = os.getenv('STAGE6_MODEL_PATH') or plan.get('model_path')
    if explicit and not Path(explicit).is_dir():
        explicit = None
    cache = spec.get('model_cache') or plan.get('model_cache')
    return resolve_model(explicit, cache)


def original(index, model, package):
    from scripts.retrieval.search import HybridRetriever
    from sentence_transformers import SentenceTransformer
    from stage6.index_pair import restricted_payload
    from index_checks.index_common import persistent_client, COLLECTION
    from .original_pipeline import OriginalPipeline
    import torch
    torch.set_num_threads(2)
    # Bind runtime resources only; the original HybridRetriever.search and
    # original UI/app.py two-stage functions execute without algorithm edits.
    retriever = HybridRetriever.__new__(HybridRetriever)
    retriever.client = persistent_client(index/'data/chromedb')
    retriever.collection = retriever.client.get_collection(COLLECTION, embedding_function=None)
    payload = restricted_payload(index/'data/bm25_index.pkl')
    retriever.bm25, retriever.bm25_ids = payload['bm25'], payload['ids']
    retriever.bm25_id_to_pos = {cid:i for i,cid in enumerate(payload['ids'])}
    retriever.model = SentenceTransformer(str(model), local_files_only=True)
    retriever.model.to('cpu').float().eval()
    if retriever.model.get_sentence_embedding_dimension() != 384 or retriever.model.max_seq_length != 128:
        raise ValueError('Embedding model differs from the accepted paired index')
    return OriginalPipeline(retriever), retriever


def evidence_adapter(selected, package):
    from live_adapter import SelectedEvidenceAdapter
    from stage2.evaluator import Evidence, sha256
    data = Path(os.getenv('STAGE2_EVIDENCE_DATA', str(Path(package)/'compat/data')))
    needed = ('policy_catalog.json', 'approved_ocr_patches.json',
              'p01_p02_approval_receipt.json', 'numeric_confirmation_receipt.json')
    if all((data/n).is_file() for n in needed):
        base = SelectedEvidenceAdapter(data, selected)
    else:
        # Unknown legacy facts are not silently promoted when optional pilot
        # metadata was excluded from a code-only archive.
        base = SelectedEvidenceAdapter.__new__(SelectedEvidenceAdapter)
        base.selected = {r['id']:r for r in selected}
        base.metadata = {r['id']:r['metadata'] for r in selected}
        base.catalog, base.patches, base.preexisting_patches = {}, {}, {}
        base.numeric = {'documents':{}}

    class ReviewedAdapter:
        def convert(self, raw):
            row = base.selected.get(raw['id'])
            if row is None or row['text'] != raw['text']:
                raise ValueError('Retrieved source differs from verified selected corpus')
            m = row['metadata']
            if m.get('agentic_verified') or (m.get('human_content_approved') and m.get('program') == 'vgf'):
                date = m.get('date_value') or ''
                return Evidence(id=row['id'], doc_id=m['doc_id'], ministry=m['ministry'],
                    text=row['text'], program=m.get('program'), document_kind='policy',
                    policy_year=int(date[:4]) if date else None, page=m.get('page_number'),
                    source_url=m['source_url'], date_value=date,
                    date_precision=m.get('date_precision','unknown'),
                    date_status=m.get('date_status','unknown'), current_version_verified=False,
                    indexed_text_sha256=sha256(row['text']), local_source_available=True,
                    policy_year_basis='source_bound_document_date')
            return base.convert(raw)
    return ReviewedAdapter()


def query_loaded(question, selected, live, retriever, package, evidence_root=None, registry=None):
    """Original results decide answers; Stage 2 pilot catalogs cannot hide them."""
    from stage6.versions import group_retrieved_sources
    from .research_registry import match_scope
    from .answering import relevant
    from .original_pipeline import format_source_hit
    prediction = live.collect('USER_QUERY', question)
    if prediction.get('error'):
        raise ValueError(prediction['error'])
    by_id = {r['id']:r for r in selected}
    matches = match_scope(question)
    program, authority = matches[0] if len(matches) == 1 else (None, None)
    pool = prediction.get('all_candidates') or retriever.search(
        prediction['retrieval_question'], top_k=100, ministry=prediction.get('ministry_filter'))
    cards = prediction.get('pipeline_cards', [])
    # Verify that formatted UI results still carry the exact sealed corpus text.
    for card in cards:
        row = by_id.get(card['clause_id'])
        if row is None or row['text'] != card['clause_text']:
            raise ValueError('Original pipeline result differs from sealed indexed text')
    if program in {'nid','passport','birth_registration','driving_license'}:
        cards = [c for c in cards if by_id[c['clause_id']]['metadata'].get('program') == program
                 and by_id[c['clause_id']]['metadata'].get('ministry') == authority
                 and relevant(question, c['clause_text'], same_program=True)]
    # The original domain vocabulary predates NID/passport and other services.
    # After its unchanged hybrid search, allow relevant newly ingested source
    # chunks even when the old domain-keyword guard returns out_of_scope.
    gathered = []
    for hit in pool:
        row = by_id.get(hit['id'])
        if row is None or row['text'] != hit['text']:
            raise ValueError('Hybrid result differs from sealed indexed text')
        m = row['metadata']
        if not (m.get('agentic_ingested') or m.get('agentic_verified')):
            continue
        if program and (m.get('program') != program or m.get('ministry') != authority):
            continue
        if hashlib.sha256(row['text'].encode()).hexdigest() != m.get('source_quote_sha256'):
            raise ValueError('Ingested source quote hash mismatch')
        if relevant(question, row['text'], same_program=bool(program)):
            gathered.append(format_source_hit(hit, row, getattr(live, 'app', None)))
    if gathered:
        # Preserve original ranking for legacy answers. Use hybrid ranking for
        # new service chunks unsupported by the old extractor vocabulary.
        existing_ids = {c['clause_id'] for c in cards}
        if not cards or not any(c.get('confidence_tier') in {'high','medium'} for c in cards):
            cards = gathered + [c for c in cards if c['clause_id'] not in {r['clause_id'] for r in gathered}]
        else:
            cards += [c for c in gathered if c['clause_id'] not in existing_ids]
    action = 'ANSWER_FROM_EVIDENCE' if cards and not (prediction.get('predicted_oos') and not gathered) else (
        'REQUEST_RESEARCH_PERMISSION' if len(matches) == 1 else
        'ASK_CLARIFICATION' if len(matches) > 1 else 'DECLINE_OUT_OF_DOMAIN')
    reason = 'original_unmochon_retrieval' if action == 'ANSWER_FROM_EVIDENCE' else 'relevant_question_insufficient_evidence'
    # An explicitly newer date still needs research; ordinary historical queries
    # are answered directly instead of being labelled as unresolved versions.
    from stage2.evaluator import infer_constraints
    constraints = infer_constraints(question)
    dates = [by_id[c['clause_id']]['metadata'].get('date_value','') for c in cards]
    dates = [d for d in dates if len(d) == 10]
    if constraints.exact_date and dates and constraints.exact_date > max(dates) and len(matches) == 1:
        action, reason = 'REQUEST_RESEARCH_PERMISSION', 'newer_information_required'
    result = {'question':question, 'action':action, 'reason':reason,
              'retrieved_source_versions':group_retrieved_sources(pool, selected),
              'original_results':cards, 'answer_results':cards if action == 'ANSWER_FROM_EVIDENCE' else [],
              'intents':prediction.get('detected_intents', []), 'ministry':prediction.get('ministry_prediction'),
              'translated':prediction.get('translated'), 'conflicts':prediction.get('conflicts', []),
              'translation_note':prediction.get('translation_note'),
              'automatic_winner_selected':False, 'current_policy_verified':False,
              'retrieval_pipeline':'UI.app.search_question -> original HybridRetriever -> original two_stage_search'}
    if action == 'REQUEST_RESEARCH_PERMISSION':
        result['research_trigger'] = {'program':program, 'ministry':authority, 'reason':reason,
                                     'gap_type':reason, 'permission_granted':False, 'execution_called':False}
    return result


def regression_snapshot(live, questions=REGRESSION_QUESTIONS):
    result = []
    for question in questions:
        p = live.collect('PAIR_REGRESSION', question)
        if p.get('error'):
            raise ValueError('Original retrieval regression probe failed')
        result.append({'question':question, 'ids':[r['id'] for r in p['pipeline_results'][:3]],
                       'raw_ids':[r['id'] for r in p['raw_results'][:3]],
                       'intents':p['detected_intents'], 'ministry':p['ministry_filter']})
    return result


def compare_regression(before, after):
    losses = []
    for a,b in zip(before,after,strict=True):
        if (a['intents'] != b['intents'] or a['ministry'] != b['ministry'] or
                (a['ids'] and a['ids'][0] not in b['ids']) or
                (a['raw_ids'] and a['raw_ids'][0] not in b['raw_ids'])):
            losses.append(a['question'])
    return {'passed':not losses, 'case_count':len(before), 'losses':losses,
            'scope':'paired_original_retrieval_probes;_not_accuracy_or_large_benchmark'}


def build_pair(index, selected, additions, encoder, model_info):
    """Small testable adapter over the ORIGINAL Stage 6 append primitive."""
    from stage6.approved import merge_items
    from stage6.index_pair import append_candidate
    # The historical helper assumes every clause has a printed date; its
    # None scope key must not collapse distinct undated service pages.
    existing = {r['id']:r for r in selected}
    duplicates = []
    fresh = []
    for row in additions:
        old = existing.get(row['id'])
        if old and old['text'] == row['text'] and all(old['metadata'].get(k) == row['metadata'].get(k)
                for k in ('source_raw_sha256','source_url','date_value','program')):
            duplicates.append({'existing_id':row['id'],'reason':'same_source_and_exact_quote'})
        else:
            fresh.append(row)
    additions = fresh
    dated = [r for r in additions if r['metadata'].get('date_value')]
    merged, added, skipped, mapping = merge_items(selected, dated)
    skipped.extend(duplicates)
    by_id = {r['id']:r for r in merged}
    for row in additions:
        if row['metadata'].get('date_value'):
            continue
        prior = by_id.get(row['id'])
        if prior is not None:
            if prior != row:
                raise ValueError('Stable undated source ID collision')
            skipped.append({'existing_id':row['id'],'reason':'same_source_and_exact_quote'})
        else:
            merged.append(row); added.append(row); by_id[row['id']] = row
    if not added:
        raise ValueError('All gathered clauses already exist; no new generation is necessary')
    collection, payload, report = append_candidate(index, merged, added, encoder, model_info)
    return collection, payload, report, merged, added, skipped


def build(spec):
    bootstrap(spec)
    from stage6.common import read, rows, write
    from stage6.generations import active, generation
    from stage6.index_pair import restricted_payload, verify_pair
    from .evidence_verification import validate_receipt
    receipt = validate_receipt(spec['receipt'])
    workspace = Path(spec['workspace'])
    if active(workspace) != spec['before'] or receipt['generation_at_consent'] != spec['before']['generation']:
        raise ValueError('Stale source/consent generation')
    candidate = generation(workspace, spec['candidate'])
    index = candidate/'index'
    selected = rows(index/'selected_corpus.jsonl')
    model = resolve_local_model(spec)
    live, retriever = original(index, model, spec['package'])
    verify_pair(retriever.collection, restricted_payload(index/'data/bm25_index.pkl'), selected)
    before = regression_snapshot(live)
    info = read(index/'build_report.json')['model']
    collection, payload, report, merged, added, skipped = build_pair(index, selected, receipt['index_items'],
        lambda texts: retriever.model.encode(texts, batch_size=16, show_progress_bar=False,
                                             normalize_embeddings=False), info)
    retriever.collection, retriever.bm25, retriever.bm25_ids = collection, payload['bm25'], payload['ids']
    retriever.bm25_id_to_pos = {cid:i for i,cid in enumerate(payload['ids'])}
    after = regression_snapshot(live)
    regression = compare_regression(before, after)
    proof = query_loaded(receipt['question'], merged, live, retriever, spec['package'], candidate/'evidence')
    passed = regression['passed']
    if not passed:
        raise ValueError('Original retrieval regression failed')
    result = {'passed':passed, 'candidate_count':len(merged), 'added_items':len(added),
        'duplicate_skips':len(skipped), 'new_ids':[r['id'] for r in added],
        'existing_embeddings_unchanged':report['existing_embeddings_unchanged'],
        'existing_vector_sha256':report['existing_vector_sha256'], 'existing_ids':[r['id'] for r in selected],
        'regression':regression, 'candidate_question_action':proof['action'],
        'consistency':report['consistency'], 'network_calls':0, 'model_downloads':0}
    write(candidate/'evidence/build_validation.json', result)
    report['benchmark_passed'] = True
    write(index/'build_report.json', report)


def reopen(spec):
    bootstrap(spec)
    from stage6.common import read, rows, write
    from stage6.generations import generation
    from stage6.index_pair import restricted_payload, verify_pair, vector_hash
    from index_checks.index_common import persistent_client, COLLECTION
    candidate = generation(spec['workspace'], spec['candidate'])
    index = candidate/'index'
    result = read(candidate/'evidence/build_validation.json')
    client = persistent_client(index/'data/chromedb')
    collection = client.get_collection(COLLECTION, embedding_function=None)
    consistency = verify_pair(collection, restricted_payload(index/'data/bm25_index.pkl'), rows(index/'selected_corpus.jsonl'))
    if vector_hash(collection, result['existing_ids'], 384) != result['existing_vector_sha256']:
        raise ValueError('Existing vectors changed after writer exit')
    for cid in result['new_ids']:
        got = collection.get(ids=[cid], include=['embeddings'])
        vector = got['embeddings'][0].tolist()
        check = collection.query(query_embeddings=[vector], n_results=1, where={'clause_id':cid})
        if check['ids'] != [[cid]]:
            raise ValueError('New dense clause not queryable after restart')
    write(candidate/'evidence/reopen_validation.json', {'passed':True, 'fresh_process':True,
          'dense_queries_executed':len(result['new_ids']), 'consistency':consistency})


def query(spec):
    bootstrap(spec)
    from stage6.common import read, rows, write
    from stage6.generations import active, generation, verify_generation
    workspace = Path(spec['workspace'])
    pointer = active(workspace)
    root = generation(workspace, pointer['generation'])
    with tempfile.TemporaryDirectory(prefix='unmochon_verified_query_') as directory:
        snapshot = Path(directory)/'index'
        shutil.copytree(root/'index', snapshot)
        # Close Chroma/Rust in a grandchild before the Windows parent deletes it.
        inner = {**spec, 'snapshot':str(snapshot), 'pointer':pointer,
                 'evidence_root':str(root/'evidence')}
        spec_path = Path(directory)/'query.json'
        write(spec_path, inner)
        import subprocess
        proc = subprocess.run([sys.executable,'-m','unmochon_live.agentic_worker','query-copy','--spec',str(spec_path)],
                              cwd=spec['project'], check=False)
        if proc.returncode:
            raise ValueError('Verified query child failed')
    verify_generation(workspace, pointer['generation'], pointer['manifest_sha256'])


def query_copy(spec):
    bootstrap(spec)
    from stage6.common import rows, write
    model = resolve_local_model(spec)
    index = Path(spec['snapshot'])
    selected = rows(index/'selected_corpus.jsonl')
    live, retriever = original(index, model, spec['package'])
    from stage6.index_pair import restricted_payload, verify_pair
    verify_pair(retriever.collection, restricted_payload(index/'data/bm25_index.pkl'), selected)
    result = query_loaded(spec['question'], selected, live, retriever, spec['package'], Path(spec['evidence_root']))
    result.update(generation=spec['pointer']['generation'], network_calls=0, model_downloads=0,
                  production_modified=False)
    write(Path(spec['output']), result)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode', choices=['build','reopen','query','query-copy'])
    parser.add_argument('--spec', type=Path, required=True)
    args = parser.parse_args(argv)
    spec = json.loads(args.spec.read_text(encoding='utf-8'))
    {'build':build, 'reopen':reopen, 'query':query, 'query-copy':query_copy}[args.mode](spec)
    return 0


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(type(exc).__name__+': '+str(exc), file=sys.stderr)
        raise SystemExit(2)
