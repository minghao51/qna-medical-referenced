<script lang="ts">
	import type { ResearchCatalogEntry, ResearchCatalogOverlap } from '$lib/types';

	type Props = {
		entry: ResearchCatalogEntry;
		overlap: ResearchCatalogOverlap[];
	};

	let { entry, overlap }: Props = $props();

	const relevantOverlap = $derived(
		overlap.find(
			(item) => item.left_catalog_id === entry.catalog_id || item.right_catalog_id === entry.catalog_id
		) ?? null
	);

	function count(value: number | null): string {
		return typeof value === 'number' && Number.isFinite(value)
			? value.toLocaleString('en-US')
			: 'N/A';
	}

	function unitLabel(): string {
		if (!entry.record_count || entry.record_count === 1) return entry.record_unit;
		if (entry.record_unit === 'conversation') return 'conversations';
		if (entry.record_unit === 'question') return 'questions';
		if (entry.record_unit === 'case') return 'cases';
		if (entry.record_unit === 'row') return 'rows';
		return 'chunks';
	}

	function splitEntries(): Array<[string, number]> {
		return Object.entries(entry.split_counts ?? {}).sort(([, a], [, b]) => b - a);
	}

	function confidenceEntries(): Array<[string, number]> {
		return Object.entries(entry.label_confidence_counts ?? {}).sort(([, a], [, b]) => b - a);
	}

	function reviewEntries(): Array<[string, number]> {
		return Object.entries(entry.raw_review_status_counts ?? {}).sort(([, a], [, b]) => b - a);
	}

	function splitWidth(value: number): number {
		const counts = Object.values(entry.split_counts ?? {});
		const max = counts.length ? Math.max(...counts) : 0;
		return max > 0 ? Math.max(4, (value / max) * 100) : 0;
	}

	function availabilityCopy(): string {
		switch (entry.availability) {
			case 'available':
				return 'Current source bytes read successfully.';
			case 'inventory_reference':
				return 'Live inventory is served by the existing document API; no second index client is opened.';
			case 'missing':
				return 'The known source file is absent. The catalog does not create it or substitute another artifact.';
			case 'malformed':
				return 'The known source exists but does not match its approved shape.';
			case 'unsupported':
				return 'The known source exceeds an approved bound or cannot be projected safely.';
		}
	}
</script>

<article class="dataset-detail" aria-labelledby="dataset-title">
	<header>
		<p class="eyebrow">Dataset / {entry.kind.replaceAll('_', ' ')}</p>
		<h1 id="dataset-title">{entry.label}</h1>
		<p class="catalog-id">{entry.catalog_id}</p>
		<p class="source-ref">{entry.origin_ref}</p>
	</header>

	<div class="state-row" class:unavailable={entry.availability !== 'available' && entry.availability !== 'inventory_reference'}>
		<span class="state-badge">{entry.availability.replaceAll('_', ' ')}</span>
		<span>{availabilityCopy()}</span>
		{#if entry.availability_reason}
			<span class="reason">Reason: {entry.availability_reason}</span>
		{/if}
	</div>

	{#if entry.availability === 'available' || entry.availability === 'inventory_reference'}
		{#if entry.availability === 'available'}
		<section class="summary" aria-labelledby="summary-title">
			<h2 id="summary-title">Current-file inventory</h2>
			<div class="summary-grid">
				<div>
					<p class="figure">{count(entry.record_count)}</p>
					<p class="figure-label">{unitLabel()}</p>
				</div>
				{#if entry.turn_count !== null}
					<div>
						<p class="figure">{count(entry.turn_count)}</p>
						<p class="figure-label">stored turns</p>
					</div>
				{/if}
				<div>
					<p class="figure revision">{entry.revision_sha256?.slice(0, 12) ?? 'N/A'}…</p>
					<p class="figure-label">current-byte revision</p>
				</div>
			</div>
			<p class="note">
				The revision fingerprints the current source bytes. It is not historical dataset identity
				and does not bind archived results to these rows.
			</p>
		</section>

		{#if splitEntries().length > 0}
			<section aria-labelledby="splits-title">
				<h2 id="splits-title">Declared splits</h2>
				<ul class="split-list">
					{#each splitEntries() as [split, value]}
						<li>
							<span class="split-label">{split}</span>
							<span class="split-bar" aria-hidden="true">
								<span style={`width:${splitWidth(value)}%`}></span>
							</span>
							<span class="split-count">{count(value)}</span>
						</li>
					{/each}
				</ul>
			</section>
		{/if}

		<div class="metadata-grid">
			<section aria-labelledby="confidence-title">
				<h2 id="confidence-title">Label confidence</h2>
				{#if confidenceEntries().length > 0}
					<dl>
						{#each confidenceEntries() as [label, value]}
							<div>
								<dt>{label}</dt>
								<dd>{count(value)}</dd>
							</div>
						{/each}
					</dl>
					<p class="note">Label confidence is not review authority.</p>
				{:else}
					<p class="note">No label-confidence counts are recorded for this artifact.</p>
				{/if}
			</section>

			<section aria-labelledby="review-title">
				<h2 id="review-title">Review status</h2>
				{#if reviewEntries().length > 0}
					<dl>
						{#each reviewEntries() as [status, value]}
							<div>
								<dt>{status}</dt>
								<dd>{count(value)}</dd>
							</div>
						{/each}
					</dl>
				{:else}
					<p class="note">Review status is absent in the raw rows.</p>
				{/if}
				{#if entry.review_status_missing_count !== null}
					<p class="note">
						{count(entry.review_status_missing_count)} record(s) carry no stored review status.
						No normalized default is presented as stored data.
					</p>
				{/if}
				<p class="note">
					Review authority:
					<strong>
						{entry.review_authority === 'manifest_declared_not_authenticated'
							? 'manifest-declared, not authenticated'
							: 'not assessed'}
					</strong>
				</p>
			</section>
		</div>

		{:else}
			<p class="callout">
				This entry points to the existing document inventory. Its live chunk total is available
				through <a href="/documents">the evidence browser</a>; no fixed count is duplicated here.
			</p>
		{/if}

		{#if entry.kind === 'reference_csv'}
			<p class="callout">
				CSV data-row count is not the served reference-chunk total. The two inventories remain
				separate.
			</p>
		{/if}

		{#if relevantOverlap}
			<section class="overlap" aria-labelledby="overlap-title">
				<p class="eyebrow">Overlap alert / exact stored query text</p>
				<h2 id="overlap-title">
					{count(relevantOverlap.intersection_unique_query_count)} queries overlap exactly.
				</h2>
				<p>
					{relevantOverlap.left_catalog_id} ({count(relevantOverlap.left_unique_query_count)})
					and {relevantOverlap.right_catalog_id} ({count(relevantOverlap.right_unique_query_count)})
					share this intersection. These are not independent samples. Matching text does not
					prove identical labels, corpus bytes or benchmark identity.
				</p>
				<p class="revisions">
					Left revision {relevantOverlap.left_revision.slice(0, 12)}… · right revision
					{relevantOverlap.right_revision.slice(0, 12)}… · normalization
					{relevantOverlap.normalization} · near duplicates
					{relevantOverlap.near_duplicate_status.replaceAll('_', ' ')}
				</p>
			</section>
		{/if}

		{#if entry.case_projection === 'summary_only'}
			<p class="callout">
				This artifact is summary-only. Reviewer identities, frozen document bodies and per-case
				rows are intentionally not exposed.
			</p>
		{:else if entry.case_projection === 'unavailable'}
			<p class="callout">
				Case rows are not available for this artifact type. Its inventory remains inspectable
				independently.
			</p>
		{/if}
	{:else}
		<div class="unavailable-panel" role="status">
			<h2>Inventory unavailable</h2>
			<p>
				The catalog reports this artifact's actual state above. Other artifacts remain
				independently available; no count is replaced with zero.
			</p>
		</div>
	{/if}
</article>

<style>
	.dataset-detail {
		display: flex;
		flex-direction: column;
		gap: 1.35rem;
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
		font-size: clamp(1.8rem, 3.6vw, 2.8rem);
	}

	.catalog-id {
		margin: 0.35rem 0 0;
		color: var(--secondary);
		font-family: monospace;
		font-size: 0.82rem;
	}

	.source-ref {
		margin: 0.2rem 0 0;
		color: var(--muted-color);
		font-family: monospace;
		font-size: 0.76rem;
		overflow-wrap: anywhere;
	}

	.state-row {
		display: flex;
		flex-wrap: wrap;
		align-items: center;
		gap: 0.5rem;
		padding: 0.7rem 0.9rem;
		border: 1px solid var(--border-color);
		border-radius: 8px;
		background: #fffdf8;
		color: var(--secondary);
		font-size: 0.82rem;
	}

	.state-row.unavailable {
		border-left: 3px solid var(--rust);
	}

	.state-badge {
		padding: 0.2rem 0.5rem;
		border: 1px solid var(--border-color);
		border-radius: 999px;
		color: var(--rust);
		font-size: 0.7rem;
		font-weight: 700;
		letter-spacing: 0.06em;
		text-transform: uppercase;
	}

	.reason {
		color: var(--muted-color);
		font-family: monospace;
		font-size: 0.74rem;
	}

	h2 {
		margin: 0 0 0.6rem;
		font-size: 1.25rem;
	}

	.summary,
	.metadata-grid > section,
	.overlap,
	.unavailable-panel {
		padding: 1.1rem;
		border: 1px solid var(--border-color);
		border-radius: 10px;
		background: #fffdf8;
	}

	.summary-grid {
		display: grid;
		grid-template-columns: repeat(auto-fit, minmax(140px, 1fr));
		gap: 0.8rem;
	}

	.figure {
		margin: 0;
		font-family: var(--font-heading);
		font-size: 1.7rem;
	}

	.figure.revision {
		font-family: monospace;
		font-size: 1rem;
		overflow-wrap: anywhere;
	}

	.figure-label {
		margin: 0.15rem 0 0;
		color: var(--muted-color);
		font-size: 0.72rem;
		letter-spacing: 0.04em;
		text-transform: uppercase;
	}

	.note {
		margin: 0.5rem 0 0;
		color: var(--muted-color);
		font-size: 0.8rem;
	}

	.split-list {
		display: flex;
		flex-direction: column;
		gap: 0.5rem;
		margin: 0;
		padding: 0;
		list-style: none;
	}

	.split-list li {
		display: grid;
		grid-template-columns: 7rem minmax(0, 1fr) 3rem;
		align-items: center;
		gap: 0.6rem;
		font-size: 0.85rem;
	}

	.split-bar {
		display: block;
		height: 10px;
		overflow: hidden;
		border-radius: 999px;
		background: var(--surface-strong);
	}

	.split-bar span {
		display: block;
		height: 100%;
		background: var(--teal);
	}

	.split-count {
		font-variant-numeric: tabular-nums;
		text-align: right;
	}

	.metadata-grid {
		display: grid;
		grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
		gap: 1rem;
	}

	dl {
		display: flex;
		flex-wrap: wrap;
		gap: 0.6rem 1.2rem;
		margin: 0;
	}

	dt {
		color: var(--muted-color);
		font-size: 0.72rem;
		letter-spacing: 0.04em;
		text-transform: uppercase;
	}

	dd {
		margin: 0.1rem 0 0;
		font-family: var(--font-heading);
		font-size: 1.15rem;
	}

	.callout {
		margin: 0;
		padding: 0.85rem 1rem;
		border-left: 3px solid var(--blue);
		background: var(--surface-subtle);
		color: var(--secondary);
		font-size: 0.85rem;
	}

	.overlap {
		border-left: 4px solid var(--rust);
	}

	.overlap h2 {
		font-size: 1.4rem;
	}

	.overlap p {
		margin: 0 0 0.6rem;
		color: var(--secondary);
		font-size: 0.88rem;
	}

	.revisions {
		font-family: monospace;
		font-size: 0.72rem !important;
		overflow-wrap: anywhere;
	}

	.unavailable-panel {
		border-left: 3px solid var(--rust);
	}

	.unavailable-panel p {
		margin: 0;
		color: var(--secondary);
		font-size: 0.88rem;
	}

	@media (max-width: 640px) {
		.split-list li {
			grid-template-columns: 5.5rem minmax(0, 1fr) 2.5rem;
		}
	}
</style>
