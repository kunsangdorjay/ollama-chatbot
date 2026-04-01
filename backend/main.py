from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
import requests
import json
import os
from typing import Literal
import re
import ast
import operator
import base64
from io import BytesIO

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
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_CHAT_URL = f"{OLLAMA_BASE_URL}/api/chat"
OLLAMA_TAGS_URL = f"{OLLAMA_BASE_URL}/api/tags"

# -------------------------
# Request schema
# -------------------------
class ChatRequest(BaseModel):
    message: str
    history: list[str] = []
    temperature: float = 0.3
    model: str = "llama3.2"
    attachments: list[dict] = []
    enabled_tools: dict = {}


class ToolRequest(BaseModel):
    query: str
    tool: Literal["calculator", "wikipedia", "weather", "url_fetch"]


# -------------------------
# Streaming generator (ASYNC)
# -------------------------
def eval_expression(expr: str):
    safe_ops = {
        ast.Add: operator.add,
        ast.Sub: operator.sub,
        ast.Mult: operator.mul,
        ast.Div: operator.truediv,
        ast.Mod: operator.mod,
        ast.Pow: operator.pow,
        ast.USub: operator.neg,
        ast.UAdd: operator.pos,
    }

    def _eval(node):
        if isinstance(node, ast.Num):
            return node.n
        if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
            return node.value
        if isinstance(node, ast.UnaryOp) and type(node.op) in safe_ops:
            return safe_ops[type(node.op)](_eval(node.operand))
        if isinstance(node, ast.BinOp) and type(node.op) in safe_ops:
            return safe_ops[type(node.op)](_eval(node.left), _eval(node.right))
        raise ValueError("Unsupported expression")

    tree = ast.parse(expr, mode="eval")
    return _eval(tree.body)


def run_tool(tool: str, query: str):
    try:
        if tool == "calculator":
            allowed = "0123456789+-*/().% "
            if any(ch not in allowed for ch in query):
                return {"ok": False, "error": "Unsafe calculator expression."}
            result = eval_expression(query)
            return {"ok": True, "result": str(result)}

        if tool == "wikipedia":
            resp = requests.get(
                "https://en.wikipedia.org/api/rest_v1/page/summary/" + query.strip().replace(" ", "_"),
                timeout=20
            )
            if not resp.ok:
                return {"ok": False, "error": "No Wikipedia summary found."}
            data = resp.json()
            return {
                "ok": True,
                "title": data.get("title", query),
                "summary": data.get("extract", "")[:1200]
            }

        if tool == "weather":
            api_key = os.getenv("OPENWEATHER_API_KEY", "")
            if not api_key:
                return {"ok": False, "error": "OPENWEATHER_API_KEY is not configured."}
            geo = requests.get(
                "https://api.openweathermap.org/geo/1.0/direct",
                params={"q": query, "limit": 1, "appid": api_key},
                timeout=20
            )
            geo_data = geo.json()
            if not geo_data:
                return {"ok": False, "error": f"Could not resolve location: {query}"}
            lat = geo_data[0]["lat"]
            lon = geo_data[0]["lon"]
            weather = requests.get(
                "https://api.openweathermap.org/data/2.5/weather",
                params={"lat": lat, "lon": lon, "appid": api_key, "units": "metric"},
                timeout=20
            )
            w = weather.json()
            return {
                "ok": True,
                "location": f'{geo_data[0].get("name", query)}, {geo_data[0].get("country", "")}',
                "temp_c": w.get("main", {}).get("temp"),
                "description": (w.get("weather", [{}])[0] or {}).get("description", "unknown"),
                "humidity": w.get("main", {}).get("humidity")
            }

        if tool == "url_fetch":
            if not query.startswith("http://") and not query.startswith("https://"):
                return {"ok": False, "error": "URL must start with http:// or https://"}
            resp = requests.get(query, timeout=20)
            text = resp.text[:4000]
            return {"ok": True, "status_code": resp.status_code, "content_preview": text}
    except Exception as e:
        return {"ok": False, "error": str(e)}

    return {"ok": False, "error": f"Unknown tool: {tool}"}


TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "calculator",
            "description": "Evaluate a safe math expression",
            "parameters": {
                "type": "object",
                "properties": {"query": {"type": "string"}},
                "required": ["query"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "wikipedia",
            "description": "Fetch a short Wikipedia summary by topic",
            "parameters": {
                "type": "object",
                "properties": {"query": {"type": "string"}},
                "required": ["query"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "weather",
            "description": "Get current weather by city name",
            "parameters": {
                "type": "object",
                "properties": {"query": {"type": "string"}},
                "required": ["query"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "url_fetch",
            "description": "Fetch URL content preview",
            "parameters": {
                "type": "object",
                "properties": {"query": {"type": "string"}},
                "required": ["query"]
            }
        }
    },
]


def extract_tool_queries(user_text: str):
    text = user_text.lower()
    plans = []

    url_match = re.search(r"https?://[^\s]+", user_text)
    if url_match:
        plans.append(("url_fetch", url_match.group(0)))

    if any(k in text for k in ["weather", "temperature", "forecast"]):
        city_match = re.search(r"in ([a-zA-Z ]+)$", user_text.strip())
        plans.append(("weather", city_match.group(1).strip() if city_match else user_text))

    if any(k in text for k in ["wikipedia", "wiki", "who is", "what is"]):
        cleaned = user_text.replace("wikipedia", "").replace("wiki", "").strip()
        plans.append(("wikipedia", cleaned or user_text))

    if any(k in text for k in ["calculate", "compute", "math", "+", "-", "*", "/"]):
        expr = re.sub(r"[^0-9+\-*/().% ]", "", user_text)
        if expr.strip():
            plans.append(("calculator", expr.strip()))

    # preserve order, remove duplicates
    seen = set()
    unique = []
    for item in plans:
        if item[0] + ":" + item[1] in seen:
            continue
        seen.add(item[0] + ":" + item[1])
        unique.append(item)
    return unique[:3]


def extract_document_text(attachment: dict):
    if attachment.get("content"):
        return str(attachment.get("content"))[:12000]

    encoded = attachment.get("data")
    if not encoded:
        return ""
    mime = attachment.get("mime", "")
    name = attachment.get("name", "file")
    try:
        raw = base64.b64decode(encoded)
    except Exception:
        return ""

    # best-effort extraction for common text-like files
    try:
        if "text" in mime or name.endswith((".md", ".txt", ".json", ".js", ".py", ".ts", ".tsx", ".jsx", ".csv")):
            return raw.decode("utf-8", errors="ignore")[:12000]
    except Exception:
        return ""

    # optional PDF extraction if dependency exists
    if "pdf" in mime or name.endswith(".pdf"):
        try:
            from pypdf import PdfReader  # type: ignore
            reader = PdfReader(BytesIO(raw))
            pages = [p.extract_text() or "" for p in reader.pages[:10]]
            return "\n".join(pages)[:12000]
        except Exception:
            return f"[Unable to extract PDF text from {name}]"

    return f"[Unsupported document parser for {name}]"


async def ollama_stream(messages: list[dict], temperature: float, model: str, request: Request):
    response = requests.post(
        OLLAMA_CHAT_URL,
        json={
            "model": model,
            "messages": messages,
            "temperature": temperature,
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
            token = data.get("message", {}).get("content", "")
            if token:
                yield token


def run_tool_loop(messages: list[dict], temperature: float, model: str, enabled_tools: dict):
    chosen_tool_names = []
    for t in TOOLS:
        name = t["function"]["name"]
        if enabled_tools.get(name, True):
            chosen_tool_names.append(t)

    tool_events = []
    if not chosen_tool_names:
        return messages, tool_events

    for _ in range(3):
        try:
            response = requests.post(
                OLLAMA_CHAT_URL,
                json={
                    "model": model,
                    "messages": messages,
                    "temperature": temperature,
                    "stream": False,
                    "tools": chosen_tool_names,
                },
                timeout=120,
            )
            response.raise_for_status()
            data = response.json()
            message = data.get("message", {})
            tool_calls = message.get("tool_calls", []) or []

            if not tool_calls:
                # No tool request from model; keep assistant text if present
                if message.get("content"):
                    messages.append({"role": "assistant", "content": message.get("content", "")})
                break

            messages.append({
                "role": "assistant",
                "content": message.get("content", ""),
                "tool_calls": tool_calls,
            })
            for call in tool_calls:
                function = call.get("function", {})
                name = function.get("name")
                args = function.get("arguments", {}) or {}
                query = args.get("query", "")
                result = run_tool(name, query)
                tool_events.append({"tool": name, "query": query, "result": result})
                messages.append({
                    "role": "tool",
                    "name": name,
                    "content": json.dumps(result),
                })
        except Exception as e:
            tool_events.append({"tool": "system", "query": "tool_loop", "result": {"ok": False, "error": str(e)}})
            break

    return messages, tool_events


# -------------------------
# Chat endpoint
# -------------------------
@app.post("/chat")
async def chat(req: ChatRequest, request: Request):
    messages = []
    for h in req.history[-6:]:
        if h.startswith("User: "):
            messages.append({"role": "user", "content": h.replace("User: ", "", 1)})
        elif h.startswith("Assistant: "):
            messages.append({"role": "assistant", "content": h.replace("Assistant: ", "", 1)})

    images = [a.get("data") for a in req.attachments if a.get("kind") == "image" and a.get("data")]
    docs = [a for a in req.attachments if a.get("kind") == "document"]

    tool_enabled = {
        "calculator": req.enabled_tools.get("calculator", True),
        "wikipedia": req.enabled_tools.get("wikipedia", True),
        "weather": req.enabled_tools.get("weather", True),
        "url_fetch": req.enabled_tools.get("urlFetch", True),
    }

    planned_tools = [p for p in extract_tool_queries(req.message) if tool_enabled.get(p[0], False)]
    tool_results = []
    for tool_name, query in planned_tools:
        result = run_tool(tool_name, query)
        tool_results.append({"tool": tool_name, "query": query, "result": result})

    system_chunks = []
    if docs:
        docs_text = "\n\n".join([f"[{d.get('name','file')}] {extract_document_text(d)[:1800]}" for d in docs[:4]])
        system_chunks.append("Attached document excerpts:\n" + docs_text)
    if tool_results:
        tool_text = "\n".join(
            [f"{t['tool']}({t['query']}): {json.dumps(t['result'])}" for t in tool_results]
        )
        system_chunks.append("Tool results:\n" + tool_text)
    if system_chunks:
        messages.append(
            {
                "role": "system",
                "content": "Use attached context and tool results when helpful.\n\n" + "\n\n".join(system_chunks),
            }
        )

    user_message = {"role": "user", "content": req.message}
    if images:
        user_message["images"] = images
    messages.append(user_message)

    # model-driven tool calling pass
    messages, model_tool_events = run_tool_loop(messages, req.temperature, req.model, tool_enabled)
    tool_results.extend(model_tool_events)

    async def combined_stream():
        for t in tool_results:
            yield f"\n[Tool] {t['tool']} -> {t['query']}\n"
        async for token in ollama_stream(messages, req.temperature, req.model, request):
            yield token

    return StreamingResponse(
        combined_stream(),
        media_type="text/plain"
    )


@app.get("/models")
async def models():
    try:
        response = requests.get(OLLAMA_TAGS_URL, timeout=20)
        response.raise_for_status()
        data = response.json()
        model_names = [m.get("name") for m in data.get("models", []) if m.get("name")]
        return {"models": model_names}
    except Exception:
        return {"models": ["llama3.2", "mistral", "gemma3"]}


@app.post("/tools/execute")
async def execute_tool(req: ToolRequest):
    return run_tool(req.tool, req.query)


@app.get("/tools")
async def list_tools():
    return {
        "tools": [
            {"name": "calculator", "description": "Evaluate math expressions"},
            {"name": "wikipedia", "description": "Get topic summary from Wikipedia"},
            {"name": "weather", "description": "Fetch weather by location"},
            {"name": "url_fetch", "description": "Fetch URL content preview"},
        ]
    }
