# Unmochon — original retrieval + automatic research update

এই update আপনার বর্তমান `G:\Capston\Unmochon` project-এর জন্য। আগের integration,
Windows encoding fix ও Windows path fix বসানো অবস্থার উপর এটি install হবে।
নতুন database বা আলাদা app বানানোর প্রয়োজন নেই।

## Install ও চালু করা

চলমান Unmochon server-এ `Ctrl+C` দিন। ZIP extract করে যে folder-এ
`install_and_run.py` আছে সেখানে PowerShell খুলুন:

```powershell
conda activate unmochon_stage1
python .\install_and_run.py --target "G:\Capston\Unmochon"
```

এটি code backup রেখে update বসাবে এবং একই app চালু করবে। Browser-এ
`http://127.0.0.1:8000` খুলে একবার `Ctrl+F5` দিন।

শুধু install করে পরে চালাতে চাইলে:

```powershell
python .\install_and_run.py --target "G:\Capston\Unmochon" --install-only
cd "G:\Capston\Unmochon"
python -X utf8 -m unmochon_live serve
```

Installer `.env`, existing accepted index, models ও raw PDF বদলায় না। Database
rebuild করতে হবে না। Installation-এর আগে file hashes মেলে; স্থানীয় code অন্যরকম
হলে সব পরিবর্তন শুরুর আগেই `BLOCKED` হবে।

## যে তিনটি সমস্যা ঠিক হয়েছে

| আগে | এই update-এর আচরণ |
|---|---|
| Stage 6-এর pilot answer gate পুরোনো retrieval results আটকে দিত; extractor/explanation/viewer fields হারাত | সরাসরি original `UI.app.search_question` path; original result ranking, extractors, metadata, PDF viewer response-এ থাকে |
| Research শেষে date/OCR/content approval form-এ থামত | নতুন permission-এর পর readable HTML/PDF/OCR content স্বয়ংক্রিয়ভাবে chunk ও paired ChromaDB/BM25-এ যোগ হয়; human review লাগে না |
| উপরে generic warning ও raw source-version panels প্রধান উত্তর ঢেকে রাখত | শুরুতে source-based overview, প্রতিটি বক্তব্যে citation chip; নিচে আগের style-এর result cards, extracted values, সম্পূর্ণ clause ও PDF/web links |

## একই original pipeline কীভাবে চলছে

`UI/app.py::search_question`-এর translation → intent/ministry →
`HybridRetriever.search` (BM25 + dense + RRF + original query expansion) →
`two_stage_search` → original NER/extractors → metadata/PDF-viewer path চালানো হয়।
এই original files, base CSS/HTML templates ও frozen Stage 1–6 source edit করা হয়নি।

মডেল এবং index paths শুধু accepted Stage 6 snapshot-এর সঙ্গে bind করা হয়।
Query sealed source-এ write না করে disposable copy ব্যবহার করে। পুরোনো limited
Stage 2 pilot catalog সাধারণ original result display বন্ধ করতে পারে না।

Original local NLLB cache থাকলে সেই translation চলে। Cache না থাকলে English
query রেখে original policy-term dictionary এবং নতুন service scopes-এর query
vocabulary ব্যবহার হয়; diagnostic-এ সেটি লেখা থাকে। কোনো model auto-download হয় না।

Original domain vocabulary-তে NID/passport ছিল না। এসব নতুন programme-এর জন্য
একই hybrid retrieval-এর relevant ingested chunks ব্যবহার হয়; service name মিললেই
অসংশ্লিষ্ট age/fee claim দিয়ে উত্তর বানানো হয় না।

## Research থেকে final answer

1. একই stored-pair retrieval-এ যথেষ্ট তথ্য না পেলে নতুন permission prompt আসে।
2. অনুমতি দিলে registry-র নির্দিষ্ট সরকারি hosts ও ঘোষিত budget-এর মধ্যে crawl হয়।
3. HTML text, PDF-এর digital text এবং সম্ভব হলে OCR text বের হয়।
4. Captured readable content-এর সব chunks যোগ হয়; শুধু প্রশ্নের সরাসরি matching
   অংশ বেছে import করা হয় না। তারিখ না থাকলে date unknown থাকে; readable OCR-এর
   জন্যও human approval লাগে না। Unreadable/error/challenge responses index হয় না।
5. একই content দুই URL-এ থাকলে text deduplicate হয়, URL aliases metadata-তে থাকে।
6. নতুন candidate-এ ChromaDB ও BM25 consistency, পুরোনো vectors, regression ও
   fresh-process reopen যাচাই হয়। তারপর এক pointer-এ নতুন pair সক্রিয় হয়।
7. Original question আবার একই retrieval দিয়ে চালিয়ে explanation ও sources দেখায়।
   পরের একই প্রশ্ন stored evidence থেকেই উত্তর পায়।

সব content সংরক্ষণের অর্থ সব content প্রশ্নের উত্তর দেবে এমন নয়। Readable
sources যোগ হওয়ার পরেও নির্দিষ্ট উত্তর না থাকলে job `research_complete` হয় এবং
কী পাওয়া যায়নি তা জানায়; source chunks সংরক্ষিত থাকে। Query/index execution
ভাঙলে পূর্বের pair-এ rollback হয়। Duplicate-only capture index আবার লেখে না।

NID registry-তে সরকারি উপজেলা নির্বাচন অফিসের একটি readable registration
instruction page যোগ হয়েছে। Citation-এ সেই source-এর নিজস্ব title ও URL থাকে;
local office-এর instructions-কে model দিয়ে জাতীয় নিয়ম হিসেবে নতুন করে লেখা হয় না।
Registry বর্তমানে সাতটি authority-এর নির্দিষ্ট scopes সমর্থন করে; unlimited
সব সরকারি website বা search engine crawl নয়। Scope configuration-এ আরও authority
যোগ করা যায়। KG/contradiction module-এর আগের integration port অপরিবর্তিত।

## Explanation-এর ভিত্তি

Google-এর overview-এর মতো answer-first presentation, bullets ও source chips
দেওয়া হয়েছে। বক্তব্যগুলো retrieved clause/page-এর আসল sentence থেকে নির্বাচন
করা হয়। কোনো LLM/API দিয়ে তথ্য বা সংখ্যা বানানো হয় না, generated answer cache-ও
ব্যবহার হয় না। একই quote-এ পুরুষ ও মহিলার আলাদা বয়স থাকলে দুটোই থাকে; এক extractor-এর
প্রথম value দিয়ে পুরো explanation লেখা হয় না।

নিচের card-এ original extractor values, সম্পূর্ণ clause, document/page metadata,
official source URL এবং PDF থাকলে page-specific viewer থাকে। Web source হলে সেই
webpage-এর link থাকে। Published date জানা না থাকলে তা বানানো হয় না।

## যাচাইয়ের পরিসর

ZIP-এর `TEST_RESULTS.txt`, `UI_CHECK.json` এবং `PACKAGE_VALIDATION.json` দেখুন।
Tests real ChromaDB/BM25 ও original retrieval methods ব্যবহার করেছে; missing
government HTTP/model assets-এর জায়গায় test-only fixtures ব্যবহার হয়েছে। Desktop
ও mobile browser rendering, citation links এবং no-review UI যাচাই করা হয়েছে।

আপনার Windows-এর real 14,397-item generation ও model cache এখানে পাওয়া যায়নি;
সেগুলোর semantic accuracy বা live government availability-এর certification এই
ZIP নয়। আপনার আগে পাস-করা Windows environment ও accepted pair-ই reuse করবে।
