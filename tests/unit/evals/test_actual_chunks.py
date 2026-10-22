from __future__ import annotations

from src.evals.checks.l3_chunking import assess_l3_chunking_quality


def test_l3_without_actual_chunks_is_incomplete_and_does_not_reconstruct():
    result = assess_l3_chunking_quality(chunk_size=400, chunk_overlap=50)

    aggregate = result["aggregate"]
    assert aggregate["measurement_status"] == "incomplete"
    assert aggregate["measurement_reason"] == "actual_emitted_chunks_not_supplied"
    assert aggregate["chunk_count"] is None
    assert aggregate["chunk_length_mean"] is None
    assert aggregate["chunk_size_config"] == 400
    assert aggregate["chunk_overlap_config"] == 50
    assert result["records"] == []


def test_l3_measures_supplied_html_pdf_and_reference_chunks():
    emitted_chunks = [
        {
            "id": "html-1",
            "source": "page.html",
            "page": None,
            "content": "first emitted html chunk",
            "section_path": ["Heading"],
        },
        {
            "id": "pdf-1",
            "source": "guide.pdf",
            "page": 4,
            "content": "emitted pdf row",
            "content_type": "table",
        },
        {
            "id": "ref-1",
            "source": "reference_ranges.csv",
            "content": "reference emitted chunk",
        },
        {
            "id": "pdf-duplicate",
            "source": "guide.pdf",
            "page": 4,
            "content": "emitted pdf row",
            "content_type": "table",
        },
    ]

    result = assess_l3_chunking_quality(
        chunk_size=400,
        chunk_overlap=50,
        chunks=emitted_chunks,
        document_count=3,
    )

    aggregate = result["aggregate"]
    assert aggregate["measurement_status"] == "measured"
    assert aggregate["document_count"] == 3
    assert aggregate["chunk_size_config"] == 400
    assert aggregate["chunk_overlap_config"] == 50
    assert aggregate["chunk_count"] == len(emitted_chunks)
    assert aggregate["duplicate_chunk_rate"] == 0.25
    assert aggregate["table_row_split_violations"] == 2
    assert {record["id"] for record in result["records"]} == {
        "html-1",
        "pdf-1",
        "ref-1",
        "pdf-duplicate",
    }


def test_l3_unknown_overlap_does_not_apply_a_fabricated_default():
    result = assess_l3_chunking_quality(
        chunks=[
            {"id": "first", "source": "same.pdf", "content": "A" + "x" * 180},
            {"id": "second", "source": "same.pdf", "content": "x" * 180 + "B"},
        ]
    )

    assert result["aggregate"]["chunk_size_config"] is None
    assert result["aggregate"]["chunk_overlap_config"] is None
    assert result["aggregate"]["observed_overlap_mean"] == 180.0


def test_l3_explicit_empty_chunks_are_measured_without_fake_ratios():
    result = assess_l3_chunking_quality(chunks=[], document_count=0)

    assert result["aggregate"]["measurement_status"] == "measured"
    assert result["aggregate"]["chunk_count"] == 0
    assert result["aggregate"]["duplicate_chunk_rate"] is None
    assert result["aggregate"]["boundary_cut_rate"] is None
