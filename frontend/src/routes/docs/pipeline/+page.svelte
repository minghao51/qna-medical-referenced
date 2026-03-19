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
	</nav>

	<header class="docs-header">
		<div class="header-left">
			<h1>Pipeline Architecture</h1>
			<p class="subtitle">Ingestion, RAG, and Evaluation flow documentation</p>
		</div>
		<div class="header-right">
			<a href="https://github.com/anomalyco/qna_medical_referenced" target="_blank" rel="noopener noreferrer" class="github-link">
				<svg viewBox="0 0 24 24" fill="currentColor" xmlns="http://www.w3.org/2000/svg">
					<path d="M12 0C5.37 0 0 5.37 0 12c0 5.31 3.435 9.795 8.205 11.385.6.105.825-.255.825-.57 0-.285-.015-1.23-.015-2.235-3.015.555-3.795-.735-4.035-1.41-.135-.345-.72-1.41-1.23-1.695-.42-.225-1.02-.78-.015-.795.945-.015 1.62.87 1.845 1.23 1.08 1.815 2.805 1.305 3.495.99.105-.78.42-1.305.765-1.605-2.67-.3-5.46-1.335-5.46-5.925 0-1.305.465-2.385 1.23-3.225-.12-.3-.54-1.53.12-3.18 0 0 1.005-.315 3.3 1.23.96-.27 1.98-.405 3-.405s2.04.135 3 .405c2.295-1.56 3.3-1.23 3.3-1.23.66 1.65.24 2.88.12 3.18.765.84 1.23 1.905 1.23 3.225 0 4.605-2.805 5.625-5.475 5.925.435.375.81 1.095.81 2.22 0 1.605-.015 2.895-.015 3.3 0 .315.225.69.825.57A12.02 12.02 0 0 0 24 12c0-6.63-5.37-12-12-12z"/>
				</svg>
				<span>View on GitHub</span>
			</a>
		</div>
	</header>

	<div class="content">
		<section class="section">
			<h2>Data Ingestion Pipeline</h2>
			<p class="section-desc">
				The ingestion pipeline transforms raw HTML and PDF documents into indexed, searchable chunks.
				Each stage produces artifacts that feed into the next stage.
			</p>
			
			<div class="flow-diagram">
				<div class="flow-row">
					<div class="flow-branch">
						<div class="branch-label">HTML Sources</div>
						<div class="branch-stages">
							<div class="stage-card l0">
								<div class="stage-icon">L0</div>
								<div class="stage-info">
									<strong>Web Download</strong>
									<span>Downloads HTML from Singapore government health sites (ACE-HTA, HealthHub, HPP, MOH)</span>
								</div>
							</div>
							<div class="flow-arrow">↓</div>
							<div class="stage-card l1">
								<div class="stage-icon">L1</div>
								<div class="stage-info">
									<strong>HTML → Markdown</strong>
									<span>Converts HTML to Markdown with structured blocks, page classification, boilerplate removal</span>
								</div>
							</div>
						</div>
					</div>
					
					<div class="flow-branch">
						<div class="branch-label">PDF Sources</div>
						<div class="branch-stages">
							<div class="stage-card l0b">
								<div class="stage-icon">L0b</div>
								<div class="stage-info">
									<strong>PDF Download</strong>
									<span>Downloads PDF clinical guidelines from government health sites</span>
								</div>
							</div>
							<div class="flow-arrow">↓</div>
							<div class="stage-card l2">
								<div class="stage-icon">L2</div>
								<div class="stage-info">
									<strong>PDF Extraction</strong>
									<span>Extracts text using pypdf (primary) or pdfplumber (fallback), creates page-level structured blocks</span>
								</div>
							</div>
						</div>
					</div>
				</div>

				<div class="flow-arrow center">↓</div>

				<div class="merge-row">
					<div class="stage-card l3">
						<div class="stage-icon">L3</div>
						<div class="stage-info">
							<strong>Chunking</strong>
							<span>Splits documents into overlapping chunks using recursive strategy</span>
							<div class="chunk-configs">
								<span class="config-tag">PDF: 650 chars, 80 overlap</span>
								<span class="config-tag">Markdown: 600 chars, 80 overlap</span>
							</div>
						</div>
					</div>
				</div>

				<div class="flow-arrow center">↓</div>

				<div class="parallel-row">
					<div class="stage-card l4">
						<div class="stage-icon">L4</div>
						<div class="stage-info">
							<strong>Reference Data</strong>
							<span>Loads CSV reference ranges as documents</span>
						</div>
					</div>
					<div class="flow-arrow horizontal">→</div>
					<div class="stage-card l5">
						<div class="stage-icon">L5</div>
						<div class="stage-info">
							<strong>Embed & Index</strong>
							<span>Generates embeddings using Qwen model, stores with hybrid search (semantic + BM25)</span>
						</div>
					</div>
				</div>

				<div class="flow-arrow center">↓</div>

				<div class="stage-card l6">
					<div class="stage-icon">L6</div>
					<div class="stage-info">
						<strong>RAG Runtime Init</strong>
						<span>Initializes runtime retrieval index with query expansion and MMR reranking</span>
					</div>
				</div>
			</div>

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

			<div class="rag-flow">
				<div class="rag-stage">
					<div class="rag-number">1</div>
					<div class="rag-content">
						<h4>Query Expansion</h4>
						<p>Multiple query variants are generated from the original:</p>
						<ul>
							<li>Original query</li>
							<li>Tokenized version</li>
							<li>Query + expanded acronyms</li>
							<li>Keyword-focused version</li>
							<li><strong>HyDE (optional):</strong> Generates hypothetical answer via LLM</li>
						</ul>
					</div>
					<div class="rag-arrow">→</div>
				</div>

				<div class="rag-stage">
					<div class="rag-number">2</div>
					<div class="rag-content">
						<h4>Hybrid Retrieval</h4>
						<p>For each expanded query, performs:</p>
						<ul>
							<li><strong>Semantic search:</strong> Query embedding → cosine similarity</li>
							<li><strong>BM25 keyword search:</strong> TF-based scoring</li>
							<li><strong>RRF fusion:</strong> Reciprocal Rank Fusion combining rankings</li>
						</ul>
					</div>
					<div class="rag-arrow">→</div>
				</div>

				<div class="rag-stage">
					<div class="rag-number">3</div>
					<div class="rag-content">
						<h4>MMR Diversification</h4>
						<p>Maximal Marginal Relevance reranking enforces:</p>
						<ul>
							<li>Max 2 chunks per source page</li>
							<li>Max 3 chunks per source</li>
							<li>Falls back to lower-ranked docs if constraints not met</li>
						</ul>
					</div>
					<div class="rag-arrow">→</div>
				</div>

				<div class="rag-stage">
					<div class="rag-number">4</div>
					<div class="rag-content">
						<h4>Context Formatting</h4>
						<p>Builds context string with source labels:</p>
						<pre>[Source: HealthHub]\ncontent\n[Source: ACE-HTA]\ncontent</pre>
					</div>
					<div class="rag-arrow final">→</div>
				</div>

				<div class="rag-stage final">
					<div class="rag-number gen">G</div>
					<div class="rag-content">
						<h4>Generation</h4>
						<p>LLM generates final answer based on context + conversation history</p>
					</div>
				</div>
			</div>

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

			<div class="eval-flow">
				<div class="eval-row">
					<div class="eval-branch">
						<div class="eval-stage l0">
							<div class="eval-icon">L0</div>
							<div class="eval-info">
								<strong>Download Audit</strong>
								<span>Validates raw HTML files: duplicate detection, parse success, file sizes</span>
							</div>
						</div>
						<div class="flow-arrow">↓</div>
						<div class="eval-stage l1">
							<div class="eval-icon">L1</div>
							<div class="eval-info">
								<strong>HTML Quality</strong>
								<span>Checks markdown conversion: retention ratio, heading preservation, boilerplate</span>
							</div>
						</div>
						<div class="flow-arrow">↓</div>
						<div class="eval-stage l2">
							<div class="eval-icon">L2</div>
							<div class="eval-info">
								<strong>PDF Extraction</strong>
								<span>Validates PDF text: empty pages, fallback extractor, OCR needs</span>
							</div>
						</div>
						<div class="flow-arrow">↓</div>
						<div class="eval-stage l3">
							<div class="eval-icon">L3</div>
							<div class="eval-info">
								<strong>Chunking Quality</strong>
								<span>Assesses chunking: duplicate chunks, boundary cuts, overlap quality</span>
							</div>
						</div>
					</div>

					<div class="eval-side">
						<div class="eval-stage l4">
							<div class="eval-icon">L4</div>
							<div class="eval-info">
								<strong>Reference Data</strong>
								<span>Validates CSV: completeness, duplicate names, parseable ranges</span>
							</div>
						</div>
					</div>
				</div>

				<div class="flow-arrow center">↓</div>

				<div class="eval-row">
					<div class="eval-stage l5">
						<div class="eval-icon">L5</div>
						<div class="eval-info">
							<strong>Vector Index</strong>
							<span>Checks index: embedding consistency, content hashes, source distribution</span>
						</div>
					</div>
				</div>

				<div class="flow-arrow center">↓</div>

				<div class="eval-stage dataset">
					<div class="eval-icon">DS</div>
					<div class="eval-info">
						<strong>Dataset Build</strong>
						<span>Loads golden queries + generates synthetic questions via LLM</span>
					</div>
				</div>

				<div class="flow-arrow center">↓</div>

				<div class="eval-row converge">
					<div class="eval-stage retrieval">
						<div class="eval-icon">RET</div>
						<div class="eval-info">
							<strong>Retrieval Evaluation</strong>
							<span>Runs queries against RAG runtime, computes hit rate, MRR, NDCG</span>
						</div>
					</div>
					<div class="flow-arrow left">←</div>
					<div class="eval-stage l6">
						<div class="eval-icon">L6</div>
						<div class="eval-info">
							<strong>Answer Quality (optional)</strong>
							<span>DeepEval judge: factual accuracy, completeness, clinical relevance</span>
						</div>
					</div>
				</div>

				<div class="flow-arrow center">↓</div>

				<div class="eval-row thresholds-reporting">
					<div class="eval-stage thresholds">
						<div class="eval-icon">TH</div>
						<div class="eval-info">
							<strong>Threshold Check</strong>
							<span>Compares all metrics against configurable thresholds</span>
						</div>
					</div>
					<div class="flow-arrow horizontal">→</div>
					<div class="eval-stage reporting">
						<div class="eval-icon">RP</div>
						<div class="eval-info">
							<strong>Reporting</strong>
							<span>Writes summary.md, logs to W&B, persists artifacts</span>
						</div>
					</div>
				</div>
			</div>

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

	.github-link {
		display: flex;
		align-items: center;
		gap: 0.5rem;
		padding: 0.5rem 1rem;
		background: #24292e;
		color: white;
		text-decoration: none;
		border-radius: 6px;
		font-size: 0.875rem;
		font-weight: 500;
		transition: background 0.2s;
	}

	.github-link:hover {
		background: #373e47;
	}

	.github-link svg {
		width: 18px;
		height: 18px;
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

	.flow-diagram {
		display: flex;
		flex-direction: column;
		align-items: center;
		gap: 0.5rem;
		padding: 1.5rem;
		background: linear-gradient(135deg, #f8fafc 0%, #f1f5f9 100%);
		border-radius: 12px;
	}

	.flow-row {
		display: flex;
		gap: 2rem;
		width: 100%;
		justify-content: center;
	}

	.flow-branch {
		display: flex;
		flex-direction: column;
		align-items: center;
	}

	.branch-label {
		font-size: 0.75rem;
		font-weight: 600;
		color: #6b7280;
		text-transform: uppercase;
		letter-spacing: 0.05em;
		margin-bottom: 0.5rem;
	}

	.branch-stages {
		display: flex;
		flex-direction: column;
		align-items: center;
	}

	.stage-card {
		display: flex;
		align-items: flex-start;
		gap: 0.75rem;
		padding: 0.75rem 1rem;
		background: white;
		border: 2px solid #e5e7eb;
		border-radius: 10px;
		min-width: 220px;
		max-width: 280px;
	}

	.stage-card.l0 { border-color: #3b82f6; }
	.stage-card.l0b { border-color: #8b5cf6; }
	.stage-card.l1 { border-color: #10b981; }
	.stage-card.l2 { border-color: #f59e0b; }
	.stage-card.l3 { border-color: #ef4444; }
	.stage-card.l4 { border-color: #6366f1; }
	.stage-card.l5 { border-color: #14b8a6; }
	.stage-card.l6 { border-color: #f97316; }

	.stage-icon {
		width: 32px;
		height: 32px;
		border-radius: 8px;
		display: flex;
		align-items: center;
		justify-content: center;
		font-weight: 700;
		font-size: 0.75rem;
		color: white;
		flex-shrink: 0;
	}

	.stage-card.l0 .stage-icon { background: #3b82f6; }
	.stage-card.l0b .stage-icon { background: #8b5cf6; }
	.stage-card.l1 .stage-icon { background: #10b981; }
	.stage-card.l2 .stage-icon { background: #f59e0b; }
	.stage-card.l3 .stage-icon { background: #ef4444; }
	.stage-card.l4 .stage-icon { background: #6366f1; }
	.stage-card.l5 .stage-icon { background: #14b8a6; }
	.stage-card.l6 .stage-icon { background: #f97316; }

	.stage-info {
		display: flex;
		flex-direction: column;
		gap: 0.25rem;
	}

	.stage-info strong {
		font-size: 0.875rem;
		color: #1f2937;
	}

	.stage-info span {
		font-size: 0.75rem;
		color: #6b7280;
		line-height: 1.4;
	}

	.chunk-configs {
		display: flex;
		gap: 0.25rem;
		margin-top: 0.25rem;
		flex-wrap: wrap;
	}

	.config-tag {
		font-size: 0.65rem;
		padding: 0.125rem 0.375rem;
		background: #f3f4f6;
		border-radius: 4px;
		color: #6b7280;
		font-family: monospace;
	}

	.flow-arrow {
		color: #9ca3af;
		font-size: 1.25rem;
		margin: 0.25rem 0;
	}

	.flow-arrow.center {
		text-align: center;
	}

	.flow-arrow.horizontal {
		margin: 0 0.5rem;
	}

	.merge-row, .parallel-row {
		display: flex;
		align-items: center;
		justify-content: center;
		gap: 0.5rem;
		width: 100%;
	}

	.parallel-row {
		gap: 1rem;
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

	.rag-flow {
		display: flex;
		flex-direction: column;
		padding: 1.5rem;
		background: linear-gradient(135deg, #f8fafc 0%, #f1f5f9 100%);
		border-radius: 12px;
	}

	.rag-stage {
		display: flex;
		align-items: flex-start;
		gap: 1rem;
	}

	.rag-number {
		width: 32px;
		height: 32px;
		border-radius: 50%;
		background: #3b82f6;
		color: white;
		display: flex;
		align-items: center;
		justify-content: center;
		font-weight: 700;
		font-size: 0.875rem;
		flex-shrink: 0;
	}

	.rag-number.gen {
		background: #10b981;
	}

	.rag-content {
		flex: 1;
		background: white;
		padding: 1rem;
		border-radius: 8px;
		border: 1px solid #e5e7eb;
	}

	.rag-content h4 {
		margin: 0 0 0.5rem 0;
		font-size: 0.95rem;
		color: #1f2937;
	}

	.rag-content p {
		margin: 0 0 0.5rem 0;
		font-size: 0.85rem;
		color: #6b7280;
	}

	.rag-content ul {
		margin: 0;
		padding-left: 1.25rem;
		font-size: 0.85rem;
		color: #374151;
	}

	.rag-content li {
		margin-bottom: 0.25rem;
	}

	.rag-content pre {
		background: #f3f4f6;
		padding: 0.75rem;
		border-radius: 6px;
		font-size: 0.75rem;
		font-family: monospace;
		overflow-x: auto;
		margin: 0.5rem 0 0 0;
	}

	.rag-arrow {
		color: #9ca3af;
		font-size: 1.5rem;
		padding-top: 0.5rem;
	}

	.rag-arrow.final {
		color: #10b981;
	}

	.rag-stage.final {
		margin-top: 0.5rem;
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

	.eval-flow {
		display: flex;
		flex-direction: column;
		align-items: center;
		gap: 0.5rem;
		padding: 1.5rem;
		background: linear-gradient(135deg, #f8fafc 0%, #f1f5f9 100%);
		border-radius: 12px;
	}

	.eval-row {
		display: flex;
		gap: 1.5rem;
		width: 100%;
		justify-content: center;
		flex-wrap: wrap;
	}

	.eval-row.converge {
		align-items: center;
	}

	.eval-row.thresholds-reporting {
		flex-wrap: nowrap;
	}

	.eval-branch {
		display: flex;
		flex-direction: column;
		align-items: center;
	}

	.eval-side {
		display: flex;
		flex-direction: column;
		align-items: center;
	}

	.eval-stage {
		display: flex;
		align-items: flex-start;
		gap: 0.75rem;
		padding: 0.75rem 1rem;
		background: white;
		border: 2px solid #e5e7eb;
		border-radius: 10px;
		min-width: 200px;
		max-width: 260px;
	}

	.eval-icon {
		width: 36px;
		height: 36px;
		border-radius: 8px;
		display: flex;
		align-items: center;
		justify-content: center;
		font-weight: 700;
		font-size: 0.7rem;
		color: white;
		flex-shrink: 0;
	}

	.eval-stage.l0 .eval-icon { background: #3b82f6; }
	.eval-stage.l1 .eval-icon { background: #10b981; }
	.eval-stage.l2 .eval-icon { background: #f59e0b; }
	.eval-stage.l3 .eval-icon { background: #ef4444; }
	.eval-stage.l4 .eval-icon { background: #6366f1; }
	.eval-stage.l5 .eval-icon { background: #14b8a6; }
	.eval-stage.dataset .eval-icon { background: #ec4899; }
	.eval-stage.retrieval .eval-icon { background: #8b5cf6; }
	.eval-stage.l6 .eval-icon { background: #f97316; }
	.eval-stage.thresholds .eval-icon { background: #64748b; }
	.eval-stage.reporting .eval-icon { background: #0ea5e9; }

	.eval-info {
		display: flex;
		flex-direction: column;
		gap: 0.2rem;
	}

	.eval-info strong {
		font-size: 0.85rem;
		color: #1f2937;
	}

	.eval-info span {
		font-size: 0.7rem;
		color: #6b7280;
		line-height: 1.4;
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
		.flow-row {
			flex-direction: column;
			align-items: center;
		}

		.eval-row {
			flex-direction: column;
			align-items: center;
		}

		.eval-row.thresholds-reporting {
			flex-direction: column;
		}

		.docs-header {
			flex-direction: column;
			gap: 1rem;
		}

		.github-link {
			align-self: flex-start;
		}
	}
</style>
