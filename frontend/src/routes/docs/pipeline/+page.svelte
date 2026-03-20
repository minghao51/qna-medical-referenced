<script lang="ts">
	import DagFlowDiagram from '$lib/components/DagFlowDiagram.svelte';
	import type { DagStage, DagConnection } from '$lib/components/DagFlowDiagram.svelte';

	const ingestionStages: DagStage[] = [
		{ id: 'l0', title: 'L0: Web Download', description: 'Downloads HTML from gov health sites' },
		{ id: 'l0b', title: 'L0b: PDF Download', description: 'Downloads PDF clinical guidelines' },
		{ id: 'l1', title: 'L1: HTML→Markdown', description: 'Converts HTML to structured Markdown' },
		{ id: 'l2', title: 'L2: PDF Extract', description: 'Extracts text from PDFs with pypdf/pdfplumber' },
		{ id: 'l3', title: 'L3: Chunking', description: 'Splits docs into overlapping chunks' },
		{ id: 'l4', title: 'L4: Reference Data', description: 'Loads CSV reference ranges' },
		{ id: 'l5', title: 'L5: Index', description: 'Embeds chunks & stores with hybrid search' },
		{ id: 'l6', title: 'L6: RAG Init', description: 'Initializes runtime retrieval index' },
	];

	const ingestionConnections: DagConnection[] = [
		{ from: 'l0', to: 'l1' },
		{ from: 'l0b', to: 'l2' },
		{ from: 'l1', to: 'l3' },
		{ from: 'l2', to: 'l3' },
		{ from: 'l3', to: 'l5' },
		{ from: 'l4', to: 'l5' },
		{ from: 'l5', to: 'l6' },
	];

	const ragQueryStages: DagStage[] = [
		{ id: 'query', title: 'Query Input', description: 'User question' },
		{ id: 'expand', title: 'Query Expansion', description: 'Tokenize, expand acronyms, optional HyDE' },
		{ id: 'retrieve', title: 'Hybrid Retrieval', description: 'Semantic + BM25 with RRF fusion' },
		{ id: 'mmr', title: 'MMR Rerank', description: 'Maximal Marginal Relevance diversification' },
		{ id: 'format', title: 'Context Format', description: 'Builds source-labeled context blocks' },
		{ id: 'generate', title: 'Generation', description: 'LLM generates final answer' },
	];

	const ragConnections: DagConnection[] = [
		{ from: 'query', to: 'expand' },
		{ from: 'expand', to: 'retrieve' },
		{ from: 'retrieve', to: 'mmr' },
		{ from: 'mmr', to: 'format' },
		{ from: 'format', to: 'generate' },
	];

	const evalStages: DagStage[] = [
		{ id: 'l0', title: 'L0: Download Audit', description: 'Validates raw HTML files' },
		{ id: 'l1', title: 'L1: HTML Quality', description: 'Checks markdown conversion quality' },
		{ id: 'l2', title: 'L2: PDF Extract', description: 'Validates PDF text extraction' },
		{ id: 'l3', title: 'L3: Chunking', description: 'Assesses text chunking quality' },
		{ id: 'l4', title: 'L4: Reference Data', description: 'Validates CSV reference ranges' },
		{ id: 'l5', title: 'L5: Vector Index', description: 'Checks embedding consistency' },
		{ id: 'dataset', title: 'Dataset Build', description: 'Golden queries + synthetic questions' },
		{ id: 'retrieval', title: 'Retrieval Eval', description: 'Hit rate, MRR, NDCG metrics' },
		{ id: 'l6', title: 'L6: Answer Quality', description: 'DeepEval for answer judgment' },
		{ id: 'thresholds', title: 'Threshold Check', description: 'Compares metrics vs thresholds' },
		{ id: 'reporting', title: 'Reporting', description: 'Writes summary.md & logs to W&B' },
	];

	const evalConnections: DagConnection[] = [
		{ from: 'l0', to: 'l1' },
		{ from: 'l1', to: 'l2' },
		{ from: 'l2', to: 'l3' },
		{ from: 'l3', to: 'l5' },
		{ from: 'l4', to: 'l5' },
		{ from: 'l5', to: 'dataset' },
		{ from: 'dataset', to: 'retrieval' },
		{ from: 'retrieval', to: 'l6' },
		{ from: 'l6', to: 'thresholds' },
		{ from: 'retrieval', to: 'thresholds' },
		{ from: 'thresholds', to: 'reporting' },
	];
</script>

<svelte:head>
	<title>Pipeline Documentation</title>
</svelte:head>

<div class="docs-container">
	<nav class="nav-bar">
		<a href="/" class="nav-link">Chat</a>
		<a href="/eval" class="nav-link">Pipeline Eval</a>
		<a href="/docs/pipeline" class="nav-link active">Pipeline Docs</a>
		<a href="https://github.com/anomalyco/qna_medical_referenced" target="_blank" rel="noopener noreferrer" class="nav-github-link" aria-label="View on GitHub">
			<svg viewBox="0 0 24 24" fill="currentColor" xmlns="http://www.w3.org/2000/svg">
				<path d="M12 0C5.37 0 0 5.37 0 12c0 5.31 3.435 9.795 8.205 11.385.6.105.825-.255.825-.57 0-.285-.015-1.23-.015-2.235-3.015.555-3.795-.735-4.035-1.41-.135-.345-.72-1.41-1.23-1.695-.42-.225-1.02-.78-.015-.795.945-.015 1.62.87 1.845 1.23 1.08 1.815 2.805 1.305 3.495.99.105-.78.42-1.305.765-1.605-2.67-.3-5.46-1.335-5.46-5.925 0-1.305.465-2.385 1.23-3.225-.12-.3-.54-1.53.12-3.18 0 0 1.005-.315 3.3 1.23.96-.27 1.98-.405 3-.405s2.04.135 3 .405c2.295-1.56 3.3-1.23 3.3-1.23.66 1.65.24 2.88.12 3.18.765.84 1.23 1.905 1.23 3.225 0 4.605-2.805 5.625-5.475 5.925.435.375.81 1.095.81 2.22 0 1.605-.015 2.895-.015 3.3 0 .315.225.69.825.57A12.02 12.02 0 0 0 24 12c0-6.63-5.37-12-12-12z"/>
			</svg>
		</a>
	</nav>

	<header class="docs-header">
		<div class="header-left">
			<h1>Pipeline Architecture</h1>
			<p class="subtitle">Ingestion, RAG, and Evaluation flow documentation</p>
		</div>
	</header>

	<div class="content">
		<section class="section">
			<h2>Data Ingestion Pipeline</h2>
			<p class="section-desc">
				The ingestion pipeline transforms raw HTML and PDF documents into indexed, searchable chunks.
				Each stage produces artifacts that feed into the next stage.
			</p>

			<DagFlowDiagram
				title="Ingestion DAG"
				stages={ingestionStages}
				connections={ingestionConnections}
			/>

			<div class="key-metrics">
				<h4>Chunking Configuration by Source Type</h4>
				<table class="config-table">
					<thead>
						<tr>
							<th>Source</th>
							<th>Chunk Size</th>
							<th>Overlap</th>
							<th>Strategy</th>
							<th>Min Chunk</th>
						</tr>
					</thead>
					<tbody>
						<tr>
							<td>PDF</td>
							<td>650</td>
							<td>80</td>
							<td>recursive</td>
							<td>140</td>
						</tr>
						<tr>
							<td>Markdown</td>
							<td>600</td>
							<td>80</td>
							<td>recursive</td>
							<td>80</td>
						</tr>
						<tr>
							<td>Default</td>
							<td>650</td>
							<td>80</td>
							<td>recursive</td>
							<td>120</td>
						</tr>
					</tbody>
				</table>
			</div>
		</section>

		<section class="section">
			<h2>RAG Query Flow</h2>
			<p class="section-desc">
				When a user asks a question, the RAG pipeline expands the query, retrieves relevant chunks,
				diversifies results, and formats context for generation.
			</p>

			<DagFlowDiagram
				title="RAG Query DAG"
				stages={ragQueryStages}
				connections={ragConnections}
			/>

			<div class="search-modes">
				<h4>Search Modes</h4>
				<div class="mode-grid">
					<div class="mode-card active">
						<strong>rrf_hybrid</strong>
						<span>Reciprocal Rank Fusion (default)</span>
					</div>
					<div class="mode-card">
						<strong>semantic_only</strong>
						<span>Embedding-based only</span>
					</div>
					<div class="mode-card">
						<strong>bm25_only</strong>
						<span>Keyword-based only</span>
					</div>
					<div class="mode-card">
						<strong>legacy_hybrid</strong>
						<span>Weighted combination</span>
					</div>
				</div>
			</div>
		</section>

		<section class="section">
			<h2>Evaluation Pipeline</h2>
			<p class="section-desc">
				The evaluation pipeline assesses each stage of the ingestion pipeline and measures
				retrieval quality against golden queries.
			</p>

			<DagFlowDiagram
				title="Evaluation DAG"
				stages={evalStages}
				connections={evalConnections}
			/>

			<div class="eval-metrics">
				<h4>Retrieval Metrics (L6)</h4>
				<div class="metrics-grid">
					<div class="metric-item">
						<strong>Hit Rate @k</strong>
						<span>% of queries with relevant doc in top-k</span>
					</div>
					<div class="metric-item">
						<strong>MRR</strong>
						<span>Mean Reciprocal Rank of first relevant doc</span>
					</div>
					<div class="metric-item">
						<strong>NDCG @k</strong>
						<span>Normalized Discounted Cumulative Gain</span>
					</div>
					<div class="metric-item">
						<strong>Precision @k</strong>
						<span>% of retrieved docs that are relevant</span>
					</div>
					<div class="metric-item">
						<strong>Recall @k</strong>
						<span>% of relevant docs that are retrieved</span>
					</div>
					<div class="metric-item">
						<strong>Latency</strong>
						<span>p50 and p95 retrieval times</span>
					</div>
				</div>
			</div>
		</section>
	</div>
</div>

<style>
	.docs-container {
		max-width: 1200px;
		width: 100%;
		margin: 0 auto;
		padding: 1rem;
	}

	.nav-bar {
		display: flex;
		gap: 1rem;
		margin-bottom: 1rem;
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

	.nav-github-link {
		margin-left: auto;
		display: flex;
		align-items: center;
		padding: 0.5rem;
		color: #666;
		border-radius: 4px;
	}

	.nav-github-link:hover {
		background: #f0f0f0;
		color: #333;
	}

	.nav-github-link svg {
		width: 20px;
		height: 20px;
	}

	.docs-header {
		display: flex;
		justify-content: space-between;
		align-items: flex-start;
		margin-bottom: 2rem;
		padding-bottom: 1rem;
		border-bottom: 2px solid #e5e7eb;
	}

	.header-left h1 {
		font-size: 1.75rem;
		margin: 0 0 0.25rem 0;
		color: #1f2937;
	}

	.subtitle {
		color: #6b7280;
		margin: 0;
		font-size: 0.95rem;
	}

	.content {
		display: flex;
		flex-direction: column;
		gap: 3rem;
	}

	.section h2 {
		font-size: 1.5rem;
		color: #1f2937;
		margin-bottom: 0.5rem;
	}

	.section-desc {
		color: #6b7280;
		margin-bottom: 1.5rem;
		max-width: 800px;
	}

	.key-metrics {
		margin-top: 1.5rem;
		padding: 1rem;
		background: #f9fafb;
		border-radius: 8px;
	}

	.key-metrics h4 {
		font-size: 0.875rem;
		color: #374151;
		margin-bottom: 0.75rem;
	}

	.config-table {
		width: 100%;
		border-collapse: collapse;
		font-size: 0.8rem;
	}

	.config-table th, .config-table td {
		padding: 0.5rem;
		text-align: left;
		border-bottom: 1px solid #e5e7eb;
	}

	.config-table th {
		font-weight: 600;
		color: #6b7280;
		font-size: 0.75rem;
		text-transform: uppercase;
	}

	.config-table td {
		color: #374151;
		font-family: monospace;
	}

	.search-modes {
		margin-top: 1.5rem;
	}

	.search-modes h4 {
		font-size: 0.875rem;
		color: #374151;
		margin-bottom: 0.75rem;
	}

	.mode-grid {
		display: grid;
		grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
		gap: 0.75rem;
	}

	.mode-card {
		display: flex;
		flex-direction: column;
		gap: 0.25rem;
		padding: 0.75rem;
		background: white;
		border: 1px solid #e5e7eb;
		border-radius: 8px;
		font-size: 0.8rem;
	}

	.mode-card.active {
		border-color: #3b82f6;
		background: #eff6ff;
	}

	.mode-card strong {
		font-family: monospace;
		color: #1f2937;
	}

	.mode-card span {
		color: #6b7280;
		font-size: 0.75rem;
	}

	.eval-metrics {
		margin-top: 1.5rem;
		padding: 1rem;
		background: #f9fafb;
		border-radius: 8px;
	}

	.eval-metrics h4 {
		font-size: 0.875rem;
		color: #374151;
		margin-bottom: 0.75rem;
	}

	.metrics-grid {
		display: grid;
		grid-template-columns: repeat(auto-fit, minmax(160px, 1fr));
		gap: 0.75rem;
	}

	.metric-item {
		display: flex;
		flex-direction: column;
		gap: 0.2rem;
	}

	.metric-item strong {
		font-size: 0.8rem;
		color: #1f2937;
	}

	.metric-item span {
		font-size: 0.7rem;
		color: #6b7280;
	}

	@media (max-width: 768px) {
		.docs-header {
			flex-direction: column;
			gap: 1rem;
		}
	}
</style>
