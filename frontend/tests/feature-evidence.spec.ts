import { test, expect, type Page } from '@playwright/test';

const REPORT_ID = 'medical_semantic_chunking_exp';

function variant(name: string, ndcg: number) {
	return {
		name,
		run_dir: `20260417T183423Z_${name}`,
		metrics: {
			query_count: 57,
			status: 'degraded',
			ndcg_at_k: ndcg,
			mrr: 0.6459064327485381,
			hit_rate_at_k: 0.7894736842105263,
			latency_p50_ms: 226
		}
	};
}

function reportFixture() {
	return {
		experiment_name: REPORT_ID,
		timestamp: '2026-04-18T12:00:00Z',
		config: {
			name: REPORT_ID,
			baseline: {
				name: 'baseline',
				chunking_strategy: 'chonkie_semantic',
				query_understanding: false
			},
			variants: [
				{
					name: 'medical_chunking',
					chunking_strategy: 'medical_semantic',
					query_understanding: false
				},
				{
					name: 'query_understanding',
					chunking_strategy: 'chonkie_semantic',
					query_understanding: true
				},
				{
					name: 'both_features',
					chunking_strategy: 'medical_semantic',
					query_understanding: true
				}
			]
		},
		baseline: variant('baseline', 0.6596215032368163),
		variants: [
			variant('medical_chunking', 0.6596215032368163),
			variant('query_understanding', 0.7008913796906576),
			variant('both_features', 0.7008913796906576)
		],
		winner: { name: 'query_understanding' },
		primary_metric: 'ndcg@5',
		target_improvement: 0.03,
		any_target_met: true,
		_artifact: {
			report_id: REPORT_ID,
			report_sha256: 'a'.repeat(64),
			schema_kind: 'legacy_feature_addition',
			availability: 'available',
			config_ref: 'medical_semantic_exp',
			config_binding: 'explicit_archive_association',
			comparable: false
		}
	};
}

async function mockFeatureApi(
	page: Page,
	options: { listStatus?: number } = {}
) {
	const { listStatus = 200 } = options;
	const requested: string[] = [];
	await page.route(/\/experiments$/, async (route) => {
		await route.fulfill({
			status: listStatus,
			contentType: 'application/json',
			body: JSON.stringify(
				listStatus === 200
					? {
							configs: [],
							reports: [
								{
									file: `experiments/outputs/${REPORT_ID}_report.json`,
									report_id: REPORT_ID,
									schema_kind: 'legacy_feature_addition',
									availability: 'available',
									config_ref: 'medical_semantic_exp'
								}
							]
						}
					: { detail: 'Missing X-API-Key header' }
			)
		});
	});
	await page.route(/\/experiments\/medical_semantic_chunking_exp\/results$/, async (route) => {
		requested.push(REPORT_ID);
		await route.fulfill({
			status: 200,
			contentType: 'application/json',
			body: JSON.stringify(reportFixture())
		});
	});
	return requested;
}

test('feature evidence separates declared variants, observed deltas and the historical winner', async ({
	page
}) => {
	await mockFeatureApi(page);
	await page.goto('/research/features');

	await expect(page.getByRole('heading', { name: 'A feature flag is not a finding.' })).toBeVisible();
	await expect(page.locator('.feature-table tbody tr')).toHaveCount(4);
	const selectedRow = page.locator('.feature-table tbody tr.selected');
	await expect(selectedRow).toContainText('query_understanding');
	await expect(selectedRow).toContainText('Inspecting');
	await expect(selectedRow).toContainText('0.7009');
	await expect(selectedRow).toContainText('+0.0413');
	await expect(selectedRow).toContainText('+6.3%');

	const medicalRow = page.locator('.feature-table tbody tr').filter({ hasText: 'medical_chunking' });
	await expect(medicalRow).toContainText('0.6596');
	await expect(medicalRow).toContainText('0.0000');

	await expect(page.locator('.delta-headline')).toContainText('+0.0413');
	await expect(page.locator('.delta-headline')).toContainText('+6.3%');
	await expect(page.getByText(/All four variants have degraded answer measurements/)).toBeVisible();
	await expect(page.getByText(/does not certify current eligibility/)).toBeVisible();
	await expect(page.locator('.inspect-card')).toContainText('Effective runtime settings');
	await expect(page.locator('.inspect-card')).toContainText('Unverified');
	await expect(page.locator('.inspect-card')).toContainText('Index binding');

	await expect(page.getByRole('heading', { name: 'Capability map' })).toBeVisible();
	await expect(page.getByText('Cross-encoder reranking')).toBeVisible();
	await expect(page.getByRole('heading', { name: 'Separate 54-query reranking study' })).toBeVisible();
	await expect(page.locator('.study-table')).toContainText('0.7205');
	await expect(page.locator('.study-table')).toContainText('485.0 ms');

	await expect(page.getByRole('button', { name: /enable|apply|run benchmark|promote/i })).toHaveCount(0);
	await expect(page.locator('input[type="checkbox"]')).toHaveCount(0);
});

test('selecting another variant changes only the inspection state', async ({ page }) => {
	await mockFeatureApi(page);
	await page.goto('/research/features');

	await page.getByRole('button', { name: 'medical_chunking' }).click();
	await expect(page.locator('.feature-table tbody tr.selected')).toContainText('medical_chunking');
	await expect(page.locator('#inspect-title')).toHaveText('medical_chunking');
	await expect(page.locator('.inspect-card')).toContainText('medical_semantic');
	await expect(page.locator('.inspect-card')).toContainText('0.6596');
	await expect(page.locator('.feature-table tbody tr.selected')).toContainText('0.0000');
	await expect(page.getByText('All four variants have degraded answer measurements')).toBeVisible();
});

test('missing feature report does not fall back to the default', async ({ page }) => {
	const requested = await mockFeatureApi(page);
	await page.goto('/research/features?report=missing_report');

	await expect(
		page.getByRole('heading', { name: 'Requested archived report unavailable' })
	).toBeVisible();
	await expect(page.getByText(/missing_report is not an available report/)).toBeVisible();
	expect(requested).toEqual([]);
});

test('unauthorized feature evidence does not substitute a latest report', async ({ page }) => {
	await mockFeatureApi(page, { listStatus: 401 });
	await page.goto('/research/features');

	await expect(page.getByRole('heading', { name: 'Research access required' })).toBeVisible();
	await expect(page.getByRole('link', { name: 'Back to Ask' })).toHaveAttribute('href', '/ask');
});
