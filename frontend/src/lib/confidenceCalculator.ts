import type {
	ContextStage,
	GenerationStage,
	PipelineTrace,
	RetrievalStage,
	RetrievedDocument,
	SourceDomainType
} from './types';

export type ConfidenceLevel = 'high' | 'medium' | 'low';

export interface ConfidenceScore {
	overall: number;
	level: ConfidenceLevel;
	breakdown: {
		retrieval: number;
		sourceQuality: number;
		contextRelevance: number;
		generationSuccess: number;
	};
}

export type DomainType = SourceDomainType;

export function getDomainType(source: string): DomainType {
	try {
		const url = new URL(source.startsWith('http') ? source : `https://${source}`);
		const hostname = url.hostname.toLowerCase();
		
		if (hostname.endsWith('.gov') || hostname.includes('.gov.')) {
			return 'government';
		}
		if (hostname.endsWith('.edu') || hostname.includes('.edu.')) {
			return 'education';
		}
		if (hostname.endsWith('.org')) {
			return 'organization';
		}
		if (hostname.endsWith('.com')) {
			return 'commercial';
		}
		return 'unknown';
	} catch {
		return 'unknown';
	}
}

export function getDomainCredibilityScore(domainType: DomainType): number {
	const scores: Record<DomainType, number> = {
		government: 100,
		education: 95,
		organization: 70,
		commercial: 40,
		unknown: 30
	};
	return scores[domainType];
}

export function calculateSourceQuality(sources: string[]): number {
	if (!sources || sources.length === 0) {
		return 30;
	}
	
	const credibilityScores = sources.map(source => {
		const domainType = getDomainType(source);
		return getDomainCredibilityScore(domainType);
	});
	
	const avgCredibility = credibilityScores.reduce((a, b) => a + b, 0) / credibilityScores.length;
	
	const sourceBonus = Math.min(sources.length * 5, 20);
	
	return Math.min(avgCredibility + sourceBonus, 100);
}

export function calculateRetrievalScore(documents: RetrievedDocument[]): number {
	if (!documents || documents.length === 0) {
		return 20;
	}
	
	const avgCombinedScore = documents.reduce((sum, doc) => sum + doc.combined_score, 0) / documents.length;
	const scorePercent = avgCombinedScore * 100;
	
	const documentCountBonus = Math.min(documents.length * 5, 15);
	
	const topScoreBonus = documents.length > 0 ? documents[0].combined_score * 20 : 0;
	
	return Math.min(scorePercent * 0.7 + documentCountBonus + topScoreBonus, 100);
}

export function calculateContextRelevance(context: ContextStage): number {
	if (!context) {
		return 30;
	}
	
	const chunkScore = Math.min(context.total_chunks / 5 * 30, 30);
	const charScore = Math.min(context.total_chars / 3000 * 30, 30);
	const sourceScore = Math.min(context.sources.length * 10, 40);
	
	return Math.min(chunkScore + charScore + sourceScore, 100);
}

export function calculateGenerationSuccess(generation: GenerationStage): number {
	if (!generation) {
		return 50;
	}
	
	const hasModel = generation.model ? 30 : 0;
	const reasonableTiming = generation.timing_ms < 30000 ? 30 : 15;
	const hasTokens = generation.tokens_estimate ? 20 : 10;
	const reasonableTokens = generation.tokens_estimate 
		? (generation.tokens_estimate < 2000 ? 20 : 10)
		: 0;
	
	return Math.min(hasModel + reasonableTiming + hasTokens + reasonableTokens, 100);
}

export function calculateConfidence(pipeline: PipelineTrace | null | undefined): ConfidenceScore {
	if (!pipeline) {
		return {
			overall: 50,
			level: 'medium',
			breakdown: {
				retrieval: 50,
				sourceQuality: 50,
				contextRelevance: 50,
				generationSuccess: 50
			}
		};
	}
	
	const retrieval = calculateRetrievalScore(pipeline.retrieval?.documents || []);
	const sourceQuality = calculateSourceQuality(pipeline.context?.sources || []);
	const contextRelevance = calculateContextRelevance(pipeline.context);
	const generationSuccess = calculateGenerationSuccess(pipeline.generation);
	
	const overall = Math.round(
		retrieval * 0.4 +
		sourceQuality * 0.3 +
		contextRelevance * 0.2 +
		generationSuccess * 0.1
	);
	
	let level: ConfidenceLevel;
	if (overall >= 75) {
		level = 'high';
	} else if (overall >= 40) {
		level = 'medium';
	} else {
		level = 'low';
	}
	
	return {
		overall,
		level,
		breakdown: {
			retrieval: Math.round(retrieval),
			sourceQuality: Math.round(sourceQuality),
			contextRelevance: Math.round(contextRelevance),
			generationSuccess: Math.round(generationSuccess)
		}
	};
}

export function getStageStatus(
	retrieval: RetrievalStage | undefined,
	context: ContextStage | undefined,
	generation: GenerationStage | undefined
): {
	retrieval: 'success' | 'warning' | 'error';
	context: 'success' | 'warning' | 'error';
	generation: 'success' | 'warning' | 'error';
} {
	const getHigherBetterStatus = (
		score: number | undefined,
		thresholdHigh: number,
		thresholdLow: number
	): 'success' | 'warning' | 'error' => {
		if (score === undefined) return 'error';
		if (score >= thresholdHigh) return 'success';
		if (score >= thresholdLow) return 'warning';
		return 'error';
	};

	const getLowerBetterStatus = (
		score: number | undefined,
		thresholdHigh: number,
		thresholdLow: number
	): 'success' | 'warning' | 'error' => {
		if (score === undefined) return 'error';
		if (score <= thresholdHigh) return 'success';
		if (score <= thresholdLow) return 'warning';
		return 'error';
	};
	
	return {
		retrieval: getHigherBetterStatus(retrieval?.documents?.[0]?.combined_score, 0.7, 0.4),
		context: getHigherBetterStatus(context?.total_chunks, 3, 1),
		generation: getLowerBetterStatus(generation?.timing_ms, 30000, 60000)
	};
}
