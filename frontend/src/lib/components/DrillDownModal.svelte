<script lang="ts">
	import MetricChart from '$lib/components/MetricChart.svelte';

	type Props = {
		open: boolean;
		onclose: () => void;
		metric: string;
		stage: string;
		currentValue: number;
		records: Array<any>;
		historicalData?: Array<{ timestamp: string; value: number }>;
	};

	let { open, onclose, metric, stage, currentValue, records, historicalData }: Props = $props();

	function handleClickOutside(e: MouseEvent) {
		if ((e.target as HTMLElement).classList.contains('modal-overlay')) {
			onclose();
		}
	}

	function handleKeydown(e: KeyboardEvent) {
		if (e.key === 'Escape') {
			onclose();
		}
	}

	function handleOverlayKeydown(e: KeyboardEvent) {
		if (
			(e.key === 'Enter' || e.key === ' ') &&
			(e.target as HTMLElement).classList.contains('modal-overlay')
		) {
			e.preventDefault();
			onclose();
		}
	}
</script>

<svelte:window onkeydown={handleKeydown} />

{#if open}
	<div
		class="modal-overlay"
		role="button"
		tabindex="0"
		aria-label="Close dialog"
		onclick={handleClickOutside}
		onkeydown={handleOverlayKeydown}
	>
		<div class="modal-content">
			<div class="modal-header">
				<h2>{metric} Details</h2>
				<button class="close-btn" onclick={onclose}>×</button>
			</div>

			<div class="modal-body">
				<!-- Current Value Summary -->
				<section class="summary-section">
					<h3>Current Value</h3>
					<div class="current-value-display">
						<span class="value">{typeof currentValue === 'number' ? currentValue.toFixed(3) : currentValue}</span>
						<span class="stage-badge">{stage.toUpperCase()}</span>
					</div>
				</section>

				<!-- Historical Trend -->
				{#if historicalData && historicalData.length > 0}
					<section class="trend-section">
						<h3>Historical Trend</h3>
						<MetricChart
							type="line"
							title="{metric} Over Time"
							data={{
								labels: historicalData.map((d) => d.timestamp),
								datasets: [
									{
										label: metric,
										data: historicalData.map((d) => d.value)
									}
								]
							}}
							height={200}
						/>
					</section>
				{/if}

				<!-- Affected Records -->
				{#if records && records.length > 0}
					<section class="records-section">
						<h3>Affected Records ({records.length})</h3>
						<div class="records-table-wrapper">
							<table class="records-table">
								<thead>
									<tr>
										{#each Object.keys(records[0] || {}).slice(0, 6) as key}
											<th>{key}</th>
										{/each}
									</tr>
								</thead>
								<tbody>
									{#each records.slice(0, 50) as record}
										<tr>
											{#each Object.entries(record).slice(0, 6) as [key, value]}
												<td>
													{#if typeof value === 'number' && value > 1000}
														{value.toFixed(0)}
													{:else if typeof value === 'number'}
														{value.toFixed(3)}
													{:else}
														{String(value).slice(0, 50)}
													{/if}
												</td>
											{/each}
										</tr>
									{/each}
								</tbody>
							</table>
							{#if records.length > 50}
								<p class="records-note">Showing 50 of {records.length} records</p>
							{/if}
						</div>
					</section>
				{:else}
					<section class="no-records">
						<p>No detailed records available for this metric.</p>
					</section>
				{/if}
			</div>
		</div>
	</div>
{/if}

<style>
	.modal-overlay {
		position: fixed;
		top: 0;
		left: 0;
		right: 0;
		bottom: 0;
		background: rgba(0, 0, 0, 0.5);
		display: flex;
		align-items: center;
		justify-content: center;
		z-index: 2000;
		padding: 2rem;
	}

	.modal-content {
		background: white;
		border-radius: 8px;
		max-width: 900px;
		width: 100%;
		max-height: 90vh;
		overflow: hidden;
		display: flex;
		flex-direction: column;
		box-shadow: 0 10px 40px rgba(0, 0, 0, 0.2);
	}

	.modal-header {
		display: flex;
		justify-content: space-between;
		align-items: center;
		padding: 1.5rem;
		border-bottom: 1px solid #e0e0e0;
	}

	.modal-header h2 {
		font-size: 1.5rem;
		margin: 0;
		color: #333;
	}

	.close-btn {
		background: none;
		border: none;
		font-size: 2rem;
		cursor: pointer;
		color: #666;
		line-height: 1;
		padding: 0;
		width: 32px;
		height: 32px;
		display: flex;
		align-items: center;
		justify-content: center;
		border-radius: 4px;
	}

	.close-btn:hover {
		background: #f0f0f0;
		color: #333;
	}

	.modal-body {
		padding: 1.5rem;
		overflow-y: auto;
		flex: 1;
		display: flex;
		flex-direction: column;
		gap: 2rem;
	}

	.summary-section h3,
	.trend-section h3,
	.records-section h3 {
		font-size: 1.1rem;
		margin-bottom: 1rem;
		color: #555;
	}

	.current-value-display {
		display: flex;
		align-items: center;
		gap: 1rem;
		padding: 1.5rem;
		background: #f9f9f9;
		border-radius: 8px;
	}

	.value {
		font-size: 2.5rem;
		font-weight: 700;
		color: #2196f3;
	}

	.stage-badge {
		padding: 0.5rem 1rem;
		background: #e3f2fd;
		color: #1976d2;
		border-radius: 4px;
		font-weight: 600;
		font-size: 1rem;
	}

	.records-table-wrapper {
		overflow-x: auto;
		border: 1px solid #e0e0e0;
		border-radius: 8px;
	}

	.records-table {
		width: 100%;
		border-collapse: collapse;
		font-size: 0.9rem;
	}

	.records-table th,
	.records-table td {
		padding: 0.75rem 1rem;
		text-align: left;
		border-bottom: 1px solid #f0f0f0;
	}

	.records-table th {
		background: #f9f9f9;
		font-weight: 600;
		color: #555;
		position: sticky;
		top: 0;
	}

	.records-table tr:hover {
		background: #f9f9f9;
	}

	.records-table td {
		color: #333;
		max-width: 200px;
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
	}

	.records-note {
		padding: 0.75rem;
		color: #666;
		font-size: 0.85rem;
		font-style: italic;
		text-align: center;
		background: #f9f9f9;
		margin: 0;
	}

	.no-records {
		text-align: center;
		padding: 2rem;
		color: #999;
	}

	@media (max-width: 768px) {
		.modal-content {
			max-height: 95vh;
		}

		.current-value-display {
			flex-direction: column;
			align-items: flex-start;
		}

		.value {
			font-size: 2rem;
		}
	}
</style>
