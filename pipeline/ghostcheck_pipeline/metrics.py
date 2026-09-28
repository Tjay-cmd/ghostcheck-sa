"""Employer metric objects (contract §7, "Metric object")."""
from __future__ import annotations

import statistics
from decimal import ROUND_HALF_UP, Decimal


def _pct(numerator: int, denominator: int) -> int:
    return int((Decimal(numerator * 100) / Decimal(denominator)).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def unavailable(unit: str, reason: str, available_from=None) -> dict:
    return {"value": None, "unit": unit, "numerator": None, "denominator": None,
            "window_label": None, "window_start": None, "available": False,
            "unavailable_reason": reason, "available_from": available_from}


def count_metric(value: int) -> dict:
    return {"value": value, "unit": "count", "numerator": None, "denominator": None,
            "window_label": None, "window_start": None, "available": True,
            "unavailable_reason": None, "available_from": None}


def days_metric(value: int) -> dict:
    return {"value": value, "unit": "days", "numerator": None, "denominator": None,
            "window_label": None, "window_start": None, "available": True,
            "unavailable_reason": None, "available_from": None}


def percent_metric(numerator: int, denominator: int, window_label=None, window_start=None) -> dict:
    value = _pct(numerator, denominator) if denominator else None
    return {"value": value, "unit": "percent", "numerator": numerator, "denominator": denominator,
            "window_label": window_label, "window_start": window_start, "available": True,
            "unavailable_reason": None, "available_from": None}


def median_days_seen(open_days_seen: list[int]) -> int:
    return int(statistics.median(open_days_seen))
