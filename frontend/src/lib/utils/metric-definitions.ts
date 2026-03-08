// Human-readable definitions for various pipeline and retrieval metrics

export const stageNames: Record<string, string> = {
	'L0': 'L0: HTML Processing',
	'L1': 'L1: Content Cleaning',
	'L2': 'L2: PDF Extraction',
	'L3': 'L3: Document Chunking',
	'L4': 'L4: Structured Data',
	'L5': 'L5: Vector Indexing',
	'L6': 'L6: Retrieval Performance'
};

export const metricDefinitions: Record<string, string> = {
	// L0
	'html_file_count': 'Total number of raw HTML files processed.',
	'html_parse_success_rate': 'Percentage of HTML files successfully parsed into raw text.',
	'duplicate_file_rate': 'Percentage of files that contain purely duplicate content.',
	'small_file_rate': 'Percentage of files that are unusually small and likely useless.',
	'manifest_inventory_record_count': 'Number of records successfully registered in the inventory.',
	
	// L1
	'pairs_evaluated': 'Number of (HTML, Markdown) pairs analyzed for quality.',
	'markdown_empty_rate': 'Percentage of converted markdown files that resulted in empty content.',
	'retention_ratio_mean': 'Average ratio of text kept after cleaning out HTML tags and junk.',
	'content_density_mean': 'Ratio of useful information vs. total text characters. Higher is better.',
	'boilerplate_ratio_mean': 'Percentage of text identified as navigation, footers, or layout noise.',
	'heading_preservation_rate_mean': 'How well structural headings (H1, H2) were preserved during conversion.',
	'table_preservation_rate_mean': 'How well data tables survived the markdown conversion process.',
	
	// L2
	'pdf_file_count': 'Total number of PDF documents processed.',
	'page_extraction_coverage': 'Percentage of total PDF pages successfully extracted.',
	'empty_page_rate': 'Percentage of pages that resulted in zero text.',
	'extractor_fallback_rate': 'How often the system had to use a heavier fallback method (like OCR) to read a page.',
	'low_confidence_page_rate': 'Percentage of pages where text extraction confidence is low.',
	'ocr_required_rate': 'Percentage of pages that required full Optical Character Recognition (scanned pages).',

	// L3
	'document_count': 'Total unique documents ready for chunking.',
	'chunk_count': 'Total number of text snippets created for the search index.',
	'duplicate_chunk_rate': 'Percentage of identical chunks (can happen from boilerplate).',
	'boundary_cut_rate': 'How often a chunk split cut a sentence or paragraph awkwardly.',
	'observed_overlap_mean': 'Average percentage of overlapping text between adjacent chunks (for context).',
	'table_row_split_violations': 'Number of times a table row was wrongly split across two chunks.',
	'section_integrity_rate': 'How well chunks respect logical document sections (like chapters).',
	'low_quality_chunk_exclusion_rate': 'Percentage of chunks discarded because they contained mostly junk.',

	// L4
	'csv_exists': 'Whether structured CSV data inputs were found.',
	'row_count': 'Total number of data rows ingested.',
	'row_completeness_rate': 'Average completeness of rows (lack of empty fields).',

	// L5
	'ids_count': 'Total number of individual vectors (embeddings) generated and stored.',
	'embedding_dim': 'The mathematical size of the vector representation (e.g., 1536).',
	'embedding_dim_consistent': 'Whether all vectors share the exact same dimensionality.',
	'short_content_rate': 'Percentage of items indexed that have very short content.',
	'index_file_size_bytes': 'The total storage size of the vector database index.',

	// L6 (Retrieval)
	'query_count': 'Total number of test queries run against the search system.',
	'hit_rate_at_k': 'Percentage of queries where the CORRECT answer appeared in the top K results.',
	'mrr': 'Mean Reciprocal Rank: How high up the list the FIRST relevant result appears (1.0 = 1st, 0.5 = 2nd, etc).',
	'precision_at_k': 'Percentage of the top K results that are actually relevant.',
	'recall_at_k': 'Percentage of ALL relevant chunks that were successfully found in the top K results.',
	'ndcg_at_k': 'Graded ranking quality: gives much higher scores when the BEST results are strictly at the top.',
	'source_hit_rate': 'Percentage of queries that correctly identified the right source document.',
	'exact_chunk_hit_rate': 'Percentage of queries that retrieved the exact intended text chunk.',
	'evidence_hit_rate': 'Percentage of queries that retrieved enough evidence to fully answer the question.',
	'latency_p50_ms': 'Median time taken to return search results (50% of requests are faster than this).',
	'latency_p95_ms': '95th percentile latency (only 5% of requests are slower than this).'
};
