import logging
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from .config import settings
from .logger import setup_logging
from .api.routes.health import router as health_router
from .api.routes.chat import router as chat_router

setup_logging()
logger = logging.getLogger(__name__)

app = FastAPI(title="Ollama Chat Backend", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allow_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.exception("Unhandled error on %s", request.url.path)
    return JSONResponse(
        status_code=500,
        content={
            "ok": False,
            "error": {
                "code": "INTERNAL_SERVER_ERROR",
                "message": str(exc),
            },
        },
    )


app.include_router(health_router, prefix=settings.api_prefix)
app.include_router(chat_router, prefix=settings.api_prefix)


# Backward compatibility for existing frontend paths
@app.post("/chat")
async def legacy_chat(request: Request):
    from .schemas import ChatRequest
    from .api.routes.chat import chat_stream

    payload = await request.json()
    req = ChatRequest(**payload)
    return await chat_stream(req)


@app.get("/models")
async def legacy_models():
    from .api.routes.chat import list_models

    return await list_models()
