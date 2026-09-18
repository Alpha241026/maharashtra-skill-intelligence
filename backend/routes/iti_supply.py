# import APIRouter to create a group of related API routes
from fastapi import APIRouter, HTTPException

# import ITISupplyResponse model to validate the endpoint response
from backend.schemas.iti_supply import ITISupplyResponse

# import service function that provides ITI supply data
from backend.services.iti_supply_service import get_iti_supply_by_district


# create router for ITI supply-related API endpoints
router = APIRouter()


# register the endpoint for district-wise ITI supply
@router.get("/api/iti/supply", response_model=ITISupplyResponse)
def get_iti_supply(district: str | None = None):
    """
    Return ITI trade supply for a selected district
    """

    # check whether district parameter is missing or contains only whitespace
    if district is None or not district.strip():
        raise HTTPException(
            status_code=400,
            detail="District is required",
        )

    # remove leading and trailing whitespace
    district = district.strip()

    # call the service layer to obtain ITI supply data
    return get_iti_supply_by_district(district)