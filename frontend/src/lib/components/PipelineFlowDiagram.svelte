<script lang="ts">
	import type { PipelineTrace } from '$lib/types';
	import { getStageStatus } from '$lib/confidenceCalculator';
	import FlowNode from './FlowNode.svelte';

	type Props = {
		pipeline: PipelineTrace;
		activeStage?: 'retrieval' | 'context' | 'generation' | null;
		onNodeClick?: (stage: 'retrieval' | 'context' | 'generation') => void;
	};

	let { pipeline, activeStage = null, onNodeClick }: Props = $props();

	const stageStatus = $derived(getStageStatus(pipeline.retrieval, pipeline.context, pipeline.generation));

	const stages = $derived([
		{
			id: 'retrieval' as const,
			title: 'Retrieval',
			status: stageStatus.retrieval,
			timing: pipeline.retrieval.timing_ms,
			details: `${pipeline.retrieval.documents.length} documents found`,
			description: 'Searches for relevant documents based on your question'
		},
		{
			id: 'context' as const,
			title: 'Context',
			status: stageStatus.context,
			timing: undefined,
			details: `${pipeline.context.total_chunks} chunks assembled`,
			description: 'Compiles retrieved content into context for the AI'
		},
		{
			id: 'generation' as const,
			title: 'Generation',
			status: stageStatus.generation,
			timing: pipeline.generation.timing_ms,
			details: `Generated using ${pipeline.generation.model}`,
			description: 'AI generates the final answer based on context'
		}
	]);

	function handleNodeClick(stage: 'retrieval' | 'context' | 'generation') {
		if (onNodeClick) {
			onNodeClick(stage);
		}
	}
</script>

<div class="flow-diagram">
	<div class="flow-container">
		{#each stages as stage, index}
			<FlowNode
				title={stage.title}
				status={stage.status}
				timing={stage.timing}
				active={activeStage === stage.id}
				details={stage.details}
				onclick={() => handleNodeClick(stage.id)}
			/>
			{#if index < stages.length - 1}
				<div class="flow-arrow" class:active={activeStage === stage.id || activeStage === stages[index + 1].id}>
					<svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
						<path d="M5 12H19M19 12L12 5M19 12L12 19" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
					</svg>
					<div class="flow-particles">
						<span class="particle"></span>
						<span class="particle"></span>
						<span class="particle"></span>
					</div>
				</div>
			{/if}
		{/each}
	</div>
	
	<div class="stage-descriptions">
		{#each stages as stage}
			<div class="description" class:active={activeStage === stage.id}>
				<span class="desc-title">{stage.title}:</span>
				<span class="desc-text">{stage.description}</span>
			</div>
		{/each}
	</div>
</div>

<style>
	.flow-diagram {
		padding: 1rem;
		background: linear-gradient(135deg, #f8fafc 0%, #f1f5f9 100%);
		border-radius: 12px;
		margin-bottom: 1rem;
	}

	.flow-container {
		display: flex;
		align-items: center;
		justify-content: center;
		gap: 0.5rem;
		flex-wrap: wrap;
	}

	.flow-arrow {
		display: flex;
		align-items: center;
		color: #94a3b8;
		transition: all 0.3s ease;
		position: relative;
		min-width: 40px;
	}

	.flow-arrow svg {
		width: 24px;
		height: 24px;
	}

	.flow-arrow.active {
		color: #3b82f6;
	}

	.flow-particles {
		position: absolute;
		left: 0;
		top: 50%;
		transform: translateY(-50%);
		width: 100%;
		height: 2px;
		overflow: hidden;
		opacity: 0;
	}

	.flow-arrow.active .flow-particles {
		opacity: 1;
	}

	.particle {
		position: absolute;
		width: 6px;
		height: 6px;
		background: #3b82f6;
		border-radius: 50%;
		animation: flowParticle 1.5s ease-in-out infinite;
	}

	.particle:nth-child(1) {
		left: 0;
		animation-delay: 0s;
	}

	.particle:nth-child(2) {
		left: 33%;
		animation-delay: 0.3s;
	}

	.particle:nth-child(3) {
		left: 66%;
		animation-delay: 0.6s;
	}

	@keyframes flowParticle {
		0% {
			transform: translateX(0);
			opacity: 0;
		}
		20% {
			opacity: 1;
		}
		80% {
			opacity: 1;
		}
		100% {
			transform: translateX(100%);
			opacity: 0;
		}
	}

	.stage-descriptions {
		display: flex;
		justify-content: center;
		gap: 1.5rem;
		margin-top: 1rem;
		flex-wrap: wrap;
	}

	.description {
		display: flex;
		flex-direction: column;
		align-items: center;
		gap: 0.25rem;
		font-size: 0.75rem;
		color: #6b7280;
		transition: all 0.3s ease;
		opacity: 0.6;
	}

	.description.active {
		opacity: 1;
		color: #1f2937;
	}

	.desc-title {
		font-weight: 600;
		color: #374151;
	}

	@media (max-width: 640px) {
		.flow-container {
			flex-direction: column;
			gap: 0.75rem;
		}

		.flow-arrow {
			transform: rotate(90deg);
		}

		.stage-descriptions {
			flex-direction: column;
			gap: 0.5rem;
			align-items: flex-start;
		}

		.description {
			flex-direction: row;
			gap: 0.5rem;
		}
	}
</style>
