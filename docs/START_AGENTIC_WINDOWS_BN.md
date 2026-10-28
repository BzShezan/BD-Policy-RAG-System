# Windows-এ বসানো এবং সবচেয়ে ছোট বাস্তব পরীক্ষা

বর্তমান Unmochon server-এ `Ctrl+C` দিয়ে থামান। আপনার existing `unmochon_stage1` Conda environment ব্যবহার করুন। এই ZIP একটি integration patch: attached `Unmochon.zip` থেকে থাকা unified project-এর উপর installer সব পরিবর্তন বসায়; আলাদা Stage command হাতে চালাতে হয় না।

## 1. Code install — dry-run, তারপর apply

Integration ZIP আলাদা temporary folder-এ Extract All করুন। সেই folder-এ PowerShell খুলুন:

```powershell
conda activate unmochon_stage1
python .\install_integration.py --target "G:\Capston\Unmochon"
python .\install_integration.py --target "G:\Capston\Unmochon" --apply
cd "G:\Capston\Unmochon"
```

প্রথম command-এ `DRY_RUN_PASS` পেলে দ্বিতীয়টি চালান। কোনো file-এ unexpected local change থাকলে installer সব লেখা বন্ধ করে filename জানাবে; `--force` নেই। নতুন code-এর SHA-ও মেলে। বিদ্যমান code backup হয় `data/integration_backups/agentic_...`-এ। `.env`, active pointer, Chroma/BM25, raw PDF, model এবং আপনার runtime review files installer পরিবর্তন করে না।

## 2. একবার runtime configuration

এই script আপনার বর্তমান `.env`-এর Stage 6 workspace/model-cache path রাখে, বাইরের code paths-এর বদলে unified repo-র bundled code ব্যবহার করে এবং চারটি ছোট hash-verified Stage 2 metadata JSON নিয়ে আসে। Existing complete Stage 6 package-টি তখনও লাগবে শুধু এই একবার metadata migration-এর জন্য।

```powershell
python scripts/configure_agentic.py --apply
python -m pip install -e . --no-deps
python scripts/agentic_diagnostic.py
```

`.env`-ও আগে `data/setup_backups/`-এ backup হয়; existing API keys/অন্য settings রাখা হয় এবং output-এ keys প্রকাশ হয় না। `--apply` বাদ দিলে read-only plan। Script কোনো generation তৈরি/বদল, model download বা crawl করে না।

যদি `.env`-এ পুরোনো paths না থাকে, অথবা metadata missing বলে থামে, কেবল এই একবার explicit paths দিন (আপনার আগের অবস্থানের উদাহরণ):

```powershell
python scripts/configure_agentic.py --workspace "G:\Capston\Unmochon_Stage6_Controlled_Index_Update\stage6_candidate_local" --stage6-assets "G:\Capston\Unmochon_Stage6_Controlled_Index_Update" --model-cache "G:\Capston\Unmochon_Stage1_Data_Prep\model_cache" --apply
```

Diagnostic-এর generation আগে সাধারণত `reviewed_c02a1b74041d`, item count 14397 হবে। সফল research-এর পরে generation/count বদলাতে পারে; আগের generation preserved থাকবে। Hash/metadata error হলে fresh empty database বানাবেন না। চারটি reviewed JSON-ও না থাকলে ওই specific missing filename-ই blocker; পুরো database/model upload দরকার নেই।

Python 3.11/3.12 এবং আপনার existing model stack ব্যবহার করুন। `--no-deps` নতুন করে Torch/Transformers upgrade করে না। প্রয়োজনীয় module সত্যিই অনুপস্থিত হলেই শুধু সংশ্লিষ্ট command দিন:

```powershell
# যদি pytest না থাকে:
python -m pip install "pytest>=8,<10"
# যদি Stage 4 PDF processing-এ PyMuPDF missing বলে:
python -m pip install "PyMuPDF==1.26.6"
```

Scanned PDF OCR-এর জন্য existing Tesseract executable এবং hash-manifest-সহ `ben.traineddata`/`eng.traineddata` লাগবে। পূর্বের Stage 4 models folder পাওয়া গেলে setup তার path রাখে। অন্য অবস্থানে থাকলে `.env`-এ `STAGE4_TESSERACT` ও `STAGE4_OCR_MODELS` দিন। Model না পেলে OCR review/error হবে; text verified বলে index হবে না।

## 3. Offline tests এবং server

```powershell
python -m pytest -q
python -m unmochon_live serve
```

অথবা বিদ্যমান unified entrypoint: `python scripts/unmochon_pipeline.py test` / `serve`। Tests-এর synthetic vectors বা HTTP fixtures production-এ ব্যবহৃত হয় না। Missing original corpus/captured snapshots/binary assets-এর test স্পষ্ট skip হয়; সেটি pass দাবি নয়। আপনার original logos/fonts এবং raw PDFs আগের অবস্থানেই রাখুন—code-only source archive-এ এগুলো ছিল না।

Open: http://127.0.0.1:8000

## 4. তিনটি UI পরীক্ষা

1. একটি আগে উত্তরযোগ্য বাংলা policy query দিন। পুরোনো verified evidence ও source দেখা উচিত; অনুমতি ছাড়াই crawl হবে না।
2. `How to apply for NID card?` দিন। Existing evidence যথেষ্ট না হলে Election Commission/NID-এর exact hosts-সহ permission দেখাবে। Disclosure পড়ে checkbox দিয়ে অনুমতি দিন। Progress শেষে যাচাই-পাস করলে নতুন pair activate হয়ে একই প্রশ্নের source-backed উত্তর আসবে। অস্পষ্ট date/OCR/context হলে একই UI-তে review করুন; source না মিললে reject/correction দিন। কোনো verified evidence না মিললে failure/review হবে—উত্তর বা update সফল বলা হবে না।
3. আরেকটি নতুন research offer-এ cancel/deny করুন। সেই job-এর crawler/update শুরু হবে না। চলমান job-ও cancel button দিয়ে বন্ধ করতে পারবেন।

Live test শেষে read-only confirmation:

```powershell
python scripts/agentic_diagnostic.py --query "How to apply for NID card?"
```

এই command নিজে research অনুমোদন করে না। নতুন active generation-এ উত্তর থাকলে offline query থেকেই পাওয়া উচিত। `index_writes: 0` এই diagnostic command-এর আচরণ; আগে UI থেকে করা update-এর item count/generation আলাদাভাবে দেখাবে।

## Code restore ও knowledge rollback

Code restore-এর আগে server থামান। Installer output-এর exact backup path দিন:

```powershell
python .\install_integration.py --target "G:\Capston\Unmochon" --restore "G:\Capston\Unmochon\data\integration_backups\agentic_YOUR_BACKUP"
python .\install_integration.py --target "G:\Capston\Unmochon" --restore "G:\Capston\Unmochon\data\integration_backups\agentic_YOUR_BACKUP" --apply
```

এটি code restore; database rollback নয়। Application re-query failure-এ automatic paired rollback আছে। আলাদা manual paired rollback দরকার হলে, server থামিয়ে নিচের explicit paired rollback command ব্যবহার করুন:

```powershell
python scripts/agentic_diagnostic.py --rollback
```

এটি `.env`-এ configured workspace-এর previous complete pair ফেরায়; active pointer বদলায়। Accepted generation folder নিজে edit/delete করবেন না।
