from unittest.mock import MagicMock, patch

import pytest

from src.app.exceptions import UpstreamServiceError
from src.usecases.chat import (
    MAX_MESSAGE_LENGTH,
    _build_history_context,
    _compose_full_context,
    process_chat_message,
)


def _mock_history_store(history=None):
    store = MagicMock()
    store.get_history.return_value = history or []
    return store


def _mock_llm(response="Test response"):
    client = MagicMock()
    client.generate.return_value = response
    return client


class TestBuildHistoryContext:
    def test_empty_history(self):
        assert _build_history_context([]) == ""

    def test_single_message(self):
        history = [{"role": "user", "content": "Hello"}]
        assert _build_history_context(history) == "user: Hello"

    def test_multiple_messages(self):
        history = [
            {"role": "user", "content": "Hi"},
            {"role": "assistant", "content": "Hello!"},
        ]
        result = _build_history_context(history)
        assert "user: Hi" in result
        assert "assistant: Hello!" in result
        assert "\n" in result


class TestComposeFullContext:
    def test_empty_history(self):
        result = _compose_full_context("", "retrieved context")
        assert result == "retrieved context"

    def test_with_history(self):
        result = _compose_full_context("user: Hi", "retrieved context")
        assert "user: Hi" in result
        assert "retrieved context" in result
        assert "Context:" in result

    def test_both_empty(self):
        result = _compose_full_context("", "")
        assert result == ""


class TestProcessChatMessage:
    @patch("src.usecases.chat.retrieve_context")
    def test_basic_flow(self, mock_retrieve):
        mock_retrieve.return_value = ("context text", ["source1.pdf"])
        store = _mock_history_store()
        llm = _mock_llm("answer")

        result = process_chat_message(
            llm_client=llm,
            history_store=store,
            message="What is LDL?",
            session_id="sess-1",
        )

        assert result["response"] == "answer"
        assert result["sources"] == ["source1.pdf"]
        assert result["pipeline"] is None

    @patch("src.usecases.chat.retrieve_context_with_trace")
    def test_with_pipeline_trace(self, mock_retrieve_trace):
        mock_trace = MagicMock()
        mock_trace.generation = MagicMock()
        mock_trace.generation.timing_ms = 0
        mock_trace.total_time_ms = 0
        mock_retrieve_trace.return_value = ("ctx", ["src"], mock_trace)
        store = _mock_history_store()
        llm = _mock_llm("answer")

        result = process_chat_message(
            llm_client=llm,
            history_store=store,
            message="What is HDL?",
            session_id="sess-2",
            include_pipeline=True,
        )

        assert result["pipeline"] is mock_trace
        assert isinstance(result["pipeline"].generation.timing_ms, int)
        assert isinstance(result["pipeline"].total_time_ms, int)

    @patch("src.usecases.chat.retrieve_context")
    def test_saves_messages_to_history(self, mock_retrieve):
        mock_retrieve.return_value = ("ctx", [])
        store = _mock_history_store()
        llm = _mock_llm("response text")

        process_chat_message(
            llm_client=llm,
            history_store=store,
            message="hello",
            session_id="sess-3",
        )

        store.save_message.assert_any_call("sess-3", "user", "hello")
        store.save_message.assert_any_call("sess-3", "assistant", "response text")
        assert store.save_message.call_count == 2

    @patch("src.usecases.chat.retrieve_context")
    def test_session_id_default(self, mock_retrieve):
        mock_retrieve.return_value = ("ctx", [])
        store = _mock_history_store()
        llm = _mock_llm("ok")

        process_chat_message(
            llm_client=llm,
            history_store=store,
            message="hi",
            session_id=None,
        )

        store.get_history.assert_called_with("default")

    def test_empty_message_raises(self):
        store = _mock_history_store()
        llm = _mock_llm()
        with pytest.raises(ValueError, match="message must be"):
            process_chat_message(
                llm_client=llm,
                history_store=store,
                message="",
                session_id="s",
            )

    def test_too_long_message_raises(self):
        store = _mock_history_store()
        llm = _mock_llm()
        with pytest.raises(ValueError, match="message must be"):
            process_chat_message(
                llm_client=llm,
                history_store=store,
                message="x" * (MAX_MESSAGE_LENGTH + 1),
                session_id="s",
            )

    def test_invalid_session_id_raises(self):
        store = _mock_history_store()
        llm = _mock_llm()
        with pytest.raises(ValueError, match="Invalid session_id"):
            process_chat_message(
                llm_client=llm,
                history_store=store,
                message="hi",
                session_id="bad session!@#",
            )

    def test_valid_session_ids(self):
        valid_ids = ["abc", "ABC", "123", "a-b-c", "a1b2c3", "default"]
        for sid in valid_ids:
            with patch("src.usecases.chat.retrieve_context", return_value=("ctx", [])):
                store = _mock_history_store()
                llm = _mock_llm("ok")
                result = process_chat_message(
                    llm_client=llm,
                    history_store=store,
                    message="hi",
                    session_id=sid,
                )
                assert result["response"] == "ok"

    @patch("src.usecases.chat.retrieve_context")
    def test_llm_failure_wraps_as_upstream_error(self, mock_retrieve):
        mock_retrieve.return_value = ("ctx", [])
        store = _mock_history_store()
        llm = _mock_llm()
        llm.generate.side_effect = RuntimeError("API down")

        with pytest.raises(UpstreamServiceError):
            process_chat_message(
                llm_client=llm,
                history_store=store,
                message="hi",
                session_id="s",
            )

    @patch("src.usecases.chat.retrieve_context")
    def test_history_context_is_passed(self, mock_retrieve):
        mock_retrieve.return_value = ("retrieved", [])
        store = _mock_history_store(history=[{"role": "user", "content": "prev question"}])
        llm = _mock_llm("ok")

        process_chat_message(
            llm_client=llm,
            history_store=store,
            message="follow up",
            session_id="s1",
        )

        call_args = llm.generate.call_args
        assert "prev question" in call_args.kwargs.get("context", call_args[1].get("context", ""))

    @patch("src.usecases.chat.retrieve_context")
    def test_message_at_max_length_succeeds(self, mock_retrieve):
        mock_retrieve.return_value = ("ctx", [])
        store = _mock_history_store()
        llm = _mock_llm("ok")

        result = process_chat_message(
            llm_client=llm,
            history_store=store,
            message="x" * MAX_MESSAGE_LENGTH,
            session_id="s",
        )
        assert result["response"] == "ok"
