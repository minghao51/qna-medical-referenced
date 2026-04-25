"""Data exploration notebook for medical Q&A documents.

This notebook provides exploratory analysis of the ingested documents
and chunks in the medallion data pipeline.
"""

# %% [markdown]
# # Medical Q&A Data Exploration

# %% [markdown]
# ## Setup

# %%
from pathlib import Path

import polars as pl

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = PROJECT_ROOT / "data"

# %% [markdown]
# ## Bronze Layer (Raw Downloads)

# %%
# List downloaded files
bronze_dir = DATA_DIR / "01_bronze"
if bronze_dir.exists():
    print("Bronze layer contents:")
    for item in bronze_dir.rglob("*"):
        if item.is_file():
            print(f"  {item.relative_to(bronze_dir)}")
else:
    print("Bronze layer not yet populated")

# %% [markdown]
# ## Silver Layer (Parsed Documents)

# %%
silver_dir = DATA_DIR / "02_silver"
pdf_docs_path = silver_dir / "documents" / "pdf_documents.parquet"
md_docs_path = silver_dir / "documents" / "markdown_documents.parquet"

if pdf_docs_path.exists():
    pdf_df = pl.read_parquet(pdf_docs_path)
    print(f"PDF documents: {len(pdf_df)}")
    print(pdf_df.head())
else:
    print("No PDF documents yet")

# %% [markdown]
# ## Gold Layer (Chunks)

# %%
gold_dir = DATA_DIR / "03_gold"
chunks_path = gold_dir / "chunks" / "raw_chunks.parquet"
enriched_path = gold_dir / "chunks" / "enriched_chunks.parquet"

if chunks_path.exists():
    chunks_df = pl.read_parquet(chunks_path)
    print(f"Raw chunks: {len(chunks_df)}")
    print(chunks_df.head())
else:
    print("No raw chunks yet")

# %% [markdown]
# ## Chunk Quality Analysis

# %%
def analyze_chunk_quality(chunks_df: pl.DataFrame) -> None:
    """Analyze chunk quality metrics."""
    print("=== Chunk Quality Analysis ===")
    print(f"Total chunks: {len(chunks_df)}")

    if "quality_score" in chunks_df.columns:
        print("\nQuality score distribution:")
        print(chunks_df.select("quality_score").describe())

    if "content" in chunks_df.columns:
        avg_length = chunks_df.select("content").to_series().str.len_chars().mean()
        print(f"\nAverage chunk length: {avg_length:.0f} characters")

analyze_chunk_quality(chunks_df)

# %% [markdown]
# ## Source Distribution

# %%
def analyze_source_distribution(chunks_df: pl.DataFrame) -> None:
    """Analyze chunk distribution by source."""
    if "source" in chunks_df.columns:
        print("=== Source Distribution ===")
        source_counts = chunks_df.group_by("source").len()
        print(source_counts)

analyze_source_distribution(chunks_df)
