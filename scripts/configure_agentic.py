"""One-time, backup-safe runtime wiring. Default: read-only plan; --apply saves.

Keeps the existing authoritative Stage 6 workspace and local model cache. Copies
only missing reviewed Stage 2 JSON metadata, after checking original hashes.
Never opens Chroma, writes active.json, rebuilds a baseline or downloads models.
"""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import shutil
import sys
import uuid

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT/'src'), str(ROOT)]
METADATA = ('policy_catalog.json','approved_ocr_patches.json',
            'p01_p02_approval_receipt.json','numeric_confirmation_receipt.json')


def parse_env(path):
    result = {}
    if path.exists():
        for line in path.read_text(encoding='utf-8-sig').splitlines():
            if line.strip() and not line.lstrip().startswith('#') and '=' in line:
                k,v = line.split('=',1)
                result[k.strip()] = v.strip().strip('"\'')
    return result


def resolve(value,root):
    path = Path(value).expanduser()
    return (path if path.is_absolute() else root/path).resolve()


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def plan(root,workspace=None,stage6_assets=None,model_cache=None):
    root = Path(root).resolve()
    from unmochon_live.runtime import load_stage6,load_stage4
    load_stage6(root/'reference_pipelines/stage6')
    load_stage4(root/'reference_pipelines/stage4')
    env = parse_env(root/'.env')
    old_package = resolve(stage6_assets or env.get('STAGE6_PACKAGE','reference_pipelines/stage6'),root)
    workspace = resolve(workspace or env.get('STAGE6_WORKSPACE','data/stage6_workspace'),root)
    from stage6.generations import active,generation
    from stage6.common import read
    pointer = active(workspace)  # Read-only sealed generation hash verification.
    generation_root = generation(workspace,pointer['generation'])
    report = read(generation_root/'index/build_report.json')
    current = read(workspace/'workspace.json')
    model_cache = model_cache or env.get('STAGE6_MODEL_CACHE') or current.get('model_cache','model_cache')
    data = root/'data/stage2_evidence'
    checksums = read(root/'reference_pipelines/stage6/package_checksums.json')
    copies = []
    for name in METADATA:
        target = data/name
        source = old_package/'compat/data'/name
        # Also accept a previously configured runtime asset directory.
        if env.get('STAGE2_EVIDENCE_DATA'):
            candidate = resolve(env['STAGE2_EVIDENCE_DATA'],root)/name
            if candidate.is_file(): source = candidate
        expected = checksums['compat/data/'+name]
        if target.exists():
            if sha(target) != expected:
                raise ValueError('Existing reviewed metadata differs from its frozen hash: '+name)
        elif source.is_file() and sha(source) == expected:
            copies.append((source,target))
        else:
            raise ValueError('Missing reviewed Stage 2 metadata '+name+
                '. Supply --stage6-assets with the ORIGINAL complete Stage 6 package; no index/model upload is needed.')
    values = {'APP_ENV':'local','RAG_BACKEND':'stage6','ENABLE_WEB_SEARCH':'false',
        'STAGE4_PACKAGE':'reference_pipelines/stage4','STAGE6_PACKAGE':'reference_pipelines/stage6',
        'STAGE6_WORKSPACE':workspace.as_posix(), 'STAGE6_MODEL_CACHE':resolve(model_cache,root).as_posix(),
        'STAGE2_EVIDENCE_DATA':'data/stage2_evidence','RESEARCH_SOURCE_REGISTRY':'config/research_sources.json',
        'RESEARCH_OUTPUT_ROOT':'data/research_runs'}
    old4 = resolve(env.get('STAGE4_PACKAGE','reference_pipelines/stage4'),root)
    if 'STAGE4_OCR_MODELS' not in env and (old4/'models/model_manifest.json').is_file():
        values['STAGE4_OCR_MODELS'] = (old4/'models').as_posix()
    if env.get('STAGE4_TESSERACT'): values['STAGE4_TESSERACT'] = env['STAGE4_TESSERACT']
    return values,copies,{'active_generation':pointer['generation'],
        'item_count':report.get('selection',{}).get('indexed_items'),
        'workspace_unchanged':True,'model_tested':False,'live_research_tested':False,'index_writes':0}


def configure(root,workspace=None,stage6_assets=None,model_cache=None,apply=False):
    root = Path(root).resolve()
    values,copies,report = plan(root,workspace,stage6_assets,model_cache)
    report.update(status='DRY_RUN_PASS',reviewed_metadata_to_copy=[p.name for _,p in copies],
                  environment_keys_updated=list(values))
    if not apply: return report
    path = root/'.env'
    old = path.read_bytes() if path.exists() else None
    backup = root/'data/setup_backups'/('agentic_'+datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')+'_'+uuid.uuid4().hex[:6])
    backup.mkdir(parents=True,exist_ok=False)
    if old is not None: (backup/'env.before').write_bytes(old)
    lines = old.decode('utf-8-sig').splitlines() if old is not None else []
    remaining = dict(values)
    new = []
    for line in lines:
        key = line.split('=',1)[0].strip() if '=' in line and not line.lstrip().startswith('#') else None
        if key in values:
            if key in remaining: new.append(key+'='+remaining.pop(key))
        else: new.append(line)
    new += [k+'='+v for k,v in remaining.items()]
    copied = []
    temp = root/('.env.'+uuid.uuid4().hex+'.tmp')
    try:
        for source,target in copies:
            target.parent.mkdir(parents=True,exist_ok=True)
            with target.open('xb') as stream: stream.write(source.read_bytes())
            copied.append(target)
        temp.write_text('\n'.join(new)+'\n',encoding='utf-8')
        os.replace(temp,path)
    except Exception:
        for file in copied: file.unlink(missing_ok=True)
        if old is not None: path.write_bytes(old)
        raise
    finally: temp.unlink(missing_ok=True)
    report.update(status='CONFIGURED_NOT_LIVE_TESTED',backup=str(backup))
    (backup/'setup_report.json').write_text(json.dumps(report,indent=2)+'\n')
    return report


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--root',type=Path,default=ROOT)
    p.add_argument('--workspace')
    p.add_argument('--stage6-assets')
    p.add_argument('--model-cache')
    p.add_argument('--apply',action='store_true')
    args=p.parse_args(argv)
    try:
        print(json.dumps(configure(args.root,args.workspace,args.stage6_assets,args.model_cache,args.apply),indent=2))
        return 0
    except (ValueError,OSError,KeyError) as exc:
        print('BLOCKED: '+str(exc),file=sys.stderr)
        return 2


if __name__=='__main__': raise SystemExit(main())
