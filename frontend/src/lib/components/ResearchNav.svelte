<script lang="ts">
	type Props = {
		current: string;
	};

	type Item = {
		href: string;
		label: string;
	};

	// Every rendered destination is a working route. Dataset cases and
	// methodology are read-only projections from their approved sources.
	const items: Item[] = [
		{ href: '/', label: 'Workspace' },
		{ href: '/research/evaluations', label: 'Evaluations' },
		{ href: '/research/features', label: 'Features' },
		{ href: '/research/datasets', label: 'Datasets' },
		{ href: '/research/methodology', label: 'Methodology' }
	];

	let { current }: Props = $props();
</script>

<nav class="research-nav" aria-label="Research">
	<span class="research-label">Research</span>
	{#each items as item}
		<a
			href={item.href}
			class="research-link"
			class:active={current === item.href}
			aria-current={current === item.href ? 'page' : undefined}
		>
			{item.label}
		</a>
	{/each}
</nav>

<style>
	.research-nav {
		display: flex;
		flex-wrap: wrap;
		align-items: center;
		gap: 0.35rem;
		padding: 0.35rem 0;
	}

	.research-label {
		margin-right: 0.35rem;
		color: var(--muted-color);
		font-size: 0.68rem;
		letter-spacing: 0.12em;
		text-transform: uppercase;
	}

	.research-link {
		display: inline-flex;
		align-items: center;
		min-height: 36px;
		padding: 0.35rem 0.75rem;
		border-radius: 999px;
		color: var(--muted-color);
		font-size: 0.9rem;
		font-weight: 600;
		text-decoration: none;
	}

	.research-link:hover {
		background: var(--surface-subtle);
		color: var(--ink);
	}

	.research-link.active {
		background: var(--ink);
		color: var(--paper);
	}

	@media (max-width: 640px) {
		.research-label {
			width: 100%;
		}
	}
</style>
