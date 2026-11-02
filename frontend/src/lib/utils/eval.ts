import type {
	AblationRun,
	CoverageExpectedBasis,
	CoverageReason,
	MetricCoverage,
	MetricCoverageTotals,
	MetricDelta,
	DrillDownPoint,
	EvaluationHistoryRun,
	EvaluationResponse,
	RetrievalMetrics
} from '$lib/types';
import { getMetricDisplayDefinition } from './metric-definitions';

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

export function finiteMetricNumber(value: unknown): number | null {
	return typeof value === 'number' && Number.isFinite(value) ? value : null;
}

export function metricCount(value: unknown): number | null {
	const number = finiteMetricNumber(value);
	return number !== null && Number.isSafeInteger(number) && number >= 0 ? number : null;
}

export function metricNumber(value: unknown, key: string): number | null {
	const number = finiteMetricNumber(value);
	if (number === null) return null;
	const { unit } = getMetricDisplayDefinition(key);
	if ((unit === 'score' || unit === 'ratio') && (number < 0 || number > 1)) return null;
	if (unit === 'count') return metricCount(number);
	if (unit === 'ms' && number < 0) return null;
	return number;
}

export function calculateMetricDelta(key: string, baseline: unknown, variant: unknown): MetricDelta {
	const base = metricNumber(baseline, key);
	const value = metricNumber(variant, key);
	const { unit, direction } = getMetricDisplayDefinition(key);
	const absolute = base !== null && value !== null ? finiteMetricNumber(value - base) : null;
	const relative = absolute !== null && base !== null && base !== 0
		? finiteMetricNumber(absolute / Math.abs(base) * 100) : null;
	const digits = unit === 'ms' ? 1 : unit === 'count' ? 0 : 4;
	const absoluteLabel = absolute === null ? 'N/A'
		: `${absolute > 0 ? '+' : ''}${absolute.toFixed(digits)}${unit === 'ms' ? ' ms' : ''}`;
	return {
		absolute, relative_percent: relative,
		absolute_label: absoluteLabel,
		relative_label: relative === null ? 'N/A' : `${relative > 0 ? '+' : ''}${relative.toFixed(1)}%`,
		favorability: absolute === null || direction === 'neutral' ? 'unknown'
			: absolute === 0 ? 'unchanged'
			: (absolute > 0) === (direction === 'higher') ? 'improved' : 'worsened'
	};
}

export function normalizeMetricCoverage(key: string, input: {
	mean?: unknown;
	measured_slots?: unknown;
	expected_slots?: unknown;
	failed_slots?: unknown;
	skipped_slots?: unknown;
	errored_cases?: unknown;
	expected_basis?: CoverageExpectedBasis;
	source_invalid?: boolean;
}): MetricCoverage {
	const reasons: CoverageReason[] = [];
	const mean = metricNumber(input.mean, key);
	const measured = metricCount(input.measured_slots);
	const expected = metricCount(input.expected_slots);
	const failed = metricCount(input.failed_slots);
	const skipped = metricCount(input.skipped_slots);
	const errored = metricCount(input.errored_cases);
	if (input.source_invalid) reasons.push('invalid_metric_shape');
	if (input.mean != null && mean === null) reasons.push('invalid_mean');
	if (['measured_slots', 'expected_slots', 'failed_slots', 'skipped_slots', 'errored_cases']
		.some((field) => {
			const raw = input[field as keyof typeof input];
			return raw != null && metricCount(raw) === null;
		})) reasons.push('invalid_count');
	if (measured !== null && measured > 0 && mean === null) reasons.push('missing_mean');
	if (measured === 0 && mean !== null) reasons.push('mean_without_measurements');
	const knownSlots = (measured ?? 0) + (failed ?? 0) + (skipped ?? 0);
	if (expected !== null && knownSlots > expected) reasons.push('counts_exceed_expected');
	let state: MetricCoverage['coverage_state'];
	if (reasons.length) state = 'inconsistent';
	else if (expected === 0) {
		state = 'not_recorded'; reasons.push('no_expected_measurements');
	} else if (expected === null) {
		state = 'not_recorded'; reasons.push('expected_not_recorded');
	} else if (measured === null) {
		state = 'not_recorded'; reasons.push('counts_not_recorded');
	} else if (measured === expected && failed === 0 && (skipped === null || skipped === 0)
		&& (errored === null || errored === 0)) state = 'complete';
	else {
		state = 'partial';
		if (knownSlots < expected) reasons.push('unaccounted_slots');
		if (failed === null) reasons.push('counts_not_recorded');
	}
	return {
		...getMetricDisplayDefinition(key), metric_key: key, mean,
		measured_slots: measured, expected_slots: expected, failed_slots: failed,
		skipped_slots: skipped, errored_cases: errored,
		expected_basis: input.expected_basis ?? 'unknown', coverage_state: state, reason_codes: reasons
	};
}

export function aggregateMetricCoverage(rows: MetricCoverage[]): MetricCoverageTotals {
	function sum(field: 'measured_slots' | 'expected_slots' | 'failed_slots' | 'skipped_slots') {
		if (!rows.length || rows.some((row) => row[field] === null)) return null;
		return metricCount(rows.reduce((total, row) => total + row[field]!, 0));
	}
	return {
		measured_slots: sum('measured_slots'), expected_slots: sum('expected_slots'),
		failed_slots: sum('failed_slots'), skipped_slots: sum('skipped_slots'),
		coverage_state: rows.some((row) => row.coverage_state === 'inconsistent') ? 'inconsistent'
			: !rows.length || rows.some((row) => row.coverage_state === 'not_recorded') ? 'not_recorded'
			: rows.some((row) => row.coverage_state === 'partial') ? 'partial' : 'complete'
	};
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
): number | null {
	const value = run.retrieval_metrics?.[key];
	return typeof value === 'number' && Number.isFinite(value) ? value : null;
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
