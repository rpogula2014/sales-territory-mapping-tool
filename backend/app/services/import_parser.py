from dataclasses import dataclass
from io import BytesIO
from typing import Any

import pandas as pd


REQUIRED_COLUMNS = {
    "Account Name",
    "Customer Number",
    "Address",
    "City",
    "State",
    "Zip",
    "Suggested Seller",
    "MTD Sales",
    "YTD Sales",
    "TTM Volume",
    "Tire Pros",
    "Activate",
    "Primary Program",
    "Secondary Program",
    "Market",
    "DC",
}

KNOWN_COLUMNS = REQUIRED_COLUMNS | {"Latitude", "Longitude"}
TRUE_VALUES = {"true", "yes", "y", "1", "x"}
FALSE_VALUES = {"false", "no", "n", "0", ""}


class ImportValidationError(ValueError):
    pass


@dataclass(frozen=True)
class ParsedWorkbook:
    rows: list[dict[str, Any]]
    extra_columns: list[str]
    warnings: list[str]


def parse_accounts_workbook(content: bytes) -> ParsedWorkbook:
    df = pd.read_excel(BytesIO(content), dtype=object)
    df.columns = [str(column).strip() for column in df.columns]

    missing = sorted(REQUIRED_COLUMNS - set(df.columns))
    if missing:
        raise ImportValidationError(f"Missing required columns: {', '.join(missing)}")

    normalized_rows = [_normalize_row(row) for row in df.to_dict(orient="records")]
    customer_numbers = [row["customer_number"] for row in normalized_rows]
    duplicates = sorted({value for value in customer_numbers if customer_numbers.count(value) > 1})
    if duplicates:
        raise ImportValidationError(f"Duplicate Customer Number values: {', '.join(duplicates[:10])}")

    if any(not row["market"] for row in normalized_rows):
        raise ImportValidationError("Market is required for every row")

    extra_columns = sorted(set(df.columns) - KNOWN_COLUMNS)
    warnings = []
    if extra_columns:
        warnings.append(f"Extra columns preserved but not filterable by default: {', '.join(extra_columns)}")

    return ParsedWorkbook(rows=normalized_rows, extra_columns=extra_columns, warnings=warnings)


def _normalize_row(row: dict[str, Any]) -> dict[str, Any]:
    original = {str(key): _json_safe(value) for key, value in row.items()}
    customer_number = _text(row.get("Customer Number"))
    if not customer_number:
        raise ImportValidationError("Customer Number is required for every row")

    return {
        "customer_number": customer_number,
        "account_name": _text(row.get("Account Name")),
        "address": _text(row.get("Address")),
        "city": _text(row.get("City")),
        "state": _text(row.get("State")),
        "zip": _text(row.get("Zip")),
        "suggested_seller": _text(row.get("Suggested Seller")),
        "current_seller": _text(row.get("Suggested Seller")),
        "mtd_sales": _number(row.get("MTD Sales")),
        "ytd_sales": _number(row.get("YTD Sales")),
        "ttm_volume": _number(row.get("TTM Volume")),
        "tire_pros": _boolean(row.get("Tire Pros")),
        "activate": _boolean(row.get("Activate")),
        "primary_program": _text(row.get("Primary Program")),
        "secondary_program": _text(row.get("Secondary Program")),
        "market": _text(row.get("Market")),
        "dc": _text(row.get("DC")),
        "latitude": _optional_float(row.get("Latitude")),
        "longitude": _optional_float(row.get("Longitude")),
        "original_row_json": original,
        "extra_attributes_json": {
            key: original[key] for key in set(original) - KNOWN_COLUMNS if original.get(key) is not None
        },
    }


def _text(value: Any) -> str:
    if value is None or pd.isna(value):
        return ""
    return str(value).strip()


def _number(value: Any) -> float:
    if value is None or pd.isna(value):
        return 0.0
    if isinstance(value, int | float):
        return float(value)
    cleaned = str(value).replace("$", "").replace(",", "").strip()
    if not cleaned:
        return 0.0
    return float(cleaned)


def _optional_float(value: Any) -> float | None:
    if value is None or pd.isna(value) or str(value).strip() == "":
        return None
    return float(value)


def _boolean(value: Any) -> bool:
    if value is None or pd.isna(value):
        return False
    normalized = str(value).strip().lower()
    if normalized in TRUE_VALUES:
        return True
    if normalized in FALSE_VALUES:
        return False
    return False


def _json_safe(value: Any) -> Any:
    if value is None or pd.isna(value):
        return None
    if hasattr(value, "item"):
        return value.item()
    return value
