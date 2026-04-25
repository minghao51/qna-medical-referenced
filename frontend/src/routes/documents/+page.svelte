<script lang="ts">
	import { onMount } from 'svelte';
	import AppShell from '$lib/components/AppShell.svelte';
	import EmptyState from '$lib/components/EmptyState.svelte';
	import LoadingSkeleton from '$lib/components/LoadingSkeleton.svelte';
	import MetricTile from '$lib/components/MetricTile.svelte';
	import { getDocuments, getDocument } from '$lib/utils/api';
	import type { DocumentListItem, DocumentDetailResponse, DocumentListResponse } from '$lib/types';

	let loading = $state(true);
	let error = $state('');
	let total = $state(0);
	let items = $state<DocumentListItem[]>([]);
	let sourceTypeCounts = $state<Record<string, number>>({});
	let page = $state(0);
	let pageSize = 50;
	let filterType = $state('');
	let selectedDoc = $state<DocumentDetailResponse | null>(null);
	let detailLoading = $state(false);
	let detailError = $state('');

	function closeModal() {
		selectedDoc = null;
		detailError = '';
	}

	function handleKeydown(e: KeyboardEvent) {
		if (e.key === 'Escape' && selectedDoc) closeModal();
	}

	async function loadDocs(p: number = 0) {
		loading = true;
		error = '';
		try {
			const offset = p * pageSize;
			const data = await getDocuments<DocumentListResponse>({
				limit: pageSize,
				offset,
				sourceType: filterType || undefined
			});
			total = data.total;
			items = data.items;
			sourceTypeCounts = data.source_type_counts ?? {};
			page = p;
		} catch (e) {
			error = e instanceof Error ? e.message : 'Failed to load documents';
		} finally {
			loading = false;
		}
	}

	async function viewDoc(id: string) {
		detailLoading = true;
		detailError = '';
		selectedDoc = null;
		try {
			selectedDoc = await getDocument<DocumentDetailResponse>(id);
		} catch (e) {
			detailError = e instanceof Error ? e.message : 'Failed to load document';
		} finally {
			detailLoading = false;
		}
	}

	function truncSource(s: string): string {
		if (!s) return '—';
		const parts = s.split('/');
		return parts[parts.length - 1] || s;
	}

	onMount(() => loadDocs(0));
</script>

<svelte:window onkeydown={handleKeydown} />

<svelte:head>
	<title>Documents</title>
</svelte:head>

<AppShell current="/documents">
	<div class="docs-page">
		<div class="page-header">
			<p class="eyebrow">Index</p>
			<h1>Document inspector</h1>
			<p class="subtitle">Browse and inspect the {total} chunks currently in the vector store.</p>
		</div>

		{#if Object.keys(sourceTypeCounts).length > 0}
			<div class="type-pills">
				<button
					type="button"
					class="pill"
					class:active={!filterType}
					onclick={() => { filterType = ''; loadDocs(0); }}
				>
					All ({total})
				</button>
				{#each Object.entries(sourceTypeCounts) as [type, count]}
					<button
						type="button"
						class="pill"
						class:active={filterType === type}
						onclick={() => { filterType = type; loadDocs(0); }}
					>
						{type} ({count})
					</button>
				{/each}
			</div>
		{/if}

		{#if loading}
			<LoadingSkeleton count={5} type="card" />
		{:else if error}
			<EmptyState title="Failed to load documents" body={error} />
		{:else if items.length === 0}
			<EmptyState title="No documents indexed" body="Run ingestion to populate the vector store." />
		{:else}
			<div class="table-wrap">
				<table class="docs-table">
					<thead>
						<tr>
							<th>Source</th>
							<th>Page</th>
							<th>Type</th>
							<th>Class</th>
							<th>Length</th>
							<th>Preview</th>
							<th></th>
						</tr>
					</thead>
					<tbody>
						{#each items as item}
							<tr>
								<td class="source-col" title={item.source}>{truncSource(item.source)}</td>
								<td>{item.page ?? '—'}</td>
								<td><span class="type-badge">{item.source_type || '—'}</span></td>
								<td>{item.source_class || '—'}</td>
								<td class="num">{item.content_length.toLocaleString()}</td>
								<td class="preview-col">{item.content_preview}</td>
								<td>
									<button type="button" class="view-btn" onclick={() => viewDoc(item.id)}>View</button>
								</td>
							</tr>
						{/each}
					</tbody>
				</table>
			</div>

			<div class="pagination">
				<button type="button" disabled={page === 0} onclick={() => loadDocs(page - 1)}>Previous</button>
				<span>Page {page + 1} of {Math.max(1, Math.ceil(total / pageSize))}</span>
				<button type="button" disabled={(page + 1) * pageSize >= total} onclick={() => loadDocs(page + 1)}>Next</button>
			</div>
		{/if}

		{#if detailLoading}
			<LoadingSkeleton count={1} type="card" />
		{/if}

		{#if detailError}
			<div class="detail-error">{detailError}</div>
		{/if}
	</div>
</AppShell>

{#if selectedDoc}
	<!-- svelte-ignore a11y_click_events_have_key_events -->
	<div class="modal-backdrop" onclick={closeModal} role="presentation">
		<div class="modal" role="dialog" aria-modal="true" tabindex="-1" onclick={(e) => e.stopPropagation()}>
			<div class="modal-header">
				<h3>{selectedDoc.id.slice(0, 16)}…</h3>
				<button type="button" class="close-btn" onclick={closeModal} aria-label="Close">&times;</button>
			</div>
			<div class="modal-meta">
				{#each Object.entries(selectedDoc.metadata) as [key, val]}
					<span class="meta-item"><strong>{key}:</strong> {String(val)}</span>
				{/each}
			</div>
			<pre class="modal-content">{selectedDoc.content}</pre>
		</div>
	</div>
{/if}

<style>
	.docs-page {
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

	.type-pills {
		display: flex;
		flex-wrap: wrap;
		gap: 0.4rem;
	}

	.pill {
		padding: 0.35rem 0.7rem;
		border: 1px solid var(--border-color);
		border-radius: 999px;
		background: white;
		cursor: pointer;
		font-size: 0.82rem;
		font-weight: 500;
	}

	.pill.active {
		background: var(--surface-strong);
		border-color: #6366f1;
	}

	.table-wrap {
		overflow-x: auto;
		border: 1px solid var(--border-color);
		border-radius: 18px;
		background: white;
	}

	.docs-table {
		width: 100%;
		border-collapse: collapse;
		font-size: 0.82rem;
	}

	.docs-table th {
		text-align: left;
		padding: 0.6rem 0.65rem;
		border-bottom: 2px solid var(--border-color);
		font-weight: 600;
		color: var(--muted-color);
		font-size: 0.75rem;
		text-transform: uppercase;
		letter-spacing: 0.03em;
		white-space: nowrap;
	}

	.docs-table td {
		padding: 0.5rem 0.65rem;
		border-bottom: 1px solid var(--border-color);
		max-width: 250px;
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
	}

	.docs-table tr:hover {
		background: var(--surface-subtle);
	}

	.source-col {
		font-weight: 600;
		max-width: 200px;
	}

	.num {
		font-variant-numeric: tabular-nums;
		text-align: right;
	}

	.preview-col {
		color: var(--muted-color);
		max-width: 300px;
	}

	.type-badge {
		padding: 0.1rem 0.4rem;
		border-radius: 999px;
		background: #dbeafe;
		color: #1d4ed8;
		font-size: 0.72rem;
		font-weight: 600;
	}

	.view-btn {
		padding: 0.25rem 0.6rem;
		border: 1px solid var(--border-color);
		border-radius: 6px;
		background: white;
		cursor: pointer;
		font-size: 0.78rem;
	}

	.view-btn:hover {
		background: var(--surface-subtle);
	}

	.pagination {
		display: flex;
		align-items: center;
		justify-content: center;
		gap: 1rem;
		font-size: 0.88rem;
		color: var(--muted-color);
	}

	.pagination button {
		padding: 0.4rem 0.8rem;
		border: 1px solid var(--border-color);
		border-radius: 8px;
		background: white;
		cursor: pointer;
	}

	.pagination button:disabled {
		opacity: 0.5;
		cursor: not-allowed;
	}

	.detail-error {
		padding: 0.75rem;
		border: 1px solid #f0c36d;
		background: #fff7e6;
		color: #7a4b00;
		border-radius: 12px;
	}

	.modal-backdrop {
		position: fixed;
		inset: 0;
		z-index: 200;
		display: flex;
		align-items: center;
		justify-content: center;
		background: rgba(0, 0, 0, 0.35);
		padding: 1rem;
	}

	.modal {
		width: 100%;
		max-width: 680px;
		max-height: 85vh;
		display: flex;
		flex-direction: column;
		border: 1px solid var(--border-color);
		border-radius: 18px;
		background: white;
		box-shadow: 0 16px 48px rgba(0, 0, 0, 0.18);
		overflow: hidden;
	}

	.modal-header {
		display: flex;
		justify-content: space-between;
		align-items: center;
		padding: 1rem 1.25rem;
		border-bottom: 1px solid var(--border-color);
	}

	.modal-header h3 {
		margin: 0;
		font-size: 1rem;
		font-family: monospace;
	}

	.close-btn {
		display: flex;
		align-items: center;
		justify-content: center;
		width: 2rem;
		height: 2rem;
		border: 1px solid var(--border-color);
		border-radius: 8px;
		background: white;
		cursor: pointer;
		font-size: 1.25rem;
		line-height: 1;
		color: var(--muted-color);
	}

	.close-btn:hover {
		background: var(--surface-subtle);
		color: var(--text-color);
	}

	.modal-meta {
		display: flex;
		flex-wrap: wrap;
		gap: 0.5rem;
		padding: 0.75rem 1.25rem;
		font-size: 0.82rem;
		color: var(--muted-color);
		border-bottom: 1px solid var(--border-color);
	}

	.modal-content {
		flex: 1;
		overflow: auto;
		padding: 1rem 1.25rem;
		background: var(--surface-subtle);
		font-size: 0.82rem;
		line-height: 1.5;
		white-space: pre-wrap;
		word-break: break-word;
		margin: 0;
	}
</style>
