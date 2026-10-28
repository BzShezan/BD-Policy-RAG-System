import hashlib, json, sys, tempfile, unittest
from pathlib import Path
HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE/'scripts'))
from stage6_import_preflight import canonical, sha, review

class TestPreflight(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.review_dir = self.root/'review';self.review_dir.mkdir()
        self.source = self.root/'stage4.json';self.source.write_text('{}',encoding='utf-8')
        self.workspace = self.root/'workspace';self.workspace.mkdir()
        self.put(self.workspace/'active.json',{'generation':'reviewed_sample','sequence':0})
        self.items = [
          {'id':'html:a','kind':'HTML','page':None,'date':None,'source_url':'https://modmr.gov.bd/doc',
           'text':'sample evidence', 'text_sha256':sha(b'sample evidence'),'raw_sha256':'a'*64,'extraction_status':'processed_unverified'},
          {'id':'pdf:b:p1','kind':'PDF','page':1,'date':'2023-06-05','source_url':'https://modmr.gov.bd/doc.pdf',
           'text':'bad extraction', 'text_sha256':sha(b'bad extraction'),'raw_sha256':'b'*64,'extraction_status':'processed_unverified'}]
        self.manifest = {'schema_version':1,'status':'awaiting_human_review','request_id':'test1',
                         'generation_at_consent':'reviewed_sample','source_snapshot_sha256':'c'*64,
                         'index_import_authorized':False,'source_file_hashes':{str(self.source):sha(self.source.read_bytes())},
                         'items':[{k:v for k,v in i.items() if k!='text'} for i in self.items]}
        self.put(self.review_dir/'review_manifest.json',self.manifest)
        (self.review_dir/'review_manifest.sha256').write_text(sha(canonical(self.manifest)),encoding='ascii')
        (self.review_dir/'review_items.jsonl').write_text(''.join(json.dumps(x)+'\n' for x in self.items),encoding='utf-8')
        self.decisions = {'schema_version':1,'manifest_sha256':sha(canonical(self.manifest)), 'request_id':'test1',
                          'reviewer':'Reviewer','decisions':[
                           {'id':'html:a','decision':'approved','source_checked':True,'context_checked':True,'notes':'Everything is fine.'},
                           {'id':'pdf:b:p1','decision':'needs_correction','source_checked':True,'context_checked':True,'notes':'Words broken'}]}
        self.decisions_path = self.root/'decisions.json';self.put(self.decisions_path,self.decisions)
        self.receipt = {'status':'content_review_recorded_not_import_approved','request_id':'test1',
             'manifest_sha256':sha(canonical(self.manifest)), 'decisions_sha256':sha(canonical(self.decisions)),
             'generation_at_consent':'reviewed_sample','index_import_authorized':False,'index_writes':0,
             'approved_content_count':1,'content_reviewed_items':[
                {'id':'html:a','raw_sha256':'a'*64,'source_url':'https://modmr.gov.bd/doc',
                 'page':None,'text_sha256':sha(b'sample evidence')} ]}
        self.put(self.review_dir/'content_review_record.json',self.receipt)
    def put(self,path, obj):path.write_text(json.dumps(obj,ensure_ascii=False,indent=2),encoding='utf-8')
    def check(self):return review(self.review_dir,self.decisions_path,self.workspace)
    def test_valid_receipt_still_no_import(self):
        result = self.check()
        self.assertEqual(result['status'],'STAGE5_CONSISTENT_IMPORT_NOT_AUTHORIZED')
        self.assertEqual(result['counts']['approved'],1)
        self.assertFalse(result['index_import_authorized'])
        self.assertEqual(result['index_writes'],0)
        self.assertIn('generic_review_note',result['items'][0]['flags'])
        self.assertIn('exclude_until_corrected_and_rereviewed',result['items'][1]['flags'])
    def test_tampered_decisions_blocked(self):
        self.decisions['decisions'][0]['notes']='Changed later';self.put(self.decisions_path,self.decisions)
        self.assertIn('Finalized receipt was not issued', ' '.join(self.check()['blocking_integrity_issues']))
    def test_changed_stage4_file_blocked(self):
        self.source.write_text('altered',encoding='utf-8')
        self.assertIn('Stage4 source changed', ' '.join(self.check()['blocking_integrity_issues']))
    def test_active_generation_drift_blocked(self):
        self.put(self.workspace/'active.json',{'generation':'newer_generation'})
        self.assertIn('Active generation differs', ' '.join(self.check()['blocking_integrity_issues']))
    def test_forged_approval_blocked(self):
        self.receipt['index_import_authorized']=True;self.put(self.review_dir/'content_review_record.json',self.receipt)
        self.assertIn('unexpected index permissions', ' '.join(self.check()['blocking_integrity_issues']))
    def test_modified_item_text_blocked(self):
        changed=dict(self.items[0]);changed['text']='tampered';self.items[0]=changed
        (self.review_dir/'review_items.jsonl').write_text(''.join(json.dumps(x)+'\n' for x in self.items),encoding='utf-8')
        self.assertIn('text hash mismatch', ' '.join(self.check()['blocking_integrity_issues']))

if __name__=='__main__': unittest.main()
