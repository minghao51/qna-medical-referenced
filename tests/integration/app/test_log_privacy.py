"""Request logs exclude caller-controlled path, cookie, address and credential values."""

# ruff: noqa: F811

from fastapi.testclient import TestClient

from tests.integration.app.test_lifespan import lifecycle  # noqa: F401


def test_429_does_not_log_browser_cookie_ip_or_forwarded_address(lifecycle, monkeypatch, caplog):
    control = lifecycle
    monkeypatch.setattr(control.settings.api, "anonymous_chat_rate_limit_per_minute", 1)
    monkeypatch.setattr(control.settings.api, "trust_proxy_headers", True)
    browser = "synthetic-browser-secret-canary"
    address = "synthetic-patient-address-canary"
    # Anonymous limiting is keyed by client IP, so a fixed client address gives this
    # test its own bucket without relying on the removed anon_browser_id cookie.
    with TestClient(control.factory.create_app(), client=("10.20.0.1", 1234)) as client:
        client.cookies.set("anon_browser_id", browser)
        headers = {"X-Forwarded-For": address}
        assert (
            client.post(
                "/chat", json={"message": "synthetic question"}, headers=headers
            ).status_code
            == 200
        )
        response = client.post("/chat", json={"message": "synthetic question"}, headers=headers)
        assert response.status_code == 429
        assert response.headers["x-request-id"] in caplog.text
    assert "rate_limit_exceeded" in caplog.text
    assert browser not in caplog.text
    assert address not in caplog.text
    assert "rate_key" not in caplog.text


def test_unmatched_request_does_not_log_path_or_header_canaries(lifecycle, caplog):
    marker = "synthetic-patient-path-secret-canary"
    with TestClient(lifecycle.factory.create_app()) as client:
        response = client.get(f"/not-a-route/{marker}", headers={"X-Request-ID": marker})
        assert response.status_code == 404
        assert response.headers["x-request-id"] != marker
    # TestClient's own HTTPX access log is client-side, not an application log.
    application_logs = "\n".join(
        record.getMessage() for record in caplog.records if record.name.startswith("src.")
    )
    assert marker not in application_logs
    assert "/unmatched" in application_logs


def test_nonstandard_http_method_is_redacted_from_application_logs(lifecycle, caplog):
    method_canary = "QNA-PATIENT-METHOD-CANARY"
    with TestClient(lifecycle.factory.create_app()) as client:
        response = client.request(method_canary, "/not-a-route")
        assert response.status_code == 404

    application_logs = "\n".join(
        record.getMessage() for record in caplog.records if record.name.startswith("src.")
    )
    assert '"method": "OTHER"' in application_logs
    assert method_canary not in application_logs


def test_standard_http_method_remains_in_application_logs(lifecycle, caplog):
    with TestClient(lifecycle.factory.create_app()) as client:
        response = client.get("/not-a-route")
        assert response.status_code == 404

    application_logs = "\n".join(
        record.getMessage() for record in caplog.records if record.name.startswith("src.")
    )
    assert '"method": "GET"' in application_logs
