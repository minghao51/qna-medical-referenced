import { test, expect, type Page } from '@playwright/test';

const REPORT_ID = 'medical_semantic_chunking_exp';
const SECOND_ID = 'second_report';
const UNSUPPORTED_ID = 'unsupported_report';

function answerMetrics(
	faithfulnessMean: number,
	faithfulnessMeasured: number,
	faithfulnessFailed: number
) {
	return {
		query_count: 57,
		status: 'ok',
		factual_accuracy: { mean: 0.9965, count: 57, error_count: 0 },
		completeness: { mean: 0.7088, count: 57, error_count: 0 },
		clinical_relevance: { mean: 0.9772, count: 57, error_count: 0 },
		clarity: { mean: 0.9193, count: 57, error_count: 0 },
		answer_relevancy: { mean: 0.8594487734, count: 25, error_count: 32 },
		faithfulness: {
			mean: faithfulnessMean,
			count: faithfulnessMeasured,
			error_count: faithfulnessFailed
		}
	};
}

function reportFixture(
	reportId: string,
	options: {
		faithfulnessMean?: number;
		faithfulnessMeasured?: number;
		faithfulnessFailed?: number;
		schemaKind?: string;
		shaChar?: string;
	} = {}
) {
	const {
		faithfulnessMean = 0.9798534799,
		faithfulnessMeasured = 15,
		faithfulnessFailed = 42,
		schemaKind = 'legacy_feature_addition',
		shaChar = 'a'
	} = options;
	return {
		experiment_name: reportId,
		timestamp: '2026-04-18T12:00:00Z',
		config: {},
		primary_metric: 'ndcg@10',
		baseline: {
			name: 'baseline',
			run_dir: `20260418T120000Z_${reportId}`,
			metrics: answerMetrics(faithfulnessMean, faithfulnessMeasured, faithfulnessFailed)
		},
		variants: [],
		winner: { name: 'baseline' },
		_artifact: {
			report_id: reportId,
			report_sha256: shaChar.repeat(64),
			schema_kind: schemaKind,
			availability: 'available',
			config_ref: 'medical_semantic_exp',
			config_binding: 'explicit_archive_association',
			comparable: false
		}
	};
}

function listFixture() {
	return {
		configs: [],
		reports: [REPORT_ID, SECOND_ID, UNSUPPORTED_ID].map((reportId) => ({
			file: `experiments/outputs/${reportId}_report.json`,
			report_id: reportId,
			schema_kind:
				reportId === UNSUPPORTED_ID ? 'unsupported' : 'legacy_feature_addition',
			availability: 'available',
			config_ref: 'medical_semantic_exp'
		}))
	};
}

async function mockEvaluationApi(
	page: Page,
	options: { listStatus?: number; defaultDelayMs?: number } = {}
) {
	const { listStatus = 200, defaultDelayMs = 0 } = options;
	const requested: string[] = [];

	await page.route(/\/experiments$/, async (route) => {
		await route.fulfill({
			status: listStatus,
			contentType: 'application/json',
			body: JSON.stringify(
				listStatus === 200 ? listFixture() : { detail: 'Missing X-API-Key header' }
			)
		});
	});

	await page.route(/\/experiments\/medical_semantic_chunking_exp\/results$/, async (route) => {
		requested.push(REPORT_ID);
		if (defaultDelayMs > 0) {
			await new Promise((resolve) => setTimeout(resolve, defaultDelayMs));
		}
		await route.fulfill({
			status: 200,
			contentType: 'application/json',
			body: JSON.stringify(reportFixture(REPORT_ID))
		});
	});

	await page.route(/\/experiments\/second_report\/results$/, async (route) => {
		requested.push(SECOND_ID);
		await route.fulfill({
			status: 200,
			contentType: 'application/json',
			body: JSON.stringify(
				reportFixture(SECOND_ID, {
					faithfulnessMean: 0.5,
					faithfulnessMeasured: 10,
					faithfulnessFailed: 47,
					shaChar: 'b'
				})
			)
		});
	});

	await page.route(/\/experiments\/unsupported_report\/results$/, async (route) => {
		requested.push(UNSUPPORTED_ID);
		await route.fulfill({
			status: 200,
			contentType: 'application/json',
			body: JSON.stringify(reportFixture(UNSUPPORTED_ID, { schemaKind: 'unsupported' }))
		});
	});

	return requested;
}

test('archived coverage shows means, denominators and the comparison gate', async ({ page }) => {
	await mockEvaluationApi(page);
	await page.goto('/research/evaluations');

	await expect(
		page.getByRole('heading', { name: 'Read the missing measurements before the means.' })
	).toBeVisible();
	await expect(page.locator('.report-summary h2')).toHaveText(REPORT_ID);
	await expect(page.locator('.summary-value')).toContainText('268 / 342');
	await expect(page.locator('.summary-detail')).toContainText('74 failed');
	await expect(page.locator('.summary-detail')).toContainText('21.6% error rate');
	await expect(page.locator('.summary-copy')).toContainText('not patient cases');

	const rows = page.locator('.coverage-table tbody tr');
	await expect(rows).toHaveCount(6);
	const faithfulnessRow = rows.filter({ hasText: 'Faithfulness' });
	await expect(faithfulnessRow).toContainText('0.9799');
	await expect(faithfulnessRow).toContainText('15 / 57');
	await expect(faithfulnessRow).toContainText('42');
	await expect(faithfulnessRow).toContainText('Partial');
	await expect(rows.filter({ hasText: 'Answer relevancy' })).toContainText('25 / 57');
	await expect(rows.filter({ hasText: 'Answer relevancy' })).toContainText('32');

	await expect(page.getByRole('heading', { name: 'Comparison not verified' })).toBeVisible();
	await expect(page.getByRole('button', { name: /compare/i })).toHaveCount(0);
	await expect(page).toHaveURL(/report=medical_semantic_chunking_exp/);
	await expect(page.getByText('Legacy expectation basis: one slot per declared query.')).toBeVisible();
});

test('explicit report selection loads that report, not the preferred default', async ({ page }) => {
	const requested = await mockEvaluationApi(page);
	await page.goto(`/research/evaluations?report=${SECOND_ID}`);

	await expect(page.locator('.report-summary h2')).toHaveText(SECOND_ID);
	await expect(page.locator('.summary-value')).toContainText('263 / 342');
	const faithfulnessRow = page.locator('.coverage-table tbody tr').filter({ hasText: 'Faithfulness' });
	await expect(faithfulnessRow).toContainText('0.5000');
	await expect(faithfulnessRow).toContainText('10 / 57');
	await expect(faithfulnessRow).toContainText('47');
	expect(requested).toEqual([SECOND_ID]);
});

test('missing requested report does not fall back to the default', async ({ page }) => {
	const requested = await mockEvaluationApi(page);
	await page.goto('/research/evaluations?report=unknown_report');

	await expect(
		page.getByRole('heading', { name: 'Requested archived report unavailable' })
	).toBeVisible();
	await expect(page.getByText(/unknown_report is not an available report/)).toBeVisible();
	await expect(page.getByText('0.9799')).toHaveCount(0);
	expect(requested).toEqual([]);
});

test('unsupported archive keeps raw diagnostics reachable', async ({ page }) => {
	await mockEvaluationApi(page);
	await page.goto(`/research/evaluations?report=${UNSUPPORTED_ID}`);

	await expect(page.getByRole('heading', { name: 'Unsupported archive schema' })).toBeVisible();
	await expect(page.getByRole('link', { name: 'Inspect raw diagnostics' })).toHaveAttribute(
		'href',
		'/eval'
	);
});

test('stale late report response cannot replace the new selection', async ({ page }) => {
	await mockEvaluationApi(page, { defaultDelayMs: 600 });
	await page.goto(`/research/evaluations?report=${REPORT_ID}`);
	await expect(page.locator('#report-select')).toBeVisible();

	await page.locator('#report-select').selectOption(SECOND_ID);
	await expect(page.locator('.report-summary h2')).toHaveText(SECOND_ID);
	await page.waitForTimeout(800);
	await expect(page.locator('.report-summary h2')).toHaveText(SECOND_ID);
});

test('unauthorized archive does not substitute a latest run', async ({ page }) => {
	await mockEvaluationApi(page, { listStatus: 401 });
	await page.goto('/research/evaluations');

	await expect(page.getByRole('heading', { name: 'Research access required' })).toBeVisible();
	await expect(page.getByRole('link', { name: 'Back to Ask' })).toHaveAttribute('href', '/ask');
});

test('methodology explains units, coverage, identity and comparison limits', async ({ page }) => {
	await page.goto('/research/methodology');

	await expect(
		page.getByRole('heading', { name: 'How to read these measurements.' })
	).toBeVisible();
	await expect(page.getByRole('heading', { name: 'Slots, queries and cases are different units.' }))
		.toBeVisible();
	await expect(page.getByRole('heading', { name: 'Read coverage before the mean.' })).toBeVisible();
	await expect(page.getByText('comparable=false')).toBeVisible();
	await expect(page.getByRole('link', { name: 'Evaluation coverage →' })).toHaveAttribute(
		'href',
		'/research/evaluations'
	);
});
