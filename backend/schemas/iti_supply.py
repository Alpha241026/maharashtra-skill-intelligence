# import BaseModel to define and validate the API response structure
from pydantic import BaseModel


# define the structure of one trade's intake response
class TradeSupply(BaseModel):
    # name of the ITI trade
    trade: str

    # total intake available for this trade in the selected district
    intake: int


# define the complete response returned by the ITI supply endpoint
class ITISupplyResponse(BaseModel):
    # name of the selected district
    district: str

    # total ITI intake across all trades in the selected district
    total_intake: int

    # list of trade-wise intake values
    trades: list[TradeSupply]