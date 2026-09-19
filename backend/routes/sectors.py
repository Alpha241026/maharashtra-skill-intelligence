from fastapi import APIRouter

from backend.schemas.sectors import SectorResponse
from backend.services.sector_service import get_all_sectors

router = APIRouter()


@router.get("/api/sectors", response_model=SectorResponse)
def get_sectors():
    """Return all sectors from the database."""
    return get_all_sectors()
