<script lang="ts">
	type Props = {
		value: number;
		label: string;
		color?: 'green' | 'yellow' | 'red' | 'blue';
		showValue?: boolean;
		compact?: boolean;
	};

	let { value, label, color = 'green', showValue = true, compact = false }: Props = $props();

	const colors = {
		green: '#22c55e',
		yellow: '#f59e0b',
		red: '#ef4444',
		blue: '#3b82f6'
	};

	const barColor = $derived(colors[color]);
	const clampedValue = $derived(Math.max(0, Math.min(100, value)));

	function getColorFromValue(val: number): 'green' | 'yellow' | 'red' {
		if (val >= 70) return 'green';
		if (val >= 40) return 'yellow';
		return 'red';
	}

	const autoColor = $derived(getColorFromValue(value));
</script>

<div class="metric-bar" class:compact>
	<span class="metric-label">{label}</span>
	<div class="bar-track">
		<div
			class="bar-fill"
			style="width: {clampedValue}%; background: {colors[autoColor]};"
		></div>
	</div>
	{#if showValue}
		<span class="metric-value">{clampedValue}%</span>
	{/if}
</div>

<style>
	.metric-bar {
		display: flex;
		align-items: center;
		gap: 0.5rem;
		font-size: 0.85rem;
	}

	.metric-bar.compact {
		gap: 0.35rem;
		font-size: 0.75rem;
	}

	.metric-label {
		min-width: 100px;
		color: #555;
		font-weight: 500;
	}

	.compact .metric-label {
		min-width: 70px;
	}

	.bar-track {
		flex: 1;
		height: 8px;
		background: #e5e7eb;
		border-radius: 4px;
		overflow: hidden;
		min-width: 60px;
	}

	.compact .bar-track {
		height: 6px;
	}

	.bar-fill {
		height: 100%;
		border-radius: 4px;
		transition: width 0.3s ease;
	}

	.metric-value {
		min-width: 40px;
		text-align: right;
		font-weight: 600;
		color: #333;
		font-family: monospace;
	}

	.compact .metric-value {
		min-width: 35px;
		font-size: 0.8rem;
	}
</style>
