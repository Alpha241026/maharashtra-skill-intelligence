from fastapi import APIRouter

from backend.schemas.district import DistrictResponse
from backend.services.district_service import get_all_districts


router = APIRouter()


@router.get("/api/districts", response_model=DistrictResponse)
def get_districts():
    return get_all_districts()