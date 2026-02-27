from src.ingestion.steps.chunk_text import TextChunker, chunk_documents


class TestTextChunker:
    def test_chunk_text_basic(self):
        chunker = TextChunker(chunk_size=800, chunk_overlap=150)
        text = "This is a test document. " * 100
        chunks = chunker.chunk_text(text, "test.pdf", "doc1")

        assert len(chunks) > 0
        assert all("content" in c for c in chunks)
        assert all("id" in c for c in chunks)
        assert all("source" in c for c in chunks)

    def test_chunk_size_respected(self):
        chunker = TextChunker(chunk_size=100, chunk_overlap=20)
        text = "a" * 500
        chunks = chunker.chunk_text(text, "test.pdf", "doc1")

        for chunk in chunks:
            assert len(chunk["content"]) <= 100

    def test_overlap_working(self):
        chunker = TextChunker(chunk_size=100, chunk_overlap=20)
        text = "abcdefghij" * 50
        chunks = chunker.chunk_text(text, "test.pdf", "doc1")

        if len(chunks) >= 2:
            second_chunk_start = chunks[1]["content"][:20]
            first_chunk_end = chunks[0]["content"][-20:]
            overlap_exists = any(c in second_chunk_start for c in first_chunk_end)
            assert overlap_exists or len(chunks) == 1

    def test_no_mid_sentence_cut_with_period(self):
        chunker = TextChunker(chunk_size=50, chunk_overlap=10)
        text = "This is sentence one. This is sentence two. This is sentence three."
        chunks = chunker.chunk_text(text, "test.pdf", "doc1")

        for chunk in chunks:
            content = chunk["content"]
            if len(content) > 0:
                last_char = content[-1]
                if last_char not in '.!?':
                    next_char_idx = chunk.get("end_char", text.find(content) + len(content))
                    if next_char_idx < len(text):
                        assert text[next_char_idx] in '.!?\n ', "Should break at sentence boundary"

    def test_paragraph_boundary_detection(self):
        chunker = TextChunker(chunk_size=100, chunk_overlap=20)
        text = "Paragraph one here.\n\nParagraph two here.\n\nParagraph three here."
        chunks = chunker.chunk_text(text, "test.pdf", "doc1")

        for chunk in chunks:
            assert "\n\n" in chunk["content"] or len(chunk["content"]) < 100

    def test_metadata_page_attached(self):
        chunker = TextChunker(chunk_size=800, chunk_overlap=150)
        text = "Test content"
        chunks = chunker.chunk_text(text, "test.pdf", "doc1", page=5)

        assert all(c["page"] == 5 for c in chunks)
        assert all(c["source"] == "test.pdf" for c in chunks)

    def test_metadata_source_attached(self):
        chunker = TextChunker(chunk_size=800, chunk_overlap=150)
        text = "Test content"
        chunks = chunker.chunk_text(text, "my_document.pdf", "doc1")

        assert all(c["source"] == "my_document.pdf" for c in chunks)

    def test_chunk_documents_from_pages(self):
        chunker = TextChunker(chunk_size=200, chunk_overlap=30)
        documents = [
            {
                "id": "doc1",
                "source": "test.pdf",
                "pages": [
                    {"page": 1, "content": "Page one content here. " * 20},
                    {"page": 2, "content": "Page two content here. " * 20}
                ]
            }
        ]

        chunks = chunker.chunk_documents(documents)

        assert len(chunks) > 0
        page_numbers = [c["page"] for c in chunks]
        assert 1 in page_numbers
        assert 2 in page_numbers
        ids = [c["id"] for c in chunks]
        assert len(ids) == len(set(ids)), "Chunk IDs should be unique across pages"

    def test_chunk_documents_without_pages(self):
        chunker = TextChunker(chunk_size=200, chunk_overlap=30)
        documents = [
            {
                "id": "doc1",
                "source": "test.pdf",
                "content": "Full document content here. " * 50
            }
        ]

        chunks = chunker.chunk_documents(documents)

        assert len(chunks) > 0

    def test_empty_text_handling(self):
        chunker = TextChunker(chunk_size=800, chunk_overlap=150)
        chunks = chunker.chunk_text("", "test.pdf", "doc1")

        assert len(chunks) == 0

    def test_short_text_single_chunk(self):
        chunker = TextChunker(chunk_size=800, chunk_overlap=150)
        text = "Short text"
        chunks = chunker.chunk_text(text, "test.pdf", "doc1")

        assert len(chunks) == 1
        assert chunks[0]["content"] == "Short text"

    def test_chunk_id_unique(self):
        chunker = TextChunker(chunk_size=50, chunk_overlap=10)
        text = "word " * 100
        chunks = chunker.chunk_text(text, "test.pdf", "doc1")

        ids = [c["id"] for c in chunks]
        assert len(ids) == len(set(ids)), "Chunk IDs should be unique"

    def test_chunker_supports_legacy_strategy(self):
        chunker = TextChunker(chunk_size=80, chunk_overlap=10, strategy="legacy")
        chunks = chunker.chunk_text("Sentence one. Sentence two. Sentence three.", "test.pdf", "doc1")

        assert len(chunks) >= 1
        assert all("chunk_index" in c for c in chunks)

    def test_recursive_strategy_prefers_sentence_boundary(self):
        chunker = TextChunker(chunk_size=60, chunk_overlap=10, strategy="recursive", min_chunk_size=20)
        text = "A short first sentence. A second sentence that is a bit longer. Third sentence."
        chunks = chunker.chunk_text(text, "test.pdf", "doc1")

        assert len(chunks) >= 2
        assert chunks[0]["end_char"] > chunks[0]["start_char"]

    def test_markdown_heading_aware_chunking_preserves_offsets(self):
        chunker = TextChunker(chunk_size=80, chunk_overlap=10, strategy="recursive")
        md = "# H1\nAlpha section text.\n\n## H2\nBeta section text that is a little longer.\n"
        chunks = chunker.chunk_documents([{"id": "md1", "source": "doc.md", "content": md}])

        assert len(chunks) >= 2
        assert all(c["source"] == "doc.md" for c in chunks)
        assert all("start_char" in c and "end_char" in c for c in chunks)
        starts = [c["start_char"] for c in chunks]
        assert starts == sorted(starts)

    def test_source_specific_chunk_configs_apply_to_markdown(self):
        chunker = TextChunker(chunk_size=800, chunk_overlap=150, strategy="legacy")
        md = "# H1\n" + ("alpha " * 200)
        chunks = chunker.chunk_documents_with_configs(
            [{"id": "md1", "source": "doc.md", "content": md}],
            source_chunk_configs={"markdown": {"chunk_size": 120, "chunk_overlap": 20, "strategy": "recursive"}},
        )
        assert len(chunks) > 1
        assert max(len(c["content"]) for c in chunks) <= 120

    def test_boundary_priority(self):
        chunker = TextChunker(chunk_size=100, chunk_overlap=20)
        text = "First paragraph.\n\nSecond paragraph.\nThird sentence."
        chunks = chunker.chunk_text(text, "test.pdf", "doc1")

        for chunk in chunks:
            content = chunk["content"]
            assert content.startswith("First") or content.startswith("Second") or content.startswith("Third")

    def test_chunk_documents_function(self):
        documents = [
            {"id": "doc1", "source": "test.pdf", "content": "Test content"}
        ]
        chunks = chunk_documents(documents)

        assert len(chunks) > 0
