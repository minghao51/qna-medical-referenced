# -*- coding: utf-8 -*-
"""Chunking analysis notebook.

Analyze different chunking strategies and their effects on chunk quality.
"""

# %% [markdown]
# # Chunking Strategy Analysis

# %% [markdown]
# ## Setup

# %%
import polars as pl
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = PROJECT_ROOT / "data"

# %% [markdown]
# ## Load Gold Layer Chunks

# %%
gold_chunks_dir = DATA_DIR / "03_gold" / "chunks"
raw_chunks_path = gold_chunks_dir / "raw_chunks.parquet"
enriched_chunks_path = gold_chunks_dir / "enriched_chunks.parquet"

if raw_chunks_path.exists():
    raw_df = pl.read_parquet(raw_chunks_path)
    print(f"Raw chunks loaded: {len(raw_df)}")
else:
    raw_df = None
    print("No raw chunks found")

if enriched_chunks_path.exists():
    enriched_df = pl.read_parquet(enriched_chunks_path)
    print(f"Enriched chunks loaded: {len(enriched_df)}")
else:
    enriched_df = None
    print("No enriched chunks found")

# %% [markdown]
# ## Chunk Length Distribution

# %%
if raw_df is not None and "content" in raw_df.columns:
    lengths = raw_df.select("content").to_series().str.len_chars()
    print("=== Chunk Length Statistics ===")
    print(f"Min: {lengths.min()}")
    print(f"Max: {lengths.max()}")
    print(f"Mean: {lengths.mean():.0f}")
    print(f"Median: {lengths.median():.0f}")

# %% [markdown]
# ## Compare Raw vs Enriched

# %%
if raw_df is not None and enriched_df is not None:
    print("=== Raw vs Enriched Comparison ===")
    print(f"Raw chunks: {len(raw_df)}")
    print(f"Enriched chunks: {len(enriched_df)}")

    if "hypothetical_questions" in enriched_df.columns:
        with_hype = enriched_df.filter(pl.col("hypothetical_questions").list.len() > 0)
        print(f"Chunks with HyPE: {len(with_hype)}")

    if "extracted_keywords" in enriched_df.columns:
        with_keywords = enriched_df.filter(pl.col("extracted_keywords").list.len() > 0)
        print(f"Chunks with keywords: {len(with_keywords)}")
