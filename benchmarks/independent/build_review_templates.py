"""Create EMPTY independent gold worksheets. No corpus/evaluation/network access."""
import argparse
import json
from pathlib import Path

MINISTRIES = [('SW','Social Welfare'),('AG','Agriculture'),('DM','Disaster Management')]


def emit(path,records):
    with path.open('x',encoding='utf-8') as stream:
        for row in records: stream.write(json.dumps(row,ensure_ascii=False,sort_keys=True)+'\n')


def main():
    a=argparse.ArgumentParser()
    a.add_argument('--output',required=True,type=Path)
    args=a.parse_args()
    if args.output.exists(): raise ValueError('Choose a NEW output folder; no overwrite is allowed')
    args.output.mkdir(parents=True)
    retrieval=[]
    for prefix,ministry in MINISTRIES:
        for i in range(1,61):
            retrieval.append({'query_id':f'POL_{prefix}_{i:03d}', 'split':'dev' if i<=42 else 'heldout',
                'case_type':'answerable','ministry':ministry,'question':'',
                'document_family':'','source_edition':'','gold_evidence_ids':[],
                'required_evidence_groups':[], 'requested_date':'',
                'source_reviewed':False,'reviewer_id':'','independent_review_note':''})
    for code,kind in [('NON','unrelated'),('MISS','verified_missing')]:
        for i in range(1,31):
            retrieval.append({'query_id':f'{code}_{i:03d}', 'split':'dev' if i<=21 else 'heldout',
                'case_type':kind,'ministry':'unrelated' if code=='NON' else '',
                'question':'','document_family':'','source_edition':'',
                'gold_evidence_ids':[], 'required_evidence_groups':[],
                'requested_date':'','source_reviewed':False,
                'reviewer_id':'','independent_review_note':'',
                'absence_scope_verified':False if code=='MISS' else None})
    pages=[]
    for prefix,ministry in MINISTRIES:
        for i in range(1,16):
            pages.append({'sample_id':f'OCR_{prefix}_{i:03d}',
                'split':'dev' if i<=10 else 'heldout',
                'ministry':ministry,'document_family':'','source_pdf_sha256':'',
                'page_number':None,'page_type':'','scan_quality':'','digital_or_scanned':'',
                'raw_engine_text_path':'','reference_text_path':'',
                'reference_reviewed':False,'reviewer_id':'',
                'numbers_dates_gold':[], 'table_cells_gold':[],
                'scope':'full_page','independent_review_note':''})
    emit(args.output/'retrieval_review_BLANK.jsonl',retrieval)
    emit(args.output/'ocr_review_BLANK.jsonl',pages)
    print('BLANK retrieval slots:',len(retrieval),'(168 development, 72 heldout)')
    print('BLANK full-page OCR slots:',len(pages),'(30 development, 15 heldout)')
    print('No ground truth was invented or scored.')

if __name__=='__main__':main()
