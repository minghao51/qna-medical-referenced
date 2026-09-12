#!/usr/bin/env python3
"""Offline parity gate for roadmap P3.2 (Hamilton delegation).

Runs the full assessment pipeline offline against a fixed, fabricated
corpus with a deterministic fake embedder — the sanctioned offline
substitute from roadmap gotcha 15 (no DashScope/embedding API key on this
machine; both sides run under the SAME embedder). Produces a normalized
metrics JSON for exact comparison between the baseline (pre-P3.2 commit)
and the branch (post-P3.2), each checked out in its own worktree so the
data/ directories (corpus, chroma, artifacts) stay isolated.

Gated metrics: deterministic L0-L5 step-check aggregates and retrieval
metrics (nDCG/recall). Known-nondeterministic fields (timings, file
sizes) are stripped before comparison. LLM-judged answer metrics are
excluded from the run entirely (include_answer_eval=False).

Usage:
    python scripts/manual/parity_gate_p32.py run --out parity_result.json
    python scripts/manual/parity_gate_p32.py compare baseline.json branch.json
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
import time
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[2]

# ---------------------------------------------------------------------------
# Deterministic corpus (identical on both sides)
# ---------------------------------------------------------------------------

MD_DOCS: dict[str, str] = {
    "cholesterol_screening": (
        "# Cholesterol Screening\n\n"
        "LDL-C targets depend on cardiovascular risk. For high-risk patients the target is "
        "below 1.8 mmol/L. For moderate-risk patients an LDL-C below 2.6 mmol/L is "
        "recommended. HDL cholesterol should be above 1.0 mmol/L for men and 1.2 mmol/L "
        "for women. Triglycerides below 2.0 mmol/L are considered desirable.\n\n"
        "## Fasting requirements\n\n"
        "Fasting lipid panels are traditionally preferred, but non-fasting panels are now "
        "acceptable for most screening purposes. Fasting remains recommended when "
        "triglycerides are markedly elevated or when follow-up confirmation is required.\n"
    ),
    "diabetes_screening": (
        "# Diabetes Screening\n\n"
        "The fasting plasma glucose test requires an eight hour fast. A fasting glucose of "
        "7.0 mmol/L or higher on two occasions supports a diagnosis of diabetes. An HbA1c "
        "of 6.5 percent or higher is also diagnostic. Impaired fasting glucose ranges from "
        "6.1 to 6.9 mmol/L.\n\n"
        "## Who should be screened\n\n"
        "Adults with a body mass index above 23 kg/m2 should be screened from age 40, or "
        "earlier with additional risk factors such as hypertension or a family history of "
        "diabetes.\n"
    ),
    "liver_function": (
        "# Liver Function Tests\n\n"
        "Alanine aminotransferase and aspartate aminotransferase are markers of hepatocellular "
        "injury. Alkaline phosphatase and gamma-glutamyl transferase indicate cholestasis. "
        "Albumin and the prothrombin time reflect synthetic liver function. Mild transaminase "
        "elevation below twice the upper limit of normal is common and often benign.\n\n"
        "## Interpretation\n\n"
        "Isolated ALT elevation warrants repeat testing before further workup. Persistent "
        "elevation above three times the upper limit of normal should prompt evaluation for "
        "viral hepatitis, fatty liver disease, and alcohol-related liver disease.\n"
    ),
}

REFERENCE_CSV = (
    "test_name,normal_range,unit,category,notes\n"
    "LDL-C,< 2.6,mmol/L,lipid,Moderate risk target\n"
    "HDL-C,> 1.0,mmol/L,lipid,Men\n"
    "Triglycerides,< 2.0,mmol/L,lipid,Desirable\n"
    "Fasting glucose,< 6.1,mmol/L,diabetes,Impaired range 6.1-6.9\n"
    "HbA1c,< 5.7,percent,diabetes,Prediabetes 5.7-6.4\n"
    "ALT,10-45,U/L,liver,Hepatocellular marker\n"
    "AST,10-35,U/L,liver,Hepatocellular marker\n"
    "ALP,40-120,U/L,liver,Cholestasis marker\n"
)


def make_minimal_pdf(path: Path, text: str) -> None:
    """Hand-crafted single-page PDF with one text line (no dependencies)."""
    stream = f"BT /F1 11 Tf 72 720 Td ({text}) Tj ET".encode()
    objs = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R "
        b"/Resources << /Font << /F1 5 0 R >> >> >>",
        b"<< /Length " + str(len(stream)).encode() + b" >>\nstream\n" + stream + b"\nendstream",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    out = bytearray(b"%PDF-1.4\n")
    offsets = []
    for i, obj in enumerate(objs, 1):
        offsets.append(len(out))
        out += f"{i} 0 obj\n".encode() + obj + b"\nendobj\n"
    xref = len(out)
    out += b"xref\n0 " + str(len(objs) + 1).encode() + b"\n0000000000 65535 f \n"
    for off in offsets:
        out += f"{off:010d} 00000 n \n".encode()
    out += (
        b"trailer\n<< /Size " + str(len(objs) + 1).encode() + b" /Root 1 0 R >>\n"
        b"startxref\n" + str(xref).encode() + b"\n%%EOF\n"
    )
    path.write_bytes(bytes(out))


def fabricate_corpus() -> None:
    raw = PROJECT_ROOT / "data" / "raw"
    raw.mkdir(parents=True, exist_ok=True)
    for name, text in MD_DOCS.items():
        html = (
            "<html><head><title>"
            + name.replace("_", " ").title()
            + "</title></head><body><article><p>"
            + text.replace("\n\n", "</p><p>").replace("# ", "").replace("## ", "")
            + "</p></article></body></html>"
        )
        (raw / f"{name}.html").write_text(html, encoding="utf-8")
        (raw / f"{name}.md").write_text(text, encoding="utf-8")
    labqar = raw / "LabQAR"
    labqar.mkdir(exist_ok=True)
    (labqar / "reference_ranges.csv").write_text(REFERENCE_CSV, encoding="utf-8")
    make_minimal_pdf(
        raw / "screening_thresholds.pdf",
        "Screening thresholds summary. Fasting glucose of 7.0 mmol/L or higher supports "
        "a diagnosis of diabetes on two occasions.",
    )
    print(f"[parity] corpus fabricated in {raw}")


# ---------------------------------------------------------------------------
# Offline embedder (same algorithm as tests/integration/conftest.py)
# ---------------------------------------------------------------------------

FAKE_EMBEDDING_DIM = 8


def _fake_embedding(text: str) -> list[float]:
    digest = hashlib.sha256(text.lower().encode("utf-8")).digest()
    raw = [byte / 255.0 for byte in digest[:FAKE_EMBEDDING_DIM]]
    norm = math.sqrt(sum(v * v for v in raw)) or 1.0
    return [v / norm for v in raw]


def install_fake_embedder() -> None:
    import src.ingestion.indexing.store as chroma_store

    def fake_embed_texts(texts, batch_size=10, model=None):
        return [_fake_embedding(text) for text in texts]

    def fake_embed_texts_with_stats(texts, batch_size=10, model=None):
        vectors = fake_embed_texts(texts, batch_size, model)
        stats = {
            "provider": "offline-stub",
            "model": model or "offline-stub",
            "batch_size": batch_size,
            "count": len(texts),
        }
        return vectors, stats

    chroma_store.embed_texts = fake_embed_texts
    chroma_store.embed_texts_with_stats = fake_embed_texts_with_stats
    print("[parity] deterministic fake embedder installed at indexing.store")


# ---------------------------------------------------------------------------
# Normalization for exact comparison
# ---------------------------------------------------------------------------

NON_DETERMINISTIC_SUBSTRINGS = (
    "timing",
    "latency",
    "elapsed",
    "size_bytes",
    "duration",
    "epoch_s",
    "wall_time",
)


def normalize(value: Any, root: str = "", path: str = "") -> Any:
    if isinstance(value, dict):
        return {
            key: normalize(item, root, f"{path}.{key}")
            for key, item in sorted(value.items())
            if not any(substring in key for substring in NON_DETERMINISTIC_SUBSTRINGS)
        }
    if isinstance(value, list):
        return [normalize(item, root, f"{path}[{i}]") for i, item in enumerate(value)]
    if isinstance(value, str) and root and root in value:
        return value.replace(root, "<ROOT>")
    return value


def first_diff(a: Any, b: Any, path: str = "$") -> str | None:
    if isinstance(a, dict) and isinstance(b, dict):
        for key in sorted(set(a) | set(b)):
            if key not in a:
                return f"{path}.{key}: missing in baseline"
            if key not in b:
                return f"{path}.{key}: missing in branch"
            diff = first_diff(a[key], b[key], f"{path}.{key}")
            if diff:
                return diff
        return None
    if isinstance(a, list) and isinstance(b, list):
        if len(a) != len(b):
            return f"{path}: list length {len(a)} != {len(b)}"
        for i, (x, y) in enumerate(zip(a, b, strict=True)):
            diff = first_diff(x, y, f"{path}[{i}]")
            if diff:
                return diff
        return None
    if a != b:
        return f"{path}: {a!r} != {b!r}"
    return None


# ---------------------------------------------------------------------------
# Gate run
# ---------------------------------------------------------------------------


def cmd_run(out: Path) -> None:
    sys.path.insert(0, str(PROJECT_ROOT))

    # NLTK stopwords: prefer the system corpus, else the vendored copy.
    try:
        from nltk.corpus import stopwords

        stopwords.words("english")
    except LookupError:
        import nltk.data

        nltk.data.path.append(str(PROJECT_ROOT / "tests/integration/fixtures/nltk_data"))
        from nltk.corpus import stopwords as vendored

        vendored.words("english")

    fabricate_corpus()
    install_fake_embedder()

    from src.config import settings
    from src.config.context import get_runtime_state
    from src.ingestion.indexing.factory import ChromaVectorStoreFactory

    chroma_dir = PROJECT_ROOT / "data" / "parity_chroma"
    settings.storage.chroma_server_host = ""
    settings.storage.chroma_persist_directory = str(chroma_dir)
    ChromaVectorStoreFactory.reset()
    get_runtime_state().reset_vector_store_state()

    from src.evals import run_assessment

    start = time.time()
    result = run_assessment(
        artifact_dir=PROJECT_ROOT / "data" / "evals_parity",
        name="p32_parity",
        disable_llm_generation=True,
        disable_llm_judging=True,
        include_answer_eval=False,
        seed=42,
        sample_seed=42,
        max_synthetic_questions=40,
        sample_docs_per_source_type=10,
        reuse_cached_dataset=False,
        force_rerun=True,
        fail_on_thresholds=False,
    )
    elapsed = time.time() - start
    run_dir = Path(result.run_dir)
    step_metrics = json.loads((run_dir / "step_metrics.json").read_text(encoding="utf-8"))
    retrieval_metrics = json.loads((run_dir / "retrieval_metrics.json").read_text(encoding="utf-8"))
    dataset = json.loads((run_dir / "retrieval_dataset.json").read_text(encoding="utf-8"))

    payload = {
        "run_dir": run_dir.name,
        "status": result.status,
        "wall_time_s_excluded": round(elapsed, 1),
        "step_metrics": normalize(step_metrics, str(PROJECT_ROOT)),
        "retrieval_metrics": normalize(retrieval_metrics, str(PROJECT_ROOT)),
        "dataset_stats": {
            "query_count": len(dataset),
        },
    }
    out.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    print(f"[parity] wrote {out} (run_dir={run_dir.name}, status={result.status})")


def cmd_compare(baseline: Path, branch: Path) -> int:
    base = json.loads(baseline.read_text(encoding="utf-8"))
    brch = json.loads(branch.read_text(encoding="utf-8"))
    failures: list[str] = []
    for section in ("step_metrics", "retrieval_metrics", "dataset_stats"):
        diff = first_diff(base.get(section), brch.get(section), f"$.{section}")
        if diff:
            failures.append(diff)
    if failures:
        print("[parity] FAIL — first divergences:")
        for failure in failures:
            print("  " + failure)
        return 1
    print("[parity] PASS - L0-L5 aggregates, retrieval metrics and dataset identical")
    print(f"  baseline: {base.get('run_dir')}  (status={base.get('status')})")
    print(f"  branch:   {brch.get('run_dir')}  (status={brch.get('status')})")
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="mode", required=True)
    run_p = sub.add_parser("run", help="run the offline parity assessment")
    run_p.add_argument("--out", type=Path, required=True)
    cmp_p = sub.add_parser("compare", help="compare two parity_result.json files")
    cmp_p.add_argument("baseline", type=Path)
    cmp_p.add_argument("branch", type=Path)
    args = parser.parse_args()

    if args.mode == "run":
        cmd_run(args.out)
    else:
        sys.exit(cmd_compare(args.baseline, args.branch))


if __name__ == "__main__":
    main()
