"""Synthetic medical Q&A generation using DeepEval's Synthesizer."""

from pathlib import Path

from deepeval.synthesizer import Synthesizer
from deepeval.synthesizer.config import ContextConstructionConfig

from src.evals.deepeval_models import get_heavy_model


def generate_synthetic_dataset(
    document_paths: list[Path | str],
    num_questions: int = 100,
    output_path: Path | str = "data/evals/synthetic_dataset.json",
) -> list:
    """Generate diverse synthetic questions from medical documents.

    Uses DeepEval's Synthesizer to create diverse question-answer pairs
    from provided medical documents. This is useful for creating evaluation
    datasets when human-curated questions are limited.

    Args:
        document_paths: List of paths to medical text documents
        num_questions: Target number of questions to generate
        output_path: Where to save the generated dataset

    Returns:
        List of golden test cases (DeepEval Golden objects)
    """
    synthesizer = Synthesizer(model=get_heavy_model(), async_mode=True)

    goldens = synthesizer.generate_goldens_from_docs(
        document_paths=[str(p) for p in document_paths],
        context_construction_config=ContextConstructionConfig(
            critic_model=get_heavy_model(),
            chunk_size=1024,
            chunk_overlap=50,
        ),
        num_transformations=max(1, num_questions // len(document_paths)),
    )

    synthesizer.save_as(file_path=str(output_path), file_type="json")
    return goldens
