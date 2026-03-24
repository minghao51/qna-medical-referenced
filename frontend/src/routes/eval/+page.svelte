<script lang="ts">
	import { onMount } from 'svelte';
	import AppShell from '$lib/components/AppShell.svelte';
	import DrillDownModal from '$lib/components/DrillDownModal.svelte';
	import EmptyState from '$lib/components/EmptyState.svelte';
	import HealthScoreBadge from '$lib/components/HealthScoreBadge.svelte';
	import IngestionTab from '$lib/components/IngestionTab.svelte';
	import LoadingSkeleton from '$lib/components/LoadingSkeleton.svelte';
	import QualityTab from '$lib/components/QualityTab.svelte';
	import RetrievalTab from '$lib/components/RetrievalTab.svelte';
	import TabNav from '$lib/components/TabNav.svelte';
	import TrendingTab from '$lib/components/TrendingTab.svelte';
	import { exportCharts, exportToCSV, exportToJSON } from '$lib/utils/export';
	import { calculateHealthScore, getHealthGrade } from '$lib/utils/health-score';
	import {
		emptyDrillDownState,
		formatRunTimestampWithZone,
		historyLabel,
		selectionKey
	} from '$lib/utils/eval';
	import type {
		AblationResponse,
		DrillDownPoint,
		DrillDownRecord,
		EvalTabId,
		EvalTrendMetric,
		EvaluationHistoryResponse,
		EvaluationHistoryRun,
		EvaluationResponse
	} from '$lib/types';

	const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

	const tabs: Array<{ id: EvalTabId; label: string }> = [
		{ id: 'ingestion', label: 'Ingestion' },
		{ id: 'retrieval', label: 'Retrieval' },
		{ id: 'quality', label: 'Quality' },
		{ id: 'trending', label: 'Trending' }
	];

	let loading = $state(true);
	let refreshing = $state(false);
	let historyLoading = $state(true);
	let ablationLoading = $state(false);
	let error = $state('');
	let data = $state<EvaluationResponse | null>(null);
	let latestData = $state<EvaluationResponse | null>(null);
	let historyData = $state<EvaluationHistoryResponse | null>(null);
	let ablationData = $state<AblationResponse | null>(null);
	let activeTab = $state<EvalTabId>('ingestion');
	let selectedTrendMetric = $state<EvalTrendMetric>('hit_rate');
	let selectedRunKey = $state('');
	let urlStateReady = false;
	let drillDownModal = $state(emptyDrillDownState());

	const healthScore = $derived(data ? calculateHealthScore(data) : 0);
	const healthGrade = $derived(getHealthGrade(healthScore));

	function getStatusColor(status: string): string {
		return status === 'ok' ? '#4caf50' : '#f44336';
	}

	function applyUrlStateFromLocation() {
		const params = new URLSearchParams(window.location.search);
		const tab = params.get('tab');
		const metric = params.get('metric');
		activeTab = tab && tabs.some((item) => item.id === tab) ? (tab as EvalTabId) : 'ingestion';
		selectedTrendMetric =
			metric === 'mrr' || metric === 'latency' ? metric : 'hit_rate';
		selectedRunKey = params.get('run') || '';
	}

	function syncUrlState() {
		if (!urlStateReady) return;
		const params = new URLSearchParams();
		if (activeTab !== 'ingestion') params.set('tab', activeTab);
		if (selectedTrendMetric !== 'hit_rate') params.set('metric', selectedTrendMetric);
		if (selectedRunKey) params.set('run', selectedRunKey);
		window.history.replaceState({}, '', `${window.location.pathname}${params.toString() ? `?${params}` : ''}`);
	}

	async function loadData() {
		try {
			const response = await fetch(`${API_URL}/evaluation/latest`);
			if (!response.ok) throw new Error('Failed to fetch evaluation data');
			const payload = (await response.json()) as EvaluationResponse;
			latestData = payload;
			if (!selectedRunKey || selectedRunKey === selectionKey(payload) || !data) {
				selectedRunKey = selectionKey(payload);
				data = payload;
			}
			error = '';
		} catch (err) {
			error = 'Failed to load evaluation data. Make sure the API is running.';
			console.error(err);
		} finally {
			loading = false;
			refreshing = false;
		}
	}

	async function loadHistory() {
		try {
			const response = await fetch(`${API_URL}/evaluation/history?limit=20`);
			if (response.ok) {
				historyData = (await response.json()) as EvaluationHistoryResponse;
			}
		} catch (err) {
			console.error('Failed to load history:', err);
		} finally {
			historyLoading = false;
		}
	}

	async function loadAblationResults() {
		try {
			ablationLoading = true;
			const response = await fetch(`${API_URL}/evaluation/ablation`);
			if (response.ok) {
				ablationData = (await response.json()) as AblationResponse;
			}
		} catch (err) {
			console.error('Failed to load ablation results:', err);
		} finally {
			ablationLoading = false;
		}
	}

	function runDetailUrl(run: EvaluationHistoryRun): string {
		return `${API_URL}/evaluation/run/${encodeURIComponent(run.run_dir)}`;
	}

	async function loadRun(runKey: string): Promise<EvaluationResponse | null> {
		if (latestData && selectionKey(latestData) === runKey) return latestData;
		const run = (historyData?.runs ?? []).find((item) => selectionKey(item) === runKey);
		if (!run) return null;
		try {
			const response = await fetch(runDetailUrl(run));
			if (response.ok) return (await response.json()) as EvaluationResponse;
		} catch (err) {
			console.error('Failed to load run:', err);
		}
		return null;
	}

	async function selectRun(runKey: string) {
		selectedRunKey = runKey;
		const selected = await loadRun(runKey);
		if (selected) data = selected;
	}

	async function refresh() {
		refreshing = true;
		await loadData();
		if (selectedRunKey && latestData && selectedRunKey !== selectionKey(latestData)) {
			const selected = await loadRun(selectedRunKey);
			if (selected) data = selected;
		}
	}

	function selectedRunLabel(): string {
		const run = (historyData?.runs ?? []).find((item) => selectionKey(item) === selectedRunKey);
		if (run) return historyLabel(run);
		return latestData ? historyLabel(latestData) : 'Latest run';
	}

	function showMetricDrillDown(
		stage: string,
		metricName: string,
		currentValue: number,
		records: DrillDownRecord[] = [],
		historicalData: DrillDownPoint[] = []
	) {
		drillDownModal = {
			open: true,
			metric: metricName,
			stage,
			currentValue,
			records,
			historicalData
		};
	}

	$effect(() => {
		syncUrlState();
	});

	onMount(async () => {
		applyUrlStateFromLocation();
		await Promise.all([loadData(), loadHistory(), loadAblationResults()]);
		if (selectedRunKey && latestData && selectedRunKey !== selectionKey(latestData)) {
			const selected = await loadRun(selectedRunKey);
			if (selected) data = selected;
		}
		urlStateReady = true;
	});
</script>

<svelte:head>
	<title>Pipeline Eval</title>
</svelte:head>

<AppShell current="/eval">
	<div class="eval-container">
		<div class="page-header">
			<div class="page-copy">
				<p class="eyebrow">Evaluation dashboard</p>
				<h1>Pipeline quality assessment</h1>
				<p class="subtitle">Focused on health, regression risk, and historical movement.</p>
			</div>
			{#if data}
				<HealthScoreBadge score={healthScore} grade={healthGrade} />
			{/if}
		</div>

		{#if data?.summary}
			<div class="run-bar">
				<div class="run-bar-primary">
					<span class="status-pill" style={`background:${getStatusColor(data.summary.status)}`}>
						{data.summary.status.toUpperCase()}
					</span>
					<div>
						<strong>{selectedRunLabel()}</strong>
						<p>{formatRunTimestampWithZone(data)}</p>
					</div>
				</div>
				<div class="run-bar-meta">
					<span>Duration {data.summary.duration_s.toFixed(2)}s</span>
					<span>{data.summary.failed_thresholds_count} failed thresholds</span>
				</div>
				<div class="run-bar-actions">
					<button type="button" class="action-btn" onclick={() => data && exportToCSV(data)} disabled={!data}>Export CSV</button>
					<button type="button" class="action-btn" onclick={() => data && exportToJSON(data)} disabled={!data}>Export JSON</button>
					<button type="button" class="action-btn" onclick={exportCharts} disabled={!data}>Export Charts</button>
					<button type="button" class="action-btn" onclick={refresh} disabled={refreshing}>
						{refreshing ? 'Refreshing...' : 'Refresh'}
					</button>
				</div>
			</div>
		{/if}

		<div class="tabs-wrap">
			<TabNav tabs={tabs} {activeTab} onchange={(id) => (activeTab = id as EvalTabId)} label="Evaluation tabs" />
		</div>

		{#if loading}
			<div class="loading-panel">
				<LoadingSkeleton count={3} type="card" />
			</div>
		{:else if error}
			<div class="error-panel">{error}</div>
		{:else if !data || (!data.summary && !data.step_metrics && !data.retrieval_metrics)}
			<EmptyState title="No evaluation data available" body="Run an evaluation to populate the dashboard." />
		{:else}
			{#if activeTab === 'ingestion'}
				<IngestionTab {data} />
			{:else if activeTab === 'retrieval'}
				<RetrievalTab {data} onDrillDown={showMetricDrillDown} />
			{:else if activeTab === 'quality'}
				<QualityTab {data} onDrillDown={showMetricDrillDown} />
			{:else}
				<TrendingTab
					{historyData}
					{historyLoading}
					{ablationData}
					{ablationLoading}
					{selectedRunKey}
					{data}
					{selectedTrendMetric}
					onTrendMetricChange={(metric) => (selectedTrendMetric = metric)}
					onSelectRun={selectRun}
					onRefreshHistory={loadHistory}
				/>
			{/if}
		{/if}
	</div>

	<DrillDownModal
		open={drillDownModal.open}
		onclose={() => (drillDownModal.open = false)}
		metric={drillDownModal.metric}
		stage={drillDownModal.stage}
		currentValue={drillDownModal.currentValue}
		records={drillDownModal.records}
		historicalData={drillDownModal.historicalData}
	/>
</AppShell>

<style>
	.eval-container {
		display: grid;
		gap: 1rem;
	}

	.page-header {
		display: flex;
		align-items: flex-start;
		justify-content: space-between;
		gap: 1rem;
		flex-wrap: wrap;
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
		margin: 0.2rem 0 0;
	}

	.subtitle {
		margin-top: 0.45rem;
		color: var(--muted-color);
		max-width: 42rem;
	}

	.run-bar,
	.tabs-wrap,
	.loading-panel,
	.error-panel {
		padding: 1rem;
		border: 1px solid var(--border-color);
		border-radius: 18px;
		background: white;
	}

	.run-bar {
		display: flex;
		flex-wrap: wrap;
		gap: 1rem;
		align-items: center;
		justify-content: space-between;
	}

	.run-bar-primary {
		display: flex;
		align-items: center;
		gap: 0.75rem;
	}

	.run-bar-primary p,
	.run-bar-meta {
		color: var(--muted-color);
		font-size: 0.9rem;
	}

	.run-bar-actions,
	.run-bar-meta {
		display: flex;
		flex-wrap: wrap;
		gap: 0.6rem 1rem;
	}

	.status-pill {
		padding: 0.3rem 0.55rem;
		border-radius: 999px;
		color: white;
		font-size: 0.78rem;
		font-weight: 700;
	}

	.action-btn {
		padding: 0.65rem 0.95rem;
		border: 1px solid var(--border-color);
		border-radius: 999px;
		background: white;
		cursor: pointer;
	}

	.action-btn:disabled {
		opacity: 0.6;
		cursor: not-allowed;
	}

	.error-panel {
		color: #b42318;
		background: #fff5f5;
	}
</style>
