<script lang="ts">
	import { onMount } from 'svelte';
	import AppShell from '$lib/components/AppShell.svelte';
	import EmptyState from '$lib/components/EmptyState.svelte';
	import LoadingSkeleton from '$lib/components/LoadingSkeleton.svelte';
	import MetricChart from '$lib/components/MetricChart.svelte';
	import MetricTile from '$lib/components/MetricTile.svelte';
	import EvalSection from '$lib/components/EvalSection.svelte';
	import { getExperiments, getExperimentResults, getExperimentConfig } from '$lib/utils/api';
	import { calculateMetricDelta, metricNumber } from '$lib/utils/eval';
	import { primaryMetricKey } from '$lib/utils/research';
	import type {
		ExperimentListResponse,
		ExperimentReport,
		ExperimentConfigSummary,
		ExperimentVariantResult,
		ParsedExperimentConfig
	} from '$lib/types';

	let loading = $state(true);
	let error = $state('');
	let listData = $state<ExperimentListResponse | null>(null);
	let selectedExperimentId = $state('');
	let report = $state<ExperimentReport | null>(null);
	let parsedConfig = $state<ParsedExperimentConfig | null>(null);
	let reportLoading = $state(false);
	let reportError = $state('');

	const configNameCounts = $derived(
		(listData?.configs ?? []).reduce<Record<string, number>>((counts, config) => {
			counts[config.name] = (counts[config.name] ?? 0) + 1;
			return counts;
		}, {})
	);

	function fmtNum(value: unknown): string {
		return typeof value === 'number' && Number.isFinite(value) ? value.toFixed(4) : '—';
	}

	function getChartData(
		baseline: ExperimentVariantResult,
		variants: ExperimentVariantResult[],
		metricKey: string
	) {
		const all = [baseline, ...variants];
		return {
			labels: all.map((v) => v.name),
			datasets: [
				{
					label: metricKey,
					data: all.map((v) => metricNumber(
						(v.metrics as Record<string, unknown>)[metricKey], metricKey
					)),
					backgroundColor: '#006b61',
					borderRadius: 6
				}
			]
		};
	}

	function allMetrics(baseline: ExperimentVariantResult, variants: ExperimentVariantResult[]): string[] {
		const keys = new Set<string>();
		for (const v of [baseline, ...variants]) {
			const m = v.metrics as Record<string, unknown>;
			for (const k of Object.keys(m)) {
				if (typeof m[k] === 'number' && Number.isFinite(m[k])
					&& !k.startsWith('by_') && !k.startsWith('retrieval_')) {
					keys.add(k);
				}
			}
		}
		return Array.from(keys).sort();
	}

	async function selectExperiment(summary: ExperimentConfigSummary) {
		selectedExperimentId = summary.experiment_id;
		report = null;
		parsedConfig = null;
		reportLoading = true;
		reportError = '';
		// Follow only an explicit server-declared config/report association.
		const reportId = listData?.reports.find((item) =>
			item.config_ref === summary.experiment_id && item.availability === 'available'
		)?.report_id ?? summary.experiment_id;

		try {
			const [reportRes, configRes] = await Promise.allSettled([
				getExperimentResults<ExperimentReport>(reportId),
				getExperimentConfig<ParsedExperimentConfig>(summary.experiment_id)
			]);

			if (reportRes.status === 'fulfilled') {
				report = reportRes.value;
			} else {
				reportError = 'No results report found for this experiment.';
			}

			if (configRes.status === 'fulfilled') {
				parsedConfig = configRes.value;
			}
		} catch (e) {
			reportError = e instanceof Error ? e.message : 'Failed to load experiment data';
		} finally {
			reportLoading = false;
		}
	}

	onMount(async () => {
		try {
			listData = await getExperiments<ExperimentListResponse>();
		} catch (e) {
			error = e instanceof Error ? e.message : 'Failed to load experiments';
		} finally {
			loading = false;
		}
	});
</script>

<svelte:head>
	<title>Experiments</title>
</svelte:head>

<AppShell current="/experiments">
	<div class="experiments-page">
		<div class="page-header">
			<p class="eyebrow">Research</p>
			<h1>Experiments</h1>
			<p class="subtitle">Browse experiment configs and compare variant results.</p>
		</div>

		{#if loading}
			<LoadingSkeleton count={3} type="card" />
		{:else if error}
			<EmptyState title="Failed to load experiments" body={error} />
		{:else if !listData || listData.configs.length === 0}
			<EmptyState title="No experiments found" body="Place YAML configs in experiments/ to populate this view." />
		{:else}
			<div class="two-col">
				<aside class="sidebar">
					<h3>Configs</h3>
					{#each listData.configs as cfg}
						<button
							type="button"
							class="experiment-btn"
							class:active={selectedExperimentId === cfg.experiment_id}
							onclick={() => selectExperiment(cfg)}
						>
							<span class="exp-name">{cfg.name}</span>
							<span class="exp-meta">
								{cfg.variant_count} variant{cfg.variant_count !== 1 ? 's' : ''}
								{#if configNameCounts[cfg.name] > 1}
									· {cfg.experiment_id}
								{/if}
							</span>
							{#if cfg.has_results}
								<span class="has-results-badge">Has results</span>
							{/if}
						</button>
					{/each}

					{#if listData.reports.length > 0}
						<h3 class="mt">Reports</h3>
						{#each listData.reports as rpt}
							<div class="report-item">
								<span class="rpt-name">{rpt.experiment_name}</span>
								<span class="rpt-meta">
									{#if rpt.any_target_met !== null}
										<span class:met={rpt.any_target_met} class:unmet={!rpt.any_target_met}>
											{rpt.any_target_met ? 'Target met' : 'Target missed'}
										</span>
									{/if}
									{#if rpt.winner}
										Reported winner: <strong>{rpt.winner}</strong>
									{/if}
								</span>
							</div>
						{/each}
					{/if}
				</aside>

					<section class="detail" aria-label="Selected experiment">
						{#if !selectedExperimentId}
							<p class="placeholder">Select an experiment on the left to view details.</p>
					{:else if reportLoading}
						<LoadingSkeleton count={4} type="card" />
					{:else}
						{#if reportError}
							<div class="notice">{reportError}</div>
						{/if}

						{#if parsedConfig}
							<EvalSection title="Configuration" description="Parsed experiment YAML">
								<div class="config-summary-grid">
									{#each Object.entries(parsedConfig.retrieval ?? {}) as [key, val]}
										<div class="kv-mini">
											<span class="kv-key">{key}</span>
											<span class="kv-val">{typeof val === 'object' ? JSON.stringify(val) : String(val)}</span>
										</div>
									{/each}
								</div>
							</EvalSection>
						{/if}

						{#if report}
							<div class="summary-grid">
								<MetricTile label="Primary metric" value={report.primary_metric} />
								<MetricTile label="Target improvement" value={`+${(report.target_improvement * 100).toFixed(0)}%`} />
								<MetricTile label="Reported winner (historical)" value={report.winner?.name ?? '—'} quiet={false} />
								<MetricTile label="Target status (reported)" value={report.any_target_met ? 'Met' : 'Not met'} quiet={true} />
							</div>
							<p class="archive-note">
								Archived report data. A reported winner is not a current eligibility or promotion
								decision; measurements may be incomplete.
							</p>

							{@const metricKey = primaryMetricKey(report.primary_metric)}
							<EvalSection title="Variant Comparison" description="Archived primary metric across variants">
								<div class="chart-card">
									{#if metricKey}
										<MetricChart
											type="bar"
											title={metricKey}
											data={getChartData(report.baseline, report.variants, metricKey)}
											height={220}
										/>
									{:else}
										<p class="archive-note">Unsupported primary metric: {report.primary_metric}</p>
									{/if}
								</div>
							</EvalSection>

							{@const metrics = allMetrics(report.baseline, report.variants)}
							<EvalSection title="Detailed Metrics" description="All metrics across baseline and variants">
								<div class="table-wrap">
									<table class="metrics-table">
										<thead>
											<tr>
												<th>Metric</th>
												<th>Baseline</th>
												{#each report.variants as v}
													<th>{v.name}</th>
												{/each}
											</tr>
										</thead>
										<tbody>
											{#each metrics as key}
												{@const baseRaw = (report.baseline.metrics as Record<string, unknown>)[key]}
												<tr>
													<td class="metric-label">{key}</td>
													<td>{fmtNum(baseRaw)}</td>
													{#each report.variants as v}
														{@const varRaw = (v.metrics as Record<string, unknown>)[key]}
														{@const delta = calculateMetricDelta(key, baseRaw, varRaw)}
														<td class:improved={delta.favorability === 'improved'} class:worsened={delta.favorability === 'worsened'}>
															{fmtNum(varRaw)}
															{#if delta.absolute !== null && delta.absolute !== 0}
																<span class="delta-tag">{delta.absolute_label} / {delta.relative_label}</span>
															{/if}
														</td>
													{/each}
												</tr>
											{/each}
										</tbody>
									</table>
								</div>
							</EvalSection>
						{/if}
					{/if}
				</section>
			</div>
		{/if}
	</div>
</AppShell>

<style>
	.experiments-page {
		display: flex;
		flex-direction: column;
		gap: 1rem;
	}

	.page-header {
		display: flex;
		flex-direction: column;
		gap: 0.25rem;
	}

	.eyebrow {
		font-size: 0.8rem;
		text-transform: uppercase;
		letter-spacing: 0.08em;
		color: var(--muted-color);
	}

	h1 {
		font-size: 2rem;
		line-height: 1.1;
		margin: 0;
	}

	.subtitle {
		max-width: 42rem;
		color: var(--muted-color);
	}

	.two-col {
		display: grid;
		grid-template-columns: 280px 1fr;
		gap: 1rem;
		align-items: start;
	}

	@media (max-width: 800px) {
		.two-col {
			grid-template-columns: 1fr;
		}
	}

	.sidebar {
		padding: 1rem;
		border: 1px solid var(--border-color);
		border-radius: 18px;
		background: white;
	}

	.sidebar h3 {
		font-size: 0.9rem;
		margin: 0 0 0.5rem;
		color: var(--muted-color);
		text-transform: uppercase;
		letter-spacing: 0.05em;
	}

	.sidebar h3.mt {
		margin-top: 1rem;
	}

	.experiment-btn {
		display: flex;
		flex-wrap: wrap;
		align-items: center;
		gap: 0.4rem;
		width: 100%;
		padding: 0.55rem 0.75rem;
		margin-bottom: 0.35rem;
		border: 1px solid var(--border-color);
		border-radius: 10px;
		background: white;
		cursor: pointer;
		text-align: left;
		transition: background 0.15s;
	}

	.experiment-btn:hover {
		background: var(--surface-subtle);
	}

	.experiment-btn.active {
		background: var(--surface-strong);
		border-color: var(--teal);
	}

	.exp-name {
		font-weight: 600;
		font-size: 0.9rem;
	}

	.exp-meta {
		font-size: 0.78rem;
		color: var(--muted-color);
	}

	.has-results-badge {
		font-size: 0.7rem;
		font-weight: 700;
		padding: 0.1rem 0.4rem;
		border-radius: 999px;
		background: #dcfce7;
		color: #15803d;
	}

	.report-item {
		padding: 0.4rem 0.75rem;
		margin-bottom: 0.25rem;
		border-radius: 8px;
		background: var(--surface-subtle);
		font-size: 0.85rem;
	}

	.rpt-name {
		font-weight: 600;
		display: block;
		overflow-wrap: anywhere;
	}

	.rpt-meta {
		font-size: 0.78rem;
		color: var(--muted-color);
	}

	.met {
		color: var(--success);
		font-weight: 600;
	}

	.unmet {
		color: #dc2626;
		font-weight: 600;
	}

	.detail {
		min-width: 0;
	}

	.placeholder {
		text-align: center;
		color: var(--muted-color);
		padding: 3rem 1rem;
		border: 1px dashed var(--border-color);
		border-radius: 18px;
	}

	.notice {
		padding: 0.75rem 1rem;
		border: 1px solid #f0c36d;
		background: #fff7e6;
		color: #7a4b00;
		border-radius: 12px;
		font-size: 0.9rem;
		margin-bottom: 1rem;
	}

	.summary-grid {
		display: grid;
		grid-template-columns: repeat(auto-fit, minmax(160px, 1fr));
		gap: 0.75rem;
	}

	.chart-card {
		padding: 0.5rem;
		border: 1px solid var(--border-color);
		border-radius: 16px;
		background: var(--surface-subtle);
	}

	.config-summary-grid {
		display: grid;
		grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
		gap: 0.4rem;
	}

	.kv-mini {
		display: flex;
		justify-content: space-between;
		padding: 0.25rem 0.5rem;
		border-radius: 6px;
		background: var(--surface-subtle);
		font-size: 0.82rem;
	}

	.kv-key {
		color: var(--muted-color);
		font-weight: 500;
	}

	.kv-val {
		font-weight: 600;
		color: var(--text-color);
		max-width: 180px;
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
	}

	.table-wrap {
		overflow-x: auto;
	}

	.metrics-table {
		width: 100%;
		border-collapse: collapse;
		font-size: 0.82rem;
	}

	.metrics-table th {
		text-align: left;
		padding: 0.5rem 0.65rem;
		border-bottom: 2px solid var(--border-color);
		font-weight: 600;
		color: var(--muted-color);
		font-size: 0.75rem;
		text-transform: uppercase;
		letter-spacing: 0.03em;
		white-space: nowrap;
	}

	.metrics-table td {
		padding: 0.45rem 0.65rem;
		border-bottom: 1px solid var(--border-color);
		white-space: nowrap;
		font-variant-numeric: tabular-nums;
	}

	.metrics-table tr:hover {
		background: var(--surface-subtle);
	}

	.metric-label {
		font-weight: 600;
		color: var(--text-color);
	}

	.improved {
		color: #046b5a;
	}

	.worsened {
		color: #a63f23;
	}

	.delta-tag {
		font-size: 0.7rem;
		margin-left: 0.3rem;
		opacity: 0.8;
	}

	.archive-note {
		max-width: 48rem;
		font-size: 0.86rem;
		color: var(--muted-color);
	}
</style>
