import { test, expect, type Page } from '@playwright/test';

const pdfItem = {
	id: 'pdf-1',
	source: 'guidelines/lipid.pdf',
	page: 4,
	source_type: 'pdf',
	source_class: 'guideline_pdf',
	content_type: 'paragraph',
	content_preview: 'LDL-C contributes to plaque buildup in arteries.',
	content_length: 1200,
	canonical_label: 'Lipid guideline',
	display_label: null,
	logical_name: 'lipid_guideline',
	source_url: 'https://example.org/guideline',
	domain: 'example.org'
};

const htmlItem = {
	id: 'html-1',
	source: 'pages/healthhub.html',
	page: 1,
	source_type: 'html',
	source_class: 'healthhub_html',
	content_type: 'paragraph',
	content_preview: 'A healthy diet supports cholesterol management.',
	content_length: 900,
	canonical_label: 'HealthHub cholesterol',
	display_label: null,
	logical_name: 'healthhub_cholesterol',
	source_url: 'https://www.healthhub.sg/cholesterol',
	domain: 'www.healthhub.sg'
};

const globalCounts = { pdf: 1306, html: 597, reference_csv: 460, markdown: 110 };

async function mockEvidenceApi(page: Page) {
	const requests: string[] = [];
	await page.route(/\/documents\?.*$/, async (route) => {
		if (route.request().resourceType() !== 'fetch') {
			await route.continue();
			return;
		}
		const url = new URL(route.request().url());
		requests.push(url.search);
		const sourceType = url.searchParams.get('source_type') ?? '';
		const filtered = sourceType === 'pdf';
		await route.fulfill({
			status: 200,
			contentType: 'application/json',
			body: JSON.stringify({
				total: filtered ? 1306 : 2473,
				offset: Number(url.searchParams.get('offset') ?? 0),
				limit: Number(url.searchParams.get('limit') ?? 50),
				items: filtered ? [pdfItem] : [pdfItem, htmlItem],
				source_type_counts: filtered ? { pdf: 1306 } : globalCounts,
				global_source_type_counts: globalCounts,
				index_metadata: {},
				index_identity: 'd'.repeat(64)
			})
		});
	});

	await page.route(/\/documents\/pdf-1$/, async (route) => {
		await route.fulfill({
			status: 200,
			contentType: 'application/json',
			body: JSON.stringify({
				id: pdfItem.id,
				content: 'LDL-C contributes to plaque buildup in arteries.',
				metadata: {},
				content_length: pdfItem.content_length,
				canonical_label: pdfItem.canonical_label,
				display_label: null,
				logical_name: pdfItem.logical_name,
				source_url: pdfItem.source_url,
				domain: pdfItem.domain,
				source_type: 'pdf',
				source_class: 'guideline_pdf',
				page: 4
			})
		});
	});

	await page.route(/\/documents\/html-1$/, async (route) => {
		await route.fulfill({
			status: 200,
			contentType: 'application/json',
			body: JSON.stringify({
				id: htmlItem.id,
				content: 'HTML content',
				metadata: {},
				content_length: 12,
				canonical_label: htmlItem.canonical_label,
				display_label: null,
				logical_name: htmlItem.logical_name,
				source_url: 'javascript:alert(1)',
				domain: htmlItem.domain,
				source_type: 'html',
				source_class: 'healthhub_html',
				page: 1
			})
		});
	});

	await page.route(/\/documents\/missing-id$/, async (route) => {
		await route.fulfill({
			status: 404,
			contentType: 'application/json',
			body: JSON.stringify({ detail: 'Document not found' })
		});
	});

	return requests;
}

test('evidence facets keep global counts while filtering results', async ({ page }) => {
	const requests = await mockEvidenceApi(page);
	await page.goto('/evidence');

	await expect(page.getByRole('heading', { name: 'What is in the frozen index?' })).toBeVisible();
	await expect(page.getByRole('button', { name: 'All (2,473)' })).toBeVisible();
	await expect(page.getByRole('button', { name: 'pdf (1,306)' })).toBeVisible();
	await expect(page.getByRole('button', { name: 'html (597)' })).toBeVisible();
	await expect(page.getByRole('button', { name: 'reference csv (460)' })).toBeVisible();
	await expect(page.locator('.identity-note')).toContainText('recorded source snapshot digest');
	await expect(page.locator('.evidence-table tbody tr')).toHaveCount(2);
	await expect(page.getByText('PDF page 4')).toBeVisible();
	await expect(page.getByText('Not provided')).toBeVisible();
	await expect(
		page.getByRole('link', { name: 'Inspect Lipid guideline, PDF page 4, result 1' })
	).toBeVisible();

	await page.getByRole('button', { name: 'pdf (1,306)' }).click();
	await expect(page).toHaveURL(/source_type=pdf/);
	await expect(page.getByRole('button', { name: 'All (2,473)' })).toBeVisible();
	await expect(page.locator('.result-summary')).toContainText('of 1,306');
	await expect(page.locator('.result-summary')).toContainText('All index 2,473');
	await expect(page.locator('.evidence-table tbody tr')).toHaveCount(1);
	expect(requests.some((query) => query.includes('source_type=pdf'))).toBe(true);

	await page.getByRole('button', { name: 'All (2,473)' }).click();
	await expect(page).toHaveURL(/\/evidence$/);
	await expect(page.locator('.evidence-table tbody tr')).toHaveCount(2);
});

test('browser back restores the previous evidence filter', async ({ page }) => {
	await mockEvidenceApi(page);
	await page.goto('/evidence');
	await page.getByRole('button', { name: 'pdf (1,306)' }).click();
	await expect(page).toHaveURL(/source_type=pdf/);
	await page.goBack();
	await expect(page).toHaveURL(/\/evidence$/);
	await expect(page.locator('.evidence-table tbody tr')).toHaveCount(2);
	await expect(page.getByRole('button', { name: 'All (2,473)' })).toHaveClass(/active/);
});

test('chunk detail shows the indexed excerpt, safe original link and PDF page only', async ({
	page
}) => {
	await mockEvidenceApi(page);
	await page.goto('/evidence/pdf-1');

	await expect(page.getByRole('heading', { name: 'Lipid guideline' })).toBeVisible();
	await expect(page.getByRole('link', { name: 'Open original source ↗' })).toHaveAttribute(
		'href',
		'https://example.org/guideline'
	);
	await expect(page.getByText(/indexed chunk excerpt, not the full publication/)).toBeVisible();
	await expect(page.getByText('PDF page 4')).toBeVisible();
	await expect(page.locator('.technical-id')).toContainText('pdf-1');
});

test('non-PDF page=1 is not presented as a print page and unsafe URLs are withheld', async ({
	page
}) => {
	await mockEvidenceApi(page);
	await page.goto('/evidence/html-1');

	await expect(page.getByText('Original link unavailable')).toBeVisible();
	await expect(page.getByText('PDF page')).toHaveCount(0);
	await expect(page.getByText('Not provided', { exact: true })).toBeVisible();
});

test('missing chunk is not reconstructed from source or page', async ({ page }) => {
	await mockEvidenceApi(page);
	await page.goto('/evidence/missing-id');

	await expect(page.getByRole('heading', { name: 'Chunk not found' })).toBeVisible();
	await expect(page.getByText(/exact chunk ID/)).toBeVisible();
});

test('old backend without global facets does not fabricate an All total', async ({ page }) => {
	await page.route(/\/documents\?.*$/, async (route) => {
		await route.fulfill({
			status: 200,
			contentType: 'application/json',
			body: JSON.stringify({
				total: 1306,
				offset: 0,
				limit: 50,
				items: [pdfItem],
				source_type_counts: { pdf: 1306 },
				index_metadata: {}
			})
		});
	});
	await page.goto('/evidence?source_type=pdf');

	await expect(page.getByText(/Unfiltered source-type counts are unavailable/)).toBeVisible();
	await expect(page.getByRole('button', { name: /All \(/ })).toHaveCount(0);
	await expect(page.locator('.result-summary')).toContainText('of 1,306');
});

test('documents alias redirects to evidence preserving safe filters', async ({ page }) => {
	await mockEvidenceApi(page);
	await page.goto('/documents?source_type=pdf&offset=50');

	await expect(page).toHaveURL(/\/evidence\?source_type=pdf&offset=50/);
	await expect(page.getByRole('button', { name: 'pdf (1,306)' })).toHaveClass(/active/);
});
