import { test, expect } from '@playwright/test';

test.beforeEach(async ({ page }) => {
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
	await page.route(/\/evaluation\/ablation$/, (route) =>
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
			body: JSON.stringify({ status: 'healthy', ready: true })
		})
	);
});

test('evaluation tabs expose arrow-key navigation and one selected tab', async ({ page }) => {
	await page.goto('/eval');
	await page.waitForLoadState('networkidle');
	await page.waitForTimeout(500);
	const ingestion = page.locator('#tab-ingestion');
	await expect(ingestion).toHaveAttribute('aria-selected', 'true');
	await ingestion.focus();
	await page.keyboard.press('ArrowRight');

	const retrieval = page.locator('#tab-retrieval');
	await expect(retrieval).toBeFocused();
	await expect(retrieval).toHaveAttribute('aria-selected', 'true');
	await expect(ingestion).toHaveAttribute('aria-selected', 'false');
	await expect(page.locator('main')).toHaveCount(1);
});
