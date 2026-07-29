import os
import sys

from boukensha.agent import Agent
from boukensha.backends.anthropic import Anthropic
from boukensha.backends.gemini import Gemini
from boukensha.backends.ollama import Ollama
from boukensha.backends.ollama_cloud import OllamaCloud
from boukensha.backends.opencode import OpenCode
from boukensha.backends.openai import OpenAI
from boukensha.client import Client
from boukensha.config import Config
from boukensha.context import Context
from boukensha.errors import ApiError, LoopError, UnknownToolError, UnsupportedModelError
from boukensha.logger import Logger
from boukensha.memory import MemoryStore
from boukensha.message import Message
from boukensha.models import context_window as resolve_context_window
from boukensha.prompt_builder import PromptBuilder
from boukensha.registry import Registry
from boukensha.repl import Repl
from boukensha.run_dsl import RunDSL
from boukensha.tool import Tool
from boukensha.tools import FileSystem, Shell, Mud
from boukensha.tracer import Tracer
from boukensha.opentelemetry import OtelExporter, _otel_enabled, DEFAULT_ENDPOINT as OTLP_DEFAULT_ENDPOINT
from boukensha.version import VERSION

try:
    from boukensha.tui import Tui
    _HAS_TUI = True
except ImportError:
    Tui = None  # type: ignore[assignment]
    _HAS_TUI = False

_boukensha_quiet = False
_boukensha_debug = False
_boukensha_config = None


def _get_config():
    global _boukensha_config
    if _boukensha_config is None:
        _boukensha_config = Config()
    return _boukensha_config


def quiet():
    global _boukensha_quiet
    _boukensha_quiet = True


def loud():
    global _boukensha_quiet
    _boukensha_quiet = False


def is_quiet():
    return _boukensha_quiet


def debug():
    global _boukensha_debug
    _boukensha_debug = True


def is_debug():
    return _boukensha_debug


_BACKEND_API_KEYS = {
    "anthropic": "ANTHROPIC_API_KEY",
    "openai": "OPENAI_API_KEY",
    "gemini": "GEMINI_API_KEY",
    "ollama_cloud": "OLLAMA_API_KEY",
    "opencode": "OPENCODE_API_KEY",
}

_BACKEND_CLASSES = {
    "anthropic": Anthropic,
    "openai": OpenAI,
    "gemini": Gemini,
    "ollama": Ollama,
    "ollama_cloud": OllamaCloud,
    "opencode": OpenCode,
}


def run(task, system=None, model=None, backend=None, api_key=None,
        ollama_host="http://localhost:11434", log=None, context_window=None,
        max_iterations=None, max_turn_tokens=None, max_output_tokens=None,
        working_dir=None, allowed_commands=None,
        shell_timeout=30, mud=None, hooks=None, *, block=None,
        trace_dir=None, memory_path=None, otel_endpoint=None):
    cfg = _get_config()

    if system is None:
        system = cfg.system_prompt
    if model is None:
        model = cfg.model()
    if backend is None:
        backend = cfg.provider_type()
    if context_window is None:
        context_window = resolve_context_window(model)

    api_key = api_key or os.environ.get(_BACKEND_API_KEYS.get(backend, ""))

    memory_store = MemoryStore(path=memory_path) if memory_path else None
    ctx = Context(
        system=system, context_window=context_window,
        working_dir=working_dir,
        compaction_threshold=cfg.agent_compaction_threshold(),
        memory_store=memory_store,
    )
    registry = Registry(ctx)

    if working_dir:
        FileSystem.register(registry, working_dir=working_dir)
        Shell.register(registry, working_dir=working_dir,
                       timeout=shell_timeout, allowed_commands=allowed_commands)

    resolved_mud = _resolve_mud(mud, cfg)
    if resolved_mud:
        Mud.register(registry, **resolved_mud)

    if block is not None:
        block(RunDSL(registry))

    backend_cls = _BACKEND_CLASSES.get(backend)
    if backend_cls is None:
        raise ValueError(
            f"Unknown backend {backend!r}. Use {', '.join(sorted(_BACKEND_CLASSES))}."
        )

    if backend == "ollama":
        be = backend_cls(model=model, host=ollama_host)
    else:
        be = backend_cls(api_key=api_key, model=model)

    builder = PromptBuilder(ctx, be)
    client = Client(builder)
    effective_max_iterations = max_iterations if max_iterations is not None else cfg.agent_max_iterations()
    effective_max_turn_tokens = max_turn_tokens if max_turn_tokens is not None else cfg.agent_max_turn_tokens()
    effective_max_output_tokens = max_output_tokens or cfg.agent_max_output_tokens()
    logger = Logger(log=log, snapshot={
        "max_iterations": effective_max_iterations,
        "max_turn_tokens": effective_max_turn_tokens,
        "max_output_tokens": effective_max_output_tokens,
        "context_window": context_window,
        "model": model,
        "provider": backend,
    })
    otel_enabled = _otel_enabled()
    otel_ep = otel_endpoint or (OTLP_DEFAULT_ENDPOINT if otel_enabled else None)
    tracer = Tracer(dir=trace_dir, otel_endpoint=otel_ep) if (trace_dir or otel_ep) else None
    agent = Agent(
        context=ctx, registry=registry, builder=builder, client=client,
        logger=logger, max_iterations=effective_max_iterations,
        max_turn_tokens=effective_max_turn_tokens,
        max_output_tokens=effective_max_output_tokens,
        hooks=hooks,
        tracer=tracer,
    )

    ctx.add_message("user", task)

    try:
        return agent.run()
    finally:
        if tracer:
            tracer.finish()
        if memory_store:
            memory_store.close()
        logger.close()


def repl(system=None, model=None, backend=None, api_key=None,
         ollama_host="http://localhost:11434", log=None, context_window=None,
         max_iterations=None, max_turn_tokens=None, max_output_tokens=None,
         working_dir=None, allowed_commands=None,
         shell_timeout=30, mud=None, tui=True, hooks=None, *, block=None,
         trace_dir=None, memory_path=None, otel_endpoint=None):
    if os.environ.get("BOUKENSHA_NO_TUI"):
        tui = False

    cfg = _get_config()

    if system is None:
        system = cfg.system_prompt
    if model is None:
        model = cfg.model()
    if backend is None:
        backend = cfg.provider_type()
    if context_window is None:
        context_window = resolve_context_window(model)

    api_key = api_key or os.environ.get(_BACKEND_API_KEYS.get(backend, ""))

    memory_store = MemoryStore(path=memory_path) if memory_path else None
    ctx = Context(
        system=system, context_window=context_window,
        working_dir=working_dir,
        compaction_threshold=cfg.agent_compaction_threshold(),
        memory_store=memory_store,
    )
    registry = Registry(ctx)

    if working_dir:
        FileSystem.register(registry, working_dir=working_dir)
        Shell.register(registry, working_dir=working_dir,
                       timeout=shell_timeout, allowed_commands=allowed_commands)

    resolved_mud = _resolve_mud(mud, cfg)
    if resolved_mud:
        Mud.register(registry, **resolved_mud)

    if block is not None:
        block(RunDSL(registry))

    backend_cls = _BACKEND_CLASSES.get(backend)
    if backend_cls is None:
        raise ValueError(
            f"Unknown backend {backend!r}. Use {', '.join(sorted(_BACKEND_CLASSES))}."
        )

    if backend == "ollama":
        be = backend_cls(model=model, host=ollama_host)
    else:
        be = backend_cls(api_key=api_key, model=model)

    builder = PromptBuilder(ctx, be)
    client = Client(builder)
    effective_max_iterations = max_iterations if max_iterations is not None else cfg.agent_max_iterations()
    effective_max_turn_tokens = max_turn_tokens if max_turn_tokens is not None else cfg.agent_max_turn_tokens()
    effective_max_output_tokens = max_output_tokens or cfg.agent_max_output_tokens()
    logger = Logger(log=log, snapshot={
        "max_iterations": effective_max_iterations,
        "max_turn_tokens": effective_max_turn_tokens,
        "max_output_tokens": effective_max_output_tokens,
        "context_window": context_window,
        "model": model,
        "provider": backend,
    })

    otel_enabled_repl = _otel_enabled()
    otel_ep_repl = otel_endpoint or (OTLP_DEFAULT_ENDPOINT if otel_enabled_repl else None)
    tracer = Tracer(dir=trace_dir, otel_endpoint=otel_ep_repl) if (trace_dir or otel_ep_repl) else None
    repl_instance = Repl(
        context=ctx, registry=registry, builder=builder, client=client,
        logger=logger, max_iterations=effective_max_iterations,
        max_turn_tokens=effective_max_turn_tokens,
        max_output_tokens=effective_max_output_tokens,
        config_dir=cfg.dir, provider=backend, model=model,
        version=VERSION, api_key=api_key, mud=resolved_mud,
        hooks=hooks, tracer=tracer,
    )

    try:
        if tui and _HAS_TUI:
            Tui(repl_instance).start()
        else:
            repl_instance.start()
    except KeyboardInterrupt:
        print("\nInterrupted.")
    finally:
        logger.close()


def _resolve_mud(mud, cfg):
    if mud is False:
        return None
    if mud is True or mud is None:
        if cfg.mud_host() and cfg.mud_username():
            return {
                "host": cfg.mud_host(),
                "port": cfg.mud_port(),
                "name": cfg.mud_username(),
                "password": cfg.mud_password(),
            }
        return None
    return mud


__all__ = [
    "Agent", "Anthropic", "Client", "Config", "Context", "Gemini", "Logger",
    "MemoryStore", "Message", "Ollama", "OllamaCloud", "OpenAI", "OpenCode",
    "PromptBuilder", "Registry", "Repl", "RunDSL", "Tool", "Tracer", "Tui",
    "VERSION",
    "ApiError", "LoopError", "UnknownToolError", "UnsupportedModelError",
    "FileSystem", "Mud", "Shell",
    "quiet", "loud", "is_quiet", "debug", "is_debug", "run", "repl",
]
