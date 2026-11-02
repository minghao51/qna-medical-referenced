<script lang="ts">
	import { formatDecimal } from '$lib/utils/eval';
	import type { CoverageState, MetricCoverage } from '$lib/types';

	type Props = {
		metrics: MetricCoverage[];
	};

	let { metrics }: Props = $props();

	const stateLabels: Record<CoverageState, string> = {
		complete: 'Complete',
		partial: 'Partial',
		not_recorded: 'Not recorded',
		inconsistent: 'Inconsistent'
	};

	function count(value: number | null): string {
		return typeof value === 'number' && Number.isFinite(value)
			? value.toLocaleString('en-US')
			: 'N/A';
	}

	function percent(part: number | null, whole: number | null): number {
		if (typeof part !== 'number' || typeof whole !== 'number' || whole <= 0) return 0;
		return Math.min(100, Math.max(0, (part / whole) * 100));
	}

	function barLabel(metric: MetricCoverage): string {
		const skipped =
			metric.skipped_slots === null ? '' : `, ${count(metric.skipped_slots)} skipped`;
		return `${metric.label}: ${count(metric.measured_slots)} measured, ${count(metric.failed_slots)} failed, ${count(metric.expected_slots)} expected${skipped}`;
	}
</script>

<div class="coverage-table-wrap">
	<table class="coverage-table">
		<caption class="sr-only">
			Answer-metric coverage. Means summarize successful measurements; missing slots are not
			scored zero.
		</caption>
		<thead>
			<tr>
				<th scope="col">Metric</th>
				<th scope="col">Mean / 0–1</th>
				<th scope="col">Measured / expected</th>
				<th scope="col">Failed</th>
				<th scope="col">Coverage</th>
			</tr>
		</thead>
		<tbody>
			{#each metrics as metric (metric.metric_key)}
				<tr>
					<th scope="row">
						<span class="metric-name">{metric.label}</span>
						<span class="metric-definition">{metric.definition_id}</span>
					</th>
					<td data-label="Mean / 0–1">
						<span class="metric-mean">{formatDecimal(metric.mean, 4)}</span>
					</td>
					<td data-label="Measured / expected">
						<span class="metric-count">{count(metric.measured_slots)} / {count(metric.expected_slots)}</span>
					</td>
					<td data-label="Failed">
						<span class="metric-failed">{count(metric.failed_slots)}</span>
						{#if metric.skipped_slots !== null && metric.skipped_slots > 0}
							<span class="metric-extra">{count(metric.skipped_slots)} skipped</span>
						{/if}
					</td>
					<td data-label="Coverage">
						<div
							class="coverage-bar"
							role="img"
							aria-label={barLabel(metric)}
						>
							<span
								class="bar-measured"
								style={`width:${percent(metric.measured_slots, metric.expected_slots)}%`}
							></span>
							<span
								class="bar-failed"
								style={`width:${percent(metric.failed_slots, metric.expected_slots)}%`}
							></span>
						</div>
						<span class="coverage-state" class:partial={metric.coverage_state === 'partial'}>
							{stateLabels[metric.coverage_state]}
						</span>
					</td>
				</tr>
			{/each}
		</tbody>
	</table>
</div>

<style>
	.sr-only {
		position: absolute;
		width: 1px;
		height: 1px;
		padding: 0;
		margin: -1px;
		overflow: hidden;
		clip: rect(0, 0, 0, 0);
		white-space: nowrap;
		border: 0;
	}

	.coverage-table-wrap {
		overflow-x: auto;
	}

	.coverage-table {
		width: 100%;
		border-collapse: collapse;
		font-size: 0.9rem;
	}

	.coverage-table th,
	.coverage-table td {
		padding: 0.7rem 0.6rem;
		border-bottom: 1px solid var(--border-color);
		text-align: left;
		vertical-align: top;
	}

	.coverage-table thead th {
		color: var(--muted-color);
		font-size: 0.68rem;
		font-weight: 700;
		letter-spacing: 0.08em;
		text-transform: uppercase;
	}

	.coverage-table tbody th {
		font-weight: 600;
	}

	.metric-name {
		display: block;
	}

	.metric-definition {
		display: block;
		margin-top: 0.15rem;
		color: var(--muted-color);
		font-size: 0.72rem;
		font-weight: 400;
	}

	.metric-mean {
		font-family: var(--font-heading);
		font-size: 1.1rem;
	}

	.metric-count,
	.metric-failed {
		font-variant-numeric: tabular-nums;
		white-space: nowrap;
	}

	.metric-failed {
		color: var(--rust);
	}

	.metric-extra {
		display: block;
		color: var(--muted-color);
		font-size: 0.72rem;
	}

	.coverage-bar {
		display: flex;
		height: 9px;
		min-width: 120px;
		overflow: hidden;
		border-radius: 999px;
		background: var(--surface-strong);
	}

	.bar-measured {
		background: var(--teal);
	}

	.bar-failed {
		background: var(--rust);
	}

	.coverage-state {
		display: inline-block;
		margin-top: 0.3rem;
		color: var(--secondary);
		font-size: 0.72rem;
	}

	.coverage-state.partial {
		color: var(--rust);
		font-weight: 700;
	}

	@media (max-width: 760px) {
		.coverage-table thead {
			display: none;
		}

		.coverage-table,
		.coverage-table tbody,
		.coverage-table tr,
		.coverage-table th,
		.coverage-table td {
			display: block;
		}

		.coverage-table tr {
			padding: 0.8rem 0;
			border-bottom: 1px solid var(--border-color);
		}

		.coverage-table th,
		.coverage-table td {
			padding: 0.2rem 0;
			border: 0;
		}

		.coverage-table td[data-label]::before {
			content: attr(data-label);
			display: block;
			color: var(--muted-color);
			font-size: 0.68rem;
			letter-spacing: 0.06em;
			text-transform: uppercase;
		}

		.coverage-bar {
			margin-top: 0.25rem;
		}
	}
</style>
