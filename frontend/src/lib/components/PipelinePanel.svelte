<script lang="ts">
	import { onMount } from 'svelte';
	import type { PipelineTrace, RetrievedDocument } from '$lib/types';
	import { getStageStatus } from '$lib/confidenceCalculator';
	import { formatScore } from '$lib/utils/format';
	import StepCard from './StepCard.svelte';
	import SourceQualityIndicator from './SourceQualityIndicator.svelte';
	import DocumentInspector from './DocumentInspector.svelte';
	import PipelineFlowDiagram from './PipelineFlowDiagram.svelte';

	let { pipeline, isOpen = $bindable(false) }: { pipeline: PipelineTrace; isOpen?: boolean } = $props();

	const stageStatus = $derived(getStageStatus(pipeline.retrieval, pipeline.context, pipeline.generation));

	let selectedDocument: RetrievedDocument | null = $state(null);
	let closeButton: HTMLButtonElement | undefined = $state();
	let panelElement: HTMLDialogElement | undefined = $state();
	let previousFocus: HTMLElement | null = null;
	let previousBodyOverflow = '';
	let activeFlowStage: 'retrieval' | 'context' | 'generation' | null = $state(null);
	let expandedStep: string | null = $state(null);

	const statusIcons = {
		success: '✓',
		warning: '⚠',
		error: '✗'
	};

	function handleFlowNodeClick(stage: 'retrieval' | 'context' | 'generation') {
		activeFlowStage = activeFlowStage === stage ? null : stage;
	}

	function detailList(step: { details: Record<string, unknown> }, key: string): string[] {
		const value = step.details[key];
		return Array.isArray(value) ? value.filter((item): item is string => typeof item === 'string') : [];
	}

	function detailValue(step: { details: Record<string, unknown> }, key: string): unknown {
		return step.details[key];
	}

	function closePanel() {
		isOpen = false;
		if (panelElement?.open) panelElement.close();
	}

	function handlePanelKeydown(event: KeyboardEvent) {
		if (selectedDocument) return;
		if (event.key === 'Escape') {
			event.preventDefault();
			closePanel();
			return;
		}
		if (event.key !== 'Tab' || !panelElement) return;
		const focusable = Array.from(
			panelElement.querySelectorAll<HTMLElement>(
				'button:not([disabled]), [href], input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])'
			)
		).filter((element) => element.getClientRects().length > 0);
		if (focusable.length === 0) return;
		const first = focusable[0];
		const last = focusable[focusable.length - 1];
		if (event.shiftKey) {
			if (document.activeElement === first || !panelElement.contains(document.activeElement)) {
				event.preventDefault();
				last.focus();
			}
			return;
		}
		if (document.activeElement === last) {
			event.preventDefault();
			first.focus();
		}
	}

	function handleBackdropClick(event: MouseEvent) {
		if (event.target === event.currentTarget) closePanel();
	}

	onMount(() => {
		previousFocus = document.activeElement instanceof HTMLElement ? document.activeElement : null;
		previousBodyOverflow = document.body.style.overflow;
		document.body.style.overflow = 'hidden';
		panelElement?.showModal();
		closeButton?.focus();
		window.addEventListener('keydown', handlePanelKeydown);
		return () => {
			window.removeEventListener('keydown', handlePanelKeydown);
			document.body.style.overflow = previousBodyOverflow;
			previousFocus?.focus();
		};
	});
</script>

{#if isOpen}
	<dialog
		bind:this={panelElement}
		class="pipeline-panel"
		aria-labelledby="pipeline-panel-title"
		aria-describedby="pipeline-panel-summary"
		onclose={() => (isOpen = false)}
		onclick={handleBackdropClick}
	>
		<div class="panel-header">
			<h2 id="pipeline-panel-title">Pipeline Details</h2>
			<button bind:this={closeButton} class="close-btn" onclick={closePanel} aria-label="Close panel">
				×
			</button>
		</div>

		<div class="recorded-summary" id="pipeline-panel-summary">
			<span class="recorded-label">Recorded pipeline evidence</span>
			<p>
				{pipeline.retrieval.documents.length} retrieved chunks ·
				{pipeline.context.total_chunks} context chunks ·
				{pipeline.total_time_ms} ms recorded total
			</p>
			<p class="recorded-note">
				Recorded RAG stages only. No medical-confidence score, provider-call tree or hidden
				reasoning is implied.
			</p>
		</div>

		<PipelineFlowDiagram
			pipeline={pipeline}
			activeStage={activeFlowStage}
			onNodeClick={handleFlowNodeClick}
		/>

		<div class="panel-content">
			<!-- Retrieval Stage -->
			<StepCard
				title="Retrieval"
				timing={pipeline.retrieval.timing_ms}
				expanded={activeFlowStage === 'retrieval' || activeFlowStage === null}
			>
				<div class="stage-header">
					<span class="stage-status status-{stageStatus.retrieval}" title="{stageStatus.retrieval}">
						{statusIcons[stageStatus.retrieval]}
					</span>
				</div>
				<div class="stage-details">
					<div class="detail-row">
						<span class="label">Query:</span>
						<span class="value">"{pipeline.retrieval.query}"</span>
					</div>
					<div class="detail-row">
						<span class="label">Documents Retrieved:</span>
						<span class="value">{pipeline.retrieval.documents.length}</span>
					</div>
					<div class="detail-row">
						<span class="label">Score Weights:</span>
						<span class="value">
							Semantic {formatScore(pipeline.retrieval.score_weights.semantic)}% |
							Keyword {formatScore(pipeline.retrieval.score_weights.keyword)}% |
							Source {formatScore(pipeline.retrieval.score_weights.source)}%
						</span>
					</div>

					{#if pipeline.retrieval.steps && pipeline.retrieval.steps.length > 0}
						<div class="steps-list">
							<h4>Retrieval Steps</h4>
							{#each pipeline.retrieval.steps as step}
								<div class="step-item-wrapper">
									<button
										class="step-item"
										class:skipped={step.skipped}
										class:expanded={expandedStep === step.name}
										onclick={() => expandedStep = expandedStep === step.name ? null : step.name}
										type="button"
									>
										<span class="step-name">{step.name.replace(/_/g, ' ')}</span>
										{#if step.skipped}
											<span class="step-status skipped">skipped</span>
										{:else}
											<span class="step-timing">{step.timing_ms}ms</span>
										{/if}
										{#if !step.skipped && step.details && Object.keys(step.details).length > 0}
											<span class="step-chevron" class:rotated={expandedStep === step.name}>▸</span>
										{/if}
									</button>
									{#if expandedStep === step.name && step.details}
										<div class="step-details">
											{#if detailList(step, 'expanded_queries').length > 0}
												<div class="detail-group">
													<span class="detail-label">Expanded Queries:</span>
													<ul class="query-list">
														{#each detailList(step, 'expanded_queries') as q, i}
															<li class="query-item" class:original={i === 0}>
																{q}
																{#if i === 0}<span class="query-tag">original</span>{/if}
															</li>
														{/each}
													</ul>
												</div>
											{/if}
											{#if detailValue(step, 'hyde_enabled') !== undefined}
												<div class="detail-row">
													<span class="detail-label">HyDE:</span>
													<span class="detail-value">{detailValue(step, 'hyde_enabled') ? 'enabled' : 'disabled'}</span>
												</div>
											{/if}
											{#if detailValue(step, 'queries_count') !== undefined}
												<div class="detail-row">
													<span class="detail-label">Query variants:</span>
													<span class="detail-value">{String(detailValue(step, 'queries_count'))}</span>
												</div>
											{/if}
											{#if typeof step.details.search_mode === 'string'}
												<div class="detail-row">
													<span class="detail-label">Search mode:</span>
													<span class="detail-value">{step.details.search_mode}</span>
												</div>
											{/if}
											{#if detailValue(step, 'mmr_lambda') !== undefined}
												<div class="detail-row">
													<span class="detail-label">MMR lambda:</span>
													<span class="detail-value">{String(detailValue(step, 'mmr_lambda'))}</span>
												</div>
											{/if}
											<details class="raw-details">
												<summary>Raw recorded fields</summary>
												<pre>{JSON.stringify(step.details, null, 2)}</pre>
											</details>
										</div>
									{/if}
								</div>
							{/each}
						</div>
					{/if}

					<div class="documents-list">
						<h4>Retrieved Documents <span class="hint">(click to inspect)</span></h4>
						{#each pipeline.retrieval.documents as doc}
							<button
								class="doc-item clickable"
								onclick={() => selectedDocument = doc}
								type="button"
							>
								<div class="doc-header">
									<span class="doc-rank">#{doc.rank}</span>
									<span class="doc-source">{doc.source}</span>
									<SourceQualityIndicator source={doc.source} />
									{#if doc.page}
										<span class="doc-page">Page {doc.page}</span>
									{/if}
									<span class="doc-score">{formatScore(doc.combined_score)}%</span>
								</div>
								<div class="doc-preview">{doc.content.slice(0, 150)}...</div>
								<div class="doc-scores">
									<div class="score-bar" title="How well this document semantically matches your query">
										<span class="score-label">Semantic:</span>
										<div class="bar-container">
											<div
												class="bar semantic"
												style="width: {formatScore(doc.semantic_score)}%"
											></div>
											<span class="score-value">{formatScore(doc.semantic_score)}%</span>
										</div>
									</div>
									<div class="score-bar" title="How many keywords from your query appear in this document">
										<span class="score-label">Keyword:</span>
										<div class="bar-container">
											<div
												class="bar keyword"
												style="width: {formatScore(doc.keyword_score)}%"
											></div>
											<span class="score-value">{formatScore(doc.keyword_score)}%</span>
										</div>
									</div>
									<div class="score-bar" title="Trust score based on domain type (gov, edu, org, com)">
										<span class="score-label">Boost:</span>
										<div class="bar-container">
											<div
												class="bar boost"
												style="width: {formatScore(doc.source_boost)}%"
											></div>
											<span class="score-value">{formatScore(doc.source_boost)}%</span>
										</div>
									</div>
								</div>
								<div class="why-hint">Why retrieved?</div>
							</button>
						{/each}
					</div>
				</div>
			</StepCard>

			<!-- Context Stage -->
			<StepCard
				title="Context Assembly"
				timing={0}
				expanded={activeFlowStage === 'context' || activeFlowStage === null}
			>
				<div class="stage-header">
					<span class="stage-status status-{stageStatus.context}" title="{stageStatus.context}">
						{statusIcons[stageStatus.context]}
					</span>
				</div>
				<div class="stage-details">
					<div class="detail-row">
						<span class="label">Total Chunks:</span>
						<span class="value">{pipeline.context.total_chunks}</span>
					</div>
					<div class="detail-row">
						<span class="label">Total Characters:</span>
						<span class="value">{pipeline.context.total_chars.toLocaleString()}</span>
					</div>
					<div class="detail-row">
						<span class="label">Sources:</span>
						<span class="value">{pipeline.context.sources.join(', ')}</span>
					</div>
					<div class="context-preview">
						<span class="label">Context Preview:</span>
						<p>{pipeline.context.preview}</p>
					</div>
				</div>
			</StepCard>

			<!-- Generation Stage -->
			<StepCard
				title="Generation"
				timing={pipeline.generation.timing_ms}
				expanded={activeFlowStage === 'generation' || activeFlowStage === null}
			>
				<div class="stage-header">
					<span class="stage-status status-{stageStatus.generation}" title="{stageStatus.generation}">
						{statusIcons[stageStatus.generation]}
					</span>
				</div>
				<div class="stage-details">
					<div class="detail-row">
						<span class="label">Model:</span>
						<span class="value">{pipeline.generation.model}</span>
					</div>
					<div class="detail-row">
						<span class="label">Generation Time:</span>
						<span class="value">{pipeline.generation.timing_ms}ms</span>
					</div>
					{#if pipeline.generation.tokens_estimate}
						<div class="detail-row">
							<span class="label">Estimated Tokens:</span>
							<span class="value">{pipeline.generation.tokens_estimate.toLocaleString()}</span>
						</div>
					{/if}
				</div>
			</StepCard>

			<!-- Total Time -->
			<div class="total-time">
				<strong>Total Pipeline Time:</strong> {pipeline.total_time_ms}ms
			</div>
		</div>

		{#if selectedDocument}
			<DocumentInspector
				document={selectedDocument}
				query={pipeline.retrieval.query}
				onclose={() => selectedDocument = null}
			/>
		{/if}
	</dialog>
{/if}

<style>
	.pipeline-panel {
		position: fixed;
		inset: 0 0 0 auto;
		width: min(480px, 100vw);
		max-width: none;
		height: 100dvh;
		max-height: 100dvh;
		margin: 0;
		padding: 0;
		border: none;
		border-left: 1px solid var(--border-color);
		background: #fffdf8;
		color: var(--ink);
		box-shadow: -12px 0 32px rgba(24, 45, 50, 0.18);
		animation: slideIn 0.3s ease-out;
	}

	.pipeline-panel[open] {
		display: flex;
		flex-direction: column;
	}

	.pipeline-panel::backdrop {
		background: rgba(24, 45, 50, 0.32);
	}

	@keyframes slideIn {
		from {
			transform: translateX(100%);
		}
		to {
			transform: translateX(0);
		}
	}

	.panel-header {
		display: flex;
		justify-content: space-between;
		align-items: center;
		padding: 1rem;
		border-bottom: 1px solid var(--border-color);
		background: var(--surface-subtle);
	}

	.panel-header h2 {
		margin: 0;
		font-size: 1.2rem;
		color: var(--ink);
	}

	.close-btn {
		background: none;
		border: none;
		font-size: 1.5rem;
		cursor: pointer;
		padding: 0;
		width: 32px;
		height: 32px;
		display: flex;
		align-items: center;
		justify-content: center;
		border-radius: 4px;
		color: var(--secondary);
	}

	.close-btn:hover {
		background: var(--surface-strong);
	}

	.panel-content {
		flex: 1;
		overflow-y: auto;
		padding: 1rem;
	}

	.stage-details {
		display: flex;
		flex-direction: column;
		gap: 0.75rem;
	}

	.detail-row {
		display: flex;
		justify-content: space-between;
		align-items: flex-start;
		gap: 0.5rem;
		font-size: 0.9rem;
	}

	.label {
		font-weight: 600;
		color: #555;
		flex-shrink: 0;
	}

	.value {
		color: #333;
		text-align: right;
		word-break: break-word;
	}

	.documents-list {
		margin-top: 1rem;
	}

	.documents-list h4 {
		margin: 0 0 0.75rem 0;
		font-size: 1rem;
		color: #333;
	}

	.documents-list .hint {
		font-size: 0.8rem;
		font-weight: normal;
		color: #4b5563;
	}

	.steps-list {
		margin-top: 1rem;
		padding: 0.75rem;
		background: #f9f9f9;
		border-radius: 6px;
	}

	.steps-list h4 {
		margin: 0 0 0.75rem 0;
		font-size: 0.9rem;
		color: #333;
		font-weight: 600;
	}

	.step-item {
		display: flex;
		justify-content: space-between;
		align-items: center;
		padding: 0.4rem 0.5rem;
		border-bottom: 1px solid #e5e7eb;
		font-size: 0.85rem;
		width: 100%;
		background: none;
		border-left: none;
		border-right: none;
		border-top: none;
		cursor: pointer;
		transition: background 0.2s ease;
	}

	.step-item:hover {
		background: rgba(59, 130, 246, 0.05);
	}

	.step-item.expanded {
		background: rgba(59, 130, 246, 0.08);
		border-bottom: none;
	}

	.step-item:last-child {
		border-bottom: none;
	}

	.step-item.skipped {
		opacity: 0.6;
	}

	.step-item-wrapper {
		border-bottom: 1px solid #e5e7eb;
	}

	.step-item-wrapper:last-child {
		border-bottom: none;
	}

	.step-name {
		text-transform: capitalize;
		color: #333;
	}

	.step-timing {
		font-family: monospace;
		color: #6b7280;
		font-weight: 500;
	}

	.step-status.skipped {
		color: #9ca3af;
		font-style: italic;
		font-size: 0.8rem;
	}

	.step-chevron {
		color: #9ca3af;
		font-size: 0.75rem;
		transition: transform 0.2s ease;
		margin-left: 0.5rem;
	}

	.step-chevron.rotated {
		transform: rotate(90deg);
	}

	.step-details {
		padding: 0.75rem;
		background: white;
		border: 1px solid #e5e7eb;
		border-top: none;
		margin-bottom: 0.5rem;
		border-radius: 0 0 4px 4px;
	}

	.detail-group {
		margin-bottom: 0.75rem;
	}

	.detail-group:last-child {
		margin-bottom: 0;
	}

	.detail-label {
		font-weight: 600;
		color: #555;
		font-size: 0.8rem;
		display: block;
		margin-bottom: 0.4rem;
	}

	.detail-row {
		display: flex;
		justify-content: space-between;
		font-size: 0.85rem;
		margin-bottom: 0.3rem;
	}

	.detail-value {
		color: #333;
		font-family: monospace;
	}

	.query-list {
		list-style: none;
		padding: 0;
		margin: 0.25rem 0 0 0;
	}

	.query-item {
		padding: 0.35rem 0.5rem;
		background: #f9f9f9;
		border-radius: 4px;
		margin-bottom: 0.3rem;
		font-size: 0.85rem;
		color: #333;
		display: flex;
		justify-content: space-between;
		align-items: center;
	}

	.query-item.original {
		border-left: 3px solid #3b82f6;
	}

	.query-tag {
		font-size: 0.7rem;
		background: #3b82f6;
		color: white;
		padding: 0.1rem 0.4rem;
		border-radius: 999px;
		font-weight: 600;
	}

	.doc-item {
		background: #f9f9f9;
		border: 1px solid #e0e0e0;
		border-radius: 6px;
		padding: 0.75rem;
		margin-bottom: 0.75rem;
		width: 100%;
		text-align: left;
		cursor: pointer;
		transition: all 0.2s ease;
	}

	.doc-item:hover {
		border-color: #2196f3;
		box-shadow: 0 2px 8px rgba(33, 150, 243, 0.15);
	}

	.doc-item.clickable {
		border-left: 3px solid #2196f3;
	}

	.doc-preview {
		font-size: 0.8rem;
		color: #666;
		margin: 0.5rem 0;
		line-height: 1.4;
	}

	.why-hint {
		font-size: 0.75rem;
		color: #1d4ed8;
		margin-top: 0.5rem;
		font-weight: 500;
	}

	.doc-header {
		display: flex;
		align-items: center;
		gap: 0.5rem;
		margin-bottom: 0.5rem;
		flex-wrap: wrap;
	}

	.doc-rank {
		background: #1d4ed8;
		color: white;
		padding: 0.2rem 0.5rem;
		border-radius: 3px;
		font-size: 0.8rem;
		font-weight: 600;
	}

	.doc-source {
		font-weight: 600;
		color: #333;
		flex: 1;
	}

	.doc-page {
		color: #666;
		font-size: 0.85rem;
	}

	.doc-score {
		background: #047857;
		color: white;
		padding: 0.2rem 0.5rem;
		border-radius: 3px;
		font-size: 0.85rem;
		font-weight: 600;
	}

	.doc-scores {
		display: flex;
		flex-direction: column;
		gap: 0.4rem;
		margin-bottom: 0.5rem;
	}

	.score-bar {
		display: flex;
		align-items: center;
		gap: 0.5rem;
		font-size: 0.85rem;
	}

	.score-label {
		min-width: 70px;
		color: #666;
	}

	.bar-container {
		flex: 1;
		display: flex;
		align-items: center;
		gap: 0.5rem;
		height: 20px;
	}

	.bar {
		height: 100%;
		border-radius: 3px;
		transition: width 0.3s ease;
		min-width: 2px;
	}

	.bar.semantic {
		background: linear-gradient(90deg, #2196f3, #64b5f6);
	}

	.bar.keyword {
		background: linear-gradient(90deg, #ff9800, #ffb74d);
	}

	.bar.boost {
		background: linear-gradient(90deg, #9c27b0, #ba68c8);
	}

	.score-value {
		min-width: 45px;
		text-align: right;
		font-weight: 600;
		color: #333;
	}

	.context-preview {
		margin-top: 0.5rem;
		padding: 0.75rem;
		background: #f9f9f9;
		border-radius: 4px;
	}

	.context-preview p {
		margin: 0.5rem 0 0 0;
		font-size: 0.85rem;
		color: #666;
		font-style: italic;
	}

	.total-time {
		margin-top: 1rem;
		padding: 1rem;
		background: #e3f2fd;
		border-radius: 6px;
		text-align: center;
		font-size: 1rem;
		color: #1976d2;
	}

	.recorded-summary {
		padding: 0.85rem 1rem;
		border-bottom: 1px solid var(--border-color);
		background: var(--surface-subtle);
	}

	.recorded-label {
		font-weight: 700;
		font-size: 0.9rem;
		color: #333;
	}

	.recorded-summary p {
		margin: 0.35rem 0 0;
		font-size: 0.85rem;
		color: #555;
	}

	.recorded-note {
		color: #6b7280 !important;
		font-size: 0.78rem !important;
	}

	.raw-details {
		margin-top: 0.5rem;
	}

	.raw-details summary {
		cursor: pointer;
		font-size: 0.78rem;
		font-weight: 600;
		color: #555;
	}

	.raw-details pre {
		max-height: 16rem;
		overflow: auto;
		margin: 0.4rem 0 0;
		padding: 0.5rem;
		background: #f3f4f6;
		font-size: 0.7rem;
		white-space: pre-wrap;
		overflow-wrap: anywhere;
	}

	.confidence-header {
		padding: 1rem;
		background: #f8fafc;
		border-bottom: 1px solid #e2e8f0;
		display: flex;
		flex-direction: column;
		gap: 0.75rem;
	}

	.confidence-label {
		font-weight: 600;
		color: #334155;
		font-size: 0.9rem;
	}

	.confidence-note {
		margin: -0.5rem 0 0;
		color: #64748b;
		font-size: 0.75rem;
	}

	.confidence-breakdown {
		display: flex;
		flex-direction: column;
		gap: 0.5rem;
		padding-top: 0.5rem;
		border-top: 1px solid #e2e8f0;
	}

	.stage-header {
		display: flex;
		justify-content: flex-end;
		margin-bottom: 0.5rem;
	}

	.stage-status {
		display: inline-flex;
		align-items: center;
		justify-content: center;
		width: 24px;
		height: 24px;
		border-radius: 50%;
		font-size: 0.75rem;
		font-weight: bold;
	}

	.stage-status.status-success {
		background: #dcfce7;
		color: #22c55e;
	}

	.stage-status.status-warning {
		background: #fef3c7;
		color: #f59e0b;
	}

	.stage-status.status-error {
		background: #fee2e2;
		color: #ef4444;
	}

	/* Responsive design */
	@media (max-width: 1024px) {
		.pipeline-panel {
			width: min(420px, 100vw);
		}
	}

	@media (max-width: 768px) {
		.pipeline-panel {
			width: 100vw;
			border-left: none;
		}
	}
</style>
