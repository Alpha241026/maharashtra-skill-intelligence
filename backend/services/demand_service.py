# import HTTPException class to return HTTP errors when the requested district is unavailable
from fastapi import HTTPException


# temporary service function that provides district demand data
# this will later be replaced with PostgreSQL data and ProjectedTrainingIntelligence processing
def get_demand_by_district(district: str):
    # check whether the requested district matches the temporary Pune data
    if district.lower() == "pune":

        # return temporary data using the same structure defined in the API contract
        return {
            "district": "Pune",
            "sectors": [
                {
                    # sector name
                    "sector": "Construction",

                    # temporary ML-derived value from the current API contract example
                    "projected_training": 179.87,

                    # current model classification for the projected training value
                    "demand_band": "Moderate",

                    # evidence/confidence value associated with the district-sector record
                    "evidence_confidence": 0.83
                }
            ]
        }

    # raise HTTP 404 when the requested district is not available
    raise HTTPException(
        status_code=404,
        detail="District not found"
    )