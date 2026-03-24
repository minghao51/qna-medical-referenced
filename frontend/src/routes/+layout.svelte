<script lang="ts">
	import favicon from '$lib/assets/favicon.svg';

	let { children } = $props();
</script>

<svelte:head>
	<link rel="icon" href={favicon} />
	<title>Health Screening Q&A</title>
</svelte:head>

{@render children()}

<style>
	:global(*) {
		margin: 0;
		padding: 0;
		box-sizing: border-box;
	}

	:global(:root) {
		--page-bg: #f7f8fa;
		--surface-subtle: #f3f5f7;
		--surface-strong: #e9f0f7;
		--border-color: #dde3ea;
		--text-color: #18212b;
		--muted-color: #62707f;
		--accent-soft: #9db8d4;
	}

	:global(body) {
		font-family:
			'Instrument Sans',
			'Segoe UI',
			-apple-system,
			BlinkMacSystemFont,
			sans-serif;
		background: var(--page-bg);
		color: var(--text-color);
		line-height: 1.5;
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
</style>
