"""Tests for bounded synthetic data generation against the DeepEval 3.9.7 API."""

import sys
from pathlib import Path
from types import ModuleType

import pytest


def _import_generator():
    from src.evals.synthetic.generator import generate_synthetic_dataset

    return generate_synthetic_dataset


def _install_deepeval_fakes(monkeypatch, generated_goldens):
    calls = {}

    class FakeSynthesizer:
        def __init__(
            self,
            model=None,
            async_mode=True,
            max_concurrent=100,
            filtration_config=None,
            evolution_config=None,
            styling_config=None,
            conversational_styling_config=None,
            cost_tracking=False,
        ):
            calls["synthesizer"] = {
                "model": model,
                "async_mode": async_mode,
                "max_concurrent": max_concurrent,
            }
            self.synthetic_goldens = []
            self.synthetic_conversational_goldens = []

        def generate_goldens_from_docs(
            self,
            document_paths,
            include_expected_output=True,
            max_goldens_per_context=2,
            context_construction_config=None,
            _send_data=True,
        ):
            calls["generate"] = {
                "document_paths": document_paths,
                "include_expected_output": include_expected_output,
                "max_goldens_per_context": max_goldens_per_context,
                "context_construction_config": context_construction_config,
                "_send_data": _send_data,
            }
            self.synthetic_goldens = generated_goldens
            return generated_goldens

        def save_as(self, file_type, directory, file_name=None, quiet=False):
            calls["save"] = {
                "file_type": file_type,
                "directory": directory,
                "file_name": file_name,
                "quiet": quiet,
            }
            calls["saved_goldens"] = list(self.synthetic_goldens)
            return str(Path(directory) / f"{file_name}.{file_type}")

    class FakeContextConstructionConfig:
        def __init__(
            self,
            embedder=None,
            critic_model=None,
            encoding=None,
            max_contexts_per_document=3,
            min_contexts_per_document=1,
            max_context_length=3,
            min_context_length=1,
            chunk_size=1024,
            chunk_overlap=0,
            context_quality_threshold=0.5,
            context_similarity_threshold=0.0,
            max_retries=3,
        ):
            self.critic_model = critic_model
            self.max_contexts_per_document = max_contexts_per_document
            self.chunk_size = chunk_size
            self.chunk_overlap = chunk_overlap

    deepeval_module = ModuleType("deepeval")
    deepeval_module.__path__ = []
    synthesizer_module = ModuleType("deepeval.synthesizer")
    synthesizer_module.Synthesizer = FakeSynthesizer
    config_module = ModuleType("deepeval.synthesizer.config")
    config_module.ContextConstructionConfig = FakeContextConstructionConfig
    deepeval_module.synthesizer = synthesizer_module
    synthesizer_module.config = config_module
    monkeypatch.setitem(sys.modules, "deepeval", deepeval_module)
    monkeypatch.setitem(sys.modules, "deepeval.synthesizer", synthesizer_module)
    monkeypatch.setitem(sys.modules, "deepeval.synthesizer.config", config_module)
    return calls


def test_synthetic_generator_uses_supported_bounded_sdk_calls(monkeypatch, tmp_path):
    generate_synthetic_dataset = _import_generator()
    document_path = tmp_path / "medical.txt"
    document_path.write_text("medical source", encoding="utf-8")
    generated_goldens = [object(), object(), object()]
    calls = _install_deepeval_fakes(monkeypatch, generated_goldens)
    model = object()
    monkeypatch.setattr("src.evals.synthetic.generator.get_heavy_model", lambda: model)

    output_path = tmp_path / "synthetic.json"
    goldens = generate_synthetic_dataset(
        document_paths=[document_path], num_questions=2, output_path=output_path
    )

    assert goldens == generated_goldens[:2]
    assert calls["synthesizer"] == {
        "model": model,
        "async_mode": True,
        "max_concurrent": 100,
    }
    assert calls["generate"]["document_paths"] == [str(document_path)]
    assert calls["generate"]["max_goldens_per_context"] == 1
    config = calls["generate"]["context_construction_config"]
    assert config.critic_model is model
    assert config.max_contexts_per_document == 2
    assert config.chunk_size == 1024
    assert config.chunk_overlap == 50
    assert calls["saved_goldens"] == goldens
    assert calls["save"] == {
        "file_type": "json",
        "directory": str(tmp_path),
        "file_name": "synthetic",
        "quiet": True,
    }


def test_synthetic_generator_limits_documents_and_context_budget(monkeypatch, tmp_path):
    generate_synthetic_dataset = _import_generator()
    document_paths = []
    for index in range(4):
        path = tmp_path / f"medical-{index}.txt"
        path.write_text("medical source", encoding="utf-8")
        document_paths.append(path)
    calls = _install_deepeval_fakes(monkeypatch, [object(), object()])
    monkeypatch.setattr("src.evals.synthetic.generator.get_heavy_model", object)

    generate_synthetic_dataset(
        document_paths=document_paths, num_questions=2, output_path=tmp_path / "out.json"
    )

    assert calls["generate"]["document_paths"] == [str(path) for path in document_paths[:2]]
    assert calls["generate"]["context_construction_config"].max_contexts_per_document == 1


@pytest.mark.parametrize("num_questions", [0, 101])
def test_synthetic_generator_rejects_unsafe_question_budgets(num_questions, tmp_path):
    generate_synthetic_dataset = _import_generator()

    with pytest.raises(ValueError, match="num_questions"):
        generate_synthetic_dataset(
            document_paths=[tmp_path / "unused.txt"], num_questions=num_questions
        )


def test_synthetic_generator_requires_existing_documents(tmp_path):
    generate_synthetic_dataset = _import_generator()

    with pytest.raises(FileNotFoundError):
        generate_synthetic_dataset(document_paths=[tmp_path / "nonexistent.txt"])
