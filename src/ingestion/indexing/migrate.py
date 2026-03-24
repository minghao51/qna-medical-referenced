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

import chromadb
from chromadb.config import Settings as ChromaSettings

project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from src.config import settings  # noqa: E402


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
    chroma_dir = chroma_dir or settings.chroma_persist_directory
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
    content_hashes = data.get("content_hashes", [])

    if not ids:
        print("[WARN] JSON file is empty. Nothing to migrate.")
        return {"attempted": 0, "inserted": 0, "skipped": 0}

    client = chromadb.PersistentClient(
        path=str(chroma_dir),
        settings=ChromaSettings(allow_reset=True),
    )

    existing = client.get_or_create_collection(name=collection_name, embedding_function=None)
    existing_count = existing.count()

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

    collection = client.get_or_create_collection(
        name=collection_name,
        embedding_function=None,
    )

    existing_ids_set = (
        set(existing_ids) if (existing_ids := collection.get(include=[]).get("ids")) else set()
    )

    to_insert_ids = []
    to_insert_embeddings = []
    to_insert_documents = []
    to_insert_metadatas = []

    skipped_duplicate_id = 0
    skipped_duplicate_content = 0

    for i, doc_id in enumerate(ids):
        if doc_id in existing_ids_set:
            skipped_duplicate_id += 1
            continue
        content_hash_val = content_hashes[i] if i < len(content_hashes) else None
        meta = dict(metadatas[i]) if i < len(metadatas) else {}
        if content_hash_val:
            meta["content_hash"] = content_hash_val

        to_insert_ids.append(doc_id)
        to_insert_embeddings.append(embeddings[i] if i < len(embeddings) else [])
        to_insert_documents.append(documents[i] if i < len(documents) else "")
        for k, v in list(meta.items()):
            if isinstance(v, list) and len(v) == 0:
                del meta[k]
            elif isinstance(v, (dict, list)):
                del meta[k]
            elif v is None:
                del meta[k]
        to_insert_metadatas.append(meta)

    if to_insert_ids:
        collection.add(
            ids=to_insert_ids,
            embeddings=to_insert_embeddings,
            documents=to_insert_documents,
            metadatas=to_insert_metadatas,
        )

    report = {
        "attempted": len(ids),
        "inserted": len(to_insert_ids),
        "skipped_duplicate_id": skipped_duplicate_id,
        "skipped_duplicate_content": skipped_duplicate_content,
        "json_file": str(json_file),
        "chroma_collection": collection_name,
        "chroma_persist_directory": str(chroma_dir),
    }

    final_count = collection.count()
    print("[OK] Migration complete.")
    print(f"    Attempted:  {report['attempted']}")
    print(f"    Inserted:   {report['inserted']}")
    print(
        f"    Skipped:    {report['skipped_duplicate_id']} duplicate IDs, "
        f"{report['skipped_duplicate_content']} duplicate content"
    )
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
        help="Collection name (defaults to settings.collection_name).",
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

    collection_name = args.collection or settings.collection_name
    migrate(
        collection_name=collection_name,
        vector_dir=args.vector_dir,
        chroma_dir=args.chroma_dir,
    )


if __name__ == "__main__":
    main()
