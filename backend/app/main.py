import os
import secrets
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from math import isfinite
from pathlib import Path
from typing import Optional

from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.responses import RedirectResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from fastapi.staticfiles import StaticFiles

from app.ingestion.sync_moenv import sync_moenv_data
from app.models.schemas import DistrictsResponse, GenderFilter, MetaResponse, ToiletsResponse
from app.services.toilet_service import (
    _haversine_m,
    aggregate_toilets,
    get_last_synced_at,
    get_opening_hours,
    get_toilet,
    initialize_db,
    list_districts,
    list_toilets,
    nearby_toilets,
)


@asynccontextmanager
async def lifespan(_: FastAPI):
    initialize_db()
    yield


app = FastAPI(title="Toilet Map API", version="0.1.0", lifespan=lifespan)
WEB_DIR = Path(__file__).resolve().parents[1] / "web"
app.mount("/web", StaticFiles(directory=WEB_DIR, html=True), name="web")
admin_bearer = HTTPBearer(auto_error=False)


def require_admin(
    credentials: HTTPAuthorizationCredentials | None = Depends(admin_bearer),
) -> None:
    token = os.getenv("TOILET_ADMIN_TOKEN")
    if not token or not token.strip():
        raise HTTPException(status_code=503, detail="Admin sync is disabled")
    if credentials is None or not secrets.compare_digest(
        credentials.credentials.encode(), token.encode()
    ):
        raise HTTPException(
            status_code=401,
            detail="Invalid admin credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )


def _parse_bbox(bbox: Optional[str]) -> Optional[tuple[float, float, float, float]]:
    if not bbox:
        return None
    try:
        parts = [float(x.strip()) for x in bbox.split(",")]
        if len(parts) != 4:
            raise ValueError
        min_lng, min_lat, max_lng, max_lat = parts
        if (
            not all(isfinite(value) for value in parts)
            or not -180 <= min_lng <= max_lng <= 180
            or not -90 <= min_lat <= max_lat <= 90
        ):
            raise ValueError
        return min_lng, min_lat, max_lng, max_lat
    except ValueError as exc:
        raise HTTPException(
            status_code=422,
            detail="bbox must be minLng,minLat,maxLng,maxLat within valid coordinate ranges",
        ) from exc


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.get("/")
def root() -> RedirectResponse:
    return RedirectResponse(url="/web")


@app.get("/v1/meta", response_model=MetaResponse)
def meta() -> MetaResponse:
    last_synced_at = get_last_synced_at() or datetime.now(timezone.utc).isoformat()
    return MetaResponse(
        lastSyncedAt=last_synced_at,
        coverage=["Taipei", "New Taipei"],
        version="v1",
    )


@app.get("/v1/toilets", response_model=ToiletsResponse)
def toilets(
    bbox: Optional[str] = Query(default=None),
    city: Optional[str] = Query(default=None),
    district: Optional[str] = Query(default=None),
    keyword: Optional[str] = Query(default=None),
    open_now: Optional[bool] = Query(default=None),
    has_men_toilet: Optional[bool] = Query(default=None),
    has_women_toilet: Optional[bool] = Query(default=None),
    has_diaper_table: Optional[bool] = Query(default=None),
    toilet_type: Optional[str] = Query(default=None),
    toilet_types: list[str] = Query(default=[]),
    gender: list[GenderFilter] = Query(default=[]),
    aggregate: bool = Query(default=False),
    limit: int = Query(default=200, ge=1, le=200),
) -> ToiletsResponse:
    parsed_bbox = _parse_bbox(bbox)
    items = list_toilets(
        bbox=None if aggregate else parsed_bbox,
        city=city,
        district=district,
        keyword=keyword,
        open_now=open_now,
        has_men_toilet=has_men_toilet,
        has_women_toilet=has_women_toilet,
        has_diaper_table=has_diaper_table,
        toilet_type=toilet_type,
        toilet_types=toilet_types,
        gender=gender,
    )
    if aggregate:
        items = aggregate_toilets(items, bbox=parsed_bbox)
    items = items[:limit]
    return ToiletsResponse(items=items, total=len(items))


@app.get("/v1/districts", response_model=DistrictsResponse)
def districts(city: Optional[str] = Query(default=None)) -> DistrictsResponse:
    return DistrictsResponse(items=list_districts(city=city))


@app.get("/v1/toilets/nearby", response_model=ToiletsResponse)
def toilets_nearby(
    lat: float = Query(ge=-90, le=90, allow_inf_nan=False),
    lng: float = Query(ge=-180, le=180, allow_inf_nan=False),
    radius_m: int = Query(default=1000, ge=100, le=5000),
    city: Optional[str] = Query(default=None),
    district: Optional[str] = Query(default=None),
    keyword: Optional[str] = Query(default=None),
    open_now: Optional[bool] = Query(default=None),
    has_men_toilet: Optional[bool] = Query(default=None),
    has_women_toilet: Optional[bool] = Query(default=None),
    has_diaper_table: Optional[bool] = Query(default=None),
    toilet_type: Optional[str] = Query(default=None),
    toilet_types: list[str] = Query(default=[]),
    gender: list[GenderFilter] = Query(default=[]),
    aggregate: bool = Query(default=False),
) -> ToiletsResponse:
    filters = dict(
        city=city,
        district=district,
        keyword=keyword,
        open_now=open_now,
        has_men_toilet=has_men_toilet,
        has_women_toilet=has_women_toilet,
        has_diaper_table=has_diaper_table,
        toilet_type=toilet_type,
        toilet_types=toilet_types,
        gender=gender,
    )
    if aggregate:
        items = aggregate_toilets(list_toilets(**filters))
        items = [
            x.model_copy(update={"distanceM": _haversine_m(lat, lng, x.lat, x.lng)}) for x in items
        ]
        items = sorted((x for x in items if x.distanceM <= radius_m), key=lambda x: x.distanceM)
    else:
        items = nearby_toilets(lat=lat, lng=lng, radius_m=radius_m, **filters)
    return ToiletsResponse(items=items, total=len(items))


@app.get("/v1/toilets/{toilet_id}")
def toilet_detail(toilet_id: str) -> dict:
    item = get_toilet(toilet_id)
    if not item:
        raise HTTPException(status_code=404, detail="Toilet not found")

    opening_hours = get_opening_hours(toilet_id)

    return {
        **item.model_dump(),
        "openingHours": opening_hours,
    }


@app.post("/v1/admin/sync", dependencies=[Depends(require_admin)])
def sync_now() -> dict:
    return sync_moenv_data()
