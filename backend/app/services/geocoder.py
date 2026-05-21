from dataclasses import dataclass
import csv
from io import StringIO

import httpx


@dataclass(frozen=True)
class GeocodeInput:
    unique_id: str
    street: str
    city: str
    state: str
    zip: str


@dataclass(frozen=True)
class GeocodeResult:
    unique_id: str
    matched: bool
    latitude: float | None
    longitude: float | None
    matched_address: str | None


class CensusBatchGeocoder:
    def __init__(self, batch_url: str, chunk_size: int) -> None:
        self.batch_url = batch_url
        self.chunk_size = chunk_size

    async def geocode(self, rows: list[GeocodeInput]) -> list[GeocodeResult]:
        results: list[GeocodeResult] = []
        for index in range(0, len(rows), self.chunk_size):
            results.extend(await self._geocode_chunk(rows[index : index + self.chunk_size]))
        return results

    async def _geocode_chunk(self, rows: list[GeocodeInput]) -> list[GeocodeResult]:
        if not rows:
            return []

        csv_body = _build_csv(rows)
        files = {"addressFile": ("addresses.csv", csv_body, "text/csv")}
        data = {"benchmark": "Public_AR_Current"}
        async with httpx.AsyncClient(timeout=60) as client:
            response = await client.post(self.batch_url, data=data, files=files)
            response.raise_for_status()

        parsed = _parse_response(response.text)
        return [
            parsed.get(
                row.unique_id,
                GeocodeResult(
                    unique_id=row.unique_id,
                    matched=False,
                    latitude=None,
                    longitude=None,
                    matched_address=None,
                ),
            )
            for row in rows
        ]


def _build_csv(rows: list[GeocodeInput]) -> str:
    output = StringIO()
    writer = csv.writer(output, lineterminator="\n")
    for row in rows:
        writer.writerow([row.unique_id, row.street, row.city, row.state, row.zip])
    return output.getvalue()


def _parse_response(content: str) -> dict[str, GeocodeResult]:
    parsed: dict[str, GeocodeResult] = {}
    reader = csv.reader(StringIO(content))
    for row in reader:
        if not row:
            continue
        unique_id = row[0]
        match_status = row[2].strip().lower() if len(row) > 2 else ""
        matched = match_status == "match"
        matched_address = row[4].strip() if matched and len(row) > 4 else None
        longitude, latitude = _parse_coordinates(row[5] if matched and len(row) > 5 else "")
        parsed[unique_id] = GeocodeResult(
            unique_id=unique_id,
            matched=matched and latitude is not None and longitude is not None,
            latitude=latitude,
            longitude=longitude,
            matched_address=matched_address,
        )
    return parsed


def _parse_coordinates(value: str) -> tuple[float | None, float | None]:
    parts = [part.strip() for part in value.split(",")]
    if len(parts) != 2:
        return None, None
    try:
        return float(parts[0]), float(parts[1])
    except ValueError:
        return None, None
