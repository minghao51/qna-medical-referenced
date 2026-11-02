<script lang="ts">
	import { onMount } from 'svelte';
	import { page } from '$app/state';
	import AppShell from '$lib/components/AppShell.svelte';
	import DatasetDetail from '$lib/components/DatasetDetail.svelte';
	import EmptyState from '$lib/components/EmptyState.svelte';
	import LoadingSkeleton from '$lib/components/LoadingSkeleton.svelte';
	import ResearchNav from '$lib/components/ResearchNav.svelte';
	import {
		getResearchDataset,
		getResearchDatasetCases,
		getResearchDatasets
	} from '$lib/utils/api';
	import type {
		ResearchCatalogCase,
		ResearchCatalogCasesResponse,
		ResearchCatalogEntry,
		ResearchCatalogOverlap,
		ResearchCatalogResponse
	} from '$lib/types';

	type LoadState = 'loading' | 'available' | 'missing' | 'unauthorized' | 'error';
	type CaseState = 'idle' | 'loading' | 'available' | 'revision_changed' | 'error';

	const datasetIdPattern = /^[a-z0-9][a-z0-9-]*$/;

	let loadState = $state<LoadState>('loading');
	let errorMessage = $state('');
	let entry = $state<ResearchCatalogEntry | null>(null);
	let overlap = $state<ResearchCatalogOverlap[]>([]);
	let caseState = $state<CaseState>('idle');
	let casesError = $state('');
	let cases = $state<ResearchCatalogCase[]>([]);
	let caseTotal = $state(0);
	let selectedIndex = $state(0);
	let entrySequence = 0;
	let caseSequence = 0;

	const selectedCase = $derived(cases[selectedIndex] ?? null);

	function isUnauthorized(message: string): boolean {
		return /401|x-api-key|missing .*key/i.test(message);
	}

	function datasetId(): string {
		return page.params.datasetId ?? '';
	}

	function requestedCaseOrdinal(): number | null {
		if (typeof window === 'undefined') return null;
		const raw = new URLSearchParams(window.location.search).get('case');
		if (raw === null || !/^\d+$/.test(raw)) return null;
		const value = Number(raw);
		return Number.isSafeInteger(value) && value >= 0 ? value : null;
	}

	function syncCaseUrl(index: number) {
		if (typeof window === 'undefined') return;
		const params = new URLSearchParams(window.location.search);
		params.set('case', String(index));
		window.history.replaceState({}, '', `${window.location.pathname}?${params.toString()}`);
	}

	function selectCase(index: number) {
		if (index < 0 || index >= cases.length) return;
		selectedIndex = index;
		syncCaseUrl(index);
	}

	function rawReviewStatus(value: string | null): string {
		return value ?? 'absent in raw row';
	}

	async function loadOverlap() {
		try {
			const catalog = await getResearchDatasets<ResearchCatalogResponse>();
			overlap = catalog.overlap ?? [];
		} catch (error) {
			if (typeof console !== 'undefined') {
				console.warn('Dataset overlap unavailable:', error);
			}
		}
	}

	async function loadCases(revision: string) {
		const token = ++caseSequence;
		caseState = 'loading';
		casesError = '';
		try {
			const response = await getResearchDatasetCases<ResearchCatalogCasesResponse>(datasetId(), {
				revision,
				limit: 100,
				offset: 0
			});
			if (token !== caseSequence) return;
			cases = response.items;
			caseTotal = response.total;
			const requested = requestedCaseOrdinal();
			selectedIndex = requested !== null && requested < cases.length ? requested : 0;
			caseState = 'available';
		} catch (error) {
			if (token !== caseSequence) return;
			const message = error instanceof Error ? error.message : 'Case rows unavailable.';
			casesError = message;
			caseState = /catalog_revision_changed/.test(message) ? 'revision_changed' : 'error';
		}
	}

	async function loadEntry() {
		const token = ++entrySequence;
		loadState = 'loading';
		errorMessage = '';
		const id = datasetId();
		if (!id || !datasetIdPattern.test(id)) {
			loadState = 'missing';
			return;
		}
		try {
			const detail = await getResearchDataset<ResearchCatalogEntry>(id);
			if (token !== entrySequence) return;
			entry = detail;
			loadState = 'available';
			await loadOverlap();
			if (
				detail.availability === 'available' &&
				detail.case_projection === 'available' &&
				detail.revision_sha256
			) {
				await loadCases(detail.revision_sha256);
			} else {
				caseState = 'idle';
			}
		} catch (error) {
			if (token !== entrySequence) return;
			const message = error instanceof Error ? error.message : 'The dataset is unavailable.';
			errorMessage = message;
			loadState = isUnauthorized(message)
				? 'unauthorized'
				: /not_found/.test(message)
					? 'missing'
					: 'error';
		}
	}

	async function refreshDataset() {
		caseSequence += 1;
		cases = [];
		caseTotal = 0;
		selectedIndex = 0;
		await loadEntry();
	}

	onMount(() => {
		void loadEntry();
	});
</script>

<svelte:head>
	<title>{entry?.label ?? 'Dataset'} · Fieldnote</title>
</svelte:head>

<AppShell current="/research/datasets">
	<div class="dataset-page">
		<div class="breadcrumb-row">
			<a href="/research/datasets">← All datasets</a>
			<ResearchNav current="/research/datasets" />
		</div>

		{#if loadState === 'loading'}
			<div aria-busy="true">
				<LoadingSkeleton count={3} type="card" />
			</div>
		{:else if loadState === 'unauthorized'}
			<EmptyState
				title="Research access required"
				body="The dataset catalog needs the authenticated private-lab gateway."
			/>
			<a class="text-link" href="/ask">Back to Ask</a>
		{:else if loadState === 'missing'}
			<EmptyState
				title="Dataset not found"
				body="This logical catalog ID is not in the fixed allowlist. No source path was requested or opened."
			/>
			<a class="text-link" href="/research/datasets">Back to the catalog</a>
		{:else if loadState === 'error'}
			<EmptyState
				title="Dataset unavailable"
				body={errorMessage || 'The catalog entry could not be read safely.'}
			/>
			<a class="text-link" href="/research/datasets">Back to the catalog</a>
		{:else if loadState === 'available' && entry}
			<DatasetDetail {entry} {overlap} />

			{#if entry.case_projection === 'available'}
				<section class="case-panel" aria-labelledby="case-title">
					<div class="panel-heading">
						<div>
							<p class="eyebrow">Fixture case inspector</p>
							<h2 id="case-title">
								{entry.kind === 'conversation_fixture' ? 'Stored conversation' : 'Stored case'}
								{caseState === 'available' && cases.length > 0
									? ` ${selectedIndex + 1} of ${caseTotal}`
									: ''}
							</h2>
						</div>
						{#if caseState === 'available' && cases.length > 1}
							<div class="case-nav">
								<label for="case-select">Case</label>
								<select
									id="case-select"
									value={String(selectedIndex)}
									onchange={(event) => selectCase(Number(event.currentTarget.value))}
								>
									{#each cases as item, index}
										<option value={String(index)}>
											{index + 1}. {item.question ?? item.source_case_id ?? 'Stored case'}
										</option>
									{/each}
								</select>
								<button
									type="button"
									disabled={selectedIndex === 0}
									onclick={() => selectCase(selectedIndex - 1)}
								>
									Previous
								</button>
								<button
									type="button"
									disabled={selectedIndex >= cases.length - 1}
									onclick={() => selectCase(selectedIndex + 1)}
								>
									Next
								</button>
							</div>
						{/if}
					</div>

					{#if caseState === 'loading'}
						<LoadingSkeleton count={2} type="card" />
					{:else if caseState === 'revision_changed'}
						<div class="state-block" role="status">
							<h3>The source revision changed</h3>
							<p>
								The cases were requested against an older revision. The selection has been
								invalidated; refresh the dataset before inspecting case rows.
							</p>
							<button type="button" onclick={refreshDataset}>Refresh dataset</button>
						</div>
					{:else if caseState === 'error'}
						<div class="state-block" role="alert">
							<h3>Case rows unavailable</h3>
							<p>{casesError || 'The case projection could not be read.'}</p>
							<button type="button" onclick={refreshDataset}>Retry</button>
						</div>
					{:else if caseState === 'available' && selectedCase}
						<div class="case-grid">
							<article class="expected-panel" aria-labelledby="expected-title">
								<p class="eyebrow">Expected / fixture labels</p>
								<h3 id="expected-title">
									{selectedCase.question ??
										(entry.kind === 'conversation_fixture'
											? 'Stored conversation turns'
											: 'Stored case')}
								</h3>
								<p class="fixture-note">
									Real public fixture content. These tokens are test expectations, not an
									answer, clinical threshold or verified evidence passage.
								</p>

								{#if entry.kind === 'conversation_fixture' && selectedCase.stored_turns}
									<ol class="turn-list">
										{#each selectedCase.stored_turns as turn, index}
											<li>
												<span class="turn-role">{turn.role ?? 'role not recorded'}</span>
												<p>{turn.content ?? 'Content not recorded'}</p>
												{#if index === 0}
													<span class="turn-note">First stored turn in this conversation</span>
												{/if}
											</li>
										{/each}
									</ol>
								{:else}
									<dl class="expectation-grid">
										<div>
											<dt>Expected source label</dt>
											<dd>{selectedCase.expected_source_labels?.join(', ') || 'Not recorded'}</dd>
										</div>
										<div>
											<dt>Expected lexical terms</dt>
											<dd>{selectedCase.expected_keywords?.join(' · ') || 'Not recorded'}</dd>
										</div>
									</dl>
								{/if}

								<ul class="case-meta">
									<li>Split: {selectedCase.split ?? 'not recorded'}</li>
									<li>Difficulty: {selectedCase.difficulty ?? 'not recorded'}</li>
									<li>Category: {selectedCase.query_category ?? 'not recorded'}</li>
									<li>Source family: {selectedCase.source_family ?? 'not recorded'}</li>
									<li>Topic: {selectedCase.topic ?? 'not recorded'}</li>
									<li>Label confidence: {selectedCase.label_confidence ?? 'not recorded'}</li>
									<li>Raw review status: {rawReviewStatus(selectedCase.raw_review_status)}</li>
								</ul>
								<p class="id-note">
									Locator: revision {selectedCase.locator.revision_sha256.slice(0, 12)}… ·
									ordinal {selectedCase.locator.source_ordinal}. Ordinals are valid only inside
									this exact revision.
								</p>
							</article>

							<article class="observed-panel" aria-labelledby="observed-title">
								<p class="eyebrow">Observed / selected archive</p>
								<h3 id="observed-title">Per-case results are not available.</h3>
								<p>
									The archived report contains aggregate metrics only. Its referenced case-run
									directory is absent or not exposed, so ranks, generated answers, judge reasons
									and call traces are not reconstructed.
								</p>
								<p class="binding-note">
									historical_binding = not_established · reason = case_records_unavailable
								</p>
								<p class="observed-warning">Not recorded here ≠ test failure.</p>
								<a class="text-link" href="/research/evaluations">Inspect aggregate coverage</a>
								<p class="id-note">
									Dataset revision {entry.revision_sha256?.slice(0, 12) ?? 'N/A'}… is not joined
									to an archived run by ordinal or question text.
								</p>
							</article>
						</div>
					{:else}
						<div class="state-block" role="status">
							<h3>No case rows available</h3>
							<p>The catalog reports no inspectable case projection for this revision.</p>
						</div>
					{/if}
				</section>
			{/if}

			{#if entry.catalog_id === 'd11-index'}
				<div class="next-links">
					<a href="/evidence">Open the indexed evidence browser</a>
					<a href="/research/evaluations">Inspect archived coverage</a>
				</div>
			{/if}
		{/if}
	</div>
</AppShell>

<style>
	.dataset-page {
		display: flex;
		flex-direction: column;
		gap: 1.25rem;
	}

	.breadcrumb-row {
		display: flex;
		flex-wrap: wrap;
		align-items: center;
		gap: 1rem;
	}

	.breadcrumb-row > a {
		color: var(--teal);
		font-weight: 700;
		text-underline-offset: 2px;
	}

	.case-panel {
		padding: 1.5rem;
		border: 1px solid var(--border-color);
		border-radius: 12px;
		background: #fffdf8;
	}

	.panel-heading {
		display: flex;
		flex-wrap: wrap;
		align-items: flex-start;
		justify-content: space-between;
		gap: 0.8rem;
		margin-bottom: 1rem;
	}

	.panel-heading > div:first-child {
		min-width: 0;
	}

	.eyebrow {
		margin: 0 0 0.4rem;
		color: var(--muted-color);
		font-size: 0.68rem;
		font-weight: 700;
		letter-spacing: 0.14em;
		text-transform: uppercase;
	}

	h2 {
		margin: 0;
		font-size: 1.4rem;
	}

	.case-nav {
		display: flex;
		flex: 1 1 320px;
		flex-wrap: wrap;
		align-items: center;
		gap: 0.4rem;
		min-width: 0;
	}

	.case-nav label {
		color: var(--muted-color);
		font-size: 0.75rem;
		font-weight: 700;
	}

	.case-nav select {
		flex: 1 1 220px;
		width: auto;
		min-width: 0;
		max-width: 320px;
		min-height: 40px;
		padding: 0.3rem 0.5rem;
		border: 1px solid var(--border-color);
		border-radius: 6px;
		background: var(--paper);
		color: var(--ink);
	}

	button {
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

	button:hover:not(:disabled) {
		border-color: var(--teal);
	}

	button:disabled {
		opacity: 0.45;
		cursor: default;
	}

	.case-grid {
		display: grid;
		grid-template-columns: minmax(0, 1.1fr) minmax(0, 0.9fr);
		gap: 1rem;
	}

	.expected-panel,
	.observed-panel {
		padding: 1.1rem;
		border: 1px solid var(--border-color);
		border-radius: 10px;
	}

	.expected-panel {
		background: #fffdf8;
	}

	.observed-panel {
		background: var(--surface-subtle);
	}

	h3 {
		margin: 0 0 0.6rem;
		font-size: 1.2rem;
	}

	.fixture-note,
	.observed-panel p {
		margin: 0 0 0.7rem;
		color: var(--secondary);
		font-size: 0.85rem;
	}

	.expectation-grid {
		display: grid;
		grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
		gap: 0.8rem;
		margin: 0 0 0.9rem;
	}

	dt {
		color: var(--muted-color);
		font-size: 0.68rem;
		letter-spacing: 0.06em;
		text-transform: uppercase;
	}

	dd {
		margin: 0.15rem 0 0;
		color: var(--ink);
		font-size: 0.9rem;
	}

	.case-meta {
		display: flex;
		flex-wrap: wrap;
		gap: 0.35rem;
		margin: 0 0 0.7rem;
		padding: 0;
		list-style: none;
	}

	.case-meta li {
		padding: 0.2rem 0.45rem;
		border: 1px solid var(--border-color);
		border-radius: 4px;
		color: var(--secondary);
		font-size: 0.74rem;
	}

	.turn-list {
		display: flex;
		flex-direction: column;
		gap: 0.6rem;
		margin: 0 0 0.9rem;
		padding: 0;
		list-style: none;
	}

	.turn-list li {
		padding: 0.7rem;
		border-left: 3px solid var(--border-color);
		background: var(--surface-subtle);
	}

	.turn-role {
		color: var(--muted-color);
		font-size: 0.68rem;
		font-weight: 700;
		letter-spacing: 0.06em;
		text-transform: uppercase;
	}

	.turn-list p {
		margin: 0.2rem 0;
		font-size: 0.9rem;
	}

	.turn-note {
		color: var(--teal);
		font-size: 0.72rem;
	}

	.binding-note {
		font-family: monospace;
		font-size: 0.74rem !important;
		overflow-wrap: anywhere;
	}

	.observed-warning {
		color: var(--rust) !important;
		font-weight: 700;
	}

	.id-note {
		margin: 0.7rem 0 0;
		color: var(--muted-color);
		font-family: monospace;
		font-size: 0.7rem;
		overflow-wrap: anywhere;
	}

	.state-block {
		padding: 1rem;
		border: 1px dashed var(--border-color);
		border-radius: 8px;
		background: var(--surface-subtle);
	}

	.state-block h3 {
		margin: 0 0 0.4rem;
		font-size: 1.05rem;
	}

	.state-block p {
		margin: 0 0 0.7rem;
		color: var(--secondary);
		font-size: 0.86rem;
	}

	.text-link {
		color: var(--teal);
		font-weight: 700;
		text-underline-offset: 2px;
	}

	.next-links {
		display: flex;
		flex-wrap: wrap;
		gap: 1rem;
	}

	.next-links a {
		color: var(--teal);
		font-weight: 700;
	}

	@media (max-width: 900px) {
		.case-grid {
			grid-template-columns: 1fr;
		}
	}

	@media (max-width: 640px) {
		.case-panel {
			padding: 1rem;
		}

		.case-nav select {
			flex-basis: 100%;
			width: 100%;
			max-width: 100%;
		}
	}
</style>
