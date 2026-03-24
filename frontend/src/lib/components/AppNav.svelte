<script lang="ts">
	type NavItem = {
		href: string;
		label: string;
	};

	type Props = {
		current: string;
		compact?: boolean;
	};

	const navItems: NavItem[] = [
		{ href: '/', label: 'Chat' },
		{ href: '/eval', label: 'Pipeline Eval' },
		{ href: '/docs/pipeline', label: 'Pipeline Docs' }
	];

	let { current, compact = false }: Props = $props();
</script>

<nav class:compact class="app-nav" aria-label="Primary">
	<div class="nav-links">
		{#each navItems as item}
			<a
				href={item.href}
				class="nav-link"
				class:active={current === item.href}
				aria-current={current === item.href ? 'page' : undefined}
			>
				{item.label}
			</a>
		{/each}
	</div>
	<a
		href="https://github.com/anomalyco/qna_medical_referenced"
		target="_blank"
		rel="noopener noreferrer"
		class="github-link"
		aria-label="View on GitHub"
	>
		<svg viewBox="0 0 24 24" fill="currentColor" xmlns="http://www.w3.org/2000/svg">
			<path d="M12 0C5.37 0 0 5.37 0 12c0 5.31 3.435 9.795 8.205 11.385.6.105.825-.255.825-.57 0-.285-.015-1.23-.015-2.235-3.015.555-3.795-.735-4.035-1.41-.135-.345-.72-1.41-1.23-1.695-.42-.225-1.02-.78-.015-.795.945-.015 1.62.87 1.845 1.23 1.08 1.815 2.805 1.305 3.495.99.105-.78.42-1.305.765-1.605-2.67-.3-5.46-1.335-5.46-5.925 0-1.305.465-2.385 1.23-3.225-.12-.3-.54-1.53.12-3.18 0 0 1.005-.315 3.3 1.23.96-.27 1.98-.405 3-.405s2.04.135 3 .405c2.295-1.56 3.3-1.23 3.3-1.23.66 1.65.24 2.88.12 3.18.765.84 1.23 1.905 1.23 3.225 0 4.605-2.805 5.625-5.475 5.925.435.375.81 1.095.81 2.22 0 1.605-.015 2.895-.015 3.3 0 .315.225.69.825.57A12.02 12.02 0 0 0 24 12c0-6.63-5.37-12-12-12z" />
		</svg>
	</a>
</nav>

<style>
	.app-nav {
		display: flex;
		align-items: center;
		justify-content: space-between;
		gap: 1rem;
		padding: 0.75rem 0 1rem;
		border-bottom: 1px solid var(--border-color);
	}

	.nav-links {
		display: flex;
		flex-wrap: wrap;
		gap: 0.5rem;
	}

	.nav-link,
	.github-link {
		display: inline-flex;
		align-items: center;
		justify-content: center;
		min-height: 2.5rem;
		padding: 0.5rem 0.9rem;
		border-radius: 999px;
		color: var(--muted-color);
		text-decoration: none;
		font-weight: 600;
		transition: background 0.2s ease, color 0.2s ease, border-color 0.2s ease;
	}

	.nav-link:hover,
	.github-link:hover {
		background: var(--surface-subtle);
		color: var(--text-color);
	}

	.nav-link.active {
		background: var(--surface-strong);
		color: var(--text-color);
	}

	.github-link {
		flex-shrink: 0;
		border: 1px solid var(--border-color);
	}

	.github-link svg {
		width: 18px;
		height: 18px;
	}

	.compact {
		padding-top: 0;
	}

	@media (max-width: 700px) {
		.app-nav {
			align-items: flex-start;
		}

		.github-link {
			margin-left: auto;
		}
	}
</style>
