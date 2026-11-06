<script lang="ts">
	type Props = {
		count?: number;
		type?: 'card' | 'row' | 'circle';
		height?: string;
	};

	let { count = 1, type = 'row', height }: Props = $props();

	const heights = {
		row: '12px',
		card: '120px',
		circle: '40px'
	};
</script>

<div class="skeleton-container">
	{#each Array(count) as _, i (i)}
		<div class="skeleton skeleton-{type}" style="height: {height || heights[type]}"></div>
	{/each}
</div>

<style>
	.skeleton-container {
		display: flex;
		flex-direction: column;
		gap: 1rem;
		width: 100%;
	}

	.skeleton {
		background: var(--surface-subtle);
		border: 1px solid var(--border-color);
		border-radius: 6px;
	}

	.skeleton-row {
		width: 100%;
	}

	.skeleton-card {
		width: 100%;
		border-radius: 8px;
		padding: 1rem;
	}

	.skeleton-circle {
		width: 40px;
		height: 40px;
		border-radius: 50%;
	}
</style>
