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


def test_chunker_preserves_ingestion_source_metadata():
    chunker = TextChunker(chunk_size=80, chunk_overlap=10)
    docs = [
        {
            "id": "md1",
            "source": "guide.md",
            "content": "Cholesterol guidance content",
            "metadata": {
                "logical_name": "Cholesterol guide",
                "source_url": "https://example.org/guide",
                "source_type": "html",
                "source_class": "guideline_html",
                "page_type": "article",
                "canonical_label": "Cholesterol guide",
                "domain": "example.org",
                "domain_type": "organization",
            },
        }
    ]

    chunks = chunker.chunk_documents(docs)

    assert len(chunks) == 1
    assert chunks[0]["metadata"]["logical_name"] == "Cholesterol guide"
    assert chunks[0]["metadata"]["source_url"] == "https://example.org/guide"
    assert chunks[0]["metadata"]["source_type"] == "html"
    assert chunks[0]["metadata"]["source_class"] == "guideline_html"
    assert chunks[0]["metadata"]["canonical_label"] == "Cholesterol guide"
    assert chunks[0]["metadata"]["domain_type"] == "organization"


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


def test_markdown_link_rewrite_preserves_balanced_parens():
    from src.ingestion.steps.convert_html import _rewrite_markdown_links

    # Only the single unbalanced ')' closing the link is consumed; the URL's
    # own balanced parens survive (the old rstrip(")") mangled this).
    line = "[Wiki](https://en.wikipedia.org/wiki/Diabetes_(disambiguation)) trailing)"
    assert _rewrite_markdown_links(line) == (
        "[Wiki](https://en.wikipedia.org/wiki/Diabetes_(disambiguation)) trailing)"
    )


def test_markdown_link_rewrite_strips_tracking_from_all_links_on_line():
    from src.ingestion.steps.convert_html import _rewrite_markdown_links

    line = "see [one](https://a.com/p?utm_source=x) and [two](https://b.com/q?utm_campaign=y)"
    assert _rewrite_markdown_links(line) == "see [one](https://a.com/p) and [two](https://b.com/q)"


def test_markdown_link_rewrite_leaves_ordinary_text_alone():
    from src.ingestion.steps.convert_html import _rewrite_markdown_links

    plain = "No links (just parens) here."
    assert _rewrite_markdown_links(plain) == plain


def test_convert_main_skips_boilerplate_hashes_when_nothing_to_convert(monkeypatch, tmp_path: Path):
    from src.ingestion.steps import convert_html

    (tmp_path / "page.html").write_text(
        "<html><body><h1>T</h1><p>Body text here.</p></body></html>", encoding="utf-8"
    )
    (tmp_path / "page.md").write_text("# T\n", encoding="utf-8")
    monkeypatch.setattr(convert_html, "DATA_DIR", tmp_path)
    monkeypatch.setattr(
        convert_html,
        "get_html_files",
        lambda: sorted(tmp_path.glob("*.html")),
    )

    def boom(paths):
        raise AssertionError("boilerplate hashes must not be computed when all .md exist")

    monkeypatch.setattr(convert_html, "_compute_global_boilerplate_hashes", boom)

    convert_html.main(force=False)  # must not raise; single-source skip accounting


def test_convert_main_computes_hashes_only_when_conversion_needed(monkeypatch, tmp_path: Path):
    from src.ingestion.steps import convert_html

    (tmp_path / "page.html").write_text(
        "<html><body><h1>T</h1><p>Body text here.</p></body></html>", encoding="utf-8"
    )
    monkeypatch.setattr(convert_html, "DATA_DIR", tmp_path)
    monkeypatch.setattr(
        convert_html,
        "get_html_files",
        lambda: sorted(tmp_path.glob("*.html")),
    )
    monkeypatch.setattr(convert_html, "persist_source_artifact", lambda artifact: None)
    calls = []
    real_hashes = convert_html._compute_global_boilerplate_hashes
    monkeypatch.setattr(
        convert_html,
        "_compute_global_boilerplate_hashes",
        lambda paths: calls.append(paths) or real_hashes(paths),
    )

    convert_html.main(force=False)

    assert calls, "hashes must be computed when at least one file is converted"
    assert (tmp_path / "page.md").exists()


def test_build_document_source_metadata_pdf_and_html_paths():
    from src.source_metadata import build_document_source_metadata

    pdf_meta = build_document_source_metadata(
        {"fallback_used_pages": 0},
        source="Lipid_Management.pdf",
        source_type="pdf",
        manifest_record={"logical_name": "Lipid guide", "url": "https://hpp.moh.gov.sg/lipid"},
        explicit_class="guideline_pdf",
    )
    assert pdf_meta["source_type"] == "pdf"
    assert pdf_meta["source_class"] == "guideline_pdf"
    assert pdf_meta["logical_name"] == "Lipid guide"
    assert pdf_meta["canonical_label"] == "Lipid guide"
    assert pdf_meta["domain"] == "hpp.moh.gov.sg"
    assert pdf_meta["domain_type"] == "government"

    html_meta = build_document_source_metadata(
        {"page_type": "article"},
        source="healthhub_screening.md",
        source_type="html",
    )
    assert html_meta["source_type"] == "html"
    assert html_meta["source_class"] == "guideline_html"
    assert html_meta["canonical_label"] == "healthhub screening"
    assert html_meta["domain"] is None
    assert html_meta["domain_type"] == "unknown"


def test_convert_html_to_md_reuses_parsed_soup(monkeypatch, tmp_path: Path):
    from src.ingestion.steps import convert_html

    (tmp_path / "page.html").write_text(
        "<html><body><h1>Heading</h1>"
        "<p>" + "Substantial body content for extraction. " * 8 + "</p></body></html>",
        encoding="utf-8",
    )
    monkeypatch.setattr(convert_html, "persist_source_artifact", lambda artifact: None)
    real_bs = convert_html.BeautifulSoup
    parses = []
    monkeypatch.setattr(
        convert_html,
        "BeautifulSoup",
        lambda html, parser: (parses.append(html[:16]), real_bs(html, parser))[1],
    )

    result = convert_html.convert_html_to_md(tmp_path / "page.html", force=True)

    assert result is not None
    # Classification soup is passed through to the fallback extraction, so the
    # file is parsed at most twice (raw + cascade's own bs step), never a third
    # time for the fallback re-parse.
    assert 1 <= len(parses) <= 2
