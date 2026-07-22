from boukensha.errors import ApiError
from boukensha.logger import Logger

MAX_ITERATIONS = 25
WRAP_UP_OUTPUT_TOKENS = 400
WRAP_UP_DIRECTIVE = (
    "You have reached your action limit for this turn. Do not call any more tools.\n"
    "Briefly summarize what you accomplished, what is still unfinished, and the\n"
    "single next action you would take."
)


class Agent:
    def __init__(self, *, context, registry, builder, client, logger=None,
                 task_settings=None, max_iterations=None, max_output_tokens=None):
        self._context = context
        self._registry = registry
        self._builder = builder
        self._client = client
        self._logger = logger or Logger()
        self._max_iterations = self._resolve_max_iterations(task_settings, max_iterations)
        self._max_output_tokens = self._resolve_max_output_tokens(task_settings, max_output_tokens)
        self._iteration = 0

    def run(self):
        while True:
            if self._iteration_limit_reached():
                self._logger.limit_reached(kind="max_iterations", n=self._iteration, max=self._max_iterations)
                return self._wrap_up("max_iterations")

            self._iteration += 1
            self._logger.iteration(n=self._iteration, max=self._max_iterations)
            self._logger.prompt(messages=self._context.messages, tools=self._context.tools)

            response = self._client.call(**self._call_opts())
            self._logger.raw(data=response)
            parsed = self._builder.parse_response(response)

            if parsed["stop_reason"] == "tool_use":
                self._handle_tool_calls(parsed["content"], response)
            else:
                text = self._extract_text(parsed["content"])
                self._log_response(text=text, response=response)
                self._logger.turn_end(reason="completed", iterations=self._iteration)
                return text

    def _resolve_max_iterations(self, task_settings, explicit):
        if explicit is not None:
            return int(explicit)
        if task_settings and hasattr(self._context.task, "max_iterations"):
            return self._context.task.max_iterations(task_settings)
        return MAX_ITERATIONS

    def _resolve_max_output_tokens(self, task_settings, explicit):
        if explicit is not None:
            return explicit
        if task_settings and hasattr(self._context.task, "max_output_tokens"):
            return self._context.task.max_output_tokens(task_settings)
        return None

    def _iteration_limit_reached(self):
        return self._max_iterations > 0 and self._iteration >= self._max_iterations

    def _call_opts(self):
        opts = {}
        if self._max_output_tokens is not None:
            opts["max_output_tokens"] = self._max_output_tokens
        return opts

    def _wrap_up(self, reason):
        self._context.add_message("user", WRAP_UP_DIRECTIVE)
        try:
            response = self._client.call(tools=[], max_output_tokens=WRAP_UP_OUTPUT_TOKENS)
            text = self._extract_text(self._builder.parse_response(response)["content"])
            text = self._fallback_message(reason) if not text.strip() else text
            self._log_response(text=text, response=response)
            self._logger.turn_end(reason=reason, iterations=self._iteration)
            return text
        except ApiError:
            msg = self._fallback_message(reason)
            self._logger.turn_end(reason=reason, iterations=self._iteration)
            return msg

    def _fallback_message(self, reason):
        return (
            f"I reached my {self._max_iterations}-action limit for this turn before finishing "
            f"({reason}). Ask me to continue and I'll pick up from here."
        )

    def _extract_text(self, content):
        return "".join(b["text"] for b in content if b.get("type") == "text")

    def _handle_tool_calls(self, content, response):
        tool_calls = [b for b in content if b.get("type") == "tool_use"]

        reasoning = self._extract_text(content)
        if reasoning.strip():
            log_text = reasoning
        else:
            log_text = f"(tool use — {len(tool_calls)} call{'s' if len(tool_calls) != 1 else ''})"
        self._log_response(text=log_text, response=response)

        self._context.add_message("assistant", content)

        for block in tool_calls:
            name = block["name"]
            args = block["input"]
            use_id = block["id"]

            self._logger.tool_call(name=name, args=args)
            try:
                result = self._registry.dispatch(name, args)
                self._logger.tool_result(name=name, result=result, ok=True)
            except Exception as e:
                result = f"ERROR: {type(e).__name__}: {e}"
                self._logger.tool_result(name=name, result=result, ok=False, error=str(e))

            self._context.add_message("tool_result", str(result), tool_use_id=use_id)

    def _log_response(self, text, response):
        self._logger.response(
            text=text,
            usage=self._normalized_usage(response),
            stop_reason=response.get("stop_reason"),
            task=self._context.task,
            backend=self._builder.backend,
        )

    def _normalized_usage(self, response):
        if "usage" in response:
            return response["usage"]
        if "usageMetadata" in response:
            return response["usageMetadata"]
        usage = {}
        for key in ("prompt_eval_count", "eval_count"):
            if key in response:
                usage[key] = response[key]
        return usage if usage else None
