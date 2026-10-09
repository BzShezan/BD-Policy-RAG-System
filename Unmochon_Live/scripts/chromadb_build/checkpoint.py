"""Resume support for the ChromaDB build.

Encoding 12k clauses takes a long time. Without this, any crash or
shutdown meant starting from zero, because the build deleted and
recreated the collection on every run.

This keeps whatever is already indexed and works out what is still
missing, so a re-run picks up where it stopped.
"""

import chromadb

from scripts.chromadb_build import config


def get_device():
    """Use the GPU if there is one. CPU encoding on this corpus takes
    hours instead of minutes, so this is worth checking."""
    try:
        import torch
        if torch.cuda.is_available():
            return "cuda"
    except ImportError:
        pass
    return "cpu"


def open_collection(client, fresh=False):
    """Open the collection, wiping it first only if asked to."""
    if fresh:
        try:
            client.delete_collection(config.COLLECTION_NAME)
            print("  removed old collection")
        except Exception:
            pass
        return client.create_collection(
            name=config.COLLECTION_NAME,
            metadata={"hnsw:space": "cosine"},
        )

    return client.get_or_create_collection(
        name=config.COLLECTION_NAME,
        metadata={"hnsw:space": "cosine"},
    )


def already_indexed(collection, page=5000):
    """Return the set of ids already in the collection.

    Read in pages rather than all at once - pulling 12k ids in a single
    call is what crashed the inspect script earlier.
    """
    total = collection.count()
    if not total:
        return set()

    print(f"  {total} items already in collection, reading ids ...")
    ids = set()
    offset = 0
    while offset < total:
        got = collection.get(limit=page, offset=offset, include=[])
        if not got["ids"]:
            break
        ids.update(got["ids"])
        offset += page
    return ids


def filter_remaining(items, done_ids):
    """Drop the items that are already indexed."""
    remaining = [x for x in items if x[0] not in done_ids]
    print(f"  {len(done_ids)} done, {len(remaining)} left to add")
    return remaining