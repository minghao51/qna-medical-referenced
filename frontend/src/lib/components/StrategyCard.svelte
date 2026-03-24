<script lang="ts">
	import type { IngestionStrategyConfig, RetrievalStrategyConfig } from '$lib/types';

	type Props = {
		title?: string;
		ingestion?: IngestionStrategyConfig | null;
		retrieval?: RetrievalStrategyConfig | null;
	};

	let { title = 'Strategy configuration', ingestion, retrieval }: Props = $props();

	function formatChunkConfig(config: { chunk_size?: number; chunk_overlap?: number; min_chunk_size?: number } | undefined): string {
		if (!config) return 'N/A';
		return `${config.chunk_size ?? '?'} / ${config.chunk_overlap ?? '?'} / ${config.min_chunk_size ?? '?'} tokens`;
	}

	function searchModeLabel(mode: string | undefined): string {
		const labels: Record<string, string> = {
			rrf_hybrid: 'RRF hybrid',
			semantic_only: 'Semantic only',
			bm25_only: 'BM25 only'
		};
		return mode ? (labels[mode] ?? mode) : 'N/A';
	}

	const ingestionSummary = $derived(
		ingestion
			? [
					['PDF extractor', ingestion.pdf_extractor_strategy ?? 'pypdf_pdfplumber'],
					['HTML extractor', ingestion.html_extractor_strategy ?? 'trafilatura_bs'],
					[
						'Structured chunking',
						ingestion.structured_chunking_enabled ? 'Enabled' : 'Disabled'
					],
					[
						'HyPE',
						ingestion.enable_hype
							? `Enabled (${Math.round((ingestion.hype_sample_rate ?? 0) * 100)}%)`
							: 'Disabled'
					]
				]
			: []
	);

	const retrievalSummary = $derived(
		retrieval
			? [
					['Search mode', searchModeLabel(retrieval.search_mode)],
					['Top-K', String(retrieval.top_k ?? 5)],
					['HyDE', retrieval.enable_hyde ? `Enabled (${retrieval.hyde_max_length ?? 200})` : 'Disabled'],
					[
						'Diversification',
						retrieval.enable_diversification
							? `MMR λ=${retrieval.mmr_lambda ?? 0.75}`
							: 'Disabled'
					]
				]
			: []
	);
</script>

<section class="strategy-card">
	<div class="header">
		<h3>{title}</h3>
		<p>Selected defaults for this run.</p>
	</div>

	{#if ingestion}
		<div class="group">
			<h4>Ingestion</h4>
			<dl class="summary">
				{#each ingestionSummary as [label, value]}
					<div>
						<dt>{label}</dt>
						<dd>{value}</dd>
					</div>
				{/each}
			</dl>
			{#if ingestion.source_chunk_configs}
				<div class="chunk-list">
					{#each Object.entries(ingestion.source_chunk_configs) as [source, config]}
						<div class="chip">
							<strong>{source}</strong>
							<span>{formatChunkConfig(config)}</span>
						</div>
					{/each}
				</div>
			{/if}
		</div>
	{/if}

	{#if retrieval}
		<div class="group">
			<h4>Retrieval</h4>
			<dl class="summary">
				{#each retrievalSummary as [label, value]}
					<div>
						<dt>{label}</dt>
						<dd>{value}</dd>
					</div>
				{/each}
			</dl>
		</div>
	{/if}

	{#if !ingestion && !retrieval}
		<p class="empty">No strategy configuration available.</p>
	{/if}
</section>

<style>
	.strategy-card {
		padding: 1rem;
		border: 1px solid var(--border-color);
		border-radius: 16px;
		background: var(--surface-subtle);
	}

	.header h3 {
		margin: 0;
		font-size: 0.98rem;
	}

	.header p {
		margin: 0.35rem 0 0;
		font-size: 0.9rem;
		color: var(--muted-color);
	}

	.group + .group {
		margin-top: 1rem;
		padding-top: 1rem;
		border-top: 1px solid var(--border-color);
	}

	h4 {
		margin: 0 0 0.75rem;
		font-size: 0.8rem;
		text-transform: uppercase;
		letter-spacing: 0.08em;
		color: var(--muted-color);
	}

	.summary {
		display: grid;
		grid-template-columns: repeat(auto-fit, minmax(160px, 1fr));
		gap: 0.75rem;
	}

	.summary div {
		padding: 0.75rem;
		border-radius: 12px;
		background: white;
		border: 1px solid var(--border-color);
	}

	dt {
		font-size: 0.78rem;
		color: var(--muted-color);
	}

	dd {
		margin: 0.25rem 0 0;
		font-weight: 600;
	}

	.chunk-list {
		display: flex;
		flex-wrap: wrap;
		gap: 0.5rem;
		margin-top: 0.75rem;
	}

	.chip {
		display: flex;
		flex-direction: column;
		gap: 0.15rem;
		padding: 0.6rem 0.75rem;
		border-radius: 12px;
		background: white;
		border: 1px solid var(--border-color);
		font-size: 0.85rem;
	}

	.chip span,
	.empty {
		color: var(--muted-color);
	}
</style>
