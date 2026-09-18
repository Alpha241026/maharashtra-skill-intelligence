# import APIRouter class to create a group of related API routes
from fastapi import APIRouter, HTTPException

# import DemandResponse model to validate the endpoint response structure
from backend.schemas.demand import DemandResponse

# import service function that provides the district demand data
from backend.services.demand_service import get_demand_by_district


# create router for demand-related API endpoints
router = APIRouter()


# register below function to handle GET requests sent to "/api/demand"
# response_model validates the returned data against the DemandResponse structure
@router.get("/api/demand", response_model=DemandResponse)
def get_demand(district: str | None = None):
    """
    Return projected training demand for a selected district
    """

    # check whether district parameter is missing or contains only whitespace
    if district is None or not district.strip():

        # raise HTTP 400 Bad Request when required district parameter is missing or invalid
        raise HTTPException(
            status_code=400,
            detail="District is required"
        )

    # remove leading and trailing whitespace from the received district name
    district = district.strip()

    # call the service layer to obtain demand data for the requested district
    return get_demand_by_district(district)