import ast
import base64
import json
import operator
import os
from io import BytesIO
import httpx


SAFE_OPERATORS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
    ast.USub: operator.neg,
    ast.UAdd: operator.pos,
}


def eval_expression(expr: str):
    def _eval(node):
        if isinstance(node, ast.Num):
            return node.n
        if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
            return node.value
        if isinstance(node, ast.UnaryOp) and type(node.op) in SAFE_OPERATORS:
            return SAFE_OPERATORS[type(node.op)](_eval(node.operand))
        if isinstance(node, ast.BinOp) and type(node.op) in SAFE_OPERATORS:
            return SAFE_OPERATORS[type(node.op)](_eval(node.left), _eval(node.right))
        raise ValueError("Unsupported expression")

    return _eval(ast.parse(expr, mode="eval").body)


async def run_tool(tool: str, query: str) -> dict:
    try:
        if tool == "calculator":
            allowed = "0123456789+-*/().% "
            if any(ch not in allowed for ch in query):
                return {"ok": False, "error": "Unsafe calculator expression"}
            return {"ok": True, "result": str(eval_expression(query))}

        async with httpx.AsyncClient(timeout=20) as client:
            if tool == "wikipedia":
                url = "https://en.wikipedia.org/api/rest_v1/page/summary/" + query.strip().replace(" ", "_")
                resp = await client.get(url)
                if resp.status_code != 200:
                    return {"ok": False, "error": "No summary found"}
                data = resp.json()
                return {"ok": True, "title": data.get("title", query), "summary": data.get("extract", "")[:1200]}

            if tool == "weather":
                api_key = os.getenv("OPENWEATHER_API_KEY", "")
                if not api_key:
                    return {"ok": False, "error": "OPENWEATHER_API_KEY missing"}
                geo = await client.get(
                    "https://api.openweathermap.org/geo/1.0/direct",
                    params={"q": query, "limit": 1, "appid": api_key},
                )
                geo_data = geo.json()
                if not geo_data:
                    return {"ok": False, "error": "Location not found"}
                lat, lon = geo_data[0]["lat"], geo_data[0]["lon"]
                weather = await client.get(
                    "https://api.openweathermap.org/data/2.5/weather",
                    params={"lat": lat, "lon": lon, "appid": api_key, "units": "metric"},
                )
                w = weather.json()
                return {
                    "ok": True,
                    "location": f'{geo_data[0].get("name", query)}, {geo_data[0].get("country", "")}',
                    "temp_c": w.get("main", {}).get("temp"),
                    "description": (w.get("weather", [{}])[0] or {}).get("description"),
                }

            if tool == "url_fetch":
                if not query.startswith(("http://", "https://")):
                    return {"ok": False, "error": "Invalid URL"}
                resp = await client.get(query)
                return {"ok": True, "status_code": resp.status_code, "content_preview": resp.text[:4000]}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}

    return {"ok": False, "error": f"Unknown tool: {tool}"}


def extract_document_text(attachment: dict) -> str:
    if attachment.get("content"):
        return str(attachment["content"])[:12000]
    data = attachment.get("data")
    if not data:
        return ""
    name = (attachment.get("name") or "file").lower()
    mime = (attachment.get("mime") or "").lower()
    try:
        raw = base64.b64decode(data)
    except Exception:
        return ""

    if "text" in mime or name.endswith((".txt", ".md", ".json", ".js", ".jsx", ".ts", ".tsx", ".py", ".csv")):
        return raw.decode("utf-8", errors="ignore")[:12000]

    if "pdf" in mime or name.endswith(".pdf"):
        try:
            from pypdf import PdfReader  # type: ignore
            reader = PdfReader(BytesIO(raw))
            return "\n".join((p.extract_text() or "") for p in reader.pages[:10])[:12000]
        except Exception:
            return f"[Unable to parse PDF: {name}]"

    return f"[Unsupported document type: {name}]"


TOOLS_SPEC = [
    {
        "type": "function",
        "function": {
            "name": "calculator",
            "description": "Evaluate a safe math expression",
            "parameters": {"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "wikipedia",
            "description": "Fetch short summary from Wikipedia",
            "parameters": {"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "weather",
            "description": "Get current weather by location",
            "parameters": {"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "url_fetch",
            "description": "Fetch URL content preview",
            "parameters": {"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]},
        },
    },
]
