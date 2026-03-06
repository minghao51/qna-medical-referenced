import type { EvaluationResponse, RetrievalMetrics } from '$lib/types';

export function calculateHealthScore(metrics: EvaluationResponse): number {
	if (!metrics.retrieval_metrics) return 0;

	const weights = {
		retrieval: 40, // hit rate, MRR
		dataQuality: 30, // L1-L5 quality metrics
		performance: 20, // latency
		completeness: 10 // no critical failures
	};

	const retrievalScore = calculateRetrievalScore(metrics.retrieval_metrics);
	const dataQualityScore = calculateDataQualityScore(metrics);
	const performanceScore = calculatePerformanceScore(metrics.retrieval_metrics);
	const completenessScore = metrics.summary?.failed_thresholds_count === 0 ? 100 : 0;

	return (
		(retrievalScore * weights.retrieval) / 100 +
		(dataQualityScore * weights.dataQuality) / 100 +
		(performanceScore * weights.performance) / 100 +
		(completenessScore * weights.completeness) / 100
	);
}

function calculateRetrievalScore(rm: RetrievalMetrics): number {
	// Hit rate and MRR are most important
	const hitRateScore = rm.hit_rate_at_k * 100;
	const mrrScore = rm.mrr * 100;
	return (hitRateScore * 0.6 + mrrScore * 0.4);
}

function calculateDataQualityScore(metrics: EvaluationResponse): number {
	if (!metrics.step_metrics) return 50;

	let totalScore = 0;
	let weight = 0;

	// L1: Content quality
	if (metrics.step_metrics.l1) {
		const l1 = metrics.step_metrics.l1.aggregate;
		const contentDensity = l1.content_density_mean || 0;
		const boilerplateRatio = l1.boilerplate_ratio_mean || 0;
		const l1Score = contentDensity * 100 * 0.6 + (1 - boilerplateRatio) * 100 * 0.4;
		totalScore += l1Score * 0.3;
		weight += 0.3;
	}

	// L3: Chunking quality
	if (metrics.step_metrics.l3) {
		const l3 = metrics.step_metrics.l3.aggregate;
		const sectionIntegrity = l3.section_integrity_rate || 0;
		const duplicateRate = l3.duplicate_chunk_rate || 0;
		const l3Score = sectionIntegrity * 100 * 0.7 + (1 - duplicateRate) * 100 * 0.3;
		totalScore += l3Score * 0.4;
		weight += 0.4;
	}

	// L2: PDF quality
	if (metrics.step_metrics.l2) {
		const l2 = metrics.step_metrics.l2.aggregate;
		const coverage = l2.page_extraction_coverage || 0;
		const emptyRate = l2.empty_page_rate || 0;
		const l2Score = coverage * 100 * 0.7 + (1 - emptyRate) * 100 * 0.3;
		totalScore += l2Score * 0.15;
		weight += 0.15;
	}

	// L5: Index quality
	if (metrics.step_metrics.l5) {
		const l5 = metrics.step_metrics.l5.aggregate;
		const dimConsistent = l5.embedding_dim_consistent ? 1 : 0;
		const shortRate = l5.short_content_rate || 0;
		const l5Score = dimConsistent * 100 * 0.7 + (1 - shortRate) * 100 * 0.3;
		totalScore += l5Score * 0.15;
		weight += 0.15;
	}

	return weight > 0 ? totalScore / weight : 50;
}

function calculatePerformanceScore(rm: RetrievalMetrics): number {
	// Latency p50: target < 500ms
	const p50Score = rm.latency_p50_ms < 500 ? 100 : Math.max(0, 100 - (rm.latency_p50_ms - 500) / 10);

	// Latency p95: target < 2000ms
	const p95Score = rm.latency_p95_ms < 2000 ? 100 : Math.max(0, 100 - (rm.latency_p95_ms - 2000) / 20);

	return (p50Score * 0.6 + p95Score * 0.4);
}

export function getHealthGrade(score: number): string {
	if (score >= 90) return 'A';
	if (score >= 80) return 'B';
	if (score >= 70) return 'C';
	if (score >= 60) return 'D';
	return 'F';
}

export function getHealthColor(grade: string): string {
	switch (grade) {
		case 'A':
			return '#4caf50';
		case 'B':
			return '#8bc34a';
		case 'C':
			return '#ff9800';
		case 'D':
			return '#ff5722';
		default:
			return '#f44336';
	}
}
