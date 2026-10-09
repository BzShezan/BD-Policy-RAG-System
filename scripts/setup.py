"""Idempotent first-run setup; never overwrite .env or any existing corpus."""
from pathlib import Path
import secrets
import sys
root=Path(__file__).resolve().parents[1]
if not ((3,11) <= sys.version_info[:2] < (3,13)):
    raise SystemExit("Use Python 3.11 or 3.12 for original model compatibility.")
env=root/".env"
if not env.exists():
    content=(root/".env.example").read_text(encoding="utf-8")
    content=content.replace("\nAPI_KEY=\n", "\nAPI_KEY="+secrets.token_urlsafe(32)+"\n")
    env.write_text(content,encoding="utf-8")
    try:env.chmod(0o600)
    except OSError:pass
    print("Created .env with an API key; existing settings will be preserved on future runs.")
else:print("Keeping your existing .env.")
print("Project root:",root)
required=("data/chromedb/chroma.sqlite3", "data/bm25_index.pkl", "data/doc_metadata.json")
missing=[name for name in required if not (root/name).exists()]
if missing:
    print("Source-only checkout: add your private original data before serving.")
    print("Expected local assets:", ", ".join(missing))
    print("Alternatively set the original data paths in .env; doctor checks those configured paths.")
print("Next: python -m unmochon_live doctor")
