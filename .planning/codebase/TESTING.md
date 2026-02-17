# Testing

## Test Framework

- **pytest** (>= 8.0.0) - Testing framework
- **pytest configuration** in `pyproject.toml`

## Running Tests

```bash
uv run pytest tests/ -v
```

## Test Files

### test_chunker.py (14 tests)
Tests for `TextChunker` in `src/processors/chunker.py`

| Test | What it Checks |
|------|----------------|
| test_chunk_text_basic | Chunks created with required fields |
| test_chunk_size_respected | No chunk exceeds chunk_size |
| test_overlap_working | Consecutive chunks share content |
| test_no_mid_sentence_cut_with_period | Breaks at sentence boundaries |
| test_paragraph_boundary_detection | Respects paragraph breaks |
| test_metadata_page_attached | Page number preserved |
| test_metadata_source_attached | Source filename preserved |
| test_chunk_documents_from_pages | Handles page-structured docs |
| test_chunk_documents_without_pages | Handles flat content |
| test_empty_text_handling | Empty input returns empty list |
| test_short_text_single_chunk | Short text as single chunk |
| test_chunk_id_unique | Each chunk has unique ID |
| test_boundary_priority | Priority: \n\n → \n → . |
| test_chunk_documents_function | Module function works |

### test_keyword_index.py (13 tests)
Tests for TF-IDF keyword search in `src/vectorstore/store.py`

| Test | What it Checks |
|------|----------------|
| test_keyword_index_built | Index is created |
| test_keyword_lowercase_indexed | Case-insensitive indexing |
| test_stop_words_filtered | Stop words not indexed |
| test_content_words_indexed | Medical terms indexed |
| test_keyword_score_basic | TF-IDF scoring works |
| test_keyword_score_no_match | Zero score for no match |
| test_multiple_documents_indexing | Multiple docs indexed |
| test_stemming_implemented | Stemming works |
| test_punctuation_handling | Punctuation handled |
| test_numbers_not_indexed | Pure numbers excluded |
| test_tfidf_ranking | Higher frequency = higher score |
| test_acronyms_preserved | Acronyms preserved |
| test_case_insensitive_query | Query case handled |

### test_retrieval.py (16 tests)
Tests for hybrid search in `src/vectorstore/store.py`

| Test | What it Checks |
|------|----------------|
| test_similarity_search_returns_results | Returns non-empty list |
| test_recall_at_5 | Relevant doc in top 5 |
| test_mean_reciprocal_rank | MRR > 0 |
| test_hybrid_vs_keyword_only | Hybrid mode works |
| test_hybrid_vs_semantic_only | Semantic-only works |
| test_acronym_query_favors_keyword | Acronyms work |
| test_synonym_query_favors_semantic | Synonyms work |
| test_top_k_parameter | top_k respected |
| test_results_have_required_fields | Required fields present |
| test_score_ordering | Results sorted descending |
| test_empty_query_handling | Empty query handled |
| test_empty_store_handling | Empty store returns [] |
| test_weight_parameterization | Custom weights work |

### test_embedding.py (11 tests)
Tests for Gemini embeddings in `src/vectorstore/store.py`

| Test | What it Checks |
|------|----------------|
| test_embedding_dimension | 3072-dim output |
| test_batch_embedding_dimension | Batch size handled |
| test_embedding_consistency | Same text = same embedding |
| test_different_texts_different_embeddings | Different text differs |
| test_batch_latency_100_chunks | 100 chunks < 60s |
| test_add_documents_stores_embeddings | Embeddings persisted |
| test_embedding_batch_size | Batch parameter works |
| test_empty_text_list | Empty input handled |
| test_single_char_embedding | Single char works |
| test_medical_term_embedding | Medical terms work |

### test_pdf_loader.py (8 tests)
Tests for PDF loading in `src/ingest/__init__.py`

| Test | What it Checks |
|------|----------------|
| test_load_all_pdfs_returns_list | Returns list |
| test_pdf_document_structure | Has id, source, pages |
| test_page_content_extraction | Page has page# and content |
| test_metadata_attachment | Filename ends with .pdf |
| test_extraction_integrity_sample | Lipid doc contains LDL |
| test_page_numbers_sequential | Pages are ordered |
| test_no_empty_pages | No empty content |
| test_get_documents_function | Module function works |

### test_settings.py (2 tests)
Tests for configuration in `src/config/settings.py`

| Test | What it Checks |
|------|----------------|
| test_settings_defaults | Default values correct |
| test_settings_custom_values | Custom override works |

## Test Requirements

- Valid `GEMINI_API_KEY` required for most tests
- Tests skip if API key is `test-api-key`
- Total: 64 tests

## Key Test Features

- API key validation via fixture
- Vector store cleanup between tests
- Performance timing for embeddings
- Recall@K and MRR metrics for retrieval
