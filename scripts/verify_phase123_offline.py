"""Phase 1-3 offline gate; launch only through verify_phase123_offline.sh."""

import os

if os.environ.get("QNA_OFFLINE_ISOLATION") != "1":
    raise SystemExit("Use scripts/verify_phase123_offline.sh (network/storage isolation required)")

from pathlib import Path

handoff = Path("docs/plans/migration/20261017-p1-c3a-handoff.md").read_text()
runner = handoff.split("```bash\nuv run --offline --no-sync python - <<'PY'\n", 1)[1].split(
    "\nPY\n```", 1
)[0]
exec(
    compile(
        runner.rsplit("\nraise SystemExit(pytest.main([", 1)[0],
        "<published-Gemini-HTTPX-pre-import-isolation>",
        "exec",
    )
)
repair = [
    "tests/unit/infra/test_gemini_httpx_transport.py",
    "tests/integration/app/test_gemini_transport_lifecycle.py",
]

# Explicit inventory: remains valid after these files are committed.
additional = [
    "tests/integration/app/test_gemini_transport_lifecycle.py",
    "tests/integration/app/test_history_turns.py",
    "tests/integration/app/test_lifespan.py",
    "tests/integration/app/test_log_privacy.py",
    "tests/integration/app/test_request_workers.py",
    "tests/integration/app/test_stream_cleanup.py",
    "tests/integration/app/test_stream_failures.py",
    "tests/integration/app/test_telemetry_integration.py",
    "tests/integration/ingestion/test_effective_features.py",
    "tests/unit/app/test_chat_turns.py",
    "tests/unit/app/test_request_workers.py",
    "tests/unit/app/test_session_security.py",
    "tests/unit/cli/test_container_configuration.py",
    "tests/unit/config/test_settings.py",
    "tests/integration/app/test_chat_sources.py",
    "tests/unit/cli/test_preflight.py",
    "tests/unit/cli/test_serve_production.py",
    "tests/unit/evals/test_actual_chunks.py",
    "tests/unit/evals/test_answer_generation_lifecycle.py",
    "tests/unit/evals/test_atomic_artifacts.py",
    "tests/unit/evals/test_attempt_identity.py",
    "tests/unit/evals/test_effective_roles.py",
    "tests/unit/evals/test_evidence_contract.py",
    "tests/unit/evals/test_frozen_index_snapshot.py",
    "tests/unit/evals/test_history_comparability.py",
    "tests/unit/evals/test_judge_lifecycle.py",
    "tests/unit/evals/test_judge_roles.py",
    "tests/unit/evals/test_measurement_completeness.py",
    "tests/unit/evals/test_pydantic_ai_judge.py",
    "tests/unit/evals/test_pydantic_evals_tasks.py",
    "tests/unit/evals/test_replay_contract.py",
    "tests/unit/evals/test_review_manifest_execution.py",
    "tests/unit/evals/test_snapshot_execution.py",
    "tests/unit/evals/test_source_provenance.py",
    "tests/unit/evals/test_usage_execution.py",
    "tests/unit/evals/test_run_telemetry.py",
    "tests/unit/evals/test_assessment_spans.py",
    "tests/unit/evals/test_verified_snapshot.py",
    "tests/unit/experiments/test_metric_dependency_boundary.py",
    "tests/unit/experiments/test_usage_summaries.py",
    "tests/unit/experiments/test_variant_isolation.py",
    "tests/unit/experiments/test_wandb_export_policy.py",
    "tests/unit/experiments/test_winner_eligibility.py",
    "tests/unit/infra/test_client_cleanup.py",
    "tests/unit/infra/test_gemini_httpx_transport.py",
    "tests/unit/infra/test_gemini_response_ownership.py",
    "tests/unit/infra/test_history_turns.py",
    "tests/unit/infra/test_llm_provider_selection.py",
    "tests/unit/infra/test_pydantic_ai_client.py",
    "tests/unit/infra/test_phase4_go_smoke.py",
    "tests/unit/infra/test_nonstream_contract.py",
    "tests/unit/infra/test_nonstream_transport.py",
    "tests/unit/infra/test_stream_cleanup_cancellation.py",
    "tests/unit/infra/test_stream_contract.py",
    "tests/unit/infra/test_stream_transport.py",
    "tests/unit/infra/test_telemetry_lifecycle.py",
    "tests/unit/infra/test_telemetry_sync_owner.py",
    "tests/unit/infra/test_provider_retry_telemetry.py",
    "tests/unit/infra/test_telemetry_policy.py",
    "tests/unit/infra/test_usage_capture.py",
    "tests/unit/rag/test_async_retrieval.py",
    "tests/unit/rag/test_hyde_log_privacy.py",
    "tests/unit/rag/test_effective_config.py",
    "tests/unit/rag/test_index_readiness.py",
    "tests/unit/rag/test_reranker_assets.py",
]
namespace = globals()
pytest = namespace["pytest"]
selected = [*namespace["targets"], *namespace["new"], *repair]
for path in [
    *additional,
    "tests/unit/cli/test_preflight.py",
    "tests/unit/cli/test_container_configuration.py",
    "tests/unit/ingestion/test_enrichment_usage_context.py",
    "tests/unit/ingestion/test_embedding_spans.py",
    "tests/unit/ingestion/test_download_web_groups.py",
    "tests/unit/ingestion/test_collection_build_metadata.py",
    "tests/unit/evals/test_qwen_endpoint_allowlist.py",
    "tests/unit/evals/test_snapshot_url_guard.py",
    "tests/unit/manual/test_build_labqar_reference_csv.py",
    "tests/unit/manual/test_backfill_d11_collection_metadata.py",
    "tests/unit/manual/test_export_review_corpus.py",
    "tests/unit/infra/test_stream_retry_telemetry.py",
    "tests/unit/experiments/test_budget_admission.py",
    "tests/unit/evals/test_review_manifest_authentication.py",
    "tests/unit/evals/test_d11_identity_builder.py",
    "tests/unit/evals/test_review_manifest_tool.py",
    "tests/unit/infra/test_explicit_export_destination.py",
    "tests/integration/telemetry/test_content_canaries.py",
]:
    if path not in selected and not any(t.endswith("/") and path.startswith(t) for t in selected):
        selected.append(path)
raise SystemExit(
    pytest.main(
        [
            "--no-cov",
            "-q",
            "-p",
            "no:cacheprovider",
            *selected,
            "-m",
            "not live_api and not live_openrouter and not e2e_real_apis and not network and not deepeval",
        ]
    )
)
