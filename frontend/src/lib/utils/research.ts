import type { LegacyArchiveProjection, LegacyArchiveVariant } from '../types';
import { aggregateMetricCoverage, metricCount, normalizeMetricCoverage } from './eval';
import { answerMetricKeys } from './metric-definitions';

function record(value: unknown): Record<string, unknown> | null {
	return value !== null && typeof value === 'object' && !Array.isArray(value)
		? value as Record<string, unknown> : null;
}

function isLegacyVariant(value: unknown): boolean {
	const row = record(value);
	return row !== null && typeof row.name === 'string' && row.name.length > 0
		&& record(row.metrics) !== null && row.measurement_contract_version == null;
}

// These aliases resolve metric vocabulary, never dataset or historical case identity.
export function primaryMetricKey(metric: string): string | null {
	if (/^ndcg@(\d+|k)$/i.test(metric)) return 'ndcg_at_k';
	if (metric === 'mrr') return 'mrr';
	if (/^hit_rate(?:@(\d+|k)|_at_k)$/.test(metric)) return 'hit_rate_at_k';
	return null;
}

/** Adapt only the known legacy feature-addition shape. Never promote an archived winner. */
export function normalizeLegacyArchive(value: unknown): LegacyArchiveProjection {
	const report = record(value);
	const artifact = record(report?._artifact);
	const id = typeof artifact?.report_id === 'string'
		&& /^[A-Za-z0-9._-]+$/.test(artifact.report_id)
		&& artifact.report_id !== '.' && artifact.report_id !== '..' ? artifact.report_id : null;
	const digest = typeof artifact?.report_sha256 === 'string'
		&& /^[a-f0-9]{64}$/.test(artifact.report_sha256) ? artifact.report_sha256 : null;
	const hasRevision = id !== null && digest !== null && artifact?.availability === 'available';
	const projection: LegacyArchiveProjection = {
		schema_kind: 'unsupported', report_id: id, report_sha256: hasRevision ? digest : null,
		identity_status: hasRevision ? 'byte_revision_recorded' : 'unverified',
		config_ref: typeof artifact?.config_ref === 'string'
			&& artifact.config_binding === 'explicit_archive_association' ? artifact.config_ref : null,
		config_binding: artifact?.config_binding === 'explicit_archive_association'
			? 'explicit_archive_association' : null,
		comparable: false, historical_binding: 'not_established', declared_winner: null, variants: []
	};
	if (!report || typeof report.experiment_name !== 'string'
		|| typeof report.primary_metric !== 'string' || !record(report.config)
		|| !isLegacyVariant(report.baseline) || !Array.isArray(report.variants)
		|| !report.variants.every(isLegacyVariant) || report.measurement_contract_version != null
		|| (artifact && (artifact.schema_kind !== 'legacy_feature_addition'
			|| artifact.availability !== 'available'))) return projection;

	const variants: LegacyArchiveVariant[] = [report.baseline, ...report.variants].map((value, index) => {
		const row = record(value)!;
		const metrics = record(row.metrics)!;
		const queries = metricCount(metrics.query_count);
		const answerMetrics = answerMetricKeys.map((key) => {
			const raw = metrics[key];
			const measurement = record(raw);
			return normalizeMetricCoverage(key, {
				mean: measurement?.mean, measured_slots: measurement?.count,
				failed_slots: measurement?.error_count, expected_slots: queries,
				expected_basis: queries === null ? 'unknown' : 'legacy_one_slot_per_query',
				source_invalid: raw != null && measurement === null
			});
		});
		return {
			name: row.name as string, role: index === 0 ? 'baseline' : 'variant',
			measurement_status: typeof metrics.status === 'string' ? metrics.status : null,
			query_count: queries, answer_metrics: answerMetrics,
			coverage_totals: aggregateMetricCoverage(answerMetrics)
		};
	});
	return {
		...projection, schema_kind: 'legacy_feature_addition', variants,
		declared_winner: typeof record(report.winner)?.name === 'string'
			? record(report.winner)!.name as string : null
	};
}
