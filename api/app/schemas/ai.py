from pydantic import BaseModel, Field


class PromptRequest(BaseModel):
    prompt: str = Field(..., min_length=3, max_length=4000)


class PromptResponse(BaseModel):
    answer: str
    model: str
