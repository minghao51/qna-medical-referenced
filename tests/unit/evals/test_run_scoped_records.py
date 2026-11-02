"""Selected-run artifact safety: confinement, no latest fallback, bounded reads."""

import json
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from src.app.routes import evaluation
from src.evals.artifact_service import EvaluationService, InvalidRunDirectoryError


def _auth_request():
    return SimpleNamespace(state=SimpleNamespace(auth=object()))


def _run_dir(root, name, *, step_metrics=None, l6_lines=None, query_count=1):
    run_dir = root / name
    run_dir.mkdir()
    (run_dir / "summary.json").write_text(
        json.dumps({"status": "ok", "duration_s": 1, "failed_thresholds_count": 0}),
        encoding="utf-8",
    )
    (run_dir / "retrieval_metrics.json").write_text(
        json.dumps({"query_count": query_count}), encoding="utf-8"
    )
    if step_metrics is not None:
        (run_dir / "step_metrics.json").write_text(json.dumps(step_metrics), encoding="utf-8")
    if l6_lines is not None:
        (run_dir / "l6_answer_quality.jsonl").write_text(
            "\n".join(l6_lines) + "\n", encoding="utf-8"
        )
    return run_dir


@pytest.fixture
def scoped_runs(tmp_path, monkeypatch):
    evals_dir = tmp_path / "evals"
    evals_dir.mkdir()
    latest = _run_dir(
        evals_dir,
        "20260102T000000Z_latest",
        step_metrics={"l3": {"records": [{"id": "latest"}], "timing_ms": 10}},
        l6_lines=[json.dumps({"query_id": "latest"})],
    )
    older = _run_dir(
        evals_dir,
        "20260101T000000Z_older",
        step_metrics={"l3": {"records": [{"id": "older"}], "timing_ms": 20}},
        l6_lines=[json.dumps({"query_id": "older"}), json.dumps({"query_id": "older-2"})],
    )
    (evals_dir / "latest_run.txt").write_text(str(latest), encoding="utf-8")
    monkeypatch.setattr(evaluation, "EVALS_DIR", evals_dir)
    monkeypatch.setattr(evaluation, "LATEST_POINTER", evals_dir / "latest_run.txt")
    service = EvaluationService(evals_dir=evals_dir, latest_pointer=evals_dir / "latest_run.txt")
    return SimpleNamespace(evals_dir=evals_dir, latest=latest, older=older, service=service)


def test_explicit_run_is_selected_instead_of_latest(scoped_runs):
    result = scoped_runs.service.load_step_records("l3", 10, scoped_runs.older.name)
    assert result["run_dir"] == scoped_runs.older.name
    assert result["records"] == [{"id": "older"}]
    assert result["total_count"] == 1

    l6 = scoped_runs.service.load_l6_records(10, scoped_runs.older.name)
    assert l6["run_dir"] == scoped_runs.older.name
    assert [record["query_id"] for record in l6["records"]] == ["older", "older-2"]


def test_omitted_run_keeps_latest_behavior(scoped_runs):
    result = scoped_runs.service.load_step_records("l3", 10)
    assert result["run_dir"] == scoped_runs.latest.name
    assert result["records"] == [{"id": "latest"}]


def test_explicit_missing_run_never_falls_back_to_latest(scoped_runs):
    with pytest.raises(FileNotFoundError):
        scoped_runs.service.load_step_records("l3", 10, "20260101T000000Z_missing")

    with pytest.raises(HTTPException) as exc_info:
        evaluation.get_step_records(
            "l3", _auth_request(), limit=10, run_dir="20260101T000000Z_missing"
        )
    assert exc_info.value.status_code == 404


@pytest.mark.parametrize(
    "name",
    [
        "",
        ".",
        "..",
        "../escape",
        "nested/run",
        "nested\\run",
        "/abs/run",
        "20260102T000000Z_latest/..",
    ],
)
def test_traversal_and_separators_are_rejected(scoped_runs, name):
    with pytest.raises(InvalidRunDirectoryError):
        scoped_runs.service.resolve_run_dir(name)

    with pytest.raises(HTTPException) as exc_info:
        evaluation.get_step_records("l3", _auth_request(), limit=10, run_dir=name)
    assert exc_info.value.status_code == 400


def test_symlink_escape_is_rejected(scoped_runs, tmp_path):
    outside = tmp_path / "outside-run"
    outside.mkdir()
    (outside / "summary.json").write_text("{}", encoding="utf-8")
    link = scoped_runs.evals_dir / "20260103T000000Z_escape"
    link.symlink_to(outside, target_is_directory=True)

    with pytest.raises(InvalidRunDirectoryError):
        scoped_runs.service.load_step_records("l3", 10, link.name)


def test_existing_run_lookups_are_confined(scoped_runs, tmp_path):
    outside = tmp_path / "outside.jsonl"
    outside.write_text('{"query_id": "outside"}\n', encoding="utf-8")

    for lookup in (
        lambda: scoped_runs.service.load_evaluation_run("../outside"),
        lambda: scoped_runs.service.load_answer_quality_details("../outside"),
    ):
        with pytest.raises(InvalidRunDirectoryError):
            lookup()

    with pytest.raises(HTTPException) as exc_info:
        evaluation.get_answer_quality_details("..", _auth_request())
    assert exc_info.value.status_code == 400


def test_l6_reads_are_bounded_and_skip_malformed_lines(scoped_runs, monkeypatch):
    run_dir = scoped_runs.latest
    (run_dir / "l6_answer_quality.jsonl").write_text(
        "\n".join(
            [
                json.dumps({"id": 1}),
                "not-json",
                json.dumps({"id": 2, "pad": "x" * 20}),
                json.dumps({"id": 3, "pad": "y" * 20}),
                "",
            ]
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr("src.evals.artifact_service._MAX_JSONL_RECORD_CHARS", 15)

    result = scoped_runs.service.load_l6_records(2, run_dir.name)
    assert result["run_dir"] == run_dir.name
    assert result["records"] == [{"id": 1}]
    assert result["total_count"] == 4
    assert result["malformed_count"] == 3


def test_step_metrics_echo_the_selected_run(scoped_runs):
    result = scoped_runs.service.load_step_metrics("l3", scoped_runs.older.name)
    assert result == {
        "records": [{"id": "older"}],
        "timing_ms": 20,
        "run_dir": scoped_runs.older.name,
    }


def test_scoped_routes_echo_selected_run(scoped_runs):
    records = evaluation.get_step_records(
        "l3", _auth_request(), limit=10, run_dir=scoped_runs.older.name
    )
    assert records["run_dir"] == scoped_runs.older.name

    l6 = evaluation.get_l6_records(_auth_request(), limit=10, run_dir=scoped_runs.older.name)
    assert l6["run_dir"] == scoped_runs.older.name

    metrics = evaluation.get_step_metrics("l3", _auth_request(), run_dir=scoped_runs.older.name)
    assert metrics["run_dir"] == scoped_runs.older.name


def test_scoped_routes_require_authentication(scoped_runs):
    unauthenticated = SimpleNamespace(state=SimpleNamespace())
    with pytest.raises(HTTPException) as exc_info:
        evaluation.get_l6_records(unauthenticated, limit=10)
    assert exc_info.value.status_code == 401
