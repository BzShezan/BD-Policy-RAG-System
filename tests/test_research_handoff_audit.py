"""Offline safety tests; all data is synthetic and never accesses the network."""
import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

MODULE = Path(__file__).resolve().parents[1] / 'scripts' / 'audit_research_handoff.py'
spec = importlib.util.spec_from_file_location('audit_research_handoff', MODULE)
audit = importlib.util.module_from_spec(spec)
spec.loader.exec_module(audit)


def dump(path, obj):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False), encoding='utf-8')


class AuditTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.base=Path(self.tmp.name)
        self.raw=self.base/'raw_123'
        self.raw.mkdir()
        dump(self.raw/'stage3_output_owner.json', {'owner':'unmochon_stage3_crawler','schema_version':1})
        self.content=b'<html>Official government page</html>'
        self.digest=hashlib.sha256(self.content).hexdigest()
        self.rel='runs/t001/raw/'+self.digest+'.html'
        src=self.raw/self.rel;src.parent.mkdir(parents=True)
        src.write_bytes(self.content)
        self.art={'url':'https://modmr.gov.bd/','requested_url':'https://modmr.gov.bd/',
            'relative_path':self.rel, 'source_role':'government_page', 'ministry':'Disaster Management',
            'content_type':'text/html', 'http_status':200, 'raw_sha256':self.digest,
            'bytes_received':len(self.content), 'evidence_status':'staged_unverified'}
        self.scope={'question':'২০২৬ ভিজিএফ?', 'program':'vgf','ministry':'Disaster Management',
                    'allowed_hosts':['modmr.gov.bd','ddm.gov.bd'], 'max_http_requests':12}
        self.receipt={'schema_version':1, 'status':'staged_unverified',
            'request_id':'r123', 'generation_at_consent':'reviewed_c02a1b74041d',
            'result':{'artifacts':[self.art],'index_updated':False,'requires_human_import_approval':True},
            'scope':self.scope, 'network_request_attempts':2, 'index_writes':0,
            'current_policy_verified':False, 'source_approval':False}
        self.events=[{'event':'request_created','request_id':'r123'},
            {'event':'consent_decision','request_id':'r123','state':'approved'},
            {'event':'permit_consumed','request_id':'r123'}]
        self.save()

    def tearDown(self):self.tmp.cleanup()

    def save(self):
        dump(self.raw/'stage3_app_summary.json',self.receipt)
        dump(self.raw/'latest_consent_audit.json',self.events)

    def test_clean_raw_creates_unapproved_review(self):
        report,rows=audit.inspect(self.raw)
        self.assertEqual(report['status'],'raw_verified_pending_stage4')
        audit.write_review_output(self.base/'review',report,rows)
        self.assertFalse(report['index_import_approved'])
        self.assertTrue((self.base/'review/stage5_UNAPPROVED_review_queue.csv').exists())
        with self.assertRaises(audit.AuditFailure):
            audit.write_review_output(self.base/'review',report,rows)

    def test_no_approval_blocks(self):
        self.events[1]['state']='denied';self.save()
        with self.assertRaises(audit.AuditFailure):audit.inspect(self.raw)

    def test_changed_bytes_blocks(self):
        (self.raw/self.rel).write_bytes(b'tampered')
        with self.assertRaises(audit.AuditFailure):audit.inspect(self.raw)

    def test_out_of_scope_blocks(self):
        self.art['url']='https://other.gov.bd/'
        self.save()
        with self.assertRaises(audit.AuditFailure):audit.inspect(self.raw)

    def test_unproven_object_storage_blocks(self):
        self.art['url']='https://objectstorage.example.net/file.pdf'
        self.save()
        with self.assertRaises(audit.AuditFailure):audit.inspect(self.raw)

    def test_budget_violation_blocks(self):
        self.receipt['network_request_attempts']=13;self.save()
        with self.assertRaises(audit.AuditFailure):audit.inspect(self.raw)

    def test_unsafe_relative_path_blocks(self):
        self.art['relative_path']='../../active.json';self.save()
        with self.assertRaises(audit.AuditFailure):audit.inspect(self.raw)

    def test_index_write_blocks(self):
        self.receipt['index_writes']=1;self.save()
        with self.assertRaises(audit.AuditFailure):audit.inspect(self.raw)

    def test_stage4_both_processed(self):
        processed=self.base/'processed_abc';processed.mkdir()
        handoff={'raw_snapshot':str(self.raw), 'processors':{'html':{'returncode':0},'pdf':{'returncode':0}},
            'manual_content_review_required':True,'index_import_authorized':False,
            'active_generation_unchanged':True}
        dump(processed/'app_stage4_handoff.json',handoff)
        summ={'source_request_id':'r123','source_consent_audit':'MATCH','source_raw_hashes_verified':1,
              'index_writes':0,'network_calls':0}
        dump(processed/'html/stage4_html_summary.json',summ)
        dump(processed/'pdf/stage4_pdf_summary.json',summ)
        r,_=audit.inspect(self.raw,processed)
        self.assertEqual(r['status'],'stage4_verified_pending_manual_review')
        summ['source_request_id']='another';dump(processed/'html/stage4_html_summary.json',summ)
        with self.assertRaises(audit.AuditFailure):audit.inspect(self.raw,processed)

    def test_raw_location_not_valid_review_output(self):
        report,rows=audit.inspect(self.raw)
        with self.assertRaises(audit.AuditFailure):
            audit.write_review_output(self.raw/'new_review',report,rows)

if __name__=='__main__':unittest.main()
