"""Offline gate tests. No Stage6 database/model required."""
import importlib.util
import pathlib
import sys
import subprocess

SCRIPT=pathlib.Path(__file__).resolve().parents[1]/'scripts'/'stage6_source_applicability.py'
sys.path.insert(0,str(SCRIPT.parent))
spec=importlib.util.spec_from_file_location('source_applicability_gate',SCRIPT)
gate=importlib.util.module_from_spec(spec)
spec.loader.exec_module(gate)

ID='pdf:'+'a'*64+':p2'
BASE={
  'status':'STAGE5_CONSISTENT_IMPORT_NOT_AUTHORIZED', 'request_id':'request123',
  'generation_at_consent':'reviewed_c02a1b74041d',
  'active_generation_read_only':'reviewed_c02a1b74041d',
  'receipt_digest':'f'*64, 'blocking_integrity_issues':[],
  'items':[{'id':ID,'kind':'PDF','decision':'approved','page':2,'date':None,
           'source_url':'https://modmr.gov.bd/source.pdf','text_sha256':'1'*64,'flags':['generic_review_note']}],
}
QUOTE='ইউনিয়ন পরিষদ যাচাই-বাছাই করে উপকারভোগীর তালিকা তৈরি করবে।'
TEXT='নথির শিরোনাম।\n'+QUOTE+'\nবিধি সমূহ।'


def ready_review():
    doc=gate.prepare(BASE)
    item=doc['items'][0]
    item.update(disposition='candidate',document_kind='official_notice',program='vgf',
         document_date='2023-06-05',date_evidence='Printed date 5 June 2023 on official PDF header.',
         source_version_notes='The printed order refers to Eid-ul-Azha in the year 2023 only.',
         applicability_notes='Historical evidence only: there is no confirmation about the 2026 order.',
         verified_quote=QUOTE, reviewer='Test reviewer',original_source_opened=True,
         page_and_quote_checked=True)
    return doc


def test_prepare_has_no_approval():
    doc=gate.prepare(BASE)
    assert doc['items'][0]['disposition']=='pending'
    assert doc['index_import_authorized'] is False
    assert len(doc['stage5_binding']['approved_ids'])==1
    assert gate.validate(BASE,doc,{ID:TEXT})['status']=='BLOCKED'


def test_review_candidate_is_not_import_authorization():
    r=gate.validate(BASE,ready_review(),{ID:TEXT})
    assert r['status']=='SOURCE_REVIEW_COMPLETE_NOT_IMPORT_AUTHORIZED'
    assert r['candidate_proposals_count']==1
    assert not r['index_import_authorized'] and r['index_writes']==0
    assert not r['current_policy_verified']


def test_stale_generation_blocks():
    inp=dict(BASE,active_generation_read_only='other_generation')
    r=gate.validate(inp,ready_review(),{ID:TEXT})
    assert r['status']=='BLOCKED'
    assert any('binding mismatch' in v for v in r['blocking_issues'])


def test_unknown_quote_blocks():
    doc=ready_review()
    doc['items'][0]['verified_quote']='ভুল তথ্য যা এই নথিতে নেই।'
    r=gate.validate(BASE,doc,{ID:TEXT})
    assert r['status']=='BLOCKED'
    assert any('literal substring' in v for v in r['blocking_issues'])


def test_date_missing_blocks():
    doc=ready_review()
    doc['items'][0]['document_date']=''
    r=gate.validate(BASE,doc,{ID:TEXT})
    assert r['status']=='BLOCKED'


def test_provenance_tampering_blocks():
    doc=ready_review()
    doc['items'][0]['page']=1
    r=gate.validate(BASE,doc,{ID:TEXT})
    assert r['status']=='BLOCKED'
    assert any('provenance mismatch' in v for v in r['blocking_issues'])


def test_exclusion_of_non_policy_html():
    doc=gate.prepare(BASE)
    doc['items'][0]['disposition']='exclude'
    r=gate.validate(BASE,doc,{ID:TEXT})
    assert r['status']=='NO_ELIGIBLE_ITEMS'
    assert r['index_import_authorized'] is False


def test_navigation_page_cannot_be_candidate():
    doc=ready_review()
    doc['items'][0]['document_kind']='navigation_page'
    assert gate.validate(BASE,doc,{ID:TEXT})['status']=='BLOCKED'


def test_cli_help_runs_without_model_or_index():
    result=subprocess.run([sys.executable,str(SCRIPT),'--help'],capture_output=True,text=True)
    assert result.returncode==0
    assert '--prepare' in result.stdout

# Optional overlap report reuses only verified active corpus rows, not the vector index.
OVERLAP_SCRIPT=SCRIPT.with_name('stage6_overlap_preview.py')
spec2=importlib.util.spec_from_file_location('source_overlap_preview',OVERLAP_SCRIPT)
overlap=importlib.util.module_from_spec(spec2)
spec2.loader.exec_module(overlap)


def test_overlap_preview_non_authorizing():
    rows=[{'id':'S6_111','metadata':{'source_raw_sha256':'a'*64,'page_number':2,
          'date_value':'2021-07-04'}}, {'id':'other','metadata':{}}]
    result=overlap.scan(BASE,'reviewed_c02a1b74041d',rows)
    assert result['items_with_same_page_overlap']==1
    assert result['index_import_authorized'] is False
    assert result['index_writes']==0


def test_overlap_blocks_untrusted_ids():
    pre=dict(BASE, items=[dict(BASE['items'][0],id='not:an:artifact')])
    import pytest
    with pytest.raises(ValueError):
        overlap.scan(pre,'reviewed_c02a1b74041d',[])
