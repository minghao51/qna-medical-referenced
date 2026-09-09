"""One-time migration: JSON vector store → ChromaDB.

Run this script once to import existing data from the old JSON-backed
vector store into ChromaDB. After migration, the application will use
ChromaDB directly.

Usage:
    python -m src.ingestion.indexing.migrate --collection medical_docs

After running, verify the migration succeeded, then delete the old JSON file:
    rm data/vectors/medical_docs.json
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, cast

import chromadb
from chromadb.config import Settings as ChromaSettings

from src.config import settings
from src.ingestion.indexing.text_utils import content_hash

MetadataValue = str | int | float | bool | list[str] | list[int] | list[float] | list[bool]
MetadataMap = dict[str, MetadataValue]


def migrate(
    collection_name: str,
    vector_dir: str = "data/vectors",
    chroma_dir: str | None = None,
) -> dict:
    """Migrate JSON vector store data to ChromaDB.

    Args:
        collection_name: Name of the collection (used for both JSON file and ChromaDB).
        vector_dir: Directory containing the old JSON vector file.
        chroma_dir: ChromaDB persist directory. Defaults to settings.chroma_persist_directory.

    Returns:
        Migration report with counts.
    """
    chroma_dir = chroma_dir or settings.storage.chroma_persist_directory
    json_file = Path(vector_dir) / f"{collection_name}.json"

    if not json_file.exists():
        print(f"[ERROR] JSON file not found: {json_file}", file=sys.stderr)
        print("Nothing to migrate. Aborting.", file=sys.stderr)
        sys.exit(1)

    with open(json_file, encoding="utf-8") as f:
        data = json.load(f)

    ids = data.get("ids", [])
    embeddings = data.get("embeddings", [])
    documents = data.get("documents", data.get("contents", []))
    metadatas = data.get("metadatas", [])

    if not ids:
        print("[WARN] JSON file is empty. Nothing to migrate.")
        return {"attempted": 0, "inserted": 0}

    if len(embeddings) != len(ids) or len(documents) != len(ids):
        print(f"[ERROR] Corrupt JSON snapshot {json_file}: array length mismatch.", file=sys.stderr)
        print(
            f"    ids: {len(ids)}, embeddings: {len(embeddings)}, documents: {len(documents)}",
            file=sys.stderr,
        )
        print("    Aborting. Re-export the snapshot from the legacy store.", file=sys.stderr)
        sys.exit(1)

    client = chromadb.PersistentClient(
        path=str(chroma_dir),
        settings=ChromaSettings(allow_reset=True),
    )

    collection = client.get_or_create_collection(name=collection_name, embedding_function=None)
    existing_count = collection.count()

    if existing_count > 0:
        print(
            f"[ERROR] ChromaDB collection '{collection_name}' already has {existing_count} documents.",
            file=sys.stderr,
        )
        print(
            "Aborting to prevent double-migration. Drop the collection first if you want to re-migrate.",
            file=sys.stderr,
        )
        sys.exit(1)

    to_insert_ids = []
    to_insert_embeddings = []
    to_insert_documents = []
    to_insert_metadatas: list[MetadataMap] = []

    for i, doc_id in enumerate(ids):
        raw_meta = dict(metadatas[i]) if i < len(metadatas) else {}
        # Mirror ChromaVectorStore.add_documents (chroma_store.py) so migrated
        # metadata round-trips identically to pipeline-written metadata:
        # keep scalars AND non-empty lists (section_path, hypothetical_questions,
        # extracted_keywords, ...) — ChromaDB stores lists natively and
        # chroma_store reads them back as lists (no JSON string encoding).
        # Drop None values (Collection.add rejects them, unlike upsert) and
        # empty lists (ChromaDB rejects those, add_documents drops them too).
        meta: MetadataMap = {}
        for k, v in raw_meta.items():
            if v is None:
                continue
            if isinstance(v, list) and len(v) == 0:
                continue
            meta[str(k)] = v
        # The JSON "content_hashes" array is a sorted set, NOT aligned with
        # ids, so never index it positionally. Recompute from the stored
        # (already sanitized) text — the exact computation add_documents uses.
        meta["content_hash"] = content_hash(documents[i])

        to_insert_ids.append(doc_id)
        to_insert_embeddings.append(embeddings[i])
        to_insert_documents.append(documents[i])
        to_insert_metadatas.append(meta)

    if to_insert_ids:
        collection.add(
            ids=to_insert_ids,
            embeddings=cast(Any, to_insert_embeddings),
            documents=to_insert_documents,
            metadatas=cast(Any, to_insert_metadatas),
        )

    # Persist index provenance (embedding model, config hash, ...) on the
    # collection, exactly as ChromaVectorStore.set_index_metadata does
    # (collection.modify(metadata=...)); l5_index.py recovers it from the
    # Chroma collection metadata.
    index_metadata = data.get("index_metadata") or {}
    if index_metadata:
        collection.modify(metadata=index_metadata)

    report = {
        "attempted": len(ids),
        "inserted": len(to_insert_ids),
        "json_file": str(json_file),
        "chroma_collection": collection_name,
        "chroma_persist_directory": str(chroma_dir),
    }

    final_count = collection.count()
    print("[OK] Migration complete.")
    print(f"    Attempted:  {report['attempted']}")
    print(f"    Inserted:   {report['inserted']}")
    if index_metadata:
        print(f"    Index metadata: {sorted(index_metadata)}")
    print(f"    ChromaDB count after migration: {final_count}")
    print()
    print(f"    JSON file still at: {json_file}")
    print("    Please verify the migration, then delete the JSON file:")
    print(f"    rm {json_file}")

    return report


def main() -> None:
    parser = argparse.ArgumentParser(description="Migrate JSON vector store to ChromaDB.")
    parser.add_argument(
        "--collection",
        type=str,
        default=None,
        help="Collection name (defaults to settings.storage.collection_name).",
    )
    parser.add_argument(
        "--vector-dir",
        type=str,
        default="data/vectors",
        help="Directory containing the old JSON vector file (default: data/vectors).",
    )
    parser.add_argument(
        "--chroma-dir",
        type=str,
        default=None,
        help="ChromaDB persist directory (default: settings.chroma_persist_directory).",
    )
    args = parser.parse_args()

    collection_name = args.collection or settings.storage.collection_name
    migrate(
        collection_name=collection_name,
        vector_dir=args.vector_dir,
        chroma_dir=args.chroma_dir,
    )


if __name__ == "__main__":
    main()
