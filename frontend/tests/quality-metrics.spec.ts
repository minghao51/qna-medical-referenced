import { test, expect, type Page } from '@playwright/test';

const API_URL = process.env.API_URL || 'http://localhost:8000';
const evaluationFixture = {
	run_dir: '20260320T101010.123456Z_baseline',
	step_metrics: {
		l1: {
			aggregate: {
				pairs_evaluated: 12,
				markdown_empty_rate: 0.02,
				retention_ratio_mean: 0.88,
				content_density_mean: 0.74,
				boilerplate_ratio_mean: 0.12,
				heading_preservation_rate_mean: 0.91,
				table_preservation_rate_mean: 0.66,
				page_classification_distribution: {
					article: 8,
					'navigation-heavy': 2,
					'index/listing': 2
				}
			},
			records: [],
			findings: []
		},
		l2: {
			aggregate: {
				pdf_file_count: 6,
				page_extraction_coverage: 0.97,
				empty_page_rate: 0.01,
				extractor_fallback_rate: 0.11,
				low_confidence_page_rate: 0.06,
				ocr_required_rate: 0.03
			},
			records: [],
			findings: []
		},
		l3: {
			aggregate: {
				document_count: 24,
				chunk_count: 180,
				duplicate_chunk_rate: 0.03,
				boundary_cut_rate: 0.04,
				observed_overlap_mean: 0.18,
				table_row_split_violations: 0,
				chunk_quality_histogram: {
					high: 120,
					medium: 50,
					low: 10
				},
				section_integrity_rate: 0.93,
				low_quality_chunk_exclusion_rate: 0.07
			},
			records: [],
			findings: []
		}
	},
	retrieval_metrics: {
		query_count: 25,
		hit_rate_at_k: 0.84,
		precision_at_k: 0.63,
		recall_at_k: 0.79,
		mrr: 0.71,
		ndcg_at_k: 0.76,
		source_hit_rate: 0.8,
		exact_chunk_hit_rate: 0.56,
		evidence_hit_rate: 0.68,
		latency_p50_ms: 120,
		latency_p95_ms: 240,
		hit_rate_at_k_high_conf: 0.89,
		mrr_high_conf: 0.78,
		dedup_hit_rate_at_k: 0.81,
		dedup_precision_at_k: 0.66,
		dedup_mrr: 0.69,
		unique_source_hit_rate_at_k: 0.74,
		unique_source_precision_at_k: 0.6,
		duplicate_source_ratio_mean: 0.12,
		duplicate_doc_ratio_mean: 0.08,
		exact_chunk_hit_rate_high_conf: 0.61,
		evidence_hit_rate_high_conf: 0.73,
		topic_false_positive_rate: 0.09
	}
};

async function mockEvaluationApi(page: Page) {
	await page.route(`${API_URL}/evaluation/latest`, async (route) => {
		await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(evaluationFixture) });
	});
	await page.route(`${API_URL}/evaluation/history?*`, async (route) => {
		await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ runs: [] }) });
	});
	await page.route(`${API_URL}/evaluation/ablation`, async (route) => {
		await route.fulfill({
			status: 200,
			contentType: 'application/json',
			body: JSON.stringify({ ablation_runs: [], message: 'No ablation runs yet' })
		});
	});
}

async function proxyBrowserApiRequests(page: Page) {
	if (API_URL === 'http://localhost:8000') return;

	await page.route('http://localhost:8000/**', async (route) => {
		const proxiedUrl = route.request().url().replace('http://localhost:8000', API_URL);
		const response = await route.fetch({ url: proxiedUrl });
		await route.fulfill({ response });
	});
}

test.describe('Quality Metrics Dashboard', () => {
	test.setTimeout(60000);

	test.beforeEach(async ({ page }) => {
		await proxyBrowserApiRequests(page);
		await mockEvaluationApi(page);
		await page.goto('/eval');
		await page.waitForSelector('.eval-container', { timeout: 15000 });
		await page.waitForSelector('.step-card, .retrieval-section', { timeout: 15000 });
	});

	test('displays chunk quality distribution in L3 card', async ({ page }) => {
		// Find L3 card
		const l3Card = page.locator('.step-card').filter({ hasText: 'L3' });
		await expect(l3Card).toBeVisible();

		// Check for quality distribution label (using filter to find specific row)
		const qualityDistRow = l3Card.locator('.metric-row').filter({ hasText: 'Quality Distribution' });
		await expect(qualityDistRow).toBeVisible();

		// Check for quality distribution chart component
		const qualityChart = l3Card.locator('.quality-distribution');
		await expect(qualityChart).toBeVisible();

		// Verify chart has high and medium segments (low may be hidden if 0%)
		await expect(qualityChart.locator('.bar-segment.high')).toBeVisible();
		await expect(qualityChart.locator('.bar-segment.medium')).toBeVisible();

		// Verify low segment exists in DOM (even if hidden with 0% width)
		const lowSegment = qualityChart.locator('.bar-segment.low');
		await expect(lowSegment).toHaveCount(1);

		// Verify labels show counts
		const labels = qualityChart.locator('.label');
		await expect(labels).toHaveCount(3);
	});

	test('displays section integrity and low quality filtered metrics in L3', async ({ page }) => {
		const l3Card = page.locator('.step-card').filter({ hasText: 'L3' });

		// Check for Section Integrity metric
		await expect(l3Card.getByText('Section Integrity')).toBeVisible();

		// Check for Low Quality Filtered metric
		await expect(l3Card.getByText('Low Quality Filtered')).toBeVisible();
	});

	test('displays HTML/Markdown quality metrics in L1 card', async ({ page }) => {
		const l1Card = page.locator('.step-card').filter({ hasText: 'L1' });
		await expect(l1Card).toBeVisible();

		// Check for Content Density
		await expect(l1Card.getByText('Content Density')).toBeVisible();

		// Check for Boilerplate Ratio
		await expect(l1Card.getByText('Boilerplate Ratio')).toBeVisible();

		// Check for Heading Preservation
		await expect(l1Card.getByText('Heading Preservation')).toBeVisible();

		// Check for Table Preservation
		await expect(l1Card.getByText('Table Preservation')).toBeVisible();

		// Check for Page Types
		const pageTypes = l1Card.locator('.page-types');
		await expect(pageTypes).toBeVisible();
	});

	test('displays PDF extraction quality metrics in L2 card', async ({ page }) => {
		const l2Card = page.locator('.step-card').filter({ hasText: 'L2' });
		await expect(l2Card).toBeVisible();

		// Check for Extractor Fallback Rate
		await expect(l2Card.getByText('Extractor Fallback Rate')).toBeVisible();

		// Check for Low Confidence Rate
		await expect(l2Card.getByText('Low Confidence Rate')).toBeVisible();

		// Check for OCR Required Rate
		await expect(l2Card.getByText('OCR Required Rate')).toBeVisible();
	});

	test('displays deduplication & diversity subsection in L6', async ({ page }) => {
		const retrievalSection = page.locator('.retrieval-section');
		await expect(retrievalSection).toBeVisible();

		// Check for Deduplication & Diversity subsection
		const dedupSection = retrievalSection.locator('.retrieval-subsection').filter({ hasText: 'Deduplication & Diversity' });
		await expect(dedupSection).toBeVisible();

		// Verify deduplication metrics are displayed
		await expect(dedupSection).toContainText('Dedup Hit Rate');
		await expect(dedupSection).toContainText('Dedup MRR');
		await expect(dedupSection).toContainText('Unique Source Hit');
		await expect(dedupSection).toContainText('Duplicate Source Ratio');
	});

	test('displays high-confidence subset subsection in L6', async ({ page }) => {
		const retrievalSection = page.locator('.retrieval-section');
		await expect(retrievalSection).toBeVisible();

		// Check for High-Confidence Subset subsection
		const highConfSection = retrievalSection.locator('.retrieval-subsection').filter({ hasText: 'High-Confidence Subset' });
		await expect(highConfSection).toBeVisible();

		// Verify high-confidence metrics are displayed
		await expect(highConfSection).toContainText('Hit Rate (High Conf)');
		await expect(highConfSection).toContainText('MRR (High Conf)');
		await expect(highConfSection).toContainText('Exact Chunk (High Conf)');
		await expect(highConfSection).toContainText('Topic False Positive');
	});

	test('displays warning styles for metrics exceeding thresholds', async ({ page }) => {
		// Check L1 for boilerplate warning style (if boilerplate_ratio_mean > 0.1)
		const l1Card = page.locator('.step-card').filter({ hasText: 'L1' });
		const boilerplateRow = l1Card.locator('.metric-row').filter({ hasText: 'Boilerplate Ratio' });
		const boilerplateValue = boilerplateRow.locator('span').last();

		// Get the text value and check if it's styled with warning class
		const valueText = await boilerplateValue.textContent();
		const hasWarningClass = await boilerplateValue.evaluate(el => el.classList.contains('warning'));

		// Verify warning style is applied when threshold is exceeded
		const numericValue = parseFloat(valueText || '0');
		if (numericValue > 10) { // 10% threshold
			expect(hasWarningClass).toBeTruthy();
		}
	});

	test('all quality metric cards are responsive and layout correctly', async ({ page }) => {
		// Check main sections are visible (history section may not exist if no data)
		const stepsSection = page.locator('.steps-section');
		await expect(stepsSection).toBeVisible();
		await expect(page.locator('.retrieval-section')).toBeVisible();

		// Verify cards are using grid layout
		const stepsGrid = page.locator('.steps-grid');
		await expect(stepsGrid).toBeVisible();

		// Check that at least one metrics grid exists
		const metricsGrid = page.locator('.metrics-grid').first();
		await expect(metricsGrid).toBeVisible();
	});
});
