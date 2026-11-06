<script lang="ts">
	import { onMount } from 'svelte';
	import AppShell from '$lib/components/AppShell.svelte';
	import EmptyState from '$lib/components/EmptyState.svelte';
	import FeatureEvidence from '$lib/components/FeatureEvidence.svelte';
	import LoadingSkeleton from '$lib/components/LoadingSkeleton.svelte';
	import ResearchNav from '$lib/components/ResearchNav.svelte';
	import { getExperiments, getExperimentResults } from '$lib/utils/api';
	import { calculateMetricDelta, formatDecimal, metricNumber } from '$lib/utils/eval';
	import { normalizeLegacyArchive, primaryMetricKey } from '$lib/utils/research';
	import type {
		ExperimentListResponse,
		ExperimentReport,
		ExperimentReportSummary,
		LegacyArchiveVariant
	} from '$lib/types';

	type LoadState = 'loading' | 'available' | 'missing' | 'unsupported' | 'unauthorized' | 'error';

	type DeclaredVariant = {
		name?: string;
		chunking_strategy?: string;
		query_understanding?: boolean;
		ingestion_overrides?: unknown;
		retrieval_overrides?: unknown;
	};

	type VariantData = {
		name: string;
		raw: Record<string, unknown>;
		declared: DeclaredVariant | null;
		normalized: LegacyArchiveVariant | null;
		display: {
			name: string;
			chunking: string;
			queryUnderstanding: string;
			ndcg: string;
			deltaAbsolute: string;
			deltaRelative: string;
			measurement: string;
			selected: boolean;
		};
	};

	const preferredReportId = 'medical_semantic_chunking_exp';
	const reportIdPattern = /^[A-Za-z0-9_-][A-Za-z0-9._-]*$/;

	let loadState = $state<LoadState>('loading');
	let errorMessage = $state('');
	let list = $state<ExperimentListResponse | null>(null);
	let selectedReportId = $state('');
	let report = $state<ExperimentReport | null>(null);
	let variantData = $state<VariantData[]>([]);
	let selectedName = $state('');
	let requestSequence = 0;

	const availableReports = $derived(
		(list?.reports ?? []).filter(
			(item): item is ExperimentReportSummary & { report_id: string } =>
				item.availability === 'available' && typeof item.report_id === 'string'
		)
	);
	const primaryKey = $derived(report ? primaryMetricKey(report.primary_metric) : null);
	const metricLabel = $derived.by(() => {
		const raw = report?.primary_metric ?? '';
		const match = raw.match(/^ndcg@(.+)$/i);
		return match ? `nDCG@${match[1]}` : raw || 'Primary metric';
	});
	const rows = $derived(
		variantData.map((item) => ({
			...item.display,
			selected: item.name === selectedName
		}))
	);
	const selectedVariant = $derived(
		variantData.find((item) => item.name === selectedName) ?? null
	);
	const allDegraded = $derived(
		variantData.length > 0 &&
			variantData.every(
				(item) =>
					item.normalized?.measurement_status === 'degraded' ||
					item.normalized?.coverage_totals.coverage_state === 'partial'
			)
	);

	const capabilities = [
		{
			title: 'Query understanding',
			implementation: 'Rule-based classification and retrieval-parameter routing',
			evidence: '57-query archive: nDCG@5 +0.0413 (+6.3%) for the declared variants',
			scope: 'Declared on in the archived variants. Effective runtime configuration is unverified.',
			refs: 'src/rag/query_understanding/classifier.py · src/rag/query_understanding/router.py'
		},
		{
			title: 'Medical semantic chunking',
			implementation: 'Optional medical-aware chunking strategy',
			evidence: '57-query archive: identical ranking metrics to the chonkie baseline',
			scope: 'Declared strategy only; no measurable ranking difference on this report.',
			refs: 'src/ingestion/steps/chunking/medical_semantic.py · strategies.py'
		},
		{
			title: 'Cross-encoder reranking',
			implementation: 'Opt-in reranking stage with local model assets',
			evidence: 'Separate 54-query retrieval study: +0.0392 nDCG, +248.5 ms p50',
			scope: 'Different dataset and retrieval-only recovery; never pooled with the 57-query report.',
			refs: 'src/rag/reranker.py · optional pyproject reranking group'
		},
		{
			title: 'HyDE / HyPE / enrichment',
			implementation: 'Optional query-time and index-time features',
			evidence: '54-query note: no retrieval-quality lift; only small latency differences',
			scope: 'Not justified by the reported retrieval evidence; effective settings unverified.',
			refs: 'src/rag/hyde.py · src/ingestion/steps/enrich_chunks.py'
		}
	];

	const rerankingStudy = [
		{ variant: 'No reranking', ndcg: '0.6813', p50: '236.5 ms' },
		{ variant: 'Cross-encoder only', ndcg: '0.7205', p50: '485.0 ms' },
		{ variant: 'MMR only', ndcg: '0.6647', p50: '538.0 ms' },
		{ variant: 'Both reranking', ndcg: '0.6647', p50: '774.0 ms' }
	];

	function isUnauthorized(message: string): boolean {
		return /401|x-api-key|missing .*key/i.test(message);
	}

	function requestedReportFromUrl(): string | null {
		if (typeof window === 'undefined') return null;
		const requested = new URLSearchParams(window.location.search).get('report');
		return requested && reportIdPattern.test(requested) && requested !== '.' && requested !== '..'
			? requested
			: null;
	}

	function syncUrl(reportId: string) {
		if (typeof window === 'undefined') return;
		const params = new URLSearchParams(window.location.search);
		params.set('report', reportId);
		window.history.replaceState({}, '', `${window.location.pathname}?${params.toString()}`);
	}

	function buildRows(payload: ExperimentReport) {
		const projection = normalizeLegacyArchive(payload);
		const rawRows = [payload.baseline, ...payload.variants];
		const key = primaryMetricKey(payload.primary_metric);
		const config = (payload.config ?? {}) as {
			baseline?: DeclaredVariant;
			variants?: DeclaredVariant[];
		};
		const declaredForName = (name: string): DeclaredVariant | null =>
			name === payload.baseline.name
				? (config.baseline ?? null)
				: (config.variants?.find((item) => item.name === name) ?? null);
		const baselineMetrics = (payload.baseline.metrics ?? {}) as Record<string, unknown>;
		const mapped: VariantData[] = rawRows.map((row) => {
			const raw = (row.metrics ?? {}) as Record<string, unknown>;
			const declared = declaredForName(row.name);
			const normalized =
				projection.variants.find((variant) => variant.name === row.name) ?? null;
			const delta = key ? calculateMetricDelta(key, baselineMetrics[key], raw[key]) : null;
			const value = key ? metricNumber(raw[key], key) : null;
			const coverage = normalized?.coverage_totals.coverage_state ?? 'not recorded';
			const status = normalized?.measurement_status ?? 'status not recorded';
			return {
				name: row.name,
				raw,
				declared,
				normalized,
				display: {
					name: row.name,
					chunking: declared?.chunking_strategy ?? 'Not declared',
					queryUnderstanding:
						declared?.query_understanding === true
							? 'On'
							: declared?.query_understanding === false
								? 'Off'
								: 'Not declared',
					ndcg: formatDecimal(value, 4),
					deltaAbsolute: delta?.absolute_label ?? 'N/A',
					deltaRelative: delta?.relative_label ?? 'N/A',
					measurement: `${status} · ${coverage}`,
					selected: false
				}
			};
		});
		variantData = mapped;
		selectedName =
			mapped.find((item) => item.name === 'query_understanding')?.name ??
			mapped[1]?.name ??
			mapped[0]?.name ??
			'';
	}

	async function loadReport(reportId: string) {
		const token = ++requestSequence;
		loadState = 'loading';
		errorMessage = '';
		report = null;
		variantData = [];
		try {
			const payload = await getExperimentResults<ExperimentReport>(reportId);
			if (token !== requestSequence) return;
			const projection = normalizeLegacyArchive(payload);
			if (
				projection.schema_kind !== 'legacy_feature_addition' ||
				projection.variants.length === 0
			) {
				loadState = 'unsupported';
				return;
			}
			report = payload;
			buildRows(payload);
			loadState = 'available';
		} catch (error) {
			if (token !== requestSequence) return;
			const message =
				error instanceof Error ? error.message : 'The archived feature report could not be read.';
			errorMessage = message;
			loadState = isUnauthorized(message) ? 'unauthorized' : 'error';
		}
	}

	async function loadPage() {
		loadState = 'loading';
		errorMessage = '';
		const requested = requestedReportFromUrl();
		try {
			list = await getExperiments<ExperimentListResponse>();
			if (availableReports.length === 0) {
				loadState = 'missing';
				return;
			}
			if (requested && !availableReports.some((item) => item.report_id === requested)) {
				selectedReportId = requested;
				loadState = 'missing';
				return;
			}
			const chosen =
				requested ??
				availableReports.find((item) => item.report_id === preferredReportId)?.report_id ??
				availableReports[0].report_id;
			selectedReportId = chosen;
			syncUrl(chosen);
			await loadReport(chosen);
		} catch (error) {
			const message =
				error instanceof Error ? error.message : 'The archived report list is unavailable.';
			errorMessage = message;
			loadState = isUnauthorized(message) ? 'unauthorized' : 'error';
		}
	}

	function selectReport(reportId: string) {
		if (!availableReports.some((item) => item.report_id === reportId)) return;
		selectedReportId = reportId;
		syncUrl(reportId);
		void loadReport(reportId);
	}

	onMount(() => {
		void loadPage();
	});
</script>

<svelte:head>
	<title>Features · Fieldnote</title>
</svelte:head>

<AppShell current="/research/features">
	<div class="features-page">
		<header class="page-header">
			<p class="eyebrow">Feature evidence / local archive</p>
			<h1>A feature flag is not a finding.</h1>
			<p class="lede">
				Separate declared configuration, observed outcomes and the evidence needed to make a
				decision. No default-profile change or live feature switch is authorized here.
			</p>
		</header>

		<ResearchNav current="/research/features" />

		{#if availableReports.length > 0}
			<div class="selection-bar">
				<label for="feature-report-select">Archived report</label>
				{#if availableReports.length > 1}
					<select
						id="feature-report-select"
						value={selectedReportId}
						onchange={(event) => selectReport(event.currentTarget.value)}
					>
						{#each availableReports as item}
							<option value={item.report_id}>{item.report_id}</option>
						{/each}
					</select>
				{:else}
					<span class="selected-report">{selectedReportId}</span>
				{/if}
				<span class="selection-note">Read-only archive · no run or profile change</span>
			</div>
		{/if}

		{#if loadState === 'loading'}
			<div class="loading-panel" aria-busy="true">
				<LoadingSkeleton count={3} type="card" />
			</div>
		{:else if loadState === 'unauthorized'}
			<EmptyState
				title="Research access required"
				body="This private-lab feature view needs the authenticated gateway. It does not fall back to a latest report."
			/>
			<a class="text-link" href="/ask">Back to Ask</a>
		{:else if loadState === 'missing'}
			<EmptyState
				title="Requested archived report unavailable"
				body={selectedReportId
					? `${selectedReportId} is not an available report in this archive. No latest report was substituted.`
					: 'No supported archived feature report is available in this installation.'}
			/>
			<a class="text-link" href="/experiments">Open the config explorer</a>
		{:else if loadState === 'unsupported'}
			<EmptyState
				title="Unsupported archive schema"
				body="This report does not match the reviewed legacy shape. Its raw data remains available through the config explorer."
			/>
			<a class="text-link" href="/experiments">Inspect raw experiment data</a>
		{:else if loadState === 'error'}
			<EmptyState
				title="Archived feature report unavailable"
				body={errorMessage || 'The report could not be read safely.'}
			/>
		{:else if loadState === 'available' && report}
			<section class="report-banner" aria-labelledby="feature-report-title">
				<div>
					<p class="eyebrow">57-query report · archived aggregate</p>
					<h2 id="feature-report-title">{#each report.experiment_name.split('_') as part, index}{#if index > 0}_{/if}{part}<wbr />{/each}</h2>
					<p class="report-meta">
						{report.timestamp} · primary metric {metricLabel} · target +
						{(report.target_improvement * 100).toFixed(0)}%
					</p>
					<p class="report-caveat">
						Declared settings and observed archived metrics are distinct from effective runtime
						configuration. No index binding or promotion is asserted.
					</p>
				</div>
				<div class="posture-note">
					<span class="badge">Read-only evidence</span>
					<span>No live settings toggles</span>
				</div>
			</section>

			<section class="matrix-panel" aria-labelledby="matrix-title">
				<div class="panel-heading">
					<h2 id="matrix-title">Declared variants and observed outcome</h2>
					<p>Select a row to inspect it; selection does not certify a winner.</p>
				</div>
				<FeatureEvidence {rows} {metricLabel} onSelect={(name) => (selectedName = name)} />
			</section>

			<div class="result-grid">
				<section class="result-card" aria-labelledby="result-title">
					<p class="eyebrow">Descriptive result ≠ eligible winner</p>
					<h2 id="result-title">Reported absolute and relative change</h2>
					<p class="delta-headline">
						<strong>{selectedVariant?.display.deltaAbsolute ?? 'N/A'}</strong> absolute
						<span>·</span>
						<strong>{selectedVariant?.display.deltaRelative ?? 'N/A'}</strong> relative
					</p>
					<p>
						These are nDCG@5 score points and a relative percentage against the archived
						baseline. They are not a confidence interval, a per-case win/loss result or a
						promotion decision.
					</p>
					<p>
						{allDegraded
							? 'All four variants have degraded answer measurements. Their retrieval ranking does not establish complete answer quality.'
							: 'Measurement status varies by variant; read each state before comparing.'}
					</p>
					<p class="historical-winner">
						Reported historical winner: <strong>{report.winner?.name ?? 'not recorded'}</strong>.
						This UI does not certify current eligibility.
					</p>
				</section>

				<section class="inspect-card" aria-labelledby="inspect-title">
					<p class="eyebrow">Inspecting</p>
					<h2 id="inspect-title">{selectedVariant?.name ?? 'No variant selected'}</h2>
					{#if selectedVariant}
						<dl>
							<div>
								<dt>Declared chunking</dt>
								<dd>{selectedVariant.declared?.chunking_strategy ?? 'Not declared'}</dd>
							</div>
							<div>
								<dt>Declared query understanding</dt>
								<dd>
									{selectedVariant.declared?.query_understanding === true
										? 'On'
										: selectedVariant.declared?.query_understanding === false
											? 'Off'
											: 'Not declared'}
								</dd>
							</div>
							<div>
								<dt>Observed {metricLabel}</dt>
								<dd>{selectedVariant.display.ndcg}</dd>
							</div>
							<div>
								<dt>Answer measurement</dt>
								<dd>
									{selectedVariant.normalized?.measurement_status ?? 'Not recorded'} ·
									{selectedVariant.normalized?.coverage_totals.coverage_state ??
										'not recorded'}
									({selectedVariant.normalized?.coverage_totals.measured_slots ?? 'N/A'} /
									{selectedVariant.normalized?.coverage_totals.expected_slots ?? 'N/A'} slots)
								</dd>
							</div>
							<div>
								<dt>Effective runtime settings</dt>
								<dd>Unverified — the archive declares configuration, not the running profile.</dd>
							</div>
							<div>
								<dt>Index binding</dt>
								<dd>Unverified — no historical index identity is asserted.</dd>
							</div>
						</dl>
					{/if}
				</section>
			</div>

			<section class="capability-panel" aria-labelledby="capabilities-title">
				<div class="panel-heading">
					<h2 id="capabilities-title">Capability map</h2>
					<p>Implementation and archived evidence are separate dimensions.</p>
				</div>
				<div class="capability-grid">
					{#each capabilities as capability}
						<article class="capability-card">
							<h3>{capability.title}</h3>
							<p>{capability.implementation}</p>
							<p class="capability-evidence">{capability.evidence}</p>
							<p class="capability-scope">{capability.scope}</p>
							<p class="capability-refs">{capability.refs}</p>
						</article>
					{/each}
				</div>
			</section>

			<section class="study-panel" aria-labelledby="study-title">
				<div class="panel-heading">
					<h2 id="study-title">Separate 54-query reranking study</h2>
					<p>Reported 15 Apr 2026 · retrieval-only recovery · not pooled with the 57-query report</p>
				</div>
				<div class="study-table-wrap">
					<table class="study-table">
						<thead>
							<tr>
								<th scope="col">Variant</th>
								<th scope="col">nDCG@K</th>
								<th scope="col">p50 latency</th>
							</tr>
						</thead>
						<tbody>
							{#each rerankingStudy as row}
								<tr>
									<th scope="row">{row.variant}</th>
									<td>{row.ndcg}</td>
									<td>{row.p50}</td>
								</tr>
							{/each}
						</tbody>
					</table>
				</div>
				<p class="study-note">
					Cross-encoder versus no reranking: +0.0392 nDCG@K and +248.5 ms median retrieval
					time. This is a reported retrieval trade-off, not a causal estimate or a medical-answer
					comparison. Source: docs/feature_ablation_findings.md. No confidence intervals are
					supplied.
				</p>
			</section>

			<section class="next-actions" aria-labelledby="next-title">
				<h2 id="next-title">What can you inspect next?</h2>
				<div class="action-links">
					<a href="/experiments">
						<strong>Open the config explorer</strong>
						<span>Declared experiment YAML and raw archived results →</span>
					</a>
					<a href="/research/evaluations">
						<strong>Read evaluation coverage</strong>
						<span>Artifact identity, denominators and measurement status →</span>
					</a>
					<a href="/eval/ablation">
						<strong>Inspect the separate ablation study</strong>
						<span>Archived variant evidence, not current eligibility →</span>
					</a>
				</div>
				<p class="source-note">
					Dataset identity and case expectations require the catalog view, which is not
					available in this build. No report/config association is inferred when absent.
				</p>
			</section>
		{/if}
	</div>
</AppShell>

<style>
	.features-page {
		display: flex;
		flex-direction: column;
		gap: 1.5rem;
	}

	.eyebrow {
		margin: 0 0 0.5rem;
		color: var(--muted-color);
		font-size: 0.7rem;
		font-weight: 700;
		letter-spacing: 0.14em;
		text-transform: uppercase;
	}

	h1 {
		max-width: 22ch;
		margin: 0;
		font-size: clamp(2rem, 3.8vw, 3rem);
	}

	.lede {
		max-width: 68ch;
		margin: 0.9rem 0 0;
		color: var(--secondary);
	}

	.selection-bar {
		display: flex;
		flex-wrap: wrap;
		align-items: center;
		gap: 0.6rem;
		padding: 0.75rem 1rem;
		border: 1px solid var(--border-color);
		border-radius: 8px;
		background: #fffdf8;
		font-size: 0.9rem;
	}

	.selection-bar label {
		font-weight: 700;
	}

	.selection-bar select {
		min-height: 40px;
		padding: 0.35rem 0.5rem;
		border: 1px solid var(--border-color);
		border-radius: 6px;
		background: var(--paper);
		color: var(--ink);
	}

	.selected-report {
		font-family: var(--font-heading);
	}

	.selection-note {
		margin-left: auto;
		color: var(--muted-color);
		font-size: 0.78rem;
	}

	.report-banner {
		display: flex;
		flex-wrap: wrap;
		justify-content: space-between;
		gap: 1rem;
		padding: 1.25rem 1.5rem;
		border: 1px solid var(--border-color);
		border-left: 4px solid var(--teal);
		border-radius: 12px;
		background: #fffdf8;
	}

	.report-banner h2 {
		margin: 0;
		font-size: 1.5rem;
		overflow-wrap: break-word;
	}

	@media (max-width: 640px) {
		.report-banner h2 {
			font-size: 1.3rem;
		}
	}

	.report-meta {
		margin: 0.35rem 0 0;
		color: var(--secondary);
		font-size: 0.86rem;
	}

	.report-caveat {
		max-width: 70ch;
		margin: 0.6rem 0 0;
		color: var(--muted-color);
		font-size: 0.82rem;
	}

	.posture-note {
		display: flex;
		flex-direction: column;
		gap: 0.3rem;
		color: var(--muted-color);
		font-size: 0.78rem;
	}

	.badge {
		padding: 0.3rem 0.55rem;
		border: 1px solid var(--teal);
		border-radius: 999px;
		color: var(--teal);
		font-weight: 700;
		text-align: center;
	}

	.matrix-panel,
	.capability-panel,
	.study-panel,
	.next-actions {
		padding: 1.5rem;
		border: 1px solid var(--border-color);
		border-radius: 12px;
		background: #fffdf8;
	}

	.panel-heading {
		display: flex;
		flex-wrap: wrap;
		align-items: baseline;
		justify-content: space-between;
		gap: 0.75rem;
		margin-bottom: 0.75rem;
	}

	.panel-heading h2,
	.next-actions h2 {
		margin: 0;
		font-size: 1.35rem;
	}

	.panel-heading p {
		margin: 0;
		color: var(--muted-color);
		font-size: 0.78rem;
	}

	.result-grid {
		display: grid;
		grid-template-columns: minmax(0, 1.1fr) minmax(0, 0.9fr);
		gap: 1.25rem;
	}

	.result-card,
	.inspect-card {
		padding: 1.35rem;
		border: 1px solid var(--border-color);
		border-radius: 12px;
		background: #fffdf8;
	}

	.result-card h2,
	.inspect-card h2 {
		margin: 0 0 0.6rem;
		font-size: 1.25rem;
	}

	.result-card p {
		color: var(--secondary);
		font-size: 0.88rem;
	}

	.delta-headline {
		color: var(--ink) !important;
		font-family: var(--font-heading);
		font-size: 1.35rem !important;
	}

	.delta-headline span {
		margin: 0 0.35rem;
		color: var(--muted-color);
	}

	.historical-winner {
		color: var(--rust) !important;
	}

	.inspect-card dl {
		display: grid;
		gap: 0.65rem;
		margin: 0;
	}

	.inspect-card dt {
		color: var(--muted-color);
		font-size: 0.68rem;
		letter-spacing: 0.08em;
		text-transform: uppercase;
	}

	.inspect-card dd {
		margin: 0.15rem 0 0;
		color: var(--secondary);
		font-size: 0.86rem;
	}

	.capability-grid {
		display: grid;
		grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
		gap: 0.9rem;
	}

	.capability-card {
		padding: 1rem;
		border: 1px solid var(--border-color);
		border-radius: 8px;
	}

	.capability-card h3 {
		margin: 0 0 0.5rem;
		font-size: 1.05rem;
	}

	.capability-card p {
		margin: 0 0 0.45rem;
		color: var(--secondary);
		font-size: 0.82rem;
	}

	.capability-evidence {
		color: var(--teal) !important;
		font-weight: 700;
	}

	.capability-scope {
		color: var(--muted-color) !important;
	}

	.capability-refs {
		font-family: monospace;
		font-size: 0.7rem !important;
		overflow-wrap: anywhere;
	}

	.study-table-wrap {
		overflow-x: auto;
	}

	.study-table {
		width: 100%;
		max-width: 620px;
		border-collapse: collapse;
		font-size: 0.88rem;
	}

	.study-table th,
	.study-table td {
		padding: 0.55rem 0.6rem;
		border-bottom: 1px solid var(--border-color);
		text-align: left;
	}

	.study-table thead th {
		color: var(--muted-color);
		font-size: 0.68rem;
		letter-spacing: 0.08em;
		text-transform: uppercase;
	}

	.study-table tbody th {
		font-weight: 600;
	}

	.study-table td {
		font-variant-numeric: tabular-nums;
	}

	.study-note,
	.source-note {
		margin: 0.75rem 0 0;
		color: var(--muted-color);
		font-size: 0.8rem;
	}

	.next-actions h2 {
		margin-bottom: 0.9rem;
	}

	.action-links {
		display: grid;
		grid-template-columns: repeat(3, minmax(0, 1fr));
		gap: 0.8rem;
	}

	.action-links a {
		display: flex;
		flex-direction: column;
		gap: 0.3rem;
		padding: 0.9rem;
		border: 1px solid var(--border-color);
		border-radius: 8px;
		color: var(--ink);
		font-size: 0.85rem;
		text-decoration: none;
	}

	.action-links a span {
		color: var(--teal);
	}

	.action-links a:hover {
		border-color: var(--teal);
	}

	.text-link {
		align-self: flex-start;
		color: var(--teal);
		font-weight: 700;
		text-underline-offset: 2px;
	}

	@media (max-width: 900px) {
		.result-grid,
		.action-links {
			grid-template-columns: 1fr;
		}
	}

	@media (max-width: 640px) {
		.report-banner,
		.matrix-panel,
		.capability-panel,
		.study-panel,
		.next-actions {
			padding: 1rem;
		}

		.selection-note {
			width: 100%;
			margin-left: 0;
		}
	}
</style>
