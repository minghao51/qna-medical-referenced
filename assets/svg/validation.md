# Validation record
## Checks performed
- **19 / 19 SVGs parsed** with Python ElementTree. Checked explicit viewBox, unique IDs and absence of script, raster image and foreignObject elements. Browser opening also exercised SVG/XML rendering.
- **19 / 19 rendered in Chromium** through the existing frontend Playwright installation, at each SVG's own viewBox width/height. Sol reviewed all full-size renders and contact sheets. Tight mobile heading/button padding and sidebar title overflow were corrected, then affected assets rerendered. The research refinement added six screens and replaced workspace/mobile/IA; every new or changed layout was rendered and visually inspected at its intended viewport.
- Browser `getBBox()` checks across every text node found **zero off-canvas text nodes and zero pairwise text overlaps** in the final render set. These checks supplement, not replace, visual review; they do not guarantee every future localized string fits a component.
- SVG chart arithmetic checked: 1,306 + 597 + 460 + 110 = 2,473; .7205 − .6813 = .0392; 485 − 236.5 = 248.5 ms; 485 / 236.5 rounds to 2.05×. Synthetic trace: 1,800 − 300 − 1,400 = 100 ms (arithmetic residual only).
- Refinement arithmetic rechecked from the actual local JSON: six baseline metrics ×57 expected =342 slots; successful counts total268; failed counts total74; 74/342 rounds21.6%. Each metric's count+errors=57. All57 split17+23+17=57; confidence43+14=57; categories45+7+5=57. Exact query overlap54 between Expanded54 and All57. Archived feature change .7008913797−.6596215032 rounds+.0413, relative+6.3%.
- Zero-baseline chart dimensions reviewed against their displayed scales: corpus max 1,500 chunks; research quality 0–1; research latency 0–800 ms; synthetic duration scale 0–1,800 ms. Coverage bars in the research refinement use 57 expected slots as their full domain; dataset split bars use 0–25 questions. Repeated coverage bars use the same domain and successful/failed meaning. The previous mobile corpus composition was replaced by a research-first entry.
- Cross-screen corpus counts, source/page/chunk identity, benchmark values and synthetic turn 02 constants checked against the data map.
- Local Markdown asset links checked by resolving relative destinations. Source code/data references were inspected during investigation. External design-reference access and redirects are qualified in design-rationale.md; not every external URL was health-checked.
- Feature mapping reviewed: all visual layouts are proposed; real underlying APIs versus additive search/facets/routes/storage/call instrumentation are separated in screen-data-map.md.
- Existing frontend `npm --prefix frontend run check` completed with **0 errors / 0 warnings**.

## Text contrast calculations (WCAG relative luminance)
| Foreground / background | Ratio |
|---|---:|
| Ink #182D32 / paper #F7F4ED | 13.09:1 |
| Secondary #506469 / paper | 5.68:1 |
| Secondary / white | 6.24:1 |
| Teal #006B61 / tint #E5F1EA | 5.53:1 |
| Rust #B34322 / warm #FBECE2 | 4.86:1 |
| White / teal | 6.41:1 |
| White / ink | 14.38:1 |
| Pale green #B5DACE / ink | 9.51:1 |
| Light text #D6E0DC / ink | 10.65:1 |
| Secondary / disabled #E6E7E2 | 5.02:1 |

These checked text pairs exceed 4.5:1. Divider strokes intentionally have lower contrast and must not be the sole indicator of interactive boundaries, focus or selection. Actual implementation needs independent 3:1 non-text/focus testing, keyboard review and automated accessibility checks.

## Implementation-package checks
The next phase adds documentation only: implementation-specification.md, implementation-map.md, implementation-plan.md, next-agent-start.md and implementation-review.md. Existing code anchors, actual route/type/test paths, Docker fixture omission and current Playwright4173 default were inspected. New file/API references are explicitly proposed, not represented as implemented.

Historical planning baseline: `bash scripts/check_backend.sh fast tests/unit/app/test_evaluation_routes.py tests/unit/evals/test_history_comparability.py tests/unit/app/test_new_routes.py -q` gave **58 passed in2.52s** before P01. P01 later raised that focused set to65; see its report. Neither result proves future catalog/UI acceptance. No provider calls, fixture generation or deployment were executed. Relative links in the documentation package were checked after drafting.

## P01 implementation validation
P01 (not a design-only change) was implemented and verified separately:
- focused backend65 passed; full offline backend2322 passed/1 optional skip; static lint passed.
- frontend svelte-check0 errors and build passed; new pure/browser specs11 passed.
- full frontend suite58 passed/9 skipped/2 failed, both inherited untouched chat/pipeline expectations and detailed in the P01 report.
- Actual archived report read through the route yielded digest `0e47dc76…` and baseline faithfulness15 measured/42 errors; no live providers or data mutation.
See `docs/plans/20261101-p01-archive-identity-and-metric-semantics.md`.

## Execution environment and limitations
- Started the existing Vite development server, received HTTP 200 and captured the current empty-chat screen in Chromium. Port 8000 backend health was unreachable. No provider-generated answer or live ingestion was attempted.
- Chromium initially failed due to missing libnspr4, NSS and audio libraries. Required distribution packages were downloaded and extracted **under /tmp only**, then passed through LD_LIBRARY_PATH; no repository dependencies or production environment were changed.
- Render PNGs and investigation logs are temporary review artifacts, not deliverables or embedded SVG content. The committed deliverables remain editable vector assets and Markdown.
- Exact requested model versions were not listed. Codex's explicitly announced gpt-5.6-luna fallback completed frontend investigation; OpenCode's listed deepseek-v4-flash fallback failed twice. Sol directly covered backend/data analysis.
- The refinement used an additional read-only Codex gpt-5.6-luna research/design review; Sol verified raw fixture/report counts and existing comparability/identity guards. No model/version substitution is silently implied.
- No authenticated DeepSeek Harness UI session, original FiveThirtyEight forecast interactive, full production build, complete test suite, live backend flow, clinical correctness study, screen-reader session or dynamic accessibility conformance test was completed. Static designs cannot prove interactive accessibility.
- Unknown source freshness, frozen/intermediate lineage, deployment access policy and durable trace retention remain explicit planning gates.
