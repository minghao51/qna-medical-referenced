<script lang="ts">
	export let high: number;
	export let medium: number;
	export let low: number;

	const total = high + medium + low;

	function getPercent(value: number): number {
		return total > 0 ? (value / total) * 100 : 0;
	}
</script>

<div class="quality-distribution">
	<div class="distribution-bar">
		<div
			class="bar-segment high"
			style="width: {getPercent(high)}%"
			title="High quality: {high} ({getPercent(high).toFixed(1)}%)"
		></div>
		<div
			class="bar-segment medium"
			style="width: {getPercent(medium)}%"
			title="Medium quality: {medium} ({getPercent(medium).toFixed(1)}%)"
		></div>
		<div
			class="bar-segment low"
			style="width: {getPercent(low)}%"
			title="Low quality: {low} ({getPercent(low).toFixed(1)}%)"
		></div>
	</div>
	<div class="distribution-labels">
		<span class="label high">High: {high}</span>
		<span class="label medium">Med: {medium}</span>
		<span class="label low">Low: {low}</span>
	</div>
</div>

<style>
	.quality-distribution {
		display: flex;
		flex-direction: column;
		gap: 0.25rem;
	}

	.distribution-bar {
		display: flex;
		height: 12px;
		border-radius: 6px;
		overflow: hidden;
		background: #f0f0f0;
	}

	.bar-segment {
		height: 100%;
		transition: width 0.3s ease;
	}

	.bar-segment.high {
		background: #4caf50;
	}

	.bar-segment.medium {
		background: #ff9800;
	}

	.bar-segment.low {
		background: #f44336;
	}

	.distribution-labels {
		display: flex;
		gap: 0.75rem;
		font-size: 0.75rem;
	}

	.label {
		font-weight: 500;
	}

	.label.high {
		color: #4caf50;
	}

	.label.medium {
		color: #ff9800;
	}

	.label.low {
		color: #f44336;
	}
</style>
