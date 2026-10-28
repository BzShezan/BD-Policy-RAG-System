"""Run the existing original UI pipeline on an isolated Stage 6 index snapshot."""
import time


class LocalTranslator:
    def __init__(self, translator=None):
        if translator is None:
            from scripts.retrieval.translator import Translator
            translator = Translator()
        self.original = translator
        self.note = None

    def to_bengali(self, question):
        try:
            return self.original.to_bengali(question)
        except (OSError, ImportError, RuntimeError, ValueError):
            # An optional missing NLLB cache must not break all English research.
            # Apply only the ORIGINAL translator's term normalization fallback.
            self.note = 'Local NLLB translation cache unavailable; original query and original policy-term dictionary used.'
            translated = self.original._apply_reverse_dictionary(question, question)
            # The old translator dictionary predates these newly added scopes.
            # Add question vocabulary only; this is never answer/source content.
            from .research_registry import match_scope
            vocabulary = {'nid':'এনআইডি জাতীয় পরিচয়পত্র ভোটার নিবন্ধন আবেদন',
                          'passport':'পাসপোর্ট আবেদন',
                          'birth_registration':'জন্ম নিবন্ধন আবেদন',
                          'driving_license':'ড্রাইভিং লাইসেন্স আবেদন'}
            for program, _ in match_scope(question):
                if program in vocabulary:
                    translated += ' ' + vocabulary[program]
            return translated


class OriginalPipeline:
    def __init__(self, retriever, translator=None):
        from UI import app
        self.app, self.retriever = app, retriever
        self.translator = LocalTranslator(translator)
        self.hybrid_calls, self.candidates = 0, []
        owner = self

        class Capture:
            def __getattr__(self, name):
                return getattr(retriever, name)

            def search(self, *args, **kwargs):
                result = retriever.search(*args, **kwargs)
                owner.hybrid_calls += 1
                owner.candidates = result
                return result

        app.initialize(Capture(), self.translator)

    def collect(self, query_id, question):
        from .answering import clause_explanation
        start = time.perf_counter()
        # Same translation -> intent/ministry -> hybrid/RRF -> two_stage ->
        # extractor -> metadata/viewer path as UI/app.py. Only the optional
        # generative explanation is replaced by literal source sentences.
        self.app.build_plain_explanation = lambda text, extracted: clause_explanation(question, text, extracted)
        data = self.app.search_question(question, return_k=10)
        cards = [r for r in data['results'] if r.get('clause_text')]
        oos = bool(data['results'] and data['results'][0].get('confidence_tier') == 'out_of_scope')
        return {'query_id': query_id, 'question': question,
                'retrieval_question': data.get('translated') or question,
                'translated': data.get('translated'), 'pipeline_cards': cards,
                'pipeline_results': [{'id': r['clause_id'], 'text': r['clause_text'],
                                     'doc_id': r['doc_id'], 'page': r['page'],
                                     'ministry': r['ministry'], 'confidence_tier': r['confidence_tier']}
                                    for r in cards],
                'raw_results': self.candidates[:10], 'all_candidates': self.candidates,
                'predicted_oos': oos, 'ministry_prediction': data['ministry'],
                'ministry_filter': data['ministry'], 'detected_intents': data['intents'],
                'conflicts': data.get('conflicts', []), 'translation_note': self.translator.note,
                'retrieval_ms': (time.perf_counter() - start) * 1000}


def format_source_hit(hit, row, app):
    m = row['metadata']
    return {'clause_id': row['id'], 'doc_id': m['doc_id'],
            'display_name': m.get('title') or m['doc_id'], 'source_url': m.get('source_url'),
            'ministry': m['ministry'], 'page': m.get('page_number') or None,
            'confidence_tier': 'source', 'clause_text': row['text'], 'extracted': [],
            'viewer_url': None, 'explanation': None, 'metadata': dict(m),
            'document_metadata': {'date_display': m.get('date_value') or None}, 'bbox': m.get('bbox')}
