"""Application handoff into the EXISTING Stage 6 pair/seal/pointer architecture."""
from __future__ import annotations
from contextlib import contextmanager
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time
import uuid

from .runtime import load_stage6


def compare_switch(workspace, expected, target, *, rollback=False):
    """Stage 6 durable switch with a compare-and-swap guard for concurrent jobs.

    Original Stage 6 switch() has no expected-pointer argument. Reuse its exact
    manifest gates, lock, history and atomic_write primitives, adding only CAS.
    """
    from stage6.common import atomic_write, now, workspace_lock, write
    from stage6.generations import active, read_pointer, verify_generation
    workspace = Path(workspace)
    with workspace_lock(workspace):
        before = read_pointer(workspace) if rollback else active(workspace)
        if before != expected:
            raise ValueError('Active generation changed; this job cannot overwrite another update')
        checked = verify_generation(workspace, target)
        if target == before['generation']:
            raise ValueError('Generation already active')
        if rollback:
            allowed = before.get('rollback_target') or {}
            if allowed.get('generation') != target or allowed.get('manifest_sha256') != checked['manifest_sha256']:
                raise ValueError('Rollback target differs from the preserved pair')
        elif not (checked['metadata'].get('role') == 'candidate' and
                  checked['metadata'].get('benchmark_passed') and
                  checked['metadata'].get('restart_check_passed')):
            raise ValueError('Candidate validation/regression/restart gates not passed')
        following = {'schema_version': 1, 'workspace_id': before['workspace_id'],
            'sequence': before['sequence'] + 1, 'generation': target,
            'manifest_sha256': checked['manifest_sha256'],
            'rollback_target': None if rollback else {'generation': before['generation'],
                'manifest_sha256': before['manifest_sha256']},
            'changed_at': now(), 'reason': 'agentic_requery_rollback' if rollback else 'authorized_research_pair'}
        history = workspace/'pointer_history'
        history.mkdir(exist_ok=True)
        write(history/(str(following['sequence']).zfill(4)+'_'+uuid.uuid4().hex+'.json'),
              {'status':'prepared_transition;_active_pointer_is_authoritative',
               'before':before, 'intended_after':following})
        atomic_write(workspace/'active.json', following)
        return following


class ControlledUpdater:
    def __init__(self, settings):
        self.settings = settings
        self.package = Path(settings.stage6_package or settings.root/'reference_pipelines/stage6').resolve()
        self.workspace = Path(settings.stage6_workspace or settings.root/'data/stage6_workspace').resolve()

    def _run(self, mode, spec, entry):
        env = dict(os.environ, PYTHONUTF8='1', PYTHONIOENCODING='utf-8', HF_HUB_OFFLINE='1',
                   TRANSFORMERS_OFFLINE='1', HF_HUB_DISABLE_TELEMETRY='1', ANONYMIZED_TELEMETRY='False')
        env['PYTHONPATH'] = str(self.settings.root/'src')+os.pathsep+str(self.settings.root)
        cmd = [self.settings.stage6_python or sys.executable, '-m', 'unmochon_live.agentic_worker',
               mode, '--spec', str(spec)]
        with tempfile.TemporaryFile(mode='w+b') as log:
            child = subprocess.Popen(cmd, cwd=self.settings.root, env=env, stdout=log, stderr=log)
            entry['child'] = child
            try:
                while child.poll() is None:
                    if entry['cancel'].is_set() or time.monotonic() >= entry['deadline']:
                        child.kill()
                        child.wait()
                        raise ValueError('Research cancelled or processing deadline exceeded')
                    try:
                        child.wait(timeout=.25)
                    except subprocess.TimeoutExpired:
                        pass
                if child.returncode:
                    log.seek(0, 2)
                    end = log.tell()
                    log.seek(max(0, end - 1800))
                    tail = log.read().decode('utf-8', errors='replace')
                    raise ValueError('Stage 6 '+mode+' failed: '+tail)
            finally:
                if child.poll() is None:
                    child.kill(); child.wait()
                entry['child'] = None

    def build(self, receipt_path, entry):
        from .evidence_verification import validate_receipt
        receipt = validate_receipt(receipt_path)
        load_stage6(self.package)
        from stage6.common import write, workspace_lock
        from stage6.generations import active, generation, seal
        if entry['cancel'].is_set():
            raise ValueError('Research cancelled')
        with workspace_lock(self.workspace):
            before = active(self.workspace)
            if before['generation'] != receipt['generation_at_consent']:
                raise ValueError('Knowledge base changed since research consent; no stale update applied')
            name = 'research_'+receipt['request_id'][:10]+'_'+uuid.uuid4().hex[:10]
            source = generation(self.workspace, before['generation'])
            from .evidence_verification import rows
            originals = {r['id']:r for r in rows(source/'index/selected_corpus.jsonl')}
            if all(r['id'] in originals and originals[r['id']]['text'] == r['text'] and
                   originals[r['id']]['metadata'].get('source_raw_sha256') == r['metadata'].get('source_raw_sha256')
                   for r in receipt['index_items']):
                return {'candidate':before['generation'], 'before':before, 'added_items':0,
                        'duplicate_skips':len(receipt['index_items']), 'noop':True, 'validation':{}}
            target = generation(self.workspace, name)
            target.mkdir(parents=True, exist_ok=False)
            shutil.copytree(source/'index', target/'index')
            if (source/'evidence').is_dir():
                shutil.copytree(source/'evidence', target/'evidence')
            (target/'evidence').mkdir(exist_ok=True)
            shutil.copy2(receipt_path, target/'evidence'/('research_'+receipt['request_id']+'.json'))
            from .stage4_dynamic import validate_app_snapshot
            from .evidence_verification import read
            manifest = read(Path(receipt['review_dir'])/'review_manifest.json')
            raw = validate_app_snapshot(manifest['raw_snapshot'])
            preserved = target/'evidence/research_sources'
            preserved.mkdir(exist_ok=True)
            for artifact in raw['result'].artifacts:
                suffix = '.pdf' if artifact.relative_path.endswith('.pdf') else '.html'
                destination = preserved/(artifact.raw_sha256+suffix)
                if not destination.exists():
                    shutil.copy2(raw['root']/artifact.relative_path,destination)
            spec = {'package':str(self.package), 'stage4_package':str(self.settings.stage4_package or
                    self.settings.root/'reference_pipelines/stage4'),
                'registry':str(self.settings.research_registry or self.settings.root/'config/research_sources.json'),
                'workspace':str(self.workspace), 'candidate':name, 'before':before,
                'receipt':str(receipt_path), 'model_cache':str(self.settings.stage6_model_cache or ''),
                'project':str(self.settings.root)}
            control = Path(entry['review_dir'])/'candidate_job.json'
            write(control, spec)
            self._run('build', control, entry)
            self._run('reopen', control, entry)
            result = json.loads((target/'evidence/build_validation.json').read_text(encoding='utf-8'))
            reopened = json.loads((target/'evidence/reopen_validation.json').read_text(encoding='utf-8'))
            if not result['passed'] or not reopened['passed'] or entry['cancel'].is_set():
                raise ValueError('Candidate validation/reopen/cancellation gate failed')
            # A writer process has exited; hash only closed Chroma files.
            seal(self.workspace, name, {'role':'candidate', 'validation_passed':True,
                'benchmark_passed':True, 'restart_check_passed':True,
                'item_count':result['candidate_count'], 'verification_receipt_sha256':receipt['receipt_sha256'],
                'regression':result['regression'], 'scope':'question_bound_authorized_official_evidence'})
            # Detect any unexpected source mutation before enabling activation.
            if active(self.workspace) != before:
                raise ValueError('Source generation changed during isolated build')
        return {'candidate':name, 'before':before, 'added_items':result['added_items'],
                'duplicate_skips':result['duplicate_skips'], 'validation':result}

    def activate(self, built, entry):
        if entry['cancel'].is_set() or time.monotonic() >= entry['deadline']:
            raise ValueError('Cancelled or expired before activation')
        if built.get('noop'):
            return None
        return compare_switch(self.workspace, built['before'], built['candidate'])

    def rollback(self, activated, previous):
        return compare_switch(self.workspace, activated, previous['generation'], rollback=True)
