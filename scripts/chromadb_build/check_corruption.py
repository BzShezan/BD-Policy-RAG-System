import chromadb
from scripts.chromadb_build import config

client = chromadb.PersistentClient(path=config.CHROMADB_DIR)
collection = client.get_collection(config.COLLECTION_NAME)

results = collection.get(
    where={"ministry": "Agriculture"},
    limit=10000,
    include=["documents"]
)

found = [d for d in results["documents"] if "৫০৯৪৭৭৭৭৭" in d]
print(f"corrupted sample still present: {len(found) > 0}")
if found:
    print(found[0][:200])