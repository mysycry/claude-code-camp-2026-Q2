from boukensha.backends.ollama import Ollama


class OllamaCloud(Ollama):
    MODELS = {
        "gemma4:31b-cloud": {
            "context_window": 1_000_000,
            "cost_per_million": {"input": 0.0, "output": 0.0},
            "usage_unit": "tokens",
        },
        "kimi-k2.5:cloud": {
            "context_window": 1_000_000,
            "cost_per_million": {"input": 0.0, "output": 0.0},
            "usage_unit": "tokens",
        },
        "minimax-m3:cloud": {
            "context_window": 1_000_000,
            "cost_per_million": {"input": 0.0, "output": 0.0},
            "usage_unit": "tokens",
        },
    }
    OLLAMA_CLOUD_BASE_URL = "https://cloud.ollama.com"

    def __init__(self, api_key=None, model=None):
        super().__init__(model=model, host=None)
        self.api_key = api_key

    def to_payload(self, context, max_output_tokens=1024, tools=None):
        payload = super().to_payload(context, max_output_tokens=max_output_tokens, tools=tools)
        payload["think"] = False
        return payload

    def headers(self):
        return {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
        }

    def url(self):
        return f"{self.OLLAMA_CLOUD_BASE_URL}/api/chat"
