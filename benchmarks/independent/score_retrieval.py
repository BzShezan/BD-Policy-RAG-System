"""Score a frozen generation vs independently reviewed evidence IDs.

Prediction JSONL: {query_id,ranked_ids:[...],action,ministry_pred,matched_source_dates:[...]}
No model tuning, label generation, corpus writes, or network access.
"""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
from freeze_reviewed_gold import load,validate,digest


def metrics(gold,predictions):
    n=0;hit3=complete3=complete10=mrr=misrouted=false_oos=unnecessary=temporal_ok=temporal_n=0
    for row in gold:
        if row['case_type'] != 'answerable':continue
        n+=1;p=predictions[row['query_id']]
        ids=p['ranked_ids']; relevant=set(row['gold_evidence_ids'])
        hit3 += bool(set(ids[:3]) & relevant)
        def complete(k):
            return all(set(g) & set(ids[:k]) for g in row['required_evidence_groups'])
        complete3+=complete(3);complete10+=complete(10)
        first=next((i for i,x in enumerate(ids,1) if x in relevant),None)
        if first:mrr+=1/first
        misrouted+=bool(p.get('ministry_pred') and p['ministry_pred']!=row['ministry'])
        false_oos+=p.get('action')=='DECLINE_OUT_OF_DOMAIN'
        unnecessary+=p.get('action')=='REQUEST_RESEARCH_PERMISSION'
        if row.get('requested_date'):
            temporal_n+=1
            temporal_ok+=row['requested_date'] in p.get('matched_source_dates',[])
    return {'answerable_n':n,'Hit_at_3':hit3/n if n else None,
            'Complete_evidence_at_3':complete3/n if n else None,
            'Complete_evidence_at_10':complete10/n if n else None,
            'MRR':mrr/n if n else None,
            'false_out_of_domain_rate':false_oos/n if n else None,
            'unnecessary_permission_rate':unnecessary/n if n else None,
            'ministry_mismatch_rate':misrouted/n if n else None,
            'requested_date_match_rate':temporal_ok/temporal_n if temporal_n else None,
            'requested_date_cases':temporal_n}


def main():
    p=argparse.ArgumentParser();p.add_argument('--retrieval-gold',type=Path,required=True)
    p.add_argument('--ocr-gold',type=Path,required=True)
    p.add_argument('--freeze',type=Path,required=True)
    p.add_argument('--predictions',type=Path,required=True)
    p.add_argument('--split',choices=['dev','heldout'],required=True)
    p.add_argument('--output',type=Path,required=True)
    a=p.parse_args()
    if a.output.exists():raise ValueError('Choose a NEW result filename: no overwrite')
    frozen=json.loads(a.freeze.read_text(encoding='utf-8'))
    if (digest(a.retrieval_gold)!=frozen['retrieval_gold_sha256'] or
          digest(a.ocr_gold)!=frozen['ocr_gold_sha256']):
        raise ValueError('Gold differs from prior frozen review')
    all_gold=load(a.retrieval_gold);validate(all_gold,load(a.ocr_gold))
    subset=[g for g in all_gold if g['split']==a.split]
    predicts=load(a.predictions)
    by_id={r['query_id']:r for r in predicts}
    if len(by_id)!=len(predicts) or set(by_id)!={g['query_id'] for g in subset}:
        raise ValueError('Predictions must contain each selected split query exactly once')
    full=metrics(subset,by_id)
    per_ministry={m:metrics([r for r in subset if r['ministry']==m],by_id)
                  for m in ['Social Welfare','Agriculture','Disaster Management']}
    report={'benchmark':'independent_retrieval','split':a.split,'gold_sha256':frozen['retrieval_gold_sha256'],
            'query_count':len(subset),'case_counts':dict(Counter(g['case_type'] for g in subset)),
            'answerable':full,'by_ministry':per_ministry,
            'out_of_domain_false_positive_rate':sum(by_id[r['query_id']]['action']!='DECLINE_OUT_OF_DOMAIN' for r in subset if r['case_type']=='unrelated')/max(1,sum(r['case_type']=='unrelated' for r in subset)),
            'verified_missing_requested_research_rate':sum(by_id[r['query_id']]['action']=='REQUEST_RESEARCH_PERMISSION' for r in subset if r['case_type']=='verified_missing')/max(1,sum(r['case_type']=='verified_missing' for r in subset)),
            'cannot_claim':'No generated answer quality, full corpus absence or causal improvement measured.'}
    a.output.parent.mkdir(parents=True,exist_ok=True)
    a.output.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print('Scored',len(subset),a.split,'cases. Output:',a.output)

if __name__=='__main__':main()
