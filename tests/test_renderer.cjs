// Wiring regression checks using the shipped renderer, with a minimal DOM test harness.
const fs = require('fs');
const vm = require('vm');
const assert = require('assert');
const path = require('path');
const filename = path.join(__dirname, '../src/unmochon_live/ui/static/app.js');
let source = fs.readFileSync(filename, 'utf8');
source = source.replace(/\}\(\)\);\s*$/, 'globalThis.testRenderer = {renderCard, renderResults, viewerURL}; }());');
const output = {innerHTML: ''};
const context = {URL, location: {origin: 'http://localhost:8000'},
  document: {addEventListener() {}, getElementById() {return output;}}};
vm.createContext(context); vm.runInContext(source, context);
const renderer = context.testRenderer;
const result = {question: 'query', route: 'RAG', status: 'EVIDENCE_FOUND', backend: 'original_hybrid_two_stage',
  elapsed_ms: 1, evidence: [{id: 'c', text: '<script>bad()</script> exact clause', page: 7,
  title: '<img src=x onerror=bad()>', source_kind: 'corpus_clause', confidence_tier: 'high',
  extracted: [{label: 'বয়স', value: '৬৫'}], explanation: 'Original explanation <b>escaped</b>',
  source_url: 'https://example.gov.bd/source', viewer_url: '/pdfjs/web/viewer.html?file=/pdf/policy.pdf#page=7&search=exact&highlight=true'}]};
renderer.renderResults(result);
assert(output.innerHTML.includes('class="extracted-values"'));
assert(output.innerHTML.includes('class="explanation-box"'));
assert(output.innerHTML.includes('/pdfjs/web/viewer.html'));
assert(output.innerHTML.includes('https://example.gov.bd/source'));
assert(output.innerHTML.includes('&lt;script&gt;bad()&lt;/script&gt;'));
assert(!output.innerHTML.includes('<script>'));
assert(!output.innerHTML.includes('<img src=x'));
result.evidence[0].source_url = 'javascript:alert(1)';
result.evidence[0].viewer_url = 'https://evil.example/pdfjs/web/viewer.html';
renderer.renderResults(result);
assert(!output.innerHTML.includes('javascript:'));
assert(!output.innerHTML.includes('evil.example'));
assert(output.innerHTML.includes('পিডিএফ উপলব্ধ নয়'));
result.conflicts = [{label:'বয়স', values:[{value:'৬৫', date_display:'2025', display_name:'New',is_current:true},{value:'৬০',date_display:'2013',display_name:'Old',is_current:false}]}];
renderer.renderResults(result);
assert(output.innerHTML.includes('class="conflict-card"'));
assert(output.innerHTML.includes('is-current'));
assert(output.innerHTML.includes('is-superseded'));
console.log('Renderer checks passed: original extraction/explanation/PDF links/conflicts, escaping, unsafe URL rejection.');
