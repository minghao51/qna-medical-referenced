import { test, expect } from '@playwright/test';

async function mockMinimalApis(page: import('@playwright/test').Page) {
	await page.route(/\/experiments$/, (route) =>
		route.fulfill({
			status: 200,
			contentType: 'application/json',
			body: JSON.stringify({ configs: [], reports: [] })
		})
	);
	await page.route(/\/documents\?.*$/, (route) =>
		route.fulfill({
			status: 200,
			contentType: 'application/json',
			body: JSON.stringify({
				total: 1,
				offset: 0,
				limit: 50,
				items: [
					{
						id: 'chunk-1',
						source: 'source.pdf',
						page: 1,
						source_type: 'pdf',
						source_class: 'guideline_pdf',
						content_type: 'paragraph',
						content_preview: 'A short indexed excerpt.',
						content_length: 24
					}
				],
				source_type_counts: { pdf: 1 },
				global_source_type_counts: { pdf: 1 },
				index_identity: null
			})
		})
	);
}

test('skip link moves focus to the main landmark', async ({ page }) => {
	await mockMinimalApis(page);
	await page.goto('/');
	await page.keyboard.press('Tab');
	const skip = page.getByRole('link', { name: 'Skip to main content' });
	await expect(skip).toBeFocused();
	await page.keyboard.press('Enter');
	await expect(page.locator('#main-content')).toBeFocused();
});

test('workspace and evidence keep no horizontal overflow at 390px', async ({ page }) => {
	await mockMinimalApis(page);
	await page.setViewportSize({ width: 390, height: 844 });

	for (const path of ['/', '/evidence']) {
		await page.goto(path);
		await page.waitForLoadState('networkidle');
		const overflow = await page.evaluate(
			() => document.documentElement.scrollWidth - document.documentElement.clientWidth
		);
		expect(overflow, `${path} horizontal overflow`).toBeLessThanOrEqual(1);
	}
});

test('research workspace remains readable at 200% zoom equivalent width', async ({ page }) => {
	await mockMinimalApis(page);
	await page.setViewportSize({ width: 720, height: 900 });
	await page.goto('/');
	await expect(
		page.getByRole('heading', { name: 'What changes actually improve this system?' })
	).toBeVisible();
	await expect(page.getByRole('button', { name: 'Menu' })).toBeVisible();
	const overflow = await page.evaluate(
		() => document.documentElement.scrollWidth - document.documentElement.clientWidth
	);
	expect(overflow).toBeLessThanOrEqual(1);
});

async function mockTheoreticalRouteApis(page: import('@playwright/test').Page) {
	const revision = 'a'.repeat(64);
	const entry = {
		catalog_id: 'golden-all',
		label: 'Golden queries — all',
		kind: 'query_fixture',
		availability: 'available',
		availability_reason: null,
		origin_ref: 'tests/fixtures/golden_queries_all.json',
		revision_sha256: revision,
		record_unit: 'question',
		record_count: 2,
		turn_count: null,
		split_counts: { regression: 1, test: 1 },
		label_confidence_counts: { high: 2 },
		raw_review_status_counts: null,
		review_status_missing_count: 2,
		review_authority: 'not_assessed',
		case_projection: 'available',
		inventory_ref: null
	};
	const firstCase = {
		locator: { revision_sha256: revision, source_ordinal: 0 },
		source_case_id: null,
		question: 'What is the LDL-C target for secondary prevention?',
		expected_keywords: ['LDL-C'],
		expected_source_labels: ['lipid_management_guideline'],
		split: 'regression',
		difficulty: 'medium',
		query_category: 'anchor',
		source_family: 'lipid',
		topic: 'targets',
		label_confidence: 'high',
		raw_review_status: null,
		normalized_review_status: null,
		stored_turns: null
	};

	await page.route(/\/research-data\/datasets$/, (route) =>
		route.fulfill({
			status: 200,
			contentType: 'application/json',
			body: JSON.stringify({ datasets: [entry], overlap: [] })
		})
	);
	await page.route(/\/research-data\/datasets\/golden-all$/, (route) =>
		route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(entry) })
	);
	await page.route(/\/research-data\/datasets\/golden-all\/cases\?.*$/, (route) =>
		route.fulfill({
			status: 200,
			contentType: 'application/json',
			body: JSON.stringify({
				catalog_id: 'golden-all',
				revision_sha256: revision,
				total: 2,
				offset: 0,
				limit: 100,
				items: [
					firstCase,
					{
						...firstCase,
						locator: { revision_sha256: revision, source_ordinal: 1 },
						question: 'What if the patient also has diabetes?'
					}
				]
			})
		})
	);
	await page.route(/\/evaluation\/latest$/, (route) =>
		route.fulfill({
			status: 404,
			contentType: 'application/json',
			body: JSON.stringify({ detail: 'No evaluation runs found' })
		})
	);
	await page.route(/\/evaluation\/history\?.*$/, (route) =>
		route.fulfill({
			status: 200,
			contentType: 'application/json',
			body: JSON.stringify({ runs: [], summary: {}, sources: { mode: 'local' } })
		})
	);
	await page.route(/\/evaluation\/ablation(\/full)?$/, (route) =>
		route.fulfill({
			status: 404,
			contentType: 'application/json',
			body: JSON.stringify({ detail: 'No evaluation runs found' })
		})
	);
	await page.route(/localhost:8000\/health$/, (route) =>
		route.fulfill({
			status: 200,
			contentType: 'application/json',
			body: JSON.stringify({
				status: 'healthy',
				ready: true,
				vector_store: { initialized: true, signature: 'a'.repeat(64) },
				rate_limit: { backend: 'SQLiteRateLimitBackend', window_seconds: 60 },
				runtime: {
					long_runtime_value: JSON.stringify({
						pdf: { chunk_size: 650, strategy: 'recursive' },
						html: { chunk_size: 512, strategy: 'recursive' }
					})
				}
			})
		})
	);
}

test('research and diagnostic routes keep their width at 390px and expose one h1', async ({ page }) => {
	await mockTheoreticalRouteApis(page);
	await page.setViewportSize({ width: 390, height: 844 });

	for (const path of ['/research/datasets/golden-all', '/eval', '/eval/ablation', '/health']) {
		await page.goto(path);
		await page.waitForLoadState('networkidle');
		const overflow = await page.evaluate(
			() => document.documentElement.scrollWidth - document.documentElement.clientWidth
		);
		expect(overflow, `${path} horizontal overflow`).toBeLessThanOrEqual(1);
		await expect(page.locator('h1'), `${path} h1`).toHaveCount(1);
	}
});
