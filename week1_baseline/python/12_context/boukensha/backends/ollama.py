import json

from boukensha.backends.base import Base


class Ollama(Base):
    MODELS = {
        "gemma4:e4b": {
            "context_window": 1_000_000,
            "cost_per_million": {"input": 0.0, "output": 0.0},
            "usage_unit": "tokens",
        },
    }
    OLLAMA_BASE_URL = "http://localhost:11434"

    def __init__(self, model=None, host=None):
        self.base_url = (host or self.OLLAMA_BASE_URL).rstrip("/")
        super().__init__(model)

    def to_messages(self, messages):
        return [_to_message(msg) for msg in messages]

    def to_tools(self, tools):
        return [
            {
                "type": "function",
                "function": {
                    "name": tool.name,
                    "description": tool.description,
                    "parameters": {
                        "type": "object",
                        "properties": tool.parameters,
                        "required": list(tool.parameters.keys()),
                    },
                },
            }
            for tool in tools.values()
        ]

    def to_payload(self, context, max_output_tokens=1024, tools=None):
        return {
            "model": self.model,
            "messages": self.to_messages(context.messages),
            "stream": False,
            "options": {"num_predict": max_output_tokens},
            "tools": tools if tools is not None else self.to_tools(context.tools),
            "think": False,
        }

    def headers(self):
        return {"Content-Type": "application/json"}

    def url(self):
        return f"{self.base_url}/api/chat"

    def parse_response(self, response):
        message = response.get("message", {})
        content = []
        reasoning_text = message.get("thinking")
        if reasoning_text:
            content.append({"type": "reasoning", "text": str(reasoning_text)})
        text = message.get("content", "")
        if text:
            content.append({"type": "text", "text": text})
        raw_tools = message.get("tool_calls") or []
        for tc in raw_tools:
            for fn_name, fn_args in tc.items():
                content.append({
                    "type": "tool_use",
                    "id": fn_name,
                    "name": fn_name,
                    "input": fn_args if isinstance(fn_args, dict) else {},
                })
        tool_used = any(b.get("type") == "tool_use" for b in content)
        return {"stop_reason": "tool_use" if tool_used else "end_turn", "content": content}


def _to_message(msg):
    if msg.role == "assistant":
        parts = msg.content if isinstance(msg.content, list) else [{"type": "text", "text": msg.content}]
        result = {"role": "assistant", "content": ""}
        tool_calls = []
        for b in parts:
            if b.get("type") == "tool_use":
                tool_calls.append({b["name"]: b.get("input", {})})
            elif b.get("type") != "reasoning":
                result["content"] += b.get("text", "")
        if tool_calls:
            result["tool_calls"] = tool_calls
        return result
    elif msg.role == "tool_result":
        return {
            "role": "tool",
            "content": str(msg.content),
        }
    else:
        return {"role": str(msg.role), "content": msg.content}
