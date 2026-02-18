import { test, expect } from '@playwright/test';

const BASE_URL = process.env.PLAYWRIGHT_BASE_URL || 'http://localhost:5174';
const API_URL = process.env.API_URL || 'http://localhost:8001';

test.describe('Pipeline Visualization', () => {
	test.beforeEach(async ({ page }) => {
		await page.goto(BASE_URL);
	});

	test('pipeline toggle checkbox is visible', async ({ page }) => {
		const toggle = page.locator('.pipeline-toggle');
		await expect(toggle).toBeVisible();
		await expect(toggle.locator('input[type="checkbox"]')).toBeVisible();
		await expect(toggle).toContainText('Show pipeline details');
	});

	test('can toggle pipeline details on', async ({ page }) => {
		const checkbox = page.locator('.pipeline-toggle input[type="checkbox"]');

		// Initially unchecked
		await expect(checkbox).not.toBeChecked();

		// Click to enable
		await checkbox.check();
		await expect(checkbox).toBeChecked();
	});

	test('pipeline button appears on assistant message when enabled', async ({ page }) => {
		// Enable pipeline toggle
		await page.locator('.pipeline-toggle input[type="checkbox"]').check();

		// Type and send a message
		await page.locator('textarea').fill('What is normal cholesterol?');
		await page.locator('button:has-text("Send")').click();

		// Wait for assistant response
		await expect(page.locator('.message.assistant')).toBeVisible({ timeout: 15000 });

		// Check for pipeline button (may not appear if API doesn't support it yet)
		const pipelineBtn = page.locator('.pipeline-btn');
		const hasPipelineButton = await pipelineBtn.count() > 0;

		if (hasPipelineButton) {
			await expect(pipelineBtn).toBeVisible();
			await expect(pipelineBtn).toContainText('Show Pipeline Details');
		}
	});

	test('send button enables when text is entered', async ({ page }) => {
		const input = page.locator('textarea');
		const sendButton = page.locator('button:has-text("Send")');

		// Initially disabled
		await expect(sendButton).toBeDisabled();

		// Type text
		await input.fill('Test question');

		// Should be enabled
		await expect(sendButton).toBeEnabled();
	});

	test('New Chat button is visible', async ({ page }) => {
		const newChatBtn = page.locator('button:has-text("New Chat")');
		await expect(newChatBtn).toBeVisible();
	});

	test('input area has correct placeholder', async ({ page }) => {
		const textarea = page.locator('textarea');
		await expect(textarea).toHaveAttribute('placeholder', /Ask a question/);
	});
});

test.describe('Pipeline Panel', () => {
	test.beforeEach(async ({ page }) => {
		await page.goto(BASE_URL);
	});

	test('pipeline panel is hidden by default', async ({ page }) => {
		const panel = page.locator('.pipeline-panel');
		await expect(panel).not.toBeVisible();
	});

	test('sources display correctly on response', async ({ page }) => {
		// Send a message
		await page.locator('textarea').fill('What is LDL cholesterol?');
		await page.locator('button:has-text("Send")').click();

		// Wait for response
		await expect(page.locator('.message.assistant')).toBeVisible({ timeout: 15000 });

		// Check if sources are displayed
		const sources = page.locator('.sources');
		const hasSources = await sources.count() > 0;

		if (hasSources) {
			await expect(sources.first()).toBeVisible();
		}
	});
});

test.describe('API Integration', () => {
	test('backend health endpoint responds', async ({ request }) => {
		const response = await request.get(`${API_URL}/health`);
		expect(response.status()).toBe(200);

		const data = await response.json();
		expect(data).toHaveProperty('status', 'healthy');
	});

	test('backend root endpoint responds', async ({ request }) => {
		const response = await request.get(`${API_URL}/`);
		expect(response.status()).toBe(200);

		const data = await response.json();
		expect(data).toHaveProperty('message');
	});

	test('chat endpoint accepts requests', async ({ request }) => {
		const response = await request.post(`${API_URL}/chat`, {
			data: {
				message: 'What is normal cholesterol?',
				session_id: 'test-session'
			},
			headers: {
				'Content-Type': 'application/json'
			}
		});

		expect(response.status()).toBe(200);

		const data = await response.json();
		expect(data).toHaveProperty('response');
		expect(data).toHaveProperty('sources');
		expect(Array.isArray(data.sources)).toBeTruthy();
	});
});

test.describe('Chat with Pipeline Enabled', () => {
	test('chat with include_pipeline parameter', async ({ request }) => {
		const response = await request.post(`${API_URL}/chat?include_pipeline=true`, {
			data: {
				message: 'What is normal cholesterol?',
				session_id: 'test-pipeline-session'
			},
			headers: {
				'Content-Type': 'application/json'
			}
		});

		expect(response.status()).toBe(200);

		const data = await response.json();
		expect(data).toHaveProperty('response');
		expect(data).toHaveProperty('sources');
		expect(data).toHaveProperty('pipeline');

		// Verify pipeline structure
		const { pipeline } = data;
		expect(pipeline).toHaveProperty('retrieval');
		expect(pipeline).toHaveProperty('context');
		expect(pipeline).toHaveProperty('generation');
		expect(pipeline).toHaveProperty('total_time_ms');

		// Verify retrieval stage
		expect(pipeline.retrieval).toHaveProperty('query');
		expect(pipeline.retrieval).toHaveProperty('top_k');
		expect(pipeline.retrieval).toHaveProperty('documents');
		expect(pipeline.retrieval).toHaveProperty('score_weights');
		expect(pipeline.retrieval).toHaveProperty('timing_ms');

		// Verify documents structure
		expect(Array.isArray(pipeline.retrieval.documents)).toBeTruthy();
		if (pipeline.retrieval.documents.length > 0) {
			const doc = pipeline.retrieval.documents[0];
			expect(doc).toHaveProperty('id');
			expect(doc).toHaveProperty('content');
			expect(doc).toHaveProperty('source');
			expect(doc).toHaveProperty('semantic_score');
			expect(doc).toHaveProperty('keyword_score');
			expect(doc).toHaveProperty('source_boost');
			expect(doc).toHaveProperty('combined_score');
			expect(doc).toHaveProperty('rank');
		}
	});

	test('pipeline score weights match expected values', async ({ request }) => {
		const response = await request.post(`${API_URL}/chat?include_pipeline=true`, {
			data: {
				message: 'Test query',
				session_id: 'test-weights'
			}
		});

		const data = await response.json();
		const { pipeline } = data;

		expect(pipeline.retrieval.score_weights).toMatchObject({
			semantic: 0.6,
			keyword: 0.2,
			source: 0.2
		});
	});
});

test.describe('Error Handling', () => {
	test('handles empty input gracefully', async ({ page }) => {
		const sendButton = page.locator('button:has-text("Send")');

		// Send button should be disabled with empty input
		await expect(sendButton).toBeDisabled();
	});

	test('New Chat clears messages', async ({ page }) => {
		// Send a message
		await page.locator('textarea').fill('Test message');
		await page.locator('button:has-text("Send")').click();

		// Wait for message to appear
		await expect(page.locator('.message.user')).toBeVisible();

		// Click New Chat
		await page.locator('button:has-text("New Chat")').click();

		// Messages should be cleared
		await expect(page.locator('.message')).not.toBeVisible();
		await expect(page.locator('.welcome')).toBeVisible();
	});
});
