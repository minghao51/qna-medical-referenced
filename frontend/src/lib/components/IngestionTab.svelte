<script lang="ts">
	import EvalSection from '$lib/components/EvalSection.svelte';
	import MetricTile from '$lib/components/MetricTile.svelte';
	import EmptyState from '$lib/components/EmptyState.svelte';
	import QualityDistributionChart from '$lib/components/QualityDistributionChart.svelte';
	import SourceDistributionChart from '$lib/components/SourceDistributionChart.svelte';
	import StrategyCard from '$lib/components/StrategyCard.svelte';
	import { stageNames } from '$lib/utils/metric-definitions';
	import { formatPercent } from '$lib/utils/eval';
	import type { StepFinding, StepMetrics, EvaluationResponse } from '$lib/types';

	type StageSummaryMetric = {
		label: string;
		value: string;
		warning?: boolean;
	};

	type StageCard = {
		stage: string;
		title: string;
		metrics: StageSummaryMetric[];
		findings: StepFinding[];
		pageTypes?: Array<[string, number]>;
		sourceDistribution?: Record<string, number>;
		qualityHistogram?: { high: number; medium: number; low: number };
	};

	type Props = {
		data: EvaluationResponse;
	};

	let { data }: Props = $props();

	let searchQuery = $state('');
	let selectedStages = $state<string[]>(['L1', 'L2', 'L3', 'L4', 'L5']);
	const allStages = ['L1', 'L2', 'L3', 'L4', 'L5'];

	function metricRow(label: string, value: string, warning = false): StageSummaryMetric {
		return { label, value, warning };
	}

	function getNumber(aggregate: Record<string, unknown>, key: string): number | undefined {
		const value = aggregate[key];
		return typeof value === 'number' ? value : undefined;
	}

	function getBoolean(aggregate: Record<string, unknown>, key: string): boolean | undefined {
		const value = aggregate[key];
		return typeof value === 'boolean' ? value : undefined;
	}

	function buildStageCard(stage: string, metrics: StepMetrics): StageCard {
		const aggregate = metrics.aggregate;
		const title = stageNames[stage.toUpperCase()] || stage.toUpperCase();

		if (stage === 'l1') {
			return {
				stage,
				title,
				findings: metrics.findings,
				pageTypes: Object.entries(
					(aggregate.page_classification_distribution as Record<string, number> | undefined) ?? {}
				),
				metrics: [
					metricRow('Pairs Evaluated', String(getNumber(aggregate, 'pairs_evaluated') ?? 0)),
					metricRow('Content Density', formatPercent(getNumber(aggregate, 'content_density_mean') ?? 0)),
					metricRow(
						'Boilerplate Ratio',
						formatPercent(getNumber(aggregate, 'boilerplate_ratio_mean') ?? 0),
						(getNumber(aggregate, 'boilerplate_ratio_mean') ?? 0) > 0.1
					),
					metricRow(
						'Heading Preservation',
						formatPercent(getNumber(aggregate, 'heading_preservation_rate_mean') ?? 0)
					),
					metricRow(
						'Table Preservation',
						formatPercent(getNumber(aggregate, 'table_preservation_rate_mean') ?? 0)
					)
				]
			};
		}

		if (stage === 'l2') {
			return {
				stage,
				title,
				findings: metrics.findings,
				metrics: [
					metricRow('PDF Files', String(getNumber(aggregate, 'pdf_file_count') ?? 0)),
					metricRow(
						'Extractor Fallback Rate',
						formatPercent(getNumber(aggregate, 'extractor_fallback_rate') ?? 0)
					),
					metricRow(
						'Low Confidence Rate',
						formatPercent(getNumber(aggregate, 'low_confidence_page_rate') ?? 0)
					),
					metricRow(
						'OCR Required Rate',
						formatPercent(getNumber(aggregate, 'ocr_required_rate') ?? 0)
					),
					metricRow(
						'Coverage',
						formatPercent(getNumber(aggregate, 'page_extraction_coverage') ?? 0)
					)
				]
			};
		}

		if (stage === 'l3') {
			return {
				stage,
				title,
				findings: metrics.findings,
				qualityHistogram:
					(aggregate.chunk_quality_histogram as { high: number; medium: number; low: number } | undefined) ??
					undefined,
				metrics: [
					metricRow('Documents', String(getNumber(aggregate, 'document_count') ?? 0)),
					metricRow('Chunks', String(getNumber(aggregate, 'chunk_count') ?? 0)),
					metricRow(
						'Section Integrity',
						formatPercent(getNumber(aggregate, 'section_integrity_rate') ?? 0)
					),
					metricRow(
						'Low Quality Filtered',
						formatPercent(getNumber(aggregate, 'low_quality_chunk_exclusion_rate') ?? 0)
					),
					metricRow(
						'Boundary Cut Rate',
						formatPercent(getNumber(aggregate, 'boundary_cut_rate') ?? 0)
					)
				]
			};
		}

		if (stage === 'l4') {
			return {
				stage,
				title,
				findings: metrics.findings,
				metrics: [
					metricRow('CSV Exists', getBoolean(aggregate, 'csv_exists') ? 'Yes' : 'No'),
					metricRow('Row Count', String(getNumber(aggregate, 'row_count') ?? 0)),
					metricRow(
						'Completeness Rate',
						formatPercent(getNumber(aggregate, 'row_completeness_rate') ?? 0)
					)
				]
			};
		}

		return {
			stage,
			title,
			findings: metrics.findings,
			sourceDistribution:
				(aggregate.source_distribution as Record<string, number> | undefined) ?? undefined,
			metrics: [
				metricRow('Vector Count', String(getNumber(aggregate, 'ids_count') ?? 0)),
				metricRow('Embedding Dim', String(getNumber(aggregate, 'embedding_dim') ?? 0)),
				metricRow(
					'Dims Consistent',
					getBoolean(aggregate, 'embedding_dim_consistent') ? 'Yes' : 'No'
				),
				metricRow(
					'Short Content Rate',
					formatPercent(getNumber(aggregate, 'short_content_rate') ?? 0),
					(getNumber(aggregate, 'short_content_rate') ?? 0) > 0.1
				)
			]
		};
	}

	const stageCards = $derived(
		Object.entries(data.step_metrics ?? {})
			.filter(([stage]) => selectedStages.includes(stage.toUpperCase()))
			.map(([stage, metrics]) => buildStageCard(stage, metrics))
			.filter((card) =>
				searchQuery.trim()
					? card.metrics.some((metric) =>
							metric.label.toLowerCase().includes(searchQuery.trim().toLowerCase())
						)
					: true
			)
	);

	const criticalFindings = $derived(
		stageCards.flatMap((card) =>
			card.findings.map((finding) => ({
				...finding,
				stage: card.stage.toUpperCase()
			}))
		)
	);
</script>

<div class="ingestion-tab" id="panel-ingestion" role="tabpanel" aria-labelledby="tab-ingestion">
	{#if data.experiment_config?.ingestion}
		<StrategyCard title="Ingestion strategy" ingestion={data.experiment_config.ingestion} />
	{/if}

	<EvalSection
		title="Ingestion health"
		description="Stage health first, with details kept inside the cards below."
	>
		<div class="summary-grid">
			<MetricTile label="Stages in view" value={String(stageCards.length)} />
			<MetricTile label="Critical findings" value={String(criticalFindings.length)} highlight={criticalFindings.length > 0} />
			<MetricTile label="Chunk stage" value={stageCards.some((card) => card.stage === 'l3') ? 'Included' : 'Hidden'} quiet />
		</div>

		<div class="filters-row">
			<input
				type="text"
				placeholder="Filter metrics"
				bind:value={searchQuery}
				class="search-input"
			/>
			<div class="stage-filters">
				{#each allStages as stage}
					<button
						type="button"
						class="stage-filter-btn"
						class:active={selectedStages.includes(stage)}
						onclick={() =>
							(selectedStages = selectedStages.includes(stage)
								? selectedStages.filter((value) => value !== stage)
								: [...selectedStages, stage])}
					>
						{stage}
					</button>
				{/each}
			</div>
		</div>
	</EvalSection>

	{#if stageCards.length > 0}
		<div class="steps-grid">
			{#each stageCards as card (card.stage)}
				<section class="step-card">
					<div class="step-header">
						<div>
							<h3 class="stage-name">{card.title}</h3>
							<p>{card.findings.length > 0 ? `${card.findings.length} issue(s) flagged` : 'No critical findings.'}</p>
						</div>
						{#if card.findings.length > 0}
							<span class="finding-badge" class:error={card.findings.some((finding) => finding.severity === 'error')}>
								{card.findings.length} issue(s)
							</span>
						{/if}
					</div>

					<div class="step-content">
						{#each card.metrics as metric}
							<div class="metric-row">
								<span>{metric.label}</span>
								<span class:warning={metric.warning}>{metric.value}</span>
							</div>
						{/each}

						{#if card.stage === 'l3' && card.qualityHistogram}
							<div class="metric-row">
								<span>Quality Distribution</span>
							</div>
							<QualityDistributionChart
								high={card.qualityHistogram.high}
								medium={card.qualityHistogram.medium}
								low={card.qualityHistogram.low}
							/>
						{/if}

						{#if card.pageTypes && card.pageTypes.length > 0}
							<div class="metric-row">
								<span>Page Types</span>
								<span class="page-types">
									{#each card.pageTypes as [type, count]}
										<span class="page-type-badge">{type}: {count}</span>
									{/each}
								</span>
							</div>
						{/if}

						{#if card.sourceDistribution}
							<SourceDistributionChart distribution={card.sourceDistribution} title="Source Distribution" height={180} />
						{/if}
					</div>

					{#if card.findings.length > 0}
						<div class="findings">
							{#each card.findings as finding}
								<p class="finding-item {finding.severity}">{finding.message}</p>
							{/each}
						</div>
					{/if}
				</section>
			{/each}
		</div>
	{:else}
		<EmptyState title="No ingestion metrics in view" body="Adjust the stage filters or run an evaluation with ingestion metrics." />
	{/if}
</div>

<style>
	.ingestion-tab {
		display: flex;
		flex-direction: column;
		gap: 1rem;
	}

	.summary-grid,
	.steps-grid {
		display: grid;
		grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
		gap: 1rem;
	}

	.filters-row {
		display: flex;
		flex-wrap: wrap;
		gap: 0.75rem;
		align-items: center;
	}

	.search-input {
		min-width: 220px;
		padding: 0.65rem 0.8rem;
		border: 1px solid var(--border-color);
		border-radius: 12px;
		background: white;
	}

	.stage-filters {
		display: flex;
		flex-wrap: wrap;
		gap: 0.4rem;
	}

	.stage-filter-btn {
		padding: 0.45rem 0.8rem;
		border: 1px solid var(--border-color);
		border-radius: 999px;
		background: white;
		cursor: pointer;
	}

	.stage-filter-btn.active {
		background: var(--surface-strong);
		border-color: var(--accent-soft);
	}

	.step-card {
		border: 1px solid var(--border-color);
		border-radius: 18px;
		background: white;
		overflow: hidden;
	}

	.step-header {
		display: flex;
		justify-content: space-between;
		gap: 1rem;
		padding: 1rem 1rem 0.85rem;
		border-bottom: 1px solid var(--border-color);
	}

	.stage-name {
		margin: 0;
		font-size: 1rem;
	}

	.step-header p {
		margin: 0.25rem 0 0;
		color: var(--muted-color);
		font-size: 0.9rem;
	}

	.finding-badge {
		align-self: flex-start;
		padding: 0.25rem 0.55rem;
		border-radius: 999px;
		background: #fff0d8;
		color: #9a5a04;
		font-size: 0.78rem;
		font-weight: 700;
	}

	.finding-badge.error {
		background: #fde2e2;
		color: #b42318;
	}

	.step-content {
		padding: 0.9rem 1rem 1rem;
	}

	.metric-row {
		display: flex;
		justify-content: space-between;
		gap: 0.75rem;
		padding: 0.4rem 0;
		border-bottom: 1px solid #eef1f4;
		flex-wrap: wrap;
	}

	.metric-row:last-child {
		border-bottom: none;
	}

	.metric-row span:first-child {
		color: var(--muted-color);
	}

	.metric-row span:last-child {
		font-weight: 600;
	}

	.warning {
		color: #b54708;
	}

	.findings {
		padding: 0.9rem 1rem 1rem;
		background: #fff9ef;
		border-top: 1px solid #f2dfbc;
	}

	.finding-item {
		margin: 0.25rem 0 0;
		font-size: 0.9rem;
	}

	.finding-item.error {
		color: #b42318;
	}

	.finding-item.warning {
		color: #9a5a04;
	}

	.page-types {
		display: flex;
		flex-wrap: wrap;
		gap: 0.3rem;
	}

	.page-type-badge {
		padding: 0.2rem 0.45rem;
		border-radius: 999px;
		background: var(--surface-subtle);
		font-size: 0.78rem;
	}
</style>
