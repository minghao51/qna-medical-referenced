<script lang="ts">
	import { onMount } from 'svelte';
	import { page } from '$app/state';
	import AppShell from '$lib/components/AppShell.svelte';
	import EmptyState from '$lib/components/EmptyState.svelte';
	import LoadingSkeleton from '$lib/components/LoadingSkeleton.svelte';
	import { getDocument } from '$lib/utils/api';
	import { getSafeExternalUrl } from '$lib/utils/url';
	import type { DocumentDetailResponse } from '$lib/types';

	type LoadState = 'loading' | 'available' | 'missing' | 'error';

	let loadState = $state<LoadState>('loading');
	let errorMessage = $state('');
	let document = $state<DocumentDetailResponse | null>(null);
	let requestSequence = 0;

	const safeSourceUrl = $derived(getSafeExternalUrl(document?.source_url));
	const displayName = $derived(
		document?.display_label ||
			document?.canonical_label ||
			document?.logical_name ||
			document?.id?.slice(0, 16) ||
			'Indexed chunk'
	);
	const pdfPage = $derived(document?.source_type === 'pdf' ? document?.page ?? null : null);

	function docId(): string {
		return page.params.id ?? '';
	}

	async function loadDocument() {
		const token = ++requestSequence;
		loadState = 'loading';
		const id = docId();
		if (!id) {
			loadState = 'missing';
			return;
		}
		try {
			const payload = await getDocument<DocumentDetailResponse>(id);
			if (token !== requestSequence) return;
			document = payload;
			loadState = 'available';
		} catch (error) {
			if (token !== requestSequence) return;
			const message = error instanceof Error ? error.message : 'The chunk could not be read.';
			errorMessage = message;
			loadState = /not found/i.test(message) ? 'missing' : 'error';
		}
	}

	onMount(() => {
		void loadDocument();
	});
</script>

<svelte:head>
	<title>{displayName} · Evidence · Fieldnote</title>
</svelte:head>

<AppShell current="/evidence">
	<div class="chunk-page">
		<div class="back-row">
			<button type="button" onclick={() => history.back()}>← Back to evidence</button>
			<a href="/evidence">All evidence</a>
		</div>

		{#if loadState === 'loading'}
			<div aria-busy="true"><LoadingSkeleton count={3} type="card" /></div>
		{:else if loadState === 'missing'}
			<EmptyState
				title="Chunk not found"
				body="The exact chunk ID is not present in the current index. IDs are not reconstructed from source names or page numbers."
			/>
		{:else if loadState === 'error'}
			<EmptyState
				title="Chunk unavailable"
				body={errorMessage || 'The indexed chunk could not be read.'}
			/>
		{:else if loadState === 'available' && document}
			<header class="chunk-header">
				<p class="eyebrow">Evidence / indexed chunk</p>
				<h1>{displayName}</h1>
				<p class="chunk-warning">
					This is an indexed chunk excerpt, not the full publication. Read the original with a
					qualified professional before relying on it.
				</p>
			</header>

			<div class="detail-grid">
				<article class="chunk-text" aria-labelledby="chunk-text-title">
					<p class="eyebrow">The indexed excerpt</p>
					<h2 id="chunk-text-title">Indexed content</h2>
					<pre>{document.content}</pre>
					<p class="excerpt-note">
						Excerpt reproduced from the frozen index. Line breaks reflowed; text otherwise
						preserved. The chunk may begin or end mid-sentence.
					</p>
				</article>

				<aside class="provenance-card" aria-labelledby="provenance-title">
					<h2 id="provenance-title">Provenance</h2>
					<dl>
						<div>
							<dt>Source label</dt>
							<dd>{document.logical_name ?? document.canonical_label ?? displayName}</dd>
						</div>
						<div>
							<dt>Source class</dt>
							<dd>{document.source_class?.replaceAll('_', ' ') ?? 'Not provided'}</dd>
						</div>
						<div>
							<dt>Host</dt>
							<dd>{document.domain ?? 'Not provided'}</dd>
						</div>
						<div>
							<dt>Position</dt>
							<dd>{pdfPage !== null ? `PDF page ${pdfPage}` : 'Not provided'}</dd>
						</div>
						<div>
							<dt>Source updated</dt>
							<dd>Not provided by the API</dd>
						</div>
						<div>
							<dt>Ingested / verified</dt>
							<dd>Not established</dd>
						</div>
					</dl>
					{#if safeSourceUrl}
						<a class="original-button" href={safeSourceUrl} target="_blank" rel="noopener noreferrer">
							Open original source ↗
						</a>
					{:else}
						<span class="unavailable-link">Original link unavailable</span>
					{/if}
				</aside>
			</div>

			<section class="technical" aria-labelledby="technical-title">
				<h2 id="technical-title">Technical identity</h2>
				<p class="technical-id">
					Exact store ID: <code>{document.id}</code>
				</p>
				<p class="technical-note">
					This ID is an application join, not a publication identifier or telemetry identity.
					The original link is shown only when a safe recorded http(s) URL exists. No date is
					inferred from file modification time.
				</p>
			</section>
		{/if}
	</div>
</AppShell>

<style>
	.chunk-page {
		display: flex;
		flex-direction: column;
		gap: 1.25rem;
	}

	.back-row {
		display: flex;
		flex-wrap: wrap;
		align-items: center;
		gap: 1rem;
	}

	.back-row button,
	.back-row a {
		color: var(--teal);
		font: inherit;
		font-weight: 700;
		text-underline-offset: 2px;
	}

	.back-row button,
	.back-row a {
		display: inline-flex;
		align-items: center;
		min-height: 44px;
	}

	.back-row button {
		min-height: 44px;
		padding: 0.35rem 0.6rem;
		border: 1px solid var(--border-color);
		border-radius: 6px;
		background: #fffdf8;
		cursor: pointer;
	}

	.eyebrow {
		margin: 0 0 0.45rem;
		color: var(--muted-color);
		font-size: 0.7rem;
		font-weight: 700;
		letter-spacing: 0.14em;
		text-transform: uppercase;
	}

	h1 {
		margin: 0;
		font-size: clamp(1.9rem, 3.8vw, 2.8rem);
		overflow-wrap: anywhere;
	}

	.unavailable-link {
		display: inline-block;
		margin-top: 0.5rem;
		color: var(--rust);
		font-size: 0.85rem;
	}

	.chunk-warning {
		max-width: 70ch;
		margin: 0.8rem 0 0;
		padding: 0.7rem 0.9rem;
		border-left: 3px solid var(--rust);
		background: var(--surface-subtle);
		color: var(--secondary);
		font-size: 0.85rem;
	}

	.detail-grid {
		display: grid;
		grid-template-columns: minmax(0, 1.35fr) minmax(280px, 0.65fr);
		gap: 1.25rem;
		align-items: start;
	}

	dt {
		color: var(--muted-color);
		font-size: 0.66rem;
		letter-spacing: 0.06em;
		text-transform: uppercase;
	}

	dd {
		margin: 0.2rem 0 0;
		font-size: 0.88rem;
		overflow-wrap: anywhere;
	}

	.chunk-text,
	.provenance-card,
	.technical {
		padding: 1.25rem;
		border: 1px solid var(--border-color);
		border-radius: 10px;
		background: #fffdf8;
	}

	.provenance-card h2 {
		margin-bottom: 0.9rem;
	}

	.provenance-card dl {
		display: grid;
		gap: 0.8rem;
		margin: 0;
	}

	.provenance-card dt {
		color: var(--muted-color);
		font-size: 0.66rem;
		letter-spacing: 0.06em;
		text-transform: uppercase;
	}

	.provenance-card dd {
		margin: 0.15rem 0 0;
		font-size: 0.92rem;
		overflow-wrap: anywhere;
	}

	.original-button {
		display: inline-flex;
		align-items: center;
		min-height: 44px;
		margin-top: 1.1rem;
		padding: 0.6rem 0.9rem;
		border-radius: 6px;
		background: var(--teal);
		color: white;
		font-weight: 700;
		text-decoration: none;
	}

	.original-button:hover {
		background: #00574f;
	}

	.excerpt-note {
		margin: 0.9rem 0 0;
		padding-top: 0.8rem;
		border-top: 1px solid var(--border-color);
		color: var(--muted-color);
		font-size: 0.78rem;
	}

	h2 {
		margin: 0 0 0.7rem;
		font-size: 1.2rem;
	}

	.chunk-text pre {
		max-height: 32rem;
		margin: 0;
		overflow: auto;
		color: var(--ink);
		font-family: var(--font-body);
		font-size: 0.92rem;
		line-height: 1.65;
		white-space: pre-wrap;
		overflow-wrap: anywhere;
	}

	.technical-id {
		margin: 0 0 0.5rem;
		font-family: monospace;
		font-size: 0.78rem;
		overflow-wrap: anywhere;
	}

	.technical-note {
		margin: 0;
		color: var(--muted-color);
		font-size: 0.8rem;
	}

	@media (max-width: 900px) {
		.detail-grid {
			grid-template-columns: minmax(0, 1fr);
		}
	}
</style>
