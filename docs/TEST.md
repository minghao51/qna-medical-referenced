# Testing

## Running Tests

```bash
uv run pytest tests/ -v
```

## Test Files

### test_chunker.py
Tests for `TextChunker` in `src/processors/chunker.py`

| Test | What it Checks |
|------|----------------|
| `test_chunk_text_basic` | Chunks are created with required fields |
| `test_chunk_size_respected` | No chunk exceeds 800 chars |
| `test_overlap_working` | Consecutive chunks share content |
| `test_no_mid_sentence_cut_with_period` | Breaks at sentence boundaries |
| `test_paragraph_boundary_detection` | Respects paragraph breaks |
| `test_metadata_page_attached` | Page number preserved |
| `test_metadata_source_attached` | Source filename preserved |
| `test_chunk_documents_from_pages` | Handles page-structured docs |
| `test_chunk_documents_without_pages` | Handles flat content |
| `test_empty_text_handling` | Empty input returns empty list |
| `test_short_text_single_chunk` | Short text as single chunk |
| `test_chunk_id_unique` | Each chunk has unique ID |
| `test_boundary_priority` | Priority: `\n\n` → `\n` → `. ` |

### test_keyword_index.py
Tests for TF-IDF keyword search in `src/vectorstore/store.py`

| Test | What it Checks |
|------|----------------|
| `test_keyword_index_built` | Index is created |
| `test_keyword_lowercase_indexed` | Case-insensitive indexing |
| `test_stop | "the",_words_filtered` "over" not indexed |
| `test_content_words_indexed` | Medical terms indexed |
| `test_keyword_score_basic` | TF-IDF scoring works |
| `test_keyword_score_no_match` | Zero score for no match |
| `test_multiple_documents_indexing` | Multiple docs indexed |
| `test_stemming_implemented` | "run" matches "running" |
| `test_punctuation_handling` | LDL-C, commas handled |
| `test_numbers_not_indexed` | Pure numbers excluded |
| `test_tfidf_ranking` | Higher frequency = higher score |
| `test_acronyms_preserved` | LDL-C preserved (not stemmed) |
| `test_case_insensitive_query` | Query case handled |

### test_retrieval.py
Tests for hybrid search in `src/vectorstore/store.py`

| Test | What it Checks |
|------|----------------|
| `test_similarity_search_returns_results` | Returns non-empty list |
| `test_recall_at_5` | Relevant doc in top 5 (≥50%) |
| `test_mean_reciprocal_rank` | MRR > 0 |
| `test_hybrid_vs_keyword_only` | Hybrid mode works |
| `test_hybrid_vs_semantic_only` | Semantic-only works |
| `test_acronym_query_favors_keyword` | Acronyms work with keyword |
| `test_synonym_query_favors_semantic` | Synonyms work with semantic |
| `test_top_k_parameter` | top_k respected |
| `test_results_have_required_fields` | Fields: id, content, source, score |
| `test_score_ordering` | Results sorted by score descending |
| `test_empty_query_handling` | Empty query handled gracefully |
| `test_empty_store_handling` | Empty store returns [] |
| `test_weight_parameterization` | Custom weights work |

### test_embedding.py
Tests for Gemini embeddings in `src/vectorstore/store.py`

| Test | What it Checks |
|------|----------------|
| `test_embedding_dimension` | 3072-dim output |
| `test_batch_embedding_dimension` | Batch size handled |
| `test_embedding_consistency` | Same text = same embedding |
| `test_different_texts_different_embeddings` | Different text differs |
| `test_batch_latency_100_chunks` | 100 chunks < 60s |
| `test_batch_latency_1000_chunks` | 1000 chunks timing |
| `test_add_documents_stores_embeddings` | Embeddings persisted |
| `test_embedding_batch_size` | Batch parameter works |
| `test_empty_text_list` | Empty input handled |
| `test_single_char_embedding` | Single char works |
| `test_medical_term_embedding` | Medical terms work |

### test_pdf_loader.py
Tests for PDF loading in `src/ingest/__init__.py`

| Test | What it Checks |
|------|----------------|
| `test_load_all_pdfs_returns_list` | Returns list |
| `test_pdf_document_structure` | Has id, source, pages |
| `test_page_content_extraction` | Page has page# and content |
| `test_metadata_attachment` | Filename ends with .pdf |
| `test_extraction_integrity_sample` | Lipid doc contains LDL |
| `test_page_numbers_sequential` | Pages are ordered |
| `test_no_empty_pages` | No empty content |
| `test_get_documents_function` | Module function works |

### test_settings.py
Tests for configuration in `src/config/settings.py`

| Test | What it Checks |
|------|----------------|
| `test_settings_defaults` | Default values correct |
| `test_settings_custom_values` | Custom override works |

## API Key Requirement

Most tests require a valid `GEMINI_API_KEY` and will skip if set to `test-api-key`.
