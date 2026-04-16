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
	await page.goto('/');
  
  // Check page title
  await expect(page).toHaveTitle(/Health Screening Q&A/);
  
  // Check header
  await expect(page.locator('h1')).toContainText('Health Screening Q&A');
  
  // Check welcome message
  await expect(page.locator('.welcome')).toContainText('health screening results');
  
  // Check input area exists
  await expect(page.locator('textarea')).toBeVisible();
  await expect(page.locator('button:has-text("Send")')).toBeVisible();
  
  // Check New Chat button
  await expect(page.locator('button:has-text("New Chat")')).toBeVisible();
});

test('can type in input field', async ({ page }) => {
	await mockChatResponse(page);
	await mockHistoryApi(page);
	await page.goto('/');
  
  const input = page.locator('textarea');
  await input.click();
  await input.pressSequentially('Test question');
  await page.waitForTimeout(300);
  
  await expect(input).toHaveValue('Test question');
});

test('send button is disabled when input is empty', async ({ page }) => {
	await mockChatResponse(page);
	await mockHistoryApi(page);
	await page.goto('/');
  
  const sendButton = page.locator('button:has-text("Send")');
  await expect(sendButton).toBeDisabled();
});
