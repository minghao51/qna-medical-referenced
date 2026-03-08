<script lang="ts">
	import { getHealthColor } from '$lib/utils/health-score';

	type Props = {
		score: number;
		grade: string;
	};

	let { score, grade }: Props = $props();
	const color = $derived(getHealthColor(grade));
</script>

<div class="health-score-badge" style="background: {color}">
	<span class="score-value">{score.toFixed(0)}</span>
	<span class="score-label">Health Score</span>
	<span class="score-grade">{grade}</span>
</div>

<style>
	.health-score-badge {
		padding: 0.5rem 1rem;
		border-radius: 8px;
		color: white;
		display: flex;
		flex-direction: column;
		align-items: center;
		gap: 0.25rem;
		min-width: 100px;
		box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
	}

	.score-value {
		font-size: 2rem;
		font-weight: 700;
		line-height: 1;
	}

	.score-label {
		font-size: 0.7rem;
		text-transform: uppercase;
		letter-spacing: 0.5px;
		opacity: 0.9;
	}

	.score-grade {
		font-size: 1.25rem;
		font-weight: 600;
	}
</style>
