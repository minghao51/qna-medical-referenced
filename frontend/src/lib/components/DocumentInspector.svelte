<script lang="ts">
	import { onMount } from 'svelte';
	import type { RetrievedDocument } from '$lib/types';
	import { getDomainType, getDomainCredibilityScore } from '$lib/confidenceCalculator';
	import SourceQualityIndicator from './SourceQualityIndicator.svelte';
	import MetricBar from './MetricBar.svelte';

	type Props = {
		document: RetrievedDocument;
		query: string;
		onclose: () => void;
	};

	let { document, query, onclose }: Props = $props();

	const domainType = $derived(getDomainType(document.source));
	const credibilityScore = $derived(getDomainCredibilityScore(domainType));
	const safeSourceUrl = $derived(getSafeExternalUrl(document.source));

	function formatScore(score: number): string {
		return (score * 100).toFixed(1);
	}

	function getRelevantSnippets(content: string, query: string): string[] {
		if (!query || !content) return [];
		const queryLower = query.toLowerCase();
		const contentLower = content.toLowerCase();
		const snippets: string[] = [];
		
		const words = queryLower.split(/\s+/).filter(w => w.length > 2);
		words.forEach(word => {
			let idx = contentLower.indexOf(word);
			if (idx !== -1) {
				const start = Math.max(0, idx - 50);
				const end = Math.min(content.length, idx + word.length + 100);
				snippets.push(content.slice(start, end));
			}
		});
		
		return snippets.slice(0, 3);
	}

	function getSafeExternalUrl(url: string): string | null {
		try {
			const parsed = new URL(url);
			if (parsed.protocol === 'http:' || parsed.protocol === 'https:') {
				return parsed.toString();
			}
			return null;
		} catch {
			return null;
		}
	}

	const relevantSnippets = $derived(getRelevantSnippets(document.content, query));

	onMount(() => {
		const handleKeydown = (event: KeyboardEvent) => {
			if (event.key === 'Escape') {
				onclose();
			}
		};
		window.addEventListener('keydown', handleKeydown);
		return () => {
			window.removeEventListener('keydown', handleKeydown);
		};
	});
</script>

<div
	class="modal-overlay"
	onclick={(event) => event.target === event.currentTarget && onclose()}
	onkeydown={(event) => (event.key === 'Escape' || event.key === 'Enter') && onclose()}
	role="button"
	tabindex="0"
	aria-label="Close modal"
>
	<div
		class="modal-content"
		role="dialog"
		aria-modal="true"
		aria-labelledby="document-inspector-title"
		tabindex="-1"
	>
		<div class="modal-header">
			<div class="modal-title">
				<span class="doc-rank">#{document.rank}</span>
				<h3 id="document-inspector-title">Document Details</h3>
			</div>
			<button class="close-btn" onclick={onclose} aria-label="Close">
				×
			</button>
		</div>

		<div class="modal-body">
			<div class="metadata-section">
				<div class="meta-row">
					<span class="meta-label">Source:</span>
					<span class="meta-value">
						<SourceQualityIndicator source={document.source} />
						{#if safeSourceUrl}
							<a href={safeSourceUrl} target="_blank" rel="noopener noreferrer" class="source-link">
								{document.source}
							</a>
						{:else}
							<span class="source-link invalid-source">{document.source}</span>
						{/if}
					</span>
				</div>
				{#if document.page}
					<div class="meta-row">
						<span class="meta-label">Page:</span>
						<span class="meta-value">{document.page}</span>
					</div>
				{/if}
				<div class="meta-row">
					<span class="meta-label">Domain Type:</span>
					<span class="meta-value">{domainType} (credibility: {credibilityScore}%)</span>
				</div>
			</div>

			<div class="scores-section">
				<h4>Retrieval Scores</h4>
				<div class="scores-grid">
					<div class="score-item">
						<MetricBar 
							label="Combined" 
							value={Math.round(document.combined_score * 100)} 
							color="blue"
						/>
					</div>
					<div class="score-item">
						<MetricBar 
							label="Semantic" 
							value={Math.round(document.semantic_score * 100)} 
						/>
					</div>
					<div class="score-item">
						<MetricBar 
							label="Keyword" 
							value={Math.round(document.keyword_score * 100)} 
						/>
					</div>
					<div class="score-item">
						<MetricBar 
							label="Source Boost" 
							value={Math.round(document.source_boost * 100)} 
						/>
					</div>
				</div>
			</div>

			<div class="why-section">
				<h4>Why was this document retrieved?</h4>
				<div class="why-explanation">
					<p>
						<strong>Semantic Match ({formatScore(document.semantic_score)}%):</strong>
						How well the document's meaning matches your query conceptually, using embeddings.
					</p>
					<p>
						<strong>Keyword Match ({formatScore(document.keyword_score)}%):</strong>
						How many keywords from your query appear in this document.
					</p>
					<p>
						<strong>Source Credibility ({formatScore(document.source_boost)}%):</strong>
						Trust score based on the domain type ({domainType}).
					</p>
				</div>
			</div>

			{#if relevantSnippets.length > 0}
				<div class="snippets-section">
					<h4>Relevant Passages</h4>
					{#each relevantSnippets as snippet}
						<div class="snippet">
							"...{snippet}..."
						</div>
					{/each}
				</div>
			{/if}

			<div class="content-section">
				<h4>Full Content</h4>
				<pre class="content-full">{document.content}</pre>
			</div>
		</div>

		<div class="modal-footer">
			<button class="close-btn-large" onclick={onclose}>Close</button>
		</div>
	</div>
</div>

<style>
	.modal-overlay {
		position: fixed;
		top: 0;
		left: 0;
		right: 0;
		bottom: 0;
		background: rgba(0, 0, 0, 0.5);
		display: flex;
		align-items: center;
		justify-content: center;
		z-index: 2000;
		animation: fadeIn 0.2s ease;
	}

	@keyframes fadeIn {
		from { opacity: 0; }
		to { opacity: 1; }
	}

	.modal-content {
		background: white;
		border-radius: 12px;
		width: 90%;
		max-width: 700px;
		max-height: 85vh;
		display: flex;
		flex-direction: column;
		box-shadow: 0 20px 60px rgba(0, 0, 0, 0.3);
		animation: slideUp 0.3s ease;
	}

	@keyframes slideUp {
		from { transform: translateY(20px); opacity: 0; }
		to { transform: translateY(0); opacity: 1; }
	}

	.modal-header {
		display: flex;
		justify-content: space-between;
		align-items: center;
		padding: 1rem 1.5rem;
		border-bottom: 1px solid #e2e8f0;
	}

	.modal-title {
		display: flex;
		align-items: center;
		gap: 0.75rem;
	}

	.modal-title h3 {
		margin: 0;
		font-size: 1.25rem;
		color: #1e293b;
	}

	.doc-rank {
		background: #2196f3;
		color: white;
		padding: 0.25rem 0.5rem;
		border-radius: 4px;
		font-size: 0.85rem;
		font-weight: 600;
	}

	.close-btn {
		background: none;
		border: none;
		font-size: 1.5rem;
		cursor: pointer;
		padding: 0.25rem;
		color: #64748b;
		line-height: 1;
	}

	.close-btn:hover {
		color: #1e293b;
	}

	.modal-body {
		flex: 1;
		overflow-y: auto;
		padding: 1.5rem;
	}

	.metadata-section {
		margin-bottom: 1.5rem;
		padding: 1rem;
		background: #f8fafc;
		border-radius: 8px;
	}

	.meta-row {
		display: flex;
		gap: 0.75rem;
		margin-bottom: 0.5rem;
		font-size: 0.9rem;
	}

	.meta-row:last-child {
		margin-bottom: 0;
	}

	.meta-label {
		font-weight: 600;
		color: #475569;
		min-width: 120px;
	}

	.meta-value {
		color: #1e293b;
		display: flex;
		align-items: center;
		gap: 0.5rem;
	}

	.source-link {
		color: #2563eb;
		text-decoration: none;
		word-break: break-all;
	}

	.source-link.invalid-source {
		color: #64748b;
		text-decoration: none;
	}

	.source-link:hover {
		text-decoration: underline;
	}

	.scores-section,
	.why-section,
	.snippets-section,
	.content-section {
		margin-bottom: 1.5rem;
	}

	h4 {
		margin: 0 0 0.75rem 0;
		font-size: 1rem;
		color: #334155;
	}

	.scores-grid {
		display: grid;
		grid-template-columns: 1fr 1fr;
		gap: 0.75rem;
	}

	.why-explanation {
		background: #f0f9ff;
		border: 1px solid #bae6fd;
		border-radius: 8px;
		padding: 1rem;
	}

	.why-explanation p {
		margin: 0 0 0.5rem 0;
		font-size: 0.9rem;
		color: #334155;
		line-height: 1.5;
	}

	.why-explanation p:last-child {
		margin-bottom: 0;
	}

	.snippet {
		background: #fef3c7;
		border-left: 3px solid #f59e0b;
		padding: 0.75rem;
		margin-bottom: 0.5rem;
		font-size: 0.85rem;
		color: #451a03;
		border-radius: 0 4px 4px 0;
	}

	.content-full {
		background: #f8fafc;
		border: 1px solid #e2e8f0;
		border-radius: 6px;
		padding: 1rem;
		font-size: 0.85rem;
		line-height: 1.6;
		white-space: pre-wrap;
		word-break: break-word;
		max-height: 300px;
		overflow-y: auto;
		margin: 0;
	}

	.modal-footer {
		padding: 1rem 1.5rem;
		border-top: 1px solid #e2e8f0;
		display: flex;
		justify-content: flex-end;
	}

	.close-btn-large {
		padding: 0.5rem 1.5rem;
		background: #f1f5f9;
		border: 1px solid #cbd5e1;
		border-radius: 6px;
		font-size: 0.9rem;
		cursor: pointer;
		color: #475569;
		transition: all 0.2s;
	}

	.close-btn-large:hover {
		background: #e2e8f0;
		color: #1e293b;
	}

	@media (max-width: 640px) {
		.modal-content {
			width: 95%;
			max-height: 90vh;
		}

		.scores-grid {
			grid-template-columns: 1fr;
		}
	}
</style>
