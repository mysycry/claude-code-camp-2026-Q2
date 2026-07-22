class PromptBuilder:
    def __init__(self, context, backend):
        self._context = context
        self._backend = backend

    def to_api_payload(self, max_output_tokens=1024, tools=None):
        return self._backend.to_payload(self._context, max_output_tokens=max_output_tokens, tools=tools)

    def parse_response(self, response):
        return self._backend.parse_response(response)

    def headers(self):
        return self._backend.headers()

    def url(self):
        return self._backend.url()
