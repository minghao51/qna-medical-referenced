import { test, expect, type Page } from '@playwright/test';

const latestFixture = {
	run_dir: '20261016T120000Z_latest',
	summary: {
		status: 'ok',
		duration_s: 2,
		failed_thresholds_count: 0,
		retrieval_metrics: {
			query_count: 2,
			hit_rate_at_k: 1,
			mrr: 0.75,
			ndcg_at_k: 0.8,
			latency_p50_ms: 10,
			latency_p95_ms: 20
		},
		l6_answer_quality_metrics: { status: 'not_applicable' }
	},
	retrieval_metrics: {
		query_count: 2,
		hit_rate_at_k: 1,
		precision_at_k: 0.5,
		recall_at_k: 1,
		mrr: 0.75,
		ndcg_at_k: 0.8,
		source_hit_rate: 1,
		exact_chunk_hit_rate: 1,
		evidence_hit_rate: 1,
		latency_p50_ms: 10,
		latency_p95_ms: 20,
		hit_rate_at_k_high_conf: 1,
		mrr_high_conf: 0.75
	}
};

const historyFixture = {
	runs: [
		{
			run_dir: '20261016T110000Z_legacy-invalid',
			timestamp: '20261016T110000Z',
			status: 'failed',
			comparable: false,
			artifact_compatibility: 'legacy',
			duration_s: null,
			failed_thresholds_count: 1,
			retrieval_metrics: {
				query_count: 2,
				hit_rate_at_k: null,
				mrr: null,
				latency_p50_ms: null,
				latency_p95_ms: null
			},
			source: 'local',
			experiment_name: 'legacy-invalid'
		},
		{
			run_dir: '20261016T100000Z_unsupported',
			timestamp: '20261016T100000Z',
			status: 'ok',
			comparable: false,
			artifact_compatibility: 'unsupported',
			duration_s: 3,
			failed_thresholds_count: 0,
			retrieval_metrics: {
				query_count: 3,
				hit_rate_at_k: 0.8,
				mrr: 0.6,
				latency_p50_ms: 12,
				latency_p95_ms: 24
			},
			source: 'local',
			experiment_name: 'unsupported'
		}
	],
	summary: {
		total_runs: 2,
		avg_hit_rate: null,
		avg_mrr: null,
		avg_latency_p50: null,
		avg_duration: null,
		sources: { local: 2 } as Record<string, number>
	}
};

async function mockEvaluationApi(
	page: Page,
	history = historyFixture,
	onRunRequest?: () => void,
	selectedRunPayload: unknown = {
		...latestFixture,
		run_dir: '20261016T100000Z_unsupported'
	}
) {
	const frontendOrigin = new URL(test.info().project.use.baseURL!).origin;
	// Only frontend assets may reach a server; every API response below is synthetic.
	await page.route('**/*', async (route) => {
		const request = route.request();
		const url = new URL(request.url());
		if (
			url.origin !== frontendOrigin ||
			request.resourceType() === 'fetch' ||
			request.resourceType() === 'xhr' ||
			/^\/(evaluation|health|config|history|chat|documents|experiments)(\/|$)/.test(url.pathname)
		) {
			await route.abort();
		} else {
			await route.continue();
		}
	});
	await page.route(/\/health$/, async (route) => {
		await route.fulfill({
			status: 200,
			contentType: 'application/json',
			body: JSON.stringify({ status: 'healthy', ready: true })
		});
	});
	await page.route(/\/evaluation\/latest$/, async (route) => {
		await route.fulfill({
			status: 200,
			contentType: 'application/json',
			body: JSON.stringify(latestFixture)
		});
	});
	await page.route(/\/evaluation\/history(?:\?.*)?$/, async (route) => {
		await route.fulfill({
			status: 200,
			contentType: 'application/json',
			body: JSON.stringify(history)
		});
	});
	await page.route(/\/evaluation\/ablation$/, async (route) => {
		await route.fulfill({
			status: 200,
			contentType: 'application/json',
			body: JSON.stringify({ ablation_runs: [] })
		});
	});
	await page.route(/\/evaluation\/run\/[^/?]+$/, async (route) => {
		onRunRequest?.();
		await route.fulfill({
			status: 200,
			contentType: 'application/json',
			body: JSON.stringify(selectedRunPayload)
		});
	});
}

async function openTrending(
	page: Page,
	history = historyFixture,
	onRunRequest?: () => void,
	selectedRunPayload?: unknown
) {
	await mockEvaluationApi(page, history, onRunRequest, selectedRunPayload);
	await page.goto('/eval');
	await page.getByRole('heading', { name: 'Pipeline quality assessment' }).waitFor();
	// The heading is server-rendered; wait for client-side data loading to finish before interacting.
	await expect(page.getByRole('button', { name: 'Export CSV' })).toBeVisible();
	await page.getByRole('tab', { name: 'Trending' }).click();
	await expect(
		page.getByText('Historical runs are not comparable.', { exact: false })
	).toBeVisible();
}

test('history shows N/A without comparisons and retains diagnostic filtering/selection', async ({
	page
}) => {
	const pageErrors: string[] = [];
	page.on('pageerror', (error) => pageErrors.push(error.message));
	let selectedRunRequested = false;
	await openTrending(page, historyFixture, () => (selectedRunRequested = true));

	await expect(
		page.locator('.metric-tile').filter({ hasText: 'Avg Hit Rate' }).locator('.value')
	).toHaveText('N/A');
	await expect(
		page.locator('.metric-tile').filter({ hasText: 'Avg MRR' }).locator('.value')
	).toHaveText('N/A');
	await expect(
		page.locator('.metric-tile').filter({ hasText: 'Avg Latency' }).locator('.value')
	).toHaveText('N/A');
	await expect(page.locator('.chart-card')).toHaveCount(0);
	await expect(page.locator('.trend-toolbar select')).toHaveCount(0);

	await page.getByRole('button', { name: /Show 2 runs/ }).click();
	const missingMetricsRun = page.locator('.run-card').filter({ hasText: 'legacy-invalid' });
	await expect(missingMetricsRun).toContainText('Hit N/A');
	await expect(missingMetricsRun).toContainText('MRR N/A');
	await expect(missingMetricsRun).toContainText('p50 N/A');

	await page.getByPlaceholder('Filter by experiment, variant, or hash').fill('unsupported');
	await expect(page.locator('.run-card')).toHaveCount(1);
	const selectedRun = page.locator('.run-card').filter({ hasText: 'unsupported' });
	await selectedRun.click();
	await expect(selectedRun).toHaveClass(/selected/);
	await expect.poll(() => selectedRunRequested).toBe(true);

	await page.getByRole('tab', { name: 'Quality' }).click();
	await expect(page.getByRole('tab', { name: 'Quality' })).toHaveAttribute('aria-selected', 'true');
	await expect(page.locator('#panel-quality')).toBeVisible();
	await page.getByRole('tab', { name: 'Ingestion' }).click();
	await expect(page.getByRole('tab', { name: 'Ingestion' })).toHaveAttribute(
		'aria-selected',
		'true'
	);
	await expect(page.locator('#panel-ingestion')).toBeVisible();
	await expect.poll(() => pageErrors).toEqual([]);
});

const incompleteSummaryCases: Array<{
	name: string;
	summary: Record<string, unknown>;
	expectedStatus: string;
	expectedDuration: string;
	expectedFailedThresholds: string;
}> = [
	{
		name: 'null summary values',
		summary: { status: null, duration_s: null, failed_thresholds_count: null },
		expectedStatus: 'N/A',
		expectedDuration: 'N/A',
		expectedFailedThresholds: 'N/A'
	},
	{
		name: 'missing summary values',
		summary: { measurement_status: 'incomplete' },
		expectedStatus: 'N/A',
		expectedDuration: 'N/A',
		expectedFailedThresholds: 'N/A'
	},
	{
		name: 'incomplete summary status',
		summary: { status: 'incomplete', duration_s: null, failed_thresholds_count: null },
		expectedStatus: 'INCOMPLETE',
		expectedDuration: 'N/A',
		expectedFailedThresholds: 'N/A'
	},
	{
		name: 'valid zero summary values',
		summary: { status: 'ok', duration_s: 0, failed_thresholds_count: 0 },
		expectedStatus: 'OK',
		expectedDuration: '0.00s',
		expectedFailedThresholds: '0'
	},
	{
		name: 'finite summary values',
		summary: { status: 'failed', duration_s: 1.25, failed_thresholds_count: 3 },
		expectedStatus: 'FAILED',
		expectedDuration: '1.25s',
		expectedFailedThresholds: '3'
	}
];

for (const scenario of incompleteSummaryCases) {
	test(`selecting an incomplete run safely shows ${scenario.name}`, async ({ page }) => {
		const pageErrors: string[] = [];
		page.on('pageerror', (error) => pageErrors.push(error.message));
		const incompleteDetail = {
			run_dir: '20261016T110000Z_legacy-invalid',
			summary: scenario.summary
		};
		await openTrending(page, historyFixture, undefined, incompleteDetail);
		await page.getByRole('button', { name: /Show 2 runs/ }).click();

		const selectedRun = page.locator('.run-card').filter({ hasText: 'legacy-invalid' });
		await selectedRun.click();
		await expect(selectedRun).toHaveClass(/selected/);
		await expect(page.locator('.run-bar-primary')).toContainText('legacy-invalid');
		await expect(page.locator('.status-pill')).toHaveText(scenario.expectedStatus);
		await expect(page.locator('.run-bar-meta')).toContainText(
			`Duration ${scenario.expectedDuration}`
		);
		await expect(page.locator('.run-bar-meta')).toContainText(
			`${scenario.expectedFailedThresholds} failed thresholds`
		);

		await page.getByRole('tab', { name: 'Quality' }).click();
		await expect(page.getByRole('tab', { name: 'Quality' })).toHaveAttribute(
			'aria-selected',
			'true'
		);
		await expect(page.locator('#panel-quality')).toBeVisible();
		await page.getByRole('tab', { name: 'Ingestion' }).click();
		await expect(page.getByRole('tab', { name: 'Ingestion' })).toHaveAttribute(
			'aria-selected',
			'true'
		);
		await expect(page.locator('#panel-ingestion')).toBeVisible();
		await expect.poll(() => pageErrors).toEqual([]);
	});
}

test('empty history shows the empty state without producing a chart', async ({ page }) => {
	const pageErrors: string[] = [];
	page.on('pageerror', (error) => pageErrors.push(error.message));
	const emptyHistory = {
		...historyFixture,
		runs: [] as typeof historyFixture.runs,
		summary: {
			total_runs: 0,
			avg_hit_rate: null,
			avg_mrr: null,
			avg_latency_p50: null,
			avg_duration: null,
			sources: {} as Record<string, number>
		}
	};
	await openTrending(page, emptyHistory);
	await expect(page.getByText('No historical data available')).toBeVisible();
	await expect(page.locator('canvas')).toHaveCount(0);

	await page.getByRole('tab', { name: 'Quality' }).click();
	await expect(page.getByRole('tab', { name: 'Quality' })).toHaveAttribute('aria-selected', 'true');
	await expect(page.locator('#panel-quality')).toBeVisible();
	await page.getByRole('tab', { name: 'Ingestion' }).click();
	await expect(page.getByRole('tab', { name: 'Ingestion' })).toHaveAttribute(
		'aria-selected',
		'true'
	);
	await expect(page.locator('#panel-ingestion')).toBeVisible();
	await page.getByRole('tab', { name: 'Trending' }).click();
	await expect(page.getByRole('tab', { name: 'Trending' })).toHaveAttribute(
		'aria-selected',
		'true'
	);
	await expect(page.getByText('No historical data available')).toBeVisible();
	await expect.poll(() => pageErrors).toEqual([]);
});
