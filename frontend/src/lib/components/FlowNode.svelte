<script lang="ts">
	type Props = {
		title: string;
		status: 'success' | 'warning' | 'error' | 'pending';
		timing?: number;
		active?: boolean;
		skipped?: boolean;
		details?: string;
		onclick?: () => void;
	};

	let { title, status = 'pending', timing, active = false, skipped = false, details, onclick }: Props = $props();

	const statusConfig = {
		success: { color: '#22c55e', bgColor: '#dcfce7', icon: '✓' },
		warning: { color: '#f59e0b', bgColor: '#fef3c7', icon: '⚠' },
		error: { color: '#ef4444', bgColor: '#fee2e2', icon: '✗' },
		pending: { color: '#6b7280', bgColor: '#f3f4f6', icon: '○' }
	};

	const config = $derived(skipped ? statusConfig.pending : statusConfig[status]);

	function formatTiming(ms: number): string {
		if (ms < 1000) return `${ms}ms`;
		return `${(ms / 1000).toFixed(1)}s`;
	}

	function formatStepName(name: string): string {
		const names: Record<string, string> = {
			query_expansion: 'Query Expansion',
			semantic_search: 'Semantic Search',
			keyword_search: 'Keyword Search',
			score_fusion: 'Fusion',
			reranking: 'Reranking'
		};
		return names[name] || name;
	}
</script>

<button 
	class="flow-node" 
	class:active 
	class:skipped
	class:clickable={onclick !== undefined}
	onclick={onclick}
	type="button"
	style="--node-color: {config.color}; --node-bg: {config.bgColor};"
	title={details}
>
	<div class="node-icon">
		{skipped ? '○' : config.icon}
	</div>
	<div class="node-content">
		<span class="node-title">{formatStepName(title)}</span>
		{#if timing !== undefined && !skipped}
			<span class="node-timing">{formatTiming(timing)}</span>
		{:else if skipped}
			<span class="node-timing skipped-label">skipped</span>
		{/if}
	</div>
	{#if active && !skipped}
		<div class="pulse-ring"></div>
	{/if}
</button>

<style>
	.flow-node {
		display: flex;
		align-items: center;
		gap: 0.75rem;
		padding: 0.75rem 1rem;
		background: var(--node-bg);
		border: 2px solid var(--node-color);
		border-radius: 12px;
		cursor: default;
		transition: all 0.3s ease;
		position: relative;
		overflow: hidden;
		min-width: 140px;
	}

	.flow-node.clickable {
		cursor: pointer;
	}

	.flow-node.clickable:hover {
		transform: scale(1.02);
		box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
	}

	.flow-node.active {
		animation: nodePulse 2s infinite;
	}

	.flow-node.skipped {
		opacity: 0.6;
		border-style: dashed;
	}

	@keyframes nodePulse {
		0%, 100% {
			box-shadow: 0 0 0 0 var(--node-color);
		}
		50% {
			box-shadow: 0 0 0 8px rgba(0, 0, 0, 0);
		}
	}

	.node-icon {
		width: 32px;
		height: 32px;
		border-radius: 50%;
		background: var(--node-color);
		color: white;
		display: flex;
		align-items: center;
		justify-content: center;
		font-size: 0.9rem;
		font-weight: bold;
		flex-shrink: 0;
	}

	.node-content {
		display: flex;
		flex-direction: column;
		gap: 0.25rem;
		text-align: left;
	}

	.node-title {
		font-weight: 600;
		font-size: 0.9rem;
		color: #1f2937;
	}

	.node-timing {
		font-size: 0.75rem;
		color: #6b7280;
		font-family: monospace;
	}

	.node-timing.skipped-label {
		color: #9ca3af;
		font-style: italic;
	}

	.pulse-ring {
		position: absolute;
		top: 0;
		left: 0;
		right: 0;
		bottom: 0;
		border-radius: 12px;
		border: 2px solid var(--node-color);
		animation: ringExpand 1.5s ease-out infinite;
		pointer-events: none;
	}

	@keyframes ringExpand {
		0% {
			transform: scale(1);
			opacity: 1;
		}
		100% {
			transform: scale(1.1);
			opacity: 0;
		}
	}
</style>
