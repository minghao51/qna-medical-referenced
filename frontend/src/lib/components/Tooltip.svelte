<script lang="ts">
	export let text: string = '';
	export let position: 'top' | 'bottom' | 'left' | 'right' = 'top';
</script>

<div class="tooltip-container">
	<slot />
	{#if text}
		<div class="tooltip-content tooltip-position-{position}">
			{text}
		</div>
	{/if}
</div>

<style>
	.tooltip-container {
		position: relative;
		display: inline-flex;
		align-items: center;
		cursor: help;
	}

	.tooltip-content {
		visibility: hidden;
		opacity: 0;
		background-color: #1e293b;
		color: #f8fafc;
		text-align: center;
		border-radius: 6px;
		padding: 8px 12px;
		position: absolute;
		z-index: 50;
		bottom: 125%; /* default top */
		left: 50%;
		transform: translateX(-50%);
		transition: opacity 0.2s, visibility 0.2s;
		font-size: 0.85rem;
		font-weight: 500;
		width: max-content;
		max-width: 250px;
		white-space: pre-wrap;
		box-shadow: 0 4px 6px -1px rgb(0 0 0 / 0.1), 0 2px 4px -2px rgb(0 0 0 / 0.1);
		pointer-events: none;
	}

	.tooltip-container:hover .tooltip-content {
		visibility: visible;
		opacity: 1;
	}

	/* Arrow */
	.tooltip-content::after {
		content: "";
		position: absolute;
		top: 100%;
		left: 50%;
		margin-left: -5px;
		border-width: 5px;
		border-style: solid;
		border-color: #1e293b transparent transparent transparent;
	}

	/* Optional: Different positions can be added here */
	.tooltip-position-bottom {
		bottom: auto;
		top: 125%;
	}
	.tooltip-position-bottom::after {
		bottom: 100%;
		top: auto;
		border-color: transparent transparent #1e293b transparent;
	}
</style>
