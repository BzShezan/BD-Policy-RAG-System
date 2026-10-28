"""Run BLINDED benchmark queries on one verified Chroma/BM25 pair, offline.

Single model load in the child process. Parent pins/verifies generation and copies
both indexes to a disposable folder, then waits for child exit before cleanup.
Never writes to Stage 1 baseline or accepted Stage 6 generations.
"""
import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile


def path_is_under(path, parent):
    p=Path(path).resolve();par=Path(parent).resolve()
    return p==par or par in p.parents


def read_rows(path):
    return [json.loads(x) for x in Path(path).read_text(encoding='utf-8-sig').splitlines() if x.strip()]


def child(a, package, temporary):
    os.environ['HF_HUB_OFFLINE']='1'
    os.environ['TRANSFORMERS_OFFLINE']='1'
    os.environ['HF_DATASETS_OFFLINE']='1'
    from stage6.common import offline,read,rows
    from stage6.legacy import install
    offline();install()
    from live_adapter import load_original
    from run_stage2_live import resolve_model,evaluate_fresh,dependency_versions
    from stage2.permissions import PermissionController
    from stage6.legacy import evidence_adapter
    from stage6.versions import request_scope,search_approved,source_versions
    from stage6.approved import load_approved
    dependency_versions()
    plan=read(Path(a.workspace)/'workspace.json')
    model=resolve_model(plan['model_path'],a.model_cache or plan['model_cache'])
    selected=rows(temporary/'index'/'selected_corpus.jsonl')
    by_id={r['id']:r for r in selected}
    live,retriever=load_original(temporary/'index',model,package/'compat')
    proposals,groups,receipt=load_approved()
    predictions=[]
    for q in read_rows(a.queries)[:a.limit or None]:
        question=q['question'];raw=live.collect(q['query_id'],question)
        if raw.get('error'):raise RuntimeError('Original retrieval reported failure: '+q['query_id'])
        flow=evaluate_fresh(raw,evidence_adapter(selected),PermissionController())
        scoped=request_scope(question)
        if scoped['program']=='vgf':
            found=search_approved(retriever,question,proposals,top_k=10)
            ids=[r['id'] for r in found]
            # Semantic review is separate; source_versions does NOT select a winner.
            mapping={p['proposal_id']:p['proposal_id'] for p in proposals}
            # Actions from frozen wrapper depend on approved editions, not labels.
            direct_dates={p['printed_order_date'] for p in proposals}
            action='REQUEST_RESEARCH_PERMISSION' if scoped['current_requested'] or (
                scoped['dates'] and not set(scoped['dates']) & direct_dates) else (
                'SHOW_SOURCE_VERSIONS' if ids else 'REQUEST_RESEARCH_PERMISSION')
            mode='approved_date_filtered_hybrid'
        else:
            ranked=retriever.search(raw['retrieval_question'],top_k=100,ministry=raw['ministry_filter'])
            ids=[r['id'] for r in ranked[:10]]
            action=flow['final']['action']
            mode='original_hybrid_rrf'
        dates=sorted({by_id[cid]['metadata'].get('date_value') for cid in ids
                      if cid in by_id and by_id[cid]['metadata'].get('date_status') in ('human_verified','source_verified')
                      and by_id[cid]['metadata'].get('date_value')})
        predictions.append({'query_id':q['query_id'],'ranked_ids':ids,
                            'action':action,'ministry_pred':raw.get('ministry_filter'),
                            'matched_source_dates':dates,'retrieval_mode':mode,
                            'generation':a.pinned_generation})
    a.output.parent.mkdir(parents=True,exist_ok=True)
    with a.output.open('x',encoding='utf-8') as f:
        for r in predictions:f.write(json.dumps(r,ensure_ascii=False)+'\n')
    print('Completed offline blinded retrieval cases:',len(predictions))


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--stage6-package',type=Path,required=True)
    p.add_argument('--workspace',type=Path,required=True)
    p.add_argument('--queries',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    p.add_argument('--model-cache',type=Path)
    p.add_argument('--limit',type=int,default=0)
    p.add_argument('--child',action='store_true',help=argparse.SUPPRESS)
    p.add_argument('--temp-root',type=Path,help=argparse.SUPPRESS)
    p.add_argument('--pinned-generation',help=argparse.SUPPRESS)
    a=p.parse_args()
    a.stage6_package=a.stage6_package.resolve();a.workspace=a.workspace.resolve()
    if not a.queries.is_file() or a.limit<0:raise ValueError('Missing queries or invalid limit')
    if a.output.exists():raise ValueError('Output already exists: refuse overwrite')
    if any(path_is_under(a.output,root) for root in (a.stage6_package,a.workspace)):
        raise ValueError('Prediction output must be outside sealed package and workspace')
    sys.path.insert(0,str(a.stage6_package))
    if a.child:
        return child(a,a.stage6_package,a.temp_root)
    from stage6.common import offline,read,verify_package
    from stage6.generations import active,generation
    offline();verify_package()
    pointer=active(a.workspace)
    a.pinned_generation=pointer['generation']
    with tempfile.TemporaryDirectory(prefix='unmochon_benchmark_') as d:
        temp=Path(d)
        shutil.copytree(generation(a.workspace,a.pinned_generation)/'index',temp/'index')
        cmd=[sys.executable,str(Path(__file__).resolve()),'--stage6-package',str(a.stage6_package),
             '--workspace',str(a.workspace),'--queries',str(a.queries),'--output',str(a.output),
             '--child','--temp-root',str(temp),'--pinned-generation',a.pinned_generation]
        if a.model_cache:cmd.extend(['--model-cache',str(a.model_cache)])
        if a.limit:cmd.extend(['--limit',str(a.limit)])
        rc=subprocess.run(cmd,check=False,cwd=a.stage6_package).returncode
        if rc:raise RuntimeError('Blinded retrieval child failed; no benchmark claim')
    # Detect switch or corrupt generation after child; no results are accepted.
    latest=active(a.workspace)
    if latest['generation']!=a.pinned_generation or latest['manifest_sha256']!=pointer['manifest_sha256']:
        a.output.unlink(missing_ok=True)
        raise RuntimeError('Active generation changed during benchmark; predictions discarded')
    print('Pinned active generation unchanged:',a.pinned_generation)

if __name__=='__main__':
    try:main()
    except Exception as e:
        print('Benchmark stopped:',type(e).__name__,str(e),file=sys.stderr)
        raise SystemExit(2)
