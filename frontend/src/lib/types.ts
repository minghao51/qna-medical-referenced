/** Pipeline lineage visualization types */

export interface RetrievedDocument {
	id: string;
	content: string;
	source: string;
	page?: number;
	semantic_score: number;
	keyword_score: number;
	source_boost: number;
	combined_score: number;
	rank: number;
}

export interface RetrievalStage {
	query: string;
	top_k: number;
	documents: RetrievedDocument[];
	score_weights: {
		semantic: number;
		keyword: number;
		source: number;
	};
	timing_ms: number;
}

export interface ContextStage {
	total_chunks: number;
	total_chars: number;
	sources: string[];
	preview: string;
}

export interface GenerationStage {
	model: string;
	timing_ms: number;
	tokens_estimate?: number;
}

export interface PipelineTrace {
	retrieval: RetrievalStage;
	context: ContextStage;
	generation: GenerationStage;
	total_time_ms: number;
	overallConfidence?: number;
	stageStatus?: {
		retrieval: 'success' | 'warning' | 'error';
		context: 'success' | 'warning' | 'error';
		generation: 'success' | 'warning' | 'error';
	};
}

export interface Message {
	role: 'user' | 'assistant';
	content: string;
	sources?: string[];
	pipeline?: PipelineTrace;
	timestamp?: number;
}

export interface EvaluationSummary {
	run_dir: string;
	duration_s: number;
	retrieval_metrics: RetrievalMetrics;
	rag_metrics: RagMetrics;
	failed_thresholds_count: number;
	status: 'ok' | 'failed';
	tracking?: Record<string, any>;
}

export interface RetrievalMetrics {
	query_count: number;
	hit_rate_at_k: number;
	precision_at_k: number;
	recall_at_k: number;
	mrr: number;
	ndcg_at_k: number;
	source_hit_rate: number;
	exact_chunk_hit_rate: number;
	evidence_hit_rate: number;
	latency_p50_ms: number;
	latency_p95_ms: number;
	hit_rate_at_k_high_conf: number;
	mrr_high_conf: number;
	// Advanced deduplication & diversity metrics
	dedup_hit_rate_at_k?: number;
	dedup_precision_at_k?: number;
	dedup_mrr?: number;
	unique_source_hit_rate_at_k?: number;
	unique_source_precision_at_k?: number;
	duplicate_source_ratio_mean?: number;
	duplicate_doc_ratio_mean?: number;
	// High-confidence subset metrics
	exact_chunk_hit_rate_high_conf?: number;
	evidence_hit_rate_high_conf?: number;
	topic_false_positive_rate?: number;
}

export interface RagMetrics {
	status: string;
	reason?: string;
	query_count?: number;
	relevance_score_mean?: number;
	faithfulness_score_mean?: number;
}

export interface StepMetrics {
	aggregate: Record<string, any>;
	// L0: html_file_count, html_parse_success_rate, duplicate_file_rate, small_file_rate
	// L1: pairs_evaluated, markdown_empty_rate, retention_ratio_mean, content_density_mean,
	//      boilerplate_ratio_mean, heading_preservation_rate_mean, table_preservation_rate_mean,
	//      page_classification_distribution
	// L2: pdf_file_count, page_extraction_coverage, empty_page_rate, extractor_fallback_rate,
	//      low_confidence_page_rate, ocr_required_rate, replacement_char_count
	// L3: document_count, chunk_count, duplicate_chunk_rate, boundary_cut_rate,
	//      chunk_quality_histogram, section_integrity_rate, low_quality_chunk_exclusion_rate,
	//      table_row_split_violations
	// L4: csv_exists, row_count, row_completeness_rate, duplicate_test_name_rate,
	//      normal_range_parseable_rate
	// L5: ids_count, embedding_dim, embedding_dim_consistent, short_content_rate
	records: any[];
	findings: Array<{
		severity: 'warning' | 'error';
		stage: string;
		message: string;
	}>;
}

export interface ChunkQualityHistogram {
	high: number;
	medium: number;
	low: number;
}

export interface PageClassificationDistribution {
	article?: number;
	faq?: number;
	'navigation-heavy'?: number;
	'index/listing'?: number;
	unknown?: number;
}

export interface EvaluationResponse {
	run_dir: string;
	summary?: EvaluationSummary;
	step_metrics?: Record<string, StepMetrics>;
	retrieval_metrics?: RetrievalMetrics;
	manifest?: Record<string, any>;
	source?: string;
	tracking?: Record<string, any>;
	wandb_run_id?: string;
	wandb_url?: string;
}

export interface EvaluationHistoryRun {
	run_dir: string;
	timestamp: string;
	status?: string;
	duration_s?: number;
	failed_thresholds_count?: number;
	retrieval_metrics?: Partial<RetrievalMetrics>;
	source: 'local' | 'wandb' | string;
	experiment_name?: string;
	variant_name?: string;
	index_config_hash?: string;
	wandb_url?: string;
	wandb_run_id?: string;
	tracking?: Record<string, any>;
}

export interface EvaluationHistoryResponse {
	runs: EvaluationHistoryRun[];
	summary: {
		total_runs: number;
		avg_hit_rate: number;
		avg_mrr: number;
		avg_latency_p50: number;
		avg_duration: number;
		sources?: Record<string, number>;
	};
	sources?: {
		mode: string;
		wandb?: {
			status?: string;
			project?: string | null;
			entity?: string | null;
		};
	};
	warnings?: string[];
}
