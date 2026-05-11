# Ingestion Pipeline

Walk through the full ingestion DAG: download, extract, chunk, enrich, embed, and index

<div style="margin: 0 -0.8rem">
  <iframe src="https://minghao.github.io/qna_medical_referenced/notebooks/html/03_ingestion_pipeline.html"
    style="width:100%; height:600px; border:1px solid var(--md-default-fg-color--lightest); border-radius:4px;"
    loading="lazy"></iframe>
</div>

## Run Locally

```bash
uv sync
uv run quarto render notebooks/03_ingestion_pipeline.qmd
```
