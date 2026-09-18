from pydantic import BaseModel


class District(BaseModel):
    id: int
    name: str


class DistrictResponse(BaseModel):
    districts: list[District]