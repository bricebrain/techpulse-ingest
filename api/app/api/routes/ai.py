from fastapi import APIRouter

from app.schemas.ai import PromptRequest, PromptResponse
from app.services.ai_service import ai_service

router = APIRouter(prefix="/ai", tags=["AI"])


@router.post("/prompt", response_model=PromptResponse)
async def prompt_ai(payload: PromptRequest) -> PromptResponse:
    return ai_service.run_prompt(payload.prompt)
