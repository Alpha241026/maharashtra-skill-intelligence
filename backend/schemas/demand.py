# import BaseModel class to define and validate the structure of API data
from pydantic import BaseModel


# define structure of one sector's projected training demand response
class SectorDemand(BaseModel):
    """Response data for one sector's projected training demand"""

    # name of the sector
    sector: str

    # ML-derived projected training requirement for the sector
    projected_training: float

    # classification of projected training requirement based on current model thresholds
    demand_band: str

    # confidence/evidence value associated with the underlying district-sector data
    evidence_confidence: float


# define structure of the complete response returned by the district demand endpoint
class DemandResponse(BaseModel):
    """Response returned by the district demand endpoint"""

    # name of the selected district
    district: str

    # list of sector demand objects following the SectorDemand structure defined above
    sectors: list[SectorDemand]