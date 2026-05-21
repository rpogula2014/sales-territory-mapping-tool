from app.services.geocoder import _build_csv, _parse_response


def test_build_csv_escapes_commas() -> None:
    rows = [
        type(
            "Row",
            (),
            {
                "unique_id": "1",
                "street": "10 Main St, Unit 2",
                "city": "Los Angeles",
                "state": "CA",
                "zip": "90001",
            },
        )()
    ]

    assert _build_csv(rows) == '1,"10 Main St, Unit 2",Los Angeles,CA,90001\n'


def test_parse_response_maps_matches_and_failures() -> None:
    content = "\n".join(
        [
            '"1","10 Main St, Los Angeles, CA, 90001","Match","Exact","10 MAIN ST, LOS ANGELES, CA, 90001","-118.1,34.2","1","L"',
            '"2","Bad Address","No_Match","","","","",""',
        ]
    )

    results = _parse_response(content)

    assert results["1"].matched is True
    assert results["1"].longitude == -118.1
    assert results["1"].latitude == 34.2
    assert results["1"].matched_address == "10 MAIN ST, LOS ANGELES, CA, 90001"
    assert results["2"].matched is False
    assert results["2"].longitude is None
    assert results["2"].latitude is None
