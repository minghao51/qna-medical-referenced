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

## Web sources (`web_sources`, 58 pages)

Clinical guideline content from Singapore government health sites, plus NICE
(UK) for a small set of cross-referenced topics:

| Domain | Pages | Content |
|---|---|---|
| `www.ace-hta.gov.sg` | 36 | ACE (Agency for Care Effectiveness) appraisal-published clinical guidance — the core corpus (osteoporosis, depression, anxiety, COPD, diabetes, VTE, lipids, atopic dermatitis, heart failure, AF, CKD, asthma, obesity, allergic rhinitis, dementia, …) |
| `www.healthhub.sg` | 10 | HealthHub patient-facing articles |
| `hpp.moh.gov.sg` | 7 | Ministry of Health healthcare professionals portal |
| `www.nice.org.uk` | 4 | NICE guidelines cross-referenced for selected topics |
| `www.moh.gov.sg` | 1 | MOH circulars/statements |

## PDF sources (`pdf_sources`, 13 files)

PDF editions of ACE and Diabetes Society of Singapore guidelines hosted on
`isomer-user-content.by.gov.sg` and `www.diabetes.org.sg`, plus HealthHub PDF
articles served via `ch-api.healthhub.sg`; ingested through the PDF extraction
path (`src/ingestion/steps/load_pdfs.py`).

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
