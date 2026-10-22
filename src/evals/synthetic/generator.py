"""Synthetic medical Q&A generation using DeepEval's Synthesizer."""

from pathlib import Path
from typing import Any

from src.evals.deepeval_models import get_heavy_model

MAX_SYNTHETIC_QUESTIONS = 100


def generate_synthetic_dataset(
    document_paths: list[Path | str],
    num_questions: int = 100,
    output_path: Path | str = "data/evals/synthetic_dataset.json",
) -> list[Any]:
    """Explicitly generate a bounded diagnostic dataset from medical documents.

    This is an opt-in diagnostic utility, not an automatic benchmark-data source.
    DeepEval 3.9.7 bounds generation with contexts and goldens per context; the
    returned and saved data are capped at ``num_questions``.
    """
    if isinstance(num_questions, bool) or not 1 <= num_questions <= MAX_SYNTHETIC_QUESTIONS:
        raise ValueError(f"num_questions must be between 1 and {MAX_SYNTHETIC_QUESTIONS}.")

    paths = [Path(path) for path in document_paths]
    if not paths:
        raise ValueError("At least one document path is required.")
    for path in paths:
        if not path.is_file():
            raise FileNotFoundError(path)

    destination = Path(output_path)
    if destination.suffix.lower() not in {"", ".json"}:
        raise ValueError("Synthetic dataset output_path must be a JSON path.")
    file_name = destination.stem if destination.suffix else destination.name
    if "." in file_name:
        raise ValueError("DeepEval save_as file_name must not contain periods.")

    bounded_paths = paths[:num_questions]
    max_contexts_per_document = max(1, num_questions // len(bounded_paths))

    from deepeval.synthesizer import Synthesizer
    from deepeval.synthesizer.config import ContextConstructionConfig

    judge_model = get_heavy_model()
    synthesizer = Synthesizer(model=judge_model, async_mode=True)
    goldens: list[Any] = synthesizer.generate_goldens_from_docs(
        document_paths=[str(path) for path in bounded_paths],
        context_construction_config=ContextConstructionConfig(
            critic_model=judge_model,
            chunk_size=1024,
            chunk_overlap=50,
            max_contexts_per_document=max_contexts_per_document,
        ),
        max_goldens_per_context=1,
    )[:num_questions]

    synthesizer.synthetic_goldens = goldens
    synthesizer.save_as(
        file_type="json",
        directory=str(destination.parent),
        file_name=file_name,
        quiet=True,
    )
    return goldens
