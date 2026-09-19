from pydantic import BaseModel


class Sector(BaseModel):
    id: int
    name: str


class SectorResponse(BaseModel):
    sectors: list[Sector]
