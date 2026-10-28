"""TEST ONLY: real Chroma/BM25 and ORIGINAL retrieval, synthetic 384-D encoder.
Never imported by application code. No models, sockets or government answers.
"""
import ast
import hashlib
import json
from pathlib import Path
import pickle
import sys
from types import SimpleNamespace

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'src'),str(ROOT)]


def encode(texts,**kwargs):
    import numpy as np
    return np.asarray([[b/127.5-1 for b in hashlib.shake_256(t.encode()).digest(384)] for t in texts],dtype=np.float32)


def original(index,model,package):
    from scripts.retrieval.search import HybridRetriever
    from unmochon_live.original_pipeline import OriginalPipeline
    from index_checks.index_common import persistent_client,COLLECTION
    from stage6.index_pair import restricted_payload
    retriever=HybridRetriever.__new__(HybridRetriever)
    retriever.collection=persistent_client(index/'data/chromedb').get_collection(COLLECTION,embedding_function=None)
    payload=restricted_payload(index/'data/bm25_index.pkl')
    retriever.bm25,retriever.bm25_ids=payload['bm25'],payload['ids']
    retriever.bm25_id_to_pos={cid:i for i,cid in enumerate(payload['ids'])}
    retriever.model=SimpleNamespace(encode=encode)
    return OriginalPipeline(retriever,translator=SimpleNamespace(to_bengali=lambda q:q)),retriever


def archived_original(index,model,package):
    from stage6.legacy import install
    install()
    vendor=Path(package)/'compat/original_components'
    sys.path[:0]=[str(vendor/'scripts/retrieval'),str(vendor/'chatbot/scripts')]
    from tokenize_bn import tokenize
    from query_expansion import expand
    from index_checks.index_common import persistent_client,COLLECTION
    from stage6.index_pair import restricted_payload
    from live_adapter import LiveRetrieval
    from benchmark.corpus import original_router
    import two_stage,intent,extractor_map
    parsed=ast.parse((vendor/'scripts/retrieval/search.py').read_text(encoding='utf-8-sig'))
    node=next(n for n in parsed.body if isinstance(n,ast.ClassDef) and n.name=='HybridRetriever')
    namespace={'config':SimpleNamespace(CANDIDATES_PER_RETRIEVER=50,RRF_K=60),'tokenize':tokenize,'expand':expand}
    exec(compile(ast.Module(body=[node],type_ignores=[]),'<unchanged-original-hybrid>', 'exec'),namespace)
    cls=namespace['HybridRetriever']; retriever=cls.__new__(cls)
    retriever.collection=persistent_client(index/'data/chromedb').get_collection(COLLECTION,embedding_function=None)
    payload=restricted_payload(index/'data/bm25_index.pkl')
    retriever.bm25,retriever.bm25_ids=payload['bm25'],payload['ids']
    retriever.bm25_id_to_pos={cid:i for i,cid in enumerate(payload['ids'])}
    retriever.model=SimpleNamespace(encode=encode)
    return LiveRetrieval(retriever,two_stage.two_stage_search,intent.detect_intents,
                         extractor_map.EXTRACTORS_FOR_INTENT,original_router(vendor)),retriever


def prepare(spec):
    from unmochon_live.agentic_worker import bootstrap
    bootstrap(spec)
    from stage6.common import write,write_rows
    from stage6.index_pair import logical_hash
    from index_checks.index_common import persistent_client,COLLECTION
    from tokenize_bn import tokenize
    from rank_bm25 import BM25Okapi
    workspace=Path(spec['workspace']);index=workspace/'generations/reviewed_c02a1b74041d/index'
    (index/'data').mkdir(parents=True)
    selected=[];catalog={}
    for cid,ministry,program,year,text in [
        ('legacy_age','Social Welfare','old_age',2013,'বয়স্ক ভাতা নীতিমালা ২০১৩: পুরুষের ক্ষেত্রে বয়স ৬৫ বছর বা তদূর্ধ্ব এবং মহিলাদের ক্ষেত্রে বয়স ৬২ বছর বা তদূর্ধ্ব। Synthetic test fixture only.'),
        ('legacy_tea','Social Welfare','tea_workers',2013,'চা শ্রমিকদের আর্থিক সহায়তা নীতিমালা ২০১৩: সর্বনিম্ন ১৮ বছর বয়স। এটি শুধুই পরীক্ষার জন্য বানানো কৃত্রিম নথির লেখা।'),
        ('legacy_agri','Agriculture','agricultural_marketing',2018,'কৃষি বিপণন নীতিমালা ২০১৮: প্রতি ৩ বছরে পর্যালোচনা করা হবে। এটি কৃত্রিম পরীক্ষার নথি, সরকারি evidence নয়।'),
        ('legacy_disaster','Disaster Management','vgf',2023,'ভিজিএফ কর্মসূচির কৃত্রিম পরীক্ষার নথি। কোনো বর্তমান বরাদ্দের উত্তর এখানে নেই। Synthetic fixture only.')]:
        selected.append({'id':cid,'text':text,'metadata':{'ministry':ministry,'doc_id':cid,'page_number':1,
            'is_table':False,'source_url':'https://msw.gov.bd/synthetic-fixture-only',
            'date_value':str(year)+'-01-01','date_precision':'year','date_status':'source_verified'}})
        catalog[cid]={'program':program,'policy_year':year,'document_kind':'policy','policy_year_basis':'synthetic_fixture','source_filename':'fixture.pdf'}
    client=persistent_client(index/'data/chromedb')
    col=client.create_collection(COLLECTION,embedding_function=None,metadata={'hnsw:space':'cosine','corpus_sha256':logical_hash(selected)})
    texts=[r['text'] for r in selected]
    col.add(ids=[r['id'] for r in selected],documents=texts,metadatas=[r['metadata'] for r in selected],embeddings=encode(texts).tolist())
    payload={'ids':[r['id'] for r in selected],'bm25':BM25Okapi([tokenize(t) for t in texts]),
        'text_sha256':[hashlib.sha256(t.encode()).hexdigest() for t in texts]}
    with (index/'data/bm25_index.pkl').open('wb') as f:pickle.dump(payload,f)
    write_rows(index/'selected_corpus.jsonl',selected)
    write(index/'build_report.json',{'model':{'name':'synthetic_fixture_not_semantic_model','revision':'test_only'},'synthetic_fixture_only':True})
    write(workspace/'workspace.json',{'workspace_id':'synthetic_fixture','model_path':'test_only','model_cache':'test_only'})
    data=Path(spec['fixture_evidence_data']);data.mkdir()
    for name,obj in [('policy_catalog.json',catalog),('approved_ocr_patches.json',{'patches':[]}),
        ('p01_p02_approval_receipt.json',{'patches':[]}),('numeric_confirmation_receipt.json',{'documents':{}})]:write(data/name,obj)


def main():
    from unmochon_live import agentic_worker as worker
    mode,specfile=sys.argv[1:]
    spec=json.loads(Path(specfile).read_text(encoding='utf-8'))
    worker.resolve_local_model=lambda _spec:None
    worker.original=original
    if mode=='prepare':return prepare(spec)
    if mode=='seal':
        worker.bootstrap(spec)
        from stage6.generations import seal,initialize
        seal(spec['workspace'],'reviewed_c02a1b74041d',{'role':'rollback_baseline','validation_passed':True})
        initialize(spec['workspace'],'reviewed_c02a1b74041d');return
    if mode=='partial-failure':
        worker.bootstrap(spec)
        from stage6.common import read,rows,write,tree
        from stage6.generations import active,generation
        from stage6.index_pair import restricted_payload,verify_pair
        from index_checks.index_common import persistent_client,COLLECTION
        import shutil
        base=generation(spec['workspace'],active(spec['workspace'])['generation'])/'index'
        target=Path(spec['workspace'])/'partial/index'
        shutil.copytree(base,target)
        selected=rows(target/'selected_corpus.jsonl')
        additions=[{'id':'partial_'+str(i),'text':'NID synthetic application clause '+str(i),
            'metadata':{'ministry':'Election Commission','doc_id':'partial','page_number':1,
                'date_value':'2026-10-19','source_raw_sha256':'a'*64,'claim_kind':'service_guidance',
                'proposal_sha256':str(i),'proposal_id':str(i),'is_table':False}}
            for i in range(40)]
        calls=[0]
        def broken_encode(texts):
            calls[0]+=1
            if calls[0]==2:raise ValueError('Injected encoder failure after a committed dense batch')
            return encode(texts)
        try:worker.build_pair(target,selected,additions,broken_encode,read(target/'build_report.json')['model'])
        except ValueError as exc:
            if 'Injected encoder' not in str(exc):raise
        else:raise AssertionError('Partial write failure was not injected')
        collection=persistent_client(target/'data/chromedb').get_collection(COLLECTION,embedding_function=None)
        payload=restricted_payload(target/'data/bm25_index.pkl')
        try:verify_pair(collection,payload,selected)
        except ValueError:pass
        else:raise AssertionError('Partial dense/sparse mismatch passed')
        assert collection.count()==len(selected)+32
        assert len(payload['ids'])==len(selected)
        assert not (target.parent/'READY.json').exists()
        write(Path(spec['workspace'])/'partial_failure_result.json',{'passed':True,'partial_dense_items':32,
            'sparse_pair_not_published':True,'active_generation':active(spec['workspace'])['generation']})
        return
    return {'build':worker.build,'reopen':worker.reopen,'query-copy':worker.query_copy}[mode](spec)

if __name__=='__main__':main()
