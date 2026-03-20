<script lang="ts">
	import type { PipelineTrace, RetrievedDocument } from '$lib/types';
	import { calculateConfidence, getStageStatus } from '$lib/confidenceCalculator';
	import { formatScore } from '$lib/utils/format';
	import StepCard from './StepCard.svelte';
	import ConfidenceBadge from './ConfidenceBadge.svelte';
	import MetricBar from './MetricBar.svelte';
	import SourceQualityIndicator from './SourceQualityIndicator.svelte';
	import DocumentInspector from './DocumentInspector.svelte';
	import PipelineFlowDiagram from './PipelineFlowDiagram.svelte';

	let { pipeline, isOpen = $bindable(false) }: { pipeline: PipelineTrace; isOpen?: boolean } = $props();

	const confidence = $derived(calculateConfidence(pipeline));
	const stageStatus = $derived(getStageStatus(pipeline.retrieval, pipeline.context, pipeline.generation));

	let selectedDocument: RetrievedDocument | null = $state(null);
	let activeFlowStage: 'retrieval' | 'context' | 'generation' | null = $state(null);

	const statusIcons = {
		success: '✓',
		warning: '⚠',
		error: '✗'
	};

	function handleFlowNodeClick(stage: 'retrieval' | 'context' | 'generation') {
		activeFlowStage = activeFlowStage === stage ? null : stage;
	}
</script>

{#if isOpen}
	<aside class="pipeline-panel">
		<div class="panel-header">
			<h2>Pipeline Details</h2>
			<button class="close-btn" onclick={() => (isOpen = false)} aria-label="Close panel">
				×
			</button>
		</div>

		<div class="confidence-header">
			<span class="confidence-label">Overall Confidence:</span>
			<ConfidenceBadge level={confidence.level} score={confidence.overall} />
			<div class="confidence-breakdown">
				<MetricBar label="Retrieval" value={confidence.breakdown.retrieval} compact />
				<MetricBar label="Sources" value={confidence.breakdown.sourceQuality} compact />
				<MetricBar label="Context" value={confidence.breakdown.contextRelevance} compact />
				<MetricBar label="Generation" value={confidence.breakdown.generationSuccess} compact />
			</div>
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
	</aside>
{/if}

{#if selectedDocument}
	<DocumentInspector 
		document={selectedDocument} 
		query={pipeline.retrieval.query}
		onclose={() => selectedDocument = null} 
	/>
{/if}

<style>
	.pipeline-panel {
		position: fixed;
		right: 0;
		top: 0;
		height: 100vh;
		width: 450px;
		background: white;
		border-left: 1px solid #ddd;
		box-shadow: -2px 0 8px rgba(0, 0, 0, 0.1);
		z-index: 1000;
		display: flex;
		flex-direction: column;
		animation: slideIn 0.3s ease-out;
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
		border-bottom: 1px solid #eee;
		background: #f9f9f9;
	}

	.panel-header h2 {
		margin: 0;
		font-size: 1.2rem;
		color: #333;
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
		color: #666;
	}

	.close-btn:hover {
		background: #e0e0e0;
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
		color: #888;
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
		color: #2196f3;
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
		background: #2196f3;
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
		background: #4caf50;
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
			width: 350px;
		}
	}

	@media (max-width: 768px) {
		.pipeline-panel {
			width: 100%;
		}
	}
</style>
