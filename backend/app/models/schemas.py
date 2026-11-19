from typing import List, Literal, Optional

from pydantic import BaseModel, Field

GenderFilter = Literal["men", "women", "gender_friendly"]


class ToiletFilters(BaseModel):
    city: str | None = None
    district: str | None = None
    keyword: str | None = None
    open_now: bool | None = None
    has_men_toilet: bool | None = None
    has_women_toilet: bool | None = None
    has_diaper_table: bool | None = None
    toilet_type: str | None = None
    toilet_types: list[str] = Field(default_factory=list)
    gender: list[GenderFilter] = Field(default_factory=list)
    aggregate: bool = False


class ToiletSearch(ToiletFilters):
    bbox: str | None = None
    limit: int = Field(default=200, ge=1, le=200)


class NearbySearch(ToiletFilters):
    lat: float = Field(ge=-90, le=90, allow_inf_nan=False)
    lng: float = Field(ge=-180, le=180, allow_inf_nan=False)
    radius_m: int = Field(default=1000, ge=100, le=5000)


class ToiletMapItem(BaseModel):
    id: str
    name: str
    city: str
    district: str
    address: Optional[str] = None
    lat: float
    lng: float
    toiletTypes: List[str] = []
    hasMenToilet: bool = False
    hasWomenToilet: bool = False
    hasDiaperTable: bool = False
    openNow: Optional[bool] = None
    openLabel: str = "Hours unavailable"
    distanceM: Optional[int] = None
    sourceCount: Optional[int] = None
    groupKind: Optional[str] = None
    aggregationVersion: Optional[str] = None
    sourceRecords: List["ToiletMapItem"] = []
    matchingSourceIds: List[str] = []
    symbolSources: dict[str, List[str]] = {}
    building: Optional[str] = None
    floor: Optional[str] = None


class MetaResponse(BaseModel):
    lastSyncedAt: str
    coverage: List[str]
    version: str


class ToiletsResponse(BaseModel):
    items: List[ToiletMapItem]
    total: int


class DistrictsResponse(BaseModel):
    items: List[str]
