<script lang="ts">
	import { getContext } from 'svelte';
	import { highlightCode } from '$lib/components/markdown/highlight';
	import {
		markdownRendererContextKey,
		type MarkdownRendererContext
	} from '$lib/components/markdown/context';

	export let lang: string | undefined = undefined;
	export let text = '';

	const { getShowCopyButton, reportError } = getContext<MarkdownRendererContext>(
		markdownRendererContextKey
	);

	let copied = false;
	let copyResetTimeout: ReturnType<typeof setTimeout> | null = null;

	$: highlighted = highlightCode(text, lang);
	$: languageLabel = highlighted.language ?? 'text';

	async function copyCode() {
		try {
			await navigator.clipboard.writeText(text);
			copied = true;

			if (copyResetTimeout) {
				clearTimeout(copyResetTimeout);
			}

			copyResetTimeout = setTimeout(() => {
				copied = false;
				copyResetTimeout = null;
			}, 2000);
		} catch (error) {
			reportError(error as Error);
		}
	}
</script>

<div class="code-block">
	<div class="code-block__toolbar">
		<span class="code-block__language">{languageLabel}</span>
		{#if getShowCopyButton()}
			<button
				type="button"
				class="code-copy-button"
				aria-label="Copy code block"
				onclick={copyCode}
			>
				{copied ? 'Copied' : 'Copy'}
			</button>
		{/if}
	</div>
	<pre><code class:hljs={true} class={"language-" + languageLabel}>{@html highlighted.html}</code></pre>
</div>
