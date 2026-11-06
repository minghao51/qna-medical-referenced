import { readFileSync } from 'node:fs';
import { createHash } from 'node:crypto';
import { test, expect } from '@playwright/test';
import {
	aggregateMetricCoverage,
	calculateMetricDelta,
	normalizeMetricCoverage
} from '../src/lib/utils/eval';
import { primaryMetricKey, normalizeLegacyArchive } from '../src/lib/utils/research';

const actualReport = JSON.parse(readFileSync(
	new URL('../../experiments/outputs/medical_semantic_chunking_exp_report.json', import.meta.url),
	'utf8'
));
const reportBytes = readFileSync(
	new URL('../../experiments/outputs/medical_semantic_chunking_exp_report.json', import.meta.url)
);

test.describe('metric coverage', () => {
	test('keeps zero distinct from missing and rejects booleans', () => {
		const zero = normalizeMetricCoverage('faithfulness', {
			mean: 0, measured_slots: 57, failed_slots: 0, expected_slots: 57
		});
		expect(zero.mean).toBe(0);
		expect(zero.coverage_state).toBe('complete');

		const invalid = normalizeMetricCoverage('faithfulness', {
			mean: true, measured_slots: false, expected_slots: 57
		});
		expect(invalid.mean).toBeNull();
		expect(invalid.measured_slots).toBeNull();
		expect(invalid.coverage_state).toBe('inconsistent');
		expect(invalid.reason_codes).toContain('invalid_mean');
		expect(invalid.reason_codes).toContain('invalid_count');
	});

	test('reports the real baseline partial measurements without inventing slots', () => {
		const metrics = actualReport.baseline.metrics;
		const faithfulness = normalizeMetricCoverage('faithfulness', {
			mean: metrics.faithfulness.mean,
			measured_slots: metrics.faithfulness.count,
			failed_slots: metrics.faithfulness.error_count,
			expected_slots: metrics.query_count,
			expected_basis: 'legacy_one_slot_per_query'
		});
		expect(faithfulness.mean).toBeCloseTo(0.9799, 4);
		expect(faithfulness.measured_slots).toBe(15);
		expect(faithfulness.failed_slots).toBe(42);
		expect(faithfulness.coverage_state).toBe('partial');

		const rows = Object.keys(metrics).filter((key) => [
			'factual_accuracy', 'completeness', 'clinical_relevance', 'clarity',
			'answer_relevancy', 'faithfulness'
		].includes(key));
		const totals = aggregateMetricCoverage(rows.map((key) => normalizeMetricCoverage(key, {
			mean: metrics[key].mean, measured_slots: metrics[key].count,
			failed_slots: metrics[key].error_count, expected_slots: metrics.query_count
		})));
		expect(rows).toHaveLength(6);
		expect(totals).toEqual({
			measured_slots: 268, expected_slots: 342, failed_slots: 74,
			skipped_slots: null, coverage_state: 'partial'
		});
	});

	test('marks inconsistent counts rather than clamping them', () => {
		const coverage = normalizeMetricCoverage('faithfulness', {
			mean: 0.9, measured_slots: 50, failed_slots: 10, expected_slots: 57
		});
		expect(coverage.coverage_state).toBe('inconsistent');
		expect(coverage.reason_codes).toContain('counts_exceed_expected');
	});

	test('does not synthesize a mean when measurements are missing', () => {
		const missingMean = normalizeMetricCoverage('faithfulness', {
			measured_slots: 57, expected_slots: 57
		});
		expect(missingMean.mean).toBeNull();
		expect(missingMean.coverage_state).toBe('inconsistent');
		expect(missingMean.reason_codes).toContain('missing_mean');

		const noExpected = normalizeMetricCoverage('faithfulness', { mean: 0.9 });
		expect(noExpected.coverage_state).toBe('not_recorded');
		expect(noExpected.reason_codes).toContain('expected_not_recorded');
	});
});

test.describe('metric deltas', () => {
	test('keeps score points and relative percentage distinct', () => {
		const delta = calculateMetricDelta('ndcg_at_k', 0.6596215032, 0.7008913797);
		expect(delta.absolute).toBeCloseTo(0.0413, 4);
		expect(delta.relative_percent).toBeCloseTo(6.3, 1);
		expect(delta.absolute_label).toBe('+0.0413');
		expect(delta.relative_label).toBe('+6.3%');
		expect(delta.favorability).toBe('improved');
	});

	test('uses metric direction for latency, errors and unknown metrics', () => {
		const latency = calculateMetricDelta('latency_p50_ms', 236.5, 485);
		expect(latency.absolute_label).toBe('+248.5 ms');
		expect(latency.favorability).toBe('worsened');

		const errors = calculateMetricDelta('metric_error_rate', 0.216, 0.07);
		expect(errors.favorability).toBe('improved');

		const unknown = calculateMetricDelta('mystery_score', 0.1, 0.2);
		expect(unknown.favorability).toBe('unknown');
	});

	test('has no relative percentage for a zero baseline', () => {
		const delta = calculateMetricDelta('ndcg_at_k', 0, 0.2);
		expect(delta.absolute).toBeCloseTo(0.2);
		expect(delta.relative_percent).toBeNull();
		expect(delta.relative_label).toBe('N/A');
		expect(delta.favorability).toBe('improved');
	});
});

test.describe('legacy archive adaptation', () => {
	const withArtifact = {
		...actualReport,
		_artifact: {
			report_id: 'medical_semantic_chunking_exp',
			report_sha256: createHash('sha256').update(reportBytes).digest('hex'),
			schema_kind: 'legacy_feature_addition',
			availability: 'available',
			config_ref: 'medical_semantic_exp',
			config_binding: 'explicit_archive_association',
			case_records_availability: 'not_exposed_by_report_api',
			comparable: false
		}
	};

	test('projects the actual archive but never promotes its historical winner', () => {
		const projection = normalizeLegacyArchive(withArtifact);
		expect(projection.schema_kind).toBe('legacy_feature_addition');
		expect(projection.identity_status).toBe('byte_revision_recorded');
		expect(projection.config_ref).toBe('medical_semantic_exp');
		expect(projection.historical_binding).toBe('not_established');
		expect(projection.comparable).toBe(false);
		expect(projection.declared_winner).toBe('query_understanding');
		expect(projection.variants.map((variant) => variant.name)).toEqual([
			'baseline', 'medical_chunking', 'query_understanding', 'both_features'
		]);
		expect(projection.variants[0].measurement_status).toBe('degraded');
		expect(projection.variants[3].coverage_totals).toEqual({
			measured_slots: 317, expected_slots: 342, failed_slots: 25,
			skipped_slots: null, coverage_state: 'partial'
		});
	});

	test('rejects unsupported shapes and unverified revisions', () => {
		const unsupported = normalizeLegacyArchive({ ...withArtifact, baseline: [] });
		expect(unsupported.schema_kind).toBe('unsupported');
		expect(unsupported.variants).toEqual([]);
		expect(unsupported.historical_binding).toBe('not_established');

		const noDigest = normalizeLegacyArchive({
			...withArtifact,
			_artifact: { ...withArtifact._artifact, report_sha256: 'not-a-digest' }
		});
		expect(noDigest.identity_status).toBe('unverified');
		expect(noDigest.comparable).toBe(false);
	});

	test('resolves only explicitly supported primary metrics', () => {
		expect(primaryMetricKey('ndcg@5')).toBe('ndcg_at_k');
		expect(primaryMetricKey('mrr')).toBe('mrr');
		expect(primaryMetricKey('hit_rate@10')).toBe('hit_rate_at_k');
		expect(primaryMetricKey('mystery@5')).toBeNull();
	});
});
