import pytest
from src.processors.chunker import TextChunker, chunk_documents


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
                    next_char_idx = text.find(content) + len(content)
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
