"""Extensible, exact-host registry using Stage 3's immutable plan and scope rules."""
from __future__ import annotations
import json
import os
from pathlib import Path
import re
import unicodedata

DEFAULT_REGISTRY = Path(__file__).resolve().parents[2] / 'config/research_sources.json'


def registry_path():
    return Path(os.getenv('RESEARCH_SOURCE_REGISTRY', DEFAULT_REGISTRY)).resolve()


def make_registry(path=None):
    from stage3.scope import Registry, canonical_url, sha_bytes
    from stage2.permissions import valid_gov_host

    class ApplicationRegistry(Registry):
        def __init__(self, source):
            raw = Path(source).read_bytes()
            obj = json.loads(raw)
            entries = obj.get('ministries', [])
            if obj.get('schema_version') != 1 or not 1 <= len(entries) <= 40:
                raise ValueError('Invalid application government registry')
            self.sha256 = sha_bytes(raw)
            self.entries = {r['name']: r for r in entries}
            if len(self.entries) != len(entries):
                raise ValueError('Duplicate government authority')
            for row in entries:
                hosts = row.get('government_hosts', [])
                if (not hosts or len(hosts) > 12 or 'gov.bd' in hosts or
                        not all(valid_gov_host(h) for h in hosts) or not row.get('verification')):
                    raise ValueError('Exact verified government hosts required')
                for proof in row['verification']:
                    canonical_url(proof['url'])
                    if not proof.get('checked_at') or not proof.get('basis'):
                        raise ValueError('Registry authority evidence required')
                self.make_plan('Registry scope validation', 'scope_check', row['name'], 'config validation')

    return ApplicationRegistry(path or registry_path())


def registry_for_scope(scope, path=None):
    current = make_registry(path)
    if scope.get('registry_sha256') == current.sha256:
        return current
    # Older consented snapshots keep their ORIGINAL registry fingerprint.
    from stage3.scope import Registry
    legacy = Registry()
    if scope.get('registry_sha256') != legacy.sha256:
        raise ValueError('Registry changed since consent; a fresh scoped request is required')
    return legacy


def match_scope(question, path=None):
    obj = json.loads(Path(path or registry_path()).read_text(encoding='utf-8'))
    q = unicodedata.normalize('NFC', question).casefold()
    matches = []
    for row in obj['ministries']:
        for program in row.get('programs', []):
            for alias in program['aliases']:
                a = unicodedata.normalize('NFC', alias).casefold()
                pattern = r'(?<![a-z0-9])' + re.escape(a) + r'(?![a-z0-9])' if a.isascii() else re.escape(a)
                if re.search(pattern, q):
                    matches.append((program['id'], row['name']))
                    break
    return list(dict.fromkeys(matches))

