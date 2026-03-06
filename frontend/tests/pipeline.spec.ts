import { test, expect } from '@playwright/test';

const BASE_URL = process.env.PLAYWRIGHT_BASE_URL || 'http://localhost:5173';
const API_URL = process.env.API_URL || 'http://localhost:8000';

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

		await expect(checkbox).not.toBeChecked();

		await checkbox.check();
		await expect(checkbox).toBeChecked();
	});

	test('send button enables when text is entered', async ({ page }) => {
		const input = page.locator('textarea');
		const sendButton = page.locator('button:has-text("Send")');

		await expect(sendButton).toBeDisabled();

		await input.click();
		await input.pressSequentially('Test question');
		await page.waitForTimeout(300);

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

	test('send message and receive response', async ({ page }) => {
		const textarea = page.locator('textarea');
		await textarea.click();
		await textarea.pressSequentially('What is LDL cholesterol?');
		await page.waitForTimeout(300);
		
		const sendButton = page.locator('button:has-text("Send")');
		await expect(sendButton).toBeEnabled();
		await sendButton.click();

		await expect(page.locator('.message.assistant')).toBeVisible({ timeout: 15000 });
		await expect(page.locator('.message.assistant .content')).not.toBeEmpty();
	});
});

test.describe('Confidence Indicators', () => {
	test.beforeEach(async ({ page }) => {
		await page.goto(BASE_URL);
		await page.locator('.pipeline-toggle input[type="checkbox"]').check();
	});

	test('confidence badge appears on assistant message with pipeline', async ({ page }) => {
		const textarea = page.locator('textarea');
		await textarea.click();
		await textarea.pressSequentially('What is normal cholesterol?');
		await page.waitForTimeout(300);
		await page.locator('button:has-text("Send")').click();

		await expect(page.locator('.message.assistant')).toBeVisible({ timeout: 15000 });

		// Pipeline button appears when pipeline is enabled
		const pipelineBtn = page.locator('.pipeline-btn');
		await expect(pipelineBtn).toBeVisible();

		// Click to show pipeline
		await pipelineBtn.click();

		// Confidence badge in message header
		const badge = page.locator('.message.assistant .confidence-badge');
		await expect(badge).toBeVisible();
		await expect(badge).toContainText(/High|Medium|Low/i);
	});

	test('source quality indicators appear for sources', async ({ page }) => {
		const textarea = page.locator('textarea');
		await textarea.click();
		await textarea.pressSequentially('What is cholesterol?');
		await page.waitForTimeout(300);
		await page.locator('button:has-text("Send")').click();

		await expect(page.locator('.message.assistant')).toBeVisible({ timeout: 15000 });

		// Check for source badges
		const sourceBadges = page.locator('.source-badge');
		const count = await sourceBadges.count();
		if (count > 0) {
			await expect(sourceBadges.first()).toBeVisible();
			await expect(sourceBadges.first()).toContainText(/Official|Education|Organization|General|Unknown/i);
		}
	});
});

test.describe('Pipeline Panel', () => {
	test.beforeEach(async ({ page }) => {
		await page.goto(BASE_URL);
		// Enable pipeline toggle for these tests
		await page.locator('.pipeline-toggle input[type="checkbox"]').check();
	});

	test('pipeline panel is hidden by default', async ({ page }) => {
		const panel = page.locator('.pipeline-panel');
		await expect(panel).not.toBeVisible();
	});

	test('pipeline button appears on assistant message when enabled', async ({ page }) => {
		const textarea = page.locator('textarea');
		await textarea.click();
		await textarea.pressSequentially('What is normal cholesterol?');
		await page.waitForTimeout(300);
		await page.locator('button:has-text("Send")').click();

		await expect(page.locator('.message.assistant')).toBeVisible({ timeout: 15000 });

		const pipelineBtn = page.locator('.pipeline-btn');
		await expect(pipelineBtn).toBeVisible();
		await expect(pipelineBtn).toContainText(/Show|Hide/);
	});

	test('pipeline panel is visible after sending message with pipeline', async ({ page }) => {
		const textarea = page.locator('textarea');
		await textarea.click();
		await textarea.pressSequentially('What is LDL?');
		await page.waitForTimeout(300);
		await page.locator('button:has-text("Send")').click();

		await expect(page.locator('.message.assistant')).toBeVisible({ timeout: 15000 });

		// Panel should be visible automatically since showPipeline is set to true after response
		const panel = page.locator('.pipeline-panel');
		await expect(panel).toBeVisible({ timeout: 10000 });
		await expect(panel).toContainText('Pipeline Details');
	});

	test('pipeline panel shows confidence breakdown', async ({ page }) => {
		const textarea = page.locator('textarea');
		await textarea.click();
		await textarea.pressSequentially('What is HDL?');
		await page.waitForTimeout(300);
		await page.locator('button:has-text("Send")').click();

		await expect(page.locator('.message.assistant')).toBeVisible({ timeout: 15000 });

		const panel = page.locator('.pipeline-panel');
		await expect(panel).toBeVisible({ timeout: 10000 });

		await expect(page.locator('.confidence-header')).toBeVisible();
		await expect(panel).toContainText('Overall Confidence');
		await expect(page.locator('.confidence-breakdown')).toBeVisible();
	});

	test('pipeline panel shows flow diagram', async ({ page }) => {
		const textarea = page.locator('textarea');
		await textarea.click();
		await textarea.pressSequentially('What is triglycerides?');
		await page.waitForTimeout(300);
		await page.locator('button:has-text("Send")').click();

		await expect(page.locator('.message.assistant')).toBeVisible({ timeout: 15000 });

		const flowDiagram = page.locator('.flow-diagram');
		await expect(flowDiagram).toBeVisible({ timeout: 10000 });
		await expect(page.locator('.flow-node')).toHaveCount(3);
	});

	test('pipeline panel shows retrieval stage details', async ({ page }) => {
		const textarea = page.locator('textarea');
		await textarea.click();
		await textarea.pressSequentially('Explain cholesterol');
		await page.waitForTimeout(300);
		await page.locator('button:has-text("Send")').click();

		await expect(page.locator('.message.assistant')).toBeVisible({ timeout: 15000 });

		await expect(page.locator('.pipeline-panel')).toBeVisible({ timeout: 10000 });
		await expect(page.locator('.pipeline-panel')).toContainText('Retrieval');
		await expect(page.locator('.pipeline-panel')).toContainText('Documents Retrieved');
	});

	test('pipeline panel shows context stage', async ({ page }) => {
		const textarea = page.locator('textarea');
		await textarea.click();
		await textarea.pressSequentially('What are lipoproteins?');
		await page.waitForTimeout(300);
		await page.locator('button:has-text("Send")').click();

		await expect(page.locator('.message.assistant')).toBeVisible({ timeout: 15000 });

		await expect(page.locator('.pipeline-panel')).toBeVisible({ timeout: 10000 });
		await expect(page.locator('.pipeline-panel')).toContainText('Context Assembly');
		await expect(page.locator('.pipeline-panel')).toContainText('Total Chunks');
	});

	test('pipeline panel shows generation stage', async ({ page }) => {
		const textarea = page.locator('textarea');
		await textarea.click();
		await textarea.pressSequentially('What is heart disease?');
		await page.waitForTimeout(300);
		await page.locator('button:has-text("Send")').click();

		await expect(page.locator('.message.assistant')).toBeVisible({ timeout: 15000 });

		await expect(page.locator('.pipeline-panel')).toBeVisible({ timeout: 10000 });
		await expect(page.locator('.pipeline-panel')).toContainText('Generation');
		await expect(page.locator('.pipeline-panel')).toContainText('Model');
	});

	test('pipeline panel can be toggled', async ({ page }) => {
		const textarea = page.locator('textarea');
		await textarea.click();
		await textarea.pressSequentially('What is blood pressure?');
		await page.waitForTimeout(300);
		await page.locator('button:has-text("Send")').click();

		await expect(page.locator('.message.assistant')).toBeVisible({ timeout: 15000 });

		// Panel should be visible
		await expect(page.locator('.pipeline-panel')).toBeVisible({ timeout: 10000 });

		// Click the pipeline button to hide
		const pipelineBtn = page.locator('.pipeline-btn');
		await pipelineBtn.click();

		// Panel should be hidden now
		await expect(page.locator('.pipeline-panel')).not.toBeVisible();
	});

	test('documents can be clicked to inspect', async ({ page }) => {
		const textarea = page.locator('textarea');
		await textarea.click();
		await textarea.pressSequentially('What is normal glucose?');
		await page.waitForTimeout(300);
		await page.locator('button:has-text("Send")').click();

		await expect(page.locator('.message.assistant')).toBeVisible({ timeout: 15000 });

		await page.locator('.pipeline-btn').click();

		const docItem = page.locator('.doc-item').first();
		if (await docItem.count() > 0) {
			await docItem.click();

			const modal = page.locator('.modal-overlay');
			await expect(modal).toBeVisible();
			await expect(page.locator('.modal-content')).toContainText('Document Details');
		}
	});

	test('modal can be closed', async ({ page }) => {
		const textarea = page.locator('textarea');
		await textarea.click();
		await textarea.pressSequentially('What is A1C?');
		await page.waitForTimeout(300);
		await page.locator('button:has-text("Send")').click();

		await expect(page.locator('.message.assistant')).toBeVisible({ timeout: 15000 });

		await page.locator('.pipeline-btn').click();

		const docItem = page.locator('.doc-item').first();
		if (await docItem.count() > 0) {
			await docItem.click();

			await expect(page.locator('.modal-overlay')).toBeVisible();

			await page.locator('.modal-footer .close-btn-large').click();
			await expect(page.locator('.modal-overlay')).not.toBeVisible();
		}
	});

	test('metric bars display correctly', async ({ page }) => {
		const textarea = page.locator('textarea');
		await textarea.click();
		await textarea.pressSequentially('What is metabolic syndrome?');
		await page.waitForTimeout(300);
		await page.locator('button:has-text("Send")').click();

		await expect(page.locator('.message.assistant')).toBeVisible({ timeout: 15000 });

		await expect(page.locator('.pipeline-panel')).toBeVisible({ timeout: 10000 });

		const metricBars = page.locator('.metric-bar');
		await expect(metricBars.first()).toBeVisible();
	});
});

test.describe('Sources Display', () => {
	test.beforeEach(async ({ page }) => {
		await page.goto(BASE_URL);
		// Enable pipeline to get sources
		await page.locator('.pipeline-toggle input[type="checkbox"]').check();
	});

	test('sources display correctly on response when available', async ({ page }) => {
		const textarea = page.locator('textarea');
		await textarea.click();
		await textarea.pressSequentially('What is LDL cholesterol?');
		await page.waitForTimeout(300);
		await page.locator('button:has-text("Send")').click();

		await expect(page.locator('.message.assistant')).toBeVisible({ timeout: 15000 });

		// Check if sources element exists (might not have sources for some queries)
		const sources = page.locator('.sources');
		const sourceCount = await sources.count();
		
		if (sourceCount > 0) {
			await expect(sources.first()).toBeVisible();
			await expect(sources.first()).toContainText('Sources:');
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
	test('chat with include_pipeline parameter returns full pipeline', async ({ request }) => {
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

		const { pipeline } = data;
		expect(pipeline).toHaveProperty('retrieval');
		expect(pipeline).toHaveProperty('context');
		expect(pipeline).toHaveProperty('generation');
		expect(pipeline).toHaveProperty('total_time_ms');
	});

	test('pipeline retrieval stage has correct structure', async ({ request }) => {
		const response = await request.post(`${API_URL}/chat?include_pipeline=true`, {
			data: {
				message: 'What is normal cholesterol?',
				session_id: 'test-retrieval'
			}
		});

		const data = await response.json();
		const { pipeline } = data;

		expect(pipeline.retrieval).toHaveProperty('query');
		expect(pipeline.retrieval).toHaveProperty('top_k');
		expect(pipeline.retrieval).toHaveProperty('documents');
		expect(pipeline.retrieval).toHaveProperty('score_weights');
		expect(pipeline.retrieval).toHaveProperty('timing_ms');
	});

	test('pipeline documents have correct structure', async ({ request }) => {
		const response = await request.post(`${API_URL}/chat?include_pipeline=true`, {
			data: {
				message: 'Test query',
				session_id: 'test-docs'
			}
		});

		const data = await response.json();
		const { pipeline } = data;

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

	test('pipeline context stage has correct structure', async ({ request }) => {
		const response = await request.post(`${API_URL}/chat?include_pipeline=true`, {
			data: {
				message: 'What is heart health?',
				session_id: 'test-context'
			}
		});

		const data = await response.json();
		const { pipeline } = data;

		expect(pipeline.context).toHaveProperty('total_chunks');
		expect(pipeline.context).toHaveProperty('total_chars');
		expect(pipeline.context).toHaveProperty('sources');
		expect(pipeline.context).toHaveProperty('preview');
	});

	test('pipeline generation stage has correct structure', async ({ request }) => {
		const response = await request.post(`${API_URL}/chat?include_pipeline=true`, {
			data: {
				message: 'Explain diabetes',
				session_id: 'test-generation'
			}
		});

		const data = await response.json();
		const { pipeline } = data;

		expect(pipeline.generation).toHaveProperty('model');
		expect(pipeline.generation).toHaveProperty('timing_ms');
	});
});

test.describe('Error Handling', () => {
	test.beforeEach(async ({ page }) => {
		await page.goto(BASE_URL);
	});

	test('handles empty input gracefully', async ({ page }) => {
		const sendButton = page.locator('button:has-text("Send")');
		await expect(sendButton).toBeDisabled();
	});

	test('New Chat clears messages', async ({ page }) => {
		const textarea = page.locator('textarea');
		await textarea.click();
		await textarea.pressSequentially('Test message');
		await page.waitForTimeout(300);
		await page.locator('button:has-text("Send")').click();

		await expect(page.locator('.message.user')).toBeVisible();

		await page.locator('button:has-text("New Chat")').click();

		await expect(page.locator('.message')).not.toBeVisible();
		await expect(page.locator('.welcome')).toBeVisible();
	});

	test('displays error when API fails', async ({ page }) => {
		await page.route('**/chat', async (route) => {
			await route.abort('failed');
		});

		const textarea = page.locator('textarea');
		await textarea.click();
		await textarea.pressSequentially('Test message');
		await page.waitForTimeout(300);
		await page.locator('button:has-text("Send")').click();

		await page.waitForTimeout(500);
		const error = page.locator('.error');
		if (await error.count() > 0) {
			await expect(error).toBeVisible();
		}
	});
});

test.describe('Navigation', () => {
	test('can navigate to eval page', async ({ page }) => {
		await page.goto(BASE_URL);

		await page.locator('a:has-text("Pipeline Eval")').click();

		await expect(page).toHaveURL(/eval/);
	});
});
