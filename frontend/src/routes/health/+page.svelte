<script lang="ts">
	import { onMount } from 'svelte';
	import AppShell from '$lib/components/AppShell.svelte';
	import EmptyState from '$lib/components/EmptyState.svelte';
	import LoadingSkeleton from '$lib/components/LoadingSkeleton.svelte';
	import { fetchHealthStatus } from '$lib/utils/api';
	import type { HealthResponse } from '$lib/types';

	let loading = $state(true);
	let error = $state('');
	let health = $state<HealthResponse | null>(null);
	let lastChecked = $state('');

	async function load() {
		try {
			health = await fetchHealthStatus();
			lastChecked = new Date().toLocaleTimeString();
			error = '';
		} catch (e) {
			error = e instanceof Error ? e.message : 'Failed to load health status';
		} finally {
			loading = false;
		}
	}

	onMount(() => {
		load();
		const interval = setInterval(load, 30000);
		return () => clearInterval(interval);
	});
</script>

<svelte:head>
	<title>System Health</title>
</svelte:head>

<AppShell current="/health">
	<div class="health-page">
		<div class="page-header">
			<p class="eyebrow">Monitoring</p>
			<h1>System health</h1>
			<p class="subtitle">Live status of the backend, vector store, and rate limiter.</p>
		</div>

		{#if loading}
			<LoadingSkeleton count={3} type="card" />
		{:else if error}
			<EmptyState title="Backend unreachable" body={error} />
		{:else if !health}
			<EmptyState title="No health data" body="The backend returned an empty response." />
		{:else}
			<div class="status-grid">
				<section class="status-card overall">
					<h2>Overall</h2>
					<span class="status-dot" class:healthy={health.status === 'healthy'} class:unhealthy={health.status === 'unhealthy'} class:degraded={health.status === 'degraded'}></span>
					<span class="status-label">{health.status.toUpperCase()}</span>
					{#if lastChecked}
						<p class="last-checked">Last checked: {lastChecked}</p>
					{/if}
				</section>

				<section class="status-card">
					<h2>Vector Store</h2>
					{#if health.vector_store}
						<dl class="kv-list">
							<div class="kv-row"><dt>Initialized</dt><dd class:ok={health.vector_store.initialized} class:warn={!health.vector_store.initialized}>{health.vector_store.initialized ? 'Yes' : 'No'}</dd></div>
							{#if health.vector_store.signature}
								<div class="kv-row"><dt>Signature</dt><dd class="mono">{health.vector_store.signature.slice(0, 12)}…</dd></div>
							{/if}
						</dl>
					{:else}
						<p class="muted">No vector store data</p>
					{/if}
				</section>

				<section class="status-card">
					<h2>Rate Limiting</h2>
					{#if health.rate_limit}
						<dl class="kv-list">
							<div class="kv-row"><dt>Backend</dt><dd>{health.rate_limit.backend ?? '—'}</dd></div>
							<div class="kv-row"><dt>Window</dt><dd>{health.rate_limit.window_seconds ? `${health.rate_limit.window_seconds}s` : '—'}</dd></div>
						</dl>
					{:else}
						<p class="muted">No rate limit data</p>
					{/if}
				</section>

				{#if health.runtime}
					<section class="status-card runtime-card">
						<h2>Runtime</h2>
						<dl class="kv-list">
							{#each Object.entries(health.runtime) as [key, val]}
								{@const valueText = typeof val === 'object' ? JSON.stringify(val) : String(val)}
								<div class="kv-row">
									<dt>{key}</dt>
									<dd>
										{#if valueText.length > 80}
											<details class="runtime-detail">
												<summary aria-label={`Show full value for ${key}`}>
													{valueText.slice(0, 72)}…
												</summary>
												<pre>{valueText}</pre>
											</details>
										{:else}
											{valueText}
										{/if}
									</dd>
								</div>
							{/each}
						</dl>
					</section>
				{/if}
			</div>

			<div class="actions">
				<button type="button" class="refresh-btn" onclick={load}>
					Refresh
				</button>
			</div>
		{/if}
	</div>
</AppShell>

<style>
	.health-page {
		display: flex;
		flex-direction: column;
		gap: 1rem;
	}

	.page-header {
		display: flex;
		flex-direction: column;
		gap: 0.25rem;
	}

	.eyebrow {
		font-size: 0.8rem;
		text-transform: uppercase;
		letter-spacing: 0.08em;
		color: var(--muted-color);
	}

	h1 {
		font-size: 2rem;
		line-height: 1.1;
		margin: 0;
	}

	.subtitle {
		max-width: 42rem;
		color: var(--muted-color);
	}

	.status-grid {
		display: grid;
		grid-template-columns: repeat(auto-fit, minmax(260px, 1fr));
		align-items: start;
		gap: 1rem;
	}

	.runtime-card {
		grid-column: 1 / -1;
	}

	.status-card {
		padding: 1rem;
		border: 1px solid var(--border-color);
		border-radius: 18px;
		background: white;
	}

	.status-card.overall {
		display: flex;
		flex-wrap: wrap;
		align-items: center;
		gap: 0.6rem;
	}

	.status-card h2 {
		font-size: 0.95rem;
		margin: 0 0 0.6rem;
		color: var(--muted-color);
		text-transform: uppercase;
		letter-spacing: 0.04em;
	}

	.status-card.overall h2 {
		margin: 0;
	}

	.status-dot {
		width: 12px;
		height: 12px;
		border-radius: 50%;
		background: #ccc;
	}

	.status-dot.healthy {
		background: #10b981;
		box-shadow: 0 0 6px rgba(16, 185, 129, 0.4);
	}

	.status-dot.unhealthy {
		background: #ef4444;
		box-shadow: 0 0 6px rgba(239, 68, 68, 0.4);
	}

	.status-dot.degraded {
		background: #f59e0b;
		box-shadow: 0 0 6px rgba(245, 158, 11, 0.4);
	}

	.status-label {
		font-weight: 700;
		font-size: 1.1rem;
	}

	.last-checked {
		width: 100%;
		font-size: 0.8rem;
		color: var(--muted-color);
		margin: 0;
	}

	.kv-list {
		display: grid;
		gap: 0.35rem;
		margin: 0;
	}

	.kv-row {
		display: grid;
		grid-template-columns: minmax(8rem, auto) minmax(0, 1fr);
		align-items: start;
		gap: 1rem;
		padding: 0.3rem 0;
		border-bottom: 1px solid var(--surface-subtle);
		font-size: 0.88rem;
	}

	.kv-row:last-child {
		border-bottom: none;
	}

	dt {
		color: var(--muted-color);
		font-weight: 500;
	}

	dd {
		min-width: 0;
		margin: 0;
		font-weight: 600;
		overflow-wrap: anywhere;
		text-align: right;
	}

	dd.ok {
		color: var(--success);
	}

	dd.warn {
		color: #d97706;
	}

	dd.mono {
		font-family: monospace;
		font-size: 0.82rem;
	}

	.runtime-detail {
		text-align: left;
	}

	.runtime-detail summary {
		color: var(--teal);
		cursor: pointer;
		overflow-wrap: anywhere;
	}

	@media (max-width: 480px) {
		.kv-row {
			grid-template-columns: minmax(0, 1fr);
			gap: 0.15rem;
		}

		dd {
			text-align: left;
		}
	}

	.runtime-detail pre {
		max-height: 14rem;
		margin: 0.5rem 0 0;
		padding: 0.6rem;
		overflow: auto;
		border: 1px solid var(--border-color);
		border-radius: 6px;
		background: var(--surface-subtle);
		white-space: pre-wrap;
		overflow-wrap: anywhere;
		font-size: 0.72rem;
		text-align: left;
	}

	.muted {
		color: var(--muted-color);
		font-size: 0.88rem;
		margin: 0;
	}

	.actions {
		display: flex;
		gap: 0.5rem;
	}

	.refresh-btn {
		padding: 0.55rem 1rem;
		border: 1px solid var(--border-color);
		border-radius: 999px;
		background: white;
		cursor: pointer;
		font-weight: 500;
	}

	.refresh-btn:hover {
		background: var(--surface-subtle);
	}
</style>
