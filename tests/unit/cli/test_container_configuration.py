import json
import os
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[3]


def test_backend_image_includes_authoritative_settings_and_compose_uses_nested_names():
    dockerfile = (PROJECT_ROOT / "Dockerfile").read_text()
    compose = (PROJECT_ROOT / "docker-compose.yml").read_text()
    env_example = (PROJECT_ROOT / ".env.example").read_text()

    assert "COPY config/settings.yaml ./config/settings.yaml" in dockerfile
    assert "APP__APP__ENVIRONMENT: production" in compose
    for setting_name in (
        "APP__LLM__PROVIDER",
        "APP__LLM__DASHSCOPE_API_KEY",
        "APP__LLM__GEMINI_API_KEY",
        "APP__API__SESSION_SIGNING_SECRET",
        "APP__PRODUCTION__PRODUCTION_PROFILE",
        "APP__STORAGE__CHROMA_PERSIST_DIRECTORY",
    ):
        assert setting_name in compose
    assert "APP__API__SESSION_SIGNING_SECRET" in env_example
    assert "ARG APP__LLM__" not in dockerfile
    assert "ENV APP__LLM__" not in dockerfile


def test_preflight_matches_container_style_nested_overrides_in_isolated_subprocess(tmp_path):
    runtime_env = {
        key: value
        for key, value in os.environ.items()
        if key in {"PATH", "HOME", "LANG", "LC_ALL", "VIRTUAL_ENV", "SYSTEMROOT"}
    }
    runtime_env.update(
        {
            "PYTHONPATH": str(PROJECT_ROOT),
            "PYTHONDONTWRITEBYTECODE": "1",
            "APP__APP__ENVIRONMENT": "production",
            "APP__LLM__PROVIDER": "gemini",
            "APP__LLM__GEMINI_API_KEY": "synthetic-generation-secret",
            "APP__LLM__DASHSCOPE_API_KEY": "synthetic-embedding-secret",
            "APP__API__SESSION_SIGNING_SECRET": "synthetic-signing-secret-with-32-bytes",
            "APP__API__API_KEYS": "synthetic-caller-secret",
            "APP__PRODUCTION__PRODUCTION_PROFILE": "baseline",
            "APP__STORAGE__CHROMA_PERSIST_DIRECTORY": str(tmp_path / "index-not-created"),
        }
    )
    result = subprocess.run(
        [sys.executable, "-m", "src.cli.preflight"],
        cwd=PROJECT_ROOT,
        env=runtime_env,
        check=False,
        capture_output=True,
        text=True,
        timeout=30,
    )

    assert result.returncode == 0
    report = json.loads(result.stdout)
    assert report["deployment"]["environment"] == "production"
    assert report["roles"]["generation"]["provider"] == "gemini"
    assert report["roles"]["embedding"]["provider"] == "qwen"
    assert report["index"]["path_exists"] is False
    assert report["index"]["readiness"] == "unverified"
    assert "synthetic-generation-secret" not in result.stdout
    assert "synthetic-embedding-secret" not in result.stdout
    assert "synthetic-signing-secret" not in result.stdout
    assert "synthetic-caller-secret" not in result.stdout
    assert not (tmp_path / "index-not-created").exists()
