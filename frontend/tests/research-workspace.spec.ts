import { test, expect, type Page } from '@playwright/test';

const reportFixture = {
	experiment_name: 'medical_semantic_chunking_exp',
	timestamp: '2026-04-18T12:00:00Z',
	config: {},
	primary_metric: 'ndcg@10',
	baseline: {
		name: 'baseline',
		run_dir: '20260418T120000Z_baseline',
		metrics: {
			query_count: 57,
			status: 'ok',
			factual_accuracy: { mean: 0.9965, count: 57, error_count: 0 },
			completeness: { mean: 0.7088, count: 57, error_count: 0 },
			clinical_relevance: { mean: 0.9772, count: 57, error_count: 0 },
			clarity: { mean: 0.9193, count: 57, error_count: 0 },
			answer_relevancy: { mean: 0.8594487734, count: 25, error_count: 32 },
			faithfulness: { mean: 0.9798534799, count: 15, error_count: 42 }
		}
	},
	variants: [],
	winner: { name: 'baseline' },
	_artifact: {
		report_id: 'medical_semantic_chunking_exp',
		report_sha256: 'a'.repeat(64),
		schema_kind: 'legacy_feature_addition',
		availability: 'available',
		config_ref: 'medical_semantic_exp',
		config_binding: 'explicit_archive_association',
		comparable: false
	}
};

async function mockWorkspaceApi(page: Page, experimentsStatus = 200) {
	await page.route(/\/experiments$/, async (route) => {
		await route.fulfill({
			status: experimentsStatus,
			contentType: 'application/json',
			body: JSON.stringify(
				experimentsStatus === 200
					? {
							configs: [],
							reports: [
								{
									file: 'experiments/outputs/medical_semantic_chunking_exp_report.json',
									report_id: 'medical_semantic_chunking_exp',
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
		await route.fulfill({
			status: 200,
			contentType: 'application/json',
			body: JSON.stringify(reportFixture)
		});
	});
	await page.route(/\/documents\?.*$/, async (route) => {
		await route.fulfill({
			status: 200,
			contentType: 'application/json',
			body: JSON.stringify({
				total: 2473,
				offset: 0,
				limit: 1,
				items: [],
				source_type_counts: { pdf: 1306, html: 597, reference_csv: 460, markdown: 110 }
			})
		});
	});
}

test('workspace shows archived coverage, corpus units and honest posture', async ({ page }) => {
	await mockWorkspaceApi(page);
	await page.goto('/');

	await expect(
		page.getByRole('heading', { name: 'What changes actually improve this system?' })
	).toBeVisible();
	await expect(page.getByText('Faithfulness mean')).toBeVisible();
	await expect(page.locator('.metric-value')).toHaveText('0.9799');
	await expect(page.locator('.metric-counts')).toContainText('15 measured');
	await expect(page.locator('.metric-counts')).toContainText('42 failed');
	await expect(page.locator('.metric-counts')).toContainText('57 expected');
	await expect(page.locator('.coverage-note')).toContainText('268 of 342');
	await expect(page.locator('.coverage-note')).toContainText('74 failed');

	await expect(page.locator('.corpus-total')).toContainText('2,473 indexed chunks');
	await expect(page.locator('.corpus-counts')).toContainText('PDF');
	await expect(page.locator('.corpus-counts')).toContainText('1,306');
	await expect(page.getByText('counts, not publications')).toBeVisible();

	await expect(page.getByRole('link', { name: /Open Q&A workbench/ })).toHaveAttribute(
		'href',
		'/ask'
	);
	await expect(page.getByRole('link', { name: 'Ask', exact: true })).toHaveAttribute(
		'href',
		'/ask'
	);
	await expect(page.getByRole('link', { name: 'Evaluations', exact: true })).toHaveAttribute(
		'href',
		'/research/evaluations'
	);
	await expect(page.getByRole('link', { name: 'Features', exact: true })).toHaveAttribute(
		'href',
		'/research/features'
	);
	await expect(page.getByRole('button', { name: /Run benchmark/i })).toHaveCount(0);
});

test('workspace keeps archive and corpus failures independent', async ({ page }) => {
	await mockWorkspaceApi(page, 401);
	await page.goto('/');

	await expect(page.getByRole('heading', { name: 'What changes actually improve this system?' }))
		.toBeVisible();
	await expect(
		page.getByRole('heading', { name: 'Archived report requires operator access' })
	).toBeVisible();
	await expect(page.locator('.corpus-total')).toContainText('2,473 indexed chunks');
});

test('research redirect lands on the workspace', async ({ page }) => {
	await mockWorkspaceApi(page);
	await page.goto('/research');
	await expect(page).toHaveURL(/\/$/);
	await expect(
		page.getByRole('heading', { name: 'What changes actually improve this system?' })
	).toBeVisible();
});

test('mobile menu is labelled and Escape restores focus', async ({ page }) => {
	await mockWorkspaceApi(page);
	await page.setViewportSize({ width: 390, height: 844 });
	await page.goto('/');
	await expect(page.locator('.corpus-total')).toContainText('2,473 indexed chunks');

	const menuButton = page.getByRole('button', { name: 'Menu' });
	await expect(menuButton).toBeVisible();
	await menuButton.click();
	await expect(page.getByRole('navigation', { name: 'Menu' })).toBeVisible();
	await expect(page.getByRole('navigation', { name: 'Menu' }).getByRole('link', { name: 'Ask' }))
		.toBeVisible();

	await page.keyboard.press('Escape');
	await expect(page.getByRole('navigation', { name: 'Menu' })).toHaveCount(0);
	await expect(menuButton).toBeFocused();
});
