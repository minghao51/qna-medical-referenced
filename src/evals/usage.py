"""Small, local usage summaries for evaluation and experiment runs.

This module records only provider-reported usage and caller-supplied cash/quota
amounts. It does not price tokens, contact billing services, or persist a ledger.
"""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from datetime import UTC, date, datetime
from typing import Any


def _utc_datetime(value: datetime | None) -> datetime:
    if value is None:
        return datetime.now(UTC)
    if value.tzinfo is None:
        raise ValueError("Usage timestamps must include a timezone")
    return value.astimezone(UTC)


def _amount(value: float | int | None, field: str) -> float | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{field} must be a finite non-negative number or null")
    try:
        amount = float(value)
    except OverflowError:
        raise ValueError(f"{field} must be a finite non-negative number or null") from None
    if not math.isfinite(amount) or amount < 0:
        raise ValueError(f"{field} must be a finite non-negative number or null")
    return amount


def _sum_amounts(values: Sequence[float], field: str) -> float:
    try:
        total = math.fsum(values)
    except OverflowError:
        raise ValueError(f"aggregated {field} must be finite") from None
    if not math.isfinite(total):
        raise ValueError(f"aggregated {field} must be finite")
    return total


def build_usage_summary(
    run_id: str,
    *,
    usage_by_role: Mapping[str, Mapping[str, Any]] | None = None,
    cash_actual_usd: float | None = None,
    cash_estimate_usd: float | None = None,
    quota_value_usd: float | None = None,
    quota_applicable: bool | None = None,
    existing_subscription_usd: float | None = None,
    pricing_source: str | None = None,
    pricing_date: str | None = None,
    unknowns: Sequence[str] = (),
    recorded_at: datetime | None = None,
) -> dict[str, Any]:
    """Create a compact per-run summary without treating absent usage as zero."""
    if not run_id.strip():
        raise ValueError("run_id must not be empty")
    if quota_applicable is not None and not isinstance(quota_applicable, bool):
        raise ValueError("quota_applicable must be a boolean or null")
    recorded = _utc_datetime(recorded_at)
    actual = _amount(cash_actual_usd, "cash_actual_usd")
    estimate = _amount(cash_estimate_usd, "cash_estimate_usd")
    quota = _amount(quota_value_usd, "quota_value_usd")
    subscription = _amount(existing_subscription_usd, "existing_subscription_usd")
    if quota_applicable is False and quota is not None:
        raise ValueError("quota_value_usd cannot be set when quota is not applicable")
    if quota is not None:
        quota_applicable = True
    quota_status = (
        "not_applicable"
        if quota_applicable is False
        else "complete"
        if quota is not None
        else "incomplete"
    )

    roles: dict[str, dict[str, Any]] = {}
    for role, usage in (usage_by_role or {}).items():
        if not role.strip() or not isinstance(usage, Mapping):
            raise ValueError("usage_by_role must map non-empty role names to mappings")
        role_usage: dict[str, Any] = {}
        for field in ("input_tokens", "output_tokens", "total_tokens"):
            value = usage.get(field)
            if value is not None and (
                isinstance(value, bool) or not isinstance(value, int) or value < 0
            ):
                raise ValueError(f"{role}.{field} must be a non-negative integer or null")
            role_usage[field] = value
        role_usage["status"] = str(usage.get("status") or "reported")
        role_usage["source"] = usage.get("source")
        roles[role] = role_usage

    usage_incomplete = not roles or any(
        usage["status"] not in {"reported", "estimated"}
        or all(usage[field] is None for field in ("input_tokens", "output_tokens", "total_tokens"))
        for usage in roles.values()
    )
    cash_status = "incomplete" if actual is None and estimate is None else "complete"
    usage_status = "incomplete" if usage_incomplete else "complete"

    missing = [str(item) for item in unknowns if str(item).strip()]
    for role, usage in roles.items():
        if usage["status"] not in {"reported", "estimated"} or all(
            usage[field] is None for field in ("input_tokens", "output_tokens", "total_tokens")
        ):
            missing.append(f"{role}_usage_unknown")
    if not roles:
        missing.append("provider_usage_unavailable")
    if cash_status == "incomplete":
        missing.append("incremental_cash_unknown")
    if quota_status == "incomplete":
        missing.append("quota_value_unknown")
    return {
        "schema_version": 1,
        "run_id": run_id,
        "utc_month": recorded.strftime("%Y-%m"),
        "recorded_at": recorded.isoformat(),
        "usage_by_role": roles,
        "usage_status": usage_status,
        "cash_status": cash_status,
        "quota_status": quota_status,
        "cash_actual_usd": actual,
        "cash_estimate_usd": estimate,
        "quota_value_usd": quota,
        "quota_applicable": quota_applicable,
        "existing_subscription_usd": subscription,
        "pricing_source": pricing_source,
        "pricing_date": pricing_date,
        "unknowns": sorted(set(missing)),
        "status": "incomplete" if missing else "complete",
    }


def build_manual_adjustment(
    record_id: str,
    *,
    amount_usd: float,
    category: str,
    recorded_at: datetime | None = None,
    note: str | None = None,
) -> dict[str, Any]:
    """Represent one manually reconciled charge as a deduplicatable local record."""
    if not record_id.strip() or category not in {
        "incremental_cash",
        "quota_value",
        "existing_subscription",
    }:
        raise ValueError("Manual adjustment category must be explicitly classified")
    recorded = _utc_datetime(recorded_at)
    amount = _amount(amount_usd, "amount_usd")
    assert amount is not None
    return {
        "schema_version": 1,
        "record_type": "manual_adjustment",
        "record_id": record_id,
        "utc_month": recorded.strftime("%Y-%m"),
        "recorded_at": recorded.isoformat(),
        "category": category,
        "amount_usd": amount,
        "note": note,
    }


def _record_usage_is_complete(record: Mapping[str, Any]) -> bool:
    status = record.get("usage_status")
    if status in {"complete", "incomplete"}:
        return bool(status == "complete")
    roles = record.get("usage_by_role")
    return record.get("status") == "complete" and isinstance(roles, Mapping) and bool(roles)


def summarize_monthly_usage(
    records: Sequence[Mapping[str, Any]], *, utc_month: str
) -> dict[str, Any]:
    """Aggregate runs and adjustments without filling unknown totals with zero."""
    try:
        parsed_month = date.fromisoformat(f"{utc_month}-01")
        if parsed_month.strftime("%Y-%m") != utc_month:
            raise ValueError
    except ValueError:
        raise ValueError("utc_month must use YYYY-MM") from None

    latest_runs: dict[str, Mapping[str, Any]] = {}
    adjustments: dict[str, Mapping[str, Any]] = {}
    for record in records:
        if record.get("utc_month") != utc_month:
            continue
        if record.get("record_type") == "manual_adjustment":
            record_id = record.get("record_id")
            if isinstance(record_id, str) and record_id:
                previous = adjustments.get(record_id)
                if previous is None or str(record.get("recorded_at", "")) > str(
                    previous.get("recorded_at", "")
                ):
                    adjustments[record_id] = record
            continue
        run_id = record.get("run_id")
        if not isinstance(run_id, str) or not run_id:
            continue
        previous = latest_runs.get(run_id)
        if previous is None or str(record.get("recorded_at", "")) > str(
            previous.get("recorded_at", "")
        ):
            latest_runs[run_id] = record

    actual_values: list[float] = []
    estimate_values: list[float] = []
    quota_values: list[float] = []
    unknown_usage_run_ids: list[str] = []
    unknown_cash_run_ids: list[str] = []
    unknown_quota_run_ids: list[str] = []
    unknown_other_run_ids: list[str] = []
    subscription_values: list[float | None] = []
    has_applicable_quota = False

    for run_id, record in latest_runs.items():
        actual = _amount(record.get("cash_actual_usd"), "cash_actual_usd")
        estimate = _amount(record.get("cash_estimate_usd"), "cash_estimate_usd")
        if actual is None and estimate is None:
            unknown_cash_run_ids.append(run_id)
        elif actual is not None:
            actual_values.append(actual)
        else:
            assert estimate is not None
            estimate_values.append(estimate)

        if not _record_usage_is_complete(record):
            unknown_usage_run_ids.append(run_id)
        if record.get("status") != "complete" and all(
            record.get(key) == "complete" for key in ("usage_status", "cash_status", "quota_status")
        ):
            unknown_other_run_ids.append(run_id)

        quota = _amount(record.get("quota_value_usd"), "quota_value_usd")
        quota_applicable = record.get("quota_applicable")
        if quota_applicable is not None and not isinstance(quota_applicable, bool):
            raise ValueError("quota_applicable must be a boolean or null")
        if quota_applicable is False and quota is not None:
            raise ValueError("quota_value_usd cannot be set when quota is not applicable")
        if quota is not None:
            has_applicable_quota = True
            quota_values.append(quota)
        elif quota_applicable is False:
            pass
        else:
            has_applicable_quota = has_applicable_quota or quota_applicable is True
            unknown_quota_run_ids.append(run_id)

        subscription_values.append(
            _amount(record.get("existing_subscription_usd"), "existing_subscription_usd")
        )

    adjustment_values: dict[str, list[float]] = {
        "incremental_cash": [],
        "quota_value": [],
        "existing_subscription": [],
    }
    for record in adjustments.values():
        category = record.get("category")
        if category in adjustment_values:
            amount = _amount(record.get("amount_usd"), "amount_usd")
            assert amount is not None
            adjustment_values[category].append(amount)

    actual_values.extend(adjustment_values["incremental_cash"])
    quota_values.extend(adjustment_values["quota_value"])
    has_applicable_quota = has_applicable_quota or bool(adjustment_values["quota_value"])
    adjustment_totals = {
        category: _sum_amounts(values, category) for category, values in adjustment_values.items()
    }

    known_actual = _sum_amounts(actual_values, "cash_actual_usd") if actual_values else None
    known_estimate = _sum_amounts(estimate_values, "cash_estimate_usd") if estimate_values else None
    cash_observed = known_actual is not None or known_estimate is not None
    known_cash = (
        _sum_amounts(
            [value for value in (known_actual, known_estimate) if value is not None],
            "known_cash_usd",
        )
        if cash_observed
        else None
    )
    cash_status = "complete" if latest_runs and not unknown_cash_run_ids else "incomplete"
    cash_total = known_cash if cash_status == "complete" else None

    known_quota = _sum_amounts(quota_values, "quota_value_usd") if quota_values else None
    if not latest_runs:
        quota_status = "incomplete"
    elif unknown_quota_run_ids:
        quota_status = "incomplete"
    elif not has_applicable_quota:
        quota_status = "not_applicable"
    else:
        quota_status = "complete"
    quota_total = known_quota if quota_status == "complete" else None

    if adjustment_values["existing_subscription"]:
        existing_subscription = adjustment_totals["existing_subscription"]
        subscription_status = "reconciled"
        subscription_source = "manual_adjustments"
        subscription_is_estimate = False
        unknown_subscription_run_ids: list[str] = []
    elif latest_runs and all(value is not None for value in subscription_values):
        complete_fees = [value for value in subscription_values if value is not None]
        if all(value == complete_fees[0] for value in complete_fees):
            existing_subscription = complete_fees[0]
            subscription_status = "estimated"
            subscription_source = "consistent_run_fee_estimate"
            subscription_is_estimate = True
            unknown_subscription_run_ids = []
        else:
            existing_subscription = None
            subscription_status = "incomplete"
            subscription_source = None
            subscription_is_estimate = False
            unknown_subscription_run_ids = list(latest_runs)
    else:
        existing_subscription = None
        subscription_status = "incomplete"
        subscription_source = None
        subscription_is_estimate = False
        unknown_subscription_run_ids = list(latest_runs)

    unknown_usage = set(unknown_usage_run_ids)
    unknown_cash = set(unknown_cash_run_ids)
    unknown_quota = set(unknown_quota_run_ids)
    unknown_subscription = set(unknown_subscription_run_ids)
    unknown_other = set(unknown_other_run_ids)
    unknown_ids = sorted(
        unknown_usage | unknown_cash | unknown_quota | unknown_subscription | unknown_other
    )
    usage_status = "complete" if latest_runs and not unknown_usage else "incomplete"
    unknown_accounting_ids = unknown_usage | unknown_cash | unknown_quota
    overall_status = (
        "complete"
        if usage_status == "complete"
        and cash_status == "complete"
        and quota_status in {"complete", "not_applicable"}
        and subscription_status != "incomplete"
        and not unknown_other
        else "incomplete"
    )

    return {
        "utc_month": utc_month,
        "run_count": len(latest_runs),
        "manual_adjustment_count": len(adjustments),
        "cash_actual_usd": known_actual,
        "cash_estimate_usd": known_estimate,
        "known_cash_usd": known_cash,
        "cash_total_usd": cash_total,
        "usage_status": usage_status,
        "cash_status": cash_status,
        "quota_status": quota_status,
        "known_quota_value_usd": known_quota,
        "quota_value_usd": quota_total,
        "existing_subscription_usd": existing_subscription,
        "existing_subscription_status": subscription_status,
        "existing_subscription_source": subscription_source,
        "existing_subscription_is_estimate": subscription_is_estimate,
        "unknown_usage_count": len(unknown_usage),
        "unknown_cash_count": len(unknown_cash),
        "unknown_quota_count": len(unknown_quota),
        "unknown_subscription_count": len(unknown_subscription),
        "unknown_other_count": len(unknown_other),
        "unknown_accounting_count": len(unknown_accounting_ids),
        "unknown_usage_run_ids": sorted(unknown_usage),
        "unknown_cash_run_ids": sorted(unknown_cash),
        "unknown_quota_run_ids": sorted(unknown_quota),
        "unknown_run_ids": unknown_ids,
        "status": overall_status,
    }


def paid_operation_budget_status(
    records: Sequence[Mapping[str, Any]],
    *,
    utc_month: str,
    operation: str,
    monthly_ceiling_usd: float = 20.0,
    overage_off_confirmed: bool = False,
) -> dict[str, Any]:
    """Fail closed for a named paid operation against the shared monthly records."""
    if not operation.strip():
        raise ValueError("operation must not be empty")
    ceiling = _amount(monthly_ceiling_usd, "monthly_ceiling_usd")
    assert ceiling is not None
    monthly = summarize_monthly_usage(records, utc_month=utc_month)
    reasons: list[str] = []
    if not overage_off_confirmed:
        reasons.append("external_overage_and_auto_top_up_not_confirmed_off")
    if monthly["usage_status"] != "complete" or monthly["cash_status"] != "complete":
        reasons.append("monthly_usage_or_cash_is_incomplete")
    if monthly["run_count"] == 0:
        reasons.append("monthly_run_usage_unavailable")
    if monthly["known_cash_usd"] is not None and monthly["known_cash_usd"] >= ceiling:
        reasons.append("recorded_monthly_cash_ceiling_reached")
    return {
        "utc_month": utc_month,
        "monthly_ceiling_usd": ceiling,
        "known_cash_usd": monthly["known_cash_usd"],
        "quota_value_usd": monthly["quota_value_usd"],
        "existing_subscription_usd": monthly["existing_subscription_usd"],
        "unknown_usage_count": monthly["unknown_usage_count"],
        "unknown_cash_count": monthly["unknown_cash_count"],
        "overage_off_confirmed": overage_off_confirmed,
        "allowed": not reasons,
        "reasons": reasons,
        "limitations": [
            "Does not include in-flight, delayed, or outside-repository charges",
            "Quota-value estimates and existing subscriptions are not incremental cash",
            "Recorded usage and estimates do not guarantee actual provider billing totals",
            "Local usage records do not enforce an operational hard spending cap",
            "Automatic provider overage and auto-top-up status are not verified by local records",
            "Existing subscription charges are excluded from the incremental cash ceiling",
            "Interactive chat serving is not budget-gated by these records",
        ],
        "operation": operation,
    }


def paid_benchmark_budget_status(
    records: Sequence[Mapping[str, Any]],
    *,
    utc_month: str,
    monthly_ceiling_usd: float = 20.0,
    overage_off_confirmed: bool = False,
) -> dict[str, Any]:
    """Preserve the benchmark CLI's legacy status shape and limitations."""
    status = paid_operation_budget_status(
        records,
        utc_month=utc_month,
        operation="benchmark",
        monthly_ceiling_usd=monthly_ceiling_usd,
        overage_off_confirmed=overage_off_confirmed,
    )
    status.pop("operation")
    status["limitations"] = status["limitations"][:3]
    return status
