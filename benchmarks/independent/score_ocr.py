"""Full-page OCR evaluator only. Never relabel Capstone B or nine selected ROIs."""
import argparse
from collections import defaultdict
import json
from pathlib import Path
import unicodedata
from freeze_reviewed_gold import load,validate,digest


def distance(a,b):
    # O(min(len(a),len(b))) memory; Unicode code points after NFC normalization.
    if len(a)<len(b): a,b=b,a
    old=list(range(len(b)+1))
    for i,c in enumerate(a,1):
        cur=[i]
        for j,d in enumerate(b,1):cur.append(min(cur[-1]+1,old[j]+1,old[j-1]+(c!=d)))
        old=cur
    return old[-1]


def nfc(v):return unicodedata.normalize('NFC',v.replace('\r\n','\n')).strip()


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--retrieval-gold',type=Path,required=True)
    p.add_argument('--ocr-gold',type=Path,required=True)
    p.add_argument('--freeze',type=Path,required=True)
    p.add_argument('--split',choices=['dev','heldout'],required=True)
    p.add_argument('--output',type=Path,required=True)
    a=p.parse_args()
    if a.output.exists():raise ValueError('Refuse to overwrite an OCR score')
    frozen=json.loads(a.freeze.read_text(encoding='utf-8'))
    if (digest(a.retrieval_gold)!=frozen['retrieval_gold_sha256'] or
            digest(a.ocr_gold)!=frozen['ocr_gold_sha256']):raise ValueError('Frozen gold changed')
    data=load(a.ocr_gold);validate(load(a.retrieval_gold),data)
    groups=defaultdict(lambda:{'pages':0,'char_edits':0,'ref_chars':0,'word_edits':0,'ref_words':0,
                                'structured_fields_correct':0,'structured_fields_total':0,
                                'table_cells_correct':0,'table_cells_total':0})
    for item in data:
        if item['split']!=a.split:continue
        for name in ['raw_engine_text_path','reference_text_path']:
            if not Path(item[name]).is_file():raise ValueError('OCR input missing: '+item['sample_id'])
        output=nfc(Path(item['raw_engine_text_path']).read_text(encoding='utf-8'))
        gold=nfc(Path(item['reference_text_path']).read_text(encoding='utf-8'))
        for group in [groups['ALL'],groups[item['ministry']]]:
            group['pages']+=1;group['char_edits']+=distance(gold,output)
            group['ref_chars']+=len(gold);group['word_edits']+=distance(gold.split(),output.split())
            group['ref_words']+=len(gold.split())
            for field in item.get('numbers_dates_gold',[]):
                group['structured_fields_total']+=1
                group['structured_fields_correct']+=nfc(field['reference'])==nfc(field['engine'])
            for cell in item.get('table_cells_gold',[]):
                group['table_cells_total']+=1
                group['table_cells_correct']+=nfc(cell['reference'])==nfc(cell['engine'])
    report={'benchmark':'independent_full_page_OCR','split':a.split,
            'normalization':'Unicode NFC and CRLF->LF, strip outer whitespace only',
            'tokenization':'Unicode whitespace split; not morphological Bengali WER',
            'scope':'Only new independently reviewed FULL pages; Capstone B results unchanged',
            'metrics':{key:{**data,
                            'CER':data['char_edits']/data['ref_chars'] if data['ref_chars'] else None,
                            'WER':data['word_edits']/data['ref_words'] if data['ref_words'] else None,
                            'numeric_date_exact_match':data['structured_fields_correct']/data['structured_fields_total'] if data['structured_fields_total'] else None,
                            'table_cell_exact_match':data['table_cells_correct']/data['table_cells_total'] if data['table_cells_total'] else None}
                       for key,data in groups.items()}}
    a.output.parent.mkdir(parents=True,exist_ok=True)
    a.output.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print('OCR pages scored:',groups['ALL']['pages'],'| output',a.output)

if __name__=='__main__':main()
