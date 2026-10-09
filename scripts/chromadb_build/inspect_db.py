"""Look inside the ChromaDB build - counts, breakdowns, sample records."""
import chromadb
from collections import Counter

from scripts.chromadb_build import config

client = chromadb.PersistentClient(path=config.CHROMADB_DIR)
collection = client.get_collection(config.COLLECTION_NAME)

print(f"Collection: {config.COLLECTION_NAME}")
print(f"Total items: {collection.count()}\n")

# Pull all metadata (no embeddings, keeps it fast)
data = collection.get(include=["metadatas"])
metas = data["metadatas"]

# Breakdown by ministry
print("By ministry:")
for name, n in Counter(m["ministry"] for m in metas).most_common():
    print(f"  {name}: {n}")

# Breakdown by source type
print("\nBy source:")
print(f"  regular clauses: {sum(1 for m in metas if not m['is_table'] and not m['from_review'])}")
print(f"  tables:          {sum(1 for m in metas if m['is_table'])}")
print(f"  from review:     {sum(1 for m in metas if m['from_review'])}")

# How many have bbox - this matters for PDF.js highlighting
with_bbox = sum(1 for m in metas if m["bbox"])
print(f"\nWith bbox: {with_bbox} / {len(metas)} ({with_bbox/len(metas)*100:.1f}%)")

# How many have source_url - defense panel requirement
with_url = sum(1 for m in metas if m["source_url"])
print(f"With source_url: {with_url} / {len(metas)} ({with_url/len(metas)*100:.1f}%)")

# Show 3 sample records
print("\n" + "=" * 60)
print("Sample records")
print("=" * 60)
sample = collection.get(limit=3, include=["documents", "metadatas"])
for i in range(len(sample["ids"])):
    m = sample["metadatas"][i]
    print(f"\nid: {sample['ids'][i]}")
    print(f"  ministry: {m['ministry']} | doc: {m['doc_id']} | page {m['page_number']}")
    print(f"  quality: {m['quality_score']:.2f} | bbox: {m['bbox'][:40]}")
    print(f"  text: {sample['documents'][i][:150]}")