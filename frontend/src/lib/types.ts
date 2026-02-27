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
	records: any[];
	findings: Array<{
		severity: 'warning' | 'error';
		stage: string;
		message: string;
	}>;
}

export interface EvaluationResponse {
	run_dir: string;
	summary?: EvaluationSummary;
	step_metrics?: Record<string, StepMetrics>;
	retrieval_metrics?: RetrievalMetrics;
	manifest?: Record<string, any>;
}
