from pathlib import Path

from src.evals.dataset_builder import build_retrieval_dataset
from src.ingestion.steps.chunk_text import TextChunker
from src.ingestion.steps.convert_html import _compute_global_boilerplate_hashes, _fallback_extract
from src.ingestion.steps.load_pdfs import PDFLoader


def test_nav_heavy_html_classified_as_index_listing():
    html = """
    <html><body>
    <nav>{links}</nav>
    <main><ul>{items}</ul></main>
    </body></html>
    """.format(
        links="".join(f"<a href='/p{i}'>Link {i}</a>" for i in range(20)),
        items="".join(f"<li>Item {i}</li>" for i in range(20)),
    )
    extracted = _fallback_extract(html)

    assert extracted["page_type"] in {"index/listing", "navigation-heavy"}


def test_article_html_preserves_headings_and_lists():
    html = """
    <html><body><main>
    <h1>Blood Pressure</h1>
    <p>Control blood pressure to reduce stroke risk.</p>
    <ul><li>Reduce salt</li><li>Exercise regularly</li></ul>
    </main></body></html>
    """
    extracted = _fallback_extract(html)

    markdown = extracted["markdown"]
    assert "# Blood Pressure" in markdown
    assert "- Reduce salt" in markdown


def test_duplicate_boilerplate_hashes_detected(tmp_path: Path):
    shared = "<p>Privacy policy and cookie preferences</p>"
    for idx in range(3):
        (tmp_path / f"file_{idx}.html").write_text(
            f"<html><body>{shared}<p>Unique {idx}</p></body></html>", encoding="utf-8"
        )

    repeated = _compute_global_boilerplate_hashes(sorted(tmp_path.glob("*.html")))

    assert repeated


def test_chunker_preserves_section_and_neighbor_metadata():
    chunker = TextChunker(chunk_size=80, chunk_overlap=10)
    docs = [
        {
            "id": "pdf1",
            "source": "test.pdf",
            "pages": [
                {
                    "page": 1,
                    "content": "Header\nBullet one\nBullet two",
                    "structured_blocks": [
                        {
                            "id": "b0",
                            "block_type": "heading",
                            "text": "Header",
                            "section_path": ["Header"],
                            "metadata": {"page": 1},
                        },
                        {
                            "id": "b1",
                            "block_type": "list",
                            "text": "- Bullet one\n- Bullet two",
                            "section_path": ["Header"],
                            "metadata": {"page": 1},
                        },
                    ],
                }
            ],
        }
    ]

    chunks = chunker.chunk_documents(docs)

    assert len(chunks) == 1
    assert chunks[0]["section_path"] == ["Header"]
    assert chunks[0]["content_type"] == "list"
    assert "previous_chunk_id" in chunks[0]
    assert "next_chunk_id" in chunks[0]


def test_dataset_builder_filters_split_and_label_confidence(tmp_path: Path):
    dataset_file = tmp_path / "dataset.json"
    dataset_file.write_text(
        """
        {
          "golden_queries": [
            {"query": "Q1", "expected_keywords": ["a"], "expected_sources": ["Lipid"], "label_confidence": "high", "dataset_split": "regression"},
            {"query": "Q2", "expected_keywords": ["b"], "expected_sources": ["Diabetes"], "label_confidence": "low", "dataset_split": "dev"}
          ]
        }
        """,
        encoding="utf-8",
    )

    bundle = build_retrieval_dataset(
        dataset_path=dataset_file,
        enable_llm_generation=False,
        dataset_split="regression",
        min_label_confidence="medium",
    )

    assert bundle["stats"]["filtered_records"] == 1
    assert bundle["dataset"][0]["query"] == "Q1"


def test_pdf_loader_marks_empty_pages_for_ocr(monkeypatch, tmp_path: Path):
    class FakePage:
        def __init__(self, text: str):
            self._text = text

        def extract_text(self):
            return self._text

    class FakeReader:
        def __init__(self, _path: str):
            self.pages = [FakePage("")]

    monkeypatch.setattr("src.ingestion.steps.load_pdfs.PdfReader", FakeReader)
    monkeypatch.setattr(PDFLoader, "_extract_with_pdfplumber", lambda self, path: [""])
    pdf_path = tmp_path / "empty.pdf"
    pdf_path.write_bytes(b"%PDF-1.4\n")

    docs = PDFLoader(tmp_path).load_all_pdfs()

    assert len(docs) == 1
    assert docs[0]["pages"][0]["ocr_required"] is True
