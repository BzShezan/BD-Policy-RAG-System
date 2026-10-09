"""Where are the undated items? Split by ministry and source type."""

from collections import Counter

import chromadb

from DATE_eXTRACTION import config

client = chromadb.PersistentClient(path=config.CHROMADB_DIR)
col = client.get_collection(config.COLLECTION_NAME)

total = col.count()
metas = []
offset = 0

while offset < total:
    got = col.get(limit=2000, offset=offset, include=["metadatas"])
    if not got["ids"]:
        break
    metas.extend(got["metadatas"])
    offset += 2000

undated = [m for m in metas if not m.get("circular_date")]

print(f"total items:  {len(metas)}")
print(f"undated:      {len(undated)} ({len(undated)/len(metas)*100:.1f}%)\n")

print("undated by ministry:")
for k, v in Counter(m.get("ministry", "") for m in undated).most_common():
    print(f"  {k}: {v}")

print("\nundated by type:")
print(f"  tables:  {sum(1 for m in undated if m.get('is_table'))}")
print(f"  clauses: {sum(1 for m in undated if not m.get('is_table'))}")

print("\ndated by ministry:")
dated = [m for m in metas if m.get("circular_date")]
for k, v in Counter(m.get("ministry", "") for m in dated).most_common():
    print(f"  {k}: {v}")