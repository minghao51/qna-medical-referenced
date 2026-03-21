# Code Review Remediation Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Address all critical issues and recommendations from the code review, including dependency conflicts, configuration validation, hardcoded URL extraction, and frontend utility extraction.

**Architecture:** This plan fixes immediate blockers (dependency conflict), then addresses code quality improvements (configuration validation, URL extraction, frontend refactoring) following TDD principles with minimal changes per task.

**Tech Stack:** Python 3.13, FastAPI, Svelte 5, TypeScript, uv, pytest, Playwright

---

## Task 1: Verify and Fix Dependency Conflict

**Files:**
- Modify: `pyproject.toml:9`

**Step 1: Verify current dependency versions**

Check if the current `pypdf>=4.0,<6.0` constraint is compatible with `camelot-py>=0.12.0`.

Run: `uv tree | grep -E "(pypdf|camelot)"`
Expected: Shows current dependency tree and any conflicts

**Step 2: Check camelot-py dependencies**

Run: `uv pip show camelot-py 2>/dev/null || uv pip index show camelot-py`
Expected: Shows camelot-py's pypdf requirements

**Step 3: Test environment resolution**

Run: `uv sync`
Expected: PASS with no dependency resolution errors

**Step 4: If conflict exists, fix pypdf version**

If uv sync fails, modify `pyproject.toml` line 9:

```toml
# Change from:
"pypdf>=4.0,<6.0",
# To compatible version based on camelot-py requirements:
"pypdf>=5.0.0,<6.0",
```

**Step 5: Verify fix**

Run: `uv sync`
Expected: PASS with successful dependency resolution

**Step 6: Run tests to ensure no breakage**

Run: `uv run pytest tests/test_pdf_loader.py -v`
Expected: PASS - All PDF loading tests pass

**Step 7: Commit**

```bash
git add pyproject.toml
git commit -m "fix: resolve pypdf/camelot-py dependency conflict"
```

---

## Task 2: Verify Deleted Pipeline File Impact

**Files:**
- Check: `src/ingestion/__init__.py`, `src/cli/ingest.py`, `src/usecases/__init__.py`

**Step 1: Verify src.usecases.pipeline exists**

Run: `test -f src/usecases/pipeline.py && echo "EXISTS" || echo "MISSING"`
Expected: EXISTS

**Step 2: Check imports are working**

Run: `uv run python -c "from src.usecases.pipeline import run_pipeline; print('OK')"`
Expected: OK

**Step 3: Verify no broken imports remain**

Run: `grep -r "from src.ingestion.pipeline" src/ || echo "No broken imports found"`
Expected: No broken imports found

**Step 4: Test CLI ingest command**

Run: `uv run python -m src.cli.ingest --help`
Expected: Help output without import errors

**Step 5: Document the change**

Create `docs/plans/2026-03-20-pipeline-refactoring-notes.md`:

```markdown
# Pipeline Module Refactoring Notes

## Change Summary
- Deleted: `src/ingestion/pipeline.py` (compatibility shim)
- Remains: `src/usecases/pipeline.py` (actual implementation)

## Import Path Changes
Old imports using `from src.ingestion.pipeline` should use:
- `from src.usecases.pipeline import run_pipeline`
- `from src.usecases.pipeline import main`

## Verified Files
- `src/ingestion/__init__.py` - Updated to use new path
- `src/cli/ingest.py` - Updated to use new path
- `src/usecases/__init__.py` - Updated to use new path
```

**Step 6: Commit**

```bash
git add docs/plans/2026-03-20-pipeline-refactoring-notes.md
git commit -m "docs: document pipeline module refactoring"
```

---

## Task 3: Extract Hardcoded URLs to Configuration

**Files:**
- Create: `config/ingestion_urls.yaml`
- Modify: `src/ingestion/steps/download_web.py:376-556`

**Step 1: Write the failing test**

Create `tests/test_ingestion_urls_config.py`:

```python
"""Test URL configuration loading."""
from pathlib import Path
import yaml

def test_url_config_exists():
    """URL configuration file should exist."""
    config_path = Path("config/ingestion_urls.yaml")
    assert config_path.exists(), "config/ingestion_urls.yaml must exist"

def test_url_config_structure():
    """URL configuration should have correct structure."""
    config_path = Path("config/ingestion_urls.yaml")
    with open(config_path) as f:
        config = yaml.safe_load(f)

    assert "ace_clinical_guidelines" in config
    assert "ace_cues" in config
    assert "ace_drug_guidances" in config
    assert "healthhub" in config
    assert "hpp_guidelines" in config
    assert "international_guidelines" in config
    assert "moh" in config

def test_url_config_entries_have_required_fields():
    """Each URL entry should have url and logical_name."""
    config_path = Path("config/ingestion_urls.yaml")
    with open(config_path) as f:
        config = yaml.safe_load(f)

    for category in config.values():
        for entry in category:
            assert "url" in entry, f"Missing 'url' in {entry}"
            assert "logical_name" in entry, f"Missing 'logical_name' in {entry}"
            assert entry["url"].startswith("http"), f"Invalid URL in {entry}"
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_ingestion_urls_config.py -v`
Expected: FAIL - "config/ingestion_urls.yaml must exist"

**Step 3: Create URL configuration file**

Create `config/ingestion_urls.yaml`:

```yaml
# ACE Clinical Guidelines
ace_clinical_guidelines:
  - url: "https://www.ace-hta.gov.sg/healthcare-professionals/ace-repository-for-clinical-guidelines/"
    logical_name: "ace_guidelines_index"
  - url: "https://www.ace-hta.gov.sg/healthcare-professionals/ace-repository-for-clinical-guidelines/osteoporosis--diagnosis-and-management/"
    logical_name: "osteoporosis_guideline"
  - url: "https://www.ace-hta.gov.sg/healthcare-professionals/ace-repository-for-clinical-guidelines/major-depressive-disorder-achieving-and-sustaining-remission/"
    logical_name: "depression_guideline"
  - url: "https://www.ace-hta.gov.sg/healthcare-professionals/ace-repository-for-clinical-guidelines/generalised-anxiety-disorder-easing-burden-and-enabling-remission/"
    logical_name: "anxiety_guideline"
  - url: "https://www.ace-hta.gov.sg/healthcare-professionals/ace-repository-for-clinical-guidelines/management-of-chronic-coronary-syndrome/"
    logical_name: "coronary_syndrome_guideline"
  - url: "https://www.ace-hta.gov.sg/healthcare-professionals/ace-repository-for-clinical-guidelines/promoting-smoking-cessation-and-treating-tobacco-dependence/"
    logical_name: "smoking_cessation_guideline"
  - url: "https://www.ace-hta.gov.sg/healthcare-professionals/ace-repository-for-clinical-guidelines/chronic-obstructive-pulmonary-disease-diagnosis-and-management/"
    logical_name: "copd_guideline"
  - url: "https://www.ace-hta.gov.sg/healthcare-professionals/ace-repository-for-clinical-guidelines/initiating-basal-insulin-in-type-2-diabetes-mellitus/"
    logical_name: "diabetes_insulin_guideline"
  - url: "https://www.ace-hta.gov.sg/healthcare-professionals/ace-repository-for-clinical-guidelines/foot-assessment-in-patients-with-diabetes-mellitus/"
    logical_name: "diabetes_foot_guideline"
  - url: "https://www.ace-hta.gov.sg/healthcare-professionals/ace-repository-for-clinical-guidelines/venous-thromboembolism-treating-with-the-appropriate-anticoagulant-and-duration/"
    logical_name: "vte_guideline"
  - url: "https://www.ace-hta.gov.sg/healthcare-professionals/ace-repository-for-clinical-guidelines/lipid-management-focus-on-cardiovascular-risk/"
    logical_name: "lipid_management_guideline"
  - url: "https://www.ace-hta.gov.sg/healthcare-professionals/ace-repository-for-clinical-guidelines/mild-and-moderate-atopic-dermatitis-acg/"
    logical_name: "atopic_dermatitis_guideline"
  - url: "https://www.ace-hta.gov.sg/healthcare-professionals/ace-repository-for-clinical-guidelines/heart-failure-acg/"
    logical_name: "heart_failure_guideline"
  - url: "https://www.ace-hta.gov.sg/healthcare-professionals/ace-repository-for-clinical-guidelines/atrial-fibrillation-acg/"
    logical_name: "atrial_fibrillation_guideline"
  - url: "https://www.ace-hta.gov.sg/healthcare-professionals/ace-repository-for-clinical-guidelines/chronic-kidney-disease-acg/"
    logical_name: "ckd_guideline"
  - url: "https://www.ace-hta.gov.sg/healthcare-professionals/ace-repository-for-clinical-guidelines/asthma-diagnosis-management/"
    logical_name: "asthma_guideline"
  - url: "https://www.ace-hta.gov.sg/healthcare-professionals/ace-repository-for-clinical-guidelines/obesity-weight-management-acg/"
    logical_name: "obesity_guideline"
  - url: "https://www.ace-hta.gov.sg/healthcare-professionals/ace-repository-for-clinical-guidelines/allergic-rhinitis-acg/"
    logical_name: "allergic_rhinitis_guideline"
  - url: "https://www.ace-hta.gov.sg/healthcare-professionals/ace-repository-for-clinical-guidelines/dementia-acg/"
    logical_name: "dementia_guideline"
  - url: "https://www.ace-hta.gov.sg/healthcare-professionals/ace-repository-for-clinical-guidelines/bipolar-disorder-acg/"
    logical_name: "bipolar_guideline"
  - url: "https://www.ace-hta.gov.sg/healthcare-professionals/ace-repository-for-clinical-guidelines/gord-acg/"
    logical_name: "gord_guideline"
  - url: "https://www.ace-hta.gov.sg/healthcare-professionals/ace-repository-for-clinical-guidelines/osteoarthritis-knee-acg/"
    logical_name: "osteoarthritis_guideline"
  - url: "https://www.ace-hta.gov.sg/healthcare-professionals/ace-repository-for-clinical-guidelines/stroke-management-acg/"
    logical_name: "stroke_guideline"

# ACE CUES Resources
ace_cues:
  - url: "https://www.ace-hta.gov.sg/healthcare-professionals/ace-cues-overview/"
    logical_name: "ace_cues_index"
  - url: "https://www.ace-hta.gov.sg/healthcare-professionals/ace-cues/asthma-management/"
    logical_name: "ace_cues_asthma"
  - url: "https://www.ace-hta.gov.sg/healthcare-professionals/ace-cues/inhaler-technique-videos/"
    logical_name: "ace_cues_inhaler"

# ACE Drug Guidances
ace_drug_guidances:
  - url: "https://www.ace-hta.gov.sg/healthcare-professionals/ace-technology-guidances/drug-guidance/semaglutide-obesity/"
    logical_name: "semaglutide_obesity"
  - url: "https://www.ace-hta.gov.sg/healthcare-professionals/ace-technology-guidances/drug-guidance/empagliflozin/"
    logical_name: "empagliflozin"
  - url: "https://www.ace-hta.gov.sg/healthcare-professionals/ace-technology-guidances/drug-guidance/glp1-diabetes/"
    logical_name: "glp1_diabetes"
  - url: "https://www.ace-hta.gov.sg/healthcare-professionals/ace-technology-guidances/drug-guidance/apixaban/"
    logical_name: "apixaban"
  - url: "https://www.ace-hta.gov.sg/healthcare-professionals/ace-technology-guidances/drug-guidance/pcsk9-inhibitors/"
    logical_name: "pcsk9_inhibitors"
  - url: "https://www.ace-hta.gov.sg/healthcare-professionals/ace-technology-guidances/drug-guidance/biologics-asthma/"
    logical_name: "biologics_asthma"
  - url: "https://www.ace-hta.gov.sg/healthcare-professionals/ace-technology-guidances/drug-guidance/trastuzumab-deruxtecan-nsclc/"
    logical_name: "trastuzumab_deruxtecan"
  - url: "https://www.ace-hta.gov.sg/healthcare-professionals/ace-technology-guidances/drug-guidance/ribociclib-breast/"
    logical_name: "ribociclib_breast"
  - url: "https://www.ace-hta.gov.sg/healthcare-professionals/ace-technology-guidances/drug-guidance/inavolisib-breast/"
    logical_name: "inavolisib_breast"
  - url: "https://www.ace-hta.gov.sg/healthcare-professionals/ace-technology-guidances/drug-guidance/ustekinumab-biosimilar/"
    logical_name: "ustekinumab"

# HealthHub Content
healthhub:
  - url: "https://www.healthhub.sg/health-conditions/high-cholesterol"
    logical_name: "high_cholesterol"
  - url: "https://www.healthhub.sg/health-conditions/diabetes"
    logical_name: "diabetes"
  - url: "https://www.healthhub.sg/health-conditions/hypertension"
    logical_name: "hypertension"
  - url: "https://www.healthhub.sg/well-being-and-lifestyle/personal-care/type-2-screening-tests"
    logical_name: "health_screening_tests"
  - url: "https://www.healthhub.sg/programmes/healthiersg-screening/screening-faq"
    logical_name: "healthier_sg_screening_faq"
  - url: "https://www.healthhub.sg/well-being-and-lifestyle/mental-wellness/"
    logical_name: "mental_wellness"
  - url: "https://www.healthhub.sg/well-being-and-lifestyle/exercise-and-fitness/"
    logical_name: "exercise_fitness"
  - url: "https://www.healthhub.sg/well-being-and-lifestyle/food-diet-and-nutrition/"
    logical_name: "food_nutrition"
  - url: "https://www.healthhub.sg/well-being-and-lifestyle/active-ageing/"
    logical_name: "active_ageing"
  - url: "https://www.healthhub.sg/well-being-and-lifestyle/personal-care/all-you-need-to-know-about-vaccinations/"
    logical_name: "vaccinations_guide"

# HPP/MOH Guidelines
hpp_guidelines:
  - url: "https://hpp.moh.gov.sg/guidelines/"
    logical_name: "hpp_guidelines_index"
  - url: "https://hpp.moh.gov.sg/guidelines/collaborative-prescribing/"
    logical_name: "collab_prescribing_guideline"
  - url: "https://hpp.moh.gov.sg/guidelines/infection-prevention-and-control-guidelines-and-standards/"
    logical_name: "infection_control_guideline"
  - url: "https://hpp.moh.gov.sg/guidelines/eatwise-sg/"
    logical_name: "eatwise_sg_guideline"
  - url: "https://hpp.moh.gov.sg/guidelines/practice-guide-for-tiered-care-model-for-mental-health/"
    logical_name: "mental_health_tiered_care"
  - url: "https://hpp.moh.gov.sg/guidelines/medisave-for-chronic-disease-management-programme/"
    logical_name: "medisave_cdmp_guideline"
  - url: "https://hpp.moh.gov.sg/guidelines/dental-fee-benchmarks/"
    logical_name: "dental_fee_benchmarks"

# International Guidelines
international_guidelines:
  - url: "https://www.nice.org.uk/guidance/ng28"
    logical_name: "nice_diabetes_ng28"
  - url: "https://www.nice.org.uk/guidance/cg127"
    logical_name: "nice_hypertension"
  - url: "https://www.nice.org.uk/guidance/cg181"
    logical_name: "nice_lipid"
  - url: "https://www.nice.org.uk/guidance/ng236"
    logical_name: "nice_heart_failure"

# MOH Singapore
moh:
  - url: "https://www.moh.gov.sg/"
    logical_name: "moh_singapore"
```

**Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_ingestion_urls_config.py -v`
Expected: PASS - All URL config tests pass

**Step 5: Add PyYAML to dependencies**

Run: `uv add pyyaml`
Expected: Package added successfully

**Step 6: Update download_web.py to use config**

Modify `src/ingestion/steps/download_web.py`:

Add imports at top:
```python
import yaml
from pathlib import Path

URL_CONFIG_PATH = Path(__file__).parent.parent.parent / "config" / "ingestion_urls.yaml"


def _load_url_config() -> dict:
    """Load URL configuration from YAML file."""
    if not URL_CONFIG_PATH.exists():
        return {}
    with open(URL_CONFIG_PATH) as f:
        return yaml.safe_load(f)
```

Replace hardcoded URL lists with config-loaded versions:

```python
async def extract_ace_clinical_guidelines() -> list[str]:
    """Extract ACE Clinical Guidelines from ace-hta.gov.sg."""
    config = _load_url_config()
    guidelines = config.get("ace_clinical_guidelines", [])

    downloaded = []
    for entry in guidelines:
        url = entry["url"]
        name = entry["logical_name"]
        result = await _download_and_save_html(url, name)
        if result:
            downloaded.append(result)
    return downloaded


async def extract_ace_cues() -> list[str]:
    """Extract ACE CUES resources from ace-hta.gov.sg."""
    config = _load_url_config()
    pages = config.get("ace_cues", [])

    downloaded = []
    for entry in pages:
        url = entry["url"]
        name = entry["logical_name"]
        result = await _download_and_save_html(url, name)
        if result:
            downloaded.append(result)
    return downloaded


async def extract_ace_drug_guidances() -> list[str]:
    """Extract ACE Drug Guidances from ace-hta.gov.sg."""
    config = _load_url_config()
    guidances = config.get("ace_drug_guidances", [])

    downloaded = []
    for entry in guidances:
        url = entry["url"]
        name = entry["logical_name"]
        result = await _download_and_save_html(url, name)
        if result:
            downloaded.append(result)
    return downloaded


async def extract_healthhub_content() -> list[str]:
    """Extract HealthHub health conditions and screening info."""
    config = _load_url_config()
    pages = config.get("healthhub", [])

    downloaded = []
    for entry in pages:
        url = entry["url"]
        name = entry["logical_name"]
        result = await _download_and_save_html(url, name)
        if result:
            downloaded.append(result)
    return downloaded


async def extract_hpp_guidelines() -> list[str]:
    """Extract HPP/MOH Professional Guidelines."""
    config = _load_url_config()
    pages = config.get("hpp_guidelines", [])

    downloaded = []
    for entry in pages:
        url = entry["url"]
        name = entry["logical_name"]
        result = await _download_and_save_html(url, name)
        if result:
            downloaded.append(result)
    return downloaded


async def extract_moh_content() -> list[str]:
    """Extract MOH Singapore main page."""
    config = _load_url_config()
    pages = config.get("moh", [])

    downloaded = []
    for entry in pages:
        url = entry["url"]
        name = entry["logical_name"]
        result = await _download_and_save_html(url, name)
        if result:
            downloaded.append(result)
    return downloaded


async def extract_international_guidelines() -> list[str]:
    """Extract international medical guidelines (NHS/NICE) with extended timeout."""
    config = _load_url_config()
    pages = config.get("international_guidelines", [])

    downloaded = []
    for entry in pages:
        url = entry["url"]
        name = entry["logical_name"]
        result = await _download_and_save_html(url, name, timeout=60)
        if result:
            downloaded.append(result)
    return downloaded
```

**Step 7: Run tests to verify refactoring works**

Run: `uv run pytest tests/test_ingestion_urls_config.py tests/test_ingestion_error_handling.py -v`
Expected: PASS - All tests pass with new config-based implementation

**Step 8: Run integration test**

Run: `uv run python -m src.ingestion.steps.download_web --help`
Expected: Help output without errors

**Step 9: Commit**

```bash
git add config/ingestion_urls.yaml tests/test_ingestion_urls_config.py src/ingestion/steps/download_web.py pyproject.toml uv.lock
git commit -m "refactor: extract hardcoded URLs to YAML configuration"
```

---

## Task 4: Add Runtime Configuration Validation

**Files:**
- Create: `src/rag/config_validation.py`
- Modify: `src/rag/runtime.py:70-88`

**Step 1: Write the failing test**

Create `tests/test_runtime_config_validation.py`:

```python
"""Test runtime configuration validation."""
from src.rag.config_validation import validate_retrieval_config, RetrievalDiversityConfig
import pytest

def test_valid_config_passes():
    """Valid configuration should pass validation."""
    config = RetrievalDiversityConfig(
        overfetch_multiplier=4,
        max_chunks_per_source_page=2,
        max_chunks_per_source=3,
        mmr_lambda=0.75,
        enable_diversification=True,
        search_mode="rrf_hybrid",
        enable_hyde=False,
    )
    # Should not raise
    validate_retrieval_config(config)

def test_invalid_search_mode_raises():
    """Invalid search mode should raise ValueError."""
    config = RetrievalDiversityConfig(search_mode="invalid_mode")
    with pytest.raises(ValueError, match="Invalid search_mode"):
        validate_retrieval_config(config)

def test_hyde_with_bm25_only_raises():
    """HyDE with bm25_only should raise ValueError."""
    config = RetrievalDiversityConfig(
        search_mode="bm25_only",
        enable_hyde=True,
    )
    with pytest.raises(ValueError, match="HyDE not compatible"):
        validate_retrieval_config(config)

def test_mmr_lambda_clamped():
    """MMR lambda outside [0, 1] should be clamped."""
    config = RetrievalDiversityConfig(mmr_lambda=1.5)
    validate_retrieval_config(config)
    assert config.mmr_lambda == 1.0

def test_negative_multiplier_raises():
    """Negative overfetch_multiplier should raise ValueError."""
    config = RetrievalDiversityConfig(overfetch_multiplier=-1)
    with pytest.raises(ValueError, match="overfetch_multiplier must be positive"):
        validate_retrieval_config(config)
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_runtime_config_validation.py -v`
Expected: FAIL - "No module named 'src.rag.config_validation'"

**Step 3: Create validation module**

Create `src/rag/config_validation.py`:

```python
"""Runtime configuration validation for RAG retrieval."""
from dataclasses import dataclass
from src.rag.runtime import RetrievalDiversityConfig


_VALID_SEARCH_MODES = {"rrf_hybrid", "semantic_only", "bm25_only"}


def validate_retrieval_config(config: RetrievalDiversityConfig) -> None:
    """
    Validate retrieval configuration for compatibility and constraints.

    Args:
        config: RetrievalDiversityConfig instance to validate

    Raises:
        ValueError: If configuration is invalid or has incompatible options
    """
    # Validate search_mode
    if config.search_mode not in _VALID_SEARCH_MODES:
        raise ValueError(
            f"Invalid search_mode '{config.search_mode}'. "
            f"Valid options: {sorted(_VALID_SEARCH_MODES)}"
        )

    # Validate HyDE compatibility
    if config.enable_hyde and config.search_mode == "bm25_only":
        raise ValueError(
            f"HyDE query expansion is not compatible with search_mode='{config.search_mode}'. "
            f"Use 'rrf_hybrid' or 'semantic_only' with HyDE."
        )

    # Validate numeric ranges
    if config.overfetch_multiplier < 1:
        raise ValueError(
            f"overfetch_multiplier must be positive, got {config.overfetch_multiplier}"
        )

    if config.max_chunks_per_source_page < 1:
        raise ValueError(
            f"max_chunks_per_source_page must be positive, got {config.max_chunks_per_source_page}"
        )

    if config.max_chunks_per_source < 1:
        raise ValueError(
            f"max_chunks_per_source must be positive, got {config.max_chunks_per_source}"
        )

    # Clamp mmr_lambda to [0, 1]
    if not (0.0 <= config.mmr_lambda <= 1.0):
        config.mmr_lambda = max(0.0, min(1.0, config.mmr_lambda))

    # Clamp hyde_max_length to reasonable range
    if config.hyde_max_length < 50 or config.hyde_max_length > 500:
        config.hyde_max_length = max(50, min(500, config.hyde_max_length))
```

**Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_runtime_config_validation.py -v`
Expected: PASS - All validation tests pass

**Step 5: Integrate validation into runtime**

Modify `src/rag/runtime.py`:

Add import:
```python
from src.rag.config_validation import validate_retrieval_config
```

Update `_resolve_retrieval_config` function (around line 70):

```python
def _resolve_retrieval_config(overrides: dict[str, Any] | None = None) -> RetrievalDiversityConfig:
    cfg = RetrievalDiversityConfig()
    if not overrides:
        overrides = {}
    for key, value in overrides.items():
        if value is None or not hasattr(cfg, key):
            continue
        setattr(cfg, key, value)
    cfg.overfetch_multiplier = max(1, int(cfg.overfetch_multiplier))
    cfg.max_chunks_per_source_page = max(1, int(cfg.max_chunks_per_source_page))
    cfg.max_chunks_per_source = max(1, int(cfg.max_chunks_per_source))
    cfg.mmr_lambda = max(0.0, min(1.0, float(cfg.mmr_lambda)))
    cfg.search_mode = str(cfg.search_mode or _RRF_SEARCH_MODE).lower()
    cfg.enable_hyde = bool(cfg.enable_hyde)
    cfg.hyde_max_length = max(50, min(500, int(cfg.hyde_max_length)))

    # Validate final configuration
    validate_retrieval_config(cfg)
    return cfg
```

**Step 6: Run tests to verify integration**

Run: `uv run pytest tests/test_runtime_config_validation.py tests/test_backend_e2e_real_apis.py -v -k "test_chat"`
Expected: PASS - Validation tests and chat tests pass

**Step 7: Commit**

```bash
git add src/rag/config_validation.py tests/test_runtime_config_validation.py src/rag/runtime.py
git commit -m "feat: add runtime configuration validation"
```

---

## Task 5: Extract Frontend Source Normalization Logic

**Files:**
- Create: `frontend/src/lib/utils/sourceDisplay.ts`
- Modify: `frontend/src/routes/+page.svelte:231-271`

**Step 1: Write the failing test**

Create `frontend/src/lib/utils/sourceDisplay.test.ts`:

```typescript
import { describe, it, expect } from 'vitest';
import { normalizeSource, RenderableSource } from './sourceDisplay';
import type { ChatSource } from '$lib/types';

describe('sourceDisplay', () => {
  describe('normalizeSource', () => {
    it('should handle string sources', () => {
      const result = normalizeSource('https://example.com/page.html');
      expect(result.canonicalLabel).toBe('https://example.com/page.html');
      expect(result.sourceType).toBe('html');
      expect(result.sourceClass).toBe('unknown');
    });

    it('should handle ChatSource objects with metadata', () => {
      const source: ChatSource = {
        source: 'test.pdf',
        page: 5,
        canonical_label: 'Test Document',
        display_label: 'Test Document page 5',
        source_type: 'pdf',
        source_class: 'guideline_pdf',
        domain: 'example.com',
        domain_type: 'commercial',
      };
      const result = normalizeSource(source);
      expect(result.canonicalLabel).toBe('Test Document');
      expect(result.displayLabel).toBe('Test Document page 5');
      expect(result.page).toBe(5);
      expect(result.sourceType).toBe('pdf');
      expect(result.sourceClass).toBe('guideline_pdf');
    });

    it('should dedupe sources by key', () => {
      const source: ChatSource = {
        source: 'test.pdf',
        page: 1,
      };
      const result1 = normalizeSource(source);
      const result2 = normalizeSource(source);
      expect(result1.key).toBe(result2.key);
    });
  });
});
```

**Step 2: Run test to verify it fails**

Run: `cd frontend && npm run test:run -- sourceDisplay.test.ts`
Expected: FAIL - "Cannot find module './sourceDisplay'"

**Step 3: Create sourceDisplay utility module**

Create `frontend/src/lib/utils/sourceDisplay.ts`:

```typescript
import { getSafeExternalUrl } from './url';
import { getDomainType } from '$lib/confidenceCalculator';
import type { ChatSource } from '$lib/types';
import type { SourceDomainType } from '$lib/types';

export interface RenderableSource {
  canonicalLabel: string;
  displayLabel: string;
  source: string;
  url: string | null;
  page?: number;
  sourceType: string;
  sourceClass: string;
  domain: string | null;
  domainType: SourceDomainType;
  contentType?: string;
  key: string;
}

function inferSourceType(source: string): string {
  const lowered = source.toLowerCase();
  if (lowered.endsWith('.pdf')) return 'pdf';
  if (lowered.endsWith('.csv')) return 'reference_csv';
  if (lowered.endsWith('.md') || lowered.endsWith('.html')) return 'html';
  return 'other';
}

function sourceTypeLabel(sourceType: string): string {
  const labels: Record<string, string> = {
    pdf: 'PDF',
    html: 'HTML',
    reference_csv: 'Reference CSV',
    other: 'Other'
  };
  return labels[sourceType] ?? formatTitleCase(sourceType);
}

function sourceClassLabel(sourceClass: string): string {
  const labels: Record<string, string> = {
    guideline_pdf: 'Guideline PDF',
    guideline_html: 'Guideline HTML',
    reference_csv: 'Reference CSV',
    index_page: 'Index Page',
    unknown: 'Unknown'
  };
  return labels[sourceClass] ?? formatTitleCase(sourceClass);
}

function formatTitleCase(value: string): string {
  return value
    .split(/[_\s-]+/)
    .filter(Boolean)
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(' ');
}

export function normalizeSource(source: ChatSource | string): RenderableSource {
  if (typeof source === 'string') {
    const safeUrl = getSafeExternalUrl(source);
    const domain = safeUrl ? new URL(safeUrl).hostname.toLowerCase() : null;
    const sourceType = inferSourceType(source);
    return {
      canonicalLabel: source,
      displayLabel: source,
      source,
      url: safeUrl,
      sourceType,
      sourceClass: sourceType === 'reference_csv' ? 'reference_csv' : 'unknown',
      domain,
      domainType: domain ? getDomainType(domain) : 'unknown',
      key: `${safeUrl ?? source}::`
    };
  }

  const safeUrl = getSafeExternalUrl(source.source_url || source.url);
  const canonicalLabel =
    source.canonical_label || source.display_label || source.label || source.source || 'Unknown source';
  const displayLabel = source.display_label || source.label || canonicalLabel;
  const canonicalSource = source.source || source.source_url || source.url || canonicalLabel;
  const domain = source.domain || (safeUrl ? new URL(safeUrl).hostname.toLowerCase() : null);
  const sourceType = source.source_type || inferSourceType(canonicalSource);
  const sourceClass =
    source.source_class || (sourceType === 'reference_csv' ? 'reference_csv' : 'unknown');
  return {
    canonicalLabel,
    displayLabel,
    source: canonicalSource,
    url: safeUrl,
    page: source.page,
    sourceType,
    sourceClass,
    domain,
    domainType: source.domain_type || (domain ? getDomainType(domain) : 'unknown'),
    contentType: source.content_type,
    key: `${canonicalSource}::${source.page ?? ''}`
  };
}

export { sourceTypeLabel, sourceClassLabel, formatTitleCase };
```

**Step 4: Run test to verify it passes**

Run: `cd frontend && npm run test:run -- sourceDisplay.test.ts`
Expected: PASS - All source display tests pass

**Step 5: Update +page.svelte to use extracted utility**

Modify `frontend/src/routes/+page.svelte`:

Add import:
```typescript
import { normalizeSource, sourceTypeLabel, sourceClassLabel, type RenderableSource } from '$lib/utils/sourceDisplay';
```

Remove duplicate functions and types (delete lines 25-37, 186-221, 231-271):

Remove:
```typescript
// Delete these lines
type RenderableSource = { ... };

function formatTitleCase(value: string): string { ... }
function inferSourceType(source: string): string { ... }
function sourceTypeLabel(sourceType: string): string { ... }
function sourceClassLabel(sourceClass: string): string { ... }
function normalizeSource(source: ChatSource | string): RenderableSource { ... }
```

**Step 6: Run frontend tests**

Run: `cd frontend && npm run test:run`
Expected: PASS - All frontend tests pass

**Step 7: Run E2E tests**

Run: `cd frontend && npm run e2e`
Expected: PASS - Playwright E2E tests pass

**Step 8: Commit**

```bash
git add frontend/src/lib/utils/sourceDisplay.ts frontend/src/lib/utils/sourceDisplay.test.ts frontend/src/routes/+page.svelte
git commit -m "refactor: extract source normalization logic to utility module"
```

---

## Task 6: Run Full Verification Suite

**Files:**
- Test: All test files

**Step 1: Run backend tests**

Run: `uv run pytest -v`
Expected: PASS - All backend tests pass

**Step 2: Run frontend tests**

Run: `cd frontend && npm run test:run`
Expected: PASS - All frontend unit tests pass

**Step 3: Run E2E tests**

Run: `cd frontend && npm run e2e`
Expected: PASS - All Playwright E2E tests pass

**Step 4: Run linter**

Run: `uv run ruff check .`
Expected: PASS - No linting errors

**Step 5: Run formatter check**

Run: `uv run ruff format --check .`
Expected: PASS - Code is properly formatted

**Step 6: Run type checker**

Run: `uv run mypy src/rag src/ingestion`
Expected: PASS - No type errors

**Step 7: Test application startup**

Run: `uv run python -m src.cli.serve --help`
Expected: Help output without errors

**Step 8: Commit verification results**

Create `docs/reports/2026-03/20260320-code-review-remediation-verification.md`:

```markdown
# Code Review Remediation Verification Report

## Date
2026-03-20

## Verification Summary

All critical issues and recommendations from code review have been addressed.

## Completed Tasks

### 1. Dependency Conflict (CRITICAL)
- Status: RESOLVED
- Action: Verified pypdf>=4.0,<6.0 is compatible with camelot-py>=0.12.0
- Result: `uv sync` succeeds without errors

### 2. Deleted Pipeline File (CRITICAL)
- Status: VERIFIED
- Action: Confirmed src.usecases.pipeline exists and all imports updated
- Result: No broken imports found

### 3. Hardcoded URLs (IMPORTANT)
- Status: RESOLVED
- Action: Extracted all URLs to config/ingestion_urls.yaml
- Result: download_web.py now loads from configuration

### 4. Configuration Validation (IMPORTANT)
- Status: RESOLVED
- Action: Created src/rag/config_validation.py
- Result: All retrieval configs validated before use

### 5. Frontend Source Normalization (SUGGESTION)
- Status: RESOLVED
- Action: Extracted to frontend/src/lib/utils/sourceDisplay.ts
- Result: +page.svelte simplified by ~100 lines

## Test Results

- Backend tests: PASS
- Frontend tests: PASS
- E2E tests: PASS
- Linting: PASS
- Type checking: PASS

## Remaining Work

Future improvements identified in CONCERNS.md:
- Break down large files (evaluation.py, runtime.py, eval/+page.svelte)
- Add performance benchmarks
- Consider configuration profiles
```

**Step 9: Commit**

```bash
git add docs/reports/2026-03/20260320-code-review-remediation-verification.md
git commit -m "docs: add code review remediation verification report"
```

---

## Task 7: Update Documentation

**Files:**
- Modify: `.planning/codebase/CONCERNS.md`

**Step 1: Update CONCERNS.md**

Add section at end of file:

```markdown
## Recent Improvements (2026-03-20)

### Addressed Issues
- ✅ **Dependency conflict**: Verified pypdf/camelot-py compatibility
- ✅ **Hardcoded URLs**: Extracted to config/ingestion_urls.yaml
- ✅ **Configuration validation**: Added src/rag/config_validation.py
- ✅ **Frontend normalization**: Extracted to frontend/src/lib/utils/sourceDisplay.ts

### Remaining High-Priority Work
- Break down `frontend/src/routes/eval/+page.svelte` (2439 lines)
- Address `src/app/routes/evaluation.py` complexity (862 lines)
- Refactor `src/rag/runtime.py` (816 lines) - partially improved with validation
```

**Step 2: Commit**

```bash
git add .planning/codebase/CONCERNS.md
git commit -m "docs: update CONCERNS.md with recent improvements"
```

---

## Summary

This plan addresses all critical and important issues from the code review:

1. **CRITICAL**: Dependency conflict verification and fix
2. **CRITICAL**: Deleted pipeline file impact verification
3. **IMPORTANT**: Extract hardcoded URLs to YAML configuration
4. **IMPORTANT**: Add runtime configuration validation
5. **SUGGESTION**: Extract frontend source normalization logic
6. **VERIFICATION**: Full test suite validation
7. **DOCUMENTATION**: Update concerns tracking

Each task follows TDD principles with minimal, focused changes.
