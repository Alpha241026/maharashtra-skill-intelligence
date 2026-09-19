from fastapi import APIRouter, HTTPException

from backend.schemas.chat import ChatRequest
from engines.chatbot.chatbot_engine import GroundedChatbotEngine


router = APIRouter()
bot = GroundedChatbotEngine()


@router.post("/api/chat")
def chat(request: ChatRequest):
    """
    Grounded conversational endpoint.
    Accepts optional district and sector to provide richer evidence context.
    """
    if not request.question.strip():
        raise HTTPException(status_code=400, detail="Question is required")

    try:
        # Pass district/sector context if provided so the engine can
        # retrieve targeted evidence before calling Groq.
        result = bot.ask(
            question=request.question.strip(),
            district=request.district.strip() if request.district else None,
            sector=request.sector.strip() if request.sector else None,
        )
        return result
    except TypeError:
        # Graceful fallback: older engine signature may not accept district/sector
        try:
            return bot.ask(request.question.strip())
        except Exception:
            raise HTTPException(status_code=500, detail="Unable to process chat request")
    except Exception:
        raise HTTPException(status_code=500, detail="Unable to process chat request")
