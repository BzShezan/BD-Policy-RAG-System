# Unmochon — Stage 5 Dynamic Human Review (2026-10-17)

## Scope

এই add-only code **Unified Unmochon** (`G:\Capston\Unmochon`)-এর `Stage4 Dynamic` output নিয়ে review queue তৈরি করে। এটি Stage 5-এর *human content review* layer মাত্র: **Stage 6 import builder, source-vs-current-policy verification, KG module, automatic winner, OCR benchmark বা final answer generation নয়**।

প্রথম real Stage4 run (2026-10-16) থেকে পাওয়া user-reported summary:
- ৫টি immutable raw artifacts (২ HTML, ৩ PDF); ৬ PDF page।
- ১৭/১৭ prior app tests PASS; Stage4 processed ৫/৫, `source_snapshot_unchanged=true`।
- `human_content_review_required=true`, `index_import_authorized=false`, index/network writes 0।

Raw files এবং reviewer-approved text **এখানে upload হয়নি**, তাই এই patch বাস্তব source factual correctness বা actual approval যাচাই করতে পারেনি।

## 1. Installer (no overwrite)

Patch ZIP Windows-এ **temporary directory**-তে extract করুন; new top-level Capston project folder বানাতে হবে না।

```powershell
conda activate unmochon_stage1
cd <EXTRACTED_PATCH_DIRECTORY>
python .\install_stage5_review.py --app-root "G:\Capston\Unmochon" --check
python .\install_stage5_review.py --app-root "G:\Capston\Unmochon" --apply
```

Existing `src\unmochon_live\stage4_dynamic.py` ও `research_flow.py` থাকতেই হবে। Installer source file replace করে না।

## 2. Local test

```powershell
cd G:\Capston\Unmochon
$env:PYTHONPATH = (Join-Path (Get-Location) 'src')
$env:PYTHONIOENCODING = 'utf-8'
$env:PYTHONUTF8 = '1'
python -m pytest -q tests/test_stage5_dynamic_review.py
```

## 3. আগের Stage4 result থেকে **review queue তৈরি**

এই command কেবল আগে অনুমোদিত ও ইতিমধ্যে সংগৃহীত **আগের snapshot** পড়বে; নতুন network/crawl/permission নয়।

```powershell
cd G:\Capston\Unmochon
python .\scripts\stage5_prepare_review.py `
  --stage4 "G:\Capston\Unmochon\data\research_runs\stage4_retry_20261016" `
  --snapshot "G:\Capston\Unmochon\data\research_runs\raw_7b82ecef5b944c0e83cad280150d6c60" `
  --package "G:\Capston\Unmochon_Stage4_Evidence_Processing" `
  --output "G:\Capston\Unmochon\data\research_runs\stage5_review_20261017"
```

`review.html`, `review_items.jsonl`, `review_manifest.json` ও `review_manifest.sha256` তৈরি হবে। Existing processed output বা original source বদলায় না। Browser-এ local page খুলুন:

```powershell
Invoke-Item ".\data\research_runs\stage5_review_20261017\review.html"
```

Review HTML **offline**; government source link আলাদাভাবে click করলে সাধারণ browser internet খুলতে পারে—এটি app crawler call নয়। Source-এর মূল PDF/document নিজে মিলিয়ে, date, quote, page/context, OCR ভুল যাচাই করুন। PDF page extraction gate pass করলেও মানব যাচাই বাকি।

Page-এর reviewer name লিখুন; item-wise decision দিন: `pending`, `approved`, `rejected`, বা `needs_correction`। Approval-এর জন্য দুইটি check, এবং অন্তত ১০-অক্ষরের notes প্রয়োজন। **Export decisions JSON** চাপলে downloaded `stage5_review_decisions.json` আসবে। User judgement ছাড়া কোনো content automatic-approved নয়।

## 4. Human content review record

Decisions file-এ ব্যক্তিগত তথ্য না রাখাই ভালো; reviewer nickname/ID যথেষ্ট। Windows-এ file কোথায় download হয়েছে সে path দিন:

```powershell
python .\scripts\stage5_finalize_review.py `
  --review-dir "G:\Capston\Unmochon\data\research_runs\stage5_review_20261017" `
  --decisions "C:\Users\<USER>\Downloads\stage5_review_decisions.json" `
  --package "G:\Capston\Unmochon_Stage4_Evidence_Processing"
```

এটি `content_review_record.json` sidecar তৈরি করবে। Manifest, raw evidence, Stage4 JSON ও model/index বদলায় না। এটিকে Stage6 approved receipt হিসেবে ব্যবহার করা যাবে না।

যদি `BLOCKED` আসে, সেটি bypass করবেন না। Error text দিন। একই review dir-এ দ্বিতীয়বার record overwrite করা যায় না; সংশোধিত review-এর জন্য নতুন আলাদা review run ও manifest তৈরি করতে হবে।

## 5. Remaining gates (not yet implemented in this package)

- Stage5 correction workflow / official source-date applicability review
- Approved chunks থেকে isolated *new* Stage6 ChromaDB+BM25 candidate build
- Cross-index count, manifest/source digest, retrieval regression এবং rollback
- Validated atomic active pointer promotion (separate manual authorization)
- Teammate KG/contradiction adapter: existing port reserved, no implementation here

**Current policy verification remains false regardless of content approvals.**
