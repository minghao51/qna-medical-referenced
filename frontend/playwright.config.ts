import { defineConfig, devices } from '@playwright/test';

const PLAYWRIGHT_PORT = process.env.PLAYWRIGHT_PORT || '4173';
const PLAYWRIGHT_BASE_URL = process.env.PLAYWRIGHT_BASE_URL || `http://127.0.0.1:${PLAYWRIGHT_PORT}`;

export default defineConfig({
	testDir: './tests',
	retries: 0,
	timeout: 30000,
	expect: {
		timeout: 5000
	},
	fullyParallel: false,
	forbidOnly: !!process.env.CI,
	workers: 1,
	reporter: 'list',
	use: {
		baseURL: PLAYWRIGHT_BASE_URL,
		trace: 'on-first-retry',
	},
	projects: [
		{
			name: 'chromium',
			use: { ...devices['Desktop Chrome'] },
		},
	],
	webServer: process.env.PLAYWRIGHT_BASE_URL
		? undefined
		: {
			command: `npm run dev -- --host 127.0.0.1 --port ${PLAYWRIGHT_PORT}`,
			url: PLAYWRIGHT_BASE_URL,
			reuseExistingServer: false,
		},
});
