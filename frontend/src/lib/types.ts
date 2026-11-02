/** Pipeline lineage visualization types */

export interface RetrievedDocument {
	id: string;
	content: string;
	source: string;
	page?: number;
	semantic_score: number;
	keyword_score: number;
	source_prior?: number;
	source_boost: number;
	combined_score: number;
	rank: number;
	semantic_rank?: number;
	bm25_rank?: number;
	fused_rank?: number;
	fused_score?: number;
	chunk_quality_score?: number;
	content_type?: string;
	section_path?: string[];
	canonical_label?: string;
	display_label?: string;
	logical_name?: string;
	source_url?: string;
	source_type?: string;
	source_class?: string;
	domain?: string;
	domain_type?: SourceDomainType;
}

export interface RetrievalStep {
	name: string;
	timing_ms: number;
	skipped: boolean;
	details: Record<string, unknown>;
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
	steps: RetrievalStep[];
}

export interface ContextStage {
	total_chunks: number;
	total_chars: number;
	sources: string[];
	preview: string;
}

export interface ChatSource {
	canonical_label: string;
	display_label: string;
	source_url?: string;
	source_type?: string;
	source_class?: string;
	domain?: string;
	domain_type?: SourceDomainType;
	label: string;
	source: string;
	url?: string;
	page?: number;
	content_type?: string;
}

export type SourceDomainType = 'government' | 'education' | 'organization' | 'commercial' | 'unknown';

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

export type MessageStatus = 'pending' | 'complete' | 'incomplete' | 'error';

export interface Message {
	role: 'user' | 'assistant';
	content: string;
	sources?: Array<ChatSource | string>;
	pipeline?: PipelineTrace;
	timestamp?: number;
	status?: MessageStatus;
}

export interface ApiErrorPayload {
	detail?: string;
	error?: {
		code?: string;
		status_code?: number;
		request_id?: string | null;
		extra?: Record<string, unknown>;
	};
}

export interface HealthResponse {
	status: 'healthy' | 'degraded' | 'unhealthy';
	ready: boolean;
	runtime?: Record<string, unknown>;
	vector_store?: {
		initialized?: boolean;
		signature?: string | null;
		config?: Record<string, unknown>;
	};
	rate_limit?: {
		backend?: string;
		window_seconds?: number | null;
	};
}

export interface EvaluationSummary {
	run_dir: string;
	duration_s?: number | null;
	retrieval_metrics: RetrievalMetrics;
	l6_answer_quality_metrics: L6AnswerQualityMetrics;
	l6_answer_quality_enabled?: boolean;
	l6_answer_quality_status?: string;
	failed_thresholds_count?: number | null;
	status?: string | null;
	tracking?: Record<string, unknown>;
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
	// HyDe (Hypothetical Document Embeddings) metrics
	hyde_enabled?: boolean;
	hyde_queries_count?: number;
	hyde_hit_rate?: number;
	hyde_mrr?: number;
	hyde_source_hit_rate?: number;
}

export interface L6AnswerQualityMetric {
	mean: number;
	count: number;
	error_count?: number;
	error_rate?: number;
}

export interface L6AnswerQualityMetrics {
	status: string;
	reason?: string;
	query_count?: number;
	query_count_scored?: number;
	metric_evaluations_total?: number;
	metric_evaluations_ok?: number;
	metric_evaluations_failed?: number;
	metric_error_rate?: number;
	factual_accuracy?: L6AnswerQualityMetric;
	completeness?: L6AnswerQualityMetric;
	clinical_relevance?: L6AnswerQualityMetric;
	clarity?: L6AnswerQualityMetric;
	answer_relevancy?: L6AnswerQualityMetric;
	faithfulness?: L6AnswerQualityMetric;
}

export interface StepMetrics {
	aggregate: Record<string, unknown>;
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
	records: Array<Record<string, unknown>>;
	findings: Array<{
		severity: 'warning' | 'error';
		stage: string;
		message: string;
	}>;
}

export interface StepFinding {
	severity: 'warning' | 'error';
	stage: string;
	message: string;
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

export interface SourceChunkConfig {
	chunk_size: number;
	chunk_overlap: number;
	min_chunk_size: number;
}

export interface IngestionStrategyConfig {
	page_classification_enabled?: boolean;
	index_only_classified_pages?: boolean;
	html_extractor_mode?: string;
	html_extractor_strategy?: string;
	pdf_extractor_strategy?: string;
	pdf_table_extractor?: string;
	structured_chunking_enabled?: boolean;
	source_chunk_configs?: Record<string, SourceChunkConfig>;
	enable_hype?: boolean;
	hype_sample_rate?: number;
}

export interface RetrievalStrategyConfig {
	top_k?: number;
	search_mode?: string;
	enable_diversification?: boolean;
	mmr_lambda?: number;
	overfetch_multiplier?: number;
	max_chunks_per_source_page?: number;
	max_chunks_per_source?: number;
	enable_hyde?: boolean;
	hyde_max_length?: number;
}

export interface ExperimentConfig {
	ingestion?: IngestionStrategyConfig;
	retrieval?: RetrievalStrategyConfig;
	metadata?: {
		name?: string;
		description?: string;
		tags?: string[];
	};
}

export interface EvaluationResponse {
	run_dir: string;
	summary?: EvaluationSummary;
	step_metrics?: Record<string, StepMetrics>;
	retrieval_metrics?: RetrievalMetrics;
	failed_thresholds?: FailedThreshold[];
	manifest?: Record<string, unknown>;
	source?: string;
	tracking?: Record<string, unknown>;
	wandb_run_id?: string;
	wandb_url?: string;
	experiment_config?: ExperimentConfig;
}

export interface FailedThreshold {
	metric?: string;
	value?: number | string | boolean | null;
	threshold_op?: 'min' | 'max' | string;
	threshold_value?: number;
	message?: string;
	severity?: 'warning' | 'error' | string;
}

export interface EvaluationHistoryRun {
	run_dir: string;
	timestamp: string;
	status?: string;
	comparable: false;
	artifact_compatibility?: 'legacy' | 'versioned' | 'unsupported';
	duration_s?: number | null;
	failed_thresholds_count?: number | null;
	retrieval_metrics?: { [K in keyof RetrievalMetrics]?: RetrievalMetrics[K] | null };
	l6_answer_quality_metrics?: Record<string, unknown>;
	source: 'local' | 'wandb' | string;
	experiment_name?: string;
	variant_name?: string;
	index_config_hash?: string;
	wandb_url?: string;
	wandb_run_id?: string;
	tracking?: Record<string, unknown>;
}

export interface EvaluationHistoryResponse {
	runs: EvaluationHistoryRun[];
	summary: {
		total_runs: number;
		avg_hit_rate: number | null;
		avg_mrr: number | null;
		avg_latency_p50: number | null;
		avg_duration: number | null;
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

export interface AblationRun {
	strategy: string;
	hit_rate_at_k: number;
	mrr: number;
	ndcg_at_k: number;
	latency_p50_ms?: number;
	is_baseline: boolean;
}

export interface AblationResponse {
	ablation_runs: AblationRun[];
	message?: string;
}

export interface FullAblationRun {
	variant: string;
	run_dir: string;
	chunks_attempted?: number;
	chunks_inserted?: number;
	chunks_duplicate?: number;
	ndcg_at_k?: number;
	mrr?: number;
	hit_rate_at_k?: number;
	precision_at_k?: number;
	recall_at_k?: number;
	latency_p50_ms?: number;
	delta_ndcg?: number;
}

export interface AblationFinding {
	title: string;
	detail: string;
	impact: 'high' | 'medium' | 'low';
}

export interface FullAblationResponse {
	runs: FullAblationRun[];
	dimensions: Record<string, FullAblationRun[]>;
	findings: AblationFinding[];
	optimal_variant: string;
	baseline_variant: string;
	total_variants: number;
	message?: string;
}

export interface DrillDownPoint {
	timestamp: string;
	value: number;
}

export type DrillDownRecord = Record<string, unknown>;

export type EvalTrendMetric = 'hit_rate' | 'mrr' | 'latency';

export type EvalTabId = 'ingestion' | 'retrieval' | 'quality' | 'trending' | 'advanced';

export interface RuntimeRetrievalConfig {
	search_mode: string;
	enable_diversification: boolean;
	mmr_lambda: number;
	overfetch_multiplier: number;
	max_chunks_per_source_page: number;
	max_chunks_per_source: number;
	top_k: number;
	enable_hyde: boolean;
	hyde_max_length: number;
	enable_hype: boolean;
	enable_reranking: boolean;
	reranking_mode: string;
	enable_medical_expansion: boolean;
	medical_expansion_provider: string;
	enable_query_understanding: boolean;
}

export interface RuntimeIngestionConfig {
	structured_chunking_enabled: boolean;
	page_classification_enabled: boolean;
	html_extractor_strategy: string;
	pdf_extractor_strategy: string;
}

export interface RuntimeEnrichmentConfig {
	enable_keyword_extraction: boolean;
	enable_chunk_summaries: boolean;
}

export interface RuntimeLlmConfig {
	provider: string;
	model_name: string;
	embedding_model: string;
}

export interface RuntimeConfig {
	retrieval: RuntimeRetrievalConfig;
	ingestion: RuntimeIngestionConfig;
	enrichment: RuntimeEnrichmentConfig;
	llm: RuntimeLlmConfig;
	production_profile: string | null;
}

export interface ExperimentConfigSummary {
	file: string;
	experiment_id: string;
	name: string;
	description: string;
	variant_count: number;
	primary_metric: string | null;
	has_results: boolean;
	availability?: 'available' | 'error';
	error?: string;
}

export type ResearchSchemaKind = 'legacy_feature_addition' | 'unsupported';

export interface ExperimentArtifact {
	report_id: string;
	report_sha256: string | null;
	schema_kind: ResearchSchemaKind;
	availability: 'available' | 'unavailable';
	config_ref: string | null;
	config_binding: 'explicit_archive_association' | null;
	case_records_availability: 'not_exposed_by_report_api';
	comparable: false;
}

export type MetricDirection = 'higher' | 'lower' | 'neutral';
export type MetricUnit = 'score' | 'ratio' | 'ms' | 'count' | 'number';
export type MetricFamily =
	| 'ranking_diagnostic'
	| 'reviewed_evidence'
	| 'answer_judgment'
	| 'latency'
	| 'measurement'
	| 'unspecified';

export interface MetricDisplayDefinition {
	definition_id: string;
	label: string;
	unit: MetricUnit;
	direction: MetricDirection;
	family: MetricFamily;
}

export type CoverageState = 'complete' | 'partial' | 'not_recorded' | 'inconsistent';
export type CoverageExpectedBasis = 'recorded' | 'legacy_one_slot_per_query' | 'unknown';
export type CoverageReason =
	| 'invalid_metric_shape'
	| 'invalid_mean'
	| 'invalid_count'
	| 'missing_mean'
	| 'mean_without_measurements'
	| 'counts_exceed_expected'
	| 'unaccounted_slots'
	| 'counts_not_recorded'
	| 'expected_not_recorded'
	| 'no_expected_measurements';

export interface MetricCoverage extends MetricDisplayDefinition {
	metric_key: string;
	mean: number | null;
	measured_slots: number | null;
	expected_slots: number | null;
	failed_slots: number | null;
	skipped_slots: number | null;
	errored_cases: number | null;
	expected_basis: CoverageExpectedBasis;
	coverage_state: CoverageState;
	reason_codes: CoverageReason[];
}

export interface MetricCoverageTotals {
	measured_slots: number | null;
	expected_slots: number | null;
	failed_slots: number | null;
	skipped_slots: number | null;
	coverage_state: CoverageState;
}

export interface LegacyArchiveVariant {
	name: string;
	role: 'baseline' | 'variant';
	measurement_status: string | null;
	query_count: number | null;
	answer_metrics: MetricCoverage[];
	coverage_totals: MetricCoverageTotals;
}

export interface LegacyArchiveProjection {
	schema_kind: ResearchSchemaKind;
	report_id: string | null;
	report_sha256: string | null;
	identity_status: 'byte_revision_recorded' | 'unverified';
	config_ref: string | null;
	config_binding: 'explicit_archive_association' | null;
	comparable: false;
	historical_binding: 'not_established';
	declared_winner: string | null;
	variants: LegacyArchiveVariant[];
}

export interface MetricDelta {
	absolute: number | null;
	relative_percent: number | null;
	absolute_label: string;
	relative_label: string;
	favorability: 'improved' | 'worsened' | 'unchanged' | 'unknown';
}

export interface ExperimentReportSummary {
	file: string;
	report_id?: string;
	report_sha256?: string | null;
	schema_kind?: ResearchSchemaKind;
	availability?: 'available' | 'unavailable' | 'unsupported' | 'error';
	error?: string;
	config_ref?: string | null;
	experiment_name?: string;
	timestamp?: string;
	winner?: string | null;
	any_target_met?: boolean | null;
}

export interface ExperimentListResponse {
	configs: ExperimentConfigSummary[];
	reports: ExperimentReportSummary[];
}

export interface ExperimentVariantResult {
	name: string;
	run_dir: string;
	metrics: Record<string, unknown>;
	meets_target?: boolean;
}

export interface ExperimentReport {
	_artifact?: ExperimentArtifact;
	experiment_name: string;
	timestamp: string;
	config: Record<string, unknown>;
	baseline: ExperimentVariantResult;
	variants: ExperimentVariantResult[];
	winner: ExperimentVariantResult | null;
	primary_metric: string;
	target_improvement: number;
	any_target_met: boolean;
}

export interface ParsedExperimentConfig {
	schema_version: number;
	metadata: { name: string; description: string; tags: string[] };
	ingestion: Record<string, unknown>;
	retrieval: Record<string, unknown>;
	embedding_index: Record<string, unknown>;
	dataset: Record<string, unknown>;
	evaluation: Record<string, unknown>;
	variants: Array<{ name: string; overrides?: Record<string, unknown> }>;
	experiment_file: string;
}

export type CatalogAvailability =
	| 'available'
	| 'missing'
	| 'malformed'
	| 'unsupported'
	| 'inventory_reference';

export type CatalogKind =
	| 'query_fixture'
	| 'conversation_fixture'
	| 'review_dataset'
	| 'reference_csv'
	| 'retrieval_index';

export interface ResearchCatalogEntry {
	catalog_id: string;
	label: string;
	kind: CatalogKind;
	availability: CatalogAvailability;
	availability_reason: string | null;
	origin_ref: string;
	revision_sha256: string | null;
	record_unit: 'question' | 'conversation' | 'case' | 'row' | 'chunk';
	record_count: number | null;
	turn_count: number | null;
	split_counts: Record<string, number> | null;
	label_confidence_counts: Record<string, number> | null;
	raw_review_status_counts: Record<string, number> | null;
	review_status_missing_count: number | null;
	review_authority: 'not_assessed' | 'manifest_declared_not_authenticated';
	case_projection: 'available' | 'summary_only' | 'unavailable';
	inventory_ref: string | null;
}

export interface ResearchCatalogOverlap {
	left_catalog_id: string;
	left_revision: string;
	right_catalog_id: string;
	right_revision: string;
	method: 'exact_stored_query_text';
	left_unique_query_count: number;
	right_unique_query_count: number;
	intersection_unique_query_count: number;
	normalization: 'none';
	near_duplicate_status: 'not_assessed';
}

export interface ResearchCatalogResponse {
	datasets: ResearchCatalogEntry[];
	overlap: ResearchCatalogOverlap[];
}

export interface ResearchCaseLocator {
	revision_sha256: string;
	source_ordinal: number;
}

export interface ResearchStoredTurn {
	role: string | null;
	content: string | null;
}

export interface ResearchCatalogCase {
	locator: ResearchCaseLocator;
	source_case_id: string | null;
	question: string | null;
	expected_keywords: string[] | null;
	expected_source_labels: string[] | null;
	split: string | null;
	difficulty: string | null;
	query_category: string | null;
	source_family: string | null;
	topic: string | null;
	label_confidence: string | null;
	raw_review_status: string | null;
	normalized_review_status: string | null;
	stored_turns: ResearchStoredTurn[] | null;
}

export interface ResearchCatalogCasesResponse {
	catalog_id: string;
	revision_sha256: string;
	total: number;
	offset: number;
	limit: number;
	items: ResearchCatalogCase[];
}

export interface DocumentListItem {
	id: string;
	source: string;
	page: number | null;
	source_type: string;
	source_class: string;
	content_type: string;
	content_preview: string;
	content_length: number;
	canonical_label?: string | null;
	display_label?: string | null;
	logical_name?: string | null;
	source_url?: string | null;
	domain?: string | null;
}

export interface DocumentListResponse {
	total: number;
	offset: number;
	limit: number;
	items: DocumentListItem[];
	source_type_counts: Record<string, number>;
	global_source_type_counts?: Record<string, number>;
	index_metadata?: Record<string, unknown>;
	index_identity?: string | null;
}

export interface DocumentDetailResponse {
	id: string;
	content: string;
	metadata: Record<string, unknown>;
	content_length: number;
	canonical_label?: string | null;
	display_label?: string | null;
	logical_name?: string | null;
	source_url?: string | null;
	domain?: string | null;
	source_type?: string | null;
	source_class?: string | null;
	page?: number | null;
}

export interface EvaluationRunSummary {
	run_dir: string;
	status: string;
	duration_s: number;
	failed_thresholds_count: number;
}

export interface StepRecordsResponse {
	stage: string;
	records: Array<Record<string, unknown>>;
	total_count: number;
}

export interface L6RecordsResponse {
	records: Array<Record<string, unknown>>;
	total_count: number;
}

export interface AnswerQualityMetric {
	score: number;
	reason: string | null;
}

export interface AnswerQualityRecord {
	query_id: string;
	query: string;
	answer: string;
	metrics: Record<string, AnswerQualityMetric>;
}

export interface AnswerQualityResponse {
	run_dir: string;
	results: AnswerQualityRecord[];
}
