import hashlib, json, sys, tempfile, unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

HERE=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(HERE/'scripts'))
from stage5_prepare_review import build,canonical,digest
from stage5_finalize_review import finalize

class TestReview(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)
        self.snapshot=self.root/'raw';self.snapshot.mkdir()
        self.package=self.root/'package';self.package.mkdir()
        self.stage4=self.root/'stage4';self.stage4.mkdir()
        self.review=self.root/'review'
        self.htmlsha='a'*64;self.pdfsha='b'*64
        self.html=SimpleNamespace(raw_sha256=self.htmlsha,url='https://modmr.gov.bd/doc',
                                  relative_path='runs/'+'c'*32+'/raw/'+self.htmlsha+'.html',government_referrer_url=None)
        self.pdf=SimpleNamespace(raw_sha256=self.pdfsha,url='https://modmr.gov.bd/test.pdf',
                                 relative_path='runs/'+'c'*32+'/raw/'+self.pdfsha+'.pdf',government_referrer_url=None)
        self.valid={'root':self.snapshot.resolve(), 'hash':'h'*64,'request_id':'req1',
                    'generation':'reviewed_test','result':SimpleNamespace(artifacts=[self.html,self.pdf])}
        self.validator=Mock(return_value=self.valid)
        htmlfolder=self.stage4/'html'/'documents';htmlfolder.mkdir(parents=True)
        body='Bangla policy text example'
        self.put(htmlfolder/(self.htmlsha+'.json'),{'text':body,'text_sha256':digest(body.encode()),
          'source':{'raw_sha256':self.htmlsha,'url':self.html.url},'title':'Heading',
          'human_approval':False,'requires_human_import_approval':True,'evidence_status':'processed_unverified'})
        pages=self.stage4/'pdf'/'pages';pages.mkdir(parents=True)
        doc=self.stage4/'pdf'/'documents';doc.mkdir(parents=True)
        text='Example text from page 1'
        self.put(doc/(self.pdfsha+'.json'),{'source':{'raw_sha256':self.pdfsha,'url':self.pdf.url},
          'pages':[{'page':1,'accepted_for_staging':True}],
          'requires_human_import_approval':True,'current_policy_verified':False})
        self.put(pages/(self.pdfsha+'_p1.json'),{'text':text,'text_sha256':digest(text.encode()),
          'raw_sha256':self.pdfsha,'source_url':self.pdf.url,'page':1,'human_approval':False,
          'requires_human_import_approval':True,'evidence_status':'processed_unverified',
          'final_quality':{'accepted_for_staging':True},'route':'digital_pdf_text'})
        self.put(self.stage4/'stage4_dynamic_summary.json',{
          'request_id':'req1','generation_at_consent':'reviewed_test','source_snapshot_sha256':'h'*64,
          'source_snapshot_unchanged':True,'status':'review_required','human_content_review_required':True,
          'index_import_authorized':False,'current_policy_verified':False,'network_calls':0,'index_writes':0,
          'artifacts_verified':2,'html_artifacts_processed':1,'pdf_artifacts_processed':1,'pdf_pages':1,
          'pages_needing_extraction_review':0,'html_output':str(self.stage4/'html'),
          'pdf_output':str(self.stage4/'pdf')})
    def put(self,path,data):
        path.parent.mkdir(parents=True,exist_ok=True)
        path.write_text(json.dumps(data,ensure_ascii=False),encoding='utf-8')
    def decisions(self,all_approved=False):
        manifest=json.loads((self.review/'review_manifest.json').read_text())
        hashval=(self.review/'review_manifest.sha256').read_text().strip()
        data={'schema_version':1,'manifest_sha256':hashval,'request_id':'req1','reviewer':'QA reviewer',
          'decisions':[{'id':item['id'],'decision':'approved' if all_approved else 'pending',
          'source_checked':all_approved,'context_checked':all_approved,
          'notes':'Verified original PDF and page context.' if all_approved else ''} for item in manifest['items']]}
        path=self.root/'decisions.json';self.put(path,data)
        return path
    def test_prepare_and_pending_review_no_index(self):
        report=build(self.stage4,self.snapshot,self.package,self.review,self.validator)
        self.assertEqual(report['items'],2)
        self.assertEqual(report['pdf_page_items'],1)
        self.assertFalse((self.review/'content_review_record.json').exists())
        path=self.decisions()
        receipt=finalize(self.review,path,self.package,self.validator)
        self.assertEqual(receipt['approved_content_count'],0)
        self.assertFalse(json.loads((self.review/'content_review_record.json').read_text())['index_import_authorized'])
    def test_manual_approved_still_not_index_import(self):
        build(self.stage4,self.snapshot,self.package,self.review,self.validator)
        path=self.decisions(True)
        report=finalize(self.review,path,self.package,self.validator)
        self.assertEqual(report['approved_content_count'],2)
        with self.assertRaisesRegex(ValueError,'already exists'):
            finalize(self.review,path,self.package,self.validator)
    def test_tampered_stage4_text_blocked(self):
        path=self.stage4/'html'/'documents'/(self.htmlsha+'.json')
        obj=json.loads(path.read_text());obj['text']='altered';self.put(path,obj)
        with self.assertRaisesRegex(ValueError,'HTML evidence'):
            build(self.stage4,self.snapshot,self.package,self.review,self.validator)
    def test_tampered_post_review_input_blocked(self):
        build(self.stage4,self.snapshot,self.package,self.review,self.validator)
        path=self.decisions(True)
        source=self.stage4/'pdf'/'pages'/(self.pdfsha+'_p1.json')
        source.write_text(source.read_text()+' ',encoding='utf-8')
        with self.assertRaisesRegex(ValueError,'Stage4 file changed'):
            finalize(self.review,path,self.package,self.validator)
    def test_false_verified_or_index_writes_blocked(self):
        path=self.stage4/'stage4_dynamic_summary.json'
        obj=json.loads(path.read_text());obj['index_import_authorized']=True;self.put(path,obj)
        with self.assertRaisesRegex(ValueError,'Stage4 safety'):
            build(self.stage4,self.snapshot,self.package,self.review,self.validator)
    def test_approval_requires_source_check(self):
        build(self.stage4,self.snapshot,self.package,self.review,self.validator)
        path=self.decisions(True)
        data=json.loads(path.read_text());data['decisions'][0]['source_checked']=False;self.put(path,data)
        with self.assertRaisesRegex(ValueError,'Cannot approve'):
            finalize(self.review,path,self.package,self.validator)
    def test_manifest_tamper_refused(self):
        build(self.stage4,self.snapshot,self.package,self.review,self.validator)
        path=self.decisions()
        manifest=self.review/'review_manifest.json'
        m=json.loads(manifest.read_text());m['generation_at_consent']='swapped';self.put(manifest,m)
        with self.assertRaisesRegex(ValueError,'manifest hash'):
            finalize(self.review,path,self.package,self.validator)
    def test_wrong_batch_decision_refused(self):
        build(self.stage4,self.snapshot,self.package,self.review,self.validator)
        path=self.decisions();obj=json.loads(path.read_text());obj['manifest_sha256']='wrong';self.put(path,obj)
        with self.assertRaisesRegex(ValueError,'not tied'):
            finalize(self.review,path,self.package,self.validator)
    def test_no_output_overlap(self):
        with self.assertRaisesRegex(ValueError,'overlap'):
            build(self.stage4,self.snapshot,self.package,self.stage4/'inside',self.validator)
    def test_extraction_problem_cannot_approve(self):
        p=self.stage4/'pdf'/'pages'/(self.pdfsha+'_p1.json')
        obj=json.loads(p.read_text());obj['evidence_status']='needs_extraction_review';obj['final_quality']['accepted_for_staging']=False;self.put(p,obj)
        d=self.stage4/'pdf'/'documents'/(self.pdfsha+'.json');obj=json.loads(d.read_text());obj['pages'][0]['accepted_for_staging']=False;self.put(d,obj)
        s=self.stage4/'stage4_dynamic_summary.json';obj=json.loads(s.read_text());obj['pages_needing_extraction_review']=1;obj['status']='processing_review_needed';self.put(s,obj)
        build(self.stage4,self.snapshot,self.package,self.review,self.validator)
        path=self.decisions(True)
        with self.assertRaisesRegex(ValueError,'Cannot approve'):
            finalize(self.review,path,self.package,self.validator)

if __name__=='__main__':unittest.main()
