<script lang="ts">
	import { onMount } from 'svelte';
	import MetricChart from '$lib/components/MetricChart.svelte';
	import MetricTile from '$lib/components/MetricTile.svelte';
	import EvalSection from '$lib/components/EvalSection.svelte';
	import LoadingSkeleton from '$lib/components/LoadingSkeleton.svelte';
	import EmptyState from '$lib/components/EmptyState.svelte';
	import { getApiBaseUrl } from '$lib/utils/api';
	import type { FullAblationResponse, FullAblationRun } from '$lib/types';

	type DimensionKey = 'all' | 'pdf_extraction' | 'html_extraction' | 'chunking_strategy' | 'chunk_size' | 'retrieval' | 'combined';
	type FeatureFinding = {
		family: string;
		winner: string;
		dataset: string;
		queryCount: number;
		metrics: string[];
		verdict: string;
	};

	const API_URL = getApiBaseUrl();

	let data: FullAblationResponse | null = null;
	let loading = true;
	let error: string | null = null;
	let activeDimension: DimensionKey = 'all';
	let showFindings = true;

	const latestFeatureFindings: FeatureFinding[] = [
		{
			family: 'Keyword / Summaries',
			winner: 'baseline',
			dataset: 'golden_queries_expanded.json',
			queryCount: 54,
			metrics: [
				'NDCG@K 0.6813',
				'MRR 0.6673',
				'Exact chunk hit 0.0556',
				'Evidence hit 0.0185',
				'Latency p50 515.0ms'
			],
			verdict: 'Keyword extraction and chunk summaries tied the baseline on retrieval quality and only added latency.'
		},
		{
			family: 'HyPE / HyDE',
			winner: 'hype_10pct',
			dataset: 'golden_queries_expanded.json',
			queryCount: 54,
			metrics: [
				'NDCG@K 0.6813',
				'MRR 0.6673',
				'Exact chunk hit 0.0556',
				'Evidence hit 0.0185',
				'Latency p50 520.0ms'
			],
			verdict: 'HyPE and HyDE did not improve retrieval quality on the expanded benchmark; the winning variant was simply the fastest.'
		},
		{
			family: 'Reranking',
			winner: 'cross_encoder_only',
			dataset: 'golden_queries_expanded.json',
			queryCount: 54,
			metrics: [
				'NDCG@K 0.7205',
				'MRR 0.7034',
				'Exact chunk hit 0.0741',
				'Evidence hit 0.1852',
				'Latency p50 485.0ms'
			],
			verdict: 'Cross-encoder reranking was the only tested feature family with a clear retrieval-quality gain, but it roughly doubled p50 latency versus no reranking.'
		}
	];

	const allDimensions: { key: DimensionKey; label: string }[] = [
		{ key: 'all', label: 'All Variants' },
		{ key: 'pdf_extraction', label: 'PDF Extraction' },
		{ key: 'html_extraction', label: 'HTML Extraction' },
		{ key: 'chunking_strategy', label: 'Chunking Strategy' },
		{ key: 'chunk_size', label: 'Chunk Size' },
		{ key: 'retrieval', label: 'Retrieval' },
		{ key: 'combined', label: 'Combined' }
	];

	function getVisibleRuns(d: FullAblationResponse | null, dim: DimensionKey): FullAblationRun[] {
		if (!d) return [];
		if (dim === 'all') return d.runs;
		return d.dimensions[dim] ?? [];
	}

	function getChartData(runs: FullAblationRun[], optimal: string, baseline: string) {
		return {
			labels: runs.map((r) => r.variant),
			datasets: [
				{
					label: 'NDCG@K',
					data: runs.map((r) => r.ndcg_at_k ?? 0),
					backgroundColor: runs.map((r) => {
						if (r.variant === optimal) return '#10b981';
						if (r.variant === baseline) return '#6366f1';
						return '#94a3b8';
					}),
					borderRadius: 6
				}
			]
		};
	}

	const impactColor = (impact: string) => {
		if (impact === 'high') return '#ef4444';
		if (impact === 'medium') return '#f59e0b';
		return '#6b7280';
	};

	const deltaLabel = (delta?: number) => {
		if (delta == null) return '';
		const sign = delta >= 0 ? '+' : '';
		return `${sign}${(delta * 100).toFixed(1)}%`;
	};

	onMount(async () => {
		try {
			const res = await fetch(`${API_URL}/evaluation/ablation/full`);
			if (!res.ok) throw new Error(`HTTP ${res.status}`);
			data = await res.json();
		} catch (e: unknown) {
			const msg = e instanceof Error ? e.message : 'Failed to load ablation data';
			error = msg;
		} finally {
			loading = false;
		}
	});
</script>

<div class="ablation-page">
	{#if loading}
		<EvalSection title="Ablation Study Results" description="Loading comprehensive ablation data...">
			<LoadingSkeleton count={4} type="card" height="80px" />
		</EvalSection>
	{:else if error}
		<EmptyState title="Failed to load ablation data" body={error} />
	{:else if !data || data.runs.length === 0}
		<EmptyState
			title="No ablation results available"
			body="Run the ablation study with scripts/run_variant_clean.py to generate results."
		/>
	{:else}
		<div class="page-header">
			<h1>Ablation Study Results</h1>
			<p class="subtitle">
				{data.total_variants} variants · Clean-state isolation · Optimal: <strong>{data.optimal_variant}</strong>
			</p>
		</div>

		<EvalSection
			title="Latest Feature Benchmark"
			description="Expanded 54-query feature-family snapshot from 2026-04-15"
		>
			<div class="feature-findings-grid">
				{#each latestFeatureFindings as finding}
					<div class="feature-finding-card">
						<div class="feature-finding-header">
							<div>
								<h3>{finding.family}</h3>
								<p>{finding.queryCount} queries · {finding.dataset}</p>
							</div>
							<span class="badge optimal-badge">{finding.winner}</span>
						</div>
						<div class="feature-metrics">
							{#each finding.metrics as metric}
								<span class="feature-metric-pill">{metric}</span>
							{/each}
						</div>
						<p class="feature-verdict">{finding.verdict}</p>
					</div>
				{/each}
			</div>
		</EvalSection>

		<!-- Key metrics -->
		<div class="summary-grid">
			{#each data.runs.slice(0, 3) as run, i}
				<MetricTile
					label={'#{i + 1} ' + run.variant}
					value={run.ndcg_at_k?.toFixed(4) ?? '—'}
					quiet={i > 0}
				/>
			{/each}
		</div>

		<!-- Findings -->
		{#if showFindings && data.findings && data.findings.length}
			<EvalSection
				title="Key Findings"
				description="Insights from the comprehensive ablation study"
			>
				<div class="findings-grid">
					{#each data.findings as finding}
						<div class="finding-card">
							<div class="finding-header">
								<span class="finding-impact" style="background: {impactColor(finding.impact)}">
									{finding.impact}
								</span>
								<strong>{finding.title}</strong>
							</div>
							<p>{finding.detail}</p>
						</div>
					{/each}
				</div>
			</EvalSection>
		{/if}

		<!-- Chart -->
		<EvalSection
			title="NDCG@K by Variant"
			description="Ranked retrieval quality across all variants"
		>
			<div class="chart-toolbar">
				<div class="dimension-tabs">
					{#each allDimensions as dim}
						<button
							type="button"
							class="tab-btn"
							class:active={activeDimension === dim.key}
							onclick={() => (activeDimension = dim.key)}
						>
							{dim.label}
						</button>
					{/each}
				</div>
			</div>
			<div class="chart-card">
				<MetricChart
					type="bar"
					title="NDCG@K comparison"
					data={getChartData(getVisibleRuns(data, activeDimension), data.optimal_variant, data.baseline_variant)}
					height={280}
				/>
			</div>
		</EvalSection>

		<!-- Detailed table -->
		<EvalSection
			title="Detailed Results"
			description="Full metrics for each variant"
		>
			<div class="table-wrapper">
				<table class="ablation-table">
					<thead>
						<tr>
							<th>Rank</th>
							<th>Variant</th>
							<th>Chunks</th>
							<th>NDCG@K</th>
							<th>Δ vs Baseline</th>
							<th>MRR</th>
							<th>HR@K</th>
							<th>Prec@K</th>
							<th>Latency</th>
						</tr>
					</thead>
					<tbody>
						{#each getVisibleRuns(data, activeDimension) as run, i}
							<tr class:optimal={run.variant === data?.optimal_variant} class:baseline={run.variant === data?.baseline_variant}>
								<td class="rank">{i + 1}</td>
								<td class="variant">
									{run.variant}
									{#if run.variant === data?.optimal_variant}
										<span class="badge optimal-badge">Optimal</span>
									{/if}
									{#if run.variant === data?.baseline_variant}
										<span class="badge baseline-badge">Baseline</span>
									{/if}
								</td>
								<td>{run.chunks_attempted ?? '—'}</td>
								<td class="metric">{run.ndcg_at_k?.toFixed(4) ?? '—'}</td>
								<td class="delta" class:positive={run.delta_ndcg != null && run.delta_ndcg > 0} class:negative={run.delta_ndcg != null && run.delta_ndcg < 0}>
									{deltaLabel(run.delta_ndcg)}
								</td>
								<td class="metric">{run.mrr?.toFixed(4) ?? '—'}</td>
								<td class="metric">{run.hit_rate_at_k?.toFixed(4) ?? '—'}</td>
								<td class="metric">{run.precision_at_k?.toFixed(4) ?? '—'}</td>
								<td>{run.latency_p50_ms ? run.latency_p50_ms + 'ms' : '—'}</td>
							</tr>
						{/each}
					</tbody>
				</table>
			</div>
		</EvalSection>
	{/if}
</div>

<style>
	.ablation-page {
		display: flex;
		flex-direction: column;
		gap: 1.25rem;
	}

	.page-header {
		margin-bottom: 0.5rem;
	}

	.page-header h1 {
		font-size: 1.5rem;
		margin: 0 0 0.25rem;
	}

	.subtitle {
		color: var(--muted-color);
		font-size: 0.9rem;
		margin: 0;
	}

	.summary-grid {
		display: grid;
		grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
		gap: 0.9rem;
	}

	.feature-findings-grid {
		display: grid;
		grid-template-columns: repeat(auto-fit, minmax(260px, 1fr));
		gap: 0.9rem;
	}

	.feature-finding-card {
		padding: 1rem;
		border: 1px solid var(--border-color);
		border-radius: 14px;
		background: linear-gradient(180deg, rgba(99, 102, 241, 0.04), rgba(255, 255, 255, 0.98));
	}

	.feature-finding-header {
		display: flex;
		justify-content: space-between;
		gap: 0.75rem;
		align-items: flex-start;
		margin-bottom: 0.75rem;
	}

	.feature-finding-header h3 {
		margin: 0;
		font-size: 1rem;
	}

	.feature-finding-header p {
		margin: 0.2rem 0 0;
		font-size: 0.82rem;
		color: var(--muted-color);
	}

	.feature-metrics {
		display: flex;
		flex-wrap: wrap;
		gap: 0.45rem;
		margin-bottom: 0.75rem;
	}

	.feature-metric-pill {
		padding: 0.35rem 0.55rem;
		border-radius: 999px;
		background: rgba(15, 23, 42, 0.06);
		font-size: 0.78rem;
		font-weight: 600;
	}

	.feature-verdict {
		margin: 0;
		font-size: 0.9rem;
		line-height: 1.5;
		color: var(--text-color);
	}

	.findings-grid {
		display: grid;
		grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
		gap: 0.75rem;
	}

	.finding-card {
		padding: 1rem;
		border: 1px solid var(--border-color);
		border-radius: 12px;
		background: white;
	}

	.finding-header {
		display: flex;
		align-items: center;
		gap: 0.5rem;
		margin-bottom: 0.5rem;
	}

	.finding-impact {
		font-size: 0.7rem;
		font-weight: 700;
		text-transform: uppercase;
		color: white;
		padding: 0.15rem 0.5rem;
		border-radius: 999px;
	}

	.finding-card p {
		margin: 0;
		font-size: 0.85rem;
		color: var(--muted-color);
		line-height: 1.5;
	}

	.chart-toolbar {
		display: flex;
		justify-content: space-between;
		align-items: center;
		margin-bottom: 0.75rem;
	}

	.dimension-tabs {
		display: flex;
		flex-wrap: wrap;
		gap: 0.4rem;
	}

	.tab-btn {
		padding: 0.4rem 0.75rem;
		border: 1px solid var(--border-color);
		border-radius: 999px;
		background: white;
		cursor: pointer;
		font-size: 0.8rem;
		transition: all 0.15s;
	}

	.tab-btn.active {
		background: var(--accent-color);
		color: white;
		border-color: var(--accent-color);
	}

	.chart-card {
		padding: 0.5rem;
		border: 1px solid var(--border-color);
		border-radius: 16px;
		background: var(--surface-subtle);
	}

	.table-wrapper {
		overflow-x: auto;
	}

	.ablation-table {
		width: 100%;
		border-collapse: collapse;
		font-size: 0.85rem;
	}

	.ablation-table th {
		text-align: left;
		padding: 0.6rem 0.75rem;
		border-bottom: 2px solid var(--border-color);
		font-weight: 600;
		color: var(--muted-color);
		font-size: 0.78rem;
		text-transform: uppercase;
		letter-spacing: 0.03em;
		white-space: nowrap;
	}

	.ablation-table td {
		padding: 0.6rem 0.75rem;
		border-bottom: 1px solid var(--border-color);
		white-space: nowrap;
	}

	.ablation-table tr:hover {
		background: var(--surface-subtle);
	}

	.ablation-table tr.optimal {
		background: #ecfdf5;
		border-left: 3px solid #10b981;
	}

	.ablation-table tr.baseline {
		background: #eef2ff;
	}

	.rank {
		font-weight: 700;
		color: var(--muted-color);
	}

	.variant {
		font-weight: 600;
	}

	.metric {
		font-variant-numeric: tabular-nums;
	}

	.delta {
		font-weight: 600;
		font-variant-numeric: tabular-nums;
	}

	.delta.positive {
		color: #059669;
	}

	.delta.negative {
		color: #dc2626;
	}

	.badge {
		font-size: 0.65rem;
		font-weight: 700;
		text-transform: uppercase;
		padding: 0.1rem 0.4rem;
		border-radius: 999px;
		margin-left: 0.4rem;
		vertical-align: middle;
	}

	.optimal-badge {
		background: #10b981;
		color: white;
	}

	.baseline-badge {
		background: #6366f1;
		color: white;
	}
</style>
