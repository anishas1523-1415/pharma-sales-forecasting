from fastapi import APIRouter, HTTPException

from backend.schemas.chat import ChatRequest, ChatResponse
from backend.services.chat_service import get_chat_reply

router = APIRouter(prefix="/api/chat", tags=["Chat"])


@router.post("", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """
    Natural-language Q&A over the live portfolio data (grounded — see
    chat_service.SYSTEM_INSTRUCTION). Tries Gemini first, falls back to
    Groq if Gemini errors or isn't configured.
    """
    if not request.message.strip():
        raise HTTPException(status_code=400, detail="message is required")

    try:
        reply, provider = await get_chat_reply(request.message)
    except Exception:
        raise HTTPException(status_code=502, detail="Chat assistant is temporarily unavailable — both providers failed.")

    return ChatResponse(reply=reply, provider=provider)
