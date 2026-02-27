<script lang="ts">
	type Props = {
		level: 'high' | 'medium' | 'low';
		score: number;
		label?: string;
		showScore?: boolean;
	};

	let { level, score, label, showScore = true }: Props = $props();

	const config = {
		high: {
			icon: '✓',
			color: '#22c55e',
			bgColor: '#dcfce7',
			label: 'High'
		},
		medium: {
			icon: '⚠',
			color: '#f59e0b',
			bgColor: '#fef3c7',
			label: 'Medium'
		},
		low: {
			icon: '!',
			color: '#ef4444',
			bgColor: '#fee2e2',
			label: 'Low'
		}
	};

	const currentConfig = $derived(config[level]);
	const displayLabel = $derived(label || currentConfig.label);
</script>

<span
	class="confidence-badge"
	style="--badge-color: {currentConfig.color}; --badge-bg: {currentConfig.bgColor};"
	title="Confidence: {score}%"
>
	<span class="badge-icon">{currentConfig.icon}</span>
	<span class="badge-label">{displayLabel}</span>
	{#if showScore}
		<span class="badge-score">{score}%</span>
	{/if}
</span>

<style>
	.confidence-badge {
		display: inline-flex;
		align-items: center;
		gap: 0.25rem;
		padding: 0.25rem 0.5rem;
		border-radius: 4px;
		font-size: 0.75rem;
		font-weight: 600;
		background: var(--badge-bg);
		color: var(--badge-color);
		white-space: nowrap;
	}

	.badge-icon {
		display: flex;
		align-items: center;
		justify-content: center;
		width: 16px;
		height: 16px;
		border-radius: 50%;
		background: var(--badge-color);
		color: white;
		font-size: 0.65rem;
	}

	.badge-label {
		text-transform: uppercase;
		letter-spacing: 0.02em;
	}

	.badge-score {
		opacity: 0.85;
		font-family: monospace;
	}
</style>
