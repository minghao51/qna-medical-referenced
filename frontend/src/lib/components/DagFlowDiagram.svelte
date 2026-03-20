<script lang="ts">
	import FlowNode from './FlowNode.svelte';

	export type DagStage = {
		id: string;
		title: string;
		description?: string;
		status?: 'success' | 'warning' | 'error' | 'pending';
		timing?: number;
		details?: string;
	};

	export type DagConnection = {
		from: string;
		to: string;
		label?: string;
	};

	export type DagBranch = {
		name: string;
		stages: DagStage[];
	};

	type Props = {
		title?: string;
		stages: DagStage[];
		connections?: DagConnection[];
		layout?: 'horizontal' | 'vertical';
	};

	let { title, stages, connections = [], layout = 'horizontal' }: Props = $props();

	const stageMap = $derived(new Map(stages.map(s => [s.id, s])));

	const getConnectedStages = (stageId: string): string[] => {
		return connections
			.filter(c => c.from === stageId)
			.map(c => c.to);
	};

	const stagesByLevel = $derived(() => {
		const levels = new Map<number, DagStage[]>();
		
		for (const stage of stages) {
			const incoming = connections.filter(c => c.to === stage.id);
			const level = incoming.length > 0 ? 1 : 0;
			
			if (!levels.has(level)) levels.set(level, []);
			levels.get(level)!.push(stage);
		}
		
		return Array.from(levels.entries()).sort((a, b) => a[0] - b[0]).map(([_, s]) => s);
	});
</script>

<div class="dag-container" class:vertical={layout === 'vertical'}>
	{#if title}
		<h3 class="dag-title">{title}</h3>
	{/if}
	
	<div class="dag-flow">
		{#each stagesByLevel() as levelStages, levelIndex}
			<div class="dag-level">
				{#each levelStages as stage, stageIndex}
					<div class="dag-stage-wrapper">
						<FlowNode
							title={stage.title}
							status={stage.status || 'pending'}
							timing={stage.timing}
							details={stage.details || stage.description}
						/>
						{#if stage.description && !stage.details}
							<p class="stage-desc">{stage.description}</p>
						{/if}
					</div>
					{#if stageIndex < levelStages.length - 1}
						<div class="dag-connector parallel">
							<span class="parallel-label">│</span>
						</div>
					{/if}
				{/each}
			</div>
			{#if levelIndex < stagesByLevel().length - 1}
				<div class="dag-connector vertical">
					<svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
						<path d="M12 5V19M12 19L19 12" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
					</svg>
				</div>
			{/if}
		{/each}
	</div>
</div>

<style>
	.dag-container {
		padding: 1.5rem;
		background: linear-gradient(135deg, #f8fafc 0%, #f1f5f9 100%);
		border-radius: 12px;
		margin-bottom: 1.5rem;
	}

	.dag-title {
		font-size: 1.1rem;
		font-weight: 600;
		color: #1f2937;
		margin-bottom: 1rem;
		padding-bottom: 0.5rem;
		border-bottom: 2px solid #e5e7eb;
	}

	.dag-flow {
		display: flex;
		flex-direction: column;
		gap: 0.75rem;
		align-items: center;
	}

	.dag-level {
		display: flex;
		align-items: center;
		gap: 0.5rem;
		flex-wrap: wrap;
		justify-content: center;
	}

	.dag-stage-wrapper {
		display: flex;
		flex-direction: column;
		align-items: center;
		gap: 0.25rem;
	}

	.stage-desc {
		font-size: 0.7rem;
		color: #6b7280;
		text-align: center;
		max-width: 120px;
		margin: 0;
	}

	.dag-connector {
		display: flex;
		align-items: center;
		justify-content: center;
		color: #94a3b8;
		flex-shrink: 0;
	}

	.dag-connector.vertical {
		width: 24px;
		height: 24px;
	}

	.dag-connector.parallel {
		display: flex;
		flex-direction: column;
		align-items: center;
		justify-content: center;
		width: 32px;
		height: 100%;
		color: #cbd5e1;
	}

	.parallel-label {
		font-size: 1.5rem;
		font-weight: 300;
		line-height: 1;
	}

	.dag-connector svg {
		width: 20px;
		height: 20px;
	}

	@media (max-width: 768px) {
		.dag-level {
			flex-direction: column;
		}

		.dag-connector.parallel {
			display: none;
		}
	}
</style>
