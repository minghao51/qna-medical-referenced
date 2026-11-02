<script lang="ts">
	import { onMount } from 'svelte';
	import AppShell from '$lib/components/AppShell.svelte';
	import ResearchNav from '$lib/components/ResearchNav.svelte';
	import LoadingSkeleton from '$lib/components/LoadingSkeleton.svelte';
	import {
		getDocuments,
		getExperiments,
		getExperimentResults
	} from '$lib/utils/api';
	import { formatDecimal } from '$lib/utils/eval';
	import { normalizeLegacyArchive } from '$lib/utils/research';
	import type {
		DocumentListResponse,
		ExperimentListResponse,
		ExperimentReport,
		LegacyArchiveProjection
	} from '$lib/types';

	type LoadState = 'loading' | 'available' | 'missing' | 'unauthorized' | 'error';

	let archiveState = $state<LoadState>('loading');
	let archiveError = $state('');
	let archive = $state<LegacyArchiveProjection | null>(null);
	let archiveTimestamp = $state<string | null>(null);
	let corpusState = $state<LoadState>('loading');
	let corpusError = $state('');
	let corpusTotal = $state<number | null>(null);
	let corpusCounts = $state<Record<string, number>>({});

	const preferredReportId = 'medical_semantic_chunking_exp';

	function isUnauthorized(message: string): boolean {
		return /401|x-api-key|missing .*key/i.test(message);
	}

	function formatCount(value: number | null | undefined): string {
		return typeof value === 'number' && Number.isFinite(value)
			? value.toLocaleString('en-US')
			: 'N/A';
	}

	function formatReportDate(value: string | null): string {
		if (!value) return 'Date not provided';
		const date = new Date(value);
		if (Number.isNaN(date.getTime())) return value;
		return date.toLocaleDateString('en-GB', {
			year: 'numeric',
			month: 'short',
			day: 'numeric'
		});
	}

	function sourceTypeLabel(type: string): string {
		const labels: Record<string, string> = {
			pdf: 'PDF',
			html: 'HTML',
			markdown: 'Markdown',
			reference_csv: 'Lab reference',
			csv: 'Lab reference',
			reference: 'Lab reference'
		};
		return labels[type] ?? type.replace(/_/g, ' ');
	}

	function percent(part: number | null | undefined, whole: number | null | undefined): number {
		if (typeof part !== 'number' || typeof whole !== 'number' || whole <= 0) return 0;
		return Math.min(100, Math.max(0, (part / whole) * 100));
	}

	const baseline = $derived(
		archive?.variants.find((variant) => variant.role === 'baseline') ??
			archive?.variants[0] ??
			null
	);
	const faithfulness = $derived(
		baseline?.answer_metrics.find((metric) => metric.metric_key === 'faithfulness') ?? null
	);
	const totals = $derived(baseline?.coverage_totals ?? null);
	const corpusEntries = $derived(
		Object.entries(corpusCounts).sort((left, right) => right[1] - left[1])
	);
	const maxCorpusCount = $derived(
		Math.max(0, ...Object.values(corpusCounts).filter((value) => Number.isFinite(value)))
	);

	async function loadArchive() {
		archiveState = 'loading';
		archiveError = '';
		try {
			const list = await getExperiments<ExperimentListResponse>();
			const candidates = list.reports.filter(
				(report) => report.availability === 'available' && typeof report.report_id === 'string'
			);
			const summary =
				candidates.find((report) => report.report_id === preferredReportId) ?? candidates[0];
			if (!summary?.report_id) {
				archiveState = 'missing';
				return;
			}

			const report = await getExperimentResults<ExperimentReport>(summary.report_id);
			const projection = normalizeLegacyArchive(report);
			if (projection.schema_kind !== 'legacy_feature_addition' || projection.variants.length === 0) {
				archiveState = 'missing';
				return;
			}
			archive = projection;
			archiveTimestamp = report.timestamp ?? null;
			archiveState = 'available';
		} catch (error) {
			const message = error instanceof Error ? error.message : 'Archived report unavailable.';
			archiveError = message;
			archiveState = isUnauthorized(message) ? 'unauthorized' : 'error';
		}
	}

	async function loadCorpus() {
		corpusState = 'loading';
		corpusError = '';
		try {
			const data = await getDocuments<DocumentListResponse>({ limit: 1, offset: 0 });
			corpusTotal = data.total;
			corpusCounts = data.source_type_counts ?? {};
			corpusState = 'available';
		} catch (error) {
			const message = error instanceof Error ? error.message : 'Index inventory unavailable.';
			corpusError = message;
			corpusState = isUnauthorized(message) ? 'unauthorized' : 'error';
		}
	}

	onMount(() => {
		void loadArchive();
		void loadCorpus();
	});
</script>

<svelte:head>
	<title>Fieldnote · Research workspace</title>
</svelte:head>

<AppShell current="/">
	<div class="workspace">
		<section class="hero" aria-labelledby="workspace-title">
			<div class="hero-copy">
				<p class="eyebrow">Private research / engineering evidence</p>
				<h1 id="workspace-title">What changes actually improve this system?</h1>
				<p class="lede">
					Inspect the dataset, the configuration and the measurement—not just the highest
					score.
				</p>
				<p class="privacy-note">
					Private lab · public or synthetic questions only · no clinical-suitability claim
				</p>
			</div>
			<div class="lab-card">
				<p class="card-eyebrow">Posture</p>
				<ul>
					<li>Archived metrics, not a live benchmark run</li>
					<li>CLI/YAML execution; no run button in the browser</li>
					<li>Comparisons remain unavailable until a verified cohort exists</li>
				</ul>
			</div>
		</section>

		<ResearchNav current="/" />

		<div class="primary-grid">
			<section class="card archive-card" aria-labelledby="archive-title">
				<p class="card-eyebrow">Local archived report</p>
				<h2 id="archive-title">A strong average can hide missing measurements.</h2>

				{#if archiveState === 'loading'}
					<LoadingSkeleton count={2} type="card" />
				{:else if archiveState === 'available'}
					{#if faithfulness}
					<p class="report-meta">
						{formatReportDate(archiveTimestamp)} · 57-query baseline · revision
						{archive?.report_sha256 ? `${archive.report_sha256.slice(0, 12)}…` : 'not recorded'}
					</p>

					<div class="metric-headline">
						<div>
							<p class="metric-label">Faithfulness mean</p>
							<p class="metric-value">{formatDecimal(faithfulness.mean, 4)}</p>
						</div>
						<div class="metric-counts">
							<span>{formatCount(faithfulness.measured_slots)} measured</span>
							<span>{formatCount(faithfulness.failed_slots)} failed</span>
							<span>{formatCount(faithfulness.expected_slots)} expected</span>
						</div>
					</div>

					<div
						class="coverage-bar"
						role="img"
						aria-label={`Faithfulness coverage: ${formatCount(faithfulness.measured_slots)} measured, ${formatCount(faithfulness.failed_slots)} failed, ${formatCount(faithfulness.expected_slots)} expected`}
					>
						<span
							class="bar-measured"
							style={`width:${percent(faithfulness.measured_slots, faithfulness.expected_slots)}%`}
						></span>
						<span
							class="bar-failed"
							style={`width:${percent(faithfulness.failed_slots, faithfulness.expected_slots)}%`}
						></span>
					</div>

					<p class="coverage-note">
						Read coverage before comparing quality. Across six answer metrics,
						{formatCount(totals?.measured_slots)} of {formatCount(totals?.expected_slots)} slots were
						measured and {formatCount(totals?.failed_slots)} failed. The archived winner is
						historical, not current eligibility.
					</p>

					{#if archive?.identity_status !== 'byte_revision_recorded'}
						<p class="state-note">Report revision bytes are not verified for this artifact.</p>
					{/if}

					<a class="button" href="/research/evaluations">Inspect evaluation coverage →</a>
					{:else}
						<div class="state-block" role="status">
							<h3>Faithfulness measurement not recorded</h3>
							<p>
								This archive is readable, but it does not expose the expected answer-metric coverage.
							</p>
							<a class="text-link" href="/eval?tab=quality">Open legacy evaluation diagnostics</a>
						</div>
					{/if}
				{:else}
					<div class="state-block" role="status">
						<h3>
							{#if archiveState === 'unauthorized'}
								Archived report requires operator access
							{:else if archiveState === 'missing'}
								No archived report is available
							{:else}
								Archived report unavailable
							{/if}
						</h3>
						<p>
							{#if archiveState === 'unauthorized'}
								This private-lab view needs the authenticated gateway. It does not fall back to a
								latest run.
							{:else if archiveState === 'missing'}
								No supported report artifact was found for this workspace.
							{:else}
								{archiveError || 'The report could not be read safely.'}
							{/if}
						</p>
						<a class="text-link" href="/eval">Open legacy evaluation diagnostics</a>
					</div>
				{/if}
			</section>

			<section class="card ask-card" aria-labelledby="ask-title">
				<p class="card-eyebrow">Q&amp;A workbench</p>
				<h2 id="ask-title">Ask. Inspect a turn. Understand the retrieval.</h2>
				<p>
					Use public or synthetic questions only. This is not a clinical product, and answers
					are not medical advice.
				</p>
				<ul class="plain-list">
					<li>Current conversation stays cookie-bound</li>
					<li>Source entries and recorded trace are inspected after completion</li>
					<li>Unavailable sources or traces say so rather than being reconstructed</li>
				</ul>
				<a class="button" href="/ask">Open Q&amp;A workbench →</a>
			</section>
		</div>

		<section class="pathways" aria-labelledby="pathways-title">
			<div class="section-heading">
				<p class="card-eyebrow">Three ways to investigate</p>
				<h2 id="pathways-title">Start with the evidence behind the score.</h2>
			</div>
			<div class="pathway-grid">
				<a class="pathway" href="/research/evaluations">
					<span class="pathway-index">01</span>
					<h3>Evaluations</h3>
					<p>See execution, measurement and eligibility as separate states.</p>
					<span class="pathway-action">Inspect reports →</span>
				</a>
				<a class="pathway" href="/research/features">
					<span class="pathway-index">02</span>
					<h3>Features</h3>
					<p>Separate a configured capability from an effective, measured change.</p>
					<span class="pathway-action">Compare feature evidence →</span>
				</a>
				<a class="pathway" href="/research/datasets">
					<span class="pathway-index">03</span>
					<h3>Datasets</h3>
					<p>Know what was tested, what overlaps and what the labels can support.</p>
					<span class="pathway-action">Inspect dataset cards →</span>
				</a>
			</div>
			<p class="pending-note">
				Comparison views remain unavailable until a verified cohort exists.
			</p>
		</section>

		<section class="card corpus-card" aria-labelledby="corpus-title">
			<div>
				<p class="card-eyebrow">Frozen index context</p>
				<h2 id="corpus-title">What is in the frozen index?</h2>

				{#if corpusState === 'loading'}
					<LoadingSkeleton count={1} type="card" />
				{:else if corpusState === 'available'}
					<p class="corpus-total">
						{formatCount(corpusTotal)} indexed chunks · counts, not publications
					</p>
					{#if corpusEntries.length > 0}
						<dl class="corpus-counts">
							{#each corpusEntries as [type, count]}
								<div class="corpus-row">
									<dt>{sourceTypeLabel(type)}</dt>
									<dd>
										<span class="corpus-bar" aria-hidden="true">
											<span style={`width:${percent(count, maxCorpusCount)}%`}></span>
										</span>
										<strong>{formatCount(count)}</strong>
									</dd>
								</div>
							{/each}
						</dl>
					{:else}
						<p class="state-note">Source-type counts were not provided by the index.</p>
					{/if}
					<p class="corpus-note">
						Source: local D11 <code>medical_docs</code> index, read-only count. Do not pool these
						inventories with query or case counts.
					</p>
					<a class="text-link" href="/evidence">Inspect indexed chunks →</a>
				{:else}
					<div class="state-block" role="status">
						<h3>
							{corpusState === 'unauthorized'
								? 'Index inventory requires operator access'
								: 'Index inventory unavailable'}
						</h3>
						<p>
							{corpusState === 'unauthorized'
								? 'The private-lab boundary is unchanged; the workspace does not substitute zero counts.'
								: corpusError || 'The index count could not be read.'}
						</p>
					</div>
				{/if}
			</div>
			<aside class="unit-note">
				<p class="card-eyebrow">Units differ</p>
				<p>
					Chunks, questions, conversations and review cases are different units. They are shown
					separately and never summed into one evidence total.
				</p>
			</aside>
		</section>

		<p class="footer-note">
			Archived metrics are shown with their recorded denominators. No live run, promotion or
			clinical-suitability claim is implied.
		</p>
	</div>
</AppShell>

<style>
	.workspace {
		display: flex;
		flex-direction: column;
		gap: 1.75rem;
	}

	.eyebrow,
	.card-eyebrow {
		margin: 0 0 0.5rem;
		color: var(--muted-color);
		font-size: 0.7rem;
		font-weight: 700;
		letter-spacing: 0.14em;
		text-transform: uppercase;
	}

	.hero {
		display: grid;
		grid-template-columns: minmax(0, 1.5fr) minmax(260px, 0.8fr);
		gap: 2rem;
		align-items: start;
	}

	h1 {
		max-width: 18ch;
		margin: 0;
		font-size: clamp(2rem, 4.2vw, 3.35rem);
		letter-spacing: -0.02em;
	}

	.lede {
		max-width: 52ch;
		margin: 1rem 0 0;
		font-size: 1.05rem;
		color: var(--secondary);
	}

	.privacy-note {
		margin: 1rem 0 0;
		font-size: 0.82rem;
		color: var(--rust);
	}

	.lab-card {
		padding: 0.25rem 0 0.25rem 1.25rem;
		border-left: 3px solid var(--teal);
	}

	.lab-card ul,
	.plain-list {
		margin: 0;
		padding-left: 1.1rem;
		color: var(--secondary);
		font-size: 0.9rem;
	}

	.lab-card li + li,
	.plain-list li + li {
		margin-top: 0.45rem;
	}

	.primary-grid {
		display: grid;
		grid-template-columns: minmax(0, 1.3fr) minmax(0, 0.9fr);
		gap: 1.25rem;
	}

	.card {
		padding: 1.5rem;
		border: 1px solid var(--border-color);
		border-radius: 14px;
		background: #fffdf8;
	}

	.card h2 {
		margin: 0 0 0.75rem;
		font-size: clamp(1.35rem, 2.2vw, 1.75rem);
	}

	.report-meta {
		margin: 0 0 1rem;
		color: var(--muted-color);
		font-size: 0.82rem;
	}

	.metric-headline {
		display: flex;
		align-items: flex-end;
		justify-content: space-between;
		gap: 1rem;
		flex-wrap: wrap;
	}

	.metric-label {
		margin: 0;
		color: var(--muted-color);
		font-size: 0.8rem;
	}

	.metric-value {
		margin: 0.1rem 0 0;
		font-family: var(--font-heading);
		font-size: 2.6rem;
		line-height: 1;
	}

	.metric-counts {
		display: flex;
		flex-wrap: wrap;
		gap: 0.4rem;
		font-size: 0.78rem;
		color: var(--secondary);
	}

	.metric-counts span {
		padding: 0.25rem 0.5rem;
		border: 1px solid var(--border-color);
		border-radius: 4px;
	}

	.coverage-bar {
		display: flex;
		height: 12px;
		margin: 1rem 0 0.5rem;
		overflow: hidden;
		border-radius: 999px;
		background: var(--surface-strong);
	}

	.bar-measured {
		background: var(--teal);
	}

	.bar-failed {
		background: var(--rust);
	}

	.coverage-note,
	.corpus-note,
	.footer-note {
		color: var(--secondary);
		font-size: 0.86rem;
	}

	.state-note {
		margin: 0.5rem 0 0;
		color: var(--rust);
		font-size: 0.82rem;
	}

	.button {
		display: inline-flex;
		align-items: center;
		min-height: 44px;
		margin-top: 1rem;
		padding: 0.6rem 1rem;
		border-radius: 6px;
		background: var(--teal);
		color: #fff;
		font-weight: 700;
		text-decoration: none;
	}

	.button:hover {
		background: #00574f;
	}

	.text-link,
	.pathway-action {
		color: var(--teal);
		font-weight: 700;
		text-decoration: underline;
		text-underline-offset: 2px;
	}

	.ask-card {
		border-color: var(--ink);
		background: var(--ink);
		color: var(--paper);
	}

	.ask-card h2 {
		color: var(--paper);
	}

	.ask-card p,
	.ask-card .plain-list {
		color: #c7d1cf;
	}

	.ask-card .card-eyebrow {
		color: #9fc7bf;
	}

	.ask-card .button {
		background: var(--paper);
		color: var(--ink);
	}

	.plain-list {
		margin-top: 0.75rem;
	}

	.pathways {
		padding: 1.5rem;
		border: 1px solid var(--border-color);
		border-radius: 14px;
		background: var(--surface-subtle);
	}

	.section-heading {
		margin-bottom: 1rem;
	}

	.section-heading h2 {
		margin: 0;
		font-size: clamp(1.4rem, 2.2vw, 1.8rem);
	}

	.pathway-grid {
		display: grid;
		grid-template-columns: repeat(3, minmax(0, 1fr));
		gap: 1rem;
	}

	.pathway {
		display: flex;
		flex-direction: column;
		min-height: 100%;
		padding: 1.1rem;
		border: 1px solid var(--border-color);
		border-radius: 10px;
		background: #fffdf8;
		color: var(--ink);
		text-decoration: none;
	}

	.pathway:hover {
		border-color: var(--teal);
	}

	.pathway-index {
		color: var(--rust);
		font-family: var(--font-heading);
		font-size: 0.9rem;
	}

	.pathway h3 {
		margin: 0.5rem 0;
		font-size: 1.2rem;
	}

	.pathway p {
		flex: 1;
		margin: 0 0 0.9rem;
		color: var(--secondary);
		font-size: 0.88rem;
	}

	.pending-note {
		margin: 1rem 0 0;
		color: var(--muted-color);
		font-size: 0.8rem;
	}

	.corpus-card {
		display: grid;
		grid-template-columns: minmax(0, 1.6fr) minmax(220px, 0.7fr);
		gap: 1.5rem;
	}

	.corpus-total {
		margin: 0 0 0.9rem;
		font-family: var(--font-heading);
		font-size: 1.35rem;
	}

	.corpus-counts {
		display: grid;
		gap: 0.55rem;
		margin: 0 0 1rem;
	}

	.corpus-row {
		display: grid;
		grid-template-columns: 7rem minmax(0, 1fr);
		align-items: center;
		gap: 0.75rem;
	}

	.corpus-counts dt {
		color: var(--muted-color);
		font-size: 0.78rem;
	}

	.corpus-counts dd {
		display: grid;
		grid-template-columns: minmax(0, 1fr) 4rem;
		align-items: center;
		gap: 0.65rem;
		margin: 0;
		font-size: 0.82rem;
	}

	.corpus-counts dd strong {
		font-variant-numeric: tabular-nums;
		text-align: right;
	}

	.corpus-bar {
		display: block;
		height: 12px;
		overflow: hidden;
		border-radius: 2px;
		background: var(--surface-strong);
	}

	.corpus-bar span {
		display: block;
		height: 100%;
		border-radius: 2px;
		background: var(--teal);
	}

	.corpus-row:nth-child(2) .corpus-bar span {
		background: var(--blue);
	}

	.unit-note {
		padding: 1rem;
		border-left: 3px solid var(--blue);
		background: var(--surface-subtle);
		font-size: 0.86rem;
		color: var(--secondary);
	}

	.state-block {
		padding: 1rem;
		border: 1px dashed var(--border-color);
		border-radius: 8px;
		background: var(--surface-subtle);
	}

	.state-block h3 {
		margin: 0 0 0.5rem;
		font-size: 1rem;
	}

	.state-block p {
		margin: 0 0 0.5rem;
		color: var(--secondary);
		font-size: 0.88rem;
	}

	.footer-note {
		margin: 0;
		padding-top: 0.5rem;
		border-top: 1px solid var(--border-color);
	}

	@media (max-width: 1024px) {
		.hero,
		.primary-grid,
		.corpus-card {
			grid-template-columns: 1fr;
		}

		.pathway-grid {
			grid-template-columns: 1fr;
		}
	}

	@media (max-width: 640px) {
		.card,
		.pathways {
			padding: 1.1rem;
		}

		.corpus-row {
			grid-template-columns: 5.5rem minmax(0, 1fr);
			gap: 0.5rem;
		}

		.corpus-counts dd {
			grid-template-columns: minmax(0, 1fr) 3rem;
			gap: 0.4rem;
		}
	}
</style>
