<script lang="ts">
	import AppNav from '$lib/components/AppNav.svelte';

	type Props = {
		current: string;
		wide?: boolean;
		children: import('svelte').Snippet;
	};

	let { current, wide = false, children }: Props = $props();
</script>

<div class:wide class="app-shell">
	<AppNav {current} />
	<div class="app-body">
		{@render children()}
	</div>
</div>

<style>
	.app-shell {
		max-width: 1100px;
		margin: 0 auto;
		padding: 1rem;
	}

	.app-shell.wide {
		max-width: 1380px;
	}

	.app-body {
		display: flex;
		flex-direction: column;
		gap: 1rem;
		padding: 1rem 0 1.5rem;
	}

	@media (max-width: 700px) {
		.app-shell {
			padding: 0.75rem;
		}
	}
</style>
