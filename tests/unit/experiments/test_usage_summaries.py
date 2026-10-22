from datetime import UTC, datetime

from src.evals.usage import (
    build_manual_adjustment,
    build_usage_summary,
    paid_benchmark_budget_status,
    summarize_monthly_usage,
)


def test_usage_summary_records_utc_month_and_keeps_quota_separate_from_cash():
    summary = build_usage_summary(
        "run-1",
        usage_by_role={
            "generator": {
                "input_tokens": 10,
                "output_tokens": 4,
                "total_tokens": 14,
                "source": "provider",
            }
        },
        cash_estimate_usd=1.25,
        quota_value_usd=3.5,
        existing_subscription_usd=20,
        pricing_source="manual estimate",
        pricing_date="2026-10-01",
        recorded_at=datetime(2026, 11, 1, 1, tzinfo=UTC),
    )

    assert summary["utc_month"] == "2026-11"
    assert summary["cash_actual_usd"] is None
    assert summary["cash_estimate_usd"] == 1.25
    assert summary["quota_value_usd"] == 3.5
    assert summary["existing_subscription_usd"] == 20
    assert summary["status"] == "complete"


def test_missing_usage_and_cash_are_unknown_not_zero():
    summary = build_usage_summary("run-unknown", recorded_at=datetime(2026, 10, 4, tzinfo=UTC))

    assert summary["cash_actual_usd"] is None
    assert summary["cash_estimate_usd"] is None
    assert summary["usage_by_role"] == {}
    assert summary["status"] == "incomplete"
    assert "provider_usage_unavailable" in summary["unknowns"]
    assert "incremental_cash_unknown" in summary["unknowns"]


def test_monthly_summary_deduplicates_run_to_latest_record_and_filters_month():
    older = build_usage_summary(
        "run-1",
        usage_by_role={"generator": {"total_tokens": 10}},
        cash_actual_usd=2,
        recorded_at=datetime(2026, 10, 2, tzinfo=UTC),
    )
    latest = build_usage_summary(
        "run-1",
        usage_by_role={"generator": {"total_tokens": 20}},
        cash_actual_usd=3,
        quota_value_usd=4,
        recorded_at=datetime(2026, 10, 3, tzinfo=UTC),
    )
    other_month = build_usage_summary(
        "run-2",
        usage_by_role={"judge": {"total_tokens": 5}},
        cash_actual_usd=8,
        recorded_at=datetime(2026, 11, 1, tzinfo=UTC),
    )

    monthly = summarize_monthly_usage([older, latest, other_month], utc_month="2026-10")

    assert monthly["run_count"] == 1
    assert monthly["cash_actual_usd"] == 3
    assert monthly["quota_value_usd"] == 4
    assert monthly["known_cash_usd"] == 3


def test_adjustments_are_single_use_and_subscription_and_quota_are_not_cash():
    run = build_usage_summary(
        "run-1",
        usage_by_role={"generator": {"total_tokens": 1}},
        cash_actual_usd=2,
        quota_value_usd=6,
        existing_subscription_usd=20,
        recorded_at=datetime(2026, 10, 2, tzinfo=UTC),
    )
    adjustment = build_manual_adjustment(
        "console-reconcile-1",
        amount_usd=1.5,
        category="incremental_cash",
        recorded_at=datetime(2026, 10, 3, tzinfo=UTC),
    )

    monthly = summarize_monthly_usage([run, adjustment, adjustment], utc_month="2026-10")

    assert monthly["cash_actual_usd"] == 3.5
    assert monthly["quota_value_usd"] == 6
    assert monthly["existing_subscription_usd"] == 20
    assert monthly["manual_adjustment_count"] == 1

    budget = paid_benchmark_budget_status(
        [run, adjustment],
        utc_month="2026-10",
        monthly_ceiling_usd=4,
        overage_off_confirmed=True,
    )
    assert budget["known_cash_usd"] == 3.5
    assert budget["quota_value_usd"] == 6
    assert budget["existing_subscription_usd"] == 20


def test_unknown_usage_or_missing_overage_confirmation_blocks_new_paid_benchmark():
    record = build_usage_summary("run-unknown", recorded_at=datetime(2026, 10, 2, tzinfo=UTC))

    status = paid_benchmark_budget_status([record], utc_month="2026-10", overage_off_confirmed=True)

    assert status["allowed"] is False
    assert "monthly_usage_or_cash_is_incomplete" in status["reasons"]
    assert status["quota_value_usd"] is None


def test_empty_month_history_does_not_prove_zero_spend():
    monthly = summarize_monthly_usage([], utc_month="2026-10")
    status = paid_benchmark_budget_status([], utc_month="2026-10", overage_off_confirmed=True)

    assert monthly["known_cash_usd"] is None
    assert monthly["quota_value_usd"] is None
    assert monthly["usage_status"] == "incomplete"
    assert monthly["cash_status"] == "incomplete"
    assert monthly["quota_status"] == "incomplete"
    assert status["allowed"] is False
    assert "monthly_run_usage_unavailable" in status["reasons"]


def test_missing_quota_stays_unknown_while_known_quota_subtotal_is_reported():
    known = build_usage_summary(
        "run-known",
        usage_by_role={"generator": {"total_tokens": 1}},
        cash_actual_usd=1,
        quota_value_usd=4,
        recorded_at=datetime(2026, 10, 2, tzinfo=UTC),
    )
    unknown = build_usage_summary(
        "run-quota-unknown",
        usage_by_role={"generator": {"total_tokens": 1}},
        cash_actual_usd=1,
        quota_applicable=True,
        recorded_at=datetime(2026, 10, 3, tzinfo=UTC),
    )

    monthly = summarize_monthly_usage([known, unknown], utc_month="2026-10")

    assert monthly["usage_status"] == "complete"
    assert monthly["cash_status"] == "complete"
    assert monthly["quota_status"] == "incomplete"
    assert monthly["known_quota_value_usd"] == 4
    assert monthly["quota_value_usd"] is None
    assert monthly["unknown_quota_count"] == 1


def test_explicitly_not_applicable_quota_is_not_reported_as_zero():
    record = build_usage_summary(
        "run-no-quota",
        usage_by_role={"generator": {"total_tokens": 1}},
        cash_actual_usd=1,
        quota_applicable=False,
        recorded_at=datetime(2026, 10, 2, tzinfo=UTC),
    )

    monthly = summarize_monthly_usage([record], utc_month="2026-10")

    assert record["quota_status"] == "not_applicable"
    assert monthly["quota_status"] == "not_applicable"
    assert monthly["known_quota_value_usd"] is None
    assert monthly["quota_value_usd"] is None
    assert monthly["unknown_quota_count"] == 0


def test_repeated_fixed_subscription_fee_is_counted_once_as_an_estimate():
    runs = [
        build_usage_summary(
            f"run-{number}",
            usage_by_role={"generator": {"total_tokens": 1}},
            cash_actual_usd=1,
            quota_applicable=False,
            existing_subscription_usd=20,
            recorded_at=datetime(2026, 10, number, tzinfo=UTC),
        )
        for number in (2, 3)
    ]

    monthly = summarize_monthly_usage(runs, utc_month="2026-10")

    assert monthly["existing_subscription_usd"] == 20
    assert monthly["existing_subscription_status"] == "estimated"
    assert monthly["existing_subscription_source"] == "consistent_run_fee_estimate"
    assert monthly["existing_subscription_is_estimate"] is True


def test_manual_subscription_adjustment_overrides_repeated_run_fee():
    runs = [
        build_usage_summary(
            f"run-{number}",
            usage_by_role={"generator": {"total_tokens": 1}},
            cash_actual_usd=1,
            quota_applicable=False,
            existing_subscription_usd=20,
            recorded_at=datetime(2026, 10, number, tzinfo=UTC),
        )
        for number in (2, 3)
    ]
    adjustment = build_manual_adjustment(
        "subscription-october",
        amount_usd=25,
        category="existing_subscription",
        recorded_at=datetime(2026, 10, 4, tzinfo=UTC),
    )

    monthly = summarize_monthly_usage([*runs, adjustment], utc_month="2026-10")

    assert monthly["existing_subscription_usd"] == 25
    assert monthly["existing_subscription_status"] == "reconciled"
    assert monthly["existing_subscription_source"] == "manual_adjustments"
    assert monthly["existing_subscription_is_estimate"] is False


def test_mixed_or_missing_run_subscription_fees_remain_unknown():
    runs = [
        build_usage_summary(
            "run-fee-known",
            usage_by_role={"generator": {"total_tokens": 1}},
            cash_actual_usd=1,
            quota_applicable=False,
            existing_subscription_usd=20,
            recorded_at=datetime(2026, 10, 2, tzinfo=UTC),
        ),
        build_usage_summary(
            "run-fee-mixed",
            usage_by_role={"generator": {"total_tokens": 1}},
            cash_actual_usd=1,
            quota_applicable=False,
            existing_subscription_usd=21,
            recorded_at=datetime(2026, 10, 3, tzinfo=UTC),
        ),
        build_usage_summary(
            "run-fee-missing",
            usage_by_role={"generator": {"total_tokens": 1}},
            cash_actual_usd=1,
            quota_applicable=False,
            recorded_at=datetime(2026, 10, 4, tzinfo=UTC),
        ),
    ]

    monthly = summarize_monthly_usage(runs, utc_month="2026-10")

    assert monthly["existing_subscription_usd"] is None
    assert monthly["existing_subscription_status"] == "incomplete"
    assert monthly["unknown_subscription_count"] == 3


def test_numeric_amounts_reject_boolean_nonfinite_and_overflowing_values():
    for invalid in (True, float("nan"), float("inf"), -1, 10**1000):
        try:
            build_usage_summary("run-invalid", cash_actual_usd=invalid)
        except ValueError:
            pass
        else:
            raise AssertionError(f"accepted invalid amount: {invalid!r}")


def test_recorded_ceiling_and_overage_confirmation_are_separate_guards():
    record = build_usage_summary(
        "run-1",
        usage_by_role={"generator": {"total_tokens": 1}},
        cash_actual_usd=20,
        recorded_at=datetime(2026, 10, 2, tzinfo=UTC),
    )

    at_ceiling = paid_benchmark_budget_status(
        [record], utc_month="2026-10", overage_off_confirmed=True
    )
    without_confirmation = paid_benchmark_budget_status(
        [record], utc_month="2026-10", overage_off_confirmed=False
    )

    assert at_ceiling["allowed"] is False
    assert "recorded_monthly_cash_ceiling_reached" in at_ceiling["reasons"]
    assert "external_overage_and_auto_top_up_not_confirmed_off" in without_confirmation["reasons"]
