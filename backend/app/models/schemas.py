from typing import List, Literal, Optional

from pydantic import BaseModel

GenderFilter = Literal["men", "women", "gender_friendly"]


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
