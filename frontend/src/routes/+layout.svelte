<script lang="ts">
	import { setContext } from 'svelte';
	import favicon from '$lib/assets/favicon.svg';
	import { createChatState } from '$lib/conversation-state.svelte';

	let { children } = $props();

	// Layout-scoped, in-memory conversation state for ordinary navigation.
	setContext('fieldnote-chat', createChatState());
</script>

<svelte:head>
	<link rel="icon" href={favicon} />
</svelte:head>

{@render children()}

<style>
	:global(*) {
		margin: 0;
		padding: 0;
		box-sizing: border-box;
	}

	:global(:root) {
		/* Fieldnote design tokens. Legacy aliases remain so unmigrated routes keep working. */
		--paper: #f7f4ed;
		--ink: #182d32;
		--teal: #006b61;
		--rust: #b34322;
		--blue: #375e91;
		--secondary: #506469;
		--success: #047857;
		--font-heading: Georgia, 'Times New Roman', serif;
		--font-body: Arial, Helvetica, sans-serif;

		--page-bg: var(--paper);
		--surface-subtle: #f0ece2;
		--surface-strong: #e5ddcf;
		--border-color: #d7d0c1;
		--text-color: var(--ink);
		--muted-color: var(--secondary);
		--accent-soft: #9cc4bd;
	}

	:global(body) {
		font-family: var(--font-body);
		background: var(--page-bg);
		color: var(--text-color);
		line-height: 1.5;
	}

	:global(h1),
	:global(h2),
	:global(h3) {
		font-family: var(--font-heading);
		font-weight: 600;
		line-height: 1.15;
	}

	:global(:focus-visible) {
		outline: 3px solid var(--teal);
		outline-offset: 2px;
	}

	:global(button),
	:global(input),
	:global(select),
	:global(textarea) {
		font: inherit;
	}

	:global(a) {
		color: inherit;
	}

	:global(a.text-link) {
		display: inline-flex;
		align-items: center;
		min-height: 44px;
	}

	@media (prefers-reduced-motion: reduce) {
		:global(*),
		:global(*::before),
		:global(*::after) {
			animation-duration: 0.01ms !important;
			animation-iteration-count: 1 !important;
			transition-duration: 0.01ms !important;
			scroll-behavior: auto !important;
		}
	}
</style>
