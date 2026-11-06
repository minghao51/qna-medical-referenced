<script lang="ts">
	type NavItem = {
		href: string;
		label: string;
	};

	type Props = {
		current: string;
	};

	const primaryItems: NavItem[] = [
		{ href: '/', label: 'Overview' },
		{ href: '/ask', label: 'Ask' },
		{ href: '/evidence', label: 'Evidence' }
	];

	// Legacy diagnostic destinations remain reachable while the research
	// subpages land in later slices.
	const researchItems: NavItem[] = [
		{ href: '/', label: 'Workspace' },
		{ href: '/research/evaluations', label: 'Evaluations' },
		{ href: '/research/methodology', label: 'Methodology' },
		{ href: '/research/features', label: 'Features' },
		{ href: '/research/datasets', label: 'Datasets' },
		{ href: '/eval/ablation', label: 'Ablation study' },
		{ href: '/docs/pipeline', label: 'Pipeline documentation' },
		{ href: '/help', label: 'Help' },
		{ href: '/settings', label: 'Settings' },
		{ href: '/health', label: 'System health' }
	];

	let { current }: Props = $props();
	let researchOpen = $state(false);
	let mobileOpen = $state(false);
	let researchButton: HTMLButtonElement | undefined = $state();
	let mobileButton: HTMLButtonElement | undefined = $state();

	const researchActive = $derived(
		current.startsWith('/research') ||
			researchItems.some(
				(item) => item.href !== '/' && (current === item.href || current.startsWith(`${item.href}/`))
			)
	);

	function closeResearch() {
		researchOpen = false;
		researchButton?.focus();
	}

	function closeMobile() {
		mobileOpen = false;
		mobileButton?.focus();
	}

	function handleKeydown(event: KeyboardEvent) {
		if (event.key !== 'Escape') return;
		if (researchOpen) closeResearch();
		if (mobileOpen) closeMobile();
	}
</script>

<svelte:window onkeydown={handleKeydown} />

<header class="app-nav">
	<a class="brand" href="/" aria-label="Fieldnote overview">FIELDNOTE</a>
	<p class="lab-note">Private lab · public + synthetic data</p>

	<nav class="desktop-nav" aria-label="Primary">
		{#each primaryItems as item}
			<a
				href={item.href}
				class="nav-link"
				class:active={current === item.href || current.startsWith(`${item.href}/`)}
				aria-current={current === item.href ? 'page' : undefined}
			>
				{item.label}
			</a>
		{/each}

		<div class="menu-wrap">
			<button
				bind:this={researchButton}
				type="button"
				class="nav-link menu-trigger"
				class:active={researchActive}
				aria-expanded={researchOpen}
				aria-haspopup="true"
				onclick={() => (researchOpen = !researchOpen)}
			>
				Research
				<span class="chevron" class:open={researchOpen} aria-hidden="true">▾</span>
			</button>

			{#if researchOpen}
				<button
					type="button"
					class="menu-backdrop"
					aria-label="Close research menu"
					onclick={closeResearch}
				></button>
				<div class="dropdown" role="menu">
					{#each researchItems as item}
						<a
							href={item.href}
							class="dropdown-item"
							class:active={current === item.href}
							role="menuitem"
							onclick={() => (researchOpen = false)}
						>
							{item.label}
						</a>
					{/each}
				</div>
			{/if}
		</div>
	</nav>

	<button
		bind:this={mobileButton}
		type="button"
		class="menu-button"
		aria-expanded={mobileOpen}
		aria-controls="mobile-menu"
		onclick={() => (mobileOpen = !mobileOpen)}
	>
		Menu
	</button>

	{#if mobileOpen}
		<button
			type="button"
			class="mobile-backdrop"
			aria-label="Close menu"
			onclick={closeMobile}
		></button>
		<nav id="mobile-menu" class="mobile-panel" aria-label="Menu">
			<p class="menu-heading">Primary</p>
			{#each primaryItems as item}
				<a
					href={item.href}
					class="mobile-link"
					class:active={current === item.href}
					aria-current={current === item.href ? 'page' : undefined}
					onclick={() => (mobileOpen = false)}
				>
					{item.label}
				</a>
			{/each}
			<p class="menu-heading">Research</p>
			{#each researchItems as item}
				<a
					href={item.href}
					class="mobile-link"
					class:active={current === item.href}
					onclick={() => (mobileOpen = false)}
				>
					{item.label}
				</a>
			{/each}
		</nav>
	{/if}
</header>

<style>
	.app-nav {
		position: relative;
		z-index: 20;
		display: flex;
		align-items: center;
		gap: 1.5rem;
		padding: 0.75rem 0 1rem;
		border-bottom: 1px solid var(--border-color);
	}

	.brand {
		display: inline-flex;
		align-items: center;
		gap: 0.55rem;
		min-height: 44px;
		font-family: var(--font-heading);
		font-size: 1.05rem;
		font-weight: 700;
		letter-spacing: 0.16em;
		color: var(--ink);
		text-decoration: none;
		white-space: nowrap;
	}

	.brand::before {
		content: '';
		width: 5px;
		height: 1.35rem;
		background: var(--rust);
	}

	.lab-note {
		margin: 0;
		color: var(--muted-color);
		font-size: 0.72rem;
		letter-spacing: 0.08em;
		text-transform: uppercase;
	}

	.desktop-nav {
		display: flex;
		align-items: center;
		gap: 0.25rem;
		margin-left: auto;
	}

	.nav-link {
		display: inline-flex;
		align-items: center;
		justify-content: center;
		min-height: 44px;
		padding: 0.45rem 0.85rem;
		border: none;
		border-radius: 6px;
		background: transparent;
		color: var(--muted-color);
		font: inherit;
		font-weight: 600;
		text-decoration: none;
		cursor: pointer;
	}

	.nav-link:hover,
	.menu-button:hover {
		background: var(--surface-subtle);
		color: var(--ink);
	}

	.nav-link.active {
		border-radius: 0;
		background: transparent;
		color: var(--teal);
		box-shadow: inset 0 -2px 0 var(--teal);
	}

	.menu-trigger {
		gap: 0.35rem;
	}

	.chevron {
		font-size: 0.7rem;
		transition: transform 0.15s ease;
	}

	.chevron.open {
		transform: rotate(180deg);
	}

	.menu-wrap {
		position: relative;
	}

	.menu-backdrop {
		position: fixed;
		inset: 0;
		z-index: 30;
		border: none;
		background: transparent;
		cursor: default;
	}

	.dropdown {
		position: absolute;
		top: calc(100% + 0.35rem);
		right: 0;
		z-index: 40;
		min-width: 14rem;
		padding: 0.4rem;
		border: 1px solid var(--border-color);
		border-radius: 10px;
		background: #fffdf8;
		box-shadow: 0 12px 30px rgb(24 45 50 / 16%);
	}

	.dropdown-item {
		display: block;
		padding: 0.65rem 0.8rem;
		border-radius: 6px;
		color: var(--muted-color);
		font-size: 0.9rem;
		font-weight: 600;
		text-decoration: none;
	}

	.dropdown-item:hover,
	.dropdown-item.active {
		background: var(--surface-subtle);
		color: var(--ink);
	}

	.menu-button {
		display: none;
		margin-left: auto;
		min-height: 44px;
		padding: 0.5rem 1rem;
		border: 1px solid var(--border-color);
		border-radius: 6px;
		background: transparent;
		color: var(--ink);
		font: inherit;
		font-weight: 600;
		cursor: pointer;
	}

	.mobile-backdrop {
		position: fixed;
		inset: 0;
		z-index: 30;
		border: none;
		background: rgb(24 45 50 / 28%);
	}

	.mobile-panel {
		position: absolute;
		top: calc(100% - 0.5rem);
		left: 0;
		right: 0;
		z-index: 40;
		display: flex;
		flex-direction: column;
		padding: 0.75rem;
		border: 1px solid var(--border-color);
		border-radius: 10px;
		background: #fffdf8;
		box-shadow: 0 12px 30px rgb(24 45 50 / 16%);
	}

	.menu-heading {
		margin: 0.6rem 0 0.25rem;
		padding: 0 0.65rem;
		color: var(--muted-color);
		font-size: 0.68rem;
		letter-spacing: 0.12em;
		text-transform: uppercase;
	}

	.mobile-link {
		display: flex;
		align-items: center;
		min-height: 44px;
		padding: 0.5rem 0.65rem;
		border-radius: 6px;
		color: var(--ink);
		font-weight: 600;
		text-decoration: none;
	}

	.mobile-link:hover,
	.mobile-link.active {
		background: var(--surface-subtle);
	}

	@media (max-width: 860px) {
		.lab-note {
			display: none;
		}

		.desktop-nav {
			display: none;
		}

		.menu-button {
			display: inline-flex;
			align-items: center;
		}
	}
</style>
