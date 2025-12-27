from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
import requests
import json

app = FastAPI()

# -------------------------
# CORS
# -------------------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# -------------------------
# Ollama config
# -------------------------
OLLAMA_URL = "http://localhost:11434/api/generate"
MODEL = "mistral:7b-instruct-q4_0"

# -------------------------
# Request schema
# -------------------------
class ChatRequest(BaseModel):
    message: str
    history: list[str] = []
    temperature: float = 0.3


# -------------------------
# Streaming generator (ASYNC)
# -------------------------
async def ollama_stream(prompt: str, temperature: float, request: Request):
    response = requests.post(
        OLLAMA_URL,
        json={
            "model": MODEL,
            "prompt": prompt,
            "temperature": temperature,
            "num_predict": 256,
            "stream": True
        },
        stream=True,
        timeout=300
    )

    for line in response.iter_lines():
        # stop if client cancelled
        if await request.is_disconnected():
            response.close()
            break

        if line:
            data = json.loads(line.decode("utf-8"))
            yield data.get("response", "")


# -------------------------
# Chat endpoint
# -------------------------
@app.post("/chat")
async def chat(req: ChatRequest, request: Request):
    conversation = ""
    for h in req.history[-6:]:
        conversation += h + "\n"

    prompt = (
        "System:\n"
        "You are a calm, intelligent, conversational AI assistant.\n"
        "Respond in clear paragraphs.\n"
        "Do NOT use bullet points unless asked.\n"
        "Do NOT summarize unless asked.\n"
        "Be logical, coherent, and helpful.\n\n"
        "Conversation:\n"
        f"{conversation}"
        f"User: {req.message}\n"
        "Assistant:"
    )

    return StreamingResponse(
        ollama_stream(prompt, req.temperature, request),
        media_type="text/plain"
    )
