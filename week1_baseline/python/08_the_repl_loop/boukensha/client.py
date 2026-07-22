import json
import ssl
import time
import urllib.error
import urllib.request

from boukensha.errors import ApiError

RETRYABLE_STATUS_CODES = {408, 409, 429, 500, 502, 503, 504}
TRANSIENT_ERRORS = (
    ConnectionError,
    ConnectionResetError,
    ConnectionRefusedError,
    TimeoutError,
    ssl.SSLError,
)
MAX_RETRIES = 3
BASE_RETRY_DELAY = 0.5


class Client:
    def __init__(self, builder):
        self._builder = builder

    def call(self, max_output_tokens=1024, tools=None):
        url = self._builder.url()
        data = json.dumps(self._builder.to_api_payload(max_output_tokens=max_output_tokens, tools=tools)).encode("utf-8")
        headers = self._builder.headers()

        safe_headers = dict(headers)
        safe_headers.setdefault("User-Agent", "boukensha/0.1.0")
        req = urllib.request.Request(url, data=data, headers=safe_headers, method="POST")

        context = None
        if url.startswith("https"):
            context = ssl.create_default_context()

        attempts = 0
        while True:
            attempts += 1
            try:
                response = urllib.request.urlopen(req, context=context, timeout=60)
                body = response.read().decode("utf-8")
                return json.loads(body)
            except tuple(TRANSIENT_ERRORS) as e:
                if attempts > MAX_RETRIES:
                    raise ApiError(
                        f"API request failed after {attempts} attempts: {type(e).__name__}: {e}"
                    ) from e
                time.sleep(_retry_delay(attempts))
            except urllib.error.HTTPError as e:
                if e.code in RETRYABLE_STATUS_CODES and attempts <= MAX_RETRIES:
                    time.sleep(_retry_delay(attempts))
                    continue
                body = e.read().decode("utf-8", errors="replace")
                raise ApiError(
                    f"API request failed after {attempts} attempt{'s' if attempts != 1 else ''} ({e.code}): {body}"
                ) from e


def _retry_delay(attempt):
    return BASE_RETRY_DELAY * (2 ** (attempt - 1))
