"""Cross-encoder reranking for retrieval results."""

import logging
import time
from dataclasses import dataclass

logger = logging.getLogger(__name__)

_DEFAULT_MODEL = "BAAI/bge-reranker-base"
_DEFAULT_BATCH_SIZE = 16
_DEFAULT_DEVICE = "cpu"


@dataclass
class RerankResult:
    original_results: list[dict]
    reranked_results: list[dict]
    model_name: str
    batch_size: int
    timing_ms: int
    candidates_count: int
    output_count: int
    filtered_out_count: int = 0


class CrossEncoderReranker:
    def __init__(
        self,
        model_name: str = _DEFAULT_MODEL,
        batch_size: int = _DEFAULT_BATCH_SIZE,
        device: str | None = None,
    ):
        self.model_name = model_name
        self.batch_size = batch_size
        self.device = device or _DEFAULT_DEVICE
        self._model = None

    def _load_model(self):
        if self._model is not None:
            return
        try:
            from sentence_transformers import CrossEncoder

            self._model = CrossEncoder(self.model_name, device=self.device)
            logger.info("Loaded cross-encoder model: %s on %s", self.model_name, self.device)
        except ImportError:
            logger.error(
                "sentence-transformers not installed. "
                "Install with: pip install sentence-transformers"
            )
            raise
        except Exception as e:
            logger.error("Failed to load cross-encoder model %s: %s", self.model_name, e)
            raise

    def rerank(
        self,
        query: str,
        results: list[dict],
        top_k: int,
        min_score: float | None = None,
    ) -> RerankResult:
        if not results:
            return RerankResult(
                original_results=[],
                reranked_results=[],
                model_name=self.model_name,
                batch_size=self.batch_size,
                timing_ms=0,
                candidates_count=0,
                output_count=0,
                filtered_out_count=0,
            )

        self._load_model()

        start = time.time()
        pairs = [(query, str(item.get("content", ""))) for item in results]

        scores = self._predict_batch(pairs)

        scored_results = []
        for idx, item in enumerate(results):
            item_copy = dict(item)
            item_copy["rerank_score"] = float(scores[idx])
            scored_results.append(item_copy)

        scored_results.sort(key=lambda x: x["rerank_score"], reverse=True)
        filtered_out_count = 0
        if min_score is not None:
            threshold = float(min_score)
            kept_results = [item for item in scored_results if item["rerank_score"] >= threshold]
            filtered_out_count = len(scored_results) - len(kept_results)
            scored_results = kept_results

        reranked = scored_results[:top_k]

        for rank, item in enumerate(reranked, start=1):
            item["rerank_rank"] = rank

        timing_ms = int((time.time() - start) * 1000)

        return RerankResult(
            original_results=results,
            reranked_results=reranked,
            model_name=self.model_name,
            batch_size=self.batch_size,
            timing_ms=timing_ms,
            candidates_count=len(results),
            output_count=len(reranked),
            filtered_out_count=filtered_out_count,
        )

    def _predict_batch(self, pairs: list[tuple[str, str]]) -> list[float]:
        all_scores: list[float] = []
        for i in range(0, len(pairs), self.batch_size):
            batch = pairs[i : i + self.batch_size]
            batch_scores = self._model.predict(batch)
            if hasattr(batch_scores, "tolist"):
                all_scores.extend(batch_scores.tolist())
            else:
                all_scores.extend(list(batch_scores))
        return all_scores


def get_reranker(
    model_name: str | None = None,
    batch_size: int | None = None,
    device: str | None = None,
) -> CrossEncoderReranker:
    from src.config import settings
    from src.config.context import get_runtime_state

    resolved_model = model_name or settings.reranker_model
    resolved_batch = batch_size or settings.reranker_batch_size
    resolved_device = device or settings.reranker_device

    state = get_runtime_state()
    cached = state.reranker_instance
    if (
        cached is not None
        and cached.model_name == resolved_model
        and cached.batch_size == resolved_batch
        and cached.device == resolved_device
    ):
        return cached

    instance = CrossEncoderReranker(
        model_name=resolved_model,
        batch_size=resolved_batch,
        device=resolved_device,
    )
    state.reranker_instance = instance
    return instance
