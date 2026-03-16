import { defineConfig, devices } from '@playwright/test';

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
		baseURL: process.env.PLAYWRIGHT_BASE_URL || 'http://127.0.0.1:5174',
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
			command: 'npm run dev -- --host 127.0.0.1 --port 5174',
			url: 'http://127.0.0.1:5174',
			reuseExistingServer: !process.env.CI,
		},
});
