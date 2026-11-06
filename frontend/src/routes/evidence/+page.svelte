<script lang="ts">
	import { onMount } from 'svelte';
	import AppShell from '$lib/components/AppShell.svelte';
	import EmptyState from '$lib/components/EmptyState.svelte';
	import LoadingSkeleton from '$lib/components/LoadingSkeleton.svelte';
	import { getDocuments } from '$lib/utils/api';
	import type { DocumentListItem, DocumentListResponse } from '$lib/types';

	const compactPageSize = 12;
	const widePageSize = 50;
	let pageSize = $state(widePageSize);

	let loading = $state(true);
	let error = $state('');
	let total = $state(0);
	let items = $state<DocumentListItem[]>([]);
	let filteredCounts = $state<Record<string, number>>({});
	let globalCounts = $state<Record<string, number> | null>(null);
	let offset = $state(0);
	let filterType = $state('');
	let indexIdentity = $state<string | null>(null);
	let requestSequence = 0;

	const globalEntries = $derived(
		Object.entries(globalCounts ?? {}).sort((left, right) => right[1] - left[1])
	);
	const globalAll = $derived.by(() => {
		if (globalCounts) {
			return Object.values(globalCounts).reduce((sum, value) => sum + value, 0);
		}
		return filterType ? null : total;
	});
	const rangeStart = $derived(total === 0 ? 0 : offset + 1);
	const rangeEnd = $derived(Math.min(offset + items.length, total));

	function formatCount(value: number | null | undefined): string {
		return typeof value === 'number' && Number.isFinite(value)
			? value.toLocaleString('en-US')
			: 'unavailable';
	}

	function sourceLabel(item: DocumentListItem): string {
		return item.display_label || item.canonical_label || item.logical_name || item.source || 'Unknown source';
	}

	function sourceFile(item: DocumentListItem): string {
		if (!item.source) return '';
		const parts = item.source.split('/');
		return parts[parts.length - 1] || item.source;
	}

	function displayPage(item: DocumentListItem): number | null {
		// HTML/Markdown "page 1" is a convention, not a rendered print page.
		return item.source_type === 'pdf' ? item.page : null;
	}

	function typeLabel(value: string): string {
		return value.replaceAll('_', ' ');
	}

	function readUrlState() {
		if (typeof window === 'undefined') return;
		const params = new URLSearchParams(window.location.search);
		const type = params.get('source_type')?.trim() ?? '';
		const requestedOffset = Number(params.get('offset') ?? '0');
		filterType = type;
		offset = Number.isSafeInteger(requestedOffset) && requestedOffset >= 0 ? requestedOffset : 0;
	}

	function pushUrl() {
		if (typeof window === 'undefined') return;
		const params = new URLSearchParams();
		if (filterType) params.set('source_type', filterType);
		if (offset > 0) params.set('offset', String(offset));
		const query = params.toString();
		window.history.pushState({}, '', `${window.location.pathname}${query ? `?${query}` : ''}`);
	}

	async function loadPage() {
		const token = ++requestSequence;
		loading = true;
		error = '';
		try {
			const data = await getDocuments<DocumentListResponse>({
				limit: pageSize,
				offset,
				sourceType: filterType || undefined
			});
			if (token !== requestSequence) return;
			total = data.total;
			items = data.items;
			filteredCounts = data.source_type_counts ?? {};
			globalCounts = data.global_source_type_counts ?? null;
			indexIdentity = data.index_identity ?? null;
		} catch (err) {
			if (token !== requestSequence) return;
			error = err instanceof Error ? err.message : 'Failed to load the evidence index.';
		} finally {
			if (token === requestSequence) loading = false;
		}
	}

	function selectType(nextType: string) {
		filterType = nextType;
		offset = 0;
		pushUrl();
		void loadPage();
	}

	function goToPage(nextOffset: number) {
		offset = Math.max(0, nextOffset);
		pushUrl();
		void loadPage();
	}

	function resetFilters() {
		filterType = '';
		offset = 0;
		pushUrl();
		void loadPage();
	}

	function handlePopState() {
		readUrlState();
		void loadPage();
	}

	onMount(() => {
		pageSize = window.matchMedia('(max-width: 640px)').matches ? compactPageSize : widePageSize;
		readUrlState();
		void loadPage();
		window.addEventListener('popstate', handlePopState);
		return () => window.removeEventListener('popstate', handlePopState);
	});
</script>

<svelte:head>
	<title>Evidence · Fieldnote</title>
</svelte:head>

<AppShell current="/evidence">
	<div class="evidence-page">
		<header class="page-header">
			<p class="eyebrow">Evidence / indexed chunks</p>
			<h1>What is in the frozen index?</h1>
			<p class="lede">
				Browse indexed chunks with their source class and recorded provenance. Counts are
				chunks, not publications or clinical evidence.
			</p>
		</header>

		<div class="facet-panel" aria-label="Source type facets">
			{#if loading && !items.length}
				<LoadingSkeleton count={1} type="row" />
			{:else if globalCounts}
				<button type="button" class="pill" class:active={!filterType} onclick={() => selectType('')}>
					All ({formatCount(globalAll)})
				</button>
				{#each globalEntries as [type, count]}
					<button
						type="button"
						class="pill"
						class:active={filterType === type}
						onclick={() => selectType(type)}
					>
						{typeLabel(type)} ({formatCount(count)})
					</button>
				{/each}
			{:else}
				<span class="facet-note">
					Unfiltered source-type counts are unavailable from this backend. The selected view
					remains honest.
				</span>
			{/if}
		</div>

		{#if indexIdentity}
			<p class="identity-note">
				Index identity: <code>{indexIdentity.slice(0, 16)}…</code>. This is a recorded source
				snapshot digest, not a publication count or freshness guarantee.
			</p>
		{:else}
			<p class="identity-note">Index identity is not provided by this backend.</p>
		{/if}

		{#if loading}
			<LoadingSkeleton count={5} type="card" />
		{:else if error}
			<EmptyState title="Could not load evidence" body={error} />
		{:else if items.length === 0}
			{#if filterType || offset > 0}
				<EmptyState
					title="No matching chunks"
					body="The filter succeeded with zero matches. No counts were relabelled."
				/>
				<button type="button" class="text-button" onclick={resetFilters}>Reset filters</button>
			{:else}
				<EmptyState
					title="No indexed chunks"
					body="The service is reachable, but the index is empty or not ready. This is not a zero-quality result."
				/>
				<a class="text-link" href="/health">Check service status</a>
			{/if}
		{:else}
			<div class="result-summary">
				<p>
					Showing {formatCount(rangeStart)}–{formatCount(rangeEnd)} of {formatCount(total)}
					{#if filterType}
						filtered chunks ({typeLabel(filterType)})
					{:else}
						chunks
					{/if}
					{#if globalAll !== null && filterType}
						· All index {formatCount(globalAll)}
					{/if}
				</p>
				{#if filteredCounts && Object.keys(filteredCounts).length > 0 && filterType}
					<p class="filtered-note">Filtered counts: {typeLabel(filterType)} ({formatCount(total)})</p>
				{/if}
			</div>

			<div class="table-wrap">
				<table class="evidence-table">
					<thead>
						<tr>
							<th scope="col">Source</th>
							<th scope="col">Location</th>
							<th scope="col">Type</th>
							<th scope="col">Class</th>
							<th scope="col">Length</th>
							<th scope="col">Excerpt</th>
							<th scope="col"><span class="sr-only">Inspect</span></th>
						</tr>
					</thead>
					<tbody>
						{#each items as item, rowIndex (item.id)}
							<tr>
								<td data-label="Source">
									<span class="source-title">{sourceLabel(item)}</span>
									<span class="source-file" title={item.source}>{sourceFile(item)}</span>
								</td>
								<td data-label="Location">
									{displayPage(item) !== null ? `PDF page ${displayPage(item)}` : 'Not provided'}
								</td>
								<td data-label="Type"><span class="type-badge">{typeLabel(item.source_type || 'unknown')}</span></td>
								<td data-label="Class">{typeLabel(item.source_class || 'unknown')}</td>
								<td data-label="Length" class="num">{item.content_length.toLocaleString()}</td>
								<td data-label="Excerpt" class="preview-col">{item.content_preview}</td>
								<td>
									<a
										class="inspect-link"
										href={`/evidence/${encodeURIComponent(item.id)}`}
										aria-label={`Inspect ${sourceLabel(item)}${displayPage(item) !== null ? `, PDF page ${displayPage(item)}` : ''}, result ${offset + rowIndex + 1}`}
									>
										Inspect
									</a>
								</td>
							</tr>
						{/each}
					</tbody>
				</table>
			</div>

			<div class="pagination">
				<button type="button" disabled={offset === 0} onclick={() => goToPage(offset - pageSize)}>
					Previous
				</button>
				<span>
					{formatCount(offset + 1)}–{formatCount(Math.min(offset + pageSize, total))} of {formatCount(total)}
				</span>
				<button
					type="button"
					disabled={offset + pageSize >= total}
					onclick={() => goToPage(offset + pageSize)}
				>
					Next
				</button>
			</div>
		{/if}

		<p class="footer-note">
			The original source link is shown only when a safe recorded URL exists. A page number is
			shown only for PDF chunks; HTML “page 1” is not rendered as a print-page claim.
		</p>
	</div>
</AppShell>

<style>
	.sr-only {
		position: absolute;
		width: 1px;
		height: 1px;
		padding: 0;
		margin: -1px;
		overflow: hidden;
		clip: rect(0, 0, 0, 0);
		white-space: nowrap;
		border: 0;
	}

	.evidence-page {
		display: flex;
		flex-direction: column;
		gap: 1.1rem;
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
		margin: 0;
		font-size: clamp(2rem, 3.8vw, 3rem);
	}

	.lede {
		max-width: 66ch;
		margin: 0.8rem 0 0;
		color: var(--secondary);
	}

	.facet-panel {
		display: flex;
		flex-wrap: wrap;
		gap: 0.4rem;
		align-items: center;
		padding: 0.7rem 0;
		border-top: 1px solid var(--border-color);
		border-bottom: 1px solid var(--border-color);
	}

	.pill {
		min-height: 36px;
		padding: 0.3rem 0.7rem;
		border: 1px solid var(--border-color);
		border-radius: 999px;
		background: #fffdf8;
		color: var(--ink);
		font: inherit;
		font-size: 0.82rem;
		font-weight: 600;
		cursor: pointer;
	}

	.pill.active {
		border-color: var(--teal);
		background: var(--teal);
		color: #fff;
	}

	.facet-note {
		color: var(--muted-color);
		font-size: 0.8rem;
	}

	.identity-note {
		margin: 0;
		color: var(--muted-color);
		font-size: 0.78rem;
	}

	.identity-note code {
		font-size: 0.74rem;
	}

	.result-summary {
		display: flex;
		flex-wrap: wrap;
		justify-content: space-between;
		gap: 0.5rem;
		color: var(--secondary);
		font-size: 0.84rem;
	}

	.result-summary p {
		margin: 0;
	}

	.filtered-note {
		color: var(--muted-color);
		font-size: 0.76rem;
	}

	.table-wrap {
		overflow-x: auto;
		border: 1px solid var(--border-color);
		border-radius: 10px;
		background: #fffdf8;
	}

	.evidence-table {
		width: 100%;
		border-collapse: collapse;
		font-size: 0.82rem;
	}

	.evidence-table th,
	.evidence-table td {
		padding: 0.65rem;
		border-bottom: 1px solid var(--border-color);
		text-align: left;
		vertical-align: top;
	}

	.evidence-table thead th {
		color: var(--muted-color);
		font-size: 0.68rem;
		letter-spacing: 0.06em;
		text-transform: uppercase;
		white-space: nowrap;
	}

	.source-title {
		display: block;
		font-weight: 700;
	}

	.source-file {
		display: block;
		max-width: 260px;
		overflow: hidden;
		color: var(--muted-color);
		font-family: monospace;
		font-size: 0.7rem;
		text-overflow: ellipsis;
		white-space: nowrap;
	}

	.type-badge {
		display: inline-block;
		padding: 0.15rem 0.4rem;
		border: 1px solid var(--border-color);
		border-radius: 4px;
		font-size: 0.72rem;
		white-space: nowrap;
	}

	.num {
		font-variant-numeric: tabular-nums;
	}

	.preview-col {
		max-width: 380px;
		color: var(--secondary);
	}

	.inspect-link {
		display: inline-flex;
		align-items: center;
		min-height: 44px;
		color: var(--teal);
		font-weight: 700;
		text-underline-offset: 2px;
	}

	.text-link {
		color: var(--teal);
		font-weight: 700;
		text-underline-offset: 2px;
	}

	.pagination {
		display: flex;
		align-items: center;
		justify-content: space-between;
		gap: 0.7rem;
		color: var(--secondary);
		font-size: 0.82rem;
	}

	.pagination button,
	.text-button {
		min-height: 40px;
		padding: 0.4rem 0.7rem;
		border: 1px solid var(--border-color);
		border-radius: 6px;
		background: #fffdf8;
		color: var(--ink);
		font: inherit;
		font-weight: 600;
		cursor: pointer;
	}

	.pagination button:disabled {
		opacity: 0.45;
		cursor: default;
	}

	.text-button {
		align-self: flex-start;
	}

	.footer-note {
		margin: 0;
		padding-top: 0.7rem;
		border-top: 1px solid var(--border-color);
		color: var(--muted-color);
		font-size: 0.78rem;
	}

	@media (max-width: 860px) {
		.evidence-table thead {
			display: none;
		}

		.evidence-table,
		.evidence-table tbody,
		.evidence-table tr,
		.evidence-table th,
		.evidence-table td {
			display: block;
		}

		.evidence-table tr {
			padding: 0.8rem 0;
			border-bottom: 1px solid var(--border-color);
		}

		.evidence-table th,
		.evidence-table td {
			padding: 0.18rem 0.65rem;
			border: 0;
		}

		.evidence-table td[data-label]::before {
			content: attr(data-label);
			display: block;
			color: var(--muted-color);
			font-size: 0.66rem;
			letter-spacing: 0.06em;
			text-transform: uppercase;
		}

		.evidence-table td[data-label='Type'],
		.evidence-table td[data-label='Class'],
		.evidence-table td[data-label='Length'] {
			display: none;
		}

		.evidence-table .source-file {
			max-width: 100%;
		}

		.evidence-table .preview-col {
			display: -webkit-box;
			max-width: none;
			overflow: hidden;
			-webkit-box-orient: vertical;
			-webkit-line-clamp: 3;
			line-clamp: 3;
		}

		.preview-col {
			max-width: none;
		}
	}
</style>
