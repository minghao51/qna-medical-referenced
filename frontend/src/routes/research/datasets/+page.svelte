<script lang="ts">
	import { onMount } from 'svelte';
	import AppShell from '$lib/components/AppShell.svelte';
	import EmptyState from '$lib/components/EmptyState.svelte';
	import LoadingSkeleton from '$lib/components/LoadingSkeleton.svelte';
	import ResearchNav from '$lib/components/ResearchNav.svelte';
	import { getResearchDatasets } from '$lib/utils/api';
	import type { ResearchCatalogEntry, ResearchCatalogResponse } from '$lib/types';

	type LoadState = 'loading' | 'available' | 'unauthorized' | 'error';

	let loadState = $state<LoadState>('loading');
	let errorMessage = $state('');
	let catalog = $state<ResearchCatalogResponse | null>(null);

	const entries = $derived(catalog?.datasets ?? []);
	const overlap = $derived(catalog?.overlap?.[0] ?? null);
	const reviewEntry = $derived(entries.find((entry) => entry.catalog_id === 'd11-review') ?? null);

	function isUnauthorized(message: string): boolean {
		return /401|x-api-key|missing .*key/i.test(message);
	}

	function count(value: number | null | undefined): string {
		return typeof value === 'number' && Number.isFinite(value)
			? value.toLocaleString('en-US')
			: 'N/A';
	}

	function quantity(entry: ResearchCatalogEntry): string {
		if (entry.kind === 'retrieval_index') return 'Live inventory reference';
		if (entry.record_count === null) return 'Count unavailable';
		const unit =
			entry.record_unit === 'question'
				? 'questions'
				: entry.record_unit === 'conversation'
					? 'conversations'
					: entry.record_unit === 'case'
						? 'cases'
						: entry.record_unit === 'row'
							? 'rows'
							: 'chunks';
		const turns = entry.turn_count !== null ? ` · ${count(entry.turn_count)} turns` : '';
		return `${count(entry.record_count)} ${unit}${turns}`;
	}

	function stateLabel(entry: ResearchCatalogEntry): string {
		if (entry.availability === 'inventory_reference') return 'Inventory reference';
		return entry.availability;
	}

	async function loadCatalog() {
		loadState = 'loading';
		try {
			catalog = await getResearchDatasets<ResearchCatalogResponse>();
			loadState = 'available';
		} catch (error) {
			const message = error instanceof Error ? error.message : 'The catalog is unavailable.';
			errorMessage = message;
			loadState = isUnauthorized(message) ? 'unauthorized' : 'error';
		}
	}

	onMount(() => {
		void loadCatalog();
	});
</script>

<svelte:head>
	<title>Datasets · Fieldnote</title>
</svelte:head>

<AppShell current="/research/datasets">
	<div class="datasets-page">
		<header class="page-header">
			<p class="eyebrow">Datasets / local inventory</p>
			<h1>What are we actually testing?</h1>
			<p class="lede">
				A catalog of distinct artifacts—not one grand total. Counts come from the current files;
				they do not prove the historical bytes used by an archived run.
			</p>
		</header>

		<ResearchNav current="/research/datasets" />

		{#if loadState === 'loading'}
			<div class="loading-panel" aria-busy="true">
				<LoadingSkeleton count={3} type="card" />
			</div>
		{:else if loadState === 'unauthorized'}
			<EmptyState
				title="Research access required"
				body="The dataset catalog needs the authenticated private-lab gateway. It does not fall back to cached or invented counts."
			/>
			<a class="text-link" href="/ask">Back to Ask</a>
		{:else if loadState === 'error'}
			<EmptyState
				title="Dataset catalog unavailable"
				body={errorMessage || 'The catalog could not be read.'}
			/>
		{:else}
			<div class="catalog-grid">
				<section class="catalog-list" aria-labelledby="catalog-title">
					<div class="section-heading">
						<h2 id="catalog-title">Select an artifact</h2>
						<p>{entries.length} known entries · independent availability</p>
					</div>
					<ul>
						{#each entries as entry}
							<li>
								<a
									class="catalog-card"
									class:unavailable={entry.availability !== 'available' && entry.availability !== 'inventory_reference'}
									href={`/research/datasets/${entry.catalog_id}`}
								>
									<span class="card-top">
										<span class="card-label">{entry.label}</span>
										<span class="card-state">{stateLabel(entry)}</span>
									</span>
									<span class="card-quantity">{quantity(entry)}</span>
									{#if entry.availability_reason}
										<span class="card-reason">{entry.availability_reason.replaceAll('_', ' ')}</span>
									{/if}
								</a>
							</li>
						{/each}
					</ul>
				</section>

				<aside class="catalog-context" aria-label="Catalog context">
					{#if overlap}
						<section class="overlap-card" aria-labelledby="overlap-title">
							<p class="eyebrow">Overlap alert / exact stored query text</p>
							<h2 id="overlap-title">
								{count(overlap.intersection_unique_query_count)} queries overlap exactly.
							</h2>
							<p>
								All {count(overlap.right_unique_query_count)} expanded-fixture questions also
								occur in the {count(overlap.left_unique_query_count)}-question all-query file.
								These are not independent samples.
							</p>
							<p class="revisions">
								Left {overlap.left_revision.slice(0, 12)}… · right
								{overlap.right_revision.slice(0, 12)}… · normalization
								{overlap.normalization} · near duplicates
								{overlap.near_duplicate_status.replaceAll('_', ' ')}
							</p>
						</section>
					{/if}

					{#if reviewEntry?.availability === 'available'}
						<section class="review-card" aria-labelledby="review-title">
							<p class="eyebrow">Separate review set</p>
							<h2 id="review-title">{count(reviewEntry.record_count)} frozen cases</h2>
							<p>
								{reviewEntry.split_counts
									? Object.entries(reviewEntry.split_counts)
											.map(([key, value]) => `${count(value)} ${key}`)
											.join(' · ')
									: 'Answerability counts unavailable'}
							</p>
							<p>
								Manifest-declared review status is not reviewer authentication or a fresh
								integrity verification. Reviewer identities are not exposed.
							</p>
							<p class="revisions">
								Review authority: {reviewEntry.review_authority.replaceAll('_', ' ')}
							</p>
						</section>
					{/if}

					<section class="units-card" aria-labelledby="units-title">
						<h2 id="units-title">Units do not pool</h2>
						<p>
							Chunks, questions, conversations, CSV rows and review cases are different units.
							Overlap is not independence, and a current file revision is not historical
							dataset identity.
						</p>
						<p>
							The index and CSV entries report inventory references; their totals are not
							rewritten as fixture counts.
						</p>
					</section>
				</aside>
			</div>
		{/if}
	</div>
</AppShell>

<style>
	.datasets-page {
		display: flex;
		flex-direction: column;
		gap: 1.5rem;
	}

	.eyebrow {
		margin: 0 0 0.5rem;
		color: var(--muted-color);
		font-size: 0.7rem;
		font-weight: 700;
		letter-spacing: 0.14em;
		text-transform: uppercase;
	}

	h1 {
		max-width: 20ch;
		margin: 0;
		font-size: clamp(2rem, 3.8vw, 3rem);
	}

	.lede {
		max-width: 66ch;
		margin: 0.9rem 0 0;
		color: var(--secondary);
	}

	.catalog-grid {
		display: grid;
		grid-template-columns: minmax(0, 1.2fr) minmax(280px, 0.8fr);
		gap: 1.25rem;
		align-items: start;
	}

	.catalog-list,
	.catalog-context section {
		padding: 1.25rem;
		border: 1px solid var(--border-color);
		border-radius: 12px;
		background: #fffdf8;
	}

	.section-heading {
		display: flex;
		flex-wrap: wrap;
		align-items: baseline;
		justify-content: space-between;
		gap: 0.5rem;
		margin-bottom: 0.8rem;
	}

	.section-heading h2,
	.catalog-context h2 {
		margin: 0;
		font-size: 1.3rem;
	}

	.section-heading p {
		margin: 0;
		color: var(--muted-color);
		font-size: 0.76rem;
	}

	.catalog-list ul {
		display: flex;
		flex-direction: column;
		gap: 0.5rem;
		margin: 0;
		padding: 0;
		list-style: none;
	}

	.catalog-card {
		display: flex;
		flex-direction: column;
		gap: 0.3rem;
		padding: 0.75rem 0.9rem;
		border: 1px solid var(--border-color);
		border-radius: 8px;
		color: var(--ink);
		text-decoration: none;
	}

	.catalog-card:hover {
		border-color: var(--teal);
	}

	.catalog-card.unavailable {
		border-left: 3px solid var(--rust);
	}

	.card-top {
		display: flex;
		align-items: baseline;
		justify-content: space-between;
		gap: 0.5rem;
	}

	.card-label {
		font-weight: 700;
	}

	.card-state {
		color: var(--muted-color);
		font-size: 0.68rem;
		letter-spacing: 0.05em;
		text-transform: uppercase;
	}

	.card-quantity {
		color: var(--secondary);
		font-size: 0.84rem;
	}

	.card-reason {
		color: var(--rust);
		font-family: monospace;
		font-size: 0.72rem;
	}

	.catalog-context {
		display: flex;
		flex-direction: column;
		gap: 1rem;
	}

	.catalog-context p {
		margin: 0 0 0.55rem;
		color: var(--secondary);
		font-size: 0.84rem;
	}

	.catalog-context p:last-child {
		margin-bottom: 0;
	}

	.overlap-card {
		border-left: 4px solid var(--rust) !important;
	}

	.revisions {
		font-family: monospace;
		color: var(--muted-color) !important;
		font-size: 0.72rem !important;
		overflow-wrap: anywhere;
	}

	.text-link {
		align-self: flex-start;
		color: var(--teal);
		font-weight: 700;
		text-underline-offset: 2px;
	}

	@media (max-width: 960px) {
		.catalog-grid {
			grid-template-columns: 1fr;
		}
	}
</style>
