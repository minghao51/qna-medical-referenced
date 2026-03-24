<script lang="ts">
	import AppShell from '$lib/components/AppShell.svelte';
	import DagFlowDiagram from '$lib/components/DagFlowDiagram.svelte';
	import TabNav from '$lib/components/TabNav.svelte';
	import type { DagConnection, DagStage } from '$lib/components/DagFlowDiagram.svelte';

	type TabId = 'overview' | 'ingestion' | 'query' | 'evaluation';

	const tabs: Array<{ id: TabId; label: string }> = [
		{ id: 'overview', label: 'Overview' },
		{ id: 'ingestion', label: 'Ingestion' },
		{ id: 'query', label: 'Query / RAG' },
		{ id: 'evaluation', label: 'Evaluation' }
	];

	let activeTab: TabId = $state('overview');

	const overviewStages: DagStage[] = [
		{ id: 'ingest', title: 'Ingest', description: 'Download, parse, chunk, index' },
		{ id: 'retrieve', title: 'Retrieve', description: 'Expand query, hybrid search, rerank' },
		{ id: 'answer', title: 'Answer', description: 'Build context and generate response' },
		{ id: 'evaluate', title: 'Evaluate', description: 'Track retrieval and answer quality' }
	];

	const overviewConnections: DagConnection[] = [
		{ from: 'ingest', to: 'retrieve' },
		{ from: 'retrieve', to: 'answer' },
		{ from: 'answer', to: 'evaluate' }
	];

	const ingestionStages: DagStage[] = [
		{ id: 'l0', title: 'Download', description: 'HTML and PDF sources' },
		{ id: 'l1', title: 'Parse', description: 'HTML to markdown, PDF extraction' },
		{ id: 'l3', title: 'Chunk', description: 'Structured chunking with quality scoring' },
		{ id: 'l5', title: 'Index', description: 'Embeddings plus optional HyPE prompts' },
		{ id: 'l6', title: 'Ready', description: 'Runtime retrieval index' }
	];

	const ingestionConnections: DagConnection[] = [
		{ from: 'l0', to: 'l1' },
		{ from: 'l1', to: 'l3' },
		{ from: 'l3', to: 'l5' },
		{ from: 'l5', to: 'l6' }
	];

	const queryStages: DagStage[] = [
		{ id: 'query', title: 'User Query', description: 'Question plus session context' },
		{ id: 'intake', title: 'Intake Check', description: 'Extract and fill health parameters' },
		{ id: 'expand', title: 'Expansion', description: 'Optional HyDE and query enrichment' },
		{ id: 'retrieve', title: 'Retrieval', description: 'Hybrid search plus MMR reranking' },
		{ id: 'generate', title: 'Generation', description: 'Source-grounded answer' }
	];

	const queryConnections: DagConnection[] = [
		{ from: 'query', to: 'intake' },
		{ from: 'intake', to: 'expand' },
		{ from: 'expand', to: 'retrieve' },
		{ from: 'retrieve', to: 'generate' }
	];

	const evaluationStages: DagStage[] = [
		{ id: 'dataset', title: 'Dataset', description: 'Golden queries and synthetic prompts' },
		{ id: 'retrieval', title: 'Retrieval Eval', description: 'Hit rate, MRR, nDCG, latency' },
		{ id: 'quality', title: 'Answer Eval', description: 'DeepEval answer judgment' },
		{ id: 'thresholds', title: 'Thresholds', description: 'Check pass/fail gates' },
		{ id: 'reporting', title: 'Reporting', description: 'Summary and tracking outputs' }
	];

	const evaluationConnections: DagConnection[] = [
		{ from: 'dataset', to: 'retrieval' },
		{ from: 'retrieval', to: 'quality' },
		{ from: 'quality', to: 'thresholds' },
		{ from: 'thresholds', to: 'reporting' }
	];

	const keyDefaults = [
		['Chunk size', '512 tokens'],
		['Overlap', '64 tokens'],
		['Search mode', 'RRF hybrid'],
		['MMR lambda', '0.75'],
		['Embedding model', 'Qwen-based embeddings']
	];

	const ingestionHighlights = [
		'HTML and PDF ingestion converge into one structured chunking stage.',
		'Chunk quality scoring removes obviously noisy or low-confidence content.',
		'HyPE moves some query-like reasoning to ingest time by storing hypothetical questions per chunk.'
	];

	const queryHighlights = [
		'Medical intake extracts missing health parameters before answer generation.',
		'HyDE operates at query time; HyPE operates at ingest time.',
		'MMR limits redundancy so the answer sees a broader evidence set.'
	];

	const evaluationHighlights = [
		'Retrieval metrics focus on whether the right evidence is surfaced.',
		'DeepEval metrics focus on whether the final answer is faithful and useful.',
		'Threshold checks turn metrics into simple pass/fail signals for regression tracking.'
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
			<DagFlowDiagram title="" stages={overviewStages} connections={overviewConnections} layout="vertical" />
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
			<DagFlowDiagram title="" stages={ingestionStages} connections={ingestionConnections} />
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
			<DagFlowDiagram title="" stages={queryStages} connections={queryConnections} />
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
					<h3>Diversification</h3>
					<p>MMR overfetches candidates, then reduces redundancy to avoid narrow source coverage.</p>
				</article>
			</div>
		</div>
	{:else}
		<div class="panel" id="panel-evaluation" role="tabpanel" aria-labelledby="tab-evaluation">
			<div class="panel-head">
				<div>
					<h2>Evaluation</h2>
					<p>Evaluation is the backstop that turns pipeline quality into visible regressions or passes.</p>
				</div>
			</div>
			<DagFlowDiagram title="" stages={evaluationStages} connections={evaluationConnections} />
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
			</div>
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
