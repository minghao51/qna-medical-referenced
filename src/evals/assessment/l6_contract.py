"""Canonical L6 answer-quality contract constants."""

# ---------------------------------------------------------------------------
# Canonical pipeline stage vocabulary (single source of truth).
# Mirrored in docs/architecture/pipeline-stages.md — keep both in sync.
# Code identifiers use the STAGE_* names; L-numbers survive only as output
# labels (STAGE_EVAL_LABELS). See docs/plans/20260910-structural-refactor-roadmap.md §3.3.
# ---------------------------------------------------------------------------

STAGE_DOWNLOAD = "download"
STAGE_PARSE = "parse"
STAGE_CHUNK = "chunk"
STAGE_ENRICH = "enrich"
STAGE_REFERENCE = "reference"
STAGE_EMBEDDING = "embedding"

PIPELINE_STAGES: tuple[str, ...] = (
    STAGE_DOWNLOAD,
    STAGE_PARSE,
    STAGE_CHUNK,
    STAGE_ENRICH,
    STAGE_REFERENCE,
    STAGE_EMBEDDING,
)

STAGE_EVAL_LABELS: dict[str, str] = {
    STAGE_DOWNLOAD: "L0 download",
    STAGE_PARSE: "L1 html / L2 pdf",
    STAGE_CHUNK: "L3 chunking",
    STAGE_ENRICH: "L3 enrich",
    STAGE_REFERENCE: "L4 reference",
    STAGE_EMBEDDING: "L5 index",
}

L6_ANSWER_QUALITY_ROWS = "l6_answer_quality.jsonl"
L6_ANSWER_QUALITY_METRICS = "l6_answer_quality_metrics.json"
SUMMARY_L6_METRICS_KEY = "l6_answer_quality_metrics"
SUMMARY_L6_ENABLED_KEY = "l6_answer_quality_enabled"
SUMMARY_L6_STATUS_KEY = "l6_answer_quality_status"
