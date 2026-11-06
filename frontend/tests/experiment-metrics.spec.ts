import { test, expect } from '@playwright/test';

const report = {
	experiment_name: 'medical_semantic_chunking_exp',
	timestamp: '2026-01-01T00:00:00Z',
	primary_metric: 'ndcg@5',
	target_improvement: 0.03,
	any_target_met: true,
	winner: { name: 'variant1' },
	_artifact: {
		report_id: 'medical_semantic_chunking_exp',
		report_sha256: 'a'.repeat(64),
		schema_kind: 'legacy_feature_addition',
		availability: 'available',
		config_ref: 'medical_semantic_exp',
		config_binding: null,
		case_records_availability: 'not_exposed_by_report_api',
		comparable: false
	},
	config: {},
	baseline: {
		name: 'baseline',
		run_dir: 'baseline-run',
		metrics: { ndcg_at_k: 0.5, latency_p50_ms: 100, faithfulness: 0.9 }
	},
	variants: [
		{
			name: 'variant1',
			run_dir: 'variant-run',
			metrics: { ndcg_at_k: 0.6, latency_p50_ms: 200 }
		}
	]
};

test('experiment archive keeps missing metrics absent and separates units', async ({ page }) => {
	await page.route(/^https?:\/\/localhost:8000\/experiments$/, async (route) => {
		await route.fulfill({
			json: {
				configs: [
					{
						file: 'medical_semantic_exp.yaml',
						experiment_id: 'medical_semantic_exp',
						name: 'Medical semantic',
						description: '',
						variant_count: 1,
						primary_metric: 'ndcg@5',
						has_results: true,
						availability: 'available'
					}
				],
				reports: [
					{
						file: 'outputs/medical_semantic_chunking_exp_report.json',
						report_id: 'medical_semantic_chunking_exp',
						report_sha256: 'a'.repeat(64),
						schema_kind: 'legacy_feature_addition',
						availability: 'available',
						config_ref: 'medical_semantic_exp',
						experiment_name: 'medical_semantic_chunking_exp',
						timestamp: report.timestamp,
						winner: 'variant1',
						any_target_met: true
					}
				]
			}
		});
	});
	await page.route(
		/^https?:\/\/localhost:8000\/experiments\/medical_semantic_chunking_exp\/results$/,
		(route) => route.fulfill({ json: report })
	);
	await page.route(/^https?:\/\/localhost:8000\/experiments\/medical_semantic_exp\/config$/, (route) =>
		route.fulfill({
			json: {
				schema_version: 1,
				metadata: { name: 'Medical semantic', description: '', tags: [] },
				ingestion: {}, retrieval: {}, embedding_index: {}, dataset: {},
				evaluation: {}, variants: [], experiment_file: 'medical_semantic_exp.yaml'
			}
		})
	);

	await page.goto('/experiments');
	await page.getByRole('button', { name: /Medical semantic/ }).click();

	await expect(page.getByText('Reported winner (historical)')).toBeVisible();
	await expect(page.getByText('Archived report data.')).toBeVisible();

	const faithfulness = page.getByRole('row', { name: /faithfulness/ });
	await expect(faithfulness).toContainText('0.9000');
	await expect(faithfulness).toContainText('—');

	const latency = page.getByRole('row', { name: /latency_p50_ms/ });
	await expect(latency).toContainText('+100.0 ms / +100.0%');
	await expect(latency).toContainText('200.0000');
});
