import json

from boukensha.backends.base import Base


class OpenCode(Base):
    BASE_URL = "https://opencode.ai/zen/v1/chat/completions"

    MODELS = {
        "deepseek-v4-flash-free": {
            "context_window": 128_000,
            "cost_per_million": {"input": 0, "output": 0},
            "usage_unit": "tokens",
        },
        "gpt-5-nano": {
            "context_window": 128_000,
            "cost_per_million": {"input": 0, "output": 0},
            "usage_unit": "tokens",
        },
        "big-pickle": {
            "context_window": 128_000,
            "cost_per_million": {"input": 0, "output": 0},
            "usage_unit": "tokens",
        },
        "mimo-v2.5-free": {
            "context_window": 128_000,
            "cost_per_million": {"input": 0, "output": 0},
            "usage_unit": "tokens",
        },
        "north-mini-code-free": {
            "context_window": 128_000,
            "cost_per_million": {"input": 0, "output": 0},
            "usage_unit": "tokens",
        },
        "nemotron-3-ultra-free": {
            "context_window": 128_000,
            "cost_per_million": {"input": 0, "output": 0},
            "usage_unit": "tokens",
        },
    }

    def __init__(self, api_key=None, model=None):
        self._api_key = api_key
        super().__init__(model)

    def _messages_from(self, system, messages):
        result = [{"role": "system", "content": system}]
        for msg in messages:
            if msg.role == "tool_result":
                result.append({
                    "role": "tool",
                    "tool_call_id": msg.tool_use_id,
                    "content": msg.content,
                })
            elif msg.role == "assistant":
                result.append(self._assistant_message(msg.content))
            else:
                result.append({"role": msg.role, "content": msg.content})
        return result

    def to_tools(self, tools):
        return [
            {
                "type": "function",
                "function": {
                    "name": t.name,
                    "description": t.description,
                    "parameters": {
                        "type": "object",
                        "properties": t.parameters,
                        "required": list(t.parameters.keys()),
                    },
                },
            }
            for t in tools.values()
        ]

    def to_payload(self, context, max_output_tokens=1024, tools=None):
        return {
            "model": self.model,
            "messages": self._messages_from(context.system, context.messages),
            "tools": self.to_tools(context.tools) if tools is None else tools,
            "max_completion_tokens": max_output_tokens,
        }

    def headers(self):
        headers = {
            "Content-Type": "application/json",
        }
        if self._api_key:
            headers["x-api-key"] = self._api_key
        return headers

    def url(self):
        return self.BASE_URL

    def parse_response(self, response):
        message = (response.get("choices") or [{}])[0].get("message") or {}
        tool_calls = message.get("tool_calls") or []

        content = []
        if message.get("content"):
            content.append({"type": "text", "text": message["content"]})

        for tc in tool_calls:
            content.append({
                "type": "tool_use",
                "id": tc["id"],
                "name": tc.get("function", {}).get("name"),
                "input": json.loads(tc.get("function", {}).get("arguments", "{}")),
            })

        return {
            "stop_reason": "tool_use" if tool_calls else "end_turn",
            "content": content,
        }

    def _assistant_message(self, content):
        if isinstance(content, str):
            blocks = [{"type": "text", "text": content}]
        else:
            blocks = content

        text_blocks = [b for b in blocks if b.get("type") == "text"]
        tool_blocks = [b for b in blocks if b.get("type") == "tool_use"]

        message = {"role": "assistant", "content": "".join(b["text"] for b in text_blocks)}
        if tool_blocks:
            message["tool_calls"] = [
                {"id": b["id"], "type": "function", "function": {"name": b["name"], "arguments": json.dumps(b["input"])}}
                for b in tool_blocks
            ]
        return message
