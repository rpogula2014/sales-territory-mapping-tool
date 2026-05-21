"""Infer a dynamic filter schema from a sample of merged location rows.

Plan §10b inference rules:
- boolean-like ("Y" / "N" / true / false) → toggle
- numeric                                  → range with min/max
- string, ≤20 distinct                     → multiselect
- string, >20 distinct                     → text (contains-search)
- string with `*` separator                → multiselect-tokens
- arrays / nested objects                  → skipped
- known IDs and lat/lng                    → skipped
"""

from __future__ import annotations

from typing import Any

# Fields excluded from filter inference entirely.
_EXCLUDED: frozenset[str] = frozenset(
    {
        "siteUseID",
        "customerId",
        "primaryDcId",
        "primarySalesRepId",
        "primary_dc_id",
        "customer_cd",
        "location_cd",
        "siteUseStatus",
        "siteUseCode",
        "latitude",
        "longitude",
        "address",
        "lat_source",
        "delivery_tier",
    }
)

# Friendly labels for fields we know about (everything else gets a generated label).
_LABELS: dict[str, str] = {
    "locationNumber": "Location #",
    "salesrepName": "Live seller",
    "creditHold": "Credit hold",
    "marketingProgAtd": "Marketing — ATD",
    "marketingProgVendor": "Marketing — Vendor",
    "dba_name": "DBA name",
    "city_name": "City",
    "state_cd": "State",
    "county_name": "County",
    "zip_cd": "ZIP",
    "delivery_tier": "Delivery tier",
    "tire_pros": "Tire Pros",
    "customer_group_name": "Customer group",
    "customer_class_name": "Customer class",
    "customer_channel_name": "Customer channel",
    "mtdsales": "MTD sales",
    "ytdsales": "YTD sales",
    "priorytdsales": "Prior YTD sales",
    "mtdunits": "MTD units",
    "ytdunits": "YTD units",
}


def _label(field: str) -> str:
    return _LABELS.get(field, field.replace("_", " ").title())


def _is_bool_like(value: Any) -> bool:
    if isinstance(value, bool):
        return True
    if isinstance(value, str):
        return value.strip().upper() in {"Y", "N", "TRUE", "FALSE"}
    return False


def _tokenize(value: str) -> list[str]:
    return [t for t in value.split("*") if t]


def infer_schema(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Return ordered descriptors for the filter sidebar."""
    if not rows:
        return []

    fields: dict[str, list[Any]] = {}
    for row in rows:
        for key, value in row.items():
            if key in _EXCLUDED:
                continue
            if value is None:
                continue
            fields.setdefault(key, []).append(value)

    descriptors: list[dict[str, Any]] = []

    for field, values in fields.items():
        non_null = [v for v in values if v is not None and v != ""]
        if not non_null:
            continue

        # Skip arrays / dicts entirely.
        if any(isinstance(v, (list, dict)) for v in non_null):
            continue

        # Toggle: predominantly boolean-like.
        if all(_is_bool_like(v) for v in non_null):
            descriptors.append({"field": field, "label": _label(field), "control": "toggle"})
            continue

        # Number: every non-null value is numeric and not bool.
        if all(isinstance(v, (int, float)) and not isinstance(v, bool) for v in non_null):
            descriptors.append(
                {
                    "field": field,
                    "label": _label(field),
                    "control": "range",
                    "min": float(min(non_null)),
                    "max": float(max(non_null)),
                }
            )
            continue

        # String: decide multiselect / tokens / text.
        if all(isinstance(v, str) for v in non_null):
            # Multi-value tokens (`*`-delimited strings).
            if any("*" in v for v in non_null):
                tokens: dict[str, int] = {}
                for v in non_null:
                    for t in _tokenize(v):
                        tokens[t] = tokens.get(t, 0) + 1
                if tokens:
                    descriptors.append(
                        {
                            "field": field,
                            "label": _label(field),
                            "control": "multiselect-tokens",
                            "separator": "*",
                            "options": [
                                {"value": k, "count": c}
                                for k, c in sorted(
                                    tokens.items(), key=lambda x: (-x[1], x[0])
                                )
                            ],
                        }
                    )
                continue

            distinct = sorted({v for v in non_null})
            if len(distinct) <= 20:
                counts: dict[str, int] = {}
                for v in non_null:
                    counts[v] = counts.get(v, 0) + 1
                descriptors.append(
                    {
                        "field": field,
                        "label": _label(field),
                        "control": "multiselect",
                        "options": [
                            {"value": k, "count": counts[k]}
                            for k in sorted(distinct, key=lambda x: (-counts[x], x))
                        ],
                    }
                )
            else:
                descriptors.append(
                    {"field": field, "label": _label(field), "control": "text"}
                )

    # Stable, human-friendly ordering: toggles, multiselects, ranges, text.
    order = {"toggle": 0, "multiselect": 1, "multiselect-tokens": 1, "range": 2, "text": 3}
    descriptors.sort(key=lambda d: (order.get(d["control"], 99), d["label"]))
    return descriptors
