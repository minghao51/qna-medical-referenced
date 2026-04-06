import { type Page } from '@playwright/test';

export const BROWSER_API_URL = process.env.VITE_API_URL || 'http://localhost:8000';
export const API_URL = process.env.API_URL || BROWSER_API_URL;

export async function proxyBrowserApiRequests(page: Page): Promise<void> {
	if (API_URL === BROWSER_API_URL) return;

	const browserApiPrefix = `${new URL(BROWSER_API_URL).origin}/`;
	await page.route(`${browserApiPrefix}**`, async (route) => {
		const proxiedUrl = route.request().url().replace(new URL(BROWSER_API_URL).origin, API_URL);
		const response = await route.fetch({ url: proxiedUrl });
		await route.fulfill({ response });
	});
}
