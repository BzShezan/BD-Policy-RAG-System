# Unmochon — অ্যাপের পূর্ণ agentic workflow integration

> Historical implementation record: mandatory review and pilot answer gates below were superseded by [READY_UPDATE_BN.md](READY_UPDATE_BN.md). The current application automatically ingests readable sources after permission.

এই পরিবর্তন আপনার দেওয়া `Unmochon.zip`-এর উপর তৈরি। নতুন standalone অ্যাপ নয়। মূল CSS, HTML templates, OCR/retrieval/extractor modules, frozen Stage 1–6 source এবং `integrations/kg/adapter.py` অপরিবর্তিত। প্রয়োজনীয় JavaScript wiring ও backend adapters যোগ হয়েছে।

## বাস্তব কোডে যে ফাঁক ছিল

| অংশ | আগে কী ছিল | এখন কী যুক্ত হয়েছে |
|---|---|---|
| `orchestrator.py` | NID-সহ পরিচিত service Stage 6 search-এর আগেই ফেরত যেত; executable permission offer হত না | আগে verified pair-এ search; evidence না থাকলে সরকারি authority/program-সহ bounded trigger |
| `research_flow.py` | শুধু তিন মন্ত্রণালয়; crawl শেষে থামত; processing আলাদা click; index writes সবসময় 0 | এক job-এ crawl → processing → verification → candidate build/restart → activation → original re-query; cancel/expiry/errors/rollback |
| `stage4_dynamic.py` | সঠিক provenance validator ছিল; পূর্ণ pilot package-এর data-ও খুঁজত | একই validator ও extractors পুনর্ব্যবহার; frozen Python source hash check; controlled registry; ইংরেজি service PDF digital extraction |
| `stage5_prepare_review.py`, `stage5_finalize_review.py` | dynamic review bundle ও human record ছিল; generalized import handoff ছিল না | এগুলোর উপর question-bound verification receipt; auto criteria অথবা একই UI-তে human review; পুনরায় যাচাই করে Stage 6-এ handoff |
| Stage 6 | frozen historical 54-clause importer; immutable generation/seal/switch/rollback ছিল | frozen importer না চালিয়ে একই append/verify/seal primitives-এ generalized candidate; CAS pointer guard; fresh-process verification |
| Stage 6 query | external package/pilot data-র উপর নির্ভরতা | unified app child entrypoint; original hybrid/two-stage/Stage 2; accepted historical evidence-এর sealed sidecars বজায় |
| Runtime | বাইরের code-folder path; ZIP থেকে registry/pilot data বাদ | bundled code defaults; versioned registry; ছোট reviewed JSON metadata-এর একবার hash-checked migration |

## ব্যবহৃত পুরোনো implementations

- Stage 3: `reference_pipelines/stage4/stage3/{consent,crawler,scope,transport,page_content}.py`। একই request-bound permit, host/redirect/robots/DNS/bytes/depth limits এবং raw receipts।
- Stage 4: `stage4_dynamic.py` এবং frozen `stage4/{html_processing,pdf_processing}.py`। একই raw/referrer SHA checks, HTML content extraction, digital PDF/OCR primitives।
- Stage 5: `scripts/stage5_prepare_review.py` দিয়ে exact provenance-bound review bundle, original `stage5/chunks.py::split_size`; human decisions-এর ক্ষেত্রে original finalizer দিয়ে আলাদা human record।
- Stage 6: `stage6/index_pair.py::{append_candidate,verify_pair,vector_hash,restricted_payload}`, `stage6/generations.py::{active,generation,seal,verify_generation}`, এবং `stage6/common.py`-এর lock/history/atomic write।
- Original search: frozen `HybridRetriever` (dense + BM25 + RRF), original two-stage search, intents, NER extractors, এবং Stage 2 evaluator। কোনো নতুন vector-search algorithm দেওয়া হয়নি।

Original Stage 6 switch-এ expected-pointer parameter নেই। নতুন `compare_switch()` একই lock/manifest/atomic-pointer architecture-এ compare-and-swap যোগ করে। একটি job আরেকটি job-এর generation overwrite বা rollback করতে পারে না। তিন pilot bucket-এর verifier-এ নতুন registry authority কেবল isolated worker-এর runtime mapping-এ যোগ হয়; frozen source পরিবর্তন হয় না।

## অনুমতি ও verification-এর নির্দিষ্ট নিয়ম

Permission prompt-এ authority, exact hosts, seeds, HTTP/resource/byte/time caps এবং conditional index-update disclosure আছে। Checkbox-এর confirmation থেকে `allow_conditional_update=true` পাঠানো হয়। শুধু সাধারণ research approval পাঠালে crawl/processing হতে পারে, কিন্তু index activation হবে না। প্রতিটি নতুন প্রশ্নে নতুন, পাঁচ মিনিটের মধ্যে দেওয়ার, one-use অনুমতি লাগে। আগের session-এর অনুমতি নেই।

Auto eligibility-র জন্য সব শর্ত প্রয়োজন:

1. সরকারি scope ও fresh consent receipt মিলে; fetched bytes, redirect/referrer এবং SHA hashes সঠিক।
2. Stage 4 ও Stage 5 source/text hashes অপরিবর্তিত; প্রত্যেক quote extracted source-এর হুবহু অংশ।
3. clean digital extraction; corrupt text/OCR auto-approved নয়। এটি extraction heuristic, মাপা CER/WER নয়।
4. প্রাসঙ্গিক, দ্ব্যর্থহীন, labelled document date থাকে। অস্পষ্ট/অনুপস্থিত তারিখ human review-তে যায়। footer-এর generic website update date দিয়ে বর্তমান প্রযোজ্যতা ঘোষণা করা হয় না।
5. Pilot policy fact হলে Stage 2 evaluator প্রশ্নের সম্পূর্ণ fact/date/version মেলায়। বর্তমান নীতি সম্পর্কে নিশ্চয়তা বা conflicting/unsupported applicability automatic approval পায় না।
6. Basic service application process হলে প্রশ্নটি process-সংক্রান্ত হতে হবে এবং substantive source-এ service identity, form/application এবং অন্তত দুই ধরনের process action থাকতে হবে। Fee, eligibility/age, renewal, correction, status, latest/current প্রশ্নকে এই process rule দিয়ে উত্তর দেওয়া হয় না।
7. কোনো প্রাসঙ্গিক source-এর verification বাধা থাকলে batch review-তে যায়। Source review-এর নামে auto decision-কে human approval বলা হয় না।

Human review-তে original source, quote/page/context, notes, এবং প্রয়োজনীয় document date যাচাই করে জমা দিতে হবে। Undated service guidance কেবল explicit human acknowledgement-এ সীমিত guidance হিসেবে গ্রহণ করা যায়; date unknown-ই থাকে, current policy হয় না। অস্পষ্ট policy date এবং failed extraction অনুমোদনের checkbox দিয়ে bypass হয় না। সংশোধনযোগ্য OCR-এর জন্য existing extraction/review tools ব্যবহার করে নতুন review প্রয়োজন।

## Update ও failure behaviour

- Active `reviewed_c02a1b74041d` বা পরবর্তী sealed generation in-place খোলা/লেখা হয় না। Query-ও disposable copy-তে হয়।
- Candidate source থেকে copy হয়; provenance ও raw PDF/HTML candidate evidence-এ রাখা হয়। একই source/quote পুনরায় এলে dedup হয়; আলাদা undated page এক করা হয় না।
- Existing dense vectors অপরিবর্তিত থাকার hash, exact Chroma/BM25 IDs, text hashes, metadata, token frequencies, lengths ও IDF পরীক্ষা হয়। Sparse index actual dense texts থেকেই rebuild হয়।
- একই original retrieval-এর তিন fixed policy probe before/after চলে; original question candidate-এ answerable হতে হয়। এটি ছোট regression gate; বড় benchmark/accuracy claim নয়।
- Writer exit-এর পরে দ্বিতীয় process pair পুনরায় খোলে এবং সব নতুন dense clause query করে। তারপরই seal ও atomic activation।
- Original question অ্যাপের একই `execute()` পথে একবার re-query হয়। নতুন permission offer তৈরি বা recursive research হয় না।
- Re-query failure/cancellation হলে আগের সম্পূর্ণ pair rollback হয়। অন্য writer pointer বদলে ফেললে তার update মুছে ফেলা হয় না; recovery status দেখায়।
- Processing job সর্বোচ্চ 40 মিনিট, একসঙ্গে 2টি; crawler-এর নিজের caps এখনও 5 resources / 12 HTTP requests / 10 MB / 30 seconds / depth 2। Cancel চলমান HTTP call শেষ/timeout হওয়ার পর পরের request আটকায়; চলমান processing/writer process থামানো হয়।
- App restart হলে পুরোনো consent resume হয় না। Diagnostic job receipts থাকে, কিন্তু fresh approval ছাড়া নতুন network কাজ শুরু হয় না।

## OOS routing কী বোঝায়

| অবস্থা | আচরণ |
|---|---|
| বিদ্যমান evidence যথেষ্ট | উত্তর; কোনো research নয় |
| পরিষ্কার non-government/non-policy request | `DECLINE_OUT_OF_DOMAIN`; crawl নয় |
| পরিচিত service কিন্তু evidence নেই | registry-bound permission offer |
| relevant policy evidence অসম্পূর্ণ | নির্ধারিত authority থাকলে bounded offer |
| latest/current বা source date প্রয়োজন | research/review; পুরোনো source-কে current বলা হয় না |
| authority/domain যাচাই করা যায়নি | clarification বা scope unavailable; unrestricted `.gov.bd` crawl নয় |
| index/model/integrity error | fail closed; corpus gap ধরে অন্য index/crawler fallback নয় |

## সীমা ও সত্যিকারের বাকি যাচাই

এখানে পূর্ণ workflow real ChromaDB + BM25 দিয়ে পরীক্ষা হয়েছে, তবে synthetic HTTP responses এবং synthetic 384-D encoder দিয়ে। Production path-এ এই fixture encoder নেই। সেখানে আপনার existing pinned local model resolve ও hash-check হয়।

Windows-এর accepted 14,397-item generation, আপনার model cache, actual NID website crawl, scanned Bangla PDF-এর real Tesseract run ও বড় retrieval/OCR benchmark এখানে চালানো হয়নি। Live government website 30-second scope budget, robots, TLS, JS/CAPTCHA অথবা missing source-এর কারণে উপযুক্ত evidence না-ও দিতে পারে। সেক্ষেত্রে verified answer/update সফল বলা হবে না।

Registry-তে সাতটি নির্দিষ্ট authority আছে; সব Bangladesh government office auto-discovery বা unrestricted search engine crawler নয়। নতুন authority যোগ করতে authority proof-সহ registry edit ও নতুন consent লাগবে। General service-এর জটিল fact extraction এবং অজানা policy programme auto-verified নয়; review বা clarification প্রয়োজন। KG/contradiction resolution teammate-এর জন্য আগের port-এ রাখা আছে।
