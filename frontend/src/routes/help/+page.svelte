<script lang="ts">
	import AppShell from '$lib/components/AppShell.svelte';

	type FAQItem = { q: string; a: string };
	type Section = { title: string; items: FAQItem[] };

	const sections: Section[] = [
		{
			title: 'Getting started',
			items: [
				{
					q: 'What does this app do?',
					a: 'This is a medical health screening Q&A system powered by Retrieval-Augmented Generation (RAG). It ingests clinical guidelines, screening documents, and reference data, then uses hybrid search and an LLM to answer questions grounded in those sources.'
				},
				{
					q: 'How do I ask a question?',
					a: 'Type your question in the Chat page and press Enter or click Send. The system will retrieve relevant document chunks and generate a source-grounded answer. Toggle "Show pipeline details" to see how retrieval worked.'
				},
				{
					q: 'What data sources are used?',
					a: 'The system indexes HTML pages, PDF documents, and CSV reference data (lab reference ranges). Sources include clinical guidelines from government and medical organizations. Each answer cites its sources.'
				}
			]
		},
		{
			title: 'Understanding answers',
			items: [
				{
					q: 'What does the confidence badge mean?',
					a: 'The confidence badge summarizes the quality of the retrieval and generation pipeline. It is derived from source quality, retrieval scores, context relevance, and generation success. High confidence means the system found strong, relevant sources.'
				},
				{
					q: 'Why are some sources marked with quality indicators?',
					a: 'Sources are classified by domain type (government, education, organization, commercial) and content type. Government and education sources generally indicate higher authority for medical information.'
				},
				{
					q: 'What do the pipeline step timings mean?',
					a: 'Each query goes through retrieval (semantic + keyword search), context assembly, and LLM generation. The pipeline panel shows per-step timing so you can understand where time is spent.'
				}
			]
		},
		{
			title: 'Evaluation & experiments',
			items: [
				{
					q: 'What is the Pipeline Eval page?',
					a: 'It shows metrics from the latest evaluation run: ingestion quality (L0–L5), retrieval effectiveness (hit rate, MRR, nDCG), and answer quality (DeepEval metrics). Use it to monitor pipeline health and detect regressions.'
				},
				{
					q: 'What are ablation studies?',
					a: 'Ablation studies test different pipeline configurations (e.g., with/without reranking, different chunking strategies) in isolation to measure each feature\'s impact on retrieval quality.'
				},
				{
					q: 'What is NDCG@K?',
					a: 'Normalized Discounted Cumulative Gain at rank K. It measures how well the system ranks relevant documents at the top of results. Higher is better. A value of 1.0 means perfect ranking.'
				},
				{
					q: 'What is the Advanced tab in evaluation?',
					a: 'It shows retrieval metrics broken down by query category (anchor, adversarial, paraphrase), difficulty level, HyDE-specific metrics when enabled, and contribution analysis (semantic vs. BM25 vs. fused ranking).'
				}
			]
		},
		{
			title: 'Known limitations',
			items: [
				{
					q: 'Why do some DeepEval metrics show high error rates?',
					a: 'Answer relevancy and faithfulness metrics require multiple LLM calls per query and may time out or hit rate limits. This does not affect the pipeline itself — only the evaluation metrics. Check metric_error_rate on the Quality tab.'
				},
				{
					q: 'Can I change the retrieval strategy from the UI?',
					a: 'The Settings page is currently read-only and shows the active configuration. To change retrieval strategy, update config/settings.yaml or set environment variables and restart the backend.'
				},
				{
					q: 'How often is the vector index updated?',
					a: 'The index is loaded on application startup. To rebuild with new data, run the ingestion pipeline and restart the backend. The System Health page shows the current index status.'
				}
			]
		}
	];

	let expanded: Record<string, boolean> = $state({});

	function toggle(key: string) {
		expanded = { ...expanded, [key]: !expanded[key] };
	}

	function isExpanded(key: string): boolean {
		return expanded[key] ?? false;
	}
</script>

<svelte:head>
	<title>Help</title>
</svelte:head>

<AppShell current="/help">
	<div class="help-page">
		<div class="page-header">
			<p class="eyebrow">Support</p>
			<h1>Help & FAQ</h1>
			<p class="subtitle">Common questions about the health screening Q&A system.</p>
		</div>

		{#each sections as section}
			<section class="faq-section">
				<h2>{section.title}</h2>
				{#each section.items as item, i}
					{@const key = `${section.title}-${i}`}
					<div class="faq-item">
						<button type="button" class="faq-question" onclick={() => toggle(key)}>
							<span>{item.q}</span>
							<span class="chevron" class:open={isExpanded(key)}>▸</span>
						</button>
						{#if isExpanded(key)}
							<div class="faq-answer">
								<p>{item.a}</p>
							</div>
						{/if}
					</div>
				{/each}
			</section>
		{/each}
	</div>
</AppShell>

<style>
	.help-page {
		display: flex;
		flex-direction: column;
		gap: 1.25rem;
		max-width: 720px;
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
		color: var(--muted-color);
	}

	.faq-section {
		padding: 1rem;
		border: 1px solid var(--border-color);
		border-radius: 18px;
		background: white;
	}

	.faq-section h2 {
		font-size: 1rem;
		margin: 0 0 0.75rem;
		color: var(--muted-color);
		text-transform: uppercase;
		letter-spacing: 0.04em;
	}

	.faq-item {
		border-bottom: 1px solid var(--surface-subtle);
	}

	.faq-item:last-child {
		border-bottom: none;
	}

	.faq-question {
		display: flex;
		justify-content: space-between;
		align-items: center;
		width: 100%;
		padding: 0.75rem 0;
		background: none;
		border: none;
		cursor: pointer;
		text-align: left;
		font-size: 0.92rem;
		font-weight: 600;
		color: var(--text-color);
		gap: 0.75rem;
	}

	.faq-question:hover {
		color: #1976d2;
	}

	.chevron {
		flex-shrink: 0;
		color: var(--muted-color);
		transition: transform 0.2s;
		font-size: 0.8rem;
	}

	.chevron.open {
		transform: rotate(90deg);
	}

	.faq-answer {
		padding: 0 0 0.75rem;
	}

	.faq-answer p {
		margin: 0;
		font-size: 0.88rem;
		line-height: 1.6;
		color: var(--muted-color);
	}
</style>
