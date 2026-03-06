<script lang="ts">
	type Threshold = {
		metric: string;
		op: 'min' | 'max';
		value: number;
		current: number;
	};

	type Props = {
		thresholds: Threshold[];
		onSave?: (thresholds: Threshold[]) => void;
		readonly?: boolean;
	};

	let { thresholds, onSave, readonly = false }: Props = $props();

	let editing = $state(false);
	let localThresholds = $state<Threshold[]>([...thresholds]);
	let saving = $state(false);

	function getStatus(threshold: Threshold): 'pass' | 'fail' {
		const { op, value, current } = threshold;
		const passes = op === 'min' ? current >= value : current <= value;
		return passes ? 'pass' : 'fail';
	}

	function startEditing() {
		if (readonly) return;
		localThresholds = thresholds.map((t) => ({ ...t }));
		editing = true;
	}

	function cancelEditing() {
		editing = false;
		localThresholds = [...thresholds];
	}

	async function handleSave() {
		if (onSave) {
			saving = true;
			try {
				await onSave(localThresholds);
				editing = false;
			} catch (e) {
				console.error('Failed to save thresholds:', e);
			} finally {
				saving = false;
			}
		} else {
			thresholds = localThresholds;
			editing = false;
		}
	}

	function updateThreshold(index: number, field: keyof Threshold, newValue: any) {
		localThresholds[index] = { ...localThresholds[index], [field]: newValue };
	}
</script>

<div class="threshold-editor">
	<div class="threshold-header">
		<h3>Quality Thresholds</h3>
		{#if !readonly}
			{#if editing}
				<div class="edit-actions">
					<button class="btn btn-secondary" onclick={cancelEditing} disabled={saving}>
						Cancel
					</button>
					<button class="btn btn-primary" onclick={handleSave} disabled={saving}>
						{saving ? 'Saving...' : 'Save Changes'}
					</button>
				</div>
			{:else}
				<button class="btn btn-edit" onclick={startEditing}>Edit Thresholds</button>
			{/if}
		{/if}
	</div>

	<div class="thresholds-grid">
		{#each localThresholds as threshold, index (index)}
			{@const status = getStatus(threshold)}
			<div class="threshold-card" class:status-{status}>
				<div class="threshold-metric">{threshold.metric}</div>
				<div class="threshold-config">
					{#if editing}
						<select
							bind:value={localThresholds[index].op}
							class="op-select"
							onchange={(e) => updateThreshold(index, 'op', e.target.value)}
						>
							<option value="min">≥ Min</option>
							<option value="max">≤ Max</option>
						</select>
						<input
							type="number"
							bind:value={localThresholds[index].value}
							step="0.01"
							class="value-input"
							onchange={(e) => updateThreshold(index, 'value', parseFloat(e.target.value))}
						/>
					{:else}
						<span class="threshold-value">{threshold.op === 'min' ? '≥' : '≤'} {threshold.value}</span>
					{/if}
				</div>
				<div class="threshold-current">
					<span class="current-label">Current:</span>
					<span class="current-value" class:status-{status}>
						{typeof threshold.current === 'number' ? threshold.current.toFixed(3) : threshold.current}
					</span>
				</div>
				<div class="threshold-status" class:status-{status}>
					{#if status === 'pass'}
						✓ PASS
					{:else}
						✗ FAIL
					{/if}
				</div>
			</div>
		{/each}
	</div>

	{#if localThresholds.length === 0}
		<p class="no-thresholds">No thresholds configured.</p>
	{/if}
</div>

<style>
	.threshold-editor {
		background: white;
		border: 1px solid #e0e0e0;
		border-radius: 8px;
		padding: 1.5rem;
	}

	.threshold-header {
		display: flex;
		justify-content: space-between;
		align-items: center;
		margin-bottom: 1.5rem;
		flex-wrap: wrap;
		gap: 1rem;
	}

	.threshold-header h3 {
		font-size: 1.25rem;
		margin: 0;
		color: #333;
	}

	.edit-actions {
		display: flex;
		gap: 0.5rem;
	}

	.btn {
		padding: 0.5rem 1rem;
		border: 1px solid #ddd;
		border-radius: 4px;
		cursor: pointer;
		font-weight: 500;
		font-size: 0.9rem;
		transition: all 0.2s;
	}

	.btn:hover:not(:disabled) {
		background: #f5f5f5;
	}

	.btn:disabled {
		opacity: 0.6;
		cursor: not-allowed;
	}

	.btn-primary {
		background: #2196f3;
		color: white;
		border-color: #2196f3;
	}

	.btn-primary:hover:not(:disabled) {
		background: #1976d2;
	}

	.btn-secondary {
		background: #f5f5f5;
	}

	.btn-edit {
		background: #e3f2fd;
		border-color: #2196f3;
		color: #1976d2;
	}

	.thresholds-grid {
		display: grid;
		grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
		gap: 1rem;
	}

	.threshold-card {
		border: 2px solid;
		border-radius: 8px;
		padding: 1rem;
		display: flex;
		flex-direction: column;
		gap: 0.75rem;
		transition: all 0.2s;
	}

	.threshold-card.status-pass {
		border-color: #4caf50;
		background: #e8f5e9;
	}

	.threshold-card.status-fail {
		border-color: #f44336;
		background: #ffebee;
	}

	.threshold-metric {
		font-weight: 600;
		color: #333;
		font-size: 0.95rem;
	}

	.threshold-config {
		display: flex;
		align-items: center;
		gap: 0.5rem;
	}

	.threshold-value {
		font-size: 1.1rem;
		font-weight: 500;
		color: #555;
	}

	.op-select {
		padding: 0.3rem 0.5rem;
		border: 1px solid #ddd;
		border-radius: 4px;
		font-size: 0.9rem;
		cursor: pointer;
	}

	.value-input {
		width: 80px;
		padding: 0.3rem 0.5rem;
		border: 1px solid #ddd;
		border-radius: 4px;
		font-size: 0.9rem;
	}

	.value-input:focus {
		outline: none;
		border-color: #2196f3;
		box-shadow: 0 0 0 2px rgba(33, 150, 243, 0.1);
	}

	.threshold-current {
		display: flex;
		justify-content: space-between;
		align-items: center;
		padding-top: 0.5rem;
		border-top: 1px solid rgba(0, 0, 0, 0.1);
	}

	.current-label {
		font-size: 0.8rem;
		color: #666;
	}

	.current-value {
		font-weight: 600;
		font-size: 1rem;
	}

	.current-value.status-pass {
		color: #4caf50;
	}

	.current-value.status-fail {
		color: #f44336;
	}

	.threshold-status {
		font-weight: 600;
		font-size: 0.85rem;
		text-align: center;
		padding: 0.4rem;
		border-radius: 4px;
	}

	.threshold-status.status-pass {
		background: #4caf50;
		color: white;
	}

	.threshold-status.status-fail {
		background: #f44336;
		color: white;
	}

	.no-thresholds {
		text-align: center;
		color: #999;
		padding: 2rem;
		font-style: italic;
	}

	@media (max-width: 768px) {
		.thresholds-grid {
			grid-template-columns: 1fr;
		}

		.threshold-header {
			flex-direction: column;
			align-items: flex-start;
		}
	}
</style>
