"""Offline Stage 4 processor for freshly-consented *arbitrary* Live-app crawls.

The original Stage 4 entrypoints intentionally pin D01/D02/D03 pilot IDs.
This adapter does not forge pilot IDs or weaken their package checks. It checks
Live-app provenance against the immutable approved scope, original crawl
receipts, raw hashes, and one-use consent audit before calling the original
HTML/PDF extraction primitives. No network, answer generation, or index write.
"""
from __future__ import annotations

import argparse
from dataclasses import asdict
import json
import os
from pathlib import Path
import re
import socket
import sys
import tempfile
import time
from unittest.mock import patch
from urllib.parse import urljoin, urlsplit


def _read(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def _save(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(data, ensure_ascii=False, indent=2) + '\n'
    # A hash-named JSON file can already be close to Windows MAX_PATH.
    # Keep the exclusive temporary sibling independent of that long filename.
    fd, name = tempfile.mkstemp(prefix='.s4-', suffix='.tmp', dir=path.parent)
    tmp = Path(name)
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as stream:
            stream.write(payload)
        os.replace(tmp, path)
    finally:
        tmp.unlink(missing_ok=True)


def validate_app_snapshot(snapshot, registry=None):
    """Returns validated Stage3 result/plan only after all provenance checks."""
    from stage2.permissions import canonical
    from stage3.crawler import CrawlResult, RawArtifact, verify_result
    from .research_registry import registry_for_scope
    from stage4.html_processing import snapshot_hash

    root = Path(snapshot).resolve(strict=True)
    if not root.is_dir():
        raise ValueError('Only a dedicated app Stage 3 snapshot directory is accepted')
    before = snapshot_hash(root)  # verifies the Stage3 ownership marker and size limits
    summary = _read(root / 'stage3_app_summary.json')
    if (summary.get('schema_version') != 1 or summary.get('status') != 'staged_unverified'
            or summary.get('source_approval') is not False
            or summary.get('current_policy_verified') is not False
            or summary.get('index_writes') != 0):
        raise ValueError('Not an unapproved, read-only app crawl receipt')
    request_id = summary.get('request_id')
    if not isinstance(request_id, str) or not request_id:
        raise ValueError('Missing consent request identity')
    scope = summary.get('scope')
    if not isinstance(scope, dict):
        raise ValueError('Missing authoritative scope')
    registry = registry or registry_for_scope(scope)
    try:
        plan = registry.make_plan(scope['question'], scope['program'], scope['ministry'], scope['reason'])
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError('Unrecognized ministry/program/plan') from exc
    registry.check_plan(plan)
    if canonical(asdict(plan)) != canonical(scope):
        raise ValueError('Stored scope differs from registry-approved scope')
    raw = summary.get('result')
    if not isinstance(raw, dict):
        raise ValueError('Missing crawl receipt')
    artifacts = tuple(RawArtifact(**{**a, 'redirects': tuple(a['redirects'])}) for a in raw['artifacts'])
    result = CrawlResult(**{**raw, 'artifacts': artifacts, 'events': tuple(raw['events']),
                            'visited': tuple(raw['visited'])})
    if not artifacts:
        raise ValueError('No evidence artifacts available')
    run_ids = set()
    for artifact in artifacts:
        match = re.fullmatch(r'runs/([0-9a-f]{32})/raw/' + artifact.raw_sha256 + r'\.(html|pdf)', artifact.relative_path)
        if not match:
            raise ValueError('Invalid staged artifact location')
        run_ids.add(match.group(1))
    if len(run_ids) != 1:
        raise ValueError('A Live crawl must have exactly one staged run')
    run = root / 'runs' / next(iter(run_ids))
    if canonical(_read(run / 'crawl_receipt.json')) != canonical(raw):
        raise ValueError('Crawl receipt disagrees with the app handoff')
    audit = _read(root / 'latest_consent_audit.json')
    if (not isinstance(audit, list) or [e.get('event') for e in audit] !=
        ['request_created', 'consent_decision', 'permit_consumed', 'raw_evidence_staged']
        or any(e.get('request_id') != request_id for e in audit)
        or audit[1].get('state') != 'approved' or not audit[1].get('actor')
        or audit[3].get('documents') != len(artifacts)
        or audit[3].get('index_updated') is not False):
        raise ValueError('Fresh approved one-use consent audit does not match')
    # Strict source URL/referrer, canonical host, bytes, SHA256, budgets, redirects.
    verify_result(plan, result, root)
    attempts = sum(e.get('event') == 'http_attempt' for e in result.events)
    count = summary.get('network_request_attempts')
    if type(count) is not int or count > plan.max_http_requests or count > attempts or attempts != result.budget['http_requests']:
        raise ValueError('Network attempts do not match the consented budget')
    if snapshot_hash(root) != before:
        raise ValueError('Raw snapshot changed during validation')
    return {'root': root, 'hash': before, 'request_id': request_id,
            'plan': plan, 'result': result, 'generation': summary.get('generation_at_consent')}


def _html(snapshot, output, valid):
    from stage3.scope import LinkProof, canonical_url, in_scope, sha_bytes
    from stage3.page_content import analyze_html
    from stage4.html_processing import prepare_output
    output = prepare_output(output, snapshot)
    docs, links = [], {}
    for a in valid['result'].artifacts:
        if not a.relative_path.endswith('.html'):
            continue
        body = (snapshot / a.relative_path).read_bytes()
        page = analyze_html(body, a.content_type)
        doc = {'schema_version': 1, 'source': asdict(a), 'title': page.title,
               'content_heading': page.content_heading, 'text': page.text,
               'text_sha256': sha_bytes(page.text.encode('utf-8')),
               'tables': page.tables, 'document_date': None,
               'evidence_status': 'processed_unverified', 'human_approval': False,
               'requires_human_import_approval': True}
        _save(output / 'documents' / (a.raw_sha256 + '.json'), doc)
        docs.append({'raw_sha256': a.raw_sha256, 'source_url': a.url,
                     'text_characters': len(page.text), 'table_count': len(page.tables)})
        for link in page.links:
            try:
                target = canonical_url(urljoin(a.url, link.href))
                if urlsplit(target).path.lower().endswith('.pdf') and in_scope(target, valid['plan'],
                    LinkProof(a.url, a.raw_sha256, target)):
                    links[target] = {'url': target, 'government_referrer_url': a.url,
                                     'government_referrer_sha256': a.raw_sha256,
                                     'status': 'unfetched_pdf_link_candidate'}
            except (ValueError, TypeError):
                pass
    summary = {'schema_version': 1, 'mode': 'app_dynamic_offline_html_processing',
               'source_request_id': valid['request_id'], 'html_artifacts_processed': len(docs),
               'documents': docs, 'pdf_link_candidates_unfetched': list(links.values()),
               'OCR_CER': None, 'OCR_WER': None, 'current_policy_verified': False,
               'network_calls': 0, 'index_writes': 0, 'human_review_required': True}
    _save(output / 'stage4_html_summary.json', summary)
    return summary


def _pdf(snapshot, output, valid, tesseract=None):
    from stage4.pdf_processing import (MAX_PAGES, MAX_OCR_PAGES, MAX_SECONDS, DPI, check_pdf_page,
                                       text_quality, find_tesseract, validate_models, ocr_image,
                                       prepare_pdf_output, PACKAGE)
    from stage3.scope import sha_bytes
    pdfs = [a for a in valid['result'].artifacts if a.relative_path.endswith('.pdf')]
    if not pdfs:
        return {'schema_version': 1, 'mode': 'app_dynamic_offline_pdf_processing',
                'pdf_artifacts_processed': 0, 'pdf_pages': 0, 'pages_needing_extraction_review': 0,
                'documents': [], 'network_calls': 0, 'index_writes': 0, 'human_review_required': True}
    try:
        import pymupdf
    except ImportError as exc:
        raise RuntimeError('PyMuPDF missing: python -m pip install "PyMuPDF==1.26.6"') from exc
    started = time.monotonic()
    expected_script = 'any' if valid['plan'].program in {'nid','passport','birth_registration','driving_license'} else 'bengali'
    page_count, documents, incomplete, ocr_count = 0, [], [], 0
    # Validate total page budget before writing output. Refuse encrypted input.
    for a in pdfs:
        with pymupdf.open(snapshot / a.relative_path) as doc:
            if doc.is_encrypted or doc.needs_pass:
                raise ValueError('Encrypted PDF unsupported')
            page_count += len(doc)
            if page_count > MAX_PAGES:
                raise ValueError('Total PDF pages exceed offline processing budget')
    root = prepare_pdf_output(output, snapshot)
    tesseract_exe, models = None, None
    for a in pdfs:
        pages = []
        with pymupdf.open(snapshot / a.relative_path) as doc:
            for index, page in enumerate(doc):
                if time.monotonic() - started >= MAX_SECONDS:
                    raise TimeoutError('PDF extraction deadline exceeded')
                check_pdf_page(page)
                digital = page.get_text('text', sort=True)
                q = text_quality(digital, expected_script=expected_script)
                text, route, issue = digital, 'digital_pdf_text', None
                if not q['accepted_for_staging']:
                    text, route = '', 'ocr_pending'
                    if ocr_count >= MAX_OCR_PAGES:
                        issue = 'OCR page budget exhausted'
                    else:
                        try:
                            if models is None:
                                models = Path(os.getenv('STAGE4_OCR_MODELS', str(PACKAGE / 'models')))
                                validate_models(models)
                            if tesseract_exe is None:
                                tesseract_exe = find_tesseract(tesseract)
                            key = a.raw_sha256 + '_p' + str(index + 1)
                            image = root / 'images' / (key + '.png')
                            image.parent.mkdir(parents=True, exist_ok=True)
                            page.get_pixmap(dpi=DPI, colorspace=pymupdf.csGRAY, alpha=False).save(image)
                            ocr_count += 1
                            base = root / 'ocr_outputs' / key
                            base.parent.mkdir(parents=True, exist_ok=True)
                            text, _words = ocr_image(tesseract_exe, image, base, models,
                                                     MAX_SECONDS - (time.monotonic() - started))
                            route = 'bengali_ocr_fallback'
                        except (OSError, ValueError, RuntimeError, TimeoutError) as exc:
                            issue, route = type(exc).__name__ + ': ' + str(exc), 'ocr_needs_review'
                final = text_quality(text, expected_script=expected_script)
                if not final['accepted_for_staging']:
                    incomplete.append({'raw_sha256': a.raw_sha256, 'page': index + 1,
                                       'issue': issue or 'Text quality gate did not pass'})
                payload = {'schema_version': 1, 'raw_sha256': a.raw_sha256, 'source_url': a.url,
                           'page': index + 1, 'route': route, 'text': text,
                           'text_sha256': sha_bytes(text.encode('utf-8')), 'digital_quality': q,
                           'final_quality': final, 'extraction_issue': issue,
                           'document_date': None, 'evidence_status': 'processed_unverified' if final['accepted_for_staging'] else 'needs_extraction_review',
                           'human_approval': False, 'requires_human_import_approval': True}
                _save(root / 'pages' / (a.raw_sha256 + '_p' + str(index + 1) + '.json'), payload)
                pages.append({'page': index + 1, 'route': route,
                              'accepted_for_staging': final['accepted_for_staging']})
        _save(root / 'documents' / (a.raw_sha256 + '.json'), {'schema_version': 1,
              'source': asdict(a), 'pages': pages, 'document_date': None,
              'requires_human_import_approval': True, 'current_policy_verified': False})
        documents.append({'raw_sha256': a.raw_sha256, 'source_url': a.url, 'pages': len(pages)})
    summary = {'schema_version': 1, 'mode': 'app_dynamic_offline_pdf_processing',
               'pdf_artifacts_processed': len(documents), 'pdf_pages': page_count,
               'OCR_engine_invocations': ocr_count, 'pages_needing_extraction_review': len(incomplete),
               'page_failures': incomplete, 'documents': documents, 'OCR_CER': None, 'OCR_WER': None,
               'current_policy_verified': False, 'human_review_required': True,
               'network_calls': 0, 'index_writes': 0}
    _save(root / 'stage4_pdf_summary.json', summary)
    return summary


def process_dynamic(snapshot, output, package, tesseract=None):
    snapshot, output, package = Path(snapshot).resolve(), Path(output).resolve(), Path(package).resolve()
    if output == snapshot or output.is_relative_to(snapshot) or output == package or output.is_relative_to(package):
        raise ValueError('Refusing to write inside a source or Stage 4 package')
    if output.exists() and any(output.iterdir()):
        raise ValueError('Output must be a fresh, empty processing directory')
    # The original package source remains checksum-bound: no modifications.
    from .runtime import load_stage4
    count = load_stage4(package)
    from stage4.html_processing import snapshot_hash
    valid = validate_app_snapshot(snapshot)
    with patch.object(socket, 'socket', side_effect=AssertionError('Offline Stage 4 forbids sockets')):
        html = _html(snapshot, output / 'html', valid)
        pdf = _pdf(snapshot, output / 'pdf', valid, tesseract)
    if snapshot_hash(snapshot) != valid['hash']:
        raise ValueError('Source snapshot changed during Stage 4 processing')
    report = {'schema_version': 1, 'mode': 'app_dynamic_offline_stage4',
              'request_id': valid['request_id'], 'generation_at_consent': valid['generation'],
              'status': 'review_required' if pdf['pages_needing_extraction_review'] == 0 else 'processing_review_needed',
              'source_snapshot_sha256': valid['hash'], 'source_snapshot_unchanged': True,
              'package_files_verified': count, 'artifacts_verified': len(valid['result'].artifacts),
              'html_artifacts_processed': html['html_artifacts_processed'],
              'pdf_artifacts_processed': pdf['pdf_artifacts_processed'],
              'pdf_pages': pdf['pdf_pages'],
              'pages_needing_extraction_review': pdf['pages_needing_extraction_review'],
              'human_content_review_required': True, 'index_import_authorized': False,
              'current_policy_verified': False, 'network_calls': 0, 'index_writes': 0,
              'html_output': str(output / 'html'), 'pdf_output': str(output / 'pdf')}
    _save(output / 'stage4_dynamic_summary.json', report)
    return report


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--snapshot', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--package', type=Path, required=True)
    p.add_argument('--tesseract', type=Path)
    args = p.parse_args(argv)
    try:
        report = process_dynamic(args.snapshot, args.output, args.package, args.tesseract)
        print(json.dumps({'status': report['status'], 'artifacts_verified': report['artifacts_verified'],
                          'html': report['html_artifacts_processed'], 'pdf': report['pdf_artifacts_processed'],
                          'index_writes': 0}, ensure_ascii=False))
        return 0
    except Exception as exc:
        print(type(exc).__name__ + ': ' + str(exc), file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
