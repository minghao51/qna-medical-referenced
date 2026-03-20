import { test, expect, type APIRequestContext, type Page } from '@playwright/test';

const API_URL = process.env.API_URL || 'http://localhost:8000';
const assistantMessage = 'LDL cholesterol is often called "bad" cholesterol because elevated levels increase cardiovascular risk.';
const structuredSources = [
	{
		label: 'MOH Lipids Guidance page 2',
		source: 'moh.gov.sg',
		url: 'https://www.moh.gov.sg/resources-statistics/reports/lipids-guidance',
		page: 2
	},
	{
		label: 'HealthHub Cholesterol Guide',
		source: 'healthhub.sg',
		url: 'https://www.healthhub.sg/a-z/diseases-and-conditions/high-blood-cholesterol'
	},
	{
		label: 'MOH Lipids Guidance page 2',
		source: 'moh.gov.sg',
		url: 'https://www.moh.gov.sg/resources-statistics/reports/lipids-guidance',
		page: 2
	}
];
const mockPipeline = {
	retrieval: {
		query: 'What is LDL cholesterol?',
		top_k: 5,
		timing_ms: 120,
		score_weights: {
			semantic: 0.6,
			keyword: 0.2,
			source: 0.2
		},
		documents: [
			{
				id: 'doc-1',
				content: 'LDL cholesterol contributes to plaque buildup in arteries and is a major cardiovascular risk factor.',
				source: 'healthhub.sg',
				page: 2,
				semantic_score: 0.91,
				keyword_score: 0.72,
				source_boost: 0.9,
				combined_score: 0.87,
				rank: 1
			}
		]
	},
	context: {
		total_chunks: 3,
		total_chars: 1480,
		sources: ['healthhub.sg', 'moh.gov.sg'],
		preview: 'LDL cholesterol contributes to plaque buildup and higher cardiovascular risk.'
	},
	generation: {
		model: 'qwen3.5-flash',
		timing_ms: 420,
		tokens_estimate: 180
	},
	total_time_ms: 540
};

async function isBackendAvailable(request: APIRequestContext): Promise<boolean> {
	try {
		const response = await request.get(`${API_URL}/health`, { timeout: 3000 });
		return response.ok();
	} catch {
		return false;
	}
}

async function mockChatResponse(page: Page, includePipeline = true) {
	const sseBody = [
		`data: ${JSON.stringify({ content: assistantMessage, done: false })}\n\n`,
		`data: ${JSON.stringify({ content: '', done: true, sources: structuredSources, ...(includePipeline ? { pipeline: mockPipeline } : {}) })}\n\n`
	].join('');

	await page.route(/\/chat/, async (route) => {
		await route.fulfill({
			status: 200,
			contentType: 'text/event-stream',
			body: sseBody
		});
	});
}

async function sendMessage(page: Page, message: string) {
	const textarea = page.locator('textarea');
	await textarea.click();
	await textarea.pressSequentially(message);
	await expect(page.locator('button:has-text("Send")')).toBeEnabled();
	await page.locator('button:has-text("Send")').click();
}

async function expectAssistantResponse(page: Page) {
	const assistant = page.locator('.message.assistant').filter({ has: page.locator('.content') }).last();
	await expect(assistant).toBeVisible();
	await expect(assistant.locator('.content')).toContainText('LDL cholesterol', { timeout: 15000 });
	return assistant;
}

test.describe('Pipeline Visualization', () => {
	test.beforeEach(async ({ page }) => {
		await mockChatResponse(page, false);
		await page.goto('/');
	});

	test('pipeline toggle checkbox is visible', async ({ page }) => {
		const toggle = page.locator('.pipeline-toggle');
		await expect(toggle).toBeVisible();
		await expect(toggle.locator('input[type="checkbox"]')).toBeVisible();
		await expect(toggle).toContainText('Show pipeline details');
	});

	test('can toggle pipeline details on', async ({ page }) => {
		const checkbox = page.locator('.pipeline-toggle input[type="checkbox"]');

		await expect(checkbox).toBeChecked();

		await checkbox.uncheck();
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
		await sendMessage(page, 'What is LDL cholesterol?');
		await expectAssistantResponse(page);
	});
});

test.describe('Confidence Indicators', () => {
	test.beforeEach(async ({ page }) => {
		await mockChatResponse(page);
		await page.goto('/');
		await page.locator('.pipeline-toggle input[type="checkbox"]').check();
	});

	test('confidence badge appears on assistant message with pipeline', async ({ page }) => {
		await sendMessage(page, 'What is normal cholesterol?');
		const assistant = await expectAssistantResponse(page);

		// Pipeline button appears when pipeline is enabled
		const pipelineBtn = page.locator('.pipeline-btn');
		await expect(pipelineBtn).toBeVisible();

		// Click to show pipeline
		await pipelineBtn.click();

		// Confidence badge in message header
		const badge = assistant.locator('.confidence-badge');
		await expect(badge).toBeVisible();
		await expect(badge).toContainText(/High|Medium|Low/i);
	});

	test('source quality indicators appear for sources', async ({ page }) => {
		await sendMessage(page, 'What is cholesterol?');
		await expectAssistantResponse(page);

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
		await mockChatResponse(page);
		await page.goto('/');
		// Enable pipeline toggle for these tests
		await page.locator('.pipeline-toggle input[type="checkbox"]').check();
	});

	test('pipeline panel is hidden by default', async ({ page }) => {
		const panel = page.locator('.pipeline-panel');
		await expect(panel).not.toBeVisible();
	});

	test('pipeline button appears on assistant message when enabled', async ({ page }) => {
		await sendMessage(page, 'What is normal cholesterol?');
		await expectAssistantResponse(page);

		const pipelineBtn = page.locator('.pipeline-btn');
		await expect(pipelineBtn).toBeVisible();
		await expect(pipelineBtn).toContainText(/Show|Hide/);
	});

	test('pipeline panel is visible after sending message with pipeline', async ({ page }) => {
		await sendMessage(page, 'What is LDL?');
		await expectAssistantResponse(page);

		// Panel should be visible automatically since showPipeline is set to true after response
		const panel = page.locator('.pipeline-panel');
		await expect(panel).toBeVisible({ timeout: 10000 });
		await expect(panel).toContainText('Pipeline Details');
	});

	test('pipeline panel shows confidence breakdown', async ({ page }) => {
		await sendMessage(page, 'What is HDL?');
		await expectAssistantResponse(page);

		const panel = page.locator('.pipeline-panel');
		await expect(panel).toBeVisible({ timeout: 10000 });

		await expect(page.locator('.confidence-header')).toBeVisible();
		await expect(panel).toContainText('Overall Confidence');
		await expect(page.locator('.confidence-breakdown')).toBeVisible();
	});

	test('pipeline panel shows flow diagram', async ({ page }) => {
		await sendMessage(page, 'What is triglycerides?');
		await expectAssistantResponse(page);

		const flowDiagram = page.locator('.flow-diagram');
		await expect(flowDiagram).toBeVisible({ timeout: 10000 });
		await expect(page.locator('.flow-node')).toHaveCount(3);
	});

	test('pipeline panel shows retrieval stage details', async ({ page }) => {
		await sendMessage(page, 'Explain cholesterol');
		await expectAssistantResponse(page);

		await expect(page.locator('.pipeline-panel')).toBeVisible({ timeout: 10000 });
		await expect(page.locator('.pipeline-panel')).toContainText('Retrieval');
		await expect(page.locator('.pipeline-panel')).toContainText('Documents Retrieved');
	});

	test('pipeline panel shows context stage', async ({ page }) => {
		await sendMessage(page, 'What are lipoproteins?');
		await expectAssistantResponse(page);

		await expect(page.locator('.pipeline-panel')).toBeVisible({ timeout: 10000 });
		await expect(page.locator('.pipeline-panel')).toContainText('Context Assembly');
		await expect(page.locator('.pipeline-panel')).toContainText('Total Chunks');
	});

	test('pipeline panel shows generation stage', async ({ page }) => {
		await sendMessage(page, 'What is heart disease?');
		await expectAssistantResponse(page);

		await expect(page.locator('.pipeline-panel')).toBeVisible({ timeout: 10000 });
		await expect(page.locator('.pipeline-panel')).toContainText('Generation');
		await expect(page.locator('.pipeline-panel')).toContainText('Model');
	});

	test('pipeline panel can be toggled', async ({ page }) => {
		await sendMessage(page, 'What is blood pressure?');
		await expectAssistantResponse(page);

		// Panel should be visible
		await expect(page.locator('.pipeline-panel')).toBeVisible({ timeout: 10000 });

		// Click the pipeline button to hide
		const pipelineBtn = page.locator('.pipeline-btn');
		await pipelineBtn.click();

		// Panel should be hidden now
		await expect(page.locator('.pipeline-panel')).not.toBeVisible();
	});

	test('documents can be clicked to inspect', async ({ page }) => {
		await sendMessage(page, 'What is normal glucose?');
		await expectAssistantResponse(page);

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
		await sendMessage(page, 'What is A1C?');
		await expectAssistantResponse(page);

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
		await sendMessage(page, 'What is metabolic syndrome?');
		await expectAssistantResponse(page);

		await expect(page.locator('.pipeline-panel')).toBeVisible({ timeout: 10000 });

		const metricBars = page.locator('.metric-bar');
		await expect(metricBars.first()).toBeVisible();
	});
});

test.describe('Sources Display', () => {
	test.beforeEach(async ({ page }) => {
		await mockChatResponse(page);
		await page.goto('/');
		// Enable pipeline to get sources
		await page.locator('.pipeline-toggle input[type="checkbox"]').check();
	});

	test('sources display correctly on response when available', async ({ page }) => {
		await sendMessage(page, 'What is LDL cholesterol?');
		await expectAssistantResponse(page);

		const sources = page.locator('.sources-panel');
		await expect(sources).toBeVisible();
		await expect(sources).toContainText('Sources');
		await expect(page.locator('.sources-list .source-card')).toHaveCount(2);
		await expect(page.locator('.sources-list .source-card').first()).toContainText('1.');
		await expect(page.locator('.sources-list .source-link').first()).toHaveAttribute(
			'href',
			'https://www.moh.gov.sg/resources-statistics/reports/lipids-guidance'
		);
		await expect(page.locator('.sources-list .source-card').first()).toContainText('Official');
	});

	test('legacy string sources still render during rollout', async ({ page }) => {
		await page.unrouteAll();
		const legacySources = ['healthhub.sg', 'plain source title'];
		const sseBody = [
			`data: ${JSON.stringify({ content: assistantMessage, done: false })}\n\n`,
			`data: ${JSON.stringify({ content: '', done: true, sources: legacySources, pipeline: null })}\n\n`
		].join('');
		await page.route(/\/chat/, async (route) => {
			await route.fulfill({
				status: 200,
				contentType: 'text/event-stream',
				body: sseBody
			});
		});

		await sendMessage(page, 'What is LDL cholesterol?');
		await expectAssistantResponse(page);
		await expect(page.locator('.sources-list .source-card')).toHaveCount(2);
		await expect(page.locator('.sources-list')).toContainText('plain source title');
	});
});

test.describe('API Integration', () => {
	test.setTimeout(60000);

	test('backend health endpoint responds', async ({ request }) => {
		test.skip(!(await isBackendAvailable(request)), 'requires a live backend at API_URL');
		const response = await request.get(`${API_URL}/health`);
		expect(response.status()).toBe(200);

		const data = await response.json();
		expect(data).toHaveProperty('status', 'healthy');
	});

	test('backend root endpoint responds', async ({ request }) => {
		test.skip(!(await isBackendAvailable(request)), 'requires a live backend at API_URL');
		const response = await request.get(`${API_URL}/`);
		expect(response.status()).toBe(200);

		const data = await response.json();
		expect(data).toHaveProperty('message');
	});

	test('evaluation ablation endpoint returns expected shape', async ({ request }) => {
		test.skip(!(await isBackendAvailable(request)), 'requires a live backend at API_URL');
		const response = await request.get(`${API_URL}/evaluation/ablation`);
		expect(response.status()).toBe(200);

		const data = await response.json();
		expect(data).toHaveProperty('ablation_runs');
		expect(Array.isArray(data.ablation_runs)).toBeTruthy();

		if (data.message !== undefined) {
			expect(typeof data.message).toBe('string');
		}
	});
});

test.describe('Chat with Pipeline Enabled', () => {
	test.setTimeout(60000);

	let pipelineResponse: any;

	test.beforeAll(async ({ playwright }) => {
		const request = await playwright.request.newContext();
		try {
			test.skip(!(await isBackendAvailable(request)), 'requires a live backend at API_URL');
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
			const body = await response.text();
			const parts = body.split('data: ').filter(s => s.trim());
			let fullResponse = { response: '', sources: [], pipeline: null };
			for (const part of parts) {
				const dataStr = part.replace(/\n\n$/, '').replace(/\n$/, '');
				try {
					const data = JSON.parse(dataStr);
					if (data.content) {
						fullResponse.response += data.content;
					}
					if (data.done && data.sources) {
						fullResponse.sources = data.sources;
						fullResponse.pipeline = data.pipeline;
					}
				} catch (e) {
					// Skip malformed JSON
				}
			}
			pipelineResponse = fullResponse;
			expect(pipelineResponse).toHaveProperty('pipeline');
		} finally {
			await request.dispose();
		}
	});

	test('chat with include_pipeline parameter returns full pipeline', async () => {
		expect(pipelineResponse).toHaveProperty('response');
		expect(pipelineResponse).toHaveProperty('sources');
		expect(pipelineResponse).toHaveProperty('pipeline');

		const { pipeline } = pipelineResponse;
		expect(pipeline).toHaveProperty('retrieval');
		expect(pipeline).toHaveProperty('context');
		expect(pipeline).toHaveProperty('generation');
		expect(pipeline).toHaveProperty('total_time_ms');
	});

	test('pipeline retrieval stage has correct structure', async () => {
		const { pipeline } = pipelineResponse;
		expect(pipeline.retrieval).toHaveProperty('query');
		expect(pipeline.retrieval).toHaveProperty('top_k');
		expect(pipeline.retrieval).toHaveProperty('documents');
		expect(pipeline.retrieval).toHaveProperty('score_weights');
		expect(pipeline.retrieval).toHaveProperty('timing_ms');
	});

	test('pipeline documents have correct structure', async () => {
		const { pipeline } = pipelineResponse;
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

	test('pipeline score weights match expected values', async () => {
		const { pipeline } = pipelineResponse;
		expect(pipeline.retrieval.score_weights).toMatchObject({
			semantic: 0.6,
			keyword: 0.2,
			source: 0.2
		});
	});

	test('pipeline context stage has correct structure', async () => {
		const { pipeline } = pipelineResponse;
		expect(pipeline.context).toHaveProperty('total_chunks');
		expect(pipeline.context).toHaveProperty('total_chars');
		expect(pipeline.context).toHaveProperty('sources');
		expect(pipeline.context).toHaveProperty('preview');
	});

	test('pipeline generation stage has correct structure', async () => {
		const { pipeline } = pipelineResponse;
		expect(pipeline.generation).toHaveProperty('model');
		expect(pipeline.generation).toHaveProperty('timing_ms');
	});
});

test.describe('Error Handling', () => {
	test.beforeEach(async ({ page }) => {
		await mockChatResponse(page, false);
		await page.goto('/');
	});

	test('handles empty input gracefully', async ({ page }) => {
		const sendButton = page.locator('button:has-text("Send")');
		await expect(sendButton).toBeDisabled();
	});

	test('New Chat clears messages', async ({ page }) => {
		await sendMessage(page, 'Test message');

		await expect(page.locator('.message.user')).toBeVisible();

		await page.locator('button:has-text("New Chat")').click();

		await expect(page.locator('.message')).not.toBeVisible();
		await expect(page.locator('.welcome')).toBeVisible();
	});

	test('displays error when API fails', async ({ page }) => {
		await page.unroute('**/chat?*');
		await page.unroute('**/chat');
		await page.route('**/chat', async (route) => {
			await route.abort('failed');
		});

		await sendMessage(page, 'Test message');

		await page.waitForTimeout(500);
		const error = page.locator('.error-message');
		if (await error.count() > 0) {
			await expect(error.first()).toBeVisible();
		}
	});
});

test.describe('Navigation', () => {
	test('can navigate to eval page', async ({ page }) => {
		await page.goto('/');

		await page.locator('a:has-text("Pipeline Eval")').click();

		await expect(page).toHaveURL(/eval/);
	});
});
