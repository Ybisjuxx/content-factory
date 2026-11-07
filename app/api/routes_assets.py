import logging
from typing import List, Optional
from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlmodel import Session, select

from app.database import get_session
from app.models.asset import Asset, AssetType, AssetResponse
from app.services.broll_manager import LocalBrollManager
from app.services.svg_generator import ProceduralSvgGenerator

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/assets", tags=["Visual & Audio Assets"])


class SvgGenerateRequest(BaseModel):
    card_type: str = "stat"
    title: str = "HIGHLIGHT"
    content: str = "Key takeaway description"
    badge: str = "KEY INSIGHT"


class SvgGenerateResponse(BaseModel):
    file_path: str
    card_type: str


@router.post("/broll/index", response_model=List[AssetResponse])
def reindex_broll_library(session: Session = Depends(get_session)):
    """Scans the local B-roll storage directory and indexes all 9:16 vertical video & image assets."""
    manager = LocalBrollManager()
    assets = manager.index_library(session=session)
    return [
        AssetResponse(
            id=a.id,
            name=a.name,
            file_path=a.file_path,
            asset_type=a.asset_type,
            tags=[t.strip() for t in a.tags.split(",") if t.strip()],
            duration_seconds=a.duration_seconds,
            width=a.width,
            height=a.height,
            is_vertical=a.is_vertical,
        )
        for a in assets
    ]


@router.get("/broll", response_model=List[AssetResponse])
def list_broll_assets(
    query: Optional[str] = Query(None, description="Search keyword filter"),
    session: Session = Depends(get_session)
):
    """Lists indexed B-roll stock assets."""
    stmt = select(Asset).where(Asset.asset_type.in_([AssetType.BROLL, AssetType.IMAGE]))
    assets = session.exec(stmt).all()

    if query:
        q = query.lower()
        assets = [a for a in assets if q in a.name.lower() or q in a.tags.lower()]

    return [
        AssetResponse(
            id=a.id,
            name=a.name,
            file_path=a.file_path,
            asset_type=a.asset_type,
            tags=[t.strip() for t in a.tags.split(",") if t.strip()],
            duration_seconds=a.duration_seconds,
            width=a.width,
            height=a.height,
            is_vertical=a.is_vertical,
        )
        for a in assets
    ]


@router.post("/svg/generate", response_model=SvgGenerateResponse)
def generate_procedural_svg(req: SvgGenerateRequest):
    """Generates a procedural 9:16 vertical SVG graphics card (stat, quote, terminal, takeaway)."""
    generator = ProceduralSvgGenerator()
    path = generator.generate_card(
        card_type=req.card_type,
        title=req.title,
        content=req.content,
        badge=req.badge
    )
    return SvgGenerateResponse(file_path=path, card_type=req.card_type)
