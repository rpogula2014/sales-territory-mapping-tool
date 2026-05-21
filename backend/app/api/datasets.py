from datetime import datetime, timezone
from io import BytesIO
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, UploadFile, status
from fastapi.responses import StreamingResponse
import pandas as pd
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.access import ensure_market_access
from app.core.database import get_db
from app.core.ids import new_uuid7
from app.core.security import CurrentUser, get_current_user, require_admin
from app.models import Account, Dataset, ImportJob, Market, Seller
from app.schemas import ImportAcceptedOut, ImportStatusOut
from app.services.import_jobs import process_import_job
from app.services.import_parser import KNOWN_COLUMNS, REQUIRED_COLUMNS

router = APIRouter()


@router.get("")
async def list_datasets(
    market_id: UUID | None = None,
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[dict]:
    query = select(Dataset).where(Dataset.deleted_at.is_(None))
    if market_id:
        ensure_market_access(user, market_id)
        query = query.where(Dataset.market_id == market_id)
    elif "*" not in user.market_ids:
        query = query.where(Dataset.market_id.in_(user.market_ids))
    query = query.order_by(Dataset.uploaded_at.desc())
    result = await db.execute(query)
    return [
        {
            "id": dataset.id,
            "name": dataset.name,
            "market_id": dataset.market_id,
            "import_status": dataset.import_status,
            "is_active": dataset.is_active,
            "row_count": dataset.row_count,
        }
        for dataset in result.scalars()
    ]


@router.post("/import", response_model=ImportAcceptedOut, status_code=status.HTTP_202_ACCEPTED)
async def import_dataset(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    market_id: UUID = Form(alias="marketId"),
    dataset_name: str = Form(alias="datasetName"),
    user: CurrentUser = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> dict:
    ensure_market_access(user, market_id)
    if await db.get(Market, market_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Market not found")
    content = await file.read()

    dataset = Dataset(
        id=new_uuid7(),
        name=dataset_name.strip(),
        market_id=market_id,
        source_filename=file.filename or "upload.xlsx",
        uploaded_by=user.email,
        import_status="pending",
        is_active=False,
    )
    job = ImportJob(id=new_uuid7(), dataset_id=dataset.id, status="queued", uploaded_by=user.email)
    db.add_all([dataset, job])
    await db.flush()
    await db.commit()

    background_tasks.add_task(process_import_job, dataset.id, job.id, content)

    return {
        "datasetId": dataset.id,
        "importJobId": job.id,
        "status": "queued",
    }


@router.delete("/{dataset_id}")
async def soft_delete_dataset(
    dataset_id: UUID,
    user: CurrentUser = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> dict:
    dataset = await db.get(Dataset, dataset_id)
    if dataset is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Dataset not found")
    ensure_market_access(user, dataset.market_id)
    if dataset.deleted_at is not None:
        return {"id": dataset.id, "deleted_at": dataset.deleted_at.isoformat()}
    dataset.deleted_at = datetime.now(timezone.utc)
    dataset.is_active = False
    await db.flush()
    await db.commit()
    return {"id": dataset.id, "deleted_at": dataset.deleted_at.isoformat()}


@router.get("/{dataset_id}/import-status", response_model=ImportStatusOut)
async def import_status(
    dataset_id: UUID,
    user: CurrentUser = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> dict:
    dataset = await db.get(Dataset, dataset_id)
    if dataset is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Dataset not found")
    ensure_market_access(user, dataset.market_id)

    result = await db.execute(
        select(ImportJob).where(ImportJob.dataset_id == dataset_id).order_by(ImportJob.started_at.desc())
    )
    job = result.scalars().first()
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Import job not found")

    return {
        "datasetId": dataset_id,
        "importJobId": job.id,
        "status": job.status,
        "rowCount": job.row_count,
        "processedCount": job.processed_count,
        "geocodeSuccessCount": job.geocode_success_count,
        "geocodeFailureCount": job.geocode_failure_count,
        "warnings": job.warnings_json or [],
    }


@router.get("/{dataset_id}/accounts")
async def dataset_accounts(
    dataset_id: UUID,
    dc: str | None = None,
    seller: str | None = None,
    tire_pros: bool | None = None,
    activate: bool | None = None,
    primary_program: str | None = None,
    secondary_program: str | None = None,
    ttm_min: float | None = None,
    ttm_max: float | None = None,
    bbox: str | None = None,
    format: str = "geojson",
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    dataset = await db.get(Dataset, dataset_id)
    if dataset is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Dataset not found")
    ensure_market_access(user, dataset.market_id)

    result = await db.execute(
        _account_query(
            dataset_id=dataset_id,
            dc=dc,
            seller=seller,
            tire_pros=tire_pros,
            activate=activate,
            primary_program=primary_program,
            secondary_program=secondary_program,
            ttm_min=ttm_min,
            ttm_max=ttm_max,
            bbox=bbox,
            mapped_only=True,
        )
    )
    rows = result.all()
    if format == "geojson":
        features = []
        for index, (account, seller_row) in enumerate(rows, start=1):
            features.append(_account_feature(account, seller_row, index))
        return {
            "type": "FeatureCollection",
            "features": features,
        }
    return {"accounts": [_account_json(account, seller_row) for account, seller_row in rows]}


@router.get("/{dataset_id}/sellers")
async def dataset_sellers(
    dataset_id: UUID,
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[dict]:
    dataset = await db.get(Dataset, dataset_id)
    if dataset is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Dataset not found")
    ensure_market_access(user, dataset.market_id)

    result = await db.execute(
        select(Seller)
        .where(Seller.market_id == dataset.market_id, Seller.is_active.is_(True))
        .order_by(Seller.display_name)
    )
    return [
        {"id": seller.id, "displayName": seller.display_name, "color": seller.color}
        for seller in result.scalars()
    ]


@router.get("/{dataset_id}/export")
async def export_dataset(
    dataset_id: UUID,
    dc: str | None = None,
    seller: str | None = None,
    tire_pros: bool | None = None,
    activate: bool | None = None,
    primary_program: str | None = None,
    secondary_program: str | None = None,
    ttm_min: float | None = None,
    ttm_max: float | None = None,
    bbox: str | None = None,
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> StreamingResponse:
    dataset = await db.get(Dataset, dataset_id)
    if dataset is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Dataset not found")
    ensure_market_access(user, dataset.market_id)

    result = await db.execute(
        _account_query(
            dataset_id=dataset_id,
            dc=dc,
            seller=seller,
            tire_pros=tire_pros,
            activate=activate,
            primary_program=primary_program,
            secondary_program=secondary_program,
            ttm_min=ttm_min,
            ttm_max=ttm_max,
            bbox=bbox,
            mapped_only=False,
        )
    )
    rows = result.all()
    workbook = _build_export_workbook(rows)
    filename = f"{_safe_filename(dataset.name)}-assignments.xlsx"
    return StreamingResponse(
        iter([workbook.getvalue()]),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


def _account_query(
    *,
    dataset_id: UUID,
    dc: str | None,
    seller: str | None,
    tire_pros: bool | None,
    activate: bool | None,
    primary_program: str | None,
    secondary_program: str | None,
    ttm_min: float | None,
    ttm_max: float | None,
    bbox: str | None,
    mapped_only: bool,
):
    query = select(Account, Seller).outerjoin(Seller, Account.seller_id == Seller.id).where(
        Account.dataset_id == dataset_id
    )
    if mapped_only:
        query = query.where(Account.latitude.is_not(None), Account.longitude.is_not(None))
    if dc:
        query = query.where(Account.dc == dc)
    if seller:
        query = query.where(Account.current_seller == seller)
    if tire_pros is not None:
        query = query.where(Account.tire_pros == tire_pros)
    if activate is not None:
        query = query.where(Account.activate == activate)
    if primary_program:
        query = query.where(Account.primary_program == primary_program)
    if secondary_program:
        query = query.where(Account.secondary_program == secondary_program)
    if ttm_min is not None:
        query = query.where(Account.ttm_volume >= ttm_min)
    if ttm_max is not None:
        query = query.where(Account.ttm_volume <= ttm_max)
    if bbox:
        west, south, east, north = _parse_bbox(bbox)
        query = query.where(
            Account.longitude >= west,
            Account.longitude <= east,
            Account.latitude >= south,
            Account.latitude <= north,
        )
    return query.order_by(Account.account_name, Account.customer_number)


def _parse_bbox(value: str) -> tuple[float, float, float, float]:
    parts = [float(part) for part in value.split(",")]
    if len(parts) != 4:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="bbox must be west,south,east,north")
    return parts[0], parts[1], parts[2], parts[3]


def _account_feature(account: Account, seller: Seller | None, pin_number: int) -> dict:
    return {
        "type": "Feature",
        "id": str(account.id),
        "geometry": {"type": "Point", "coordinates": [account.longitude, account.latitude]},
        "properties": {**_account_json(account, seller), "pinNumber": pin_number},
    }


def _account_json(account: Account, seller: Seller | None) -> dict:
    return {
        "id": account.id,
        "customerNumber": account.customer_number,
        "accountName": account.account_name,
        "currentSeller": account.current_seller,
        "sellerId": account.seller_id,
        "sellerColor": seller.color if seller else "#7b8794",
        "ttmVolume": account.ttm_volume,
        "tirePros": account.tire_pros,
        "activate": account.activate,
        "primaryProgram": account.primary_program,
        "secondaryProgram": account.secondary_program,
        "dc": account.dc,
        "version": account.version,
    }


def _build_export_workbook(rows: list[tuple[Account, Seller | None]]) -> BytesIO:
    original_columns = _export_original_columns([account for account, _ in rows])
    data = []
    for account, seller in rows:
        row = {column: account.original_row_json.get(column) for column in original_columns}
        row.update(
            {
                "Current Seller": account.current_seller,
                "Seller ID": str(seller.id) if seller else None,
                "Assignment Changed": account.assignment_changed,
                "Assigned At": account.assigned_at.isoformat() if account.assigned_at else None,
                "Assigned By": account.assigned_by,
                "Assignment Version": account.version,
                "Geocode Status": account.geocode_status,
                "Matched Address": account.matched_address,
                "Geocode Latitude": account.latitude,
                "Geocode Longitude": account.longitude,
            }
        )
        data.append(row)

    output = BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        pd.DataFrame(data, columns=original_columns + _assignment_export_columns()).to_excel(
            writer, index=False, sheet_name="Assignments"
        )
    output.seek(0)
    return output


def _export_original_columns(accounts: list[Account]) -> list[str]:
    preferred = [
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
    ]
    discovered = set().union(*(account.original_row_json.keys() for account in accounts)) if accounts else set()
    known = [column for column in preferred if column in discovered or column in REQUIRED_COLUMNS]
    extras = sorted(discovered - set(known) - KNOWN_COLUMNS)
    lat_lng = [column for column in ["Latitude", "Longitude"] if column in discovered]
    return known + lat_lng + extras


def _assignment_export_columns() -> list[str]:
    return [
        "Current Seller",
        "Seller ID",
        "Assignment Changed",
        "Assigned At",
        "Assigned By",
        "Assignment Version",
        "Geocode Status",
        "Matched Address",
        "Geocode Latitude",
        "Geocode Longitude",
    ]


def _safe_filename(value: str) -> str:
    cleaned = "".join(character if character.isalnum() or character in ("-", "_") else "-" for character in value)
    return cleaned.strip("-") or "dataset"
