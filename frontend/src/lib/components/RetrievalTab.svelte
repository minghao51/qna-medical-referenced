<script lang="ts">
	import EvalSection from '$lib/components/EvalSection.svelte';
	import EmptyState from '$lib/components/EmptyState.svelte';
	import MetricTile from '$lib/components/MetricTile.svelte';
	import StrategyCard from '$lib/components/StrategyCard.svelte';
	import { formatDecimal, formatPercent } from '$lib/utils/eval';
	import type { EvaluationResponse, RetrievalStrategyConfig } from '$lib/types';

	type Props = {
		data: EvaluationResponse;
		onDrillDown?: (stage: string, metricName: string, currentValue: number) => void;
	};

	let { data, onDrillDown }: Props = $props();

	function handleDrillDown(metricName: string, currentValue: number) {
		onDrillDown?.('l6', metricName, currentValue);
	}

	const metrics = $derived(data.retrieval_metrics);
</script>

<div class="retrieval-tab" id="panel-retrieval" role="tabpanel" aria-labelledby="tab-retrieval">
	{#if data.experiment_config?.retrieval}
		<StrategyCard
			title="Retrieval strategy"
			retrieval={data.experiment_config.retrieval as RetrievalStrategyConfig}
		/>
	{/if}

	{#if metrics}
		<EvalSection
			title="Core retrieval"
			description="Primary effectiveness and latency metrics for the current run."
		>
			<div class="metrics-grid">
				<MetricTile label="Query Count" value={String(metrics.query_count)} quiet />
				<MetricTile
					label="Hit Rate @k"
					value={formatPercent(metrics.hit_rate_at_k)}
					highlight
					onclick={() => handleDrillDown('hit_rate_at_k', metrics.hit_rate_at_k)}
				/>
				<MetricTile
					label="MRR"
					value={formatDecimal(metrics.mrr, 3)}
					highlight
					onclick={() => handleDrillDown('mrr', metrics.mrr)}
				/>
				<MetricTile label="Precision @k" value={formatPercent(metrics.precision_at_k)} />
				<MetricTile label="Recall @k" value={formatPercent(metrics.recall_at_k)} />
				<MetricTile label="nDCG @k" value={formatPercent(metrics.ndcg_at_k)} />
				<MetricTile label="Latency p50" value={formatDecimal(metrics.latency_p50_ms, 0, 'ms')} />
				<MetricTile label="Latency p95" value={formatDecimal(metrics.latency_p95_ms, 0, 'ms')} />
			</div>
		</EvalSection>

		{#if metrics.dedup_hit_rate_at_k !== undefined || metrics.unique_source_hit_rate_at_k !== undefined}
			<EvalSection
				title="Deduplication & Diversity"
				description="Secondary retrieval quality signals once duplicate-heavy results are removed."
			>
				<div class="metrics-grid">
					{#if metrics.dedup_hit_rate_at_k !== undefined}
						<MetricTile label="Dedup Hit Rate" value={formatPercent(metrics.dedup_hit_rate_at_k)} />
					{/if}
					{#if metrics.dedup_mrr !== undefined}
						<MetricTile label="Dedup MRR" value={formatDecimal(metrics.dedup_mrr, 3)} />
					{/if}
					{#if metrics.unique_source_hit_rate_at_k !== undefined}
						<MetricTile
							label="Unique Source Hit"
							value={formatPercent(metrics.unique_source_hit_rate_at_k)}
						/>
					{/if}
					{#if metrics.duplicate_source_ratio_mean !== undefined}
						<MetricTile
							label="Duplicate Source Ratio"
							value={formatPercent(metrics.duplicate_source_ratio_mean)}
						/>
					{/if}
				</div>
			</EvalSection>
		{/if}

		{#if metrics.hit_rate_at_k_high_conf !== undefined || metrics.exact_chunk_hit_rate_high_conf !== undefined}
			<EvalSection
				title="High-Confidence Subset"
				description="Performance after restricting evaluation to high-confidence labeled examples."
			>
				<div class="metrics-grid">
					{#if metrics.hit_rate_at_k_high_conf !== undefined}
						<MetricTile label="Hit Rate (High Conf)" value={formatPercent(metrics.hit_rate_at_k_high_conf)} highlight />
					{/if}
					{#if metrics.mrr_high_conf !== undefined}
						<MetricTile label="MRR (High Conf)" value={formatDecimal(metrics.mrr_high_conf, 3)} highlight />
					{/if}
					{#if metrics.exact_chunk_hit_rate_high_conf !== undefined}
						<MetricTile
							label="Exact Chunk (High Conf)"
							value={formatPercent(metrics.exact_chunk_hit_rate_high_conf)}
						/>
					{/if}
					{#if metrics.topic_false_positive_rate !== undefined}
						<MetricTile
							label="Topic False Positive"
							value={formatPercent(metrics.topic_false_positive_rate)}
						/>
					{/if}
				</div>
			</EvalSection>
		{/if}
	{:else}
		<EmptyState title="No retrieval metrics available" body="Run an evaluation to populate retrieval metrics." />
	{/if}
</div>

<style>
	.retrieval-tab {
		display: flex;
		flex-direction: column;
		gap: 1rem;
	}

	.metrics-grid {
		display: grid;
		grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
		gap: 0.9rem;
	}
</style>
