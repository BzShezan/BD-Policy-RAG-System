# Unmochon Stage 3/4 → Stage 5 offline handoff audit

এই tool **শুধু local verification** করে। Network, OCR, ChromaDB/BM25 writes বা Stage 5 approval করে না। Output-এ `stage5_UNAPPROVED_review_queue.csv` মানে এটি কেবল প্রাথমিক reviewer list; কোনো reviewed clause বা index-import receipt নয়।

## কখন চালাবে

1. `G:\Capston\Unmochon` থেকে browser-এ প্রশ্ন দিয়ে Stage 2 research consent screen দেখো। Cancel করলে এখানে কিছু করার নেই।
2. কোনো **নতুন নির্দিষ্ট request-এর scope** গ্রহণযোগ্য হলে UI-তেই checkbox/Approve দেবে। পুরোনো অনুমতি পুনর্ব্যবহার করবে না।
3. Status-এ `staged_unverified` এলে UI-এর Stage 4 process চালাতে পারো। `review_required` হলে নিচের audit চালাও।
4. PowerShell-এ সর্বশেষ output folders খুঁজে নাও (শুধু listing, কোনো পরিবর্তন নয়):

```powershell
cd G:\Capston\Unmochon
Get-ChildItem .\data\research_runs -Directory |
  Sort-Object LastWriteTime -Descending |
  Select-Object -First 12 Name,FullName,LastWriteTime
```

সঠিক `raw_*` ও তার সংশ্লিষ্ট `processed_*` folder বেছে নাও—শুধু নামের সময় কাছাকাছি হলেই একই run নয়; script-এর `raw_snapshot` check মিলতে হবে।

```powershell
$raw = 'G:\Capston\Unmochon\data\research_runs\raw_<id>'
$processed = 'G:\Capston\Unmochon\data\research_runs\processed_<id>'
$out = 'G:\Capston\Unmochon\data\review_audits\audit_<NEW_UNIQUE_ID>'

python .\scripts\audit_research_handoff.py --raw $raw --processed $processed `
  --active-pointer 'G:\Capston\Unmochon_Stage6_Controlled_Index_Update\stage6_candidate_local\active.json' `
  --output $out
```

শুধু Stage 3 completed (Stage 4 এখনো run হয়নি) হলে `--processed $processed` বাদ দেবে।

Audit fail হলে source evidence এডিট করে PASS করানোর চেষ্টা করবে না। `AUDIT BLOCKED` message ও non-sensitive logs রিপোর্ট করবে। `audit.json` + `stage5_UNAPPROVED_review_queue.csv` তৈরি হলে original PDF ও website document যাচাইয়ের জন্য ব্যবহার করবে; **প্রতিটি chunk-এর আলাদা Stage 5 review**, এবং পরে **আলাদা index-import authorization** প্রয়োজন।

## Proof boundary

- Scope verified ≠ content relevant.
- Date extracted ≠ current policy legally effective.
- Stage 4 OCR processed ≠ OCR quality independently measured.
- Stage 5 queue ≠ content approved.
- Content approved ≠ index import approved.
- Indexed candidate ≠ promoted active generation.
- KG/contradiction module absent, no automatic version winner.

Accepted generation `reviewed_c02a1b74041d` অক্ষত রাখবে। পুরোনো Stage 6 fixed-54 importer নতুন evidence-এর জন্য ব্যবহার করবে না।

Stage4 processing হয়ে থাকলে একই command-এ `--processed $processed` যোগ করবে। `--active-pointer` কেবল JSON পড়বে; generation বদলাবে না।
