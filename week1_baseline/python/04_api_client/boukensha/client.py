import json
import socket
import ssl
import time
import urllib.error
import urllib.request

from boukensha.errors import ApiError


class Client:
    RETRYABLE_STATUS_CODES = (408, 409, 429, 500, 502, 503, 504)
    TRANSIENT_ERRORS = (
        urllib.error.URLError,
        ConnectionError,
        TimeoutError,
        ssl.SSLError,
        OSError,
    )
    MAX_RETRIES = 3
    BASE_RETRY_DELAY = 0.5
    USER_AGENT = "boukensha/0.1.0"

    def __init__(self, builder):
        self._builder = builder

    def call(self, max_output_tokens=1024):
        url = self._builder.url()
        headers = dict(self._builder.headers())
        headers.setdefault("User-Agent", self.USER_AGENT)

        payload = self._builder.to_api_payload(max_output_tokens=max_output_tokens)
        data = json.dumps(payload).encode("utf-8")

        ssl_ctx = ssl.create_default_context()

        for attempt in range(1, self.MAX_RETRIES + 2):
            try:
                req = urllib.request.Request(url, data=data, headers=headers, method="POST")
                with urllib.request.urlopen(req, context=ssl_ctx, timeout=30) as resp:
                    body = resp.read().decode("utf-8")
                    if resp.status in self.RETRYABLE_STATUS_CODES and attempt <= self.MAX_RETRIES:
                        time.sleep(self._retry_delay(attempt))
                        continue
                    if resp.status >= 400:
                        raise ApiError(
                            f"API request failed after {attempt} attempt{'s' if attempt != 1 else ''} ({resp.status}): {body}"
                        )
                    return json.loads(body)
            except urllib.error.HTTPError as e:
                status = e.code
                error_body = e.read().decode("utf-8", errors="replace")
                if status in self.RETRYABLE_STATUS_CODES and attempt <= self.MAX_RETRIES:
                    time.sleep(self._retry_delay(attempt))
                    continue
                raise ApiError(
                    f"API request failed after {attempt} attempt{'s' if attempt != 1 else ''} ({status}): {error_body}"
                )
            except self.TRANSIENT_ERRORS as e:
                if attempt > self.MAX_RETRIES:
                    raise ApiError(
                        f"API request failed after {attempt} attempts: {type(e).__name__}: {e}"
                    )
                time.sleep(self._retry_delay(attempt))

    @staticmethod
    def _retry_delay(attempt):
        return Client.BASE_RETRY_DELAY * (2 ** (attempt - 1))
