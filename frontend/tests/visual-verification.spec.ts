import { test, expect, type Page } from '@playwright/test';

const API_URL = process.env.API_URL || 'http://localhost:8000';

async function proxyBrowserApiRequests(page: Page) {
	if (API_URL === 'http://localhost:8000') return;

	await page.route('http://localhost:8000/**', async (route) => {
		const proxiedUrl = route.request().url().replace('http://localhost:8000', API_URL);
		const response = await route.fetch({ url: proxiedUrl });
		await route.fulfill({ response });
	});
}

test.describe('Visual Verification - Quality Metrics', () => {
	test('captures screenshot of quality metrics dashboard', async ({ page }) => {
		await proxyBrowserApiRequests(page);
		await page.goto('/eval');
		await page.waitForSelector('.eval-container', { timeout: 5000 });

		// Wait for all content to load
		await page.waitForLoadState('networkidle');

		// Capture full page screenshot
		await page.screenshot({
			path: 'test-results/quality-metrics-dashboard.png',
			fullPage: true
		});

		console.log('Screenshot saved to test-results/quality-metrics-dashboard.png');
	});
});
