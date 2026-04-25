<script lang="ts">
	import AppShell from '$lib/components/AppShell.svelte';
	import MermaidDiagram from '$lib/components/MermaidDiagram.svelte';
	import TabNav from '$lib/components/TabNav.svelte';

	type TabId = 'overview' | 'ingestion' | 'query' | 'evaluation' | 'features' | 'troubleshooting';

	const tabs: Array<{ id: TabId; label: string }> = [
		{ id: 'overview', label: 'Overview' },
		{ id: 'ingestion', label: 'Ingestion' },
		{ id: 'query', label: 'Query / RAG' },
		{ id: 'evaluation', label: 'Evaluation' },
		{ id: 'features', label: 'Features' },
		{ id: 'troubleshooting', label: 'Troubleshooting' }
	];

	let activeTab: TabId = $state('overview');

	const overviewDiagram = `
flowchart TB
    subgraph Ingest[" "]
        direction TB
        I1["Ingest<br/><small>Download, parse, chunk, index</small>"]
    end

    subgraph Retrieve[" "]
        direction TB
        R1["Retrieve<br/><small>Expand query, hybrid search, rerank</small>"]
    end

    subgraph Answer[" "]
        direction TB
        A1["Answer<br/><small>Build context and generate response</small>"]
    end

    subgraph Evaluate[" "]
        direction TB
        E1["Evaluate<br/><small>Track retrieval and answer quality</small>"]
    end

    Ingest --> Retrieve
    Retrieve --> Answer
    Answer --> Evaluate
    style Ingest fill:#e1f5fe
    style Retrieve fill:#f3e5f5
    style Answer fill:#e8f5e8
    style Evaluate fill:#fff3e0
`;

	const ingestionDiagram = `
flowchart TB
    L0["L0: Download<br/><small>HTML and PDF sources</small>"]
    L1["L1: Parse<br/><small>HTML to markdown, PDF extraction</small>"]
    L2["L2: Classify<br/><small>Block classification<br/>(heading/paragraph/list/table)</small>"]
    L3["L3: Chunk<br/><small>Structured chunking with quality scoring</small>"]
    L4["L4: Reference<br/><small>Lab reference ranges enrichment</small>"]
    L5["L5: Index<br/><small>Embeddings, BM25, optional HyPE prompts</small>"]
    L6["L6: Ready<br/><small>Runtime retrieval index</small>"]

    L0 --> L1
    L1 --> L2
    L2 --> L3
    L3 --> L4
    L4 --> L5
    L5 --> L6

    style L0 fill:#e1f5fe
    style L1 fill:#e1f5fe
    style L2 fill:#bbdefb
    style L3 fill:#c8e6c9
    style L4 fill:#c8e6c9
    style L5 fill:#f3e5f5
    style L6 fill:#fff9c4
`;

	const queryDiagram = `
flowchart TB
    Q["Query<br/><small>User question + session context</small>"]
    Intake["Intake Check<br/><small>Extract and fill health parameters</small>"]
    Expand["Expansion<br/><small>Optional HyDE and query enrichment</small>"]
    Search["Search<br/><small>Hybrid RRF + MMR diversification</small>"]
    Rerank["Rerank<br/><small>Cross-encoder reranking (+NDCG)</small>"]
    Gen["Generation<br/><small>Source-grounded answer</small>"]

    Q --> Intake
    Intake --> Expand
    Expand --> Search
    Search --> Rerank
    Rerank --> Gen

    style Q fill:#e3f2fd
    style Intake fill:#e8f5e8
    style Expand fill:#f3e5f5
    style Search fill:#e1f5fe
    style Rerank fill:#fff9c4
    style Gen fill:#fce4ec
`;

	const evaluationDiagram = `
flowchart TB
    DS["Dataset<br/><small>Golden queries and synthetic prompts</small>"]
    RET["Retrieval Eval<br/><small>Hit rate, MRR, nDCG, latency</small>"]
    QUAL["Answer Eval<br/><small>DeepEval answer judgment</small>"]
    THR["Thresholds<br/><small>Check pass/fail gates</small>"]
    REP["Reporting<br/><small>Summary and tracking outputs</small>"]

    DS --> RET
    RET --> QUAL
    QUAL --> THR
    THR --> REP

    style DS fill:#e1f5fe
    style RET fill:#c8e6c9
    style QUAL fill:#f3e5f5
    style THR fill:#fff9c4
    style REP fill:#fff3e0
`;

	const keyDefaults = [
		['Chunk size', '512 tokens'],
		['Overlap', '64 tokens'],
		['Search mode', 'RRF hybrid'],
		['MMR lambda', '0.75'],
		['Embedding model', 'Qwen-based embeddings']
	];

	const ingestionHighlights = [
		'HTML and PDF ingestion converge at the Classify stage for structured block detection.',
		'Chunk quality scoring removes obviously noisy or low-confidence content.',
		'HyPE moves query-like reasoning to ingest time by storing hypothetical questions per chunk.',
		'Reference data (lab ranges) enriches chunks before indexing.'
	];

	const queryHighlights = [
		'Medical intake extracts missing health parameters before answer generation.',
		'HyDE operates at query time; HyPE operates at ingest time.',
		'MMR limits redundancy so the answer sees a broader evidence set.',
		'Cross-encoder reranking is the only feature that improved NDCG (+0.039) on the 54-query benchmark, at +248ms latency cost.'
	];

	const evaluationHighlights = [
		'Retrieval metrics focus on whether the right evidence is surfaced.',
		'DeepEval metrics focus on whether the final answer is faithful and useful.',
		'Threshold checks turn metrics into simple pass/fail signals for regression tracking.',
		'Feature ablation: cross-encoder reranking is the only tested technique to show NDCG gain (+0.039) on 54-query benchmark.'
	];
</script>

<svelte:head>
	<title>Pipeline Docs</title>
</svelte:head>

<AppShell current="/docs/pipeline">
	<div class="page-header">
		<p class="eyebrow">Architecture notes</p>
		<h1>Pipeline architecture</h1>
		<p class="subtitle">A concise view of how ingestion, retrieval, and evaluation fit together.</p>
	</div>

	<div class="tabs-wrap">
		<TabNav tabs={tabs} activeTab={activeTab} onchange={(id) => (activeTab = id as TabId)} label="Pipeline documentation sections" />
	</div>

	{#if activeTab === 'overview'}
		<div class="panel" id="panel-overview" role="tabpanel" aria-labelledby="tab-overview">
			<div class="panel-head">
				<div>
					<h2>System overview</h2>
					<p>The app is a document pipeline first, a retrieval system second, and a medical answer UI on top.</p>
				</div>
			</div>
			<MermaidDiagram code={overviewDiagram} />
			<div class="facts-grid">
				{#each keyDefaults as [label, value]}
					<div class="fact-card">
						<span>{label}</span>
						<strong>{value}</strong>
					</div>
				{/each}
			</div>
		</div>
	{:else if activeTab === 'ingestion'}
		<div class="panel" id="panel-ingestion" role="tabpanel" aria-labelledby="tab-ingestion">
			<div class="panel-head">
				<div>
					<h2>Ingestion</h2>
					<p>Turn mixed-source medical content into an index that is consistent enough for retrieval and evaluation.</p>
				</div>
			</div>
			<MermaidDiagram code={ingestionDiagram} />
			<ul class="compact-list">
				{#each ingestionHighlights as item}
					<li>{item}</li>
				{/each}
			</ul>
			<div class="note-grid">
				<article>
					<h3>PDF extraction</h3>
					<p>Primary extraction is lightweight, with fallback extraction for complex layouts or low-confidence pages.</p>
				</article>
				<article>
					<h3>Block classification</h3>
					<p>Classifies content into heading, paragraph, list, and table blocks for structured chunking.</p>
				</article>
				<article>
					<h3>Chunking</h3>
					<p>Structured chunking favors clean section boundaries and table integrity over brute-force splitting.</p>
				</article>
				<article>
					<h3>HyPE</h3>
					<p>Stores hypothetical questions at ingest time so some recall gains happen before a user even asks a query.</p>
				</article>
			</div>
		</div>
	{:else if activeTab === 'query'}
		<div class="panel" id="panel-query" role="tabpanel" aria-labelledby="tab-query">
			<div class="panel-head">
				<div>
					<h2>Query / RAG</h2>
					<p>The answer path prioritizes context gathering before generation.</p>
				</div>
			</div>
			<MermaidDiagram code={queryDiagram} />
			<ul class="compact-list">
				{#each queryHighlights as item}
					<li>{item}</li>
				{/each}
			</ul>
			<div class="note-grid">
				<article>
					<h3>HyDE vs HyPE</h3>
					<p>HyDE creates hypothetical answers at query time. HyPE creates hypothetical questions at ingest time.</p>
				</article>
				<article>
					<h3>Medical intake</h3>
					<p>The intake layer tracks missing or conflicting patient context before the assistant answers.</p>
				</article>
				<article>
					<h3>MMR Diversification</h3>
					<p>MMR overfetches candidates, then reduces redundancy to avoid narrow source coverage.</p>
				</article>
				<article>
					<h3>Cross-encoder Reranking</h3>
					<p>Optional post-search step. Only feature with measurable NDCG gain (+0.039). Adds ~248ms latency. Enabled via <code>enable_reranking</code>.</p>
				</article>
			</div>
		</div>
	{:else if activeTab === 'evaluation'}
		<div class="panel" id="panel-evaluation" role="tabpanel" aria-labelledby="tab-evaluation">
			<div class="panel-head">
				<div>
					<h2>Evaluation</h2>
					<p>Evaluation is the backstop that turns pipeline quality into visible regressions or passes.</p>
				</div>
			</div>
			<MermaidDiagram code={evaluationDiagram} />
			<ul class="compact-list">
				{#each evaluationHighlights as item}
					<li>{item}</li>
				{/each}
			</ul>
			<div class="note-grid">
				<article>
					<h3>Retrieval metrics</h3>
					<p>Hit rate, MRR, and nDCG check whether the system surfaces the right evidence quickly enough.</p>
				</article>
				<article>
					<h3>Answer quality</h3>
					<p>DeepEval metrics cover faithfulness, clarity, clinical relevance, and completeness.</p>
				</article>
				<article>
					<h3>Thresholds</h3>
					<p>Threshold checks are the fastest way to spot whether a run is healthy without reading every metric.</p>
				</article>
				<article>
					<h3>Ablation studies</h3>
					<p>Feature ablation runs (keyword, HyPE/HyDE, reranking) identify which techniques improve retrieval. See <code>scripts/run_feature_ablations.py</code>.</p>
				</article>
			</div>
		</div>
	{:else if activeTab === 'features'}
		<div class="panel" id="panel-features" role="tabpanel" aria-labelledby="tab-features">
			<div class="panel-head">
				<div>
					<h2>Feature Toggles</h2>
					<p>Each feature can be enabled independently. The Settings page shows which are currently active.</p>
				</div>
			</div>
			<div class="note-grid">
				<article>
					<h3>Retrieval Strategy</h3>
					<p><strong>rrf_hybrid</strong> (default) combines semantic and BM25 keyword search via Reciprocal Rank Fusion. <strong>semantic_only</strong> uses embedding similarity alone. <strong>bm25_only</strong> uses traditional keyword matching.</p>
				</article>
				<article>
					<h3>Reranking (Cross-Encoder)</h3>
					<p>Post-retrieval step that re-scores candidates with a cross-encoder model (BAAI/bge-reranker-base). The only tested feature with a measurable NDCG gain (+0.039) on the 54-query benchmark, at ~248ms latency cost. Controlled by <code>enable_reranking</code>.</p>
				</article>
				<article>
					<h3>MMR Diversification</h3>
					<p>Over-fetches candidates then selects a diverse subset using Maximal Marginal Relevance. Reduces redundant chunks from the same source. Controlled by <code>enable_diversification</code> and tuned with <code>mmr_lambda</code>.</p>
				</article>
				<article>
					<h3>HyDE (Hypothetical Document Embeddings)</h3>
					<p>Query-time technique: the LLM generates a hypothetical answer, which is embedded and used as the search query. Can improve recall for short or ambiguous queries. Controlled by <code>enable_hyde</code>.</p>
				</article>
				<article>
					<h3>HyPE (Hypothetical Prompt Embeddings)</h3>
					<p>Ingest-time technique: for each chunk, the LLM generates hypothetical questions a user might ask. These questions are embedded alongside the chunk, so some recall gains happen before a query arrives. Controlled by <code>enable_hype</code> and <code>hype_sample_rate</code>.</p>
				</article>
				<article>
					<h3>Query Understanding</h3>
					<p>Classifies the query type and routes it through specialized processing. The winning variant in ablation testing: improved NDCG@5 by +6.3% over baseline. Controlled by <code>enable_query_understanding</code>.</p>
				</article>
				<article>
					<h3>Medical Expansion</h3>
					<p>Expands queries with medical terminology synonyms and acronyms before retrieval. Requires a configured provider (currently noop by default). Controlled by <code>medical_expansion_enabled</code>.</p>
				</article>
				<article>
					<h3>Keyword Extraction &amp; Summaries</h3>
					<p>At ingest time, LLM-extracted keywords and chunk summaries can be stored to improve BM25 matching and context previews. Controlled by <code>enable_keyword_extraction</code> and <code>enable_chunk_summaries</code>.</p>
				</article>
			</div>
		</div>
	{:else}
		<div class="panel" id="panel-troubleshooting" role="tabpanel" aria-labelledby="tab-troubleshooting">
			<div class="panel-head">
				<div>
					<h2>Troubleshooting</h2>
					<p>Common issues and their resolution paths.</p>
				</div>
			</div>
			<ul class="compact-list">
				<li><strong>Backend is reachable, but the runtime index is not ready yet.</strong> — The vector store has not finished loading embeddings into memory. Wait a minute and refresh, or check that <code>data/chroma/</code> exists.</li>
				<li><strong>Answer quality is low.</strong> — Check the evaluation dashboard for retrieval metrics. If hit_rate_at_k is below 0.6, the retrieval layer may need tuning (chunk size, top_k, or search mode). Review the L6 quality tab for per-metric DeepEval scores.</li>
				<li><strong>Latency is high.</strong> — Reranking adds ~248ms. HyDE adds an LLM call per query. Check the pipeline trace in the chat interface for per-step timing breakdowns.</li>
				<li><strong>Sources are duplicated.</strong> — Enable diversification (<code>enable_diversification</code>) and tune <code>mmr_lambda</code>. Check the Advanced tab for duplicate_source_ratio_mean.</li>
				<li><strong>Evaluation shows "degraded" status.</strong> — Some DeepEval metric evaluations failed (check metric_error_rate). This is often a timeout or API rate limit issue, not a pipeline bug.</li>
			</ul>
		</div>
	{/if}
</AppShell>

<style>
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
	}

	.subtitle {
		max-width: 42rem;
		color: var(--muted-color);
	}

	.tabs-wrap,
	.panel {
		padding: 1rem;
		border: 1px solid var(--border-color);
		border-radius: 18px;
		background: white;
	}

	.panel {
		display: flex;
		flex-direction: column;
		gap: 1rem;
	}

	.panel-head h2 {
		margin: 0;
		font-size: 1.05rem;
	}

	.panel-head p {
		margin-top: 0.35rem;
		color: var(--muted-color);
	}

	.facts-grid,
	.note-grid {
		display: grid;
		grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
		gap: 0.9rem;
	}

	.fact-card,
	.note-grid article {
		padding: 1rem;
		border: 1px solid var(--border-color);
		border-radius: 14px;
		background: var(--surface-subtle);
	}

	.fact-card span {
		display: block;
		font-size: 0.82rem;
		color: var(--muted-color);
	}

	.fact-card strong {
		display: block;
		margin-top: 0.3rem;
		font-size: 1rem;
	}

	.compact-list {
		padding-left: 1.1rem;
		color: var(--text-color);
	}

	.compact-list li + li {
		margin-top: 0.45rem;
	}

	.note-grid h3 {
		margin: 0;
		font-size: 0.95rem;
	}

	.note-grid p {
		margin-top: 0.35rem;
		color: var(--muted-color);
		font-size: 0.92rem;
	}
</style>
