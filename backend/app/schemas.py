from pydantic import BaseModel, Field
from typing import Literal, Any


class Attachment(BaseModel):
    kind: Literal["image", "document"]
    name: str | None = None
    mime: str | None = None
    data: str | None = None
    content: str | None = None


class ChatRequest(BaseModel):
    message: str = Field(min_length=1)
    history: list[str] = Field(default_factory=list)
    temperature: float = Field(default=0.7, ge=0, le=2)
    model: str = "llama3.2"
    attachments: list[Attachment] = Field(default_factory=list)
    enabled_tools: dict[str, bool] = Field(default_factory=dict)


class ChatResponse(BaseModel):
    ok: bool = True
    message: str
    tool_events: list[dict[str, Any]] = Field(default_factory=list)
    model: str


class APIErrorResponse(BaseModel):
    ok: bool = False
    error: dict[str, Any]


class ToolRequest(BaseModel):
    query: str
    tool: Literal["calculator", "wikipedia", "weather", "url_fetch"]
