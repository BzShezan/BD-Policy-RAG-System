"""Offline Stage3/4 provenance audit and *unapproved* Stage5 review queue.

This script never crawls, imports code from sealed stage packages, or writes to a
retrieval index. Its report is NOT a content/index approval receipt.
"""
from __future__ import annotations
import argparse
import csv
import hashlib
import ipaddress
import json
from pathlib import Path
import re
import sys
from urllib.parse import urlsplit

HEX64 = re.compile(r'^[0-9a-f]{64}$')

class AuditFailure(ValueError):
    pass


def fail(message):
    raise AuditFailure(message)


def load_object(path):
    if not path.is_file() or path.is_symlink():
        fail('Missing, or symlinked JSON file: ' + str(path))
    data = json.loads(path.read_text(encoding='utf-8'))
    if not isinstance(data, dict):
        fail('Expected JSON object: ' + str(path))
    return data


def in_directory(root, relative):
    if not isinstance(relative, str) or not relative or '\\' in relative:
        fail('Invalid raw file relative path')
    from pathlib import PurePosixPath
    p = PurePosixPath(relative)
    if p.is_absolute() or any(s in ('..', '.') for s in p.parts):
        fail('Traversal in raw relative path')
    target = root.joinpath(*p.parts)
    if not target.resolve().is_relative_to(root.resolve()):
        fail('Raw file escapes snapshot')
    if any(t.is_symlink() for t in [target, *list(target.parents)[:len(p.parts)]]) or not target.is_file():
        fail('Missing or symlinked source evidence')
    return target


def sha256(path):
    h = hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda: f.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def host_of(url):
    if not isinstance(url, str):
        fail('Non-string source URL')
    p = urlsplit(url)
    if p.scheme.lower() != 'https' or not p.hostname or p.username or p.password or p.fragment:
        fail('Non-HTTPS or invalid source URL')
    host = p.hostname.lower().rstrip('.')
    try:
        ipaddress.ip_address(host)
    except ValueError:
        pass
    else:
        fail('IP-address URL is not in government research scope')
    return host


def official(host):
    return host.endswith('.gov.bd') or host == 'gov.bd'


def scope_host(host, hosts):
    return any(host == h or host == 'www.'+h or h == 'www.'+host for h in hosts)


def check_audit_events(events, request_id):
    if not isinstance(events, list):
        fail('Missing consent audit event list')
    own = [e for e in events if isinstance(e, dict) and e.get('request_id') == request_id]
    if (sum(e.get('event') == 'request_created' for e in own) != 1 or
        sum(e.get('event') == 'consent_decision' and e.get('state') == 'approved' for e in own) != 1 or
        sum(e.get('event') == 'permit_consumed' for e in own) != 1 or
        any(e.get('event') == 'consent_decision' and e.get('state') != 'approved' for e in own)):
        fail('No matching single approved and consumed consent request')
    if len(own) != len(events):
        fail('Mixed request IDs in consent audit')


def inspect(raw_root, processed_root=None):
    raw_root = Path(raw_root).resolve(strict=True)
    if raw_root.is_symlink():
        fail('Raw root cannot be symlink')
    owner = load_object(raw_root / 'stage3_output_owner.json')
    if owner != {'owner': 'unmochon_stage3_crawler', 'schema_version': 1}:
        fail('Missing Stage3-owned snapshot marker')
    receipt = load_object(raw_root / 'stage3_app_summary.json')
    if receipt.get('status') != 'staged_unverified' or receipt.get('index_writes') != 0:
        fail('Raw snapshot is not unapproved/non-indexed staged evidence')
    if receipt.get('current_policy_verified') is not False or receipt.get('source_approval') is not False:
        fail('Raw evidence cannot claim policy/content approval')
    scope = receipt.get('scope')
    if not isinstance(scope, dict) or not isinstance(scope.get('allowed_hosts'), (tuple, list)):
        fail('No allowed government scope in consent receipt')
    hosts = set()
    for name in scope['allowed_hosts']:
        if not isinstance(name, str) or not name or name.lower()!=name or not official(name) or urlsplit('//'+name).hostname!=name:
            fail('Invalid scoped government host')
        hosts.add(name)
    if not hosts or not isinstance(scope.get('question'), str) or not scope['question']:
        fail('Missing question-bound research scope')
    result = receipt.get('result')
    if not isinstance(result, dict) or not isinstance(result.get('artifacts'), list):
        fail('No artifact list in raw receipt')
    rid = receipt.get('request_id')
    if not isinstance(rid, str) or not rid:
        fail('Missing research request id')
    events_path = raw_root / 'latest_consent_audit.json'
    if not events_path.is_file() or events_path.is_symlink():
        fail('Missing consent audit')
    check_audit_events(json.loads(events_path.read_text(encoding='utf-8')), rid)
    limit = scope.get('max_http_requests')
    attempts = receipt.get('network_request_attempts')
    if (type(limit) is not int or type(attempts) is not int or
        limit < 1 or attempts < 0 or attempts > limit):
        fail('Network call limit audit failed')
    if result.get('index_updated') is not False or result.get('requires_human_import_approval') is not True:
        fail('Unexpected raw crawl index/approval state')
    checked = []
    for n, art in enumerate(result['artifacts'], 1):
        if not isinstance(art, dict):
            fail('Invalid artifact object')
        digest = art.get('raw_sha256')
        if not isinstance(digest, str) or not HEX64.fullmatch(digest):
            fail('Invalid artifact digest')
        path = in_directory(raw_root, art.get('relative_path'))
        if sha256(path) != digest or path.stat().st_size != art.get('bytes_received'):
            fail('Raw evidence sha256/length mismatch: ' + str(n))
        url = art.get('url')
        host = host_of(url)
        ref_url = art.get('government_referrer_url')
        ref_digest = art.get('government_referrer_sha256')
        if official(host):
            if not scope_host(host, hosts):
                fail('Government page outside allowed hosts')
        else:
            # The Stage3 crawler enforces storage LinkProof; this independent
            # audit additionally demands a matching fetched government referrer.
            if not ref_url or not ref_digest or not HEX64.fullmatch(ref_digest):
                fail('External object lacks government referrer proof')
            if not scope_host(host_of(ref_url), hosts):
                fail('External object referrer outside scoped government host')
        if art.get('evidence_status') != 'staged_unverified' or art.get('http_status') != 200:
            fail('Unexpected raw evidence status')
        checked.append({'artifact_number': n, 'raw_sha256': digest,
                        'relative_path': art['relative_path'], 'ministry': art.get('ministry', ''),
                        'source_role': art.get('source_role', ''), 'content_type': art.get('content_type', ''),
                        'url': url, 'government_referrer_url': ref_url or '',
                        'review_decision': '', 'reviewer_notes': '', 'original_pdf_checked': ''})
    by_digest = {a['raw_sha256']: a for a in checked}
    for art in result['artifacts']:
        host=host_of(art['url'])
        if not official(host):
            parent=by_digest.get(art.get('government_referrer_sha256'))
            if not parent or parent['url'] != art.get('government_referrer_url'):
                fail('Missing matching raw government referrer artifact')
    consent_generation = receipt.get('generation_at_consent')
    if not isinstance(consent_generation, str) or not consent_generation:
        fail('Missing pinned Stage6 generation in consent receipt')
    report = {'schema_version': 1, 'status': 'raw_verified_pending_stage4',
              'request_id': rid, 'generation_at_consent': consent_generation,
              'question': scope['question'], 'program': scope.get('program'),
              'ministry': scope.get('ministry'), 'scoped_hosts': sorted(hosts),
              'request_attempts': attempts, 'request_limit': limit,
              'artifacts_verified': len(checked), 'raw_snapshot': str(raw_root),
              'stage4': None, 'content_approved': False, 'index_import_approved': False,
              'current_policy_verified': False, 'index_writes': 0,
              'kg_contradiction_module_applied': False}
    if processed_root is not None:
        processed_root = Path(processed_root).resolve(strict=True)
        handoff = load_object(processed_root / 'app_stage4_handoff.json')
        if Path(handoff.get('raw_snapshot', '')).resolve() != raw_root:
            fail('Stage4 handoff points to a different raw crawl')
        if (handoff.get('manual_content_review_required') is not True or
            handoff.get('index_import_authorized') is not False or
            handoff.get('active_generation_unchanged') is not True):
            fail('Stage4 handoff cannot authorize index imports')
        process = handoff.get('processors')
        if not isinstance(process, dict) or not {'html', 'pdf'} <= process.keys():
            fail('Stage4 processor status incomplete')
        verified = {}
        for kind in ('html', 'pdf'):
            status = process[kind]
            if not isinstance(status, dict):
                fail('Stage4 processor status invalid')
            path = processed_root / kind / ('stage4_'+kind+'_summary.json')
            if status.get('returncode') == 0:
                summary = load_object(path)
                if (summary.get('source_request_id') != rid or
                    summary.get('source_consent_audit') != 'MATCH' or
                    summary.get('source_raw_hashes_verified') != len(checked) or
                    summary.get('index_writes') != 0 or summary.get('network_calls') != 0):
                    fail('Stage4 summary mismatch, consent check failure, or attempted write')
                verified[kind] = {'returncode': 0, 'summary_verified': True}
            else:
                verified[kind] = {'returncode': status.get('returncode'), 'summary_verified': False,
                                  'reason': 'Needs manual processing review'}
        report['stage4'] = verified
        report['status'] = ('stage4_verified_pending_manual_review' if all(x['summary_verified'] for x in verified.values())
                            else 'stage4_incomplete_manual_review_needed')
    return report, checked


def write_review_output(out, report, artifacts):
    out = Path(out).absolute()
    for ancestor in (out, *out.parents):
        if ancestor.is_symlink():
            fail('Symlinked audit output path refused')
        if (ancestor / 'active.json').exists() or (ancestor / 'chroma.sqlite3').exists():
            fail('Refusing to write inside an active/index workspace')
    raw = Path(report['raw_snapshot']).resolve()
    if out.resolve().is_relative_to(raw) or raw.is_relative_to(out.resolve()):
        fail('Review output must be separate from raw evidence')
    if out.exists():
        fail('Refusing to overwrite an existing audit output folder')
    if out.is_symlink():
        fail('Refusing symlink output')
    out.mkdir(parents=True)
    (out / 'audit.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    fields = ['artifact_number', 'raw_sha256', 'relative_path', 'ministry', 'source_role',
              'content_type', 'url', 'government_referrer_url', 'review_decision',
              'reviewer_notes', 'original_pdf_checked']
    with (out / 'stage5_UNAPPROVED_review_queue.csv').open('w', newline='', encoding='utf-8-sig') as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(artifacts)


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--raw', required=True)
    parser.add_argument('--processed')
    parser.add_argument('--active-pointer', help='Optional existing Stage6 active.json: read-only cross-check')
    parser.add_argument('--output', required=True, help='NEW separate output folder')
    args=parser.parse_args(argv)
    report, rows = inspect(args.raw, args.processed)
    if args.active_pointer:
        pointer = load_object(Path(args.active_pointer))
        if (pointer.get('schema_version') != 1 or pointer.get('generation') != report['generation_at_consent']):
            fail('Active generation is different from the generation at research consent')
        report['active_pointer_read_only_checked'] = True
    if args.processed:
        p = Path(args.processed).resolve()
        o = Path(args.output).resolve()
        if o.is_relative_to(p) or p.is_relative_to(o):
            fail('Review output must be separate from processed evidence')
    write_review_output(args.output, report, rows)
    print(json.dumps({'status': report['status'], 'artifacts': len(rows), 'output': args.output,
                      'index_writes': 0, 'content_approved': False}, ensure_ascii=False))
    return 0

if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except (AuditFailure, OSError, ValueError, json.JSONDecodeError) as exc:
        print('AUDIT BLOCKED:', exc, file=sys.stderr)
        raise SystemExit(2)
