"""Only questions/IDs; NEVER send gold labels to the inference runner."""
import argparse
from pathlib import Path
import json
from freeze_reviewed_gold import load

def main():
    p=argparse.ArgumentParser();p.add_argument('--reviewed',type=Path,required=True)
    p.add_argument('--split',choices=['dev','heldout'],required=True)
    p.add_argument('--output',type=Path,required=True)
    a=p.parse_args()
    if a.output.exists():raise ValueError('Choose a fresh output filename')
    rows=load(a.reviewed)
    selected=[{'query_id':r['query_id'],'question':r['question'],'split':r['split']}
              for r in rows if r['split']==a.split]
    if not selected or any(len(r['question'].strip())<2 for r in selected):raise ValueError('Questions are not ready')
    if len({r['query_id'] for r in selected})!=len(selected):raise ValueError('Duplicate IDs')
    a.output.parent.mkdir(parents=True,exist_ok=True)
    with a.output.open('x',encoding='utf-8') as f:
        for row in selected:f.write(json.dumps(row,ensure_ascii=False)+'\n')
    print('Blinded queries written:',len(selected),'| no answers, evidence IDs or gold labels included')
if __name__=='__main__':main()
