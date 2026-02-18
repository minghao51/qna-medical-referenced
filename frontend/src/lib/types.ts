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
}

export interface Message {
	role: 'user' | 'assistant';
	content: string;
	sources?: string[];
	pipeline?: PipelineTrace;
}
