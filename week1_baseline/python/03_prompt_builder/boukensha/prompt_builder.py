class PromptBuilder:
    def __init__(self, context, backend):
        self._context = context
        self._backend = backend

    def to_api_payload(self, max_output_tokens=1024):
        return self._backend.to_payload(self._context, max_output_tokens=max_output_tokens)

    def headers(self):
        return self._backend.headers()

    def url(self):
        return self._backend.url()
