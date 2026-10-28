import asyncio
from pathlib import Path

from unmochon_live.answering import build_overview, relevant
from unmochon_live.schemas import Evidence
from unmochon_live.stage6_bridge import convert_stage6_result


def test_explanation_uses_both_gender_values_from_source_not_first_extractor_value():
    quote = 'আবেদনকারীর ক্ষেত্রে পুরুষের বয়স ৬৫ বছর বা তদূর্ধ্ব এবং মহিলার বয়স ৬২ বছর বা তদূর্ধ্ব হতে হবে।'
    e = Evidence(id='age-source', text=quote, source_kind='corpus_clause',
                 extracted=[{'label':'বয়স','value':'65'}],
                 source_url='https://msw.gov.bd/example.pdf', page=3)
    overview, answer = build_overview('পুরুষ ও মহিলার বয়স কত?', [e])
    assert '৬৫' in answer and '৬২' in answer
    assert all(block['text'] in quote and block['evidence_ids']==['age-source'] for block in overview['blocks'])
    assert overview['method']=='retrieved_source_sentences'


def test_original_extractor_and_pdf_metadata_survive_stage6_bridge():
    row = {'clause_id':'c1','clause_text':'পুরুষের বয়স ৬৫ এবং মহিলার বয়স ৬২ বছর।',
           'doc_id':'old_age_2013','display_name':'Original policy', 'ministry':'Social Welfare',
           'page':4, 'source_url':'https://msw.gov.bd/example.pdf',
           'viewer_url':'/pdfjs/web/viewer.html?file=/pdf/test.pdf#page=4&search=age',
           'confidence_tier':'high','extracted':[{'label':'বয়স','value':'65','confidence':1}],
           'explanation':'পুরুষের বয়স ৬৫ এবং মহিলার বয়স ৬২ বছর।',
           'metadata':{'page_number':4},'document_metadata':{'date_display':'2013'}}
    result = convert_stage6_result({'action':'ANSWER_FROM_EVIDENCE','generation':'fixture',
                                    'answer_results':[row], 'original_results':[row]}, 3)
    e = result.evidence[0]
    assert result.sufficient and e.viewer_url==row['viewer_url']
    assert e.extracted==row['extracted'] and e.explanation==row['explanation']
    assert e.page==4 and e.source_url==row['source_url'] and e.confidence_tier=='high'


def test_service_name_does_not_substitute_for_missing_fee_or_age_fact():
    guide = 'NID application form: fill and submit the form, then collect the receipt.'
    assert relevant('How to apply for NID?',guide,same_program=True)
    assert not relevant('What is the NID fee?',guide,same_program=True)
    assert not relevant('What is the NID age requirement?',guide,same_program=True)


def test_legacy_ui_files_preserved_and_no_human_review_in_active_ui():
    root=Path(__file__).resolve().parents[1]
    js=(root/'src/unmochon_live/ui/static/app.js').read_text(encoding='utf-8')
    assert 'function renderOverview' in js and 'evidence_ids' in js
    assert 'showContentReview' not in js and 'submit-evidence-review' not in js
    assert 'historicalOnly' not in js


def test_missing_translation_cache_keeps_bilingual_service_query_searchable():
    from unmochon_live.original_pipeline import LocalTranslator
    class NoCache:
        def to_bengali(self,q):
            raise OSError('Synthetic missing cache')
        def _apply_reverse_dictionary(self,original,translated):
            return translated
    translator=LocalTranslator(NoCache())
    result=translator.to_bengali('How to apply for NID?')
    assert 'NID' in result and 'ভোটার' in result and translator.note
