from boukensha.errors import ApiError


class _NullSpanContext:
    def __enter__(self): return self
    def __exit__(self, *a): pass
    def ok(self, **kw): pass
    def fail(self, msg, **kw): pass


class _SpanContext:
    def __init__(self, tracer, span_id):
        self.tracer = tracer
        self.span_id = span_id
    def __enter__(self): return self
    def __exit__(self, typ, val, tb):
        if typ is not None:
            self.tracer.end_span(self.span_id, "error", str(val))
        else:
            self.tracer.end_span(self.span_id, "ok")
    def ok(self, metadata=None):
        self.tracer.end_span(self.span_id, "ok", metadata=metadata or {})
    def fail(self, msg):
        self.tracer.end_span(self.span_id, "error", msg)


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
                 max_output_tokens=None, hooks=None, tracer=None):
        self.context = context
        self.registry = registry
        self.builder = builder
        self.client = client
        self.logger = logger
        self.max_iterations = max(max_iterations or MAX_ITERATIONS, 0)
        self.max_turn_tokens = max_turn_tokens or 0
        self.max_output_tokens = max_output_tokens
        self.iteration = 0
        self.hooks = hooks or {}
        self.tracer = tracer

    def _run_hook(self, name, *args):
        fn = self.hooks.get(name)
        if fn is not None:
            try:
                fn(*args)
            except Exception as e:
                self.logger.raw(data={"hook_error": name, "exception": f"{type(e).__name__}: {e}"})

    def _trace(self, name, phase):
        if self.tracer is None:
            return _NullSpanContext()
        span_id = self.tracer.start_span(name, phase)
        return _SpanContext(self.tracer, span_id)

    def run(self):
        with self._trace("turn", "turn") as turn_span:
            return self._run_with_trace(turn_span)

    def _run_with_trace(self, turn_span):
        self.context.reset_turn_tokens()
        self.context.inject_here_block()
        compacted = self._compact_if_needed()
        self._run_hook("before_turn", self.context)

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

            call_opts = self._call_opts()
            self._run_hook("before_model", self.context, call_opts)

            with self._trace("llm_call", "llm") as llm_span:
                try:
                    response = self.client.call(**call_opts)
                    llm_span.ok(metadata={
                        "stop_reason": response.get("stop_reason"),
                        "usage": response.get("usage"),
                    })
                except Exception as e:
                    llm_span.fail(str(e))
                    raise

            self.logger.raw(data=response)
            parsed = self.builder.parse_response(response)
            self._run_hook("after_model", self.context, response, parsed)
            self._record_usage(response)
            self._log_reasoning(parsed.get("content", []))

            if parsed.get("stop_reason") == "tool_use":
                with self._trace("tool_loop", "tools") as tools_span:
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
                self._run_hook("after_turn", self.context, text)
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
        with self._trace("compaction", "compaction") as span:
            before = self.context.current_tokens
            dropped = self.context.compact_messages()
            self.logger.compaction(
                before=before, dropped=dropped,
                context_window=self.context.context_window,
            )
            span.ok(metadata={
                "before": before, "dropped": dropped,
                "after": self.context.current_tokens,
            })

    def _wrap_up(self, reason):
        with self._trace("wrap_up", "wrap_up") as span:
            self.context.add_message("user", WRAP_UP_DIRECTIVE)
            wrap_opts = {"tools": [], "max_output_tokens": WRAP_UP_OUTPUT_TOKENS}
            self._run_hook("before_model", self.context, wrap_opts)
            try:
                response = self.client.call(**wrap_opts)
            except Exception as e:
                span.fail(str(e))
                raise
            parsed = self.builder.parse_response(response)
            self._run_hook("after_model", self.context, response, parsed)
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
            self._run_hook("after_turn", self.context, text)
            span.ok(metadata={"reason": reason, "iterations": self.iteration})
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

            with self._trace(f"tool/{name}", "tool") as tool_span:
                self._run_hook("before_tool", self.context, name, args)
                self.logger.tool_call(name=name, args=args)
                error = None
                try:
                    result = self.registry.dispatch(name, args)
                    self.logger.tool_result(name=name, result=result, ok=True)
                except Exception as e:
                    error = e
                    result = f"ERROR: {type(e).__name__}: {e}"
                    self.logger.tool_result(name=name, result=result, ok=False, error=str(e))
                    tool_span.fail(str(e))
                self._run_hook("after_tool", self.context, name, args, result, error)

                self.context.add_message("tool_result", str(result), tool_use_id=use_id)


def _extract_text(content):
    return "\n".join(
        b["text"] for b in content if b.get("type") == "text"
    )
