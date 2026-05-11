"""Generate MkDocs stub pages from .qmd notebook frontmatter.

Reads all notebooks/*.qmd files, extracts title and description from YAML
frontmatter, and generates:
  - docs/notebooks/<slug>.md  — iframe embed + run-locally snippet
  - docs/notebooks/index.md   — notebook listing

Usage:
    uv run python scripts/generate_notebook_docs.py
"""

from __future__ import annotations

import re
from pathlib import Path

import yaml

PROJECT_ROOT = Path(__file__).resolve().parents[1]
NOTEBOOKS_DIR = PROJECT_ROOT / "notebooks"
DOCS_NOTEBOOKS_DIR = PROJECT_ROOT / "docs" / "notebooks"
MKDOCS_YML = PROJECT_ROOT / "mkdocs.yml"

IFRAME_TEMPLATE = """# {title}

{description}

<div style="margin: 0 -0.8rem">
  <iframe src="{base_path}/notebooks/html/{html_filename}"
    style="width:100%; height:600px; border:1px solid var(--md-default-fg-color--lightest); border-radius:4px;"
    loading="lazy"></iframe>
</div>

## Run Locally

```bash
uv sync
uv run quarto render notebooks/{qmd_filename}
```
"""

INDEX_TEMPLATE = """# Notebooks

Interactive tutorials exploring the medical Q&A RAG pipeline.

| Notebook | Description |
|----------|-------------|
{notebook_table}
"""


def slugify(title: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")


def parse_frontmatter(qmd_path: Path) -> dict:
    text = qmd_path.read_text(encoding="utf-8")
    if not text.startswith("---"):
        return {}
    end = text.find("---", 3)
    if end == -1:
        return {}
    return yaml.safe_load(text[3:end]) or {}


def get_base_path() -> str:
    if MKDOCS_YML.exists():
        with open(MKDOCS_YML) as f:
            config = yaml.safe_load(f)
        site_url = config.get("site_url", "")
        if site_url and site_url != "/":
            return site_url.rstrip("/")
    return ""


def generate() -> None:
    base_path = get_base_path()

    qmd_files = sorted(NOTEBOOKS_DIR.glob("*.qmd"))
    if not qmd_files:
        print("No .qmd files found in notebooks/")
        return

    DOCS_NOTEBOOKS_DIR.mkdir(parents=True, exist_ok=True)
    (DOCS_NOTEBOOKS_DIR / "html").mkdir(parents=True, exist_ok=True)

    table_rows = []
    for qmd_path in qmd_files:
        fm = parse_frontmatter(qmd_path)
        title = fm.get("title", qmd_path.stem)
        description = fm.get("description", "")
        html_filename = f"{qmd_path.stem}.html"
        slug = slugify(title)

        stub_path = DOCS_NOTEBOOKS_DIR / f"{slug}.md"
        stub_content = IFRAME_TEMPLATE.format(
            title=title,
            description=description,
            base_path=base_path,
            html_filename=html_filename,
            qmd_filename=qmd_path.name,
        )
        stub_path.write_text(stub_content, encoding="utf-8")
        print(f"  Generated: {stub_path.relative_to(PROJECT_ROOT)}")

        table_rows.append(f"| [{title}]({slug}.md) | {description} |")

    index_content = INDEX_TEMPLATE.format(
        notebook_table="\n".join(table_rows),
    )
    index_path = DOCS_NOTEBOOKS_DIR / "index.md"
    index_path.write_text(index_content, encoding="utf-8")
    print(f"  Generated: {index_path.relative_to(PROJECT_ROOT)}")


if __name__ == "__main__":
    generate()
