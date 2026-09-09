"""Generate the chunking regression golden fixture against current code.

Run: uv run python tests/fixtures/gen_chunking_golden.py
Regenerating rewrites tests/fixtures/chunking_regression_golden.json — only do
this when chunk outputs are INTENTIONALLY changed.
"""

from __future__ import annotations

import json
from pathlib import Path

GOLDEN_PATH = Path(__file__).resolve().parent / "chunking_regression_golden.json"

PLAIN_TEXT = (
    "Patient presents with hypertension and type 2 diabetes. "
    "Metformin 500 mg twice daily is prescribed for glycemic control. "
    "Lisinopril 10 mg daily targets blood pressure. "
    "Monitor creatinine and potassium every three months. "
    "Report dizziness or persistent cough immediately. "
) * 8

MARKDOWN_DOC = (
    "# Hypertension Guideline\n"
    "Alpha recommendation text about blood pressure targets and monitoring. "
    + "Beta detail sentence. "
    * 12
    + "\n\n## Diabetes Management\n"
    "Gamma recommendation text about HbA1c targets. "
    + "Delta detail sentence. " * 10
    + "\n\n### Monitoring\n"
    + "Epsilon follow-up detail. " * 8
    + "\n"
)

STRUCTURED_DOC = {
    "id": "doc_struct",
    "source": "clinic.pdf",
    "pages": [
        {
            "page": 1,
            "structured_blocks": [
                {
                    "id": "h1",
                    "block_type": "heading",
                    "text": "Medication Plan",
                    "section_path": ["Medication Plan"],
                    "metadata": {"page": 1},
                },
                {
                    "id": "p1",
                    "block_type": "paragraph",
                    "text": "Short intro paragraph about the plan.",
                    "section_path": ["Medication Plan"],
                    "metadata": {"page": 1},
                },
                {
                    "id": "l1",
                    "block_type": "list",
                    "text": "\n".join(f"- Item {idx}: " + "detail " * 30 for idx in range(1, 5)),
                    "section_path": ["Medication Plan"],
                    "metadata": {"page": 1},
                },
                {
                    "id": "t1",
                    "block_type": "table",
                    "text": "\n".join(
                        ["Medication | Dose | Indication"]
                        + [f"Drug {idx} | {idx} mg | " + "note " * 12 for idx in range(1, 7)]
                    ),
                    "section_path": ["Medication Plan"],
                    "metadata": {"page": 1},
                },
            ],
        }
    ],
    "metadata": {"logical_name": "clinic-notes", "source_type": "pdf"},
}

PLAIN_DOC = {
    "id": "doc_plain",
    "source": "handbook.pdf",
    "content": PLAIN_TEXT,
    "metadata": {"logical_name": "handbook"},
}

MULTI_SOURCE_DOCS = [
    {
        "id": "d_pdf",
        "source": "a.pdf",
        "content": "Pdf source sentence about care. " * 40,
    },
    {
        "id": "d_md",
        "source": "b.md",
        "content": "# Md Title\n" + "Markdown sentence about care. " * 40,
    },
    {
        "id": "d_html",
        "source": "c.html",
        "content": "Html sentence about care. " * 40,
    },
    {
        "id": "d_other",
        "source": "d.txt",
        "content": "Other sentence about care. " * 40,
    },
]

PER_SOURCE_CONFIGS = {
    "pdf": {"chunk_size": 150, "chunk_overlap": 16, "min_chunk_size": 30},
    "markdown": {"chunk_size": 180, "chunk_overlap": 20, "strategy": "recursive"},
    "html": {"chunk_size": 512, "chunk_overlap": 64, "min_chunk_size": 60},
    "default": {"chunk_size": 130, "chunk_overlap": 16, "min_chunk_size": 30},
}


def _deterministic_embed(texts, batch_size=10, model=None, **kwargs):
    import numpy as np

    out = []
    for text in texts:
        seed = sum(ord(ch) for ch in text) % (2**32)
        rng = np.random.default_rng(seed)
        out.append(rng.standard_normal(768).tolist())
    return out


def build_cases() -> dict:
    from src.ingestion.steps.chunking.core import TextChunker

    cases: dict = {}

    chunker = TextChunker(chunk_size=120, chunk_overlap=24, min_chunk_size=30)
    cases["plain_text_recursive"] = chunker.chunk_text(PLAIN_TEXT, "guide.pdf", "doc1", 2)

    cases["structured_blocks"] = TextChunker(chunk_size=512, chunk_overlap=64).chunk_documents(
        [STRUCTURED_DOC]
    )

    cases["markdown_document"] = TextChunker(chunk_size=160, chunk_overlap=20).chunk_documents(
        [{"id": "md1", "source": "doc.md", "content": MARKDOWN_DOC}]
    )

    cases["plain_doc_default_configs"] = TextChunker(
        chunk_size=512, chunk_overlap=64
    ).chunk_documents([PLAIN_DOC])

    base = TextChunker(chunk_size=512, chunk_overlap=64, min_chunk_size=100)
    cases["multi_source_per_doc_configs"] = base.chunk_documents_with_configs(
        MULTI_SOURCE_DOCS, source_chunk_configs=PER_SOURCE_CONFIGS
    )

    # Chonkie strategies: content-level projection (schema is normalized separately
    # in test_chunking_regression.py; token_count_estimate is recomputed after
    # overlap enrichment, so only its un-overlapped behavior is locked here).
    try:
        import src.ingestion.steps.chunking.qwen_embedding_wrapper as qw

        original = qw.embed_texts
        qw.embed_texts = _deterministic_embed
        try:
            from src.ingestion.steps.chunking.chonkie_adapter import ChonkieChunkerAdapter

            adapter = ChonkieChunkerAdapter(
                strategy="chonkie_recursive", chunk_size=150, chunk_overlap=10
            )
            chunks = adapter.chunk_text(PLAIN_TEXT, "guide.pdf", "doc1", 1)
            cases["chonkie_recursive"] = _content_projection(chunks)

            adapter = ChonkieChunkerAdapter(
                strategy="chonkie_semantic", chunk_size=150, chunk_overlap=10
            )
            chunks = adapter.chunk_text(PLAIN_TEXT, "guide.pdf", "doc1", 1)
            cases["chonkie_semantic"] = _content_projection(chunks, lock_token_count=False)
        finally:
            qw.embed_texts = original
    except ImportError:
        pass

    return cases


_CONTENT_FIELDS = ("id", "source", "page", "chunk_index", "content", "char_count")


def _content_projection(chunks: list[dict], *, lock_token_count: bool = True) -> list[dict]:
    fields = list(_CONTENT_FIELDS)
    if lock_token_count:
        fields.append("token_count_estimate")
    return [{field: chunk[field] for field in fields} for chunk in chunks]


def main() -> None:
    cases = build_cases()
    GOLDEN_PATH.write_text(json.dumps(cases, indent=2, sort_keys=False) + "\n")
    print(f"wrote {GOLDEN_PATH}")
    for name, chunks in cases.items():
        print(f"  {name}: {len(chunks)} chunks")


if __name__ == "__main__":
    main()
