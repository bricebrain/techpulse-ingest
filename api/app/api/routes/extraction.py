from fastapi import APIRouter, Depends, HTTPException, Security, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.config import settings
from app.schemas.extraction import ArticleExtractionRequest, ArticleExtractionResponse
from app.services.extraction_service import extraction_service

router = APIRouter(prefix="/extract", tags=["Extraction"])
bearer = HTTPBearer(auto_error=False)


def verify_secret(
    credentials: HTTPAuthorizationCredentials | None = Security(bearer),
) -> None:
    if not settings.reddit_proxy_secret:
        return
    if not credentials or credentials.credentials != settings.reddit_proxy_secret:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Non autorisé")


@router.post(
    "/article",
    response_model=ArticleExtractionResponse,
    dependencies=[Depends(verify_secret)],
)
async def extract_article(payload: ArticleExtractionRequest) -> ArticleExtractionResponse:
    return extraction_service.extract_article(payload)
