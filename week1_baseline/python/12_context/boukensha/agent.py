from boukensha.errors import ApiError


MAX_ITERATIONS = 25
WRAP_UP_OUTPUT_TOKENS = 400
WRAP_UP_DIRECTIVE = (
    "You have reached your action limit for this turn. Do not call any more tools. "
    "Briefly summarize what you accomplished, what is still unfinished, and the "
    "single next action you would take."
)


class Agent:
    def __init__(self, context=None, registry=None, builder=None, client=None,
                 logger=None, max_iterations=None, max_turn_tokens=None,
                 max_output_tokens=None):
        self.context = context
        self.registry = registry
        self.builder = builder
        self.client = client
        self.logger = logger
        self.max_iterations = max(max_iterations or MAX_ITERATIONS, 0)
        self.max_turn_tokens = max_turn_tokens or 0
        self.max_output_tokens = max_output_tokens
        self.iteration = 0

    def run(self):
        self.context.reset_turn_tokens()
        self._compact_if_needed()

        while True:
            if self._iteration_limit_reached():
                self.logger.limit_reached(
                    kind="max_iterations", n=self.iteration, max=self.max_iterations
                )
                return self._wrap_up("max_iterations")

            if self._token_limit_reached():
                self.logger.limit_reached(
                    kind="max_tokens", n=self.context.turn_tokens,
                    max=self.max_turn_tokens,
                )
                return self._wrap_up("max_tokens")

            self.iteration += 1
            self.logger.iteration(n=self.iteration, max=self.max_iterations)
            self.logger.prompt(
                messages=self.context.messages,
                tools=self.context.tools,
                context_window=self.context.context_window,
            )

            response = self.client.call(**self._call_opts())
            self.logger.raw(data=response)
            parsed = self.builder.parse_response(response)
            self._record_usage(response)
            self._log_reasoning(parsed.get("content", []))

            if parsed.get("stop_reason") == "tool_use":
                result = self._handle_tool_calls(
                    parsed.get("content", []), response
                )
                if result is not None:
                    return result
            else:
                text = _extract_text(parsed.get("content", []))
                self.logger.response(
                    text=text, usage=response.get("usage"),
                    stop_reason=parsed.get("stop_reason"),
                )
                self.logger.turn_end(
                    reason="completed", iterations=self.iteration,
                    tokens=self.context.turn_tokens,
                )
                self.context.add_message("assistant", text)
                return text

    def _iteration_limit_reached(self):
        return self.max_iterations > 0 and self.iteration >= self.max_iterations

    def _token_limit_reached(self):
        return self.max_turn_tokens > 0 and self.context.turn_tokens >= self.max_turn_tokens

    def _call_opts(self):
        if self.max_output_tokens:
            return {"max_output_tokens": self.max_output_tokens}
        return {}

    def _record_usage(self, response):
        usage = response.get("usage") or {}
        self.context.add_turn_tokens(usage.get("input_tokens"), usage.get("output_tokens"))
        self.context.update_tokens(usage.get("input_tokens"))

    def _compact_if_needed(self):
        if not self.context.needs_compaction():
            return
        before = self.context.current_tokens
        dropped = self.context.compact_messages()
        self.logger.compaction(
            before=before, dropped=dropped,
            context_window=self.context.context_window,
        )

    def _wrap_up(self, reason):
        self.context.add_message("user", WRAP_UP_DIRECTIVE)
        response = self.client.call(tools=[], max_output_tokens=WRAP_UP_OUTPUT_TOKENS)
        parsed = self.builder.parse_response(response)
        text = _extract_text(parsed.get("content", []))
        if not text.strip():
            text = self._fallback_message(reason)
        self._record_usage(response)
        self.logger.response(
            text=text, usage=response.get("usage"),
            stop_reason=parsed.get("stop_reason"),
        )
        self.logger.turn_end(
            reason=reason, iterations=self.iteration,
            tokens=self.context.turn_tokens,
        )
        self.context.add_message("assistant", text)
        return text

    def _fallback_message(self, reason):
        return (
            f"I reached my {self.max_iterations}-action limit for this turn before "
            f"finishing ({reason}). Ask me to continue and I'll pick up from here."
        )

    def _log_reasoning(self, content):
        for block in content:
            if block.get("type") != "reasoning":
                continue
            redacted = block.get("redacted") is True
            text = str(block.get("text", ""))
            if not text.strip() and not redacted:
                continue
            self.logger.reasoning(text=text, redacted=redacted)

    def _handle_tool_calls(self, content, response):
        tool_calls = [b for b in content if b.get("type") == "tool_use"]

        preamble = _extract_text(content)
        if preamble.strip():
            self.logger.plan(text=preamble)
        self.logger.response(
            text=f"(tool use — {len(tool_calls)} call{'s' if len(tool_calls) != 1 else ''})",
            usage=response.get("usage"),
            stop_reason="tool_use",
        )

        self.context.add_message("assistant", content)

        for block in tool_calls:
            name = block["name"]
            args = block.get("input", {})
            use_id = block.get("id")

            self.logger.tool_call(name=name, args=args)
            try:
                result = self.registry.dispatch(name, args)
                self.logger.tool_result(name=name, result=result, ok=True)
            except Exception as e:
                result = f"ERROR: {type(e).__name__}: {e}"
                self.logger.tool_result(name=name, result=result, ok=False, error=str(e))

            self.context.add_message("tool_result", str(result), tool_use_id=use_id)


def _extract_text(content):
    return "\n".join(
        b["text"] for b in content if b.get("type") == "text"
    )
