<script lang="ts">
	import EvalSection from '$lib/components/EvalSection.svelte';
	import EmptyState from '$lib/components/EmptyState.svelte';
	import MetricTile from '$lib/components/MetricTile.svelte';
	import SourceDistributionChart from '$lib/components/SourceDistributionChart.svelte';
	import { formatDecimal, formatPercent } from '$lib/utils/eval';
	import type { EvaluationResponse } from '$lib/types';

	type Props = {
		data: EvaluationResponse;
		onDrillDown?: (stage: string, metricName: string, currentValue: number) => void;
	};

	let { data, onDrillDown }: Props = $props();

	const l6 = $derived(data.summary?.l6_answer_quality_metrics);
	const failedThresholds = $derived(data.failed_thresholds ?? []);
	const sourceDistribution = $derived(
		(data.step_metrics?.l5?.aggregate.source_distribution as Record<string, number> | undefined) ?? undefined
	);

	function handleDrillDown(metricName: string, currentValue: number) {
		onDrillDown?.('l6', metricName, currentValue);
	}
</script>

<div class="quality-tab" id="panel-quality" role="tabpanel" aria-labelledby="tab-quality">
	{#if failedThresholds.length > 0}
		<EvalSection
			title="Threshold Failures"
			description="Only failing checks are shown here so the review starts with real issues."
		>
			<div class="threshold-list">
				{#each failedThresholds as failure}
					<article class="threshold-card">
						<strong>{failure.metric || failure.message || 'Threshold check'}</strong>
						<p>
							Observed {String(failure.value)} against {failure.threshold_op} {failure.threshold_value}
						</p>
					</article>
				{/each}
			</div>
		</EvalSection>
	{/if}

	{#if l6 && l6.status !== 'skipped'}
		<EvalSection
			title="DeepEval answer quality"
			description="A concise scorecard for answer judgment quality."
		>
			<div class="metrics-grid">
				<MetricTile label="Status" value={l6.status} quiet />
				<MetricTile label="Scored Queries" value={String(l6.query_count_scored ?? l6.query_count ?? 'N/A')} />
				<MetricTile
					label="Metric Error Rate"
					value={l6.metric_error_rate != null ? formatPercent(l6.metric_error_rate) : 'N/A'}
				/>
			</div>

			<div class="metrics-grid">
				<MetricTile
					label="Answer Relevancy"
					value={formatDecimal(l6.answer_relevancy?.mean)}
					onclick={() => handleDrillDown('answer_relevancy', l6.answer_relevancy?.mean ?? 0)}
				/>
				<MetricTile
					label="Faithfulness"
					value={formatDecimal(l6.faithfulness?.mean)}
					onclick={() => handleDrillDown('faithfulness', l6.faithfulness?.mean ?? 0)}
				/>
				<MetricTile
					label="Factual Accuracy"
					value={formatDecimal(l6.factual_accuracy?.mean)}
					onclick={() => handleDrillDown('factual_accuracy', l6.factual_accuracy?.mean ?? 0)}
				/>
				<MetricTile
					label="Completeness"
					value={formatDecimal(l6.completeness?.mean)}
					onclick={() => handleDrillDown('completeness', l6.completeness?.mean ?? 0)}
				/>
				<MetricTile
					label="Clinical Relevance"
					value={formatDecimal(l6.clinical_relevance?.mean)}
					onclick={() => handleDrillDown('clinical_relevance', l6.clinical_relevance?.mean ?? 0)}
				/>
				<MetricTile
					label="Clarity"
					value={formatDecimal(l6.clarity?.mean)}
					onclick={() => handleDrillDown('clarity', l6.clarity?.mean ?? 0)}
				/>
			</div>
		</EvalSection>
	{/if}

	{#if sourceDistribution}
		<EvalSection
			title="Supporting data quality"
			description="A single supporting view of what the index currently contains."
		>
			<div class="chart-wrap">
				<SourceDistributionChart distribution={sourceDistribution} title="Source Distribution" height={220} />
			</div>
		</EvalSection>
	{/if}

	{#if (!l6 || l6.status === 'skipped') && failedThresholds.length === 0 && !sourceDistribution}
		<EmptyState title="No quality metrics available" body="Run a full evaluation with L6 enabled to see quality metrics." />
	{/if}
</div>

<style>
	.quality-tab {
		display: flex;
		flex-direction: column;
		gap: 1rem;
	}

	.metrics-grid,
	.threshold-list {
		display: grid;
		grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
		gap: 0.9rem;
	}

	.threshold-card {
		padding: 1rem;
		border-radius: 14px;
		background: #fff7ed;
		border: 1px solid #f3dcc0;
	}

	.threshold-card p {
		margin: 0.35rem 0 0;
		color: #9a5a04;
		font-size: 0.9rem;
	}

	.chart-wrap {
		max-width: 460px;
	}
</style>
