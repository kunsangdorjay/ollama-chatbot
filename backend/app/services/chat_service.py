import json
from ..config import settings
from ..schemas import ChatRequest
from .ollama_service import OllamaService
from .tool_service import TOOLS_SPEC, extract_document_text, run_tool


class ChatService:
    def __init__(self, ollama: OllamaService) -> None:
        self.ollama = ollama

    def _build_messages(self, req: ChatRequest) -> list[dict]:
        messages: list[dict] = []
        for item in req.history[-settings.max_history_messages :]:
            if item.startswith("User: "):
                messages.append({"role": "user", "content": item.replace("User: ", "", 1)})
            elif item.startswith("Assistant: "):
                messages.append({"role": "assistant", "content": item.replace("Assistant: ", "", 1)})

        docs = [a.model_dump() for a in req.attachments if a.kind == "document"]
        if docs:
            text = "\n\n".join([f"[{d.get('name','file')}] {extract_document_text(d)[:1800]}" for d in docs[:4]])
            messages.append({"role": "system", "content": f"Attached document excerpts:\n{text}"})

        user_message = {"role": "user", "content": req.message}
        images = [a.data for a in req.attachments if a.kind == "image" and a.data]
        if images:
            user_message["images"] = images
        messages.append(user_message)
        return messages

    def _enabled_tools(self, req: ChatRequest) -> list[dict]:
        flags = req.enabled_tools or {}
        selected = []
        for spec in TOOLS_SPEC:
            name = spec["function"]["name"]
            is_enabled = flags.get(name, flags.get("urlFetch" if name == "url_fetch" else name, True))
            if is_enabled:
                selected.append(spec)
        return selected

    async def _run_model_tool_loop(self, messages: list[dict], req: ChatRequest) -> tuple[list[dict], list[dict]]:
        tool_events = []
        tools = self._enabled_tools(req)
        if not tools:
            return messages, tool_events

        for _ in range(3):
            data = await self.ollama.chat_once(
                {
                    "model": req.model,
                    "messages": messages,
                    "temperature": req.temperature,
                    "stream": False,
                    "tools": tools,
                }
            )
            msg = data.get("message", {})
            tool_calls = msg.get("tool_calls", []) or []
            if not tool_calls:
                if msg.get("content"):
                    messages.append({"role": "assistant", "content": msg.get("content", "")})
                break

            messages.append({"role": "assistant", "content": msg.get("content", ""), "tool_calls": tool_calls})
            for call in tool_calls:
                fn = call.get("function", {})
                name = fn.get("name")
                args = fn.get("arguments", {}) or {}
                query = args.get("query", "")
                result = await run_tool(name, query)
                tool_events.append({"tool": name, "query": query, "result": result})
                messages.append({"role": "tool", "name": name, "content": json.dumps(result)})

        return messages, tool_events

    async def stream_chat(self, req: ChatRequest):
        messages = self._build_messages(req)
        messages, tool_events = await self._run_model_tool_loop(messages, req)

        for event in tool_events:
            yield {"type": "tool", "data": event}

        async for token in self.ollama.stream_chat(
            {
                "model": req.model,
                "messages": messages,
                "temperature": req.temperature,
                "stream": True,
            }
        ):
            yield {"type": "token", "data": token}

        yield {"type": "done", "data": {"model": req.model}}

    async def chat_once(self, req: ChatRequest) -> tuple[str, list[dict]]:
        content = ""
        events = []
        async for event in self.stream_chat(req):
            if event["type"] == "token":
                content += event["data"]
            elif event["type"] == "tool":
                events.append(event["data"])
        return content, events
