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
		<div class="skeleton skeleton-{type}" style="height: {height || heights[type]}">
			<div class="skeleton-shimmer"></div>
		</div>
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
		background: #f0f0f0;
		border-radius: 4px;
		position: relative;
		overflow: hidden;
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

	.skeleton-shimmer {
		position: absolute;
		top: 0;
		left: 0;
		right: 0;
		bottom: 0;
		background: linear-gradient(
			90deg,
			transparent 0%,
			rgba(255, 255, 255, 0.4) 50%,
			transparent 100%
		);
		animation: shimmer 1.5s ease-in-out infinite;
		transform: translateX(-100%);
	}

	@keyframes shimmer {
		0% {
			transform: translateX(-100%);
		}
		100% {
			transform: translateX(100%);
		}
	}
</style>
