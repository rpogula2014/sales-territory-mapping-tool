from datetime import UTC, datetime
from uuid import uuid4

from openpyxl import load_workbook

from app.api.datasets import _build_export_workbook
from app.models import Account, Seller


def test_build_export_workbook_preserves_original_columns_and_appends_assignment_columns() -> None:
    account = Account(
        id=uuid4(),
        dataset_id=uuid4(),
        customer_number="C-1",
        account_name="Acme",
        original_row_json={
            "Account Name": "Acme",
            "Customer Number": "C-1",
            "Latitude": 10,
            "Custom Field": "Priority",
        },
        current_seller="Sam Seller",
        assignment_changed=True,
        assigned_at=datetime(2026, 1, 2, 3, 4, 5, tzinfo=UTC),
        assigned_by="admin@example.com",
        geocode_status="matched",
        matched_address="10 MAIN ST",
        latitude=34.2,
        longitude=-118.1,
        version=3,
    )
    seller = Seller(id=uuid4(), display_name="Sam Seller", color="#2563eb")

    workbook = load_workbook(_build_export_workbook([(account, seller)]))
    sheet = workbook["Assignments"]
    headers = [cell.value for cell in sheet[1]]
    values = [cell.value for cell in sheet[2]]

    assert "Account Name" in headers
    assert "Custom Field" in headers
    assert "Current Seller" in headers
    assert "Geocode Latitude" in headers
    assert values[headers.index("Current Seller")] == "Sam Seller"
    assert values[headers.index("Geocode Latitude")] == 34.2
    assert values[headers.index("Geocode Longitude")] == -118.1
