import { test, expect, type Page } from '@playwright/test';

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
	}
];

async function mockChatResponse(page: Page) {
	const sseBody = [
		`data: ${JSON.stringify({ content: assistantMessage, done: false })}\n\n`,
		`data: ${JSON.stringify({ content: '', done: true, sources: structuredSources, pipeline: null })}\n\n`
	].join('');

	await page.route(/\/chat/, async (route) => {
		await route.fulfill({
			status: 200,
			contentType: 'text/event-stream',
			body: sseBody
		});
	});
}

async function mockHistoryApi(page: Page) {
	await page.route(/\/history/, async (route) => {
		if (route.request().method() === 'DELETE') {
			await route.fulfill({ status: 204, body: '' });
			return;
		}
		await route.fulfill({
			status: 200,
			contentType: 'application/json',
			body: JSON.stringify({ history: [] })
		});
	});
}

test('chat page loads correctly', async ({ page }) => {
	await mockChatResponse(page);
	await mockHistoryApi(page);
	await page.goto('/ask');
	await page.locator('.chat-container[data-hydrated="true"]').waitFor();

  // Check page title
  await expect(page).toHaveTitle(/Ask · Fieldnote/);

  // Check header
  await expect(page.locator('h1')).toContainText('Ask the evidence.');

  // Check welcome message
  await expect(page.locator('.welcome')).toContainText('indexed public or synthetic corpus');

  // Check input area exists
  await expect(page.locator('textarea')).toBeVisible();
  await expect(page.locator('button:has-text("Send")')).toBeVisible();

  // Check New Chat button
  await expect(page.locator('button:has-text("New Chat")')).toBeVisible();
});

test('can type in input field', async ({ page }) => {
	await mockChatResponse(page);
	await mockHistoryApi(page);
	await page.goto('/ask');
	await page.locator('.chat-container[data-hydrated="true"]').waitFor();

  const input = page.locator('textarea');
  await input.click();
  await input.pressSequentially('Test question');
  await page.waitForTimeout(300);

  await expect(input).toHaveValue('Test question');
});

test('send button is disabled when input is empty', async ({ page }) => {
	await mockChatResponse(page);
	await mockHistoryApi(page);
	await page.goto('/ask');
	await page.locator('.chat-container[data-hydrated="true"]').waitFor();

  const sendButton = page.locator('button:has-text("Send")');
  await expect(sendButton).toBeDisabled();
});

test('EOF without a terminal event stays explicitly incomplete', async ({ page }) => {
	await page.route(/\/chat/, async (route) => {
		await route.fulfill({
			status: 200,
			contentType: 'text/event-stream',
			body: `data: ${JSON.stringify({ content: 'Partial answer', done: false })}\n\n`
		});
	});
	await mockHistoryApi(page);
	await page.goto('/ask');
	await page.locator('.chat-container[data-hydrated="true"]').waitFor();

	await page.locator('textarea').fill('question');
	await page.getByRole('button', { name: 'Send' }).click();

	const assistant = page.locator('.message.assistant').last();
	await expect(assistant).toContainText('Partial answer');
	await expect(assistant.locator('.turn-status')).toHaveText('Incomplete');
	await expect(assistant.locator('.turn-status')).not.toHaveText('Complete');
	await expect(assistant.getByRole('button', { name: 'Ask again' })).toBeVisible();
});

test('loading exposes Stop response and abort keeps partial output incomplete', async ({ page }) => {
	let release: (() => void) | undefined;
	const gate = new Promise<void>((resolve) => {
		release = resolve;
	});
	await page.route(/\/chat/, async (route) => {
		await gate;
		await route
			.fulfill({
				status: 200,
				contentType: 'text/event-stream',
				body: `data: ${JSON.stringify({ content: 'Partial answer', done: false })}\n\n`
			})
			.catch(() => undefined);
	});
	await mockHistoryApi(page);
	await page.goto('/ask');
	await page.locator('.chat-container[data-hydrated="true"]').waitFor();

	await page.locator('textarea').fill('question');
	await page.getByRole('button', { name: 'Send' }).click();
	await expect(page.getByRole('button', { name: 'Stop response' })).toBeVisible();

	await page.getByRole('button', { name: 'Stop response' }).click();
	const assistant = page.locator('.message.assistant').last();
	await expect(assistant.locator('.turn-status')).toHaveText('Incomplete');
	await expect(assistant.getByRole('button', { name: 'Ask again' })).toBeVisible();
	release?.();
});

test('terminal error after content is distinct from success', async ({ page }) => {
	await page.route(/\/chat/, async (route) => {
		const body = [
			`data: ${JSON.stringify({ content: 'Partial answer', done: false })}\n\n`,
			`data: ${JSON.stringify({
				done: true,
				error: 'generation failed',
				error_code: 'chat_failed',
				request_id: 'req-1'
			})}\n\n`
		].join('');
		await route.fulfill({ status: 200, contentType: 'text/event-stream', body });
	});
	await mockHistoryApi(page);
	await page.goto('/ask');
	await page.locator('.chat-container[data-hydrated="true"]').waitFor();

	await page.locator('textarea').fill('question');
	await page.getByRole('button', { name: 'Send' }).click();

	const assistant = page.locator('.message.assistant').last();
	await expect(assistant).toContainText('Partial answer');
	await expect(assistant.locator('.turn-status')).toHaveText('Error');
	await expect(page.locator('div.error')).toContainText('[chat_failed] generation failed');
	await expect(page.locator('div.error')).toContainText('(request req-1)');
});

test('draft survives ordinary in-app navigation', async ({ page }) => {
	await mockChatResponse(page);
	await mockHistoryApi(page);
	await page.goto('/ask');
	await page.locator('.chat-container[data-hydrated="true"]').waitFor();
	await page.locator('textarea').fill('unfinished draft');
	await page.getByRole('link', { name: 'Fieldnote overview' }).click();
	await page.getByRole('link', { name: 'Ask', exact: true }).click();
	await page.locator('.chat-container[data-hydrated="true"]').waitFor();
	await expect(page.locator('textarea')).toHaveValue('unfinished draft');
});
