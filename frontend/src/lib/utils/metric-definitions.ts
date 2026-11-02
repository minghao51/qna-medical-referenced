import type { MetricDisplayDefinition } from '../types';

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
	'ndcg_at_k': 'Legacy keyword/source ranking diagnostic; not interchangeable with reviewed-evidence nDCG or medical correctness.',
	'source_hit_rate': 'Percentage of queries that correctly identified the right source document.',
	'exact_chunk_hit_rate': 'Percentage of queries that retrieved the exact intended text chunk.',
	'evidence_hit_rate': 'Legacy evidence-match diagnostic; not proof of a correct or complete medical answer.',
	'latency_p50_ms': 'Median time taken to return search results (50% of requests are faster than this).',
	'latency_p95_ms': '95th percentile latency (only 5% of requests are slower than this).'
};

// Mirrors REQUIRED_ANSWER_METRICS, without importing backend/runtime code.
export const answerMetricKeys = [
	'factual_accuracy', 'completeness', 'clinical_relevance', 'clarity',
	'answer_relevancy', 'faithfulness'
] as const;

const answerMetricLabels: Record<string, string> = {
	factual_accuracy: 'Factual accuracy (judge)',
	completeness: 'Completeness (judge)',
	clinical_relevance: 'Clinical relevance (judge)',
	clarity: 'Clarity (judge)',
	answer_relevancy: 'Answer relevancy (judge)',
	faithfulness: 'Faithfulness (judge)'
};
const legacyRankingKeys = new Set([
	'ndcg_at_k', 'mrr', 'hit_rate_at_k', 'precision_at_k', 'recall_at_k',
	'source_hit_rate', 'exact_chunk_hit_rate', 'evidence_hit_rate'
]);
const reviewedEvidenceKeys = new Set([
	'evidence_ndcg_at_k', 'evidence_mrr', 'evidence_hit_rate_at_k',
	'evidence_precision_at_k', 'evidence_recall_at_k'
]);

export function getMetricDisplayDefinition(key: string): MetricDisplayDefinition {
	const label = key.replaceAll('_', ' ');
	if (Object.hasOwn(answerMetricLabels, key)) {
		return {
			definition_id: `answer-judgment:${key}`, label: answerMetricLabels[key],
			unit: 'score', direction: 'higher', family: 'answer_judgment'
		};
	}
	if (legacyRankingKeys.has(key) || reviewedEvidenceKeys.has(key)) {
		const reviewed = reviewedEvidenceKeys.has(key);
		return {
			definition_id: `${reviewed ? 'evidence-qrels' : 'legacy-diagnostic'}:${key}`,
			label: `${label} (${reviewed ? 'reviewed evidence' : 'legacy diagnostic'})`,
			unit: key.includes('ndcg') || key.includes('mrr') ? 'score' : 'ratio',
			direction: 'higher', family: reviewed ? 'reviewed_evidence' : 'ranking_diagnostic'
		};
	}
	if (key.endsWith('_ms')) {
		return { definition_id: `duration:${key}`, label, unit: 'ms', direction: 'lower', family: 'latency' };
	}
	if (key === 'metric_error_rate' || key === 'error_rate') {
		return { definition_id: `measurement:${key}`, label, unit: 'ratio', direction: 'lower', family: 'measurement' };
	}
	if (key.endsWith('_count') || key.startsWith('metric_evaluations_')) {
		return {
			definition_id: `count:${key}`, label, unit: 'count',
			direction: key === 'error_count' || key === 'metric_evaluations_failed' ? 'lower' : 'neutral',
			family: 'measurement'
		};
	}
	// Unknown metrics can be inspected, but have no assumed desirable direction.
	return { definition_id: `unspecified:${key}`, label, unit: 'number', direction: 'neutral', family: 'unspecified' };
}
