import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Optional, List
from sqlmodel import SQLModel, Field
from pydantic import BaseModel


class AssetType(str, Enum):
    BROLL = "broll"
    AUDIO = "audio"
    SVG_CARD = "svg_card"
    IMAGE = "image"


class AssetBase(SQLModel):
    name: str
    file_path: str
    asset_type: AssetType = Field(default=AssetType.BROLL)
    tags: str = Field(default="")
    duration_seconds: Optional[float] = Field(default=None)
    width: Optional[int] = Field(default=None)
    height: Optional[int] = Field(default=None)
    is_vertical: bool = Field(default=True)


class Asset(AssetBase, table=True):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class AssetResponse(BaseModel):
    id: str
    name: str
    file_path: str
    asset_type: AssetType
    tags: List[str]
    duration_seconds: Optional[float] = None
    width: Optional[int] = None
    height: Optional[int] = None
    is_vertical: bool = True
