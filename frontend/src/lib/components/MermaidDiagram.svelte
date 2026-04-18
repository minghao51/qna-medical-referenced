<script lang="ts">
	import { onMount } from 'svelte';

	interface Props {
		code: string;
		theme?: 'default' | 'neutral' | 'dark';
	}

	let { code, theme = 'default' }: Props = $props();
	let container: HTMLDivElement;
	let error = $state('');

	onMount(async () => {
		const mermaid = await import('mermaid');
		mermaid.default.initialize({
			startOnLoad: false,
			theme: theme,
			flowchart: {
				htmlLabels: true,
				curve: 'basis'
			}
		});

		try {
			const id = `mermaid-${Math.random().toString(36).slice(2, 9)}`;
			const { svg } = await mermaid.default.render(id, code);
			container.innerHTML = svg;
			error = '';
		} catch (e) {
			error = e instanceof Error ? e.message : 'Mermaid rendering failed';
			console.error('Mermaid error:', e);
		}
	});
</script>

{#if error}
	<pre class="mermaid-error">{error}</pre>
{/if}
<div bind:this={container} class="mermaid-container"></div>

<style>
	.mermaid-container {
		width: 100%;
		overflow-x: auto;
		display: flex;
		justify-content: center;
	}

	.mermaid-container :global(svg) {
		max-width: 100%;
		height: auto;
	}

	.mermaid-error {
		color: var(--error-color, #dc2626);
		background: var(--error-bg, #fef2f2);
		padding: 0.75rem;
		border-radius: 8px;
		font-size: 0.85rem;
		overflow-x: auto;
	}
</style>
