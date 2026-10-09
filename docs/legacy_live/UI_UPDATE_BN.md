# Existing folder-এ UI update

এই ZIP একটি update; complete নতুন project নয়। আপনার existing `unmochon-live`
folder, `.venv`, `.env` ও corpus data ব্যবহার করবে। কোনো নতুন Python dependency,
Node.js server, React build, Flask server বা environment প্রয়োজন নেই।

1. চালু server থাকলে terminal-এ Ctrl+C দিয়ে বন্ধ করুন।
2. ZIP extract করুন। ভেতরের `unmochon-live` folder থেকে `src`, `docs`, `tests`
   এবং `pyproject.toml` আপনার existing `G:\Capston\unmochon-live` folder-এ
   copy করুন। Same-name code files replace করুন। Folder-এর ভেতরে আরেকটি
   `unmochon-live` nested folder বানাবেন না। Existing folder delete করবেন না।
3. ZIP-এ `.env`, `.venv` বা `data` নেই। আপনার settings/corpus অক্ষত থাকবে।
4. Existing project folder-এ PowerShell খুলে চালান:

```powershell
.\.venv\Scripts\python.exe -m unmochon_live serve
```

5. Browser-এ **http://127.0.0.1:8000** খুলুন। `/docs` নয়। প্রশ্ন লিখে Search চাপুন।
   Server চলার সময় ওই terminal খোলা রাখুন।

আপনার আগের setup editable install (`pip install -e .`) ব্যবহার করে, তাই নতুন
code files সরাসরি লোড হবে। নতুন venv বা dependency reinstall দরকার নেই।
যদি package আগে editable install করা না থাকে, existing venv ব্যবহার করে শুধু:
```powershell
.\.venv\Scripts\python.exe -m pip install --no-deps --no-build-isolation -e .
```

পুরোনো Flask UI-এর `app.py` এই folder-এ চালাবেন না; adapted HTML/CSS/JS এখন
FastAPI server থেকে serve হয়। পুরোনো Flask app ও নতুন agent পাশাপাশি চালানোর দরকার নেই।

Home এবং results shell আপনার দেওয়া UI.zip থেকে এসেছে। Logo ও palette reuse
করা হয়েছে, বাংলা font bundle করা হয়েছে। Result cards এখন real orchestration
response দেখায়; old confidence/contradiction logic frontend-এ বানিয়ে বসানো হয়নি।
Existing teammate HTTP adapter অপরিবর্তিত। Raw PDF/PDF.js highlighting এই patch-এ
সংযুক্ত নয়; বর্তমানে source URL ও document/page দেখায়। PDF files এবং full
retrieval module পাওয়া গেলে সেগুলো contract অনুযায়ী যুক্ত করতে হবে।

Live source retrieval-এর আগের network/JS/PDF limitations একই আছে। UI যুক্ত
হওয়া মানেই NID/Passport-এর তথ্য যাচাই সফল হয়েছে, এমন নয়।
