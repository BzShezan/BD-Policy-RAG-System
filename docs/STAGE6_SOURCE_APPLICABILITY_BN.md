# Stage 6: নতুন Evidence-এর Source Edition / Applicability Review

এই পর্যায় **Stage 5 content review-এর পরে, Stage 6 index-import permission-এর আগে**।
এতে index, model cache, `active.json`, crawled data বা KG/contradiction hook কোনোটাই বদলানো হয় না।

## কেন প্রয়োজন

বর্তমান preflight: ৬টি content-approved, ২টি correction-needed, ৬টি generic note, document date সব কটিরই অনিশ্চিত। Source/document edition নিশ্চিত না করে ৬টি item-কে import-ready policy clause বলা যাবে না।

## Review file-এ কী লিখবেন

প্রতিটি approved item-এ `disposition` হবে `exclude` অথবা `candidate`। প্রথমে সব `pending`।

- `exclude`: শুধু homepage/portal navigation, duplicate non-policy document, বা সন্দেহজনক content হলে। কারণ আলাদা audit note-এ রাখুন। `needs_correction` item এখানে দেখানোই হয় না।
- `candidate`: মূল সরকারি নথি (নীতিমালা/প্রজ্ঞাপন/নির্দিষ্ট আদেশ) এবং উদ্ধৃতিটি নথির নির্দিষ্ট অংশ থেকে যাচাই করলে।
- `document_kind`: `official_policy_document`, `official_notice`, `navigation_page`, `other`।
- `document_date`: PDF/official source-এ সত্যিই মুদ্রিত তারিখ `YYYY-MM-DD`। URL folder year দেখে তারিখ বানাবেন না। প্রমাণ না থাকলে `exclude`/`pending` রাখুন।
- `date_evidence`: কোন printed line/page দেখে তারিখ যাচাই করেছেন তা বিস্তারিত লিখুন।
- `source_version_notes`: নথির নাম, edition ও এটি কোন event/year নিয়ে, তা স্পষ্ট করুন।
- `applicability_notes`: নথির পরিধি/সময়কাল এবং ২০২৬ সালের দাবি কেন এখনো যাচাই হয়নি, তা লিখুন।
- `verified_quote`: Stage 5 extracted text-এর **হুবহু substring** (কমপক্ষে ১২ অক্ষর)। OCR ভুল থাকলে source দেখে নিজের মতো বদলাবেন না; Stage 4 correction + Stage 5 re-review লাগবে।
- `reviewer`, `original_source_opened`, `page_and_quote_checked`: বাস্তবে যাচাই করলে পূরণ করুন।
- `current_policy_verified`: সর্বদা `false`; এটি current policy যাচাই করে না।

**গুরুত্বপূর্ণ:** `SOURCE_REVIEW_COMPLETE_NOT_IMPORT_AUTHORIZED` মানে শুধু human review metadata internally consistent হয়েছে; এই tool কোনো import permit দেয় না। আর `candidate_proposals_count` actual new index rows-এর সংখ্যা নয়।

## Review করার আগে

`G:\Capston\Unmochon`-এ Stage 5 receipt finalization ও Stage 6 import preflight PASS করতে হবে।

```powershell
cd G:\Capston\Unmochon
$env:PYTHONPATH = (Join-Path (Get-Location) 'src')
python .\scripts\stage6_source_applicability.py `
 --review-dir '.\data\research_runs\stage5_review_20261017' `
 --decisions 'G:\Capston\stage5_review_decisions_v2.json' `
 --workspace 'G:\Capston\Unmochon_Stage6_Controlled_Index_Update\stage6_candidate_local' `
 --prepare '.\data\research_runs\stage6_source_review_DRAFT_20261017.json'
```

`stage6_source_review_DRAFT_20261017.json` সম্পাদনা করে নতুন filename-এ সংরক্ষণ করুন। Unverified document date/quote অনুমান করে পূরণ করবেন না। পরে:

```powershell
python .\scripts\stage6_source_applicability.py `
 --review-dir '.\data\research_runs\stage5_review_20261017' `
 --decisions 'G:\Capston\stage5_review_decisions_v2.json' `
 --workspace 'G:\Capston\Unmochon_Stage6_Controlled_Index_Update\stage6_candidate_local' `
 --validate '.\data\research_runs\stage6_source_review_REVIEWED.json'
```

সফল হলেও index write হবে না। পরে **স্বতন্ত্র import authorization**, exact duplicate scan, isolated ChromaDB+BM25 build, old-model/held-out-safe regressions এবং controlled activation দরকার। KG module teammate পরে add করতে পারবেন।

## একই PDF আগের generation-এ আছে কি না (read-only)

```powershell
python .\scripts\stage6_overlap_preview.py `
 --review-dir '.\data\research_runs\stage5_review_20261017' `
 --decisions 'G:\Capston\stage5_review_decisions_v2.json' `
 --workspace 'G:\Capston\Unmochon_Stage6_Controlled_Index_Update\stage6_candidate_local'
```

`same_raw_source_index_rows` ও `same_pdf_page_index_rows` শুধু overlapping source/page count; quote/claim duplicate প্রমাণ নয়। এতে শুধু sealed selected corpus-এর checksum মেলে; পূর্ণ ChromaDB/BM25 pair audit নয়।
