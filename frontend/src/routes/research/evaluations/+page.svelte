<script lang="ts">
	import { onMount } from 'svelte';
	import AppShell from '$lib/components/AppShell.svelte';
	import EmptyState from '$lib/components/EmptyState.svelte';
	import LoadingSkeleton from '$lib/components/LoadingSkeleton.svelte';
	import MeasurementCoverage from '$lib/components/MeasurementCoverage.svelte';
	import ResearchNav from '$lib/components/ResearchNav.svelte';
	import { getExperiments, getExperimentResults } from '$lib/utils/api';
	import { formatDecimal, formatPercent } from '$lib/utils/eval';
	import { normalizeLegacyArchive } from '$lib/utils/research';
	import type {
		ExperimentListResponse,
		ExperimentReport,
		ExperimentReportSummary,
		LegacyArchiveProjection
	} from '$lib/types';

	type LoadState = 'loading' | 'available' | 'missing' | 'unsupported' | 'unauthorized' | 'error';

	const preferredReportId = 'medical_semantic_chunking_exp';
	const reportIdPattern = /^[A-Za-z0-9_-][A-Za-z0-9._-]*$/;

	let loadState = $state<LoadState>('loading');
	let errorMessage = $state('');
	let list = $state<ExperimentListResponse | null>(null);
	let selectedReportId = $state('');
	let report = $state<ExperimentReport | null>(null);
	let archive = $state<LegacyArchiveProjection | null>(null);
	let requestSequence = 0;

	const availableReports = $derived(
		(list?.reports ?? []).filter(
			(item): item is ExperimentReportSummary & { report_id: string } =>
				item.availability === 'available' && typeof item.report_id === 'string'
		)
	);
	const baseline = $derived(
		archive?.variants.find((variant) => variant.role === 'baseline') ??
			archive?.variants[0] ??
			null
	);
	const metrics = $derived(baseline?.answer_metrics ?? []);
	const totals = $derived(baseline?.coverage_totals ?? null);
	const errorRate = $derived(
		totals?.failed_slots != null && totals?.expected_slots
			? totals.failed_slots / totals.expected_slots
			: null
	);

	function isUnauthorized(message: string): boolean {
		return /401|x-api-key|missing .*key/i.test(message);
	}

	function formatCount(value: number | null | undefined): string {
		return typeof value === 'number' && Number.isFinite(value)
			? value.toLocaleString('en-US')
			: 'N/A';
	}

	function formatReportDate(value: string | null | undefined): string {
		if (!value) return 'Date not provided';
		const date = new Date(value);
		if (Number.isNaN(date.getTime())) return value;
		return date.toLocaleDateString('en-GB', {
			year: 'numeric',
			month: 'short',
			day: 'numeric'
		});
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

	async function loadReport(reportId: string) {
		const token = ++requestSequence;
		loadState = 'loading';
		errorMessage = '';
		report = null;
		archive = null;
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
			archive = projection;
			loadState = 'available';
		} catch (error) {
			if (token !== requestSequence) return;
			const message =
				error instanceof Error ? error.message : 'The archived evaluation could not be read.';
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
				error instanceof Error ? error.message : 'The archived evaluation list is unavailable.';
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
	<title>Evaluations · Fieldnote</title>
</svelte:head>

<AppShell current="/research/evaluations">
	<div class="evaluations-page">
		<header class="page-header">
			<p class="eyebrow">Evaluation / local archived report</p>
			<h1>Read the missing measurements before the means.</h1>
			<p class="lede">
				Artifact identity, metric coverage and definitions stay separate from eligibility.
				Comparisons remain unavailable without a verified cohort.
			</p>
		</header>

		<ResearchNav current="/research/evaluations" />

		{#if availableReports.length > 0}
			<div class="selection-bar">
				<label for="report-select">Archived report</label>
				{#if availableReports.length > 1}
					<select
						id="report-select"
						value={selectedReportId}
						onchange={(event) => selectReport(event.currentTarget.value)}
					>
						{#each availableReports as item}
							<option value={item.report_id}>{item.report_id}</option>
						{/each}
					</select>
				{:else}
					<span class="selected-report">{selectedReportId || availableReports[0].report_id}</span>
				{/if}
				<span class="selection-note">
					Archive selection, not a live run. <a href="/eval">Current runs</a> stay on legacy diagnostics.
				</span>
			</div>
		{/if}

		{#if loadState === 'loading'}
			<div class="loading-panel" aria-busy="true">
				<LoadingSkeleton count={3} type="card" />
			</div>
		{:else if loadState === 'unauthorized'}
			<EmptyState
				title="Research access required"
				body="This private-lab view needs the authenticated gateway. It does not fall back to a latest run."
			/>
			<a class="text-link" href="/ask">Back to Ask</a>
		{:else if loadState === 'missing'}
			<EmptyState
				title="Requested archived report unavailable"
				body={selectedReportId
					? `${selectedReportId} is not an available report in this archive. No latest report was substituted.`
					: 'No supported archived report is available in this installation.'}
			/>
			<a class="text-link" href="/eval">Open legacy evaluation diagnostics</a>
		{:else if loadState === 'unsupported'}
			<EmptyState
				title="Unsupported archive schema"
				body="This report does not match the reviewed legacy shape. Its raw diagnostics remain available on the legacy evaluation page."
			/>
			<a class="text-link" href="/eval">Inspect raw diagnostics</a>
		{:else if loadState === 'error'}
			<EmptyState
				title="Archived evaluation unavailable"
				body={errorMessage || 'The report could not be read safely.'}
			/>
			<a class="text-link" href="/eval">Open legacy evaluation diagnostics</a>
		{:else if loadState === 'available' && archive && baseline}
			<section class="report-summary" aria-labelledby="report-title">
				<div>
					<p class="eyebrow">Degraded measurement</p>
					<h2 id="report-title">{#each (archive.report_id ?? '').split('_') as part, index}{#if index > 0}_{/if}{part}<wbr />{/each}</h2>
					<p class="report-meta">
						Baseline · {formatCount(baseline.query_count)} queries · {formatReportDate(
							report?.timestamp
						)} · archived aggregate
					</p>
					<p class="report-caveat">
						The underlying per-case run rows are not exposed by this aggregate report. Per-case
						failures and judge reasons are not inferred from counts.
					</p>
				</div>
				<div class="comparison-badge">
					<span class="badge">Archive, not comparable cohort</span>
					<span>comparable = false</span>
				</div>
			</section>

			<section class="coverage-summary" aria-labelledby="coverage-summary-title">
				<div class="summary-figure">
					<p class="summary-label" id="coverage-summary-title">Measurement slots</p>
					<p class="summary-value">
						{formatCount(totals?.measured_slots)} / {formatCount(totals?.expected_slots)}
					</p>
					<p class="summary-detail">
						{formatCount(totals?.failed_slots)} failed ·
						{errorRate === null ? 'N/A' : formatPercent(errorRate)}
						error rate
					</p>
				</div>
				<div class="summary-copy">
					<p>
						{metrics.length} answer metrics × {formatCount(baseline.query_count)} queries.
						These are metric slots, not patient cases.
					</p>
					<p>
						Means summarize successful measurements only; missing slots are never scored zero.
						{#if metrics[0]?.expected_basis === 'legacy_one_slot_per_query'}
							Legacy expectation basis: one slot per declared query.
						{/if}
					</p>
				</div>
			</section>

			<section class="coverage-panel" aria-labelledby="coverage-table-title">
				<div class="panel-heading">
					<h2 id="coverage-table-title">Metric coverage</h2>
					<p>
						<span class="legend-swatch measured"></span> successful measurement
						<span class="legend-swatch failed"></span> failed metric evaluation
					</p>
				</div>
				<MeasurementCoverage {metrics} />
				<p class="table-note">
					Coverage scale is per-row expected slots. A high mean computed over few successful
					measurements is not a complete result.
				</p>
			</section>

			<details class="provenance">
				<summary>View report provenance</summary>
				<dl>
					<div>
						<dt>Report ID</dt>
						<dd>{archive.report_id}</dd>
					</div>
					<div>
						<dt>Schema kind</dt>
						<dd>{archive.schema_kind}</dd>
					</div>
					<div>
						<dt>Exact-byte revision</dt>
						<dd>
							{archive.report_sha256
								? `${archive.report_sha256.slice(0, 16)}…`
								: 'Not recorded'}
						</dd>
					</div>
					<div>
						<dt>Config association</dt>
						<dd>
							{archive.config_ref ?? 'None'}
							{#if archive.config_binding}
								· explicit archive association
							{/if}
						</dd>
					</div>
					<div>
						<dt>Historical binding</dt>
						<dd>{archive.historical_binding}</dd>
					</div>
					<div>
						<dt>Comparability</dt>
						<dd>Not comparable (comparable=false)</dd>
					</div>
				</dl>
			</details>

			<section class="gate" aria-labelledby="gate-title">
				<p class="eyebrow">Comparison / inspection is not eligibility</p>
				<h2 id="gate-title">Comparison not verified</h2>
				<p>
					Current API history returns <code>comparable=false</code>. Inspect records
					independently; do not enable aggregate trends or promote the archived winner.
				</p>
				<ul>
					<li>Format compatibility and matching row counts do not establish a cohort.</li>
					<li>Dataset overlap is not historical byte or label identity.</li>
					<li>A future verified cohort needs an explicit backend contract.</li>
				</ul>
			</section>

			<section class="next-actions" aria-labelledby="next-title">
				<h2 id="next-title">What can you inspect next?</h2>
				<div class="action-links">
					<a class="action-card" href="/research/features">
						<strong>Inspect configured feature changes</strong>
						<span>Declared settings and archived variant outcomes →</span>
					</a>
					<a class="action-card" href="/research/methodology">
						<strong>Read the measurement methodology</strong>
						<span>Units, definitions, identity and comparison limits →</span>
					</a>
					<a class="action-card" href="/eval?tab=quality">
						<strong>Open legacy L0–L6 diagnostics</strong>
						<span>Detailed tabs, thresholds and exports remain available →</span>
					</a>
				</div>
				<p class="source-note">
					Source: archived report projection from the experiments API. No judge identity is
					verified, and metric names are not evidence of clinical suitability.
				</p>
			</section>
		{/if}
	</div>
</AppShell>

<style>
	.evaluations-page {
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
		max-width: 24ch;
		margin: 0;
		font-size: clamp(2rem, 3.8vw, 3rem);
	}

	.lede {
		max-width: 65ch;
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

	.report-summary {
		display: flex;
		flex-wrap: wrap;
		align-items: flex-start;
		justify-content: space-between;
		gap: 1rem;
		padding: 1.25rem 1.5rem;
		border: 1px solid var(--border-color);
		border-left: 4px solid var(--rust);
		border-radius: 12px;
		background: #fffdf8;
	}

	.report-summary h2 {
		margin: 0;
		font-size: 1.5rem;
		overflow-wrap: break-word;
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

	.comparison-badge {
		display: flex;
		flex-direction: column;
		gap: 0.3rem;
		color: var(--muted-color);
		font-size: 0.78rem;
	}

	.badge {
		padding: 0.3rem 0.55rem;
		border: 1px solid var(--rust);
		border-radius: 999px;
		color: var(--rust);
		font-weight: 700;
		text-align: center;
	}

	.coverage-summary {
		display: grid;
		grid-template-columns: minmax(220px, 0.7fr) minmax(0, 1.3fr);
		gap: 1.5rem;
		padding: 1.5rem;
		border: 1px solid var(--ink);
		border-radius: 12px;
		background: var(--ink);
		color: var(--paper);
	}

	.summary-label {
		margin: 0;
		color: #b9cbc7;
		font-size: 0.72rem;
		font-weight: 700;
		letter-spacing: 0.1em;
		text-transform: uppercase;
	}

	.summary-value {
		margin: 0.25rem 0 0;
		font-family: var(--font-heading);
		font-size: clamp(2rem, 4vw, 2.8rem);
		line-height: 1;
		color: var(--paper);
	}

	.summary-detail {
		margin: 0.4rem 0 0;
		color: #f0b09d;
		font-size: 0.86rem;
	}

	.summary-copy p {
		margin: 0 0 0.5rem;
		color: #c7d1cf;
		font-size: 0.9rem;
	}

	.coverage-panel,
	.gate,
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
	.gate h2,
	.next-actions h2 {
		margin: 0;
		font-size: 1.35rem;
	}

	.panel-heading p {
		margin: 0;
		color: var(--muted-color);
		font-size: 0.75rem;
	}

	.legend-swatch {
		display: inline-block;
		width: 0.7rem;
		height: 0.7rem;
		margin: 0 0.2rem 0 0.6rem;
		border-radius: 2px;
	}

	.legend-swatch.measured {
		background: var(--teal);
	}

	.legend-swatch.failed {
		background: var(--rust);
	}

	.table-note {
		margin: 0.75rem 0 0;
		color: var(--muted-color);
		font-size: 0.8rem;
	}

	.provenance {
		padding: 0.9rem 1.25rem;
		border: 1px solid var(--border-color);
		border-radius: 10px;
		background: #fffdf8;
	}

	.provenance summary {
		cursor: pointer;
		font-weight: 700;
	}

	.provenance dl {
		display: grid;
		grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
		gap: 0.9rem;
		margin: 1rem 0 0;
	}

	.provenance dt {
		color: var(--muted-color);
		font-size: 0.7rem;
		letter-spacing: 0.08em;
		text-transform: uppercase;
	}

	.provenance dd {
		margin: 0.2rem 0 0;
		font-size: 0.86rem;
		overflow-wrap: anywhere;
	}

	.gate {
		border-left: 4px solid var(--blue);
		background: var(--surface-subtle);
	}

	.gate p,
	.gate li {
		color: var(--secondary);
		font-size: 0.88rem;
	}

	.gate ul {
		margin: 0.75rem 0 0;
		padding-left: 1.1rem;
	}

	.next-actions h2 {
		margin-bottom: 0.9rem;
	}

	.action-links {
		display: grid;
		grid-template-columns: repeat(3, minmax(0, 1fr));
		gap: 0.8rem;
	}

	.action-card {
		display: flex;
		flex-direction: column;
		gap: 0.35rem;
		padding: 0.9rem;
		border: 1px solid var(--border-color);
		border-radius: 8px;
		color: var(--ink);
		font-size: 0.85rem;
		text-decoration: none;
	}

	.action-card span {
		color: var(--teal);
	}

	.action-card:hover {
		border-color: var(--teal);
	}

	.source-note {
		margin: 1rem 0 0;
		color: var(--muted-color);
		font-size: 0.76rem;
	}

	.text-link {
		align-self: flex-start;
		color: var(--teal);
		font-weight: 700;
		text-underline-offset: 2px;
	}

	@media (max-width: 900px) {
		.coverage-summary,
		.action-links {
			grid-template-columns: 1fr;
		}
	}

	@media (max-width: 640px) {
		.report-summary,
		.coverage-summary,
		.coverage-panel,
		.gate,
		.next-actions {
			padding: 1rem;
		}

		.selection-note {
			width: 100%;
			margin-left: 0;
		}
	}
</style>
