import json
import logging
from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from ...schemas import ChatRequest, ChatResponse, ToolRequest
from ...services.ollama_service import OllamaService
from ...services.chat_service import ChatService
from ...services.tool_service import run_tool

router = APIRouter(prefix="/chat", tags=["chat"])
logger = logging.getLogger(__name__)
ollama_service = OllamaService()
chat_service = ChatService(ollama_service)


@router.post("", response_model=ChatResponse)
async def chat_once(req: ChatRequest):
    content, tool_events = await chat_service.chat_once(req)
    return ChatResponse(message=content, tool_events=tool_events, model=req.model)


@router.post("/stream")
async def chat_stream(req: ChatRequest):
    async def ndjson_stream():
        try:
            async for event in chat_service.stream_chat(req):
                yield json.dumps(event) + "\n"
        except Exception as exc:
            logger.exception("stream chat failed")
            yield json.dumps({"type": "error", "data": {"message": str(exc)}}) + "\n"

    return StreamingResponse(ndjson_stream(), media_type="application/x-ndjson")


@router.post("/tools/execute")
async def execute_tool(req: ToolRequest):
    return await run_tool(req.tool, req.query)


@router.get("/models")
async def list_models():
    return {"models": await ollama_service.list_models()}


@router.get("/tools")
async def list_tools():
    return {
        "tools": [
            {"name": "calculator", "description": "Evaluate math expressions"},
            {"name": "wikipedia", "description": "Wikipedia summary lookup"},
            {"name": "weather", "description": "Current weather by location"},
            {"name": "url_fetch", "description": "Fetch URL content preview"},
        ]
    }
