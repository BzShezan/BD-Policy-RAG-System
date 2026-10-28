# Windows test failure — ছোট সংশোধন

এই patch আগের `Unmochon_Agentic_Integration_20261019.zip` বসানো project-এর উপর প্রযোজ্য। মূল index বা Stage 1 pipeline rebuild লাগবে না।

## Log-এ কী পাওয়া গেছে

| Error | কারণ | সংশোধন |
|---|---|---|
| প্রথম agentic query-তে `NEEDS_VERIFICATION`; পরের test-এ `offer=None` / `NoneType` | Test fixture-এর query-result JSON বাংলা UTF-8-তে লেখা হলেও কয়েকটি `read_text()` এবং child-output reader Windows-এর locale encoding নিচ্ছিল। CP1252 দিয়ে একই প্রথম failure reproduce হয়েছে। | JSON read/write এবং captured subprocess output-এ explicit UTF-8; child environment-এ UTF-8 output |
| Temporary pointer test-এ `sealed_original`-এর বদলে real generation | Runtime `.env`/shell-এর `STAGE6_WORKSPACE` test-এর temporary `.env` override করছে। এটি configuration precedence; database corruption নয়। | ওই test module-এ environment isolation; real application-এর environment override behaviour অপরিবর্তিত |
| `No module named flask` | Retained original UI test-এর dependency বর্তমান Conda environment-এ নেই | নিচের ছোট pip command |
| `No module named pytesseract` | Original OCR module import-এর dependency নেই | একই pip command; এটি Tesseract executable reinstall করে না |

১৩টি agentic failure অনেকটাই এক শুরুর query failure থেকে তৈরি পরের error। `NoneType` নিজে আলাদা ১৩টি crawler/index সমস্যা প্রমাণ করে না। Log-এ Chroma corruption-এর error নেই। Starlette-এর warning পরীক্ষার failure নয়।

## কী করবেন

Server চললে `Ctrl+C` দিন। ZIP আলাদা folder-এ extract করে সেই folder-এর PowerShell-এ:

```powershell
conda activate unmochon_stage1
python .\install_windows_fix.py --target "G:\Capston\Unmochon"
python .\install_windows_fix.py --target "G:\Capston\Unmochon" --apply
cd "G:\Capston\Unmochon"
python -m pip install "Flask>=3,<4" "pytesseract>=0.3.10,<1"
$env:PYTHONUTF8="1"
$env:PYTHONIOENCODING="utf-8"
python -m pytest -q tests/test_agentic_integration.py tests/test_unmochon_pipeline_entrypoint.py tests/test_original_merge.py -x --tb=short
```

প্রথম installer command dry-run। অপ্রত্যাশিত local code change থাকলে কিছু না লিখে থামবে। দ্বিতীয়টি backup নিয়ে শুধু চারটি code/test file ও এই নির্দেশনা বসায়। `.env`, ChromaDB, BM25, active pointer, raw PDF, model cache, frozen Stage 1–6 code এবং UI theme পরিবর্তন করে না।

আপনার shell থেকে `STAGE6_WORKSPACE` মুছে দিতে হবে না। Test isolation সেটি test-এর মধ্যে সাময়িকভাবে আলাদা রাখবে; application-এর configured workspace আগের মতো থাকবে।

Tests পাস হলে:

```powershell
python scripts/agentic_diagnostic.py
python -m unmochon_live serve
```

তারপর http://127.0.0.1:8000-এ আগে উত্তরযোগ্য একটি প্রশ্ন এবং `How to apply for NID card?` পরীক্ষা করুন। এই test fix live research consent দেয় না এবং কোনো নতুন generation activate করে না।

## Changed files

- `tests/test_agentic_integration.py`: explicit UTF-8 JSON/file/subprocess I/O এবং CP1252 regression test।
- `tests/agentic_fixture_worker.py`: UTF-8 fixture specification reader।
- `tests/test_unmochon_pipeline_entrypoint.py`: temporary-repository tests-এ environment isolation; real environment precedence আলাদা test-এ বজায় আছে।
- `src/unmochon_live/controlled_update.py`: candidate/reopen validation JSON-ও explicit UTF-8-তে পড়া।
- `docs/WINDOWS_COMPATIBILITY_FIX_BN.md`: এই নির্দেশনা।

CP1252 simulation-এ পূর্ণ consent→pair update→re-query workflow এবং inherited-workspace test স্থানীয়ভাবে reproduce করে fix যাচাই করা হয়েছে। পূর্ণ local suite-এর ফল ZIP-এর `TEST_RESULTS.txt`-এ আছে। এটি প্রকৃত Windows machine বা আপনার accepted 14,397-item index/model দিয়ে live validation-এর দাবি নয়; উপরের targeted command দিয়ে সেই পরিবেশে পুনরায় পরীক্ষা করুন।
