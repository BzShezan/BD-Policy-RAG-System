"""Read-only, offline bridge into Stage 6's VERIFIED paired hybrid generation.

Stage 6 owns the generation pointer and both indexes. This process must not
open or write an independent ChromaDB/BM25 pair. Stage 6 validates, snapshots,
queries and re-verifies its pinned generation in a separate child process.
"""
import asyncio
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

from .schemas import Evidence, RagResult


class Stage6BridgeError(RuntimeError):
    pass


def _all_sources(document):
    """Carry original quotes with their own provenance, never invent dates/links."""
    if not isinstance(document, dict):
        return []
    result = []
    for version in document.get('source_versions', []):
        for clause in version.get('clauses', []):
            meta = clause.get('source') or {}
            result.append(Evidence(
                id=clause['index_id'], text=clause['source_quote'],
                source_kind='corpus_clause', document_id=version.get('review_group'),
                title=version.get('document_subject') or version.get('review_group') or '',
                page=meta.get('page'), source_url=meta.get('source_url') or version.get('source_url'),
                published_at=version.get('printed_order_date'),
                metadata={**meta, 'review_group': version.get('review_group'),
                          'kind': clause.get('kind'),
                          'criterion_number': clause.get('criterion_number'),
                          'eligibility_group_id': clause.get('eligibility_group_id'),
                          'proposal_id': clause.get('proposal_id')},
                document_metadata={
                    'printed_order_date': version.get('printed_order_date'),
                    'document_subject': version.get('document_subject'),
                    'raw_sha256': version.get('raw_sha256'),
                    'current_policy_verified': False},
                verification='corpus_only', freshness='not_checked'))
    return result


def convert_stage6_result(payload, top_k=3):
    """Unmodified Stage 6 actions remain authoritative; no answer hallucination."""
    if (not isinstance(payload, dict) or payload.get('automatic_winner_selected') is True
            or payload.get('current_policy_verified') is True):
        raise Stage6BridgeError('Invalid Stage 6 result or unreviewed current-policy conclusion')
    action = payload.get('action')
    if action not in {'ANSWER_FROM_EVIDENCE', 'SHOW_SOURCE_VERSIONS',
                      'REQUEST_RESEARCH_PERMISSION', 'ASK_CLARIFICATION',
                      'DECLINE_OUT_OF_DOMAIN', 'HUMAN_REVIEW',
                      'VERIFY_LOCAL_SOURCE', 'RETRY_RETRIEVAL', 'RETRY_LOCAL'}:
        # Reject unknown actions rather than treating them as sufficient.
        raise Stage6BridgeError(f'Unknown Stage 6 action: {action!r}')
    evidence = []
    for row in payload.get('answer_results', []):
        meta = row.get('metadata') or {}
        docmeta = row.get('document_metadata') or {}
        page = row.get('page') or None
        raw_sha = meta.get('source_raw_sha256')
        ingested = bool(meta.get('agentic_ingested') or meta.get('agentic_verified'))
        viewer = row.get('viewer_url')
        if raw_sha and page and not viewer:
            viewer = f'/pdfjs/web/viewer.html?file=/verified-pdf/{raw_sha}.pdf#page={page}'
        evidence.append(Evidence(id=row['clause_id'], text=row['clause_text'],
            source_kind='official_web' if ingested and not page else 'corpus_clause',
            document_id=row.get('doc_id'), title=(meta.get('title') if ingested else None) or row.get('display_name') or row.get('doc_id') or '',
            source_url=row.get('source_url') or meta.get('source_url'), page=page,
            ministry=row.get('ministry'), viewer_url=viewer,
            confidence_tier=row.get('confidence_tier'), extracted=row.get('extracted', []),
            explanation=row.get('explanation'), bbox=row.get('bbox'),
            published_at=meta.get('date_value') or docmeta.get('date_display') or None,
            checked_at=meta.get('fetched_at'), content_sha256=raw_sha,
            verification='official_fetched' if ingested else 'corpus_only',
            metadata=meta, document_metadata=docmeta))
    if not evidence and 'answer_results' not in payload:
        evidence = _all_sources(payload)
    if not evidence and 'answer_results' not in payload:
        for source in payload.get('retrieved_source_versions', []) or payload.get('legacy_source_versions', []):
            for clause in source.get('clauses', []):
                meta = clause.get('source_metadata') or {}
                page = clause.get('page') or None
                raw_sha = meta.get('source_raw_sha256')
                viewer = (f'/pdfjs/web/viewer.html?file=/verified-pdf/{raw_sha}.pdf#page={page}'
                          if meta.get('agentic_verified') and raw_sha and page else None)
                evidence.append(Evidence(id=str(clause['id']),text=clause['text'],
                    source_kind='corpus_clause', document_id=source.get('doc_id'),
                    title=meta.get('title') or meta.get('doc_id') or '',
                    page=page, source_url=source.get('source_url'), viewer_url=viewer,
                    verification='official_fetched' if meta.get('agentic_verified') else 'corpus_only',
                    content_sha256=meta.get('source_raw_sha256'),
                    published_at=source.get('date_value') or None,
                    metadata=meta,
                    document_metadata={'date_status': source.get('date_status'),
                                       'current_policy_verified': False}))
    # Pydantic API contract caps displayed result cards at 10; the full source
    # editions/quotes remain in source_versions on the response and in the UI.
    seen = set()
    cards = []
    for e in evidence:
        if e.id not in seen:
            seen.add(e.id)
            cards.append(e)
        if len(cards) >= min(top_k,10): break
    ready = action in {'ANSWER_FROM_EVIDENCE','SHOW_SOURCE_VERSIONS'} and bool(cards)
    warnings = ['Research is not authorized; a NEW question-bound permission is required.'] if action == 'REQUEST_RESEARCH_PERMISSION' else []
    if payload.get('translation_note'):
        warnings.append(payload['translation_note'])
    if action == 'SHOW_SOURCE_VERSIONS':
        warnings.append('Historical source editions are displayed without deciding which currently applies.')
    trigger = payload.get('research_trigger')
    if action == 'REQUEST_RESEARCH_PERMISSION' and not trigger:
        # The child Stage 2 PermissionController is intentionally short lived.
        # Its historical request ID is NOT a usable grant in this app process.
        original = (payload.get('assessment') or {}).get('research_request') or {}
        plan = original.get('plan') or {}
        trigger = {'question_sha256': plan.get('question_sha256'),
                   'program': plan.get('program'), 'ministry': plan.get('ministry'),
                   'reason': plan.get('reason'), 'permission_granted': False,
                   'execution_called': False,
                   'next_step': 'fresh_question_bound_Stage3_consent_required',
                   'full_corpus_absence_proven': False}
    return RagResult(
        backend='stage6_original_hybrid_verified_pair', evidence=cards, sufficient=ready,
        reason=payload.get('reason') or action, warnings=warnings,
        action=action, source_versions=payload.get('source_versions', []),
        historical_reference_only=payload.get('historical_reference_only', []),
        source_variants=payload.get('source_variants', []),
        retrieved_source_versions=payload.get('retrieved_source_versions',
                                               payload.get('legacy_source_versions', [])),
        research_trigger=trigger,
        generation=payload.get('generation'),
        resolution=payload.get('resolution', 'pending_teammate_update_show_all'),
        automatic_winner_selected=False,
        current_policy_verified=bool(payload.get('current_policy_verified', False)),
        teammate_annotations=payload.get('teammate_annotations'),
        original_results=payload.get('original_results',[]),
        conflicts=payload.get('conflicts', []),
        intents=payload.get('intents',[]), ministry=payload.get('ministry'),
        translated=payload.get('translated'))


class Stage6Backend:
    def __init__(self, settings, run_query=None):
        self.settings = settings
        self.root = Path(settings.stage6_package or (settings.root / 'reference_pipelines/stage6')).resolve()
        self.workspace = Path(settings.stage6_workspace or (settings.root / 'data/stage6_workspace')).resolve()
        self.model_cache = Path(settings.stage6_model_cache).resolve() if settings.stage6_model_cache else None
        self.timeout = settings.stage6_timeout
        self.python = settings.stage6_python or sys.executable
        self.run_query = run_query or self._run_query
        if run_query is None:
            if not (self.root / 'run_stage6_query.py').is_file():
                raise Stage6BridgeError('Stage 6 package entrypoint is missing')
            if not (self.workspace / 'active.json').is_file():
                raise Stage6BridgeError('Stage 6 active generation pointer is missing')

    def _run_query(self, question):
        with tempfile.TemporaryDirectory(prefix='unmochon_app_stage6_') as temp:
            output = Path(temp) / 'result.json'
            spec = Path(temp)/'query_spec.json'
            spec.write_text(json.dumps({'package':str(self.root), 'workspace':str(self.workspace),
                'question':question, 'output':str(output), 'model_cache':str(self.model_cache or ''),
                'project':str(self.settings.root),
                'stage4_package':str(self.settings.stage4_package or self.settings.root/'reference_pipelines/stage4'),
                'registry':str(self.settings.research_registry or self.settings.root/'config/research_sources.json')},
                ensure_ascii=False),encoding='utf-8')
            cmd = [self.python,'-m','unmochon_live.agentic_worker','query','--spec',str(spec)]
            # Windows consoles commonly default to a legacy code page (cp1252,
            # cp936, ...). Stage 6's worker prints original Bangla source quotes
            # AFTER writing and verifying its JSON result. Without UTF-8 output,
            # that final print can fail and return exit status 2 even though the
            # generation and the retrieved evidence are valid. This environment
            # is inherited by run_stage6_query.py AND its worker subprocess.
            env = dict(os.environ, HF_HUB_OFFLINE='1', TRANSFORMERS_OFFLINE='1',
                       HF_DATASETS_OFFLINE='1', HF_HUB_DISABLE_TELEMETRY='1',
                       PYTHONIOENCODING='utf-8', PYTHONUTF8='1')
            env['PYTHONPATH'] = str(self.settings.root/'src')+os.pathsep+str(self.settings.root)
            try:
                process = subprocess.run(cmd, cwd=self.settings.root, env=env,
                                         capture_output=True, text=True,
                                         encoding='utf-8', errors='replace',
                                         timeout=self.timeout, check=False)
            except (OSError, subprocess.TimeoutExpired) as ex:
                raise Stage6BridgeError('Stage 6 child failed to run locally') from ex
            if process.returncode or not output.is_file():
                # Do not forward arbitrary stderr that may include local filenames or query text.
                raise Stage6BridgeError('Stage 6 query verification failed; no fallback index was used')
            if output.stat().st_size > 8_000_000:
                raise Stage6BridgeError('Stage 6 output exceeded fixed size limit')
            return json.loads(output.read_text(encoding='utf-8'))

    async def search(self, question, top_k):
        try:
            raw = await asyncio.to_thread(self.run_query,question)
            return convert_stage6_result(raw,top_k)
        except Exception as ex:  # Fail closed; never use a different generation/index.
            return RagResult(backend='stage6_original_hybrid_verified_pair',
                reason='Failed closed: verified query could not be completed',
                warnings=[str(ex) if isinstance(ex, Stage6BridgeError) else 'Stage 6 result invalid; no fallback index used.'])
