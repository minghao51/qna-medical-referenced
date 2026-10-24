# Data Sources

Inventory of the ingestion corpus. The machine-readable source of truth is
[`config/sources.yaml`](../../config/sources.yaml); this page is the human
overview. The ingestion pipeline (download → convert → parse → chunk → index)
is described in [`docs/architecture/overview.md`](../architecture/overview.md)
and `.planning/codebase/ARCHITECTURE.md`.

## Source classes

Every document carries a `source_class` (assigned by
`src/core/source_metadata.py`) that drives retrieval-time source boosting:

| `source_class` | Origin | Ingested as |
|---|---|---|
| `guideline_html` | `web_sources` in `config/sources.yaml` | downloaded HTML → Markdown conversion |
| `guideline_pdf` | `pdf_sources` in `config/sources.yaml` | downloaded PDF → structural text extraction |
| `reference_csv` | local `data/raw/LabQAR/reference_ranges.csv` | LabQAR reference ranges (lab test Q&A pairs) |

## Web sources (`web_sources`, 53 pages)

Clinical guideline content from Singapore government health sites, plus NICE
(UK) for a small set of cross-referenced topics. **2026-10-24 URL refresh:**
after the ACE site restructure and HealthHub content-API retirement, every
404 source was remapped to its live successor via the ACE sitemap or replaced
with the equivalent live HealthHub page; sources with no live successor
(heart-failure, obesity, GORD and bipolar ACGs; GLP-1 drug guidances; CUES
overview/asthma) were removed and are recorded in `config/sources.yaml`
comments.

| Domain | Pages | Content |
|---|---|---|
| `www.ace-hta.gov.sg` | 28 | ACE (Agency for Care Effectiveness) appraisal-published clinical guidance — the core corpus (osteoporosis, depression, anxiety, COPD, diabetes, VTE, lipids, atopic dermatitis, AF, CKD, asthma, allergic rhinitis, dementia, knee osteoarthritis, stroke rehabilitation, drug guidances, …) |
| `www.healthhub.sg` | 13 | HealthHub patient-facing articles |
| `hpp.moh.gov.sg` | 7 | Ministry of Health healthcare professionals portal |
| `www.nice.org.uk` | 4 | NICE guidelines cross-referenced for selected topics |
| `www.moh.gov.sg` | 1 | MOH circulars/statements (defined but not yet fetched: `download_web.main` iterates a hardcoded group list that omits the `moh` group) |

## PDF sources (`pdf_sources`, 10 files)

PDF editions of ACE and Diabetes Society of Singapore guidelines hosted on
`isomer-user-content.by.gov.sg` and `www.diabetes.org.sg`, plus HealthHub PDF
articles served via `ch-api.healthhub.sg`; ingested through the PDF extraction
path (`src/ingestion/steps/load_pdfs.py`). The two retired `ch-api`
named-slug PDFs (RDA, childhood immunisation schedule, mindSG) were replaced
by their live HealthHub article pages under `web_sources` on 2026-10-24.

## Local reference data

- `data/raw/LabQAR/reference_ranges.csv` — LabQAR lab-reference question set,
  loaded by `src/ingestion/steps/load_reference_data.py` as `reference_csv`
  documents (the retrieval-time source boost for this class is configured in
  `config/settings.yaml`).

## Notes

- Downloads are cached under `data/raw/` (see `.gitignore`); re-running
  ingestion without `--force` reuses the cache.
- The document counts above reflect `config/sources.yaml` at the time of
  writing; the yaml file is authoritative if they drift.
