import type {
	AblationRun,
	DrillDownPoint,
	EvalTrendMetric,
	EvaluationHistoryRun,
	EvaluationResponse,
	RetrievalMetrics
} from '$lib/types';

export function formatPercent(value: number | null | undefined, digits = 1): string {
	if (typeof value !== 'number' || !Number.isFinite(value)) return 'N/A';
	return `${(value * 100).toFixed(digits)}%`;
}

export function formatDecimal(
	value: number | null | undefined,
	digits = 2,
	suffix = ''
): string {
	if (typeof value !== 'number' || !Number.isFinite(value)) return 'N/A';
	return `${value.toFixed(digits)}${suffix}`;
}

export function parseRunDate(raw: string | null | undefined): Date | null {
	if (!raw) return null;
	const match = raw.match(
		/(\d{4})(\d{2})(\d{2})T(\d{2})(\d{2})(\d{2})(?:\.(\d{1,6}))?Z?/
	);
	if (!match) return null;

	const [, year, month, day, hour, minute, second, fraction = '0'] = match;
	const milliseconds = Number(fraction.padEnd(3, '0').slice(0, 3));

	return new Date(
		Date.UTC(
			Number(year),
			Number(month) - 1,
			Number(day),
			Number(hour),
			Number(minute),
			Number(second),
			milliseconds
		)
	);
}

export function extractRunTimestamp(run: EvaluationHistoryRun | EvaluationResponse): string {
	return ('timestamp' in run ? run.timestamp : '') || run.run_dir || '';
}

export function formatRunTimestamp(
	run: EvaluationHistoryRun | EvaluationResponse,
	options: Intl.DateTimeFormatOptions = {
		month: 'short',
		day: 'numeric',
		hour: 'numeric',
		minute: '2-digit'
	}
): string {
	const parsed = parseRunDate(extractRunTimestamp(run));
	return parsed ? parsed.toLocaleString(undefined, options) : extractRunTimestamp(run) || 'N/A';
}

export function formatRunTimestampWithZone(
	run: EvaluationHistoryRun | EvaluationResponse
): string {
	return formatRunTimestamp(run, {
		year: 'numeric',
		month: 'short',
		day: 'numeric',
		hour: 'numeric',
		minute: '2-digit',
		second: '2-digit',
		timeZoneName: 'short'
	});
}

export function selectionKey(run: EvaluationHistoryRun | EvaluationResponse): string {
	return `local:${run.run_dir}`;
}

export function historyLabel(run: EvaluationHistoryRun | EvaluationResponse): string {
	if ('experiment_name' in run) {
		return run.experiment_name || run.variant_name || formatRunTimestamp(run);
	}
	return formatRunTimestamp(run);
}

export function retrievalMetric(
	run: EvaluationHistoryRun,
	key: keyof RetrievalMetrics
): number {
	const value = run.retrieval_metrics?.[key];
	return typeof value === 'number' ? value : 0;
}

export function runMetricLabels(run: EvaluationHistoryRun): string[] {
	const labels = [
		`Hit ${formatPercent(retrievalMetric(run, 'hit_rate_at_k'))}`,
		`MRR ${formatDecimal(retrievalMetric(run, 'mrr'), 3)}`,
		`p50 ${formatDecimal(retrievalMetric(run, 'latency_p50_ms'), 0, 'ms')}`
	];

	if (run.retrieval_metrics?.hyde_enabled) {
		labels.push(
			`HyDE ${
				run.retrieval_metrics.hyde_hit_rate == null
					? 'on'
					: formatPercent(run.retrieval_metrics.hyde_hit_rate)
			}`
		);
	}

	return labels;
}

export function buildTrendDatasets(
	runs: EvaluationHistoryRun[],
	selectedTrendMetric: EvalTrendMetric
): Array<{ label: string; data: number[] }> {
	if (selectedTrendMetric === 'latency') {
		return [
			{ label: 'p50', data: runs.map((run) => retrievalMetric(run, 'latency_p50_ms')) },
			{ label: 'p95', data: runs.map((run) => retrievalMetric(run, 'latency_p95_ms')) }
		];
	}

	if (selectedTrendMetric === 'mrr') {
		return [
			{ label: 'MRR', data: runs.map((run) => retrievalMetric(run, 'mrr') * 100) },
			{
				label: 'Precision @k',
				data: runs.map((run) => retrievalMetric(run, 'precision_at_k') * 100)
			},
			{ label: 'Recall @k', data: runs.map((run) => retrievalMetric(run, 'recall_at_k') * 100) }
		];
	}

	return [
		{
			label: 'Hit Rate @k',
			data: runs.map((run) => retrievalMetric(run, 'hit_rate_at_k') * 100)
		},
		{ label: 'MRR', data: runs.map((run) => retrievalMetric(run, 'mrr') * 100) }
	];
}

export function summarizeAblation(run: AblationRun): string[] {
	return [
		`Hit ${formatPercent(run.hit_rate_at_k)}`,
		`MRR ${formatDecimal(run.mrr, 3)}`,
		`nDCG ${formatPercent(run.ndcg_at_k)}`,
		`p50 ${formatDecimal(run.latency_p50_ms, 0, 'ms')}`
	];
}

export function emptyDrillDownState(): {
	open: boolean;
	metric: string;
	stage: string;
	currentValue: number;
	records: Array<Record<string, unknown>>;
	historicalData: DrillDownPoint[];
} {
	return {
		open: false,
		metric: '',
		stage: '',
		currentValue: 0,
		records: [],
		historicalData: []
	};
}
