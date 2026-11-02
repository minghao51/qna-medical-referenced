<script lang="ts">
	type Row = {
		name: string;
		chunking: string;
		queryUnderstanding: string;
		ndcg: string;
		deltaAbsolute: string;
		deltaRelative: string;
		measurement: string;
		selected: boolean;
	};

	type Props = {
		rows: Row[];
		metricLabel: string;
		onSelect: (name: string) => void;
	};

	let { rows, metricLabel, onSelect }: Props = $props();
</script>

<div class="feature-table-wrap">
	<table class="feature-table">
		<caption class="sr-only">
			Declared feature variants and archived nDCG results. Selecting a row inspects it; it does
			not certify a winner.
		</caption>
		<thead>
			<tr>
				<th scope="col">Declared variant</th>
				<th scope="col">Chunking</th>
				<th scope="col">Query understanding</th>
				<th scope="col">{metricLabel}</th>
				<th scope="col">Δ vs baseline</th>
				<th scope="col">Measurement</th>
			</tr>
		</thead>
		<tbody>
			{#each rows as row (row.name)}
				<tr class:selected={row.selected}>
					<th scope="row">
						<button
							type="button"
							class="variant-button"
							aria-pressed={row.selected}
							onclick={() => onSelect(row.name)}
						>
							{row.name}
						</button>
						{#if row.selected}
							<span class="inspecting">Inspecting</span>
						{/if}
					</th>
					<td data-label="Chunking">{row.chunking}</td>
					<td data-label="Query understanding">{row.queryUnderstanding}</td>
					<td data-label={metricLabel}>
						<span class="metric-value">{row.ndcg}</span>
					</td>
					<td data-label="Δ vs baseline">
						<span class="delta">{row.deltaAbsolute}</span>
						{#if row.deltaRelative !== 'N/A'}
							<span class="relative">{row.deltaRelative}</span>
						{/if}
					</td>
					<td data-label="Measurement">
						<span class="measurement">{row.measurement}</span>
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

	.feature-table-wrap {
		overflow-x: auto;
	}

	.feature-table {
		width: 100%;
		border-collapse: collapse;
		font-size: 0.9rem;
	}

	.feature-table th,
	.feature-table td {
		padding: 0.75rem 0.6rem;
		border-bottom: 1px solid var(--border-color);
		text-align: left;
		vertical-align: top;
	}

	.feature-table thead th {
		color: var(--muted-color);
		font-size: 0.68rem;
		font-weight: 700;
		letter-spacing: 0.08em;
		text-transform: uppercase;
	}

	.feature-table tbody th {
		font-weight: 400;
	}

	.feature-table tr.selected {
		background: #f4f1e7;
		box-shadow: inset 3px 0 0 var(--teal);
	}

	.variant-button {
		min-height: 32px;
		padding: 0;
		border: 0;
		background: transparent;
		color: var(--ink);
		font: inherit;
		font-weight: 700;
		text-align: left;
		text-decoration: underline;
		text-decoration-color: var(--border-color);
		text-underline-offset: 3px;
		cursor: pointer;
	}

	.variant-button:hover {
		text-decoration-color: var(--teal);
	}

	.inspecting {
		display: block;
		margin-top: 0.2rem;
		color: var(--teal);
		font-size: 0.68rem;
		font-weight: 700;
		letter-spacing: 0.06em;
		text-transform: uppercase;
	}

	.metric-value {
		font-family: var(--font-heading);
		font-size: 1.15rem;
	}

	.delta,
	.relative {
		display: block;
		font-variant-numeric: tabular-nums;
	}

	.relative {
		color: var(--muted-color);
		font-size: 0.75rem;
	}

	.measurement {
		color: var(--rust);
		font-size: 0.78rem;
		text-transform: uppercase;
		letter-spacing: 0.04em;
	}

	@media (max-width: 860px) {
		.feature-table thead {
			display: none;
		}

		.feature-table,
		.feature-table tbody,
		.feature-table tr,
		.feature-table th,
		.feature-table td {
			display: block;
		}

		.feature-table tr {
			padding: 0.8rem 0;
			border-bottom: 1px solid var(--border-color);
		}

		.feature-table th,
		.feature-table td {
			padding: 0.2rem 0;
			border: 0;
		}

		.feature-table td[data-label]::before {
			content: attr(data-label);
			display: block;
			color: var(--muted-color);
			font-size: 0.68rem;
			letter-spacing: 0.06em;
			text-transform: uppercase;
		}
	}
</style>
