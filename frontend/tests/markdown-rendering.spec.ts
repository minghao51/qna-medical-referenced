import { test, expect, type Page } from '@playwright/test';

const markdownFixture = `
# Health Summary

Here is a [trusted source](https://example.com/reference) and an unsafe [bad link](javascript:alert('xss')).

| Test | Value |
| --- | --- |
| HbA1c | 5.4% |
| LDL | 110 mg/dL |

\`\`\`python
print("monitor cholesterol")
\`\`\`

Inline \`code\` still works.

<script>window.__markdown_xss = true</script>
`;

async function mockChatApi(page: Page) {
	await page.route('**/history**', async (route) => {
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

	const sseBody = [
		`data: ${JSON.stringify({ content: markdownFixture, done: false })}\n\n`,
		`data: ${JSON.stringify({ content: '', done: true, sources: [], pipeline: null })}\n\n`
	].join('');

	await page.route(/\/chat/, async (route) => {
		await route.fulfill({
			status: 200,
			contentType: 'text/event-stream',
			body: sseBody
		});
	});
}

test.describe('Markdown Rendering', () => {
	test.beforeEach(async ({ page, baseURL, context }) => {
		await context.grantPermissions(['clipboard-read', 'clipboard-write']);
		await mockChatApi(page);
		await page.goto(baseURL || 'http://127.0.0.1:5174');
	});

	test('renders markdown structure with deterministic content', async ({ page }) => {
		await page.locator('textarea').fill('show markdown');
		await page.getByRole('button', { name: 'Send' }).click();

		const assistantMessage = page.locator('.message.assistant').last();
		await expect(assistantMessage.getByRole('heading', { level: 1, name: 'Health Summary' })).toBeVisible();
		await expect(assistantMessage.locator('table')).toBeVisible();
		await expect(assistantMessage.locator('tbody tr')).toHaveCount(2);
		await expect(assistantMessage.locator('code').filter({ hasText: 'code' })).toBeVisible();
	});

	test('highlights code blocks and exposes copy affordance', async ({ page }) => {
		await page.locator('textarea').fill('show code');
		await page.getByRole('button', { name: 'Send' }).click();

		const assistantMessage = page.locator('.message.assistant').last();
		const codeBlock = assistantMessage.locator('.code-block');
		await expect(codeBlock).toBeVisible();
		await expect(codeBlock.locator('.code-block__language')).toHaveText('python');
		await expect(codeBlock.locator('code.hljs')).toBeVisible();

		const copyButton = codeBlock.getByRole('button', { name: 'Copy code block' });
		await copyButton.click();
		await expect(copyButton).toContainText('Copied');
	});

	test('blocks raw html execution and unsafe links', async ({ page }) => {
		await page.locator('textarea').fill('show unsafe markdown');
		await page.getByRole('button', { name: 'Send' }).click();

		const assistantMessage = page.locator('.message.assistant').last();
		await expect(assistantMessage.locator('script')).toHaveCount(0);

		const renderedText = await assistantMessage.textContent();
		expect(renderedText).toContain('<script>window.__markdown_xss = true</script>');
		expect(await page.evaluate(() => (window as typeof window & { __markdown_xss?: boolean }).__markdown_xss)).toBeUndefined();

		const trustedLink = assistantMessage.getByRole('link', { name: 'trusted source' });
		await expect(trustedLink).toHaveAttribute('href', 'https://example.com/reference');
		await expect(trustedLink).toHaveAttribute('target', '_blank');

		const badLink = assistantMessage.getByText('bad link');
		await expect(badLink).toBeVisible();
		await expect(badLink.evaluate((element) => element.tagName)).resolves.toBe('SPAN');
	});

	test('keeps markdown tables usable on mobile', async ({ page }) => {
		await page.setViewportSize({ width: 390, height: 844 });
		await page.locator('textarea').fill('show mobile markdown');
		await page.getByRole('button', { name: 'Send' }).click();

		const table = page.locator('.message.assistant table').last();
		await expect(table).toBeVisible();
		await expect(table.evaluate((element) => window.getComputedStyle(element).overflowX)).resolves.toBe('auto');
	});
});
