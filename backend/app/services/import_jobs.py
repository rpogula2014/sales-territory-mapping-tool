from datetime import UTC, datetime
from hashlib import sha1
from uuid import UUID

import httpx
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update

from app.core.config import get_settings
from app.core.database import AsyncSessionLocal
from app.models import Account, Dataset, ImportJob, Seller
from app.services.geocoder import CensusBatchGeocoder, GeocodeInput, GeocodeResult
from app.services.import_parser import ImportValidationError, parse_accounts_workbook


async def process_import_job(dataset_id: UUID, import_job_id: UUID, content: bytes) -> None:
    async with AsyncSessionLocal() as db:
        job = await db.get(ImportJob, import_job_id)
        dataset = await db.get(Dataset, dataset_id)
        if job is None or dataset is None:
            return

        job.status = "processing"
        job.started_at = datetime.now(UTC)
        dataset.import_status = "processing"
        await db.commit()

        try:
            parsed = parse_accounts_workbook(content)
            previous_accounts = await _load_previous_accounts(db, dataset)
            sellers = await _load_sellers(db, dataset.market_id)
            geocoded, geocode_warnings = await _geocode_missing_coordinates(parsed.rows)

            job.row_count = len(parsed.rows)
            dataset.row_count = len(parsed.rows)
            job.warnings_json = parsed.warnings + geocode_warnings

            for row in parsed.rows:
                seller = await _seller_for_name(db, dataset.market_id, row["current_seller"], sellers)
                previous = previous_accounts.get(row["customer_number"])
                latitude = row["latitude"]
                longitude = row["longitude"]
                matched_address = None
                if latitude is not None and longitude is not None:
                    geocode_status = "provided"
                else:
                    result = geocoded.get(row["customer_number"])
                    latitude = result.latitude if result else None
                    longitude = result.longitude if result else None
                    matched_address = result.matched_address if result else None
                    geocode_status = "matched" if result and result.matched else "failed"

                account = Account(
                    dataset_id=dataset.id,
                    customer_number=row["customer_number"],
                    account_name=row["account_name"],
                    address=row["address"],
                    city=row["city"],
                    state=row["state"],
                    zip=row["zip"],
                    latitude=latitude,
                    longitude=longitude,
                    geocode_status=geocode_status,
                    matched_address=matched_address,
                    suggested_seller=row["suggested_seller"],
                    current_seller=previous.current_seller if previous else row["current_seller"],
                    seller_id=previous.seller_id if previous else seller.id,
                    mtd_sales=row["mtd_sales"],
                    ytd_sales=row["ytd_sales"],
                    ttm_volume=row["ttm_volume"],
                    tire_pros=row["tire_pros"],
                    activate=row["activate"],
                    primary_program=row["primary_program"],
                    secondary_program=row["secondary_program"],
                    market=row["market"],
                    dc=row["dc"],
                    original_row_json=row["original_row_json"],
                    extra_attributes_json=row["extra_attributes_json"],
                    assignment_changed=previous.assignment_changed if previous else False,
                    assigned_at=previous.assigned_at if previous else None,
                    assigned_by=previous.assigned_by if previous else None,
                )
                db.add(account)
                job.processed_count += 1
                if geocode_status == "failed":
                    job.geocode_failure_count += 1
                else:
                    job.geocode_success_count += 1

            await db.execute(
                update(Dataset)
                .where(Dataset.market_id == dataset.market_id)
                .values(is_active=False)
            )
            dataset.is_active = True
            dataset.import_status = (
                "completed_with_warnings" if job.geocode_failure_count or job.warnings_json else "completed"
            )
            dataset.geocode_success_count = job.geocode_success_count
            dataset.geocode_failure_count = job.geocode_failure_count
            job.status = dataset.import_status
            job.finished_at = datetime.now(UTC)
            await db.commit()
        except ImportValidationError as exc:
            await _fail_import(db, dataset, job, str(exc))
        except Exception as exc:
            await _fail_import(db, dataset, job, "Unexpected import failure")
            raise exc


async def _geocode_missing_coordinates(rows: list[dict]) -> tuple[dict[str, GeocodeResult], list[str]]:
    missing = [
        GeocodeInput(
            unique_id=row["customer_number"],
            street=row["address"],
            city=row["city"],
            state=row["state"],
            zip=row["zip"],
        )
        for row in rows
        if row["latitude"] is None or row["longitude"] is None
    ]
    if not missing:
        return {}, []

    settings = get_settings()
    geocoder = CensusBatchGeocoder(settings.census_batch_url, settings.geocode_chunk_size)
    try:
        results = await geocoder.geocode(missing)
    except httpx.HTTPError as exc:
        warning = f"Census geocoder request failed; {len(missing)} rows need manual correction: {exc}"
        return {}, [warning]
    return {result.unique_id: result for result in results}, []


async def _fail_import(db: AsyncSession, dataset: Dataset, job: ImportJob, message: str) -> None:
    dataset.import_status = "failed"
    job.status = "failed"
    job.error_message = message
    job.finished_at = datetime.now(UTC)
    await db.commit()


async def _load_previous_accounts(db: AsyncSession, dataset: Dataset) -> dict[str, Account]:
    result = await db.execute(
        select(Account)
        .join(Dataset, Account.dataset_id == Dataset.id)
        .where(Dataset.market_id == dataset.market_id, Dataset.is_active.is_(True))
    )
    return {account.customer_number: account for account in result.scalars()}


async def _load_sellers(db: AsyncSession, market_id: UUID) -> dict[str, Seller]:
    result = await db.execute(select(Seller).where(Seller.market_id == market_id))
    return {seller.normalized_name: seller for seller in result.scalars()}


async def _seller_for_name(
    db: AsyncSession,
    market_id: UUID,
    display_name: str,
    sellers: dict[str, Seller],
) -> Seller:
    normalized = _normalize_seller(display_name)
    if normalized in sellers:
        return sellers[normalized]

    seller = Seller(
        market_id=market_id,
        display_name=display_name or "Unassigned",
        normalized_name=normalized,
        color=_seller_color(normalized),
    )
    db.add(seller)
    await db.flush()
    sellers[normalized] = seller
    return seller


def _normalize_seller(value: str) -> str:
    normalized = " ".join((value or "Unassigned").strip().lower().split())
    return normalized or "unassigned"


def _seller_color(normalized_name: str) -> str:
    palette = [
        "#2563eb",
        "#16a34a",
        "#dc2626",
        "#9333ea",
        "#ca8a04",
        "#0891b2",
        "#c2410c",
        "#4f46e5",
    ]
    digest = sha1(normalized_name.encode("utf-8")).hexdigest()
    return palette[int(digest[:8], 16) % len(palette)]
