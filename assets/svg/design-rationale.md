# Design rationale
## Decision
Choose a **substantial redesign within SvelteKit**, with targeted backend contract work. This is not a production rewrite authorization.

| Option | Benefit | Cost / risk | Assessment |
|---|---|---|---|
| Incremental polish | Fastest; preserves routes/components | Leaves mixed reader/operator IA, blank entry and misleading score hierarchy | Insufficient for the evidence problem |
| Substantial redesign | Reuses functioning framework, API and RAG while rebuilding hierarchy, evidence and turn inspection | New layouts, route aliases, accessible interaction work, explicit data/auth gaps | **Recommended** |
| Frontend rebuild | Freedom to change every boundary | Reimplements SSE/cookies, source normalization, safe Markdown, exports, lazy loading and tests; no observed framework blocker | Cost without demonstrated benefit |

Retain underlying ingestion, frozen index, chat/session semantics, evaluation definitions and research affordances. Migrate by vertical slices and aliases, not by changing metrics or rebuilding the corpus to fit a graphic.

## Product idea — refined after research audit
**Fieldnote: what changes actually improve this system?** A private engineering lab with an inspectable medical-reference Q&A workbench. Owner decisions D01/D02/D07/D09/D10 in `docs/plans/migration/decisions.md` take precedence over the first pass's public-reader emphasis. No public or clinical rollout is proposed.
- Central question and action rather than generic KPIs.
- A corpus composition chart answers “what can this system draw from?” It never implies population coverage.
- The readable source is primary; raw scores are secondary.
- Research views put measurement coverage, dataset identity and declared/effective features next to every score. Archived comparisons are descriptive, not eligibility or promotion evidence. No exact provider cost is invented.
- A conversation remains the main Q&A interface. Every completed turn gets its own compact evidence/status showcase and inspect action.
- “Full breakdown” means all available recorded fields, not an invented transcript of internal cognition.

## References actually researched
1. [FiveThirtyEight Our Data](https://data.fivethirtyeight.com/) — direct fetch returned the short sharing/check-our-work statement, with an incomplete-extraction warning. Adopt proximity of claims to sources and reproducibility.
2. [Science Isn't Broken — awards showcase](https://www.informationisbeautifulawards.com/showcase/1708-science-isn-t-broken) — accessible description of FiveThirtyEight's interactive explanation of p-hacking. Adopt explanatory interaction and explicit dependence on analytical choices, not decorative chart density.
3. [2020 forecast](https://projects.fivethirtyeight.com/2020-election-forecast/) — attempted direct access redirected to ABC Politics, so the original interactive was **not visually inspected**. [Forecast methodology reference](https://fivethirtyeight.com/features/how-fivethirtyeights-2020-presidential-forecast-works-and-whats-different-because-of-covid-19/) was located through search, not treated as a successfully inspected live page.
4. [DeepSeek Harness trajectory documentation](https://github.com/deepseek-ai/deepseek-harness/blob/master/packages/client/ui-trajectory/README.md) — successfully fetched the [raw README](https://raw.githubusercontent.com/deepseek-ai/deepseek-harness/master/packages/client/ui-trajectory/README.md). It describes a turn-aware event ledger, timing overview, independently folded calls/subcalls, record inspection, Input/Output/Timing/Raw and missing-data rules.
5. [Harness core event reference](https://github.com/deepseek-ai/deepseek-harness/blob/master/docs/subsystems/core.md) — raw document fetched; describes turn/step/tool events. This project's RAG trace is much less granular.

**Access qualification:** no authenticated DeepSeek Harness web session or original FiveThirtyEight interactive screenshot was inspected. Editorial styling is an original interpretation; the Harness interaction adaptation is grounded in its accessible UI documentation, not a claim of pixel-copying its live web client.

## Adopted principles, adapted to actual contracts
- Distinct editorial headings + compact sans-serif data labels; use Georgia and Arial stacks, no downloaded font files.
- Directly labeled horizontal bars with zero baselines, comparable scales, units and nearby caveats.
- Meaningful type facets (PDF / HTML / lab reference / Markdown), not arbitrary demographic filters.
- Turn-aware navigation and nested recorded-step disclosure, inspired by Harness. No arbitrary tool calls where the application has only a RetrievalStep.
- A raw inspector is a controlled expansion, not the default answer view.
- Pending state never fakes a measured duration or completed step. Current API only delivers detailed trace at the terminal event.
- Raw score values never become percentages of correctness. Domain classification is not a clinical credential.
- “Not recorded” differs from zero, skipped, failed, absent trace and stale data.
- Cite the original PDF, preserve the chunk boundary warning and distinguish excerpt from generated paraphrase.
- Semantic HTML for application structure; reusable Svelte components for stateful views; chart output only for quantitative graphics, with accessible tables.

## Visual identity
Ink #182D32, paper #F7F4ED, action teal #006B61, caution rust #B34322, reference blue #375E91. Restrained corner rounding and editorial rules replace pill-heavy dashboard chrome. Rust flags limits, never severity of a patient's condition. No FiveThirtyEight logo, palette or brand typography is copied.
Working name requires owner approval. Public naming/deployment and clinical product positioning are outside the current private-lab scope.

## Refinement findings and priorities
See [review-and-refinement.md](review-and-refinement.md). The initial design over-weighted a public explanation journey and under-weighted the repository's private research purpose. Root/mobile overview and IA are replaced accordingly; Q&A and source inspection remain intact.
- Evaluation coverage, configured-feature evidence and dataset provenance now have complete screens, not only labels in a navigation diagram.
- A real incomplete archive is more explanatory than a synthetic perfect leaderboard: baseline faithfulness .9799 on 15/57 successful measurements.
- The existing fail-closed comparability contract is a feature to expose, not friction to remove.
- Paired wins/losses, bootstrap intervals, live cost plots, automatic winner promotion and full experiment execution are deferred until real data/contracts support them.
- Avoid rebuilding Logfire's primary trace UI; retain the in-app current-session RAG inspector and authorized links to genuine recorded destinations.

## Deliberate trade-offs
The static desktop explorer includes a clearly labelled proposed search control; it must not ship enabled until server search exists. Global facet counts require an additive contract fix. Shared title mapping is display convenience, not a new publication database. Durable turn trace history and true individual provider-call instrumentation are valuable but consequential privacy/storage extensions; they are not prerequisites for a current-session inspector.
