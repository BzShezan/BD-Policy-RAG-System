# Windows Stage 4 path fix — 19 October 2026

আপনার নতুন log-এ `sentencepiece` ইনস্টল হয়েছে। এরপর test-এর crawl শেষ হয়ে
Stage 4 JSON লেখার সময় `FileNotFoundError` হয়েছে। ব্যর্থ path ২৬৭ অক্ষরের;
final JSON path ২৩০ অক্ষরের। Windows-এর সাধারণ ২৬০ অক্ষরের path সীমায় long
JSON filename-এর সঙ্গে UUID যোগ করা temporary filename আটকে যাচ্ছিল।

এই patch-এ temporary file একই directory-তে ছোট, exclusive filename দিয়ে
তৈরি হয়। UTF-8 JSON লেখা এবং atomic replacement বজায় থাকে। Evidence-এর
final filename, source hash ও frozen Stage 3–6 code বদলায় না।

## Install

আগের `Unmochon_Agentic_Integration_20261019` এবং `Unmochon_Windows_Fix_20261019`
ইনস্টল করা project-এ এটি দিন। চলমান test/serve বন্ধ করে ZIP extract করুন।
Extracted folder-এর ভেতর `install_windows_path_fix.py` আছে; সেখানে PowerShell খুলুন:

```powershell
conda activate unmochon_stage1
python .\install_windows_path_fix.py --target "G:\Capston\Unmochon" --apply
cd "G:\Capston\Unmochon"
```

Installer আগে code hashes যাচাই করে backup রাখে। `.env`, models এবং existing
database/index বদলায় না। Local code আলাদা হলে `BLOCKED` দেখাবে; force overwrite করবেন না।

## Retest

প্রথমে failed workflow ও path regression test চালান:

```powershell
python -X utf8 -m pytest -q tests/test_stage4_windows_paths.py tests/test_agentic_integration.py::test_full_consented_html_pdf_to_pair_to_original_requery --basetemp="G:\Capston\ut_pathfix_20261019" -x --tb=short
```

দুটি pass হলে আগের targeted suite চালান:

```powershell
python -X utf8 -m pytest -q tests/test_agentic_integration.py tests/test_unmochon_pipeline_entrypoint.py tests/test_original_merge.py --basetemp="G:\Capston\ut_pathfix_suite_20261019" -x --tb=short
```

`--basetemp` folder-টি শুধু এই tests-এর জন্য। Pytest আবার চালালে সেই folder-এর
contents মুছে নতুন temporary data তৈরি করে। তাই `G:\Capston\Unmochon` বা নিজের
কোনো data folder কখনো `--basetemp` হিসেবে দেবেন না।

নতুন failure-এর পুরো message প্রয়োজন হলে একই command-এর `-q` বদলে `-vv` দিন।

## Verification scope

Linux-এ Windows-এর ২৫৯ অক্ষরের usable path সীমা simulate করে পুরোনো code-এর
একই `FileNotFoundError` পুনরুৎপাদন করা হয়েছে। নতুন code সেই test-এ UTF-8 JSON
ঠিকভাবে লেখে এবং temporary file রেখে যায় না। Targeted suite-এর ফল ZIP-এর
`TEST_RESULTS.txt`-এ আছে। Actual Windows এবং আপনার real accepted index এখানে
চালানো হয়নি; উপরের Windows retest সেই যাচাই করবে।
