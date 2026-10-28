"""Read-only Windows validation by default; explicit --rollback restores a pair."""
import argparse
import asyncio
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'src'),str(ROOT)]


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    mode=p.add_mutually_exclusive_group()
    mode.add_argument('--query',help='Optional real-index, offline query; never authorizes research')
    mode.add_argument('--rollback',action='store_true',help='Explicitly restore the previous complete paired generation')
    a=p.parse_args(argv)
    from unmochon_live.config import Settings
    from unmochon_live.runtime import load_stage4,load_stage6
    from unmochon_live.research_registry import make_registry
    settings=Settings.load()
    load_stage4(settings.stage4_package);load_stage6(settings.stage6_package)
    from stage6.generations import active,generation,read_pointer
    from stage6.common import read
    if a.rollback:
        from unmochon_live.controlled_update import compare_switch
        previous=read_pointer(settings.stage6_workspace)
        target=(previous.get('rollback_target') or {}).get('generation')
        if not target:raise ValueError('No previous paired generation is recorded')
        pointer=compare_switch(settings.stage6_workspace,previous,target,rollback=True)
    else:
        pointer=active(settings.stage6_workspace)
    report=read(generation(settings.stage6_workspace,pointer['generation'])/'index/build_report.json')
    registry=make_registry(settings.research_registry)
    result={'status':'READ_ONLY_GENERATION_HASH_CHECK_PASS', 'generation':pointer['generation'],
        'indexed_items':report.get('selection',{}).get('indexed_items'),
        'paired_consistency_in_sealed_report':report.get('consistency'),
        'authority_count':len(registry.entries),'model_tested':False,
        'live_research_tested':False,'index_writes':0,'network_calls':0}
    if a.rollback:
        result.update(status='EXPLICIT_PAIRED_ROLLBACK_COMPLETE',pointer_writes=1)
    if a.query:
        from unmochon_live.orchestrator import Orchestrator
        from unmochon_live.schemas import Query
        response=asyncio.run(Orchestrator(settings).ask(Query(question=a.query)))
        result['query']=response.model_dump(mode='json')
        result['model_tested']=bool(response.generation)
        if not response.generation:
            result['status']='QUERY_FAILED_CLOSED'
    print(json.dumps(result,ensure_ascii=False,indent=2))
    return 0 if result['status']!='QUERY_FAILED_CLOSED' else 2


if __name__=='__main__':
    try: raise SystemExit(main())
    except Exception as exc:
        print('BLOCKED: '+str(exc),file=sys.stderr)
        raise SystemExit(2)
