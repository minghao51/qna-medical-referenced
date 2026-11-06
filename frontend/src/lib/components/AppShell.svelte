<script lang="ts">
	import AppNav from '$lib/components/AppNav.svelte';

	type Props = {
		current: string;
		children: import('svelte').Snippet;
	};

	let { current, children }: Props = $props();
</script>

<a class="skip-link" href="#main-content">Skip to main content</a>
<div class="app-shell">
	<AppNav {current} />
	<main id="main-content" class="app-body" tabindex="-1">
		{@render children()}
	</main>
</div>

<style>
	.skip-link {
		position: absolute;
		left: 1rem;
		top: -4rem;
		z-index: 1000;
		padding: 0.75rem 1rem;
		border-radius: 0 0 8px 8px;
		background: var(--ink);
		color: var(--paper);
		font-weight: 700;
		text-decoration: none;
	}

	.skip-link:focus {
		top: 0;
	}

	.app-shell {
		max-width: 1440px;
		margin: 0 auto;
		padding: 1.25rem 48px 2rem;
	}

	.app-body {
		display: flex;
		flex-direction: column;
		gap: 1.5rem;
		width: 100%;
		max-width: 1344px;
		margin: 0 auto;
		padding: 1.5rem 0 2rem;
		outline: none;
	}

	@media (max-width: 1024px) {
		.app-shell {
			padding: 1rem 24px 1.5rem;
		}

		.app-body {
			padding-top: 1rem;
		}
	}
</style>
