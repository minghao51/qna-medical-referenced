import { test, expect, type Page } from '@playwright/test';

const revisionA = 'a'.repeat(64);
const revisionB = 'b'.repeat(64);

function entry(overrides: Record<string, unknown> = {}) {
	return {
		catalog_id: 'golden-all',
		label: 'Golden queries — all',
		kind: 'query_fixture',
		availability: 'available',
		availability_reason: null,
		origin_ref: 'tests/fixtures/golden_queries_all.json',
		revision_sha256: revisionA,
		record_unit: 'question',
		record_count: 57,
		turn_count: null,
		split_counts: { regression: 17, test: 23, dev: 17 },
		label_confidence_counts: { high: 43, medium: 14 },
		raw_review_status_counts: null,
		review_status_missing_count: 57,
		review_authority: 'not_assessed',
		case_projection: 'available',
		inventory_ref: null,
		...overrides
	};
}

function catalogEntries() {
	return [
		entry(),
		entry({
			catalog_id: 'golden-expanded',
			label: 'Golden queries — expanded',
			origin_ref: 'tests/fixtures/golden_queries_expanded.json',
			record_count: 54,
			split_counts: { regression: 17, test: 23, dev: 14 },
			label_confidence_counts: { high: 40, medium: 14 }
		}),
		entry({
			catalog_id: 'golden-comprehensive',
			label: 'Golden queries — comprehensive',
			record_count: 35
		}),
		entry({ catalog_id: 'golden-diverse', label: 'Golden queries — diverse', record_count: 20 }),
		entry({ catalog_id: 'golden-original', label: 'Golden queries — original', record_count: 21 }),
		entry({
			catalog_id: 'golden-conversations',
			label: 'Golden conversations',
			kind: 'conversation_fixture',
			record_unit: 'conversation',
			record_count: 15,
			turn_count: 30,
			split_counts: null,
			label_confidence_counts: null,
			review_status_missing_count: null,
			origin_ref: 'tests/fixtures/golden_conversations.json'
		}),
		entry({
			catalog_id: 'd11-review',
			label: 'D11 frozen review set',
			kind: 'review_dataset',
			record_unit: 'case',
			record_count: 8,
			split_counts: { answerable: 7, unanswerable: 1 },
			label_confidence_counts: null,
			raw_review_status_counts: { human_reviewed: 8 },
			review_status_missing_count: 0,
			review_authority: 'manifest_declared_not_authenticated',
			case_projection: 'summary_only',
			origin_ref: 'data/evals/review/dataset.json'
		}),
		entry({
			catalog_id: 'lab-reference',
			label: 'LabQAR reference ranges',
			kind: 'reference_csv',
			record_unit: 'row',
			record_count: 471,
			split_counts: null,
			label_confidence_counts: null,
			review_status_missing_count: null,
			case_projection: 'unavailable',
			origin_ref: 'data/raw/LabQAR/reference_ranges.csv'
		}),
		entry({
			catalog_id: 'd11-index',
			label: 'D11 retrieval index',
			kind: 'retrieval_index',
			availability: 'inventory_reference',
			record_unit: 'chunk',
			record_count: null,
			split_counts: null,
			label_confidence_counts: null,
			review_status_missing_count: null,
			case_projection: 'unavailable',
			origin_ref: 'data/chroma-d11',
			inventory_ref: '/documents'
		})
	];
}

const overlap = {
	left_catalog_id: 'golden-all',
	left_revision: revisionA,
	right_catalog_id: 'golden-expanded',
	right_revision: 'c'.repeat(64),
	method: 'exact_stored_query_text',
	left_unique_query_count: 57,
	right_unique_query_count: 54,
	intersection_unique_query_count: 54,
	normalization: 'none',
	near_duplicate_status: 'not_assessed'
};

const firstCase = {
	locator: { revision_sha256: revisionA, source_ordinal: 0 },
	source_case_id: null,
	question: 'What is the LDL-C target for secondary prevention?',
	expected_keywords: ['LDL-C', 'secondary', 'prevention', '1.8', 'mmol'],
	expected_source_labels: ['lipid_management_guideline'],
	split: 'regression',
	difficulty: 'medium',
	query_category: 'anchor',
	source_family: 'lipid',
	topic: 'targets',
	label_confidence: 'high',
	raw_review_status: null,
	normalized_review_status: null,
	stored_turns: null
};

function casePage(revision: string) {
	const items = [
		firstCase,
		{
			...firstCase,
			locator: { revision_sha256: revision, source_ordinal: 1 },
			question: 'What if the patient also has diabetes?',
			expected_keywords: ['diabetes', 'risk'],
			expected_source_labels: ['lipid_management_guideline'],
			difficulty: 'hard'
		},
		...Array.from({ length: 55 }, (_, index) => ({
			...firstCase,
			locator: { revision_sha256: revision, source_ordinal: index + 2 },
			question: `Stored fixture question ${index + 3}`,
			expected_keywords: ['term'],
			expected_source_labels: ['source']
		}))
	];
	return {
		catalog_id: 'golden-all',
		revision_sha256: revision,
		total: items.length,
		offset: 0,
		limit: 100,
		items
	};
}

async function mockCatalogApi(
	page: Page,
	options: {
		detailStatus?: number;
		revisionRefresh?: boolean;
		summaryOnly?: boolean;
	} = {}
) {
	const { detailStatus = 404, revisionRefresh = false } = options;
	let detailCalls = 0;
	let caseCalls = 0;

	await page.route(/\/research-data\/datasets$/, async (route) => {
		await route.fulfill({
			status: 200,
			contentType: 'application/json',
			body: JSON.stringify({ datasets: catalogEntries(), overlap: [overlap] })
		});
	});

	await page.route(/\/research-data\/datasets\/golden-all$/, async (route) => {
		detailCalls += 1;
		const revision = revisionRefresh && detailCalls > 1 ? revisionB : revisionA;
		await route.fulfill({
			status: 200,
			contentType: 'application/json',
			body: JSON.stringify(entry({ revision_sha256: revision }))
		});
	});

	await page.route(/\/research-data\/datasets\/d11-review$/, async (route) => {
		await route.fulfill({
			status: 200,
			contentType: 'application/json',
			body: JSON.stringify(
				entry({
					catalog_id: 'd11-review',
					label: 'D11 frozen review set',
					kind: 'review_dataset',
					record_unit: 'case',
					record_count: 8,
					split_counts: { answerable: 7, unanswerable: 1 },
					label_confidence_counts: null,
					raw_review_status_counts: { human_reviewed: 8 },
					review_status_missing_count: 0,
					review_authority: 'manifest_declared_not_authenticated',
					case_projection: 'summary_only'
				})
			)
		});
	});

	await page.route(/\/research-data\/datasets\/unknown-id$/, async (route) => {
		await route.fulfill({
			status: detailStatus,
			contentType: 'application/json',
			body: JSON.stringify({ detail: 'catalog_not_found' })
		});
	});

	await page.route(/\/research-data\/datasets\/golden-all\/cases\?.*$/, async (route) => {
		caseCalls += 1;
		const revision = new URL(route.request().url()).searchParams.get('revision') ?? revisionA;
		if (revisionRefresh && revision === revisionA) {
			await route.fulfill({
				status: 409,
				contentType: 'application/json',
				body: JSON.stringify({ detail: 'catalog_revision_changed' })
			});
			return;
		}
		await route.fulfill({
			status: 200,
			contentType: 'application/json',
			body: JSON.stringify(casePage(revision))
		});
	});

	await page.route(/\/research-data\/datasets\/d11-review\/cases\?.*$/, async (route) => {
		await route.fulfill({ status: 409, contentType: 'application/json', body: '{}' });
	});

	return {
		detailCalls: () => detailCalls,
		caseCalls: () => caseCalls
	};
}

test('catalog lists distinct artifacts, exact overlap and review authority caveats', async ({
	page
}) => {
	await mockCatalogApi(page);
	await page.goto('/research/datasets');

	await expect(page.getByRole('heading', { name: 'What are we actually testing?' })).toBeVisible();
	await expect(page.locator('.catalog-card')).toHaveCount(9);
	await expect(page.locator('.catalog-card').filter({ hasText: 'Golden queries — all' }))
		.toContainText('57 questions');
	await expect(page.locator('.catalog-card').filter({ hasText: 'Golden conversations' }))
		.toContainText('15 conversations · 30 turns');
	await expect(page.locator('.catalog-card').filter({ hasText: 'D11 frozen review set' }))
		.toContainText('8 cases');
	await expect(page.locator('.overlap-card')).toContainText('54 queries overlap exactly');
	await expect(page.locator('.overlap-card')).toContainText('not independent samples');
	await expect(page.locator('.review-card')).toContainText('7 answerable');
	await expect(page.locator('.review-card')).toContainText('1 unanswerable');
	await expect(page.locator('.review-card')).toContainText('not reviewer authentication');
	await expect(page.locator('.catalog-context')).toContainText('Units do not pool');
	await expect(page.locator('.catalog-card').filter({ hasText: 'LabQAR reference ranges' }))
		.toContainText('471 rows');
});

test('dataset detail shows current-file splits, overlap and the real fixture case', async ({
	page
}) => {
	await mockCatalogApi(page);
	await page.goto('/research/datasets/golden-all');

	await expect(page.getByRole('heading', { name: 'Golden queries — all' })).toBeVisible();
	await expect(page.locator('.summary')).toContainText('57');
	await expect(page.locator('.summary')).toContainText('questions');
	await expect(page.locator('.split-list')).toContainText('regression');
	await expect(page.locator('.split-list')).toContainText('17');
	await expect(page.locator('.split-list')).toContainText('test');
	await expect(page.locator('.split-list')).toContainText('23');
	await expect(page.locator('[aria-labelledby="confidence-title"]')).toContainText('43');
	await expect(page.locator('[aria-labelledby="review-title"]')).toContainText(
		'Review status is absent in the raw rows.'
	);
	await expect(page.locator('.overlap')).toContainText('54 queries overlap exactly');

	await expect(page.locator('.expected-panel')).toContainText(
		'What is the LDL-C target for secondary prevention?'
	);
	await expect(page.locator('.expected-panel')).toContainText('lipid_management_guideline');
	await expect(page.locator('.expected-panel')).toContainText('LDL-C · secondary · prevention · 1.8 · mmol');
	await expect(page.locator('.expected-panel')).toContainText('Raw review status: absent in raw row');
	await expect(page.locator('.observed-panel')).toContainText('Per-case results are not available.');
	await expect(page.locator('.binding-note')).toContainText(
		'historical_binding = not_established'
	);
	await expect(page.locator('.binding-note')).toContainText('case_records_unavailable');
	await expect(page.locator('.observed-panel')).toContainText('Not recorded here ≠ test failure');
	await expect(page.getByText('1 of 57')).toBeVisible();

	await page.getByRole('button', { name: 'Next' }).click();
	await expect(page.locator('.expected-panel')).toContainText(
		'What if the patient also has diabetes?'
	);
	await expect(page).toHaveURL(/case=1/);
});

test('case ordinal URL selects the stored case', async ({ page }) => {
	await mockCatalogApi(page);
	await page.goto('/research/datasets/golden-all?case=1');
	await expect(page.locator('.expected-panel')).toContainText(
		'What if the patient also has diabetes?'
	);
});

test('summary-only review entries never request or fake cases', async ({ page }) => {
	const calls = await mockCatalogApi(page);
	await page.goto('/research/datasets/d11-review');

	await expect(page.getByRole('heading', { name: 'D11 frozen review set' })).toBeVisible();
	await expect(page.getByText(/This artifact is summary-only/)).toBeVisible();
	await expect(page.locator('.case-panel')).toHaveCount(0);
	expect(calls.caseCalls()).toBe(0);
});

test('revision change invalidates stale case selection and refreshes explicitly', async ({ page }) => {
	await mockCatalogApi(page, { revisionRefresh: true });
	await page.goto('/research/datasets/golden-all');

	await expect(page.getByRole('heading', { name: 'The source revision changed' })).toBeVisible();
	await expect(page.locator('.state-block')).toContainText('selection has been invalidated');
	await page.getByRole('button', { name: 'Refresh dataset' }).click();
	await expect(page.locator('.expected-panel')).toContainText(
		'What is the LDL-C target for secondary prevention?'
	);
});

test('unknown dataset ID is not treated as a path', async ({ page }) => {
	await mockCatalogApi(page);
	await page.goto('/research/datasets/unknown-id');

	await expect(page.getByRole('heading', { name: 'Dataset not found' })).toBeVisible();
	await expect(page.getByText(/fixed allowlist/)).toBeVisible();
});
