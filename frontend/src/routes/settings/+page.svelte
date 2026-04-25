<script lang="ts">
	import { onMount } from 'svelte';
	import AppShell from '$lib/components/AppShell.svelte';
	import EmptyState from '$lib/components/EmptyState.svelte';
	import LoadingSkeleton from '$lib/components/LoadingSkeleton.svelte';
	import { getConfig } from '$lib/utils/api';
	import type { RuntimeConfig } from '$lib/types';

	let loading = $state(true);
	let error = $state('');
	let config = $state<RuntimeConfig | null>(null);

	const searchModeLabels: Record<string, string> = {
		rrf_hybrid: 'Hybrid (RRF)',
		semantic_only: 'Semantic Only',
		bm25_only: 'BM25 Only'
	};

	function labelFor(val: boolean): string {
		return val ? 'Enabled' : 'Disabled';
	}
	function colorFor(val: boolean): string {
		return val ? '#059669' : '#6b7280';
	}

	onMount(async () => {
		try {
			config = await getConfig<RuntimeConfig>();
		} catch (e) {
			error = e instanceof Error ? e.message : 'Failed to load configuration';
		} finally {
			loading = false;
		}
	});
</script>

<svelte:head>
	<title>Settings</title>
</svelte:head>

<AppShell current="/settings">
	<div class="settings-page">
		<div class="page-header">
			<p class="eyebrow">Configuration</p>
			<h1>Runtime settings</h1>
			<p class="subtitle">Read-only snapshot of the active retrieval, ingestion, and LLM configuration.</p>
		</div>

		{#if loading}
			<LoadingSkeleton count={3} type="card" />
		{:else if error}
			<EmptyState title="Failed to load configuration" body={error} />
		{:else if !config}
			<EmptyState title="No configuration available" body="The backend did not return config data." />
		{:else}
			<div class="config-grid">
				<section class="config-card">
					<h2>Retrieval</h2>
					<dl class="kv-list">
						<div class="kv-row"><dt>Search mode</dt><dd>{searchModeLabels[config.retrieval.search_mode] ?? config.retrieval.search_mode}</dd></div>
						<div class="kv-row"><dt>Top K</dt><dd>{config.retrieval.top_k}</dd></div>
						<div class="kv-row"><dt>MMR lambda</dt><dd>{config.retrieval.mmr_lambda}</dd></div>
						<div class="kv-row"><dt>Overfetch multiplier</dt><dd>{config.retrieval.overfetch_multiplier}</dd></div>
						<div class="kv-row"><dt>Max chunks / source page</dt><dd>{config.retrieval.max_chunks_per_source_page}</dd></div>
						<div class="kv-row"><dt>Max chunks / source</dt><dd>{config.retrieval.max_chunks_per_source}</dd></div>
					</dl>
				</section>

				<section class="config-card">
					<h2>Feature Toggles</h2>
					<dl class="kv-list">
						<div class="kv-row"><dt>Diversification (MMR)</dt><dd style="color:{colorFor(config.retrieval.enable_diversification)}">{labelFor(config.retrieval.enable_diversification)}</dd></div>
						<div class="kv-row"><dt>Reranking</dt><dd style="color:{colorFor(config.retrieval.enable_reranking)}">{labelFor(config.retrieval.enable_reranking)}</dd></div>
						{#if config.retrieval.enable_reranking}
							<div class="kv-row"><dt>Reranking mode</dt><dd>{config.retrieval.reranking_mode}</dd></div>
						{/if}
						<div class="kv-row"><dt>HyDE</dt><dd style="color:{colorFor(config.retrieval.enable_hyde)}">{labelFor(config.retrieval.enable_hyde)}</dd></div>
						{#if config.retrieval.enable_hyde}
							<div class="kv-row"><dt>HyDE max length</dt><dd>{config.retrieval.hyde_max_length}</dd></div>
						{/if}
						<div class="kv-row"><dt>HyPE</dt><dd style="color:{colorFor(config.retrieval.enable_hype)}">{labelFor(config.retrieval.enable_hype)}</dd></div>
						<div class="kv-row"><dt>Medical expansion</dt><dd style="color:{colorFor(config.retrieval.enable_medical_expansion)}">{labelFor(config.retrieval.enable_medical_expansion)}</dd></div>
						{#if config.retrieval.enable_medical_expansion}
							<div class="kv-row"><dt>Expansion provider</dt><dd>{config.retrieval.medical_expansion_provider}</dd></div>
						{/if}
						<div class="kv-row"><dt>Query understanding</dt><dd style="color:{colorFor(config.retrieval.enable_query_understanding)}">{labelFor(config.retrieval.enable_query_understanding)}</dd></div>
					</dl>
				</section>

				<section class="config-card">
					<h2>Ingestion</h2>
					<dl class="kv-list">
						<div class="kv-row"><dt>Structured chunking</dt><dd style="color:{colorFor(config.ingestion.structured_chunking_enabled)}">{labelFor(config.ingestion.structured_chunking_enabled)}</dd></div>
						<div class="kv-row"><dt>Page classification</dt><dd style="color:{colorFor(config.ingestion.page_classification_enabled)}">{labelFor(config.ingestion.page_classification_enabled)}</dd></div>
						<div class="kv-row"><dt>HTML extractor</dt><dd>{config.ingestion.html_extractor_strategy}</dd></div>
						<div class="kv-row"><dt>PDF extractor</dt><dd>{config.ingestion.pdf_extractor_strategy}</dd></div>
					</dl>
				</section>

				<section class="config-card">
					<h2>Enrichment</h2>
					<dl class="kv-list">
						<div class="kv-row"><dt>Keyword extraction</dt><dd style="color:{colorFor(config.enrichment.enable_keyword_extraction)}">{labelFor(config.enrichment.enable_keyword_extraction)}</dd></div>
						<div class="kv-row"><dt>Chunk summaries</dt><dd style="color:{colorFor(config.enrichment.enable_chunk_summaries)}">{labelFor(config.enrichment.enable_chunk_summaries)}</dd></div>
					</dl>
				</section>

				<section class="config-card">
					<h2>LLM</h2>
					<dl class="kv-list">
						<div class="kv-row"><dt>Provider</dt><dd>{config.llm.provider}</dd></div>
						<div class="kv-row"><dt>Model</dt><dd>{config.llm.model_name}</dd></div>
						<div class="kv-row"><dt>Embedding model</dt><dd>{config.llm.embedding_model}</dd></div>
					</dl>
				</section>

				{#if config.production_profile}
					<section class="config-card accent">
						<h2>Production Profile</h2>
						<p class="profile-name">{config.production_profile}</p>
					</section>
				{/if}
			</div>
		{/if}
	</div>
</AppShell>

<style>
	.settings-page {
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

	.config-grid {
		display: grid;
		grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
		gap: 1rem;
	}

	.config-card {
		padding: 1rem;
		border: 1px solid var(--border-color);
		border-radius: 18px;
		background: white;
	}

	.config-card.accent {
		border-color: #6366f1;
		background: #eef2ff;
	}

	.config-card h2 {
		font-size: 1rem;
		margin: 0 0 0.75rem;
		color: var(--text-color);
	}

	.kv-list {
		display: grid;
		gap: 0.4rem;
		margin: 0;
	}

	.kv-row {
		display: flex;
		justify-content: space-between;
		align-items: center;
		padding: 0.35rem 0;
		border-bottom: 1px solid var(--surface-subtle);
		font-size: 0.88rem;
	}

	.kv-row:last-child {
		border-bottom: none;
	}

	dt {
		color: var(--muted-color);
		font-weight: 500;
	}

	dd {
		margin: 0;
		font-weight: 600;
		color: var(--text-color);
	}

	.profile-name {
		margin: 0;
		font-size: 1.1rem;
		font-weight: 700;
		color: #4338ca;
	}
</style>
