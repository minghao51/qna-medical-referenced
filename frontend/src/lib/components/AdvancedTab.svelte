<script lang="ts">
	import EvalSection from '$lib/components/EvalSection.svelte';
	import EmptyState from '$lib/components/EmptyState.svelte';
	import MetricTile from '$lib/components/MetricTile.svelte';
	import { formatDecimal, formatPercent } from '$lib/utils/eval';
	import type { EvaluationResponse, RetrievalMetrics } from '$lib/types';

	type Props = {
		data: EvaluationResponse;
	};

	let { data }: Props = $props();

	const m = $derived(data.retrieval_metrics);

	type CategoryBucket = {
		query_count?: number;
		hit_rate_at_k?: number;
		mrr?: number;
		source_hit_rate?: number;
		exact_chunk_hit_rate?: number;
		evidence_hit_rate?: number;
		duplicate_source_ratio_mean?: number;
	};

	function fmt(v: unknown, decimals = 3): string {
		if (typeof v !== 'number') return '—';
		return v < 1 ? v.toFixed(decimals) : v.toFixed(decimals);
	}

	function bucketEntries(bucket: Record<string, CategoryBucket>): [string, CategoryBucket][] {
		return Object.entries(bucket).sort(([a], [b]) => a.localeCompare(b));
	}
</script>

<div class="advanced-tab">
	{#if !m}
		<EmptyState title="No advanced metrics" body="Run an evaluation to populate advanced metrics." />
	{:else}
		{#if m.hyde_enabled && (m.hyde_hit_rate !== undefined || m.hyde_mrr !== undefined)}
			<EvalSection
				title="HyDE Metrics"
				description="Retrieval quality when HyDE (Hypothetical Document Embeddings) is active."
			>
				<div class="metrics-grid">
					<MetricTile label="HyDE Enabled" value={m.hyde_enabled ? 'Yes' : 'No'} />
					{#if m.hyde_queries_count !== undefined}
						<MetricTile label="HyDE Queries" value={String(m.hyde_queries_count)} quiet />
					{/if}
					{#if m.hyde_hit_rate !== undefined}
						<MetricTile label="HyDE Hit Rate" value={formatPercent(m.hyde_hit_rate)} highlight />
					{/if}
					{#if m.hyde_mrr !== undefined}
						<MetricTile label="HyDE MRR" value={formatDecimal(m.hyde_mrr, 3)} highlight />
					{/if}
					{#if m.hyde_source_hit_rate !== undefined}
						<MetricTile label="HyDE Source Hit" value={formatPercent(m.hyde_source_hit_rate)} />
					{/if}
				</div>
			</EvalSection>
		{/if}

		{#if m.topic_false_positive_rate !== undefined}
			<EvalSection
				title="Topic Analysis"
				description="Measures how often retrieval returns results for off-topic queries."
			>
				<div class="metrics-grid">
					<MetricTile
						label="Topic False Positive Rate"
						value={formatPercent(m.topic_false_positive_rate)}
						highlight
					/>
				</div>
			</EvalSection>
		{/if}

		{@const fullMetrics = data.retrieval_metrics as unknown as Record<string, unknown>}
		{#if fullMetrics && typeof fullMetrics.by_query_category === 'object' && fullMetrics.by_query_category !== null}
			<EvalSection
				title="By Query Category"
				description="Retrieval quality broken down by query type (anchor, adversarial, paraphrase)."
			>
				<div class="table-wrap">
					<table class="breakdown-table">
						<thead>
							<tr>
								<th>Category</th>
								<th>Queries</th>
								<th>Hit Rate</th>
								<th>MRR</th>
								<th>Source Hit</th>
								<th>Evidence Hit</th>
							</tr>
						</thead>
						<tbody>
							{#each bucketEntries(fullMetrics.by_query_category as Record<string, CategoryBucket>) as [cat, bucket]}
								<tr>
									<td class="cat-label">{cat}</td>
									<td>{bucket.query_count ?? '—'}</td>
									<td>{fmt(bucket.hit_rate_at_k)}</td>
									<td>{fmt(bucket.mrr)}</td>
									<td>{fmt(bucket.source_hit_rate)}</td>
									<td>{fmt(bucket.evidence_hit_rate)}</td>
								</tr>
							{/each}
						</tbody>
					</table>
				</div>
			</EvalSection>
		{/if}

		{#if fullMetrics && typeof fullMetrics.by_difficulty === 'object' && fullMetrics.by_difficulty !== null}
			<EvalSection
				title="By Difficulty"
				description="Retrieval quality by labeled difficulty."
			>
				<div class="table-wrap">
					<table class="breakdown-table">
						<thead>
							<tr>
								<th>Difficulty</th>
								<th>Queries</th>
								<th>Hit Rate</th>
								<th>MRR</th>
								<th>Source Hit</th>
								<th>Evidence Hit</th>
							</tr>
						</thead>
						<tbody>
							{#each bucketEntries(fullMetrics.by_difficulty as Record<string, CategoryBucket>) as [diff, bucket]}
								<tr>
									<td class="cat-label">{diff}</td>
									<td>{bucket.query_count ?? '—'}</td>
									<td>{fmt(bucket.hit_rate_at_k)}</td>
									<td>{fmt(bucket.mrr)}</td>
									<td>{fmt(bucket.source_hit_rate)}</td>
									<td>{fmt(bucket.evidence_hit_rate)}</td>
								</tr>
							{/each}
						</tbody>
					</table>
				</div>
			</EvalSection>
		{/if}

		{#if fullMetrics && typeof fullMetrics.contribution_analysis === 'object' && fullMetrics.contribution_analysis !== null}
			<EvalSection
				title="Contribution Analysis"
				description="How many hits were ranked by semantic, BM25, or fused scoring."
			>
				<div class="metrics-grid">
					{#each Object.entries(fullMetrics.contribution_analysis as Record<string, number>) as [key, val]}
						<MetricTile label={key.replace(/_/g, ' ')} value={String(val)} quiet />
					{/each}
				</div>
			</EvalSection>
		{/if}
	{/if}
</div>

<style>
	.advanced-tab {
		display: flex;
		flex-direction: column;
		gap: 1rem;
	}

	.metrics-grid {
		display: grid;
		grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
		gap: 0.9rem;
	}

	.table-wrap {
		overflow-x: auto;
	}

	.breakdown-table {
		width: 100%;
		border-collapse: collapse;
		font-size: 0.85rem;
	}

	.breakdown-table th {
		text-align: left;
		padding: 0.5rem 0.65rem;
		border-bottom: 2px solid var(--border-color);
		font-weight: 600;
		color: var(--muted-color);
		font-size: 0.78rem;
		text-transform: uppercase;
		letter-spacing: 0.03em;
		white-space: nowrap;
	}

	.breakdown-table td {
		padding: 0.45rem 0.65rem;
		border-bottom: 1px solid var(--border-color);
		font-variant-numeric: tabular-nums;
	}

	.breakdown-table tr:hover {
		background: var(--surface-subtle);
	}

	.cat-label {
		font-weight: 600;
		text-transform: capitalize;
	}
</style>
