<script lang="ts">
	import { setContext } from 'svelte';
	import SvelteMarkdown from 'svelte-markdown';
	import CodeBlockRenderer from '$lib/components/markdown/renderers/CodeBlockRenderer.svelte';
	import HtmlRenderer from '$lib/components/markdown/renderers/HtmlRenderer.svelte';
	import LinkRenderer from '$lib/components/markdown/renderers/LinkRenderer.svelte';
	import { markdownRendererContextKey } from '$lib/components/markdown/context';

	interface Props {
		content: string;
		className?: string;
		maxHeight?: string;
		showCopyButton?: boolean;
		truncate?: number;
		onError?: (error: Error) => void;
	}

	const markdownOptions = {
		gfm: true,
		headerIds: false,
		mangle: false
	} as const;

	const renderers = {
		code: CodeBlockRenderer,
		html: HtmlRenderer,
		link: LinkRenderer
	};

	let {
		content,
		className = '',
		maxHeight,
		showCopyButton = true,
		truncate,
		onError = console.error
	}: Props = $props();

	setContext(markdownRendererContextKey, {
		getShowCopyButton: () => showCopyButton,
		reportError: (error: Error) => onError(error)
	});

	let displayContent = $derived(
		truncate && content.length > truncate ? `${content.slice(0, truncate).trimEnd()}...` : content
	);
</script>

<div class={`markdown-renderer ${className}`.trim()} class:markdown-renderer--scrollable={Boolean(maxHeight)} style:max-height={maxHeight}>
	{#if typeof content === 'string'}
		{#if displayContent}
			<SvelteMarkdown source={displayContent} options={markdownOptions} {renderers} />
		{/if}
	{:else}
		<p class="error">Unable to display content</p>
	{/if}
</div>

<style>
	.markdown-renderer--scrollable {
		overflow-y: auto;
	}

	.error {
		color: #d32f2f;
		font-style: italic;
	}
</style>
