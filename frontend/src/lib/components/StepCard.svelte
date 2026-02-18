<script lang="ts">
	import { createEventDispatcher } from 'svelte';
	import { flip } from 'svelte';
	import { scale } from 'svelte/transition';

	export let title: string;
	export let timing: number;
	export let expanded = false;

	const dispatch = createEventDispatcher();

	function toggle() {
		expanded = !expanded;
		dispatch('toggle', { expanded });
	}
</script>

<div class="step-card">
	<button class="step-header" onclick={toggle} aria-expanded={expanded}>
		<span class="step-title">{title}</span>
		{#if timing > 0}
			<span class="step-timing">{timing}ms</span>
		{/if}
		<span class="expand-icon {expanded ? 'expanded' : ''}">▶</span>
	</button>

	{#if expanded}
		<div class="step-content" transition:scale|flip>
			<slot />
		</div>
	{/if}
</div>

<style>
	.step-card {
		background: white;
		border: 1px solid #e0e0e0;
		border-radius: 8px;
		margin-bottom: 1rem;
		overflow: hidden;
		transition: box-shadow 0.2s ease;
	}

	.step-card:hover {
		box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
	}

	.step-header {
		width: 100%;
		display: flex;
		align-items: center;
		gap: 0.75rem;
		padding: 0.875rem 1rem;
		background: #f9f9f9;
		border: none;
		border-bottom: 1px solid #e0e0e0;
		cursor: pointer;
		text-align: left;
		transition: background 0.2s ease;
	}

	.step-header:hover {
		background: #f0f0f0;
	}

	.step-header:focus {
		outline: 2px solid #2196f3;
		outline-offset: -2px;
	}

	.step-title {
		flex: 1;
		font-weight: 600;
		font-size: 1rem;
		color: #333;
	}

	.step-timing {
		background: #e3f2fd;
		color: #1976d2;
		padding: 0.25rem 0.5rem;
		border-radius: 4px;
		font-size: 0.85rem;
		font-weight: 600;
		font-family: monospace;
	}

	.expand-icon {
		color: #666;
		transition: transform 0.2s ease;
		font-size: 0.75rem;
	}

	.expand-icon.expanded {
		transform: rotate(90deg);
	}

	.step-content {
		padding: 1rem;
		background: white;
	}

	/* Global transition styles */
	:global(.step-content) {
		transform-origin: top;
	}
</style>
