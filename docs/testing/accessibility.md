# Accessibility audit

**Status:** offline browser audit complete for the private-lab UI. No authenticated release claim.

## Automated WCAG audit

- Engine: axe-core **4.10.2**, injected temporarily from a CDN into Playwright; it is **not** a repository dependency.
- Rules: `wcag2a`, `wcag2aa`, `wcag21a`, `wcag21aa`, `wcag22aa`.
- Static routes at 1440 px: `/`, `/ask`, `/research/evaluations`, `/research/features`, `/research/datasets`, `/research/datasets/golden-all`, `/research/methodology`, `/evidence`, `/evidence/[id]`, `/eval`, `/eval/ablation`, `/experiments`, `/health`, `/settings`, `/help`, `/docs/pipeline`.
- Dynamic states: populated Ask, pipeline modal open, mobile menu open, and 390 px versions of root, Ask, evaluations, evidence and dataset detail.
- Result after fixes: **0 violations** in all audited states.

Fixed during the audit:

- Removed dynamic `aria-controls` from tabs whose panels are not mounted; panels remain associated through `aria-labelledby`.
- Darkened health success text and pipeline node/description/document badge colours to meet 4.5:1.
- Gave repeated evidence Inspect links unique accessible names including source, PDF page and result ordinal.
- Gave Ask copy/retry actions turn-aware accessible names.
- Named health runtime disclosures by setting instead of exposing a raw JSON prefix as the accessible name.

## Accessibility tree and keyboard review

- Chromium accessibility tree was inspected for root, evaluations, datasets, evidence, health, Ask and the pipeline modal.
- One `<main>`, one `<h1>` on reviewed routes, labelled navigation, skip link first in tab order.
- Evaluation tabs expose `role=tab`, `aria-selected`, roving tabindex and ArrowLeft/ArrowRight/Home/End behaviour.
- Pipeline inspector exposes a named `dialog` (`Pipeline Details`), contained focus, Escape dismissal, background inertness, scroll lock and focus restoration.
- Evidence Inspect links have unique names; Ask copy/retry buttons identify their turn.
- Mobile Menu exposes `aria-expanded`, closes on Escape and restores focus.

## Limits

- No NVDA, JAWS or VoiceOver session was available; this is a Chromium accessibility-tree/keyboard audit, not a physical screen-reader sign-off.
- Chart.js canvases retain textual summaries/table alternatives where implemented, but generated canvas internals are not inspected by axe.
- Automated rules cannot prove cognitive load, reading order in every zoom state, or clinical-language comprehension.
