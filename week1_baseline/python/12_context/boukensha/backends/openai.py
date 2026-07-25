import json

from boukensha.backends.base import Base


class OpenAI(Base):
    BASE_URL = "https://api.openai.com/v1/responses"
    MODELS = {
        "gpt-5.5": {
            "context_window": 1_000_000,
            "cost_per_million": {"input": 5.0, "output": 30.0},
            "usage_unit": "tokens",
        },
        "gpt-5.4-mini": {
            "context_window": 400_000,
            "cost_per_million": {"input": 0.75, "output": 4.5},
            "usage_unit": "tokens",
        },
        "gpt-5.4-nano": {
            "context_window": 400_000,
            "cost_per_million": {"input": 0.2, "output": 1.25},
            "usage_unit": "tokens",
        },
    }

    def __init__(self, api_key=None, model=None):
        self.api_key = api_key
        super().__init__(model)

    def to_input(self, messages):
        items = []
        for msg in messages:
            if msg.role == "tool_result":
                items.append({
                    "type": "function_call_output",
                    "call_id": msg.tool_use_id,
                    "output": str(msg.content),
                })
            elif msg.role == "assistant":
                items.extend(_assistant_items(msg.content))
            else:
                items.append({"role": str(msg.role), "content": msg.content})
        return items

    def to_tools(self, tools):
        return [
            {
                "type": "function",
                "name": tool.name,
                "description": tool.description,
                "parameters": {
                    "type": "object",
                    "properties": tool.parameters,
                    "required": list(tool.parameters.keys()),
                },
            }
            for tool in tools.values()
        ]

    def to_payload(self, context, max_output_tokens=1024, tools=None):
        return {
            "model": self.model,
            "instructions": context.system,
            "input": self.to_input(context.messages),
            "tools": tools if tools is not None else self.to_tools(context.tools),
            "max_output_tokens": max_output_tokens,
            "reasoning": {"effort": "none"},
        }

    def headers(self):
        return {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
        }

    def url(self):
        return self.BASE_URL

    def parse_response(self, response):
        function_calls = []
        output = response.get("output") or []
        content = []
        for item in output:
            t = item.get("type")
            if t == "reasoning":
                summary = item.get("summary") or []
                text = "".join(s.get("text", "") for s in summary)
                content.append({"type": "reasoning", "text": text})
            elif t == "message":
                msg_content = item.get("content") or []
                text = "".join(
                    c["text"] for c in msg_content if c.get("type") == "output_text"
                )
                if text:
                    content.append({"type": "text", "text": text})
            elif t == "function_call":
                function_calls.append(item)

        for fc in function_calls:
            try:
                args = json.loads(fc.get("arguments", "{}"))
            except (json.JSONDecodeError, TypeError):
                args = {}
            content.append({
                "type": "tool_use",
                "id": fc["call_id"],
                "name": fc["name"],
                "input": args,
            })

        return {
            "stop_reason": "end_turn" if not function_calls else "tool_use",
            "content": content,
        }


def _assistant_items(content):
    blocks = content if isinstance(content, list) else [{"type": "text", "text": content}]
    items = []
    text_parts = [b["text"] for b in blocks if b.get("type") == "text"]
    full_text = "".join(text_parts)
    if full_text:
        items.append({"role": "assistant", "content": full_text})
    for b in blocks:
        if b.get("type") == "tool_use":
            items.append({
                "type": "function_call",
                "call_id": b["id"],
                "name": b["name"],
                "arguments": json.dumps(b.get("input", {})),
            })
    return items
