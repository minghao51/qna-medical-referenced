from src.ingestion.steps.chunking.core import TextChunker
from src.ingestion.steps.chunking.helpers import group_list_items, split_list_items, split_table_rows


def test_split_list_items_preserves_continuation_lines():
    text = "- First item\n  continuation detail\n- Second item\n- Third item"

    items = split_list_items(text)

    assert items == [
        "- First item\n  continuation detail",
        "- Second item",
        "- Third item",
    ]


def test_group_list_items_keeps_whole_bullets():
    items = ["- Alpha", "- Beta with detail", "- Gamma"]

    groups = group_list_items(items, max_chars=18)

    assert groups == ["- Alpha", "- Beta with detail", "- Gamma"]


def test_split_table_rows_repeats_header_for_split_groups():
    header = "Drug | Dose | Notes"
    rows = [f"Drug {idx} | {idx} mg | {'x' * 30}" for idx in range(1, 6)]

    groups = split_table_rows("\n".join([header, *rows]), max_chars=90, repeat_header=True)

    assert len(groups) > 1
    assert all(str(group["text"]).splitlines()[0] == header for group in groups)
    assert all(group["header_repeated"] is True for group in groups)


def test_text_chunker_splits_large_list_on_item_boundaries():
    chunker = TextChunker(chunk_size=120, chunk_overlap=10)
    long_item = "detail " * 40
    docs = [
        {
            "id": "doc1",
            "source": "guide.pdf",
            "pages": [
                {
                    "page": 1,
                    "structured_blocks": [
                        {
                            "id": "h1",
                            "block_type": "heading",
                            "text": "Treatment",
                            "section_path": ["Treatment"],
                            "metadata": {"page": 1},
                        },
                        {
                            "id": "l1",
                            "block_type": "list",
                            "text": "\n".join(
                                [f"- Item {idx}: {long_item}" for idx in range(1, 5)]
                            ),
                            "section_path": ["Treatment"],
                            "metadata": {"page": 1},
                        },
                    ],
                }
            ],
        }
    ]

    chunks = chunker.chunk_documents(docs)

    assert len(chunks) > 1
    assert all(chunk["content_type"] == "list" for chunk in chunks)
    assert all(chunk["section_path"] == ["Treatment"] for chunk in chunks)
    assert all(chunk["content"].splitlines()[0].startswith("- ") for chunk in chunks)
    assert all(
        line.startswith("- ") or not line.strip()
        for chunk in chunks
        for line in chunk["content"].splitlines()
    )


def test_text_chunker_repeats_table_header_when_splitting_large_table():
    chunker = TextChunker(chunk_size=120, chunk_overlap=10)
    header = "Medication | Dose | Indication"
    row_payload = " ".join(["cholesterol"] * 20)
    docs = [
        {
            "id": "doc2",
            "source": "guide.pdf",
            "pages": [
                {
                    "page": 2,
                    "structured_blocks": [
                        {
                            "id": "h2",
                            "block_type": "heading",
                            "text": "Medication table",
                            "section_path": ["Medication table"],
                            "metadata": {"page": 2},
                        },
                        {
                            "id": "t1",
                            "block_type": "table",
                            "text": "\n".join(
                                [header]
                                + [
                                    f"Drug {idx} | {idx} mg | {row_payload}"
                                    for idx in range(1, 8)
                                ]
                            ),
                            "section_path": ["Medication table"],
                            "metadata": {"page": 2},
                        },
                    ],
                }
            ],
        }
    ]

    chunks = chunker.chunk_documents(docs)

    assert len(chunks) > 1
    assert all(chunk["content_type"] == "table" for chunk in chunks)
    assert all(chunk["content"].splitlines()[0] == header for chunk in chunks)
    assert all(chunk["section_path"] == ["Medication table"] for chunk in chunks)


def test_text_chunker_keeps_section_boundaries_between_headings():
    chunker = TextChunker(chunk_size=200, chunk_overlap=20)
    docs = [
        {
            "id": "doc3",
            "source": "guide.pdf",
            "pages": [
                {
                    "page": 1,
                    "structured_blocks": [
                        {
                            "id": "h1",
                            "block_type": "heading",
                            "text": "Hypertension",
                            "section_path": ["Hypertension"],
                            "metadata": {"page": 1},
                        },
                        {
                            "id": "p1",
                            "block_type": "paragraph",
                            "text": "Treat blood pressure to reduce stroke risk.",
                            "section_path": ["Hypertension"],
                            "metadata": {"page": 1},
                        },
                        {
                            "id": "h2",
                            "block_type": "heading",
                            "text": "Diabetes",
                            "section_path": ["Diabetes"],
                            "metadata": {"page": 1},
                        },
                        {
                            "id": "p2",
                            "block_type": "paragraph",
                            "text": "Use HbA1c to monitor longer-term control.",
                            "section_path": ["Diabetes"],
                            "metadata": {"page": 1},
                        },
                    ],
                }
            ],
        }
    ]

    chunks = chunker.chunk_documents(docs)

    assert [chunk["section_path"] for chunk in chunks] == [["Hypertension"], ["Diabetes"]]
    assert chunks[0]["next_chunk_id"] == chunks[1]["id"]
    assert chunks[1]["previous_chunk_id"] == chunks[0]["id"]
