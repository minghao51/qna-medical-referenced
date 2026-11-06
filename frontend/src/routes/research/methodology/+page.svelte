<script lang="ts">
	import AppShell from '$lib/components/AppShell.svelte';
	import ResearchNav from '$lib/components/ResearchNav.svelte';
</script>

<svelte:head>
	<title>Methodology · Fieldnote</title>
</svelte:head>

<AppShell current="/research/methodology">
	<div class="methodology">
		<header>
			<p class="eyebrow">Methodology / measurement and identity</p>
			<h1>How to read these measurements.</h1>
			<p class="lede">
				The workspace separates artifact identity, measurement coverage, metric families and
				comparison eligibility. A number is not a verdict, and a missing value is not zero.
			</p>
		</header>

		<ResearchNav current="/research/methodology" />

		<nav class="toc" aria-label="Methodology sections">
			<a href="#units">Units</a>
			<a href="#coverage">Coverage</a>
			<a href="#families">Metric families</a>
			<a href="#identity">Identity</a>
			<a href="#comparison">Comparison</a>
			<a href="#qa">Q&amp;A evidence</a>
		</nav>

		<section id="units" aria-labelledby="units-title">
			<p class="section-index">01</p>
			<h2 id="units-title">Slots, queries and cases are different units.</h2>
			<p>
				The archived answer-quality report declares six answer metrics per query. With 57
				queries, that is 342 expected metric slots. That does not mean 342 questions, 342
				patient cases or 342 independent clinical judgments.
			</p>
			<p>
				Dataset inventories use different units again: the frozen index is measured in chunks,
				query fixtures in questions, conversation fixtures in conversations and the review set
				in cases. They are displayed separately and never summed into one evidence total.
			</p>
		</section>

		<section id="coverage" aria-labelledby="coverage-title">
			<p class="section-index">02</p>
			<h2 id="coverage-title">Read coverage before the mean.</h2>
			<p>
				A mean summarizes successful measurements only. It is not a score for failed slots and
				not a complete result when some measurements are absent. Each metric row shows its mean,
				measured and expected slots, failed slots and a coverage state.
			</p>
			<ul>
				<li><strong>Complete</strong> — measured slots equal expected slots with no failures.</li>
				<li><strong>Partial</strong> — some expected measurements succeeded and others failed or are unaccounted for.</li>
				<li><strong>Not recorded</strong> — expected or measured counts were not recorded; the mean is not treated as complete.</li>
				<li><strong>Inconsistent</strong> — counts or values conflict; they stay visible instead of being repaired.</li>
			</ul>
			<p>
				For the recognized legacy archive, the expected basis is one answer-metric slot per
				declared query. Failed metric evaluations are not converted into failed cases. Raw
				per-case errors and judge reasons are not available from the aggregate report and are
				not invented.
			</p>
		</section>

		<section id="families" aria-labelledby="families-title">
			<p class="section-index">03</p>
			<h2 id="families-title">Metric families have different meanings.</h2>
			<dl>
				<div>
					<dt>Answer judgments</dt>
					<dd>
						Judge-scored answer metrics such as factual accuracy, completeness, clinical
						relevance, clarity, answer relevancy and faithfulness. The judge identity is not
						verified by the archive, and these names are not evidence of clinical suitability.
					</dd>
				</div>
				<div>
					<dt>Ranking diagnostics</dt>
					<dd>
						Legacy retrieval fields such as nDCG, MRR, hit rate, precision and recall. They
						describe retrieval behaviour, not the correctness of a medical answer.
					</dd>
				</div>
				<div>
					<dt>Reviewed evidence</dt>
					<dd>
						Qrels-style evidence metrics are a separate family from legacy diagnostics. A
						manifest can declare review status, but that declaration is not authenticated
						reviewer identity or clinical endorsement.
					</dd>
				</div>
				<div>
					<dt>Latency and processing</dt>
					<dd>
						Milliseconds and error rates are lower-is-better. Counts are not percentages, and
						source entries are not unique publications. There is no universal
						larger-is-better rule.
					</dd>
				</div>
			</dl>
		</section>

		<section id="identity" aria-labelledby="identity-title">
			<p class="section-index">04</p>
			<h2 id="identity-title">Archive identity is a revision, not a historical dataset claim.</h2>
			<p>
				A report is identified by its validated report ID plus the SHA-256 of the exact bytes
				read for this request. That digest fingerprints the current file; it does not prove that
				historical case rows, dataset labels or index bytes match today's fixtures.
			</p>
			<p>
				The known config/report association is explicit and declared. It is not proof of the
				effective runtime settings. The archived winner is retained as historical data and is
				not current eligibility.
			</p>
			<div class="callout">
				<strong>D11 identity</strong>
				<p>
					The frozen index has a recorded snapshot identity in the review manifest, but the
					catalog also reports a current inventory reference. Neither is a publication count or
					a live freshness guarantee.
				</p>
			</div>
		</section>

		<section id="comparison" aria-labelledby="comparison-title">
			<p class="section-index">05</p>
			<h2 id="comparison-title">Two reports are not automatically one experiment.</h2>
			<p>
				The current API returns <code>comparable=false</code> and null cross-run aggregates.
				Matching formats, row counts, metric names or an old winner label do not establish a
				comparison cohort. The evaluation workspace therefore disables aggregate trends and
				winner promotion.
			</p>
			<p>
				A future verified cohort would need explicit evidence for dataset bytes and labels,
				split, run family, measurement contract, effective settings and index identity. Identity
				matching alone would still not prove clinical validity or reviewer qualification.
			</p>
		</section>

		<section id="qa" aria-labelledby="qa-title">
			<p class="section-index">06</p>
			<h2 id="qa-title">Q&amp;A evidence is recorded, not reconstructed.</h2>
			<p>
				The workbench shows sources and a pipeline trace only when the backend actually returned
				them. Reloading history does not reconstruct unavailable sources or traces. Retrieval
				step intervals describe recorded work; placeholder zero timings are not measurements, and
				no provider-call tree, private reasoning, exact token cost or medical confidence is
				inferred.
			</p>
			<p>
				Questions, answers and prompts are not placed in URLs. Conversation history stays
				cookie-bound; there is no saved-conversation library or durable trace store.
			</p>
		</section>

		<section class="links" aria-labelledby="links-title">
			<h2 id="links-title">Related views</h2>
			<div class="action-links">
				<a href="/research/evaluations">Evaluation coverage →</a>
				<a href="/research/features">Feature evidence →</a>
				<a href="/documents">Indexed evidence →</a>
				<a href="/eval?tab=quality">Legacy L0–L6 diagnostics →</a>
				<a href="/docs/pipeline">Pipeline documentation →</a>
				<a href="/help">Help →</a>
			</div>
		</section>
	</div>
</AppShell>

<style>
	.methodology {
		display: flex;
		flex-direction: column;
		gap: 1.5rem;
		max-width: 760px;
	}

	.eyebrow {
		margin: 0 0 0.5rem;
		color: var(--muted-color);
		font-size: 0.7rem;
		font-weight: 700;
		letter-spacing: 0.14em;
		text-transform: uppercase;
	}

	h1 {
		margin: 0;
		font-size: clamp(2rem, 3.8vw, 3rem);
	}

	.lede {
		margin: 0.9rem 0 0;
		color: var(--secondary);
	}

	.toc {
		display: flex;
		flex-wrap: wrap;
		gap: 0.4rem;
		padding: 0.75rem 0;
		border-top: 1px solid var(--border-color);
		border-bottom: 1px solid var(--border-color);
	}

	.toc a {
		padding: 0.4rem 0.65rem;
		border-radius: 999px;
		color: var(--secondary);
		font-size: 0.82rem;
		font-weight: 600;
		text-decoration: none;
	}

	.toc a:hover {
		background: var(--surface-subtle);
		color: var(--ink);
	}

	section {
		padding-bottom: 1.25rem;
		border-bottom: 1px solid var(--border-color);
	}

	.section-index {
		margin: 0 0 0.3rem;
		color: var(--rust);
		font-family: var(--font-heading);
		font-size: 0.85rem;
	}

	h2 {
		margin: 0 0 0.75rem;
		font-size: 1.5rem;
	}

	section p,
	section li,
	section dd {
		color: var(--secondary);
		font-size: 0.92rem;
	}

	section p {
		margin: 0 0 0.75rem;
	}

	section ul {
		margin: 0 0 0.75rem;
		padding-left: 1.15rem;
	}

	dl {
		display: grid;
		gap: 0.9rem;
		margin: 0;
	}

	dt {
		color: var(--ink);
		font-weight: 700;
	}

	dd {
		margin: 0.2rem 0 0;
	}

	.callout {
		padding: 0.9rem 1rem;
		border-left: 3px solid var(--blue);
		background: var(--surface-subtle);
	}

	.callout p {
		margin: 0.35rem 0 0;
	}

	.links {
		border: 0;
	}

	.action-links {
		display: grid;
		grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
		gap: 0.6rem;
	}

	.action-links a {
		padding: 0.75rem;
		border: 1px solid var(--border-color);
		border-radius: 8px;
		color: var(--teal);
		font-weight: 700;
		text-decoration: none;
	}

	.action-links a:hover {
		border-color: var(--teal);
	}

	@media (max-width: 640px) {
		.methodology {
			gap: 1.1rem;
		}
	}
</style>
