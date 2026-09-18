from fastapi import APIRouter, HTTPException

from backend.schemas.chat import ChatRequest
from engines.chatbot.chatbot_engine import GroundedChatbotEngine


router = APIRouter()

bot = GroundedChatbotEngine()


@router.post("/api/chat")
def chat(request: ChatRequest):
    if not request.question.strip():
        raise HTTPException(
            status_code=400,
            detail="Question is required",
        )

    try:
        return bot.ask(request.question.strip())
    except Exception:
        raise HTTPException(
            status_code=500,
            detail="Unable to process chat request",
        )