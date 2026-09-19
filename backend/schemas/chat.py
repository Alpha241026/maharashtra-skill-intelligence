from pydantic import BaseModel
from typing import Optional


class ChatRequest(BaseModel):
    question: str
    district: Optional[str] = None
    sector: Optional[str] = None
