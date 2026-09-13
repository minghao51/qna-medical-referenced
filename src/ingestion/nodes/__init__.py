"""Hamilton DAG nodes for the data ingestion pipeline.

One module per canonical pipeline stage (see docs/architecture/pipeline-stages.md
for the stage vocabulary). Each node is a thin Hamilton wrapper that delegates
to the real implementation in src/ingestion/steps/ or src/ingestion/indexing/.
"""

from src.ingestion.nodes import chunk, download, embedding, enrich, parse, reference

# Stage order (Hamilton derives actual execution order from dataflow;
# this list only feeds driver.Builder().with_modules()).
NODE_MODULES = [download, parse, chunk, enrich, reference, embedding]

__all__ = [
    "NODE_MODULES",
    "chunk",
    "download",
    "embedding",
    "enrich",
    "parse",
    "reference",
]
