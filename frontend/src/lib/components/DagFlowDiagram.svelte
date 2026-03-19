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

	const getIncomingConnections = (stageId: string): DagConnection[] => {
		return connections.filter(c => c.to === stageId);
	};

	const isRoot = (stageId: string): boolean => {
		return !connections.some(c => c.to === stageId);
	};

	const isLeaf = (stageId: string): boolean => {
		return !connections.some(c => c.from === stageId);
	};

	const getLevel = (stageId: string): number => {
		const visited = new Set<string>();
		const queue: Array<{ id: string; level: number }> = [{ id: stageId, level: 0 }];
		
		while (queue.length > 0) {
			const { id, level } = queue.shift()!;
			if (visited.has(id)) continue;
			visited.add(id);
			
			const outgoing = getConnectedStages(id);
			for (const nextId of outgoing) {
				if (!visited.has(nextId)) {
					queue.push({ id: nextId, level: level + 1 });
				}
			}
		}
		return 0;
	};

	const sortedStages = $derived(() => {
		const result: DagStage[] = [];
		const visited = new Set<string>();
		
		const roots = stages.filter(s => isRoot(s.id));
		const visit = (stage: DagStage) => {
			if (visited.has(stage.id)) return;
			visited.add(stage.id);
			result.push(stage);
			for (const nextId of getConnectedStages(stage.id)) {
				const nextStage = stageMap.get(nextId);
				if (nextStage) visit(nextStage);
			}
		};
		
		for (const root of roots) {
			visit(root);
		}
		
		for (const stage of stages) {
			if (!visited.has(stage.id)) result.push(stage);
		}
		
		return result;
	});

	const stagesByLevel = $derived(() => {
		const levels = new Map<number, DagStage[]>();
		
		for (const stage of stages) {
			let level = 0;
			const incoming = getIncomingConnections(stage.id);
			if (incoming.length > 0) {
				level = Math.max(...incoming.map(conn => {
					const fromStage = stageMap.get(conn.from);
					return fromStage ? sortedStages().indexOf(fromStage) : 0;
				})) + 1;
			}
			
			if (!levels.has(level)) levels.set(level, []);
			levels.get(level)!.push(stage);
		}
		
		return Array.from(levels.entries()).sort((a, b) => a[0] - b[0]).map(([_, s]) => s);
	});

	function getConnectionPath(fromId: string, toId: string): string {
		return `M0,20 H40`;
	}
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
						<div class="dag-connector horizontal">
							<svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
								<path d="M5 12H19M19 12L12 5M19 12L12 19" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
							</svg>
						</div>
					{/if}
				{/each}
			</div>
			{#if levelIndex < stagesByLevel().length - 1}
				<div class="dag-connector vertical">
					<svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
						<path d="M12 5V19M12 19L5 12M12 19L19 12" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
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

	.dag-connector.horizontal {
		width: 24px;
		height: 24px;
	}

	.dag-connector.vertical {
		width: 24px;
		height: 24px;
		transform: rotate(90deg);
	}

	.dag-connector svg {
		width: 20px;
		height: 20px;
	}

	@media (max-width: 768px) {
		.dag-level {
			flex-direction: column;
		}

		.dag-connector.vertical {
			transform: rotate(0deg);
		}
	}
</style>
