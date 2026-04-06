import { test, expect, type Page } from '@playwright/test';
import { proxyBrowserApiRequests } from './helpers';

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
