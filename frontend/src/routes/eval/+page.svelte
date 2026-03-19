<script lang="ts">
	import { onMount } from 'svelte';
	import Tooltip from '$lib/components/Tooltip.svelte';
	import { stageNames, metricDefinitions } from '$lib/utils/metric-definitions';

	import type {
		EvaluationHistoryResponse,
		EvaluationHistoryRun,
		EvaluationResponse,
		RetrievalMetrics,
		StepMetrics
	} from '$lib/types';
	import MetricChart from '$lib/components/MetricChart.svelte';
	import QualityDistributionChart from '$lib/components/QualityDistributionChart.svelte';
	import HealthScoreBadge from '$lib/components/HealthScoreBadge.svelte';
	import SourceDistributionChart from '$lib/components/SourceDistributionChart.svelte';
	import CategoryBreakdownChart from '$lib/components/CategoryBreakdownChart.svelte';
	import MultiSelect from '$lib/components/MultiSelect.svelte';
	import DrillDownModal from '$lib/components/DrillDownModal.svelte';
	import ThresholdEditor from '$lib/components/ThresholdEditor.svelte';
	import LoadingSkeleton from '$lib/components/LoadingSkeleton.svelte';
	import { calculateHealthScore, getHealthGrade } from '$lib/utils/health-score';
	import { exportToCSV, exportToJSON, exportCharts } from '$lib/utils/export';

	let loading = $state(true);
	let refreshing = $state(false);
	let error = $state('');
	let data = $state<EvaluationResponse | null>(null);
	let latestData = $state<EvaluationResponse | null>(null);
	let historyData = $state<EvaluationHistoryResponse | null>(null);
	let historyLoading = $state(true);
	let selectedTrendMetric = $state<'hit_rate' | 'mrr' | 'latency'>('hit_rate');
	let experimentFilter = $state('');
	let selectedRunKey = $state('');
	let urlStateReady = false;

	// Comparison mode
	let compareMode = $state(false);
	let baselineRun = $state<string>('');
	let compareRun = $state<string>('');
	let comparisonData = $state<{ baseline: EvaluationResponse | null; comparison: EvaluationResponse | null }>({
		baseline: null,
		comparison: null
	});

	// Filtering
	let searchQuery = $state('');
	let selectedStages = $state<string[]>(['L0', 'L1', 'L2', 'L3', 'L4', 'L5']);
	const allStages = ['L0', 'L1', 'L2', 'L3', 'L4', 'L5'];

	// Drill-down modal
	let drillDownModal = $state({
		open: false,
		metric: '',
		stage: '',
		currentValue: 0,
		records: [] as any[],
		historicalData: [] as Array<{ timestamp: string; value: number }>
	});

	// Ablation results
	let ablationData = $state<{ ablation_runs: any[]; message?: string } | null>(null);
	let ablationLoading = $state(false);

	const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

	function parseRunDate(raw: string | null | undefined): Date | null {
		if (!raw) return null;
		const match = raw.match(
			/(\d{4})(\d{2})(\d{2})T(\d{2})(\d{2})(\d{2})(?:\.(\d{1,6}))?Z?/
		);
		if (!match) return null;

		const [, year, month, day, hour, minute, second, fraction = '0'] = match;
		const milliseconds = Number(fraction.padEnd(3, '0').slice(0, 3));
		return new Date(
			Date.UTC(
				Number(year),
				Number(month) - 1,
				Number(day),
				Number(hour),
				Number(minute),
				Number(second),
				milliseconds
			)
		);
	}

	function extractRunTimestamp(run: EvaluationHistoryRun | EvaluationResponse): string {
		return ('timestamp' in run ? run.timestamp : '') || run.run_dir || '';
	}

	function formatRunTimestamp(
		run: EvaluationHistoryRun | EvaluationResponse,
		options: Intl.DateTimeFormatOptions = {
			month: 'short',
			day: 'numeric',
			hour: 'numeric',
			minute: '2-digit'
		}
	): string {
		const parsed = parseRunDate(extractRunTimestamp(run));
		return parsed ? parsed.toLocaleString(undefined, options) : extractRunTimestamp(run) || 'N/A';
	}

	function formatRunTimestampWithZone(run: EvaluationHistoryRun | EvaluationResponse): string {
		const parsed = parseRunDate(extractRunTimestamp(run));
		return parsed
			? parsed.toLocaleString(undefined, {
					year: 'numeric',
					month: 'short',
					day: 'numeric',
					hour: 'numeric',
					minute: '2-digit',
					second: '2-digit',
					timeZoneName: 'short'
				})
			: extractRunTimestamp(run) || 'N/A';
	}

	function buildHistoryUrl(): string {
		const params = new URLSearchParams({ limit: '20' });
		return `${API_URL}/evaluation/history?${params.toString()}`;
	}

	function formatPercent(value: number): string {
		return (value * 100).toFixed(1) + '%';
	}

	function getStatusColor(status: string): string {
		return status === 'ok' ? '#4caf50' : '#f44336';
	}

	function getMetricStatus(value: number, threshold: number, op: 'min' | 'max'): boolean {
		if (op === 'min') return value >= threshold;
		return value <= threshold;
	}

	function applyUrlStateFromLocation() {
		const params = new URLSearchParams(window.location.search);
		searchQuery = params.get('q') || '';
		experimentFilter = params.get('history_q') || '';
		selectedStages = params.get('stages')?.split(',').filter(Boolean) || [...allStages];
		selectedTrendMetric =
			(params.get('metric') as 'hit_rate' | 'mrr' | 'latency' | null) || 'hit_rate';
		compareMode = params.get('compare') === '1';
		baselineRun = params.get('baseline') || '';
		compareRun = params.get('candidate') || '';
		selectedRunKey = params.get('run') || '';
	}

	function syncUrlState() {
		if (!urlStateReady) return;

		const params = new URLSearchParams();
		if (searchQuery.trim()) params.set('q', searchQuery.trim());
		if (experimentFilter.trim()) params.set('history_q', experimentFilter.trim());
		if (selectedStages.length && selectedStages.length !== allStages.length) {
			params.set('stages', selectedStages.join(','));
		}
		if (selectedTrendMetric !== 'hit_rate') params.set('metric', selectedTrendMetric);
		if (compareMode) params.set('compare', '1');
		if (baselineRun) params.set('baseline', baselineRun);
		if (compareRun) params.set('candidate', compareRun);
		if (selectedRunKey) params.set('run', selectedRunKey);

		const next = `${window.location.pathname}${params.toString() ? `?${params}` : ''}`;
		window.history.replaceState({}, '', next);
	}

	async function loadData() {
		try {
			const res = await fetch(`${API_URL}/evaluation/latest`);
			if (!res.ok) {
				throw new Error('Failed to fetch evaluation data');
			}
			const payload = (await res.json()) as EvaluationResponse;
			latestData = payload;
			if (!selectedRunKey || selectedRunKey === `local:${payload.run_dir}` || !data) {
				selectedRunKey = `local:${payload.run_dir}`;
				data = payload;
			}
			error = '';
		} catch (e) {
			error = 'Failed to load evaluation data. Make sure the API is running.';
			console.error(e);
		} finally {
			loading = false;
			refreshing = false;
		}
	}

	async function refresh() {
		refreshing = true;
		await loadData();
		if (selectedRunKey && data && selectedRunKey !== `local:${latestData?.run_dir}`) {
			const selected = await loadRun(selectedRunKey);
			if (selected) data = selected;
		}
	}

	async function loadHistory() {
		try {
			const res = await fetch(buildHistoryUrl());
			if (res.ok) {
				historyData = await res.json();
			}
		} catch (e) {
			console.error('Failed to load history:', e);
		} finally {
			historyLoading = false;
		}
	}

	async function loadAblationResults() {
		try {
			ablationLoading = true;
			const res = await fetch(`${API_URL}/evaluation/ablation`);
			if (res.ok) {
				ablationData = await res.json();
			}
		} catch (e) {
			console.error('Failed to load ablation results:', e);
		} finally {
			ablationLoading = false;
		}
	}

	function selectionKey(run: EvaluationHistoryRun): string {
		return `local:${run.run_dir}`;
	}

	function runDetailUrl(run: EvaluationHistoryRun): string {
		return `${API_URL}/evaluation/run/${encodeURIComponent(run.run_dir)}`;
	}

	async function loadRun(runDir: string): Promise<EvaluationResponse | null> {
		if (latestData && `local:${latestData.run_dir}` === runDir) {
			return latestData;
		}
		const run = (historyData?.runs || []).find((item) => selectionKey(item) === runDir);
		if (!run) return null;
		try {
			const res = await fetch(runDetailUrl(run));
			if (res.ok) {
				return await res.json();
			}
		} catch (e) {
			console.error('Failed to load run:', e);
		}
		return null;
	}

	async function selectRun(runKey: string) {
		selectedRunKey = runKey;
		const selected = await loadRun(runKey);
		if (selected) {
			data = selected;
		}
	}

	async function loadComparisonData() {
		if (baselineRun) {
			comparisonData.baseline = await loadRun(baselineRun);
		}
		if (compareRun) {
			comparisonData.comparison = await loadRun(compareRun);
		}
	}

	async function handleExportCSV() {
		if (data) {
			await exportToCSV(data);
		}
	}

	async function handleExportJSON() {
		if (data) {
			await exportToJSON(data);
		}
	}

	async function handleExportCharts() {
		await exportCharts();
	}

	function getMetricDelta(baseline: number, comparison: number): { value: number; positive: boolean | null } {
		const delta = comparison - baseline;
		if (delta > 0) return { value: delta, positive: true };
		if (delta < 0) return { value: delta, positive: false };
		return { value: 0, positive: null };
	}

	function historyLabel(run: EvaluationHistoryRun): string {
		return run.experiment_name || run.variant_name || formatRunTimestamp(run);
	}

	function isSelectedRun(run: EvaluationHistoryRun): boolean {
		return selectionKey(run) === selectedRunKey;
	}

	function selectedRunLabel(): string {
		const run = (historyData?.runs || []).find((item) => selectionKey(item) === selectedRunKey);
		if (run) return historyLabel(run);
		if (latestData && selectedRunKey === `local:${latestData.run_dir}`) {
			return formatRunTimestamp(latestData);
		}
		return 'Latest run';
	}

	function formatDelta(value: number, digits = 1, suffix = ''): string {
		if (!Number.isFinite(value)) return 'N/A';
		const sign = value > 0 ? '+' : '';
		return `${sign}${value.toFixed(digits)}${suffix}`;
	}

	function retrievalMetric(run: EvaluationHistoryRun, key: keyof RetrievalMetrics): number {
		const value = run.retrieval_metrics?.[key];
		return typeof value === 'number' ? value : 0;
	}

	function filteredHistoryRuns(): EvaluationHistoryRun[] {
		const runs = historyData?.runs || [];
		return runs.filter((run) => {
			if (!experimentFilter.trim()) return true;
			const haystack = [
				run.experiment_name,
				run.variant_name,
				run.run_dir,
				run.index_config_hash
			]
				.filter(Boolean)
				.join(' ')
				.toLowerCase();
			return haystack.includes(experimentFilter.trim().toLowerCase());
		});
	}

	$effect(() => {
		if (!urlStateReady) return;
		syncUrlState();
	});

	async function showMetricDrillDown(stage: string, metricName: string, currentValue: number) {
		try {
			const url = stage === 'l6'
				? `${API_URL}/evaluation/l6/records?limit=100`
				: `${API_URL}/evaluation/steps/${stage}/records?limit=100`;
			const res = await fetch(url);
			if (res.ok) {
				const data = await res.json();
				drillDownModal = {
					open: true,
					metric: metricName,
					stage: stage,
					currentValue: currentValue,
					records: data.records || [],
					historicalData: stage === 'l6'
						? []
						: filteredHistoryRuns()
							.map((run) => {
								const value = run.retrieval_metrics?.[metricName as keyof typeof run.retrieval_metrics];
								if (value !== undefined) {
									return {
										timestamp: formatRunTimestamp(run, {
											month: 'short',
											day: 'numeric',
											hour: 'numeric',
											minute: '2-digit'
										}),
										value: typeof value === 'number' ? value : 0
									};
								}
								return null;
							})
							.filter(Boolean) as Array<{ timestamp: string; value: number }>
				};
			}
		} catch (e) {
			console.error('Failed to load drill-down data:', e);
		}
	}

	onMount(async () => {
		applyUrlStateFromLocation();
		await Promise.all([loadData(), loadHistory(), loadAblationResults()]);
		if (selectedRunKey && latestData && selectedRunKey !== `local:${latestData.run_dir}`) {
			const selected = await loadRun(selectedRunKey);
			if (selected) data = selected;
		}
		if (compareMode && (baselineRun || compareRun)) {
			await loadComparisonData();
		}
		urlStateReady = true;
	});
</script>

<div class="eval-container">
	<nav class="nav-bar">
		<a href="/" class="nav-link">Chat</a>
		<a href="/eval" class="nav-link active">Pipeline Eval</a>
		<a href="/docs/pipeline" class="nav-link">Pipeline Docs</a>
	</nav>
	<header>
		<div class="header-left">
			<a href="https://github.com/anomalyco/qna_medical_referenced" target="_blank" rel="noopener noreferrer" class="github-link" aria-label="View on GitHub">
				<svg viewBox="0 0 24 24" fill="currentColor" xmlns="http://www.w3.org/2000/svg">
					<path d="M12 0C5.37 0 0 5.37 0 12c0 5.31 3.435 9.795 8.205 11.385.6.105.825-.255.825-.57 0-.285-.015-1.23-.015-2.235-3.015.555-3.795-.735-4.035-1.41-.135-.345-.72-1.41-1.23-1.695-.42-.225-1.02-.78-.015-.795.945-.015 1.62.87 1.845 1.23 1.08 1.815 2.805 1.305 3.495.99.105-.78.42-1.305.765-1.605-2.67-.3-5.46-1.335-5.46-5.925 0-1.305.465-2.385 1.23-3.225-.12-.3-.54-1.53.12-3.18 0 0 1.005-.315 3.3 1.23.96-.27 1.98-.405 3-.405s2.04.135 3 .405c2.295-1.56 3.3-1.23 3.3-1.23.66 1.65.24 2.88.12 3.18.765.84 1.23 1.905 1.23 3.225 0 4.605-2.805 5.625-5.475 5.925.435.375.81 1.095.81 2.22 0 1.605-.015 2.895-.015 3.3 0 .315.225.69.825.57A12.02 12.02 0 0 0 24 12c0-6.63-5.37-12-12-12z"/>
				</svg>
			</a>
			<h1>Pipeline Quality Assessment</h1>
			{#if data?.summary}
				<span class="status-badge" style="background: {getStatusColor(data.summary.status)}">
					{data.summary.status.toUpperCase()}
				</span>
			{/if}
		</div>
		{#if data}
			{@const healthScore = calculateHealthScore(data)}
			{@const healthGrade = getHealthGrade(healthScore)}
			<HealthScoreBadge score={healthScore} grade={healthGrade} />
		{/if}
		<div class="header-actions">
			<button class="action-btn compare-btn" onclick={() => compareMode = !compareMode} class:active={compareMode}>
				{compareMode ? 'Exit Compare' : 'Compare Runs'}
			</button>
			<button class="action-btn" onclick={handleExportCSV} disabled={!data}>Export CSV</button>
			<button class="action-btn" onclick={handleExportJSON} disabled={!data}>Export JSON</button>
			<button class="action-btn" onclick={handleExportCharts} disabled={!data}>Export Charts</button>
			<button class="refresh-btn" onclick={refresh} disabled={refreshing}>
				{refreshing ? 'Refreshing...' : 'Refresh'}
			</button>
		</div>
	</header>

	<!-- History Loading Skeleton -->
	{#if historyLoading}
		<section class="history-section">
			<h2>Historical Trending</h2>
			<div class="history-summary">
				<LoadingSkeleton count={4} type="card" height="80px" />
			</div>
			<div class="charts-grid">
				<LoadingSkeleton count={2} type="card" height="200px" />
			</div>
		</section>
	{/if}

	<!-- Comparison Controls -->
	{#if compareMode && historyData?.runs}
		<section class="comparison-controls-section">
			<h3>Compare Runs</h3>
			<div class="comparison-controls">
				<div class="control-group">
					<label for="baseline-run">Baseline Run:</label>
					<select id="baseline-run" bind:value={baselineRun} onchange={loadComparisonData}>
						<option value="">Select baseline...</option>
						{#each filteredHistoryRuns() as run}
							<option value={selectionKey(run)}>{historyLabel(run)} [{run.source}]</option>
						{/each}
					</select>
				</div>
				<div class="control-group">
					<label for="comparison-run">Comparison Run:</label>
					<select id="comparison-run" bind:value={compareRun} onchange={loadComparisonData}>
						<option value="">Select comparison...</option>
						{#each filteredHistoryRuns() as run}
							<option value={selectionKey(run)}>{historyLabel(run)} [{run.source}]</option>
						{/each}
					</select>
				</div>
			</div>
		</section>
	{/if}

	<!-- Filters -->
	<section class="filters-section">
		<div class="filter-group">
			<input
				type="text"
				placeholder="Search metrics..."
				bind:value={searchQuery}
				class="search-input"
			/>
		</div>
		<div class="filter-group">
			<MultiSelect options={allStages} bind:value={selectedStages} label="Pipeline Stages" />
		</div>
	</section>

	{#if historyData && historyData.runs && historyData.runs.length > 0 && !historyLoading}
		<section class="history-section">
			<div class="section-header">
				<h2>Historical Trending</h2>
				<div class="history-controls">
					<div class="metric-selector">
						<label for="trend-metric">Metric:</label>
						<select bind:value={selectedTrendMetric} id="trend-metric">
							<option value="hit_rate">Hit Rate & MRR</option>
							<option value="mrr">MRR Focus</option>
							<option value="latency">Latency</option>
						</select>
					</div>
					<button class="action-btn" onclick={loadHistory}>Reload History</button>
				</div>
				<div class="history-controls">
					<input
						type="text"
						placeholder="Filter by experiment, variant, or index hash"
						bind:value={experimentFilter}
						class="search-input history-search"
					/>
				</div>
			</div>
			<div class="history-summary">
				<div class="summary-stat">
					<span class="stat-label">Total Runs</span>
					<span class="stat-value">{historyData.summary.total_runs}</span>
				</div>
				<div class="summary-stat">
					<span class="stat-label">Avg Hit Rate</span>
					<span class="stat-value">{(historyData.summary.avg_hit_rate * 100).toFixed(1)}%</span>
				</div>
				<div class="summary-stat">
					<span class="stat-label">Avg MRR</span>
					<span class="stat-value">{historyData.summary.avg_mrr.toFixed(3)}</span>
				</div>
				<div class="summary-stat">
					<span class="stat-label">Avg Latency</span>
					<span class="stat-value">{historyData.summary.avg_latency_p50.toFixed(0)}ms</span>
				</div>
				<div class="summary-stat">
					<span class="stat-label">Sources</span>
					<span class="stat-value small">
						{Object.entries(historyData.summary.sources || {}).map(([key, count]) => `${key}:${count}`).join(' · ')}
					</span>
				</div>
			</div>
			{#if filteredHistoryRuns().length >= 2}
				{@const latestRun = filteredHistoryRuns()[0]}
				{@const previousRun = filteredHistoryRuns()[1]}
				<section class="delta-strip">
					<div class="delta-strip-header">
						<div>
							<h3>Latest vs Previous</h3>
							<p>
								{historyLabel(latestRun)} compared with {historyLabel(previousRun)}
							</p>
						</div>
						<button class="action-btn secondary-btn" onclick={() => selectRun(selectionKey(latestRun))}>
							Open latest run
						</button>
					</div>
					<div class="delta-grid">
						<div class="delta-card">
							<span class="delta-label">Hit Rate @k</span>
							<strong>{(retrievalMetric(latestRun, 'hit_rate_at_k') * 100).toFixed(1)}%</strong>
							<span
								class:positive={(retrievalMetric(latestRun, 'hit_rate_at_k') - retrievalMetric(previousRun, 'hit_rate_at_k')) * 100 > 0}
								class:negative={(retrievalMetric(latestRun, 'hit_rate_at_k') - retrievalMetric(previousRun, 'hit_rate_at_k')) * 100 < 0}
							>
								{formatDelta((retrievalMetric(latestRun, 'hit_rate_at_k') - retrievalMetric(previousRun, 'hit_rate_at_k')) * 100, 1, ' pts')}
							</span>
						</div>
						<div class="delta-card">
							<span class="delta-label">MRR</span>
							<strong>{retrievalMetric(latestRun, 'mrr').toFixed(3)}</strong>
							<span
								class:positive={retrievalMetric(latestRun, 'mrr') - retrievalMetric(previousRun, 'mrr') > 0}
								class:negative={retrievalMetric(latestRun, 'mrr') - retrievalMetric(previousRun, 'mrr') < 0}
							>
								{formatDelta(retrievalMetric(latestRun, 'mrr') - retrievalMetric(previousRun, 'mrr'), 3)}
							</span>
						</div>
						<div class="delta-card">
							<span class="delta-label">Latency p50</span>
							<strong>{retrievalMetric(latestRun, 'latency_p50_ms').toFixed(0)}ms</strong>
							<span
								class:positive={retrievalMetric(latestRun, 'latency_p50_ms') - retrievalMetric(previousRun, 'latency_p50_ms') < 0}
								class:negative={retrievalMetric(latestRun, 'latency_p50_ms') - retrievalMetric(previousRun, 'latency_p50_ms') > 0}
							>
								{formatDelta(retrievalMetric(latestRun, 'latency_p50_ms') - retrievalMetric(previousRun, 'latency_p50_ms'), 0, 'ms')}
							</span>
						</div>
						<div class="delta-card">
							<span class="delta-label">Failed Thresholds</span>
							<strong>{latestRun.failed_thresholds_count || 0}</strong>
							<span
								class:positive={(latestRun.failed_thresholds_count || 0) - (previousRun.failed_thresholds_count || 0) < 0}
								class:negative={(latestRun.failed_thresholds_count || 0) - (previousRun.failed_thresholds_count || 0) > 0}
							>
								{formatDelta((latestRun.failed_thresholds_count || 0) - (previousRun.failed_thresholds_count || 0), 0)}
							</span>
						</div>
					</div>
				</section>
			{/if}
			<div class="charts-grid">
				{#if selectedTrendMetric === 'hit_rate'}
					<div class="chart-card">
						<MetricChart
							type="line"
							title="Hit Rate & MRR Over Time"
							data={{
								labels: filteredHistoryRuns().map(r => historyLabel(r)),
								datasets: [
									{
										label: 'Hit Rate @k',
										data: filteredHistoryRuns().map(r => (r.retrieval_metrics?.hit_rate_at_k || 0) * 100)
									},
									{
										label: 'MRR',
										data: filteredHistoryRuns().map(r => (r.retrieval_metrics?.mrr || 0) * 100)
									}
								]
							}}
							height={200}
						/>
					</div>
				{:else if selectedTrendMetric === 'mrr'}
					<div class="chart-card">
						<MetricChart
							type="line"
							title="MRR & Precision Over Time"
							data={{
								labels: filteredHistoryRuns().map(r => historyLabel(r)),
								datasets: [
									{
										label: 'MRR',
										data: filteredHistoryRuns().map(r => (r.retrieval_metrics?.mrr || 0) * 100)
									},
									{
										label: 'Precision @k',
										data: filteredHistoryRuns().map(r => (r.retrieval_metrics?.precision_at_k || 0) * 100)
									},
									{
										label: 'Recall @k',
										data: filteredHistoryRuns().map(r => (r.retrieval_metrics?.recall_at_k || 0) * 100)
									}
								]
							}}
							height={200}
						/>
					</div>
				{:else if selectedTrendMetric === 'latency'}
					<div class="chart-card">
						<MetricChart
							type="bar"
							title="Latency Over Time (ms)"
							data={{
								labels: filteredHistoryRuns().map(r => historyLabel(r)),
								datasets: [
									{
										label: 'p50',
										data: filteredHistoryRuns().map(r => r.retrieval_metrics?.latency_p50_ms || 0)
									},
									{
										label: 'p95',
										data: filteredHistoryRuns().map(r => r.retrieval_metrics?.latency_p95_ms || 0)
									}
								]
							}}
							height={200}
						/>
					</div>
				{/if}
			</div>
			<div class="history-run-list">
				{#each filteredHistoryRuns() as run}
					<div
						class="history-run-card"
						class:selected={isSelectedRun(run)}
						role="button"
						tabindex="0"
						onclick={() => selectRun(selectionKey(run))}
						onkeydown={(event) => {
							if (event.key === 'Enter' || event.key === ' ') {
								event.preventDefault();
								selectRun(selectionKey(run));
							}
						}}
					>
							<div class="history-run-meta">
								<div class="history-run-title">
									<strong>{historyLabel(run)}</strong>
								</div>
							<span class="history-run-subtitle">
								{formatRunTimestampWithZone(run)} · {run.run_dir}
							</span>
							</div>
						<div class="history-run-metrics">
							<span>Hit {((run.retrieval_metrics?.hit_rate_at_k || 0) * 100).toFixed(1)}%</span>
							<span>MRR {(run.retrieval_metrics?.mrr || 0).toFixed(3)}</span>
							<span>p50 {(run.retrieval_metrics?.latency_p50_ms || 0).toFixed(0)}ms</span>
						</div>
						<div class="history-run-tags">
							{#if run.variant_name}<span class="history-tag">variant: {run.variant_name}</span>{/if}
							{#if run.index_config_hash}<span class="history-tag">index: {run.index_config_hash.slice(0, 8)}</span>{/if}
							{#if run.wandb_url}
								<a class="history-link" href={run.wandb_url} target="_blank" rel="noreferrer" onclick={(event) => event.stopPropagation()}>Open W&amp;B</a>
							{/if}
						</div>
					</div>
				{/each}
			</div>
		</section>
	{/if}

	<!-- Comparison View -->
	{#if compareMode && comparisonData.baseline && comparisonData.comparison}
		<section class="comparison-view">
			<h2>Run Comparison</h2>
			<div class="comparison-grid">
				<div class="comparison-col">
					<h3>Baseline</h3>
					<p class="run-id">{comparisonData.baseline.run_dir}</p>
					{#if comparisonData.baseline.wandb_url}
						<p class="run-link-row">
							<a href={comparisonData.baseline.wandb_url} target="_blank" rel="noreferrer">Open W&amp;B run</a>
						</p>
					{/if}
					{#if comparisonData.baseline.retrieval_metrics}
						<div class="metrics-grid compact">
							<div class="metric-card">
								<span class="metric-label">Hit Rate</span>
								<span class="metric-value">{formatPercent(comparisonData.baseline.retrieval_metrics.hit_rate_at_k)}</span>
							</div>
							<div class="metric-card">
								<Tooltip text={metricDefinitions['mrr']}><span class="metric-label">MRR</span></Tooltip>
								<span class="metric-value">{comparisonData.baseline.retrieval_metrics.mrr.toFixed(3)}</span>
							</div>
							<div class="metric-card">
								<Tooltip text={metricDefinitions['latency_p50_ms']}><span class="metric-label">Latency p50</span></Tooltip>
								<span class="metric-value">{comparisonData.baseline.retrieval_metrics.latency_p50_ms.toFixed(0)}ms</span>
							</div>
						</div>
					{/if}
				</div>
				<div class="comparison-col">
					<h3>Comparison</h3>
					<p class="run-id">{comparisonData.comparison.run_dir}</p>
					{#if comparisonData.comparison.wandb_url}
						<p class="run-link-row">
							<a href={comparisonData.comparison.wandb_url} target="_blank" rel="noreferrer">Open W&amp;B run</a>
						</p>
					{/if}
					{#if comparisonData.comparison.retrieval_metrics}
						<div class="metrics-grid compact">
							<div class="metric-card">
								<span class="metric-label">Hit Rate</span>
								<span class="metric-value">{formatPercent(comparisonData.comparison.retrieval_metrics.hit_rate_at_k)}</span>
							</div>
							<div class="metric-card">
								<Tooltip text={metricDefinitions['mrr']}><span class="metric-label">MRR</span></Tooltip>
								<span class="metric-value">{comparisonData.comparison.retrieval_metrics.mrr.toFixed(3)}</span>
							</div>
							<div class="metric-card">
								<Tooltip text={metricDefinitions['latency_p50_ms']}><span class="metric-label">Latency p50</span></Tooltip>
								<span class="metric-value">{comparisonData.comparison.retrieval_metrics.latency_p50_ms.toFixed(0)}ms</span>
							</div>
						</div>
					{/if}
				</div>
					<div class="comparison-col">
						<h3>Delta</h3>
						<p class="run-id">Change</p>
						{#if comparisonData.baseline.retrieval_metrics && comparisonData.comparison.retrieval_metrics}
							{@const hitRateDelta = getMetricDelta(
								comparisonData.baseline.retrieval_metrics.hit_rate_at_k,
								comparisonData.comparison.retrieval_metrics.hit_rate_at_k
							)}
							{@const mrrDelta = getMetricDelta(
								comparisonData.baseline.retrieval_metrics.mrr,
								comparisonData.comparison.retrieval_metrics.mrr
							)}
							{@const latencyDelta = getMetricDelta(
								comparisonData.baseline.retrieval_metrics.latency_p50_ms,
								comparisonData.comparison.retrieval_metrics.latency_p50_ms
							)}
							<div class="metrics-grid compact">
								<div class="metric-card">
									<span class="metric-label">Hit Rate</span>
									<span class="metric-value delta" class:positive={hitRateDelta.positive === true} class:negative={hitRateDelta.positive === false}>
										{hitRateDelta.positive === true ? '+' : ''}{(hitRateDelta.value * 100).toFixed(1)}%
									</span>
								</div>
								<div class="metric-card">
									<Tooltip text={metricDefinitions['mrr']}><span class="metric-label">MRR</span></Tooltip>
									<span class="metric-value delta" class:positive={mrrDelta.positive === true} class:negative={mrrDelta.positive === false}>
										{mrrDelta.positive === true ? '+' : ''}{mrrDelta.value.toFixed(3)}
									</span>
								</div>
								<div class="metric-card">
									<Tooltip text={metricDefinitions['latency_p50_ms']}><span class="metric-label">Latency p50</span></Tooltip>
									<span class="metric-value delta" class:positive={latencyDelta.positive === false} class:negative={latencyDelta.positive === true}>
										{latencyDelta.positive === true ? '+' : ''}{latencyDelta.value.toFixed(0)}ms
									</span>
								</div>
						</div>
					{/if}
				</div>
			</div>
		</section>
	{/if}

	{#if loading}
		<div class="skeleton-wrapper">
			<h2>Loading evaluation data...</h2>
			<div class="skeleton-grid">
				<LoadingSkeleton count={3} type="card" />
				<LoadingSkeleton count={3} type="card" />
				<LoadingSkeleton count={3} type="card" />
			</div>
		</div>
	{:else if error}
		<div class="error">{error}</div>
	{:else if !data || (!data.summary && !data.step_metrics && !data.retrieval_metrics)}
		<div class="empty-state">
			<p>No evaluation data available.</p>
			<p class="empty-hint">Run an evaluation to see pipeline metrics.</p>
		</div>
	{:else if data}
		<div class="content">
			{#if data.summary}
				<section class="summary-card">
					<div class="summary-header">
						<div>
							<h2>Run Summary</h2>
							<p class="summary-subtitle">Viewing {selectedRunLabel()}</p>
						</div>
						{#if latestData && data.run_dir !== latestData.run_dir}
							<button class="action-btn secondary-btn" onclick={() => latestData && selectRun(`local:${latestData.run_dir}`)}>
								Back to latest
							</button>
						{/if}
					</div>
					<div class="summary-grid">
						<div class="summary-item">
							<span class="label">Run Time</span>
							<span class="value">{formatRunTimestampWithZone(data)}</span>
						</div>
						<div class="summary-item">
							<span class="label">Run Directory</span>
							<span class="value">{data.run_dir}</span>
						</div>
						<div class="summary-item">
							<span class="label">Duration</span>
							<span class="value">{data.summary.duration_s.toFixed(2)}s</span>
						</div>
						<div class="summary-item">
							<span class="label">Status</span>
							<span class="value" style="color: {getStatusColor(data.summary.status)}">{data.summary.status}</span>
						</div>
						<div class="summary-item">
							<span class="label">Failed Thresholds</span>
							<span class="value">{data.summary.failed_thresholds_count}</span>
						</div>
					</div>
				</section>
				{/if}

				{#if data.failed_thresholds && data.failed_thresholds.length > 0}
					<section class="threshold-summary">
						<div class="summary-header">
							<div>
								<h2>Threshold Failures</h2>
								<p class="summary-subtitle">Current value versus configured threshold</p>
							</div>
						</div>
						<div class="threshold-list">
							{#each data.failed_thresholds as failure}
								<div class="threshold-card">
									<div class="threshold-card-header">
										<strong>{failure.metric || failure.message || 'Threshold check'}</strong>
										<span class="threshold-badge">{failure.threshold_op} {failure.threshold_value}</span>
									</div>
									<div class="threshold-card-body">
										<span>Observed: {String(failure.value)}</span>
										{#if failure.message}
											<span>{failure.message}</span>
										{/if}
									</div>
								</div>
							{/each}
						</div>
					</section>
				{/if}

				{#if data.step_metrics}
					{@const filteredSteps = Object.entries(data.step_metrics).filter(([stage]) =>
						selectedStages.includes(stage.toUpperCase())
					)}
					{@const searchedSteps = searchQuery
						? filteredSteps.filter(([_, metrics]) =>
								Object.keys(metrics.aggregate || {}).some((key) =>
									key.toLowerCase().includes(searchQuery.toLowerCase())
								)
							)
						: filteredSteps}
					<section class="steps-section">
						<h2>Pipeline Steps (L0-L5)</h2>
						<div class="steps-grid">
						{#each searchedSteps as [stage, metrics]: [string, any] (stage)}
							{@const agg = metrics.aggregate}
							{@const findings = metrics.findings || []}
							<div class="step-card">
								<div class="step-header">
									<span class="stage-name">{stageNames[stage.toUpperCase()] || stage.toUpperCase()}</span>
									{#if findings.length > 0}
										<span class="finding-badge" class:error={findings.some(f => f.severity === 'error')}>
											{findings.length} issue(s)
										</span>
									{/if}
								</div>
								<div class="step-content">
									{#if stage === 'l0'}
										<div class="metric-row">
											<Tooltip text={metricDefinitions['html_file_count']}><span>HTML Files</span></Tooltip>
											<span>{agg.html_file_count || 0}</span>
										</div>
										<div class="metric-row">
											<Tooltip text={metricDefinitions['html_parse_success_rate']}><span>Parse Success Rate</span></Tooltip>
											<span>{formatPercent(agg.html_parse_success_rate || 0)}</span>
										</div>
										<div class="metric-row">
											<Tooltip text={metricDefinitions['duplicate_file_rate']}><span>Duplicate Rate</span></Tooltip>
											<span>{formatPercent(agg.duplicate_file_rate || 0)}</span>
										</div>
										<div class="metric-row">
											<Tooltip text={metricDefinitions['small_file_rate']}><span>Small File Rate</span></Tooltip>
											<span class:warning={agg.small_file_rate > 0.1}>
												{formatPercent(agg.small_file_rate || 0)}
											</span>
										</div>
										<div class="metric-row">
											<Tooltip text={metricDefinitions['manifest_inventory_record_count']}><span>Manifest Records</span></Tooltip>
											<span>{agg.manifest_inventory_record_count || 0}</span>
										</div>
									{:else if stage === 'l1'}
										<div class="metric-row">
											<Tooltip text={metricDefinitions['pairs_evaluated']}><span>Pairs Evaluated</span></Tooltip>
											<span>{agg.pairs_evaluated || 0}</span>
										</div>
										<div class="metric-row">
											<Tooltip text={metricDefinitions['markdown_empty_rate']}><span>Empty Markdown Rate</span></Tooltip>
											<span class:warning={agg.markdown_empty_rate > 0.1}>
												{formatPercent(agg.markdown_empty_rate || 0)}
											</span>
										</div>
										<div class="metric-row">
											<Tooltip text={metricDefinitions['retention_ratio_mean']}><span>Retention Ratio</span></Tooltip>
											<span>{formatPercent(agg.retention_ratio_mean || 0)}</span>
										</div>
										<div class="metric-row">
											<Tooltip text={metricDefinitions['content_density_mean']}><span>Content Density</span></Tooltip>
											<span>{(agg.content_density_mean * 100).toFixed(1)}%</span>
										</div>
										<div class="metric-row">
											<Tooltip text={metricDefinitions['boilerplate_ratio_mean']}><span>Boilerplate Ratio</span></Tooltip>
											<span class:warning={agg.boilerplate_ratio_mean > 0.1}>
												{(agg.boilerplate_ratio_mean * 100).toFixed(1)}%
											</span>
										</div>
										<div class="metric-row">
											<Tooltip text={metricDefinitions['heading_preservation_rate_mean']}><span>Heading Preservation</span></Tooltip>
											<span>{formatPercent(agg.heading_preservation_rate_mean || 0)}</span>
										</div>
										<div class="metric-row">
											<Tooltip text={metricDefinitions['table_preservation_rate_mean']}><span>Table Preservation</span></Tooltip>
											<span>{formatPercent(agg.table_preservation_rate_mean || 0)}</span>
										</div>
										<div class="metric-row">
											<span>Page Types</span>
											<span class="page-types">
												{#each Object.entries(agg.page_classification_distribution || {}) as [type, count]}
													<span class="page-type-badge">{type}: {count}</span>
												{/each}
											</span>
										</div>
									{:else if stage === 'l2'}
										<div class="metric-row">
											<Tooltip text={metricDefinitions['pdf_file_count']}><span>PDF Files</span></Tooltip>
											<span>{agg.pdf_file_count || 0}</span>
										</div>
										<div class="metric-row">
											<Tooltip text={metricDefinitions['page_extraction_coverage']}><span>Page Extraction Coverage</span></Tooltip>
											<span>{formatPercent(agg.page_extraction_coverage || 0)}</span>
										</div>
										<div class="metric-row">
											<Tooltip text={metricDefinitions['empty_page_rate']}><span>Empty Page Rate</span></Tooltip>
											<span class:warning={agg.empty_page_rate > 0.2}>
												{formatPercent(agg.empty_page_rate || 0)}
											</span>
										</div>
										<div class="metric-row">
											<Tooltip text={metricDefinitions['extractor_fallback_rate']}><span>Extractor Fallback Rate</span></Tooltip>
											<span>{formatPercent(agg.extractor_fallback_rate || 0)}</span>
										</div>
										<div class="metric-row">
											<Tooltip text={metricDefinitions['low_confidence_page_rate']}><span>Low Confidence Rate</span></Tooltip>
											<span class:warning={agg.low_confidence_page_rate > 0.1}>
												{formatPercent(agg.low_confidence_page_rate || 0)}
											</span>
										</div>
										<div class="metric-row">
											<Tooltip text={metricDefinitions['ocr_required_rate']}><span>OCR Required Rate</span></Tooltip>
											<span>{formatPercent(agg.ocr_required_rate || 0)}</span>
										</div>
									{:else if stage === 'l3'}
										<div class="metric-row">
											<Tooltip text={metricDefinitions['document_count']}><span>Documents</span></Tooltip>
											<span>{agg.document_count || 0}</span>
										</div>
										<div class="metric-row">
											<Tooltip text={metricDefinitions['chunk_count']}><span>Chunks</span></Tooltip>
											<span>{agg.chunk_count || 0}</span>
										</div>
										<div class="metric-row">
											<Tooltip text={metricDefinitions['duplicate_chunk_rate']}><span>Duplicate Chunk Rate</span></Tooltip>
											<span class:warning={agg.duplicate_chunk_rate > 0.05}>
												{formatPercent(agg.duplicate_chunk_rate || 0)}
											</span>
										</div>
										<div class="metric-row">
											<Tooltip text={metricDefinitions['boundary_cut_rate']}><span>Boundary Cut Rate</span></Tooltip>
											<span>{formatPercent(agg.boundary_cut_rate || 0)}</span>
										</div>
										<div class="metric-row">
											<Tooltip text={metricDefinitions['observed_overlap_mean']}><span>Observed Overlap</span></Tooltip>
											<span>{(agg.observed_overlap_mean * 100).toFixed(1)}%</span>
										</div>
										<div class="metric-row">
											<Tooltip text={metricDefinitions['table_row_split_violations']}><span>Table Row Split Violations</span></Tooltip>
											<span class:warning={(agg.table_row_split_violations || 0) > 0}>
												{agg.table_row_split_violations || 0}
											</span>
										</div>
										<div class="metric-row">
											<span>Quality Distribution</span>
											<QualityDistributionChart
												high={agg.chunk_quality_histogram?.high || 0}
												medium={agg.chunk_quality_histogram?.medium || 0}
												low={agg.chunk_quality_histogram?.low || 0}
											/>
										</div>
										<div class="metric-row">
											<Tooltip text={metricDefinitions['section_integrity_rate']}><span>Section Integrity</span></Tooltip>
											<span>{formatPercent(agg.section_integrity_rate || 0)}</span>
										</div>
										<div class="metric-row">
											<Tooltip text={metricDefinitions['low_quality_chunk_exclusion_rate']}><span>Low Quality Filtered</span></Tooltip>
											<span>{formatPercent(agg.low_quality_chunk_exclusion_rate || 0)}</span>
										</div>
									{:else if stage === 'l4'}
										<div class="metric-row">
											<Tooltip text={metricDefinitions['csv_exists']}><span>CSV Exists</span></Tooltip>
											<span>{agg.csv_exists ? 'Yes' : 'No'}</span>
										</div>
										<div class="metric-row">
											<Tooltip text={metricDefinitions['row_count']}><span>Row Count</span></Tooltip>
											<span>{agg.row_count || 0}</span>
										</div>
										<div class="metric-row">
											<Tooltip text={metricDefinitions['row_completeness_rate']}><span>Completeness Rate</span></Tooltip>
											<span>{formatPercent(agg.row_completeness_rate || 0)}</span>
										</div>
									{:else if stage === 'l5'}
										<div class="metric-row">
											<Tooltip text={metricDefinitions['ids_count']}><span>Vector Count</span></Tooltip>
											<span>{agg.ids_count || 0}</span>
										</div>
										<div class="metric-row">
											<Tooltip text={metricDefinitions['embedding_dim']}><span>Embedding Dim</span></Tooltip>
											<span>{agg.embedding_dim || 'N/A'}</span>
										</div>
										<div class="metric-row">
											<Tooltip text={metricDefinitions['embedding_dim_consistent']}><span>Dims Consistent</span></Tooltip>
											<span>{agg.embedding_dim_consistent ? 'Yes' : 'No'}</span>
										</div>
										<div class="metric-row">
											<Tooltip text={metricDefinitions['short_content_rate']}><span>Short Content Rate</span></Tooltip>
											<span class:warning={agg.short_content_rate > 0.1}>
												{formatPercent(agg.short_content_rate || 0)}
											</span>
										</div>
										<div class="metric-row">
											<Tooltip text={metricDefinitions['index_file_size_bytes']}><span>Index File Size</span></Tooltip>
											<span>{(agg.index_file_size_bytes / 1024 / 1024).toFixed(2)} MB</span>
										</div>
										{#if agg.source_distribution}
											<div class="metric-row">
												<span>Source Distribution</span>
												<span class="source-dist-mini">
													{#each Object.entries(agg.source_distribution).slice(0, 3) as [source, count]}
														<span class="source-badge">{source}: {count}</span>
													{/each}
													{#if Object.keys(agg.source_distribution).length > 3}
														<span class="source-badge">+{Object.keys(agg.source_distribution).length - 3} more</span>
													{/if}
												</span>
											</div>
										{/if}
									{/if}
								</div>
								{#if findings.length > 0}
									<div class="findings">
										{#each findings as finding}
											<div class="finding-item {finding.severity}">
												{finding.message}
											</div>
										{/each}
									</div>
								{/if}
							</div>
						{/each}
					</div>
				</section>
			{/if}

			{#if data.retrieval_metrics}
				{@const rm = data.retrieval_metrics}
				<section class="retrieval-section">
					<h2>{stageNames["L6"] || "Retrieval Metrics"}</h2>
					<div class="metrics-grid">
						<div class="metric-card">
							<Tooltip text={metricDefinitions['query_count']}><span class="metric-label">Query Count</span></Tooltip>
							<span class="metric-value">{rm.query_count}</span>
						</div>
						<button
							type="button"
							class="metric-card clickable metric-card-button"
							onclick={() => showMetricDrillDown('l6', 'hit_rate_at_k', rm.hit_rate_at_k)}
						>
							<Tooltip text={metricDefinitions['hit_rate_at_k']}><span class="metric-label">Hit Rate @k</span></Tooltip>
							<span class="metric-value highlight">{formatPercent(rm.hit_rate_at_k)}</span>
						</button>
						<button
							type="button"
							class="metric-card clickable metric-card-button"
							onclick={() => showMetricDrillDown('l6', 'mrr', rm.mrr)}
						>
							<Tooltip text={metricDefinitions['mrr']}><span class="metric-label">MRR</span></Tooltip>
							<span class="metric-value highlight">{rm.mrr.toFixed(3)}</span>
						</button>
						<div class="metric-card">
							<Tooltip text={metricDefinitions['precision_at_k']}><span class="metric-label">Precision @k</span></Tooltip>
							<span class="metric-value">{formatPercent(rm.precision_at_k)}</span>
						</div>
						<div class="metric-card">
							<Tooltip text={metricDefinitions['recall_at_k']}><span class="metric-label">Recall @k</span></Tooltip>
							<span class="metric-value">{formatPercent(rm.recall_at_k)}</span>
						</div>
						<div class="metric-card">
							<Tooltip text={metricDefinitions['ndcg_at_k']}><span class="metric-label">nDCG @k</span></Tooltip>
							<span class="metric-value">{formatPercent(rm.ndcg_at_k)}</span>
						</div>
						<div class="metric-card">
							<Tooltip text={metricDefinitions['source_hit_rate']}><span class="metric-label">Source Hit Rate</span></Tooltip>
							<span class="metric-value">{formatPercent(rm.source_hit_rate)}</span>
						</div>
						<div class="metric-card">
							<Tooltip text={metricDefinitions['exact_chunk_hit_rate']}><span class="metric-label">Exact Chunk Hit</span></Tooltip>
							<span class="metric-value">{formatPercent(rm.exact_chunk_hit_rate)}</span>
						</div>
						<div class="metric-card">
							<Tooltip text={metricDefinitions['evidence_hit_rate']}><span class="metric-label">Evidence Hit</span></Tooltip>
							<span class="metric-value">{formatPercent(rm.evidence_hit_rate)}</span>
						</div>
						<div class="metric-card">
							<Tooltip text={metricDefinitions['latency_p50_ms']}><span class="metric-label">Latency p50</span></Tooltip>
							<span class="metric-value">{rm.latency_p50_ms.toFixed(0)}ms</span>
						</div>
						<div class="metric-card">
							<Tooltip text={metricDefinitions['latency_p95_ms']}><span class="metric-label">Latency p95</span></Tooltip>
							<span class="metric-value">{rm.latency_p95_ms.toFixed(0)}ms</span>
						</div>
					</div>
					{#if rm.dedup_hit_rate_at_k !== undefined || rm.unique_source_hit_rate_at_k !== undefined}
						<section class="retrieval-subsection">
							<h3>Deduplication & Diversity</h3>
							<div class="metrics-grid">
								{#if rm.dedup_hit_rate_at_k !== undefined}
									<div class="metric-card">
										<span class="metric-label">Dedup Hit Rate</span>
										<span class="metric-value">{formatPercent(rm.dedup_hit_rate_at_k)}</span>
									</div>
								{/if}
								{#if rm.dedup_mrr !== undefined}
									<div class="metric-card">
										<span class="metric-label">Dedup MRR</span>
										<span class="metric-value">{(rm.dedup_mrr || 0).toFixed(3)}</span>
									</div>
								{/if}
								{#if rm.unique_source_hit_rate_at_k !== undefined}
									<div class="metric-card">
										<span class="metric-label">Unique Source Hit</span>
										<span class="metric-value">{formatPercent(rm.unique_source_hit_rate_at_k)}</span>
									</div>
								{/if}
								{#if rm.duplicate_source_ratio_mean !== undefined}
									<div class="metric-card">
										<span class="metric-label">Duplicate Source Ratio</span>
										<span class="metric-value">{(rm.duplicate_source_ratio_mean * 100).toFixed(1)}%</span>
									</div>
								{/if}
							</div>
						</section>
					{/if}
					{#if rm.hit_rate_at_k_high_conf !== undefined || rm.exact_chunk_hit_rate_high_conf !== undefined}
						<section class="retrieval-subsection">
							<h3>High-Confidence Subset</h3>
							<div class="metrics-grid">
								{#if rm.hit_rate_at_k_high_conf !== undefined}
									<div class="metric-card">
										<span class="metric-label">Hit Rate (High Conf)</span>
										<span class="metric-value highlight">{formatPercent(rm.hit_rate_at_k_high_conf)}</span>
									</div>
								{/if}
								{#if rm.mrr_high_conf !== undefined}
									<div class="metric-card">
										<span class="metric-label">MRR (High Conf)</span>
										<span class="metric-value highlight">{(rm.mrr_high_conf || 0).toFixed(3)}</span>
									</div>
								{/if}
								{#if rm.exact_chunk_hit_rate_high_conf !== undefined}
									<div class="metric-card">
										<span class="metric-label">Exact Chunk (High Conf)</span>
										<span class="metric-value">{formatPercent(rm.exact_chunk_hit_rate_high_conf)}</span>
									</div>
								{/if}
								{#if rm.topic_false_positive_rate !== undefined}
									<div class="metric-card">
										<span class="metric-label">Topic False Positive</span>
										<span class="metric-value">{(rm.topic_false_positive_rate * 100).toFixed(1)}%</span>
									</div>
								{/if}
							</div>
						</section>
					{/if}
					{#if rm.hyde_enabled}
						<section class="retrieval-subsection">
							<h3>HyDe Query Expansion</h3>
							<div class="metrics-grid">
								<div class="metric-card">
									<span class="metric-label">HyDe Queries</span>
									<span class="metric-value">{rm.hyde_queries_count ?? 'N/A'}</span>
								</div>
								{#if rm.hyde_hit_rate !== undefined && rm.hyde_hit_rate !== null}
									<div class="metric-card">
										<span class="metric-label">HyDe Hit Rate</span>
										<span class="metric-value highlight">{formatPercent(rm.hyde_hit_rate)}</span>
									</div>
								{/if}
								{#if rm.hyde_mrr !== undefined && rm.hyde_mrr !== null}
									<div class="metric-card">
										<span class="metric-label">HyDe MRR</span>
										<span class="metric-value highlight">{rm.hyde_mrr.toFixed(3)}</span>
									</div>
								{/if}
								{#if rm.hyde_source_hit_rate !== undefined && rm.hyde_source_hit_rate !== null}
									<div class="metric-card">
										<span class="metric-label">HyDe Source Hit</span>
										<span class="metric-value">{formatPercent(rm.hyde_source_hit_rate)}</span>
									</div>
								{/if}
							</div>
						</section>
					{/if}
				</section>
			{/if}

			{#if ablationData?.ablation_runs && ablationData.ablation_runs.length > 0}
				<section class="ablation-section">
					<h2>Retrieval Strategy Comparison (Ablation Study)</h2>
					<div class="ablation-table-wrapper">
						<table class="ablation-table">
							<thead>
								<tr>
									<th>Strategy</th>
									<th>Hit Rate</th>
									<th>MRR</th>
									<th>nDCG</th>
									<th>Latency (p50)</th>
								</tr>
							</thead>
							<tbody>
								{#each ablationData.ablation_runs as run}
									<tr class:highlighted={run.is_baseline}>
										<td>
											<span class="strategy-name">{run.strategy}</span>
											{#if run.is_baseline}
												<span class="baseline-badge">Baseline</span>
											{/if}
										</td>
										<td class:good={run.hit_rate_at_k >= 0.7}>
											{(run.hit_rate_at_k * 100).toFixed(1)}%
										</td>
										<td class:good={run.mrr >= 0.6}>{run.mrr.toFixed(3)}</td>
										<td class:good={run.ndcg_at_k >= 0.7}>
											{(run.ndcg_at_k * 100).toFixed(1)}%
										</td>
										<td>{run.latency_p50_ms?.toFixed(0) || 'N/A'}ms</td>
									</tr>
								{/each}
							</tbody>
						</table>
					</div>
					{#if ablationData.message}
						<p class="ablation-message">{ablationData.message}</p>
					{/if}
				</section>
			{/if}

			{#if data.step_metrics?.l5?.aggregate?.source_distribution}
				<section class="data-quality-section">
					<h2>Data Quality Overview</h2>
					<div class="charts-grid">
						<div class="chart-card">
							<SourceDistributionChart
								distribution={data.step_metrics.l5.aggregate.source_distribution}
								title="Source Distribution"
								height={220}
							/>
						</div>
					</div>
				</section>
			{/if}

			{#if data.summary?.l6_answer_quality_metrics && data.summary.l6_answer_quality_metrics.status !== 'skipped'}
				{@const l6 = data.summary.l6_answer_quality_metrics}
				<section class="rag-section">
					<h2>L6 Answer Quality</h2>
					<div class="rag-stats">
						<div class="metric-card">
							<span class="metric-label">L6 Status</span>
							<span class="metric-value">{l6.status}</span>
						</div>
						<div class="metric-card">
							<span class="metric-label">Query Count Scored</span>
							<span class="metric-value">{l6.query_count_scored ?? l6.query_count ?? 'N/A'}</span>
						</div>
						<div class="metric-card">
							<span class="metric-label">Metric Error Rate</span>
							<span class="metric-value">
								{l6.metric_error_rate !== undefined
									? formatPercent(l6.metric_error_rate)
									: 'N/A'}
							</span>
						</div>
						<button
							type="button"
							class="metric-card clickable metric-card-button"
							onclick={() => showMetricDrillDown('l6', 'answer_relevancy', l6.answer_relevancy?.mean ?? 0)}
						>
							<span class="metric-label">Answer Relevancy</span>
							<span class="metric-value">{l6.answer_relevancy?.mean?.toFixed(2) || 'N/A'}</span>
						</button>
						<button
							type="button"
							class="metric-card clickable metric-card-button"
							onclick={() => showMetricDrillDown('l6', 'faithfulness', l6.faithfulness?.mean ?? 0)}
						>
							<span class="metric-label">Faithfulness</span>
							<span class="metric-value">{l6.faithfulness?.mean?.toFixed(2) || 'N/A'}</span>
						</button>
						<button
							type="button"
							class="metric-card clickable metric-card-button"
							onclick={() => showMetricDrillDown('l6', 'factual_accuracy', l6.factual_accuracy?.mean ?? 0)}
						>
							<span class="metric-label">Factual Accuracy</span>
							<span class="metric-value">{l6.factual_accuracy?.mean?.toFixed(2) || 'N/A'}</span>
						</button>
						<button
							type="button"
							class="metric-card clickable metric-card-button"
							onclick={() => showMetricDrillDown('l6', 'completeness', l6.completeness?.mean ?? 0)}
						>
							<span class="metric-label">Completeness</span>
							<span class="metric-value">{l6.completeness?.mean?.toFixed(2) || 'N/A'}</span>
						</button>
						<button
							type="button"
							class="metric-card clickable metric-card-button"
							onclick={() => showMetricDrillDown('l6', 'clinical_relevance', l6.clinical_relevance?.mean ?? 0)}
						>
							<span class="metric-label">Clinical Relevance</span>
							<span class="metric-value">{l6.clinical_relevance?.mean?.toFixed(2) || 'N/A'}</span>
						</button>
						<button
							type="button"
							class="metric-card clickable metric-card-button"
							onclick={() => showMetricDrillDown('l6', 'clarity', l6.clarity?.mean ?? 0)}
						>
							<span class="metric-label">Clarity</span>
							<span class="metric-value">{l6.clarity?.mean?.toFixed(2) || 'N/A'}</span>
						</button>
					</div>
				</section>
			{/if}
		</div>
	{/if}

	<!-- Drill-Down Modal -->
	<DrillDownModal
		open={drillDownModal.open}
		onclose={() => (drillDownModal.open = false)}
		metric={drillDownModal.metric}
		stage={drillDownModal.stage}
		currentValue={drillDownModal.currentValue}
		records={drillDownModal.records}
		historicalData={drillDownModal.historicalData}
	/>
</div>

<style>
	.eval-container {
		max-width: 1200px;
		margin: 0 auto;
		padding: 1rem;
	}

	.nav-bar {
		display: flex;
		gap: 1rem;
		margin-bottom: 1.5rem;
		padding-bottom: 0.5rem;
		border-bottom: 1px solid #eee;
	}

	.nav-link {
		padding: 0.5rem 1rem;
		text-decoration: none;
		color: #666;
		border-radius: 4px;
		font-weight: 500;
	}

	.nav-link:hover {
		background: #f0f0f0;
	}

	.nav-link.active {
		background: #e3f2fd;
		color: #1976d2;
	}

	header {
		display: flex;
		justify-content: space-between;
		align-items: center;
		gap: 1rem;
		margin-bottom: 2rem;
		flex-wrap: wrap;
	}

	.header-left {
		display: flex;
		align-items: center;
		gap: 1rem;
	}

	header h1 {
		font-size: 1.75rem;
		margin: 0;
	}

	.refresh-btn {
		padding: 0.5rem 1rem;
		background: #f0f0f0;
		border: none;
		border-radius: 4px;
		cursor: pointer;
		font-weight: 500;
		transition: background 0.2s;
	}

	.refresh-btn:hover:not(:disabled) {
		background: #e0e0e0;
	}

	.refresh-btn:disabled {
		opacity: 0.6;
		cursor: not-allowed;
	}

	.github-link {
		display: flex;
		align-items: center;
		justify-content: center;
		width: 36px;
		height: 36px;
		color: #333;
		border-radius: 6px;
		transition: background 0.2s;
	}

	.github-link:hover {
		background: #e0e0e0;
	}

	.github-link svg {
		width: 22px;
		height: 22px;
	}

	.status-badge {
		padding: 0.25rem 0.75rem;
		border-radius: 4px;
		color: white;
		font-size: 0.85rem;
		font-weight: 600;
	}

	.history-section {
		background: white;
		border: 1px solid #e0e0e0;
		border-radius: 8px;
		padding: 1.5rem;
		margin-bottom: 2rem;
	}

	.history-section h2 {
		font-size: 1.25rem;
		margin-bottom: 1rem;
		color: #333;
	}

	.section-header {
		display: flex;
		justify-content: space-between;
		align-items: center;
		margin-bottom: 1rem;
		flex-wrap: wrap;
		gap: 1rem;
	}

	.metric-selector {
		display: flex;
		align-items: center;
		gap: 0.5rem;
		font-size: 0.9rem;
	}

	.history-controls {
		display: flex;
		align-items: center;
		gap: 0.75rem;
		flex-wrap: wrap;
	}

	.metric-selector label {
		color: #666;
		font-weight: 500;
	}

	.metric-selector select {
		padding: 0.4rem 0.75rem;
		border: 1px solid #ddd;
		border-radius: 4px;
		font-size: 0.9rem;
		background: white;
		cursor: pointer;
	}

	.metric-selector select:hover {
		border-color: #2196f3;
	}

	.compact-input input {
		padding: 0.4rem 0.75rem;
		border: 1px solid #ddd;
		border-radius: 4px;
		font-size: 0.9rem;
	}

	.history-summary {
		display: flex;
		gap: 2rem;
		margin-bottom: 1.5rem;
		flex-wrap: wrap;
	}

	.summary-stat {
		display: flex;
		flex-direction: column;
		gap: 0.25rem;
	}

	.stat-label {
		font-size: 0.85rem;
		color: #666;
	}

	.stat-value {
		font-size: 1.5rem;
		font-weight: 600;
		color: #2196f3;
	}

	.stat-value.small {
		font-size: 0.95rem;
		line-height: 1.4;
	}

	.charts-grid {
		display: grid;
		grid-template-columns: repeat(auto-fit, minmax(400px, 1fr));
		gap: 1.5rem;
	}

	.chart-card {
		background: #fafafa;
		border-radius: 8px;
		padding: 1rem;
		overflow: visible;
	}

	.history-warning {
		margin-bottom: 1rem;
		padding: 0.75rem 1rem;
		border-radius: 6px;
		background: #fff4e5;
		color: #8a5700;
		font-size: 0.9rem;
	}

	.delta-strip {
		margin-bottom: 1.5rem;
		padding: 1rem;
		border: 1px solid #d7e6ff;
		border-radius: 10px;
		background: linear-gradient(135deg, #f8fbff 0%, #eef5ff 100%);
	}

	.delta-strip-header {
		display: flex;
		justify-content: space-between;
		align-items: flex-start;
		gap: 1rem;
		margin-bottom: 1rem;
		flex-wrap: wrap;
	}

	.delta-strip-header h3 {
		margin: 0 0 0.25rem;
		font-size: 1rem;
	}

	.delta-strip-header p {
		margin: 0;
		color: #5f6b7a;
		font-size: 0.9rem;
	}

	.delta-grid {
		display: grid;
		grid-template-columns: repeat(auto-fit, minmax(160px, 1fr));
		gap: 0.75rem;
	}

	.delta-card {
		display: flex;
		flex-direction: column;
		gap: 0.25rem;
		padding: 0.85rem 1rem;
		border-radius: 8px;
		background: rgba(255, 255, 255, 0.9);
		border: 1px solid rgba(62, 111, 190, 0.14);
	}

	.delta-label {
		font-size: 0.8rem;
		color: #607086;
	}

	.delta-card strong {
		font-size: 1.1rem;
		color: #1c2b39;
	}

	.positive {
		color: #1b8a5a;
	}

	.negative {
		color: #c2410c;
	}

	.history-run-list {
		display: grid;
		grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
		gap: 1rem;
		margin-top: 1.5rem;
	}

	.history-run-card {
		border: 1px solid #e6e6e6;
		border-radius: 10px;
		padding: 1rem;
		background: linear-gradient(180deg, #fff 0%, #f8fbff 100%);
		cursor: pointer;
		transition: border-color 0.2s ease, box-shadow 0.2s ease, transform 0.2s ease;
	}

	.history-run-card:hover,
	.history-run-card:focus-visible {
		border-color: #90b8ff;
		box-shadow: 0 8px 22px rgba(33, 88, 181, 0.08);
		transform: translateY(-1px);
		outline: none;
	}

	.history-run-card.selected {
		border-color: #2563eb;
		box-shadow: 0 0 0 2px rgba(37, 99, 235, 0.12);
	}

	.history-run-meta {
		display: flex;
		flex-direction: column;
		gap: 0.3rem;
		margin-bottom: 0.75rem;
	}

	.history-run-title {
		display: flex;
		align-items: center;
		gap: 0.5rem;
		flex-wrap: wrap;
	}

	.history-run-subtitle {
		font-size: 0.8rem;
		color: #6b7280;
		line-height: 1.4;
		word-break: break-word;
	}

	.history-run-metrics {
		display: flex;
		flex-wrap: wrap;
		gap: 0.75rem;
		font-size: 0.9rem;
		font-weight: 500;
		color: #334155;
		margin-bottom: 0.75rem;
	}

	.history-run-tags {
		display: flex;
		flex-wrap: wrap;
		gap: 0.5rem;
		align-items: center;
	}

	.history-tag {
		font-size: 0.78rem;
		padding: 0.2rem 0.45rem;
		border-radius: 999px;
		background: #eef2ff;
		color: #3547a5;
	}

	.history-link {
		font-size: 0.82rem;
		color: #0f62fe;
		text-decoration: none;
		font-weight: 600;
	}

	.history-link:hover {
		text-decoration: underline;
	}

	.history-search {
		min-width: 280px;
	}

	.loading, .error, .empty-state {
		text-align: center;
		padding: 2rem;
		color: #666;
	}

	.skeleton-wrapper {
		background: white;
		border: 1px solid #e0e0e0;
		border-radius: 8px;
		padding: 1.5rem;
		margin-bottom: 2rem;
	}

	.skeleton-wrapper h2 {
		font-size: 1.25rem;
		margin-bottom: 1rem;
		color: #333;
	}

	.skeleton-grid {
		display: grid;
		grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
		gap: 1rem;
	}

	.empty-state {
		background: #f9f9f9;
		border-radius: 8px;
		margin-top: 2rem;
	}

	.empty-hint {
		font-size: 0.9rem;
		color: #999;
	}

	.error {
		color: #d32f2f;
	}

	.content {
		display: flex;
		flex-direction: column;
		gap: 2rem;
		animation: fadeIn 0.4s ease-in;
	}

	@keyframes fadeIn {
		from {
			opacity: 0;
			transform: translateY(10px);
		}
		to {
			opacity: 1;
			transform: translateY(0);
		}
	}

	section h2 {
		font-size: 1.25rem;
		margin-bottom: 1rem;
		color: #333;
	}

	.summary-card {
		background: white;
		border: 1px solid #e0e0e0;
		border-radius: 8px;
		padding: 1.5rem;
	}

	.summary-header {
		display: flex;
		justify-content: space-between;
		align-items: flex-start;
		gap: 1rem;
		margin-bottom: 1rem;
		flex-wrap: wrap;
	}

	.summary-header h2 {
		margin-bottom: 0.25rem;
	}

	.summary-subtitle {
		margin: 0;
		font-size: 0.92rem;
		color: #667085;
	}

	.summary-grid {
		display: grid;
		grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
		gap: 1rem;
	}

	.summary-item {
		display: flex;
		flex-direction: column;
		gap: 0.25rem;
	}

	.summary-item .label {
		font-size: 0.85rem;
		color: #666;
	}

	.summary-item .value {
		font-size: 1rem;
		font-weight: 500;
		color: #333;
	}

	.steps-grid {
		display: grid;
		grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
		gap: 1rem;
	}

	.step-card {
		background: white;
		border: 1px solid #e0e0e0;
		border-radius: 8px;
		overflow: visible;
		transition: box-shadow 0.2s ease, transform 0.2s ease;
	}

	.step-card:hover {
		box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
	}

	.step-header {
		display: flex;
		justify-content: space-between;
		align-items: center;
		padding: 0.75rem 1rem;
		background: #f9f9f9;
		border-bottom: 1px solid #e0e0e0;
	}

	.stage-name {
		font-weight: 600;
		color: #333;
	}

	.finding-badge {
		font-size: 0.75rem;
		padding: 0.2rem 0.5rem;
		border-radius: 3px;
		background: #ff9800;
		color: white;
	}

	.finding-badge.error {
		background: #f44336;
	}

	.step-content {
		padding: 1rem;
	}

	.metric-row {
		display: flex;
		justify-content: space-between;
		padding: 0.4rem 0;
		font-size: 0.9rem;
		border-bottom: 1px solid #f0f0f0;
	}

	.metric-row:last-child {
		border-bottom: none;
	}

	.metric-row span:first-child {
		color: #666;
	}

	.metric-row span:last-child {
		font-weight: 500;
		color: #333;
	}

	.metric-row .warning {
		color: #ff9800;
	}

	.findings {
		padding: 0.75rem 1rem;
		background: #fff3e0;
		border-top: 1px solid #ffe0b2;
	}

	.finding-item {
		font-size: 0.85rem;
		padding: 0.25rem 0;
	}

	.finding-item.error {
		color: #d32f2f;
	}

	.finding-item.warning {
		color: #e65100;
	}

	.metrics-grid {
		display: grid;
		grid-template-columns: repeat(auto-fill, minmax(150px, 1fr));
		gap: 1rem;
	}

	.metric-card {
		background: white;
		border: 1px solid #e0e0e0;
		border-radius: 8px;
		padding: 1rem;
		display: flex;
		flex-direction: column;
		gap: 0.5rem;
		position: relative;
		overflow: visible;
		transition: box-shadow 0.2s ease, border-color 0.2s ease;
	}

	.metric-card:hover {
		box-shadow: 0 2px 6px rgba(0, 0, 0, 0.08);
	}

	.threshold-summary {
		background: white;
		border: 1px solid #f0d7bf;
		border-radius: 8px;
		padding: 1.5rem;
	}

	.threshold-list {
		display: grid;
		grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
		gap: 0.9rem;
	}

	.threshold-card {
		padding: 0.9rem 1rem;
		border-radius: 8px;
		border: 1px solid #f6dcc7;
		background: #fffaf5;
	}

	.threshold-card-header {
		display: flex;
		justify-content: space-between;
		gap: 0.75rem;
		align-items: flex-start;
		margin-bottom: 0.5rem;
	}

	.threshold-card-header strong {
		font-size: 0.95rem;
		color: #7c2d12;
		word-break: break-word;
	}

	.threshold-badge {
		flex-shrink: 0;
		font-size: 0.75rem;
		padding: 0.2rem 0.45rem;
		border-radius: 999px;
		background: #fde6d3;
		color: #9a3412;
		font-weight: 600;
	}

	.threshold-card-body {
		display: flex;
		flex-direction: column;
		gap: 0.3rem;
		font-size: 0.88rem;
		color: #7c4a2d;
	}

	.metric-card-button {
		font: inherit;
		color: inherit;
		text-align: left;
		width: 100%;
	}

	.metric-label {
		font-size: 0.85rem;
		color: #666;
	}

	.metric-value {
		font-size: 1.25rem;
		font-weight: 600;
		color: #333;
		transition: color 0.3s ease, transform 0.3s ease;
	}

	.metric-value.highlight {
		color: #2196f3;
	}

	.metric-value.updated {
		animation: valueUpdate 0.5s ease;
	}

	@keyframes valueUpdate {
		0% {
			transform: scale(1);
		}
		50% {
			transform: scale(1.1);
			color: #2196f3;
		}
		100% {
			transform: scale(1);
		}
	}

	.page-types {
		display: flex;
		flex-wrap: wrap;
		gap: 0.25rem;
	}

	.page-type-badge {
		font-size: 0.75rem;
		padding: 0.15rem 0.4rem;
		background: #e0e0e0;
		border-radius: 3px;
		color: #555;
		font-weight: 500;
	}

	.retrieval-subsection {
		margin-top: 1.5rem;
		padding-top: 1.5rem;
		border-top: 1px solid #e0e0e0;
	}

	.retrieval-subsection h3 {
		font-size: 1rem;
		margin-bottom: 0.75rem;
		color: #555;
		font-weight: 500;
	}

	.source-dist-mini {
		display: flex;
		flex-wrap: wrap;
		gap: 0.25rem;
	}

	.source-badge {
		font-size: 0.7rem;
		padding: 0.15rem 0.4rem;
		background: #e0e0e0;
		border-radius: 3px;
		color: #555;
		font-weight: 500;
	}

	.data-quality-section {
		background: white;
		border: 1px solid #e0e0e0;
		border-radius: 8px;
		padding: 1.5rem;
		margin-bottom: 2rem;
	}

	/* Header Actions */
	.header-actions {
		display: flex;
		align-items: center;
		gap: 0.5rem;
		flex-wrap: wrap;
	}

	.action-btn {
		padding: 0.5rem 1rem;
		background: white;
		border: 1px solid #ddd;
		border-radius: 4px;
		cursor: pointer;
		font-weight: 500;
		font-size: 0.9rem;
		transition: all 0.2s;
	}

	.secondary-btn {
		background: #f8fbff;
		border-color: #cfe0ff;
		color: #2155b5;
	}

	.action-btn:hover:not(:disabled) {
		background: #f5f5f5;
		border-color: #2196f3;
	}

	.action-btn:disabled {
		opacity: 0.5;
		cursor: not-allowed;
	}

	.compare-btn.active {
		background: #e3f2fd;
		border-color: #2196f3;
		color: #1976d2;
	}

	/* Filters Section */
	.filters-section {
		background: white;
		border: 1px solid #e0e0e0;
		border-radius: 8px;
		padding: 1rem 1.5rem;
		margin-bottom: 1.5rem;
		display: flex;
		gap: 2rem;
		flex-wrap: wrap;
		align-items: flex-end;
	}

	.filter-group {
		display: flex;
		flex-direction: column;
		gap: 0.25rem;
		flex: 1;
		min-width: 200px;
	}

	.search-input {
		padding: 0.5rem 0.75rem;
		border: 1px solid #ddd;
		border-radius: 4px;
		font-size: 0.9rem;
		width: 100%;
	}

	.search-input:focus {
		outline: none;
		border-color: #2196f3;
		box-shadow: 0 0 0 2px rgba(33, 150, 243, 0.1);
	}

	/* Comparison Controls */
	.comparison-controls-section {
		background: #e3f2fd;
		border: 1px solid #bbdefb;
		border-radius: 8px;
		padding: 1rem 1.5rem;
		margin-bottom: 1.5rem;
	}

	.comparison-controls-section h3 {
		font-size: 1.1rem;
		margin: 0 0 1rem 0;
		color: #1976d2;
	}

	.comparison-controls {
		display: flex;
		gap: 2rem;
		flex-wrap: wrap;
	}

	.control-group {
		display: flex;
		flex-direction: column;
		gap: 0.5rem;
		min-width: 250px;
	}

	.control-group label {
		font-size: 0.85rem;
		color: #555;
		font-weight: 500;
	}

	.control-group select {
		padding: 0.5rem 0.75rem;
		border: 1px solid #ddd;
		border-radius: 4px;
		font-size: 0.9rem;
		background: white;
	}

	/* Comparison View */
	.comparison-view {
		background: white;
		border: 1px solid #e0e0e0;
		border-radius: 8px;
		padding: 1.5rem;
		margin-bottom: 2rem;
	}

	.comparison-view h2 {
		font-size: 1.25rem;
		margin-bottom: 1rem;
		color: #333;
	}

	.comparison-grid {
		display: grid;
		grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
		gap: 1.5rem;
	}

	.comparison-col h3 {
		font-size: 1rem;
		margin-bottom: 0.5rem;
		color: #555;
	}

	.run-id {
		font-size: 0.8rem;
		color: #999;
		margin-bottom: 1rem;
		font-family: monospace;
	}

	.run-link-row {
		margin: -0.5rem 0 1rem;
		font-size: 0.85rem;
	}

	.run-link-row a {
		color: #0f62fe;
		text-decoration: none;
	}

	.run-link-row a:hover {
		text-decoration: underline;
	}

	.metrics-grid.compact {
		grid-template-columns: 1fr;
		gap: 0.5rem;
	}

	.metric-value.delta {
		font-weight: 700;
	}

	.metric-value.delta.positive {
		color: #4caf50;
	}

	.metric-value.delta.negative {
		color: #f44336;
	}

	/* Responsive adjustments */
	@media (max-width: 768px) {
		.eval-container {
			padding: 0.5rem;
		}

		header {
			flex-direction: column;
			align-items: flex-start;
			gap: 1rem;
		}

		.header-left {
			width: 100%;
		}

		.header-actions {
			width: 100%;
			justify-content: stretch;
			flex-wrap: wrap;
		}

		.action-btn {
			flex: 1;
			min-width: 120px;
			font-size: 0.85rem;
			padding: 0.4rem 0.75rem;
		}

		.filters-section {
			flex-direction: column;
			gap: 1rem;
		}

		.comparison-grid {
			grid-template-columns: 1fr;
		}

		.steps-grid {
			grid-template-columns: 1fr;
		}

		.metrics-grid {
			grid-template-columns: repeat(2, 1fr);
		}

		.charts-grid {
			grid-template-columns: 1fr;
		}

		.history-summary {
			grid-template-columns: repeat(2, 1fr);
		}

		.summary-grid {
			grid-template-columns: 1fr;
		}

		.metric-value {
			font-size: 1.1rem;
		}
	}

	@media (max-width: 480px) {
		header h1 {
			font-size: 1.4rem;
		}

		.metrics-grid {
			grid-template-columns: 1fr;
		}

		.history-summary {
			grid-template-columns: 1fr;
		}

		.skeleton-grid {
			grid-template-columns: 1fr;
		}

		.action-btn {
			font-size: 0.8rem;
			padding: 0.35rem 0.65rem;
		}
	}

	/* Ablation Section */
	.ablation-section {
		background: white;
		border: 1px solid #e0e0e0;
		border-radius: 8px;
		padding: 1.5rem;
		margin-bottom: 2rem;
	}

	.ablation-section h2 {
		font-size: 1.25rem;
		margin-bottom: 1rem;
		color: #333;
	}

	.ablation-table-wrapper {
		overflow-x: auto;
	}

	.ablation-table {
		width: 100%;
		border-collapse: collapse;
		font-size: 0.9rem;
	}

	.ablation-table th,
	.ablation-table td {
		padding: 0.75rem 1rem;
		text-align: left;
		border-bottom: 1px solid #f0f0f0;
	}

	.ablation-table th {
		background: #f9f9f9;
		font-weight: 600;
		color: #555;
	}

	.ablation-table tr.highlighted {
		background: #e3f2fd;
		font-weight: 500;
	}

	.ablation-table td.good {
		color: #4caf50;
		font-weight: 600;
	}

	.strategy-name {
		font-weight: 500;
	}

	.baseline-badge {
		display: inline-block;
		margin-left: 0.5rem;
		padding: 0.2rem 0.5rem;
		background: #2196f3;
		color: white;
		font-size: 0.75rem;
		border-radius: 3px;
		font-weight: 600;
	}

	.ablation-message {
		margin-top: 1rem;
		color: #666;
		font-style: italic;
		font-size: 0.9rem;
	}

	/* Clickable metric cards */
	.metric-card.clickable {
		cursor: pointer;
		transition: all 0.2s;
	}

	.metric-card.clickable:hover {
		transform: translateY(-2px);
		box-shadow: 0 4px 8px rgba(0, 0, 0, 0.1);
		border-color: #2196f3;
	}

	.metric-card.clickable::after {
		content: '↓';
		position: absolute;
		bottom: 0.5rem;
		right: 0.75rem;
		font-size: 0.8rem;
		color: #2196f3;
		opacity: 0;
		transition: opacity 0.2s;
	}

	.metric-card.clickable:hover::after {
		opacity: 1;
	}
</style>
