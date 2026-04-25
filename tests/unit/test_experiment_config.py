from pathlib import Path

import pytest

from src.experiments.config import (
    _deep_merge,
    _parse_scalar,
    _strip_comment,
    build_run_assessment_kwargs,
    compute_retrieval_delta,
    load_experiment_file,
    parse_simple_yaml,
    resolve_experiment_runs,
)


def test_load_experiment_file_normalizes_defaults():
    config = load_experiment_file("experiments/v1/baseline.yaml")

    assert config["schema_version"] == 1
    assert config["metadata"]["name"] == "baseline"
    assert config["embedding_index"]["collection_name"] == "medical_docs_baseline"
    assert config["experiment_config_hash"]
    assert config["index_config_hash"]
    assert config["ingestion"]["source_chunk_configs"]["pdf"]["chunk_size"] == 650
    assert config["tracking"]["wandb"]["enabled"] is False
    assert config["tracking"]["wandb"]["project"] == "qna-medical-referenced"
    assert config["tracking"]["wandb"]["metrics_verbosity"] == "standard"


def test_load_experiment_file_rejects_unknown_version(tmp_path: Path):
    config_file = tmp_path / "bad.yaml"
    config_file.write_text("schema_version: 99\nmetadata:\n  name: broken\n", encoding="utf-8")

    with pytest.raises(ValueError, match="Unsupported experiment schema_version"):
        load_experiment_file(config_file)


def test_resolve_experiment_variants_includes_base_and_variant():
    runs = resolve_experiment_runs("experiments/v1/baseline.yaml", variant="chunk_small")

    assert len(runs) == 2
    assert runs[0]["variant_name"] is None
    assert runs[1]["variant_name"] == "chunk_small"
    assert runs[1]["ingestion"]["source_chunk_configs"]["pdf"]["chunk_size"] == 480


def test_build_run_assessment_kwargs_uses_experiment_values():
    config = load_experiment_file("experiments/v1/baseline.yaml")

    kwargs = build_run_assessment_kwargs(config)

    assert kwargs["artifact_dir"] == "data/evals"
    assert kwargs["dataset_split"] == "regression"
    assert kwargs["disable_llm_generation"] is True
    assert kwargs["retrieval_options"]["search_mode"] == "rrf_hybrid"
    assert kwargs["experiment_config"]["metadata"]["name"] == "baseline"


# --- Unit tests for utility functions ---


class TestStripComment:
    def test_no_comment(self):
        assert _strip_comment("key: value") == "key: value"

    def test_hash_comment(self):
        assert _strip_comment("key: value # comment") == "key: value"

    def test_only_comment(self):
        assert _strip_comment("# full comment") == ""

    def test_empty(self):
        assert _strip_comment("") == ""


class TestParseScalar:
    def test_bool_true(self):
        assert _parse_scalar("true") is True

    def test_bool_false(self):
        assert _parse_scalar("false") is False

    def test_integer(self):
        assert _parse_scalar("42") == 42

    def test_float(self):
        assert _parse_scalar("3.14") == pytest.approx(3.14)

    def test_string(self):
        assert _parse_scalar("hello") == "hello"

    def test_quoted_string(self):
        result = _parse_scalar('"hello world"')
        assert result == "hello world"


class TestParseSimpleYaml:
    def test_basic(self):
        text = "key: value\nnum: 42"
        result = parse_simple_yaml(text)
        assert result == {"key": "value", "num": 42}

    def test_nested(self):
        text = "parent:\n  child: value"
        result = parse_simple_yaml(text)
        assert result == {"parent": {"child": "value"}}

    def test_comments_ignored(self):
        text = "# comment\nkey: value"
        result = parse_simple_yaml(text)
        assert result == {"key": "value"}

    def test_empty(self):
        result = parse_simple_yaml("")
        assert result == {}


class TestDeepMerge:
    def test_flat_merge(self):
        base = {"a": 1, "b": 2}
        overrides = {"b": 3, "c": 4}
        result = _deep_merge(base, overrides)
        assert result == {"a": 1, "b": 3, "c": 4}

    def test_nested_merge(self):
        base = {"parent": {"a": 1, "b": 2}}
        overrides = {"parent": {"b": 3, "c": 4}}
        result = _deep_merge(base, overrides)
        assert result == {"parent": {"a": 1, "b": 3, "c": 4}}

    def test_empty_overrides(self):
        base = {"a": 1}
        assert _deep_merge(base, {}) == {"a": 1}

    def test_empty_base(self):
        overrides = {"a": 1}
        assert _deep_merge({}, overrides) == {"a": 1}


class TestComputeRetrievalDelta:
    def test_basic_delta(self):
        baseline = {"exact_chunk_hit_rate": 0.4, "mrr": 0.3}
        comparison = {"exact_chunk_hit_rate": 0.6, "mrr": 0.5}
        delta = compute_retrieval_delta(baseline, comparison)
        assert delta["exact_chunk_hit_rate"] == pytest.approx(0.2)
        assert delta["mrr"] == pytest.approx(0.2)

    def test_empty_returns_tracked_keys_with_zero(self):
        delta = compute_retrieval_delta({}, {})
        # Returns all tracked keys with 0.0 delta
        assert "exact_chunk_hit_rate" in delta
        assert all(v == 0.0 for v in delta.values())

    def test_negative_delta(self):
        baseline = {"exact_chunk_hit_rate": 0.8}
        comparison = {"exact_chunk_hit_rate": 0.5}
        delta = compute_retrieval_delta(baseline, comparison)
        assert delta["exact_chunk_hit_rate"] == pytest.approx(-0.3)
