<script lang="ts">
	import EmptyState from '$lib/components/EmptyState.svelte';
	import EvalSection from '$lib/components/EvalSection.svelte';
	import MetricChart from '$lib/components/MetricChart.svelte';
	import LoadingSkeleton from '$lib/components/LoadingSkeleton.svelte';
	import MetricTile from '$lib/components/MetricTile.svelte';
	import {
		buildTrendDatasets,
		formatPercent,
		historyLabel,
		runMetricLabels,
		selectionKey,
		summarizeAblation
	} from '$lib/utils/eval';
	import type {
		AblationResponse,
		EvalTrendMetric,
		EvaluationHistoryResponse,
		EvaluationHistoryRun,
		EvaluationResponse
	} from '$lib/types';

	type Props = {
		historyData: EvaluationHistoryResponse | null;
		historyLoading: boolean;
		ablationData: AblationResponse | null;
		ablationLoading: boolean;
		selectedRunKey: string;
		data: EvaluationResponse;
		selectedTrendMetric: EvalTrendMetric;
		onTrendMetricChange: (metric: EvalTrendMetric) => void;
		onSelectRun: (runKey: string) => void;
		onRefreshHistory: () => void;
	};

	let {
		historyData,
		historyLoading,
		ablationData,
		ablationLoading,
		selectedRunKey,
		data,
		selectedTrendMetric,
		onTrendMetricChange,
		onSelectRun,
		onRefreshHistory
	}: Props = $props();

	let historyRunsExpanded = $state(false);
	let experimentFilter = $state('');

	const filteredRuns = $derived(
		(historyData?.runs ?? []).filter((run) => {
			if (!experimentFilter.trim()) return true;
			const haystack = [
				run.experiment_name,
				run.variant_name,
				run.run_dir,
				run.index_config_hash
			]
				.filter(Boolean)
				.join(' ')
				.toLowerCase();
			return haystack.includes(experimentFilter.trim().toLowerCase());
		})
	);

	function isSelected(run: EvaluationHistoryRun): boolean {
		return selectionKey(run) === selectedRunKey;
	}
</script>

<div class="trending-tab" id="panel-trending" role="tabpanel" aria-labelledby="tab-trending">
	{#if historyLoading}
		<EvalSection title="Historical trending" description="Loading recent evaluation history.">
			<LoadingSkeleton count={3} type="card" height="90px" />
		</EvalSection>
	{:else if historyData && historyData.runs.length > 0}
		<EvalSection
			title="Historical trending"
			description="Trend chart first, with the run list kept compact."
		>
			<div class="trend-toolbar">
				<div class="summary-grid">
					<MetricTile label="Total Runs" value={String(historyData.summary.total_runs)} quiet />
					<MetricTile label="Avg Hit Rate" value={formatPercent(historyData.summary.avg_hit_rate)} />
					<MetricTile label="Avg MRR" value={historyData.summary.avg_mrr.toFixed(3)} />
					<MetricTile label="Avg Latency" value={`${historyData.summary.avg_latency_p50.toFixed(0)}ms`} />
				</div>
				<div class="controls">
					<label>
						<span>Metric</span>
						<select
							value={selectedTrendMetric}
							onchange={(event) =>
								onTrendMetricChange(event.currentTarget.value as EvalTrendMetric)}
						>
							<option value="hit_rate">Hit Rate & MRR</option>
							<option value="mrr">MRR Focus</option>
							<option value="latency">Latency</option>
						</select>
					</label>
					<button type="button" class="action-btn" onclick={onRefreshHistory}>Reload History</button>
				</div>
			</div>

			<div class="chart-card">
				<MetricChart
					type={selectedTrendMetric === 'latency' ? 'bar' : 'line'}
					title="Evaluation trend"
					data={{
						labels: filteredRuns.map((run) => historyLabel(run)),
						datasets: buildTrendDatasets(filteredRuns, selectedTrendMetric)
					}}
					height={220}
				/>
			</div>

			<div class="run-list-head">
				<input
					type="text"
					class="search-input"
					placeholder="Filter by experiment, variant, or hash"
					bind:value={experimentFilter}
				/>
				<button
					type="button"
					class="action-btn"
					onclick={() => (historyRunsExpanded = !historyRunsExpanded)}
				>
					{historyRunsExpanded ? 'Hide run list' : `Show ${filteredRuns.length} runs`}
				</button>
			</div>

			{#if historyRunsExpanded}
				<div class="run-list">
					{#each filteredRuns as run}
						<button
							type="button"
							class="run-card"
							class:selected={isSelected(run)}
							onclick={() => onSelectRun(selectionKey(run))}
						>
							<div class="run-card-top">
								<strong>{historyLabel(run)}</strong>
								{#if isSelected(run)}
									<span class="selected-pill">Selected</span>
								{/if}
							</div>
							<p>{run.run_dir}</p>
							<div class="run-card-metrics">
								{#each runMetricLabels(run) as label}
									<span>{label}</span>
								{/each}
							</div>
						</button>
					{/each}
				</div>
			{/if}
		</EvalSection>
	{:else}
		<EmptyState title="No historical data available" body="Run more than one evaluation to unlock trending views." />
	{/if}

	{#if ablationLoading}
		<EvalSection title="Ablation study" description="Loading retrieval strategy comparison.">
			<LoadingSkeleton count={2} type="card" height="70px" />
		</EvalSection>
	{:else if ablationData?.ablation_runs.length}
		<EvalSection
			title="Ablation study"
			description="A compact comparison of retrieval strategies."
		>
			<div class="run-list">
				{#each ablationData.ablation_runs as run}
					<div class="run-card" class:selected={run.is_baseline}>
						<div class="run-card-top">
							<strong>{run.strategy}</strong>
							{#if run.is_baseline}
								<span class="selected-pill">Baseline</span>
							{/if}
						</div>
						<div class="run-card-metrics">
							{#each summarizeAblation(run) as label}
								<span>{label}</span>
							{/each}
						</div>
					</div>
				{/each}
			</div>
		</EvalSection>
	{/if}
</div>

<style>
	.trending-tab {
		display: flex;
		flex-direction: column;
		gap: 1rem;
	}

	.trend-toolbar {
		display: flex;
		flex-direction: column;
		gap: 1rem;
	}

	.summary-grid,
	.run-list {
		display: grid;
		grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
		gap: 0.9rem;
	}

	.controls,
	.run-list-head {
		display: flex;
		flex-wrap: wrap;
		gap: 0.75rem;
		align-items: end;
		justify-content: space-between;
	}

	label {
		display: flex;
		flex-direction: column;
		gap: 0.35rem;
		font-size: 0.9rem;
		color: var(--muted-color);
	}

	select,
	.search-input {
		padding: 0.65rem 0.8rem;
		border: 1px solid var(--border-color);
		border-radius: 12px;
		background: white;
	}

	.chart-card {
		padding: 0.5rem;
		border: 1px solid var(--border-color);
		border-radius: 16px;
		background: var(--surface-subtle);
	}

	.action-btn {
		padding: 0.65rem 0.95rem;
		border: 1px solid var(--border-color);
		border-radius: 999px;
		background: white;
		cursor: pointer;
	}

	.run-card {
		display: flex;
		flex-direction: column;
		gap: 0.5rem;
		padding: 1rem;
		border: 1px solid var(--border-color);
		border-radius: 16px;
		background: white;
		text-align: left;
	}

	.run-card.selected {
		background: var(--surface-strong);
		border-color: var(--accent-soft);
	}

	.run-card-top {
		display: flex;
		align-items: center;
		justify-content: space-between;
		gap: 0.5rem;
	}

	.run-card p {
		color: var(--muted-color);
		font-size: 0.85rem;
		word-break: break-word;
	}

	.run-card-metrics {
		display: flex;
		flex-wrap: wrap;
		gap: 0.4rem;
	}

	.run-card-metrics span,
	.selected-pill {
		padding: 0.2rem 0.45rem;
		border-radius: 999px;
		background: var(--surface-subtle);
		font-size: 0.78rem;
	}

	.selected-pill {
		background: white;
		font-weight: 700;
	}
</style>
