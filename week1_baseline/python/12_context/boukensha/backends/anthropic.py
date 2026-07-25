from boukensha.backends.base import Base


class Anthropic(Base):
    BASE_URL = "https://api.anthropic.com/v1/messages"
    MODELS = {
        "claude-haiku-4-5": {
            "context_window": 200_000,
            "cost_per_million": {"input": 1.0, "output": 5.0},
            "usage_unit": "tokens",
        },
        "claude-sonnet-4-6": {
            "context_window": 1_000_000,
            "cost_per_million": {"input": 3.0, "output": 15.0},
            "usage_unit": "tokens",
        },
        "claude-opus-4-8": {
            "context_window": 1_000_000,
            "cost_per_million": {"input": 5.0, "output": 25.0},
            "usage_unit": "tokens",
        },
    }

    def __init__(self, api_key=None, model=None):
        self.api_key = api_key
        super().__init__(model)

    def to_messages(self, messages):
        result = []
        for msg in messages:
            if msg.role == "tool_result":
                result.append({
                    "role": "user",
                    "content": [{
                        "type": "tool_result",
                        "tool_use_id": msg.tool_use_id,
                        "content": msg.content,
                    }],
                })
            elif msg.role == "assistant":
                result.append({
                    "role": "assistant",
                    "content": _assistant_content(msg.content),
                })
            else:
                result.append({"role": str(msg.role), "content": msg.content})
        return result

    def to_tools(self, tools):
        return [
            {
                "name": tool.name,
                "description": tool.description,
                "input_schema": {
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
            "system": context.system,
            "max_tokens": max_output_tokens,
            "tools": tools if tools is not None else self.to_tools(context.tools),
            "messages": self.to_messages(context.messages),
        }

    def headers(self):
        return {
            "Content-Type": "application/json",
            "x-api-key": self.api_key,
            "anthropic-version": "2023-06-01",
        }

    def url(self):
        return self.BASE_URL

    def parse_response(self, response):
        stop_reason = "tool_use" if response.get("stop_reason") == "tool_use" else "end_turn"
        content = [_normalize_block(b) for b in (response.get("content") or [])]
        return {"stop_reason": stop_reason, "content": content}


def _normalize_block(block):
    t = block.get("type")
    if t == "thinking":
        return {
            "type": "reasoning",
            "text": str(block.get("thinking", "")),
            "signature": block.get("signature"),
        }
    elif t == "redacted_thinking":
        return {
            "type": "reasoning",
            "text": "",
            "redacted": True,
            "signature": block.get("data"),
        }
    return block


def _assistant_content(content):
    if isinstance(content, str):
        return content
    return [_denormalize_block(b) for b in content]


def _denormalize_block(block):
    if block.get("type") != "reasoning":
        return block
    if block.get("redacted"):
        return {"type": "redacted_thinking", "data": block.get("signature")}
    return {
        "type": "thinking",
        "thinking": str(block.get("text", "")),
        "signature": block.get("signature"),
    }
