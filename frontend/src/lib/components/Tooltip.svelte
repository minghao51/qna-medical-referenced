<script lang="ts">
	import { tick } from 'svelte';

	export let text: string = '';
	export let position: 'top' | 'bottom' | 'left' | 'right' = 'top';

	let containerEl: HTMLDivElement;
	let tooltipEl: HTMLDivElement;
	let visible = false;
	let resolvedPosition: 'top' | 'bottom' | 'left' | 'right' = position;
	let tooltipStyle = '';

	function computeTooltipStyle() {
		if (!containerEl || !tooltipEl || !visible) return;

		const containerRect = containerEl.getBoundingClientRect();
		const tooltipRect = tooltipEl.getBoundingClientRect();
		const spacing = 12;
		const viewportPadding = 12;

		let nextPosition = position;
		let top = containerRect.top - tooltipRect.height - spacing;
		let left = containerRect.left + (containerRect.width - tooltipRect.width) / 2;

		if (position === 'bottom') {
			top = containerRect.bottom + spacing;
		}

		if (position === 'left') {
			top = containerRect.top + (containerRect.height - tooltipRect.height) / 2;
			left = containerRect.left - tooltipRect.width - spacing;
		}

		if (position === 'right') {
			top = containerRect.top + (containerRect.height - tooltipRect.height) / 2;
			left = containerRect.right + spacing;
		}

		if (nextPosition === 'top' && top < viewportPadding) {
			nextPosition = 'bottom';
			top = containerRect.bottom + spacing;
		} else if (
			nextPosition === 'bottom' &&
			top + tooltipRect.height > window.innerHeight - viewportPadding
		) {
			nextPosition = 'top';
			top = containerRect.top - tooltipRect.height - spacing;
		}

		if (nextPosition === 'left' && left < viewportPadding) {
			nextPosition = 'right';
			left = containerRect.right + spacing;
		} else if (
			nextPosition === 'right' &&
			left + tooltipRect.width > window.innerWidth - viewportPadding
		) {
			nextPosition = 'left';
			left = containerRect.left - tooltipRect.width - spacing;
		}

		left = Math.min(
			Math.max(left, viewportPadding),
			window.innerWidth - tooltipRect.width - viewportPadding
		);
		top = Math.min(
			Math.max(top, viewportPadding),
			window.innerHeight - tooltipRect.height - viewportPadding
		);

		resolvedPosition = nextPosition;
		tooltipStyle = `top:${top}px;left:${left}px;`;
	}

	async function showTooltip() {
		visible = true;
		await tick();
		computeTooltipStyle();
	}

	function hideTooltip() {
		visible = false;
	}
</script>

<svelte:window onscroll={computeTooltipStyle} onresize={computeTooltipStyle} />

<div
	class="tooltip-container"
	bind:this={containerEl}
	role="presentation"
	onmouseenter={showTooltip}
	onmouseleave={hideTooltip}
	onfocusin={showTooltip}
	onfocusout={hideTooltip}
>
	<slot />
	{#if text && visible}
		<div
			class="tooltip-content tooltip-position-{resolvedPosition}"
			bind:this={tooltipEl}
			style={tooltipStyle}
			role="tooltip"
		>
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
		background-color: #1e293b;
		color: #f8fafc;
		text-align: left;
		border-radius: 6px;
		padding: 10px 12px;
		position: fixed;
		z-index: 1000;
		transition: opacity 0.15s ease;
		font-size: 0.85rem;
		font-weight: 500;
		line-height: 1.4;
		width: min(18rem, calc(100vw - 24px));
		white-space: pre-wrap;
		box-shadow: 0 4px 6px -1px rgb(0 0 0 / 0.1), 0 2px 4px -2px rgb(0 0 0 / 0.1);
		pointer-events: none;
	}

	/* Arrow */
	.tooltip-content::after {
		content: '';
		position: absolute;
		left: 50%;
		border-width: 5px;
		border-style: solid;
		transform: translateX(-50%);
	}

	.tooltip-position-top::after {
		top: 100%;
		border-color: #1e293b transparent transparent transparent;
	}

	.tooltip-position-bottom::after {
		bottom: 100%;
		border-color: transparent transparent #1e293b transparent;
	}

	.tooltip-position-left::after {
		top: 50%;
		left: 100%;
		transform: translateY(-50%);
		border-color: transparent transparent transparent #1e293b;
	}

	.tooltip-position-right::after {
		top: 50%;
		left: 0;
		transform: translate(-100%, -50%);
		border-color: transparent #1e293b transparent transparent;
	}
</style>
