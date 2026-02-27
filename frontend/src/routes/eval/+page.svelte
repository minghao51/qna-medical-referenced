<script lang="ts">
	import { onMount } from 'svelte';
	import type { EvaluationResponse, RetrievalMetrics, StepMetrics } from '$lib/types';

	let loading = $state(true);
	let error = $state('');
	let data = $state<EvaluationResponse | null>(null);

	const API_URL = 'http://localhost:8000';

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

	onMount(async () => {
		try {
			const res = await fetch(`${API_URL}/evaluation/latest`);
			if (!res.ok) {
				throw new Error('Failed to fetch evaluation data');
			}
			data = await res.json();
		} catch (e) {
			error = 'Failed to load evaluation data. Make sure the API is running.';
			console.error(e);
		} finally {
			loading = false;
		}
	});
</script>

<div class="eval-container">
	<nav class="nav-bar">
		<a href="/" class="nav-link">Chat</a>
		<a href="/eval" class="nav-link active">Pipeline Eval</a>
	</nav>
	<header>
		<h1>Pipeline Quality Assessment</h1>
		{#if data?.summary}
			<span class="status-badge" style="background: {getStatusColor(data.summary.status)}">
				{data.summary.status.toUpperCase()}
			</span>
		{/if}
	</header>

	{#if loading}
		<div class="loading">Loading evaluation data...</div>
	{:else if error}
		<div class="error">{error}</div>
	{:else if data}
		<div class="content">
			{#if data.summary}
				<section class="summary-card">
					<h2>Run Summary</h2>
					<div class="summary-grid">
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

			{#if data.step_metrics}
				<section class="steps-section">
					<h2>Pipeline Steps (L0-L5)</h2>
					<div class="steps-grid">
						{#each Object.entries(data.step_metrics) as [stage, metrics]: [string, any] (stage)}
							{@const agg = metrics.aggregate}
							{@const findings = metrics.findings || []}
							<div class="step-card">
								<div class="step-header">
									<span class="stage-name">{stage.toUpperCase()}</span>
									{#if findings.length > 0}
										<span class="finding-badge" class:error={findings.some(f => f.severity === 'error')}>
											{findings.length} issue(s)
										</span>
									{/if}
								</div>
								<div class="step-content">
									{#if stage === 'l0'}
										<div class="metric-row">
											<span>HTML Files</span>
											<span>{agg.html_file_count || 0}</span>
										</div>
										<div class="metric-row">
											<span>Parse Success Rate</span>
											<span>{formatPercent(agg.html_parse_success_rate || 0)}</span>
										</div>
										<div class="metric-row">
											<span>Duplicate Rate</span>
											<span>{formatPercent(agg.duplicate_file_rate || 0)}</span>
										</div>
									{:else if stage === 'l1'}
										<div class="metric-row">
											<span>Pairs Evaluated</span>
											<span>{agg.pairs_evaluated || 0}</span>
										</div>
										<div class="metric-row">
											<span>Empty Markdown Rate</span>
											<span class:warning={agg.markdown_empty_rate > 0.1}>
												{formatPercent(agg.markdown_empty_rate || 0)}
											</span>
										</div>
										<div class="metric-row">
											<span>Retention Ratio</span>
											<span>{formatPercent(agg.retention_ratio_mean || 0)}</span>
										</div>
									{:else if stage === 'l2'}
										<div class="metric-row">
											<span>PDF Files</span>
											<span>{agg.pdf_file_count || 0}</span>
										</div>
										<div class="metric-row">
											<span>Page Extraction Coverage</span>
											<span>{formatPercent(agg.page_extraction_coverage || 0)}</span>
										</div>
										<div class="metric-row">
											<span>Empty Page Rate</span>
											<span class:warning={agg.empty_page_rate > 0.2}>
												{formatPercent(agg.empty_page_rate || 0)}
											</span>
										</div>
									{:else if stage === 'l3'}
										<div class="metric-row">
											<span>Documents</span>
											<span>{agg.document_count || 0}</span>
										</div>
										<div class="metric-row">
											<span>Chunks</span>
											<span>{agg.chunk_count || 0}</span>
										</div>
										<div class="metric-row">
											<span>Duplicate Chunk Rate</span>
											<span class:warning={agg.duplicate_chunk_rate > 0.05}>
												{formatPercent(agg.duplicate_chunk_rate || 0)}
											</span>
										</div>
										<div class="metric-row">
											<span>Boundary Cut Rate</span>
											<span>{formatPercent(agg.boundary_cut_rate || 0)}</span>
										</div>
									{:else if stage === 'l4'}
										<div class="metric-row">
											<span>CSV Exists</span>
											<span>{agg.csv_exists ? 'Yes' : 'No'}</span>
										</div>
										<div class="metric-row">
											<span>Row Count</span>
											<span>{agg.row_count || 0}</span>
										</div>
										<div class="metric-row">
											<span>Completeness Rate</span>
											<span>{formatPercent(agg.row_completeness_rate || 0)}</span>
										</div>
									{:else if stage === 'l5'}
										<div class="metric-row">
											<span>Vector Count</span>
											<span>{agg.ids_count || 0}</span>
										</div>
										<div class="metric-row">
											<span>Embedding Dim</span>
											<span>{agg.embedding_dim || 'N/A'}</span>
										</div>
										<div class="metric-row">
											<span>Dims Consistent</span>
											<span>{agg.embedding_dim_consistent ? 'Yes' : 'No'}</span>
										</div>
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
					<h2>Retrieval Metrics (L6)</h2>
					<div class="metrics-grid">
						<div class="metric-card">
							<span class="metric-label">Query Count</span>
							<span class="metric-value">{rm.query_count}</span>
						</div>
						<div class="metric-card">
							<span class="metric-label">Hit Rate @k</span>
							<span class="metric-value highlight">{formatPercent(rm.hit_rate_at_k)}</span>
						</div>
						<div class="metric-card">
							<span class="metric-label">MRR</span>
							<span class="metric-value highlight">{rm.mrr.toFixed(3)}</span>
						</div>
						<div class="metric-card">
							<span class="metric-label">nDCG @k</span>
							<span class="metric-value">{formatPercent(rm.ndcg_at_k)}</span>
						</div>
						<div class="metric-card">
							<span class="metric-label">Source Hit Rate</span>
							<span class="metric-value">{formatPercent(rm.source_hit_rate)}</span>
						</div>
						<div class="metric-card">
							<span class="metric-label">Exact Chunk Hit</span>
							<span class="metric-value">{formatPercent(rm.exact_chunk_hit_rate)}</span>
						</div>
						<div class="metric-card">
							<span class="metric-label">Evidence Hit</span>
							<span class="metric-value">{formatPercent(rm.evidence_hit_rate)}</span>
						</div>
						<div class="metric-card">
							<span class="metric-label">Latency p50</span>
							<span class="metric-value">{rm.latency_p50_ms.toFixed(0)}ms</span>
						</div>
						<div class="metric-card">
							<span class="metric-label">Latency p95</span>
							<span class="metric-value">{rm.latency_p95_ms.toFixed(0)}ms</span>
						</div>
					</div>
				</section>
			{/if}

			{#if data.summary?.rag_metrics && data.summary.rag_metrics.status !== 'skipped'}
				<section class="rag-section">
					<h2>Answer Evaluation</h2>
					<div class="rag-stats">
						<div class="metric-card">
							<span class="metric-label">Relevance Score</span>
							<span class="metric-value">{data.summary.rag_metrics.relevance_score_mean?.toFixed(2) || 'N/A'}</span>
						</div>
						<div class="metric-card">
							<span class="metric-label">Faithfulness Score</span>
							<span class="metric-value">{data.summary.rag_metrics.faithfulness_score_mean?.toFixed(2) || 'N/A'}</span>
						</div>
					</div>
				</section>
			{/if}
		</div>
	{/if}
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
		align-items: center;
		gap: 1rem;
		margin-bottom: 2rem;
	}

	header h1 {
		font-size: 1.75rem;
		margin: 0;
	}

	.status-badge {
		padding: 0.25rem 0.75rem;
		border-radius: 4px;
		color: white;
		font-size: 0.85rem;
		font-weight: 600;
	}

	.loading, .error {
		text-align: center;
		padding: 2rem;
		color: #666;
	}

	.error {
		color: #d32f2f;
	}

	.content {
		display: flex;
		flex-direction: column;
		gap: 2rem;
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
		overflow: hidden;
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
	}

	.metric-label {
		font-size: 0.85rem;
		color: #666;
	}

	.metric-value {
		font-size: 1.25rem;
		font-weight: 600;
		color: #333;
	}

	.metric-value.highlight {
		color: #2196f3;
	}
</style>
