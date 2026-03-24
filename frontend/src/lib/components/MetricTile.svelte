<script lang="ts">
	type Props = {
		label: string;
		value: string;
		highlight?: boolean;
		quiet?: boolean;
		onclick?: (() => void) | undefined;
	};

	let { label, value, highlight = false, quiet = false, onclick }: Props = $props();
</script>

{#if onclick}
	<button type="button" class:highlight class:quiet class="metric-tile button" onclick={onclick}>
		<span class="label">{label}</span>
		<strong class="value">{value}</strong>
	</button>
{:else}
	<div class:highlight class:quiet class="metric-tile">
		<span class="label">{label}</span>
		<strong class="value">{value}</strong>
	</div>
{/if}

<style>
	.metric-tile {
		display: flex;
		flex-direction: column;
		gap: 0.35rem;
		padding: 1rem;
		border: 1px solid var(--border-color);
		border-radius: 14px;
		background: white;
		min-height: 5.5rem;
	}

	.metric-tile.button {
		width: 100%;
		font: inherit;
		text-align: left;
		cursor: pointer;
		transition: transform 0.2s ease, border-color 0.2s ease, box-shadow 0.2s ease;
	}

	.metric-tile.button:hover {
		transform: translateY(-1px);
		border-color: var(--accent-soft);
		box-shadow: 0 8px 24px rgba(15, 23, 42, 0.06);
	}

	.metric-tile.highlight {
		background: var(--surface-strong);
		border-color: var(--accent-soft);
	}

	.metric-tile.quiet {
		background: var(--surface-subtle);
	}

	.label {
		font-size: 0.82rem;
		color: var(--muted-color);
	}

	.value {
		font-size: 1.15rem;
		line-height: 1.2;
		color: var(--text-color);
	}
</style>
