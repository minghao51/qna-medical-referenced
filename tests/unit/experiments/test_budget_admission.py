import json
from datetime import UTC, datetime

import pytest

from src.cli import eval_pipeline
from src.evals.usage import (
    build_usage_summary,
    paid_benchmark_budget_status,
    paid_operation_budget_status,
    summarize_monthly_usage,
)


def test_benchmark_wrapper_preserves_legacy_status_dict():
    record = build_usage_summary(
        "run-1",
        usage_by_role={"generator": {"total_tokens": 4}},
        cash_actual_usd=1.0,
        quota_applicable=False,
        recorded_at=datetime(2026, 10, 2, tzinfo=UTC),
    )

    status = paid_benchmark_budget_status([record], utc_month="2026-10", overage_off_confirmed=True)

    assert status == {
        "utc_month": "2026-10",
        "monthly_ceiling_usd": 20.0,
        "known_cash_usd": 1.0,
        "quota_value_usd": None,
        "existing_subscription_usd": None,
        "unknown_usage_count": 0,
        "unknown_cash_count": 0,
        "overage_off_confirmed": True,
        "allowed": True,
        "reasons": [],
        "limitations": [
            "Does not include in-flight, delayed, or outside-repository charges",
            "Quota-value estimates and existing subscriptions are not incremental cash",
            "Recorded usage and estimates do not guarantee actual provider billing totals",
        ],
    }


def test_generalized_admission_names_operation_and_uses_legacy_fail_closed_reasons():
    record = build_usage_summary("run-unknown", recorded_at=datetime(2026, 10, 2, tzinfo=UTC))
    benchmark = paid_benchmark_budget_status(
        [record], utc_month="2026-10", overage_off_confirmed=False
    )
    diagnostic = paid_operation_budget_status(
        [record],
        utc_month="2026-10",
        operation="diagnostic",
        overage_off_confirmed=False,
    )

    assert diagnostic["operation"] == "diagnostic"
    assert diagnostic["allowed"] is False
    assert diagnostic["reasons"] == benchmark["reasons"]
    assert set(diagnostic["reasons"]) == {
        "external_overage_and_auto_top_up_not_confirmed_off",
        "monthly_usage_or_cash_is_incomplete",
    }
    assert {
        "Does not include in-flight, delayed, or outside-repository charges",
        "Quota-value estimates and existing subscriptions are not incremental cash",
        "Recorded usage and estimates do not guarantee actual provider billing totals",
        "Local usage records do not enforce an operational hard spending cap",
        "Automatic provider overage and auto-top-up status are not verified by local records",
        "Existing subscription charges are excluded from the incremental cash ceiling",
        "Interactive chat serving is not budget-gated by these records",
    } <= set(diagnostic["limitations"])


def test_empty_month_and_unknown_usage_remain_fail_closed():
    monthly = summarize_monthly_usage([], utc_month="2026-10")
    status = paid_operation_budget_status(
        [], utc_month="2026-10", operation="benchmark", overage_off_confirmed=True
    )

    assert monthly["known_cash_usd"] is None
    assert monthly["usage_status"] == "incomplete"
    assert status["allowed"] is False
    assert status["reasons"] == [
        "monthly_usage_or_cash_is_incomplete",
        "monthly_run_usage_unavailable",
    ]


def test_offline_diagnostic_reports_each_recorded_paid_operation_without_assessment(
    monkeypatch, tmp_path, capsys
):
    recorded_at = datetime(2026, 10, 2, tzinfo=UTC)
    records = [
        {
            **build_usage_summary(
                "benchmark-run",
                usage_by_role={"generator": {"total_tokens": 2}},
                cash_actual_usd=1.0,
                recorded_at=recorded_at,
            ),
            "execution_mode": "benchmark",
        },
        {
            **build_usage_summary(
                "diagnostic-run",
                usage_by_role={"judge": {"total_tokens": 3}},
                cash_actual_usd=2.0,
                recorded_at=recorded_at,
            ),
            "execution_mode": "diagnostic",
        },
    ]
    summary_path = tmp_path / "usage.json"
    summary_path.write_text(json.dumps({"records": records}), encoding="utf-8")
    monkeypatch.setattr(
        eval_pipeline,
        "run_assessment",
        lambda **kwargs: pytest.fail("usage diagnostics must not run an assessment"),
    )
    monkeypatch.setattr(
        "sys.argv",
        [
            "eval_pipeline",
            "--usage-summary",
            str(summary_path),
            "--usage-month",
            "2026-10",
            "--confirm-overage-off",
        ],
    )

    with pytest.raises(SystemExit) as exc:
        eval_pipeline.main()

    output = json.loads(capsys.readouterr().out)
    admissions = output["operation_admission"]
    assert exc.value.code == 0
    assert set(admissions) == {"benchmark", "diagnostic"}
    assert admissions["benchmark"]["operation"] == "benchmark"
    assert admissions["diagnostic"]["operation"] == "diagnostic"
    assert admissions["benchmark"]["known_cash_usd"] == 3.0
    assert admissions["diagnostic"]["known_cash_usd"] == 3.0


def test_usage_manifest_execution_mode_is_carried_to_its_summary(tmp_path):
    summary_path = tmp_path / "manifest.json"
    summary_path.write_text(
        json.dumps(
            {
                "execution_mode": "diagnostic",
                "usage_summary": build_usage_summary(
                    "diagnostic-run",
                    usage_by_role={"generator": {"total_tokens": 1}},
                    cash_actual_usd=1.0,
                    recorded_at=datetime(2026, 10, 2, tzinfo=UTC),
                ),
            }
        ),
        encoding="utf-8",
    )

    records = eval_pipeline._load_usage_records(summary_path)

    assert records[0]["execution_mode"] == "diagnostic"


def test_generalized_admission_fails_closed_at_recorded_cash_ceiling():
    record = build_usage_summary(
        "run-ceiling",
        usage_by_role={"generator": {"total_tokens": 4}},
        cash_actual_usd=20.0,
        quota_applicable=False,
        recorded_at=datetime(2026, 10, 2, tzinfo=UTC),
    )

    at_default_ceiling = paid_operation_budget_status(
        [record], utc_month="2026-10", operation="diagnostic", overage_off_confirmed=True
    )
    assert at_default_ceiling["allowed"] is False
    assert "recorded_monthly_cash_ceiling_reached" in at_default_ceiling["reasons"]

    under_custom_ceiling = paid_operation_budget_status(
        [record],
        utc_month="2026-10",
        operation="diagnostic",
        overage_off_confirmed=True,
        monthly_ceiling_usd=25.0,
    )
    assert under_custom_ceiling["allowed"] is True
    assert under_custom_ceiling["reasons"] == []
