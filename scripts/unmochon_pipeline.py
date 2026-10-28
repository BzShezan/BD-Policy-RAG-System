"""Unified local entrypoint for the already implemented Unmochon Stage 1–6.

This adapter does NOT rebuild or write ChromaDB/BM25; it does not grant
research permission or activate any index. All paths are resolved read-only.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
from typing import Any

STAGES = {
    "stage1": ("src/unmochon_live/rag.py", "reference_pipelines/stage1_data_prep/prepare_data.py"),
    "stage2": ("src/unmochon_live/stage6_bridge.py", "src/unmochon_live/research_flow.py"),
    "stage3": ("src/unmochon_live/research_flow.py", "reference_pipelines/stage4/stage3/consent.py"),
    "stage4": ("src/unmochon_live/stage4_dynamic.py", "reference_pipelines/stage4/stage4/pdf_processing.py"),
    "stage5": ("scripts/stage5_prepare_review.py", "scripts/stage5_finalize_review.py"),
    "stage6": ("src/unmochon_live/stage6_bridge.py", "reference_pipelines/stage6/stage6/generations.py"),
}
TESTS = (
    "tests/test_agentic_integration.py", "tests/test_agentic_installer.py",
    "tests/test_stage6_bridge.py", "tests/test_current_merge_contract.py",
    "tests/test_research_workflow.py", "tests/test_research_http_pdf.py",
    "tests/test_stage4_dynamic_adapter.py", "tests/test_stage5_dynamic_review.py",
    "tests/test_stage6_import_preflight.py", "tests/test_stage6_source_applicability.py",
)


def read_known_env(path: Path) -> dict[str, str]:
    """Parse ONLY path and safe feature flags, without printing secrets."""
    known = {"APP_ENV", "RAG_BACKEND", "ENABLE_WEB_SEARCH", "STAGE4_PACKAGE",
             "STAGE6_PACKAGE", "STAGE6_WORKSPACE", "STAGE6_MODEL_CACHE"}
    values: dict[str, str] = {}
    if path.is_file():
        for raw in path.read_text(encoding="utf-8-sig").splitlines():
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            key = key.removeprefix("export ").strip()
            if key in known:
                values[key] = value.strip().strip("'\"")
    for key in known:
        if key in os.environ:
            values[key] = os.environ[key]
    return values


def resolved_path(value: str, project: Path) -> Path | None:
    if not value:
        return None
    p = Path(os.path.expandvars(value)).expanduser()
    return (p if p.is_absolute() else project / p).resolve()


def inventory(root: Path) -> dict[str, Any]:
    root = root.resolve()
    conf = read_known_env(root / '.env')
    stages = {key: {"code_present": all((root / p).is_file() for p in paths),
                    "files": {p: (root / p).is_file() for p in paths}}
              for key, paths in STAGES.items()}
    pack4 = resolved_path(conf.get('STAGE4_PACKAGE', ''), root)
    pack6 = resolved_path(conf.get('STAGE6_PACKAGE', ''), root)
    workspace = resolved_path(conf.get('STAGE6_WORKSPACE', ''), root)
    cache = resolved_path(conf.get('STAGE6_MODEL_CACHE', ''), root)
    ptr = workspace / 'active.json' if workspace else None
    pointer_generation = None
    pointer_error = None
    if ptr and ptr.is_file():
        try:
            data = json.loads(ptr.read_text(encoding='utf8'))
            pointer_generation = data.get('generation')
        except (OSError, ValueError) as ex:
            pointer_error = type(ex).__name__
    return {
        'repo': str(root), 'status': 'CODE_CHECK_ONLY_NOT_END_TO_END_VALIDATION',
        'stages': stages,
        'local_mode': conf.get('APP_ENV') == 'local',
        'stage6_selected': conf.get('RAG_BACKEND') == 'stage6',
        'automatic_web_fallback_disabled': conf.get('ENABLE_WEB_SEARCH','').lower() == 'false',
        'stage4_entrypoint_present': bool(pack4 and (pack4 / 'run_stage3_crawl.py').is_file()),
        'stage6_entrypoint_present': bool(pack6 and (pack6 / 'run_stage6_query.py').is_file()),
        'active_pointer_present': bool(ptr and ptr.is_file()),
        'active_pointer_generation_unverified': pointer_generation,
        'active_pointer_parse_error': pointer_error,
        'model_cache_path_exists': bool(cache and cache.is_dir()),
        'kg': 'NO_OP_RESERVED',
        'index_writes': 0,
        'network_calls': 0,
    }


def safe_runtime(root: Path) -> None:
    r = inventory(root)
    checks = ('local_mode','stage6_selected','automatic_web_fallback_disabled',
              'stage6_entrypoint_present','active_pointer_present')
    if not all(r[x] for x in checks):
        raise RuntimeError('App execution blocked: configure local Stage6 and disable automatic web fallback in .env; run doctor first')


def launch(root: Path, argv: list[str]) -> int:
    env = dict(os.environ)
    src = str(root / 'src')
    env['PYTHONPATH'] = src + (os.pathsep + env['PYTHONPATH'] if env.get('PYTHONPATH') else '')
    env.update(PYTHONUTF8='1', PYTHONIOENCODING='utf-8',
               HF_HUB_OFFLINE='1', TRANSFORMERS_OFFLINE='1',
               HF_HUB_DISABLE_TELEMETRY='1')
    # Subprocess is used for correct Windows terminal encoding and exit status.
    return subprocess.call([sys.executable, *argv], cwd=root, env=env)


def build_parser():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--root', type=Path, default=Path(__file__).resolve().parent.parent)
    sub=p.add_subparsers(dest='command', required=True)
    sub.add_parser('doctor', help='Read-only Stage 1–6 code and runtime path inventory')
    sub.add_parser('test', help='Run existing offline integration/regression tests')
    sub.add_parser('serve', help='Run existing local Unmochon web app; NO automatic crawl')
    ask=sub.add_parser('ask',help='Run existing verified Stage6 query via Unmochon app')
    ask.add_argument('question')
    prep=sub.add_parser('review-prepare',help='Call existing Stage5 reviewer generator')
    for arg in ('stage4','snapshot','package','output'):
        prep.add_argument('--'+arg,required=True)
    finalize=sub.add_parser('review-finalize',help='Record decisions with existing Stage5 finalizer; NO import')
    for arg in ('review-dir','decisions','package'):
        finalize.add_argument('--'+arg,required=True)
    return p


def main(argv=None):
    p=build_parser(); a=p.parse_args(argv)
    root=a.root.resolve()
    if not (root/'src/unmochon_live/cli.py').is_file():
        p.error('Missing Unmochon unified application at --root; no changes made')
    if a.command=='doctor':
        report=inventory(root)
        print(json.dumps(report,indent=2,ensure_ascii=False))
        return 0
    if a.command=='test':
        tests=[str(root/t) for t in TESTS if (root/t).is_file()]
        if not tests:
            p.error('No existing regression tests found')
        return launch(root,['-m','pytest','-q',*tests])
    if a.command in ('ask','serve'):
        try: safe_runtime(root)
        except RuntimeError as ex: p.error(str(ex))
        cmd=['-m','unmochon_live',a.command]
        if a.command=='ask': cmd += [a.question,'--json']
        return launch(root,cmd)
    if a.command=='review-prepare':
        script=root/'scripts/stage5_prepare_review.py'
        if not script.is_file(): p.error('Stage5 review tool missing')
        cmd=[str(script),'--stage4',a.stage4,'--snapshot',a.snapshot,
             '--package',a.package,'--output',a.output]
        return launch(root,cmd)
    if a.command=='review-finalize':
        script=root/'scripts/stage5_finalize_review.py'
        if not script.is_file(): p.error('Stage5 finalizer missing')
        cmd=[str(script),'--review-dir',a.review_dir,'--decisions',a.decisions,
             '--package',a.package]
        return launch(root,cmd)
    return 2

if __name__=='__main__':
    raise SystemExit(main())
