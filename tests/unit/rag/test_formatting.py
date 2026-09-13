from src.rag.formatting import (
    build_chat_sources,
    build_context_and_sources,
    build_source_payload,
    format_source_name,
    format_source_with_url,
)
from src.rag.trace_models import ChatSource


def _sample_result(source="health_screening.pdf", content="Some content", page=None, **meta):
    return {
        "source": source,
        "content": content,
        "page": page,
        "metadata": meta,
    }


class TestBuildSourcePayload:
    def test_minimal_result(self):
        result = _sample_result()
        payload = build_source_payload(result)
        assert payload["source"] == "health_screening.pdf"
        assert payload["source_type"] == "pdf"
        assert payload["page"] is None
        assert payload["content_type"] is None

    def test_with_metadata(self):
        result = _sample_result(
            source="report.html",
            content="hello",
            page=5,
            source_url="https://example.com/report",
            logical_name="Test Report",
        )
        payload = build_source_payload(result)
        assert payload["page"] == 5
        assert payload["source_url"] == "https://example.com/report"
        assert payload["canonical_label"] == "Test Report"
        assert "page 5" in payload["display_label"]

    def test_empty_metadata(self):
        result = {"source": "data.csv", "content": "row1", "metadata": {}}
        payload = build_source_payload(result)
        assert payload["source_type"] == "reference_csv"
        assert payload["source_class"] == "reference_csv"

    def test_source_url_from_top_level(self):
        result = {
            "source": "doc.html",
            "content": "text",
            "metadata": {},
            "source_url": "https://www.healthhub.sg/article",
        }
        payload = build_source_payload(result)
        assert payload["source_url"] == "https://www.healthhub.sg/article"

    def test_content_type_from_metadata(self):
        result = _sample_result(content_type="table")
        payload = build_source_payload(result)
        assert payload["content_type"] == "table"

    def test_missing_source_key(self):
        result = {"content": "text", "metadata": {}}
        payload = build_source_payload(result)
        assert payload["source"] == "unknown"

    def test_empty_source_url_returns_none(self):
        result = _sample_result(source_url="")
        payload = build_source_payload(result)
        assert payload["source_url"] is None


class TestFormatSourceName:
    def test_returns_display_label(self):
        result = _sample_result(logical_name="My Guide")
        assert format_source_name(result) == "My Guide"

    def test_without_metadata(self):
        result = {"source": "report.pdf", "content": "x", "metadata": {}}
        name = format_source_name(result)
        assert "report" in name.lower()


class TestFormatSourceWithUrl:
    def test_with_url(self):
        result = _sample_result(source_url="https://example.com/page")
        formatted = format_source_with_url(result)
        assert "https://example.com/page" in formatted

    def test_without_url(self):
        result = _sample_result()
        formatted = format_source_with_url(result)
        assert "http" not in formatted


class TestBuildChatSources:
    def test_single_result(self):
        results = [_sample_result(logical_name="Guide")]
        sources = build_chat_sources(results)
        assert len(sources) == 1
        assert isinstance(sources[0], ChatSource)
        assert sources[0].canonical_label == "Guide"

    def test_multiple_results(self):
        results = [
            _sample_result(source="a.pdf", logical_name="A"),
            _sample_result(source="b.html", source_url="https://b.com", logical_name="B"),
        ]
        sources = build_chat_sources(results)
        assert len(sources) == 2
        assert sources[1].source_url == "https://b.com"

    def test_empty_list(self):
        assert build_chat_sources([]) == []


class TestBuildContextAndSources:
    def test_single_result(self):
        results = [_sample_result(content="chunk text", logical_name="Guide")]
        context, labels, chat_sources = build_context_and_sources(results)
        assert "[Source: Guide]" in context
        assert "chunk text" in context
        assert labels == ["Guide"]
        assert len(chat_sources) == 1

    def test_multiple_results_joined(self):
        results = [
            _sample_result(source="a.pdf", content="aaa", logical_name="A"),
            _sample_result(source="b.pdf", content="bbb", logical_name="B"),
        ]
        context, labels, chat_sources = build_context_and_sources(results)
        assert "[Source: A]" in context
        assert "[Source: B]" in context
        assert len(labels) == 2
        assert "aaa" in context
        assert "bbb" in context

    def test_empty_list(self):
        context, labels, chat_sources = build_context_and_sources([])
        assert context == ""
        assert labels == []
        assert chat_sources == []

    def test_zip_consistency(self):
        results = [_sample_result(content=f"text{i}", logical_name=f"L{i}") for i in range(5)]
        context, labels, chat_sources = build_context_and_sources(results)
        assert len(labels) == len(chat_sources) == 5
