"""Question-bound Stage 5 handoff, conservative verification and literal quotes.

No model invents facts or fills missing dates. Auto approval covers clean digital
sources with a supported Stage 2 fact, or basic service application guidance.
Undated service guidance requires human review and is never verified current
policy. OCR always requires source/context review. Original tools remain available.
"""
from __future__ import annotations
from dataclasses import asdict
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import sys
import unicodedata

POLICY = 'official-evidence-v1'
AUTO_POLICY = 'official-source-auto-ingest-v2'
SERVICES = {'nid', 'passport', 'birth_registration', 'driving_license'}


def digest(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
                                   separators=(',', ':'), allow_nan=False).encode()).hexdigest()


def read(path):
    p = Path(path)
    if p.is_symlink():
        raise ValueError('Symlinked evidence input')
    return json.loads(p.read_text(encoding='utf-8-sig'))


def write(path, obj):
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(obj, ensure_ascii=False, indent=2, allow_nan=False) + '\n', encoding='utf-8')


def rows(path):
    return [json.loads(line) for line in Path(path).read_text(encoding='utf-8').splitlines() if line.strip()]


def prepare_review(processed, snapshot, package, output):
    from scripts.stage5_prepare_review import build
    return build(processed, snapshot, package, output)


def service_request(question, program):
    q = unicodedata.normalize('NFC', question).casefold()
    if program not in SERVICES:
        return False
    # A procedural answer must not stand in for fees, eligibility, amendment,
    # application status, dates, latest rules or other unsupported requests.
    if re.search(r'fee|cost|age|eligible|eligibility|correct|renew|lost|status|latest|current|\b20\d{2}\b|'
                 r'ফি|খরচ|বয়স|বয়স|যোগ্য|সংশোধন|হারিয়ে|হারিয়ে|নবায়ন|নবায়ন|সর্বশেষ|বর্তমান|কত|[০-৯]{4}', q):
        return False
    return bool(re.search(r'how|apply|application|register|registration|কিভাবে|কীভাবে|আবেদন|নিবন্ধন|করার নিয়ম|করার নিয়ম', q))


def service_text(text, program):
    """Evidence is a substantive process description, not a menu or login page."""
    t = unicodedata.normalize('NFC', text).casefold()
    identities = {
        'nid': r'\bnid\b|national identity|ভোটার|জাতীয় পরিচয়|জাতীয় পরিচয়',
        'passport': r'passport|পাসপোর্ট',
        'birth_registration': r'birth registration|জন্ম নিবন্ধন|জন্মনিবন্ধন',
        'driving_license': r'driving licen[sc]e|ড্রাইভিং লাইসেন্স',
    }
    actions = [r'fill|complete|পূরণ', r'submit|জমা|দাখিল',
               r'collect|সংগ্রহ', r'visit|উপস্থিত|যেতে|অফিসে',
               r'photograph|fingerprint|biometric|আঙুল|ছবি|বায়োমেট্রিক',
               r'register|নিবন্ধন']
    return (len(t) >= 180 and bool(re.search(identities.get(program, r'(?!)'), t))
            and bool(re.search(r'form|application|আবেদন|ফরম|ফর্ম', t))
            and sum(bool(re.search(a, t)) for a in actions) >= 2
            and not re.search(r'access denied|captcha|verify you are human|just a moment', t))


def extraction_reasons(item, human=False):
    from stage4.pdf_processing import text_quality
    text = item['text']
    reasons = []
    if item['extraction_status'] != 'processed_unverified' or item.get('extraction_issue'):
        reasons.append('extraction_requires_correction')
    if '\ufffd' in text or re.search(r'\[FAILED|\[PAGE FAILED|[\x00-\x08]', text):
        reasons.append('corrupt_text')
    if not text_quality(text, expected_script='any')['accepted_for_staging']:
        reasons.append('text_quality_gate_failed')
    if item.get('route') not in (None, 'digital_pdf_text') and not human:
        reasons.append('OCR_requires_original_source_review')
    return reasons


def labelled_date(text):
    from stage3.page_content import query_date_hints
    from stage2.evaluator import parse_date
    found = []
    for line in text.splitlines():
        if re.search(r'তারিখ|\bdate\s*:', line, re.I):
            found.extend(query_date_hints(line))
            found.extend(parse_date(line))
    found = list(dict.fromkeys(found))
    return found[0] if len(found) == 1 else None


def assess(question, items, program, ministry, human=None):
    """Return selected full-source items and reasons; no index operations."""
    from stage2.evaluator import Evidence, evaluate, infer_constraints
    human = human or {}
    selected, issues, evidence = [], [], []
    c = infer_constraints(question)
    service = service_request(question, program)
    for item in items:
        decision = human.get(item['id'])
        if decision and decision.get('decision') in ('rejected', 'pending', 'needs_correction'):
            continue
        text = item['text']
        matched = service_text(text, program) if program in SERVICES else bool(
            program == c.program and any(evaluate(question, [Evidence(
                id=item['id'], doc_id=item['raw_sha256'], ministry=ministry, text=text,
                program=program, document_kind='policy', policy_year=c.year,
                date_value=c.exact_date or '', date_precision='day', date_status='source_verified'
            )]).facts))
        if not matched:
            continue
        reasons = extraction_reasons(item, bool(decision))
        date = labelled_date(text)
        if decision:
            if not (decision.get('source_checked') is True and decision.get('context_checked') is True
                    and len(decision.get('notes', '').strip()) >= 10):
                reasons.append('explicit_source_and_context_review_required')
            supplied = decision.get('document_date') or None
            if supplied:
                from datetime import date as date_type
                try:
                    date_type.fromisoformat(supplied)
                except ValueError:
                    reasons.append('invalid_reviewed_document_date')
                date = supplied
        if program in SERVICES:
            if not service:
                reasons.append('service_question_requires_specific_fact_or_version_review')
            if not date and not (decision and decision.get('undated_guidance_reviewed') is True):
                reasons.append('unclear_document_date_requires_human_review')
        else:
            if not date:
                reasons.append('explicit_document_date_required')
            if c.needs_current_version:
                reasons.append('current_applicability_not_established')
            evidence.append(Evidence(id=item['id'], doc_id=item['raw_sha256'], ministry=ministry,
                text=text, program=program, document_kind='policy', page=item['page'],
                source_url=item['source_url'], policy_year=int(date[:4]) if date else None,
                date_value=date or '', date_precision='day' if date else 'unknown',
                date_status='human_verified' if decision else 'source_verified',
                indexed_text_sha256=hashlib.sha256(text.encode()).hexdigest(), local_source_available=True))
        if reasons:
            issues.append({'id': item['id'], 'reasons': reasons})
        else:
            selected.append({**item, 'verified_document_date': date,
                             'verification_method': 'human_source_context_review' if decision else POLICY,
                             'date_status': 'human_verified' if date and decision else
                                            'source_verified' if date else 'undated_service_guidance',
                             'review_notes': decision.get('notes', '') if decision else ''})
    assessment = None
    if program not in SERVICES:
        assessment = evaluate(question, evidence).to_dict()
        if assessment['action'] != 'ANSWER_FROM_EVIDENCE':
            issues.append({'id': 'question', 'reasons': [assessment['reason']]})
    if not selected:
        issues.append({'id': 'question', 'reasons': ['no_complete_relevant_verified_evidence']})
    return selected, issues, assessment


def index_items(selected, program, ministry, request_id):
    # Reuse Stage 5's bounded splitter. Original quotes are not rewritten.
    from stage5.chunks import split_size
    output = []
    for item in selected:
        for quote in split_size(item['text'], limit=1400):
            if len(quote) < 50:
                continue
            title = item['title'] or item['text'].splitlines()[0][:160]
            date = item['verified_document_date'] or ''
            identity = {'raw': item['raw_sha256'], 'page': item['page'], 'quote': quote,
                        'date': date, 'program': program, 'url': item['source_url']}
            cid = 'AR_' + digest(identity)
            meta = {'clause_id': cid, 'doc_id': 'AR_' + item['raw_sha256'],
                'ministry': ministry, 'tag': ministry, 'program': program,
                'page_number': item['page'] or 0, 'source_url': item['source_url'],
                'title': title, 'source_raw_sha256': item['raw_sha256'],
                'source_quote': quote, 'source_quote_sha256': hashlib.sha256(quote.encode()).hexdigest(),
                'source_item_id': item['id'], 'date_value': date, 'date_status': item['date_status'],
                'date_precision': 'day' if date else 'unknown', 'is_table': False,
                'validation_status': 'question_bound_verified_source',
                'verification_method': item['verification_method'], 'agentic_verified': True,
                'human_content_approved': item['verification_method'] == 'human_source_context_review',
                'current_version_verified': False, 'needs_review': False,
                'claim_kind': 'service_guidance' if program in SERVICES else 'policy_clause',
                'proposal_id': cid, 'proposal_sha256': digest(identity),
                'candidate_index_import_authorized': True}
            if item['verification_method'] == AUTO_POLICY:
                meta.update(agentic_ingested=True, agentic_verified=False,
                    validation_status='official_source_integrity_checked',
                    content_status='automatically_extracted_official_source',
                    fetched_at=item.get('fetched_at') or '',
                    extraction_route=item.get('route') or 'html_text',
                    source_urls=json.dumps(item.get('source_urls') or [item['source_url']],ensure_ascii=False),
                    source_kind='pdf' if item['page'] else 'webpage')
            output.append({'id': cid, 'text': quote, 'metadata': meta})
    unique = {x['id']: x for x in output}
    return list(unique.values())


def verify_review(review_dir, question, program, ministry, *, human=None, save=True):
    """Recheck original Stage 5 bindings and Stage 3 receipts before approval."""
    from .stage4_dynamic import validate_app_snapshot
    from scripts.stage5_prepare_review import canonical, digest as bytes_digest
    review_dir = Path(review_dir).resolve()
    manifest = read(review_dir / 'review_manifest.json')
    if bytes_digest(canonical(manifest)) != (review_dir/'review_manifest.sha256').read_text().strip():
        raise ValueError('Stage 5 manifest changed')
    for filename, sha in manifest['source_file_hashes'].items():
        path = Path(filename)
        if path.is_symlink() or hashlib.sha256(path.read_bytes()).hexdigest() != sha:
            raise ValueError('Stage 4 evidence changed after staging')
    valid = validate_app_snapshot(manifest['raw_snapshot'])
    if (valid['hash'] != manifest['source_snapshot_sha256'] or
            valid['request_id'] != manifest['request_id'] or
            valid['generation'] != manifest['generation_at_consent'] or
            valid['plan'].question != unicodedata.normalize('NFC', question) or
            valid['plan'].program != program or valid['plan'].ministry != ministry):
        raise ValueError('Research source/question/scope binding changed')
    consent = read(Path(manifest['raw_snapshot']) / 'conditional_update_consent.json')
    if (consent.get('policy') != POLICY or consent.get('allow_conditional_update') is not True
            or consent.get('request_id') != manifest['request_id']
            or consent.get('question_sha256') != valid['plan'].question_sha256):
        raise ValueError('No question-bound conditional update authorization')
    audit = read(Path(manifest['raw_snapshot']) / 'latest_consent_audit.json')
    if digest(consent) not in audit[1]['consent_note']:
        raise ValueError('Conditional update scope is not bound to the consent decision')
    items = rows(review_dir/'review_items.jsonl')
    if human:
        decisions = read(review_dir/'human_decisions.json')
        record = read(review_dir/'content_review_record.json')
        if (record.get('decisions_sha256') != digest(decisions)
                or {d['id']:d for d in decisions['decisions']} != human
                or record.get('request_id') != valid['request_id']
                or not record.get('reviewer')):
            raise ValueError('Human decisions are not bound to the original Stage 5 review record')
    if [{k:v for k,v in x.items() if k != 'text'} for x in items] != manifest['items']:
        raise ValueError('Stage 5 review item metadata changed')
    for x in items:
        if hashlib.sha256(x['text'].encode()).hexdigest() != x['text_sha256']:
            raise ValueError('Stage 5 source text changed')
    if str(Path(__file__).resolve().parents[2]/'reference_pipelines/stage5') not in sys.path:
        sys.path.append(str(Path(__file__).resolve().parents[2]/'reference_pipelines/stage5'))
    selected, issues, assessment = assess(question, items, program, ministry, human)
    added = index_items(selected, program, ministry, manifest['request_id']) if not issues else []
    if not added and not issues:
        issues.append({'id':'question', 'reasons':['no_indexable_clauses']})
    result = {'schema_version': 1, 'policy': POLICY, 'request_id': manifest['request_id'],
        'question': question, 'program': program, 'ministry': ministry,
        'generation_at_consent': valid['generation'], 'review_dir': str(review_dir),
        'source_snapshot_sha256': valid['hash'], 'consent_sha256': digest(consent),
        'status': 'review_required' if issues else 'verified_eligible',
        'issues': issues, 'assessment': assessment, 'index_items': added,
        'human_decisions': human or {}, 'current_policy_verified': False,
        'index_import_authorized': not issues, 'index_writes': 0}
    result['receipt_sha256'] = digest(result)
    if save:
        write(review_dir/'verification_receipt.json', result)
    return result


def validate_receipt(path):
    supplied = read(path)
    copy = dict(supplied)
    wanted = copy.pop('receipt_sha256')
    if digest(copy) != wanted or supplied['status'] != 'verified_eligible':
        raise ValueError('Evidence verification receipt is invalid or not eligible')
    if supplied.get('policy') == AUTO_POLICY:
        checked = ingest_sources(supplied['review_dir'], supplied['question'], supplied['program'],
                                 supplied['ministry'], save=False)
    else:
        checked = verify_review(supplied['review_dir'], supplied['question'], supplied['program'],
                                supplied['ministry'], human=supplied['human_decisions'], save=False)
    if checked != supplied:
        raise ValueError('Evidence/consent changed after verification')
    return checked


def ingest_sources(review_dir, question, program, ministry, *, save=True):
    """Automatically ingest ALL readable crawled content, including undated OCR.

    Integrity checks establish source provenance, not factual approval or current
    legal applicability. Unreadable pages are recorded and skipped, never sent
    to a human approval queue. Query relevance is decided later by retrieval.
    """
    from .stage4_dynamic import validate_app_snapshot
    from scripts.stage5_prepare_review import canonical, digest as bytes_digest
    from stage4.pdf_processing import text_quality
    review_dir = Path(review_dir).resolve()
    manifest = read(review_dir/'review_manifest.json')
    if bytes_digest(canonical(manifest)) != (review_dir/'review_manifest.sha256').read_text(encoding='ascii').strip():
        raise ValueError('Source staging manifest changed')
    for filename, sha in manifest['source_file_hashes'].items():
        path = Path(filename)
        if path.is_symlink() or hashlib.sha256(path.read_bytes()).hexdigest() != sha:
            raise ValueError('Extracted source changed after staging')
    valid = validate_app_snapshot(manifest['raw_snapshot'])
    if (valid['hash'] != manifest['source_snapshot_sha256'] or
            valid['request_id'] != manifest['request_id'] or
            valid['generation'] != manifest['generation_at_consent'] or
            valid['plan'].question != unicodedata.normalize('NFC', question) or
            valid['plan'].program != program or valid['plan'].ministry != ministry):
        raise ValueError('Source/question/permission binding changed')
    consent = read(Path(manifest['raw_snapshot'])/'conditional_update_consent.json')
    if (consent.get('policy') != AUTO_POLICY or consent.get('allow_conditional_update') is not True or
            consent.get('request_id') != valid['request_id'] or
            consent.get('question_sha256') != valid['plan'].question_sha256):
        raise ValueError('Automatic source ingestion was not authorized')
    audit = read(Path(manifest['raw_snapshot'])/'latest_consent_audit.json')
    if digest(consent) not in audit[1]['consent_note']:
        raise ValueError('Automatic ingestion permission audit mismatch')
    items = rows(review_dir/'review_items.jsonl')
    if [{k:v for k,v in x.items() if k != 'text'} for x in items] != manifest['items']:
        raise ValueError('Staged source metadata changed')
    fetched = {a.raw_sha256:a.fetched_at_utc for a in valid['result'].artifacts}
    accepted, skipped = [], []
    for item in items:
        if hashlib.sha256(item['text'].encode()).hexdigest() != item['text_sha256']:
            raise ValueError('Staged source text hash mismatch')
        text = item['text']
        quality = text_quality(text, expected_script='any')
        if (not quality['accepted_for_staging'] or '\ufffd' in text or
                re.search(r'access denied|verify you are human|just a moment|captcha challenge', text, re.I)):
            skipped.append({'id':item['id'], 'reasons':['unreadable_or_access_challenge']})
            continue
        date = labelled_date(text)
        accepted.append({**item, 'verified_document_date':date,
                         'verification_method':AUTO_POLICY,
                         'date_status':'source_date_observed' if date else 'not_recorded',
                         'fetched_at':fetched[item['raw_sha256']]})
    # Stage 5's original splitter is deterministic and preserves literal text.
    stage5 = str(Path(__file__).resolve().parents[2]/'reference_pipelines/stage5')
    if stage5 not in sys.path:
        sys.path.append(stage5)
    added = index_items(accepted, program, ministry, valid['request_id'])
    result = {'schema_version':1, 'policy':AUTO_POLICY, 'request_id':valid['request_id'],
              'question':question, 'program':program, 'ministry':ministry,
              'generation_at_consent':valid['generation'], 'review_dir':str(review_dir),
              'source_snapshot_sha256':valid['hash'], 'consent_sha256':digest(consent),
              'status':'verified_eligible' if added else 'no_usable_evidence',
              'issues':[] if added else [{'id':'question','reasons':['no_readable_source_chunks']}],
              'skipped_items':skipped, 'assessment':None, 'index_items':added,
              'human_decisions':{}, 'human_review_required':False,
              'current_policy_verified':False, 'index_import_authorized':bool(added), 'index_writes':0}
    result['receipt_sha256'] = digest(result)
    if save:
        write(review_dir/'verification_receipt.json', result)
    return result
