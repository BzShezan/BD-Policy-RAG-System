from original_paths import project_path
import json, sys
sys.path.insert(0, project_path('scripts'))
from scripts.ocr_pipeline.quality import is_broken_bengali

path = project_path('data/processed_jsonl/Social_Welfare_clauses.jsonl')

# The six documents we know are corrupted
bad_docs = {
    "SW_RSS_2011_12_Policy_v1",
    "SW_teaWorker_2025_06_Report_v1",
    "SW_MULTI_2023_00_Report_v1",
    "SocialMin_DisAllow_2013_00_Law_v1_Little clear updated",
    "SocialMin_DisAllow_2013_00_Law_v1",
    "SW_MULTI_2025_00_Report_v1",
}

hit = miss = false_alarm = clean_pass = 0
false_samples = []

for line in open(path, encoding='utf-8'):
    if not line.strip():
        continue
    c = json.loads(line)
    text = c.get('text', '')
    flagged = is_broken_bengali(text)
    known_bad = c.get('doc_id', '') in bad_docs

    if known_bad and flagged:
        hit += 1
    elif known_bad:
        miss += 1
    elif flagged:
        false_alarm += 1
        if len(false_samples) < 5:
            false_samples.append((c.get('doc_id', ''), text[:100]))
    else:
        clean_pass += 1

print(f"corrupted, caught:  {hit}")
print(f"corrupted, missed:  {miss}")
print(f"clean, false alarm: {false_alarm}")
print(f"clean, passed:      {clean_pass}")

if false_samples:
    print("\nFalse alarms (check if these are actually clean):")
    for doc, s in false_samples:
        print(f"\n  {doc}")
        print(f"  {s}")