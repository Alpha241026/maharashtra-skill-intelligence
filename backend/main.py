#import FastAPI class (to create web application) and HTTPException class (to return HTTP errors) from fastapi package
from fastapi import FastAPI, HTTPException

#import BaseModel class (to define & validate the structure of API request/response data) from pydantic package
from pydantic import BaseModel


#create main FastAPI application instance for Uvicorn to load & run the API (where title gives metadata for OpenAPI documentation)
app = FastAPI(title="Maharashtra Skill Intelligence API")


#define structure of one sector's projected training demand response using Pydantic model
class SectorDemand(BaseModel):
    """Response data for one sector's projected training demand"""

    #name of the sector
    sector: str

    #ML-derived projected training requirement for the sector
    projected_training: float

    #classification of projected training requirement based on current model thresholds
    demand_band: str

    #confidence/evidence value associated with the underlying district-sector data
    evidence_confidence: float


#define structure of the complete response returned by the district demand endpoint
class DemandResponse(BaseModel):
    """Response returned by the district demand endpoint"""

    #name of the selected district
    district: str

    #list of sector demand objects following the SectorDemand structure defined above
    sectors: list[SectorDemand]


#register below function to handle GET requests sent to "/" (root path)
@app.get("/")
def root():
    """Simple endpoint to verify that the API is running"""

    #return Python dictionary which FastAPI automatically converts into a JSON response
    return {"message": "Maharashtra Skill Intelligence API is running"}


#register below function to handle GET requests sent to "/api/demand" and validate returned data against DemandResponse model
@app.get("/api/demand", response_model=DemandResponse)
def get_demand(district: str | None = None):
    """
    Return projected training demand for a selected district

    Temporary implementation:
    Uses sample Pune data until PostgreSQL is connected
    """

    #check whether district parameter is missing or contains only whitespace
    if district is None or not district.strip():

        #raise HTTP 400 Bad Request error when required district parameter is missing or invalid
        raise HTTPException(
            status_code=400,
            detail="District is required"
        )

    #remove leading & trailing whitespace from the received district name
    district = district.strip()

    #temporary sample data used to test the API contract before PostgreSQL integration
    #this will later be replaced by PostgreSQL data + ProjectedTrainingIntelligence ML processing
    if district.lower() == "pune":

        #return district and its sector demand data in the structure defined by DemandResponse
        return {
            "district": "Pune",
            "sectors": [
                {
                    #sector name
                    "sector": "Construction",

                    #temporary ML-derived value taken from the API contract example
                    "projected_training": 179.87,

                    #current model classification for the projected training value
                    "demand_band": "Moderate",

                    #evidence/confidence value associated with the district-sector record
                    "evidence_confidence": 0.83
                }
            ]
        }

    #raise HTTP 404 Not Found error when the requested district is not available
    raise HTTPException(
        status_code=404,
        detail="District not found"
    )