from pydantic import BaseModel, Field, HttpUrl


class ArticleExtractionRequest(BaseModel):
    article_id: str = Field(..., min_length=1)
    url: HttpUrl
    source: str | None = None


class ArticleExtractionResponse(BaseModel):
    success: bool
    url: str
    title: str | None = None
    text: str | None = None
    excerpt: str | None = None
    image_url: str | None = None
    authors: list[str] = Field(default_factory=list)
    published_at: str | None = None
    extraction_method: str = "trafilatura"
    status_code: int | None = None
    error: str | None = None
