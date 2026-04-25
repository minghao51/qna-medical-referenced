<script lang="ts">
	import AppNav from '$lib/components/AppNav.svelte';

	type Props = {
		current: string;
		children: import('svelte').Snippet;
	};

	let { current, children }: Props = $props();
</script>

<div class="app-shell">
	<AppNav {current} />
	<div class="app-body">
		{@render children()}
	</div>
</div>

<style>
	.app-shell {
		max-width: 1380px;
		margin: 0 auto;
		padding: 1rem;
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
