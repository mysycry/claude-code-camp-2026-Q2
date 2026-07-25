from boukensha.backends.base import Base


class Gemini(Base):
    BASE_URL = "https://generativelanguage.googleapis.com/v1beta/models"
    MODELS = {
        "gemini-3.5-flash": {
            "context_window": 1_048_576,
            "cost_per_million": {"input": 1.5, "output": 9.0},
            "usage_unit": "tokens",
        },
        "gemini-3.1-flash-lite": {
            "context_window": 1_048_576,
            "cost_per_million": {"input": 0.25, "output": 1.5},
            "usage_unit": "tokens",
        },
    }

    def __init__(self, api_key=None, model=None):
        self.api_key = api_key
        super().__init__(model)

    def to_messages(self, messages):
        result = []
        for msg in messages:
            if msg.role == "assistant":
                result.append({"role": "model", "parts": _assistant_parts(msg.content)})
            elif msg.role == "tool_result":
                result.append({
                    "role": "user",
                    "parts": [{
                        "functionResponse": {
                            "name": msg.tool_use_id,
                            "response": {"content": msg.content},
                        },
                    }],
                })
            else:
                result.append({"role": str(msg.role), "parts": [{"text": msg.content}]})
        return result

    def to_tools(self, tools):
        if not tools:
            return []
        return [{
            "functionDeclarations": [
                {
                    "name": tool.name,
                    "description": tool.description,
                    "parameters": {
                        "type": "object",
                        "properties": tool.parameters,
                        "required": list(tool.parameters.keys()),
                    },
                }
                for tool in tools.values()
            ],
        }]

    def to_payload(self, context, max_output_tokens=1024, tools=None):
        return {
            "systemInstruction": {"parts": [{"text": context.system}]},
            "contents": self.to_messages(context.messages),
            "tools": tools if tools is not None else self.to_tools(context.tools),
            "generationConfig": {
                "maxOutputTokens": max_output_tokens,
                "thinkingConfig": _thinking_config(self.model),
            },
        }

    def headers(self):
        return {
            "Content-Type": "application/json",
            "x-goog-api-key": self.api_key,
        }

    def url(self):
        return f"{self.BASE_URL}/{self.model}:generateContent"

    def parse_response(self, response):
        parts = (
            response.get("candidates", [{}])[0]
            .get("content", {})
            .get("parts", [])
        )
        content = []
        tool_used = False
        for part in parts:
            fc = part.get("functionCall")
            if fc:
                entry = {
                    "type": "tool_use",
                    "id": fc["name"],
                    "name": fc["name"],
                    "input": fc.get("args", {}),
                }
                if part.get("thoughtSignature"):
                    entry["signature"] = part["thoughtSignature"]
                content.append(entry)
                tool_used = True
            elif part.get("thought"):
                entry = {
                    "type": "reasoning",
                    "text": str(part.get("text", "")),
                }
                if part.get("thoughtSignature"):
                    entry["signature"] = part["thoughtSignature"]
                content.append(entry)
            elif part.get("text"):
                content.append({"type": "text", "text": part["text"]})
        return {
            "stop_reason": "tool_use" if tool_used else "end_turn",
            "content": content,
        }


def _thinking_config(model):
    if model == "gemini-3.1-pro-preview-customtools":
        return {"thinkingLevel": "LOW"}
    return {"thinkingBudget": 0}


def _assistant_parts(content):
    blocks = content if isinstance(content, list) else [{"type": "text", "text": content}]
    result = []
    for b in blocks:
        if b.get("type") == "tool_use":
            part = {"functionCall": {"name": b["name"], "args": b.get("input", {})}}
            if b.get("signature"):
                part["thoughtSignature"] = b["signature"]
            result.append(part)
        elif b.get("type") == "reasoning":
            part = {"text": str(b.get("text", "")), "thought": True}
            if b.get("signature"):
                part["thoughtSignature"] = b["signature"]
            result.append(part)
        else:
            result.append({"text": b.get("text", "")})
    return result
