"""Real lifespan/HTTP/SSE history admission and atomic publishing, synthetic only."""

import asyncio
import json
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from tests.integration.app import test_lifespan

lifecycle = test_lifespan.lifecycle


def _events(response):
    return [
        json.loads(line[6:]) for line in response.text.splitlines() if line.startswith("data: ")
    ]


@pytest.mark.parametrize("clear_path", ["/history", "/history/ignored-legacy-session"])
def test_http_overlapping_turn_and_clear_rejected_other_session_progresses(
    lifecycle, monkeypatch, clear_path
):
    from src.app.session import _verify_signed_session_id

    entered, release = threading.Event(), threading.Event()
    generations = []

    async def generation(*, prompt, context):
        generations.append(prompt)
        yield "synthetic "
        if prompt == "first question":
            entered.set()
            if not await asyncio.to_thread(release.wait, 4):
                raise TimeoutError("test failed to release generation")
        yield "answer"

    app = lifecycle.factory.create_app()
    with TestClient(app) as http:
        monkeypatch.setattr(app.state.llm_client, "a_generate_stream", generation)
        cookie = http.get("/history").cookies["chat_session_id"]
        headers = {"Cookie": f"chat_session_id={cookie}"}
        session = _verify_signed_session_id(cookie)
        with ThreadPoolExecutor(max_workers=1) as pool:
            first = pool.submit(
                http.post,
                "/chat?include_pipeline=true",
                json={"message": "first question"},
                headers=headers,
            )
            try:
                assert entered.wait(3)
                busy = http.post("/chat", json={"message": "overlapping question"}, headers=headers)
                assert busy.status_code == 200  # Headers precede generator admission.
                events = _events(busy)
                assert len(events) == 1
                assert events[0]["done"]
                assert events[0]["error_code"] == "chat_session_busy"
                assert events[0]["request_id"] == busy.headers["X-Request-ID"]
                clear = http.delete(clear_path, headers=headers)
                assert clear.status_code == 409
                assert clear.json()["error"]["code"] == "chat_session_busy"
                assert "set-cookie" not in clear.headers
                assert http.get("/history", headers=headers).json() == {"history": []}
                assert generations == ["first question"]
                other_cookie = http.get("/history", headers={"Cookie": ""}).cookies[
                    "chat_session_id"
                ]
                other_session = _verify_signed_session_id(other_cookie)
                assert other_session != session
                other = http.post(
                    "/chat",
                    json={"message": "other question"},
                    headers={"Cookie": f"chat_session_id={other_cookie}"},
                )
                assert _events(other)[-1]["error"] is None
                assert len(app.state.chat_history_store.get_history(other_session)) == 2
            finally:
                release.set()
                result = first.result(timeout=5)
        assert _events(result)[-1]["error"] is None
        history = app.state.chat_history_store.get_history(session)
        assert [(m["role"], m["content"]) for m in history] == [
            ("user", "first question"),
            ("assistant", "synthetic answer"),
        ]
        cleared = http.delete(clear_path, headers=headers)
        assert cleared.status_code == 200
        assert cleared.cookies["chat_session_id"] != cookie
        assert app.state.chat_history_store.get_history(session) == []


@pytest.mark.parametrize("include_pipeline", [False, True])
def test_http_complete_turn_has_one_publication_and_compatible_terminal(
    lifecycle, monkeypatch, include_pipeline
):
    app = lifecycle.factory.create_app()
    with TestClient(app) as http:
        store = app.state.chat_history_store
        original = store._save_history_unlocked
        publications = []

        def publish(history):
            publications.append(json.loads(json.dumps(history)))
            original(history)

        monkeypatch.setattr(store, "_save_history_unlocked", publish)
        response = http.post(
            f"/chat?include_pipeline={str(include_pipeline).lower()}",
            json={"message": "synthetic question"},
        )
        assert response.status_code == 200
        events = _events(response)
        assert "".join(event["content"] for event in events) == "synthetic answer"
        assert sum(event["done"] for event in events) == 1
        terminal = events[-1]
        assert terminal["sources"]
        assert terminal["error"] is None
        assert terminal["request_id"] == response.headers["X-Request-ID"]
        assert bool(terminal["pipeline"]) is include_pipeline
        assert len(publications) == 1
        saved = next(iter(publications[0].values()))
        assert saved["version"] == 2
        assert [m["role"] for m in saved["messages"]] == ["user", "assistant"]


@pytest.mark.parametrize("failure", ["serialize", "replace"])
def test_http_write_failure_preserves_prior_history_and_releases_session(
    lifecycle, monkeypatch, caplog, failure
):
    from src.app.session import _verify_signed_session_id

    app = lifecycle.factory.create_app()
    with TestClient(app) as http:
        cookie = http.get("/history").cookies["chat_session_id"]
        session = _verify_signed_session_id(cookie)
        store = app.state.chat_history_store
        store.save_turn(session, "older question", "older answer")
        before = store.path.read_bytes()

        def fail(*args, **kwargs):
            raise OSError("forbidden-storage-detail")

        with monkeypatch.context() as patch:
            if failure == "serialize":
                # Limit JSON dump injection to the history writer, not HTTP/SSE.
                original = json.dump

                def fail_history_dump(payload, handle, *args, **kwargs):
                    if Path(handle.name) == store.path.with_suffix(".json.tmp"):
                        fail()
                    return original(payload, handle, *args, **kwargs)

                patch.setattr(json, "dump", fail_history_dump)
            else:
                patch.setattr(Path, "replace", fail)
            response = http.post(
                "/chat?include_pipeline=true",
                json={"message": "synthetic question"},
                headers={"Cookie": f"chat_session_id={cookie}"},
            )
        events = _events(response)
        assert "".join(event["content"] for event in events) == "synthetic answer"
        assert sum(event["done"] for event in events) == 1
        assert events[-1]["error_code"] == "chat_stream_failed"
        assert events[-1]["sources"]
        assert events[-1]["pipeline"]
        assert events[-1]["request_id"] == response.headers["X-Request-ID"]
        assert store.path.read_bytes() == before
        assert "forbidden-storage-detail" not in response.text + caplog.text
        assert session not in caplog.text
        with store.turn(session):
            pass
        retry = http.post(
            "/chat",
            json={"message": "retry question"},
            headers={"Cookie": f"chat_session_id={cookie}"},
        )
        assert _events(retry)[-1]["error"] is None
        assert len(store.get_history(session)) == 4
